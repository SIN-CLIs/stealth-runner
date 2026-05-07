"""Pre-drag hit-test: the missing piece in every captcha solver.

WARUM: Root-Cause des "CGEvent fires on document but not on element" Bugs:
Ein SVG/Canvas-Overlay mit pointer-events:auto sitzt über dem Captcha-Block
und absorbiert Mouse-Events bevor sie .gc-drag-block erreichen.
Ohne Hit-Test wird der Drag ins Leere gefeuert → Captcha-Fail.

ARCHITEKTUR: 3-Stufen-Fix via CDP Runtime.evaluate:
  1. elementFromPoint() am Block-Center ausführen
  2. Vom getroffenen Element den DOM-Tree hochwalken
  3. pointer-events auf Blocker(s) temporär auf "none" setzen
Nach Drag wird pointer-events wiederhergestellt.
Keine Koordinaten-Raten, keine blinden Clicks.

BANNED METHODS — NIEMALS VERWENDEN:
❌ playstealth launch
❌ webauto-nodriver — ABSOLUT BANNED
❌ cua-driver click (raw index)
❌ --remote-allow-origins=* (ohne Quotes)
❌ /tmp/heypiggy-bot (fixed profile)
❌ Hardcoded PIDs
❌ pkill -f "Google Chrome"
❌ killall Google Chrome
❌ skylight-cli click --element-index
  4. Returns an opaque token for restoring after the drag

Without this step, NO event dispatch method (CGEvent, JS dispatchEvent,
or CDP Input.dispatchMouseEvent) will reach the captcha element.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from stealth_captcha.cdp.client import CDPSession
from stealth_captcha.exceptions import HitTestError
from stealth_captcha.telemetry import get_logger

log = get_logger(__name__)


@dataclass(slots=True, frozen=True)
class NeutralizedOverlay:
    """A DOM element whose pointer-events were temporarily disabled."""

    tag: str
    selector: str
    token: str


@dataclass(slots=True, frozen=True)
class HitTestResult:
    """Result of a successful hit-test with optional overlay neutralization."""

    target_selector: str
    center: tuple[float, float]
    target_box: tuple[float, float, float, float]  # x, y, w, h
    target_is_topmost: bool
    neutralized_overlays: tuple[NeutralizedOverlay, ...]


# ── JS expression injected into the page ─────────────────────────────────
# This runs elementFromPoint, detects blockers, neutralizes them, and
# re-checks. Returns a JSON object with all necessary data.
_HIT_TEST_JS = r"""
(() => {
  const sel = %s;
  const el = document.querySelector(sel);
  if (!el) return { ok: false, error: 'target_not_found' };

  // Scroll into view
  el.scrollIntoView({ block: 'center', inline: 'center', behavior: 'instant' });

  const r = el.getBoundingClientRect();
  const cx = r.left + r.width / 2;
  const cy = r.top + r.height / 2;

  // elementFromPoint at the block's center
  const top = document.elementFromPoint(cx, cy);
  if (!top) return { ok: false, error: 'no_element_at_point', center: [cx, cy] };

  const isTarget = (top === el) || el.contains(top) || (top && top.contains(el));
  const neutralized = [];

  if (!isTarget) {
    // Walk up from the blocker, disabling pointer-events
    let walker = top;
    let guard = 0;
    while (walker && walker !== document.body && walker !== el && !el.contains(walker) && guard < 20) {
      const cs = getComputedStyle(walker);
      if (cs.pointerEvents !== 'none') {
        const token = '__st_' + Math.random().toString(36).slice(2, 10);
        const tag = walker.tagName + (walker.id ? '#' + walker.id : '') +
                    (walker.className && typeof walker.className === 'string'
                      ? '.' + walker.className.trim().split(/\s+/).join('.') : '');
        walker.dataset[token] = cs.pointerEvents || 'auto';
        walker.style.setProperty('pointer-events', 'none', 'important');
        neutralized.push({ tag, token });
        // Only neutralize the first blocker (usually the right one)
        break;
      }
      walker = walker.parentElement;
      guard++;
    }
  }

  // Re-check after neutralization
  const top2 = document.elementFromPoint(cx, cy);
  const nowTarget = (top2 === el) || el.contains(top2) || (top2 && top2.contains(el));

  return {
    ok: true,
    center: [cx, cy],
    box: [r.left, r.top, r.width, r.height],
    isTopmost: nowTarget,
    neutralized: neutralized,
  };
})()
"""

_RESTORE_JS = r"""
(() => {
  const tokens = %s;
  for (const token of tokens) {
    const attr = 'data-' + token.toLowerCase();
    const els = document.querySelectorAll('[' + attr + ']');
    for (const el of els) {
      const orig = el.dataset[token];
      el.style.pointerEvents = (!orig || orig === 'auto') ? '' : orig;
      delete el.dataset[token];
    }
  }
  return true;
})()
"""


@dataclass(slots=True)
class HitTester:
    """Ensures the captcha target element is the topmost at its center point.

    Usage:
        hit = HitTester(session)
        result = await hit.ensure_topmost(".gc-drag-block")
        # ... do drag ...
        await hit.restore(result)
    """

    session: CDPSession

    async def ensure_topmost(self, target_selector: str) -> HitTestResult:
        """Check and (if needed) fix elementFromPoint for the target.

        Args:
            target_selector: CSS selector for the captcha drag block.

        Returns:
            HitTestResult with center coordinates and any neutralized overlays.

        Raises:
            HitTestError: if the target is not found or cannot be made topmost.
        """
        expr = _HIT_TEST_JS % json.dumps(target_selector)
        result = await self._eval(expr)

        if not result or not result.get("ok"):
            raise HitTestError(
                f"Cannot make '{target_selector}' topmost: {result.get('error', 'unknown')}"
            )

        center = tuple(result["center"])
        box = tuple(result["box"])
        is_topmost = bool(result.get("isTopmost", False))
        overlays = tuple(
            NeutralizedOverlay(
                tag=o["tag"],
                selector=f'[data-{o["token"].lower()}]',
                token=o["token"],
            )
            for o in result.get("neutralized", [])
        )

        if not is_topmost:
            log.warning(
                "hit_test_neutralized_overlay",
                selector=target_selector,
                overlays=[o.tag for o in overlays],
            )

        log.info(
            "hit_test_result",
            selector=target_selector,
            topmost=is_topmost,
            overlays=len(overlays),
        )

        return HitTestResult(
            target_selector=target_selector,
            center=(float(center[0]), float(center[1])),
            target_box=(float(box[0]), float(box[1]), float(box[2]), float(box[3])),
            target_is_topmost=is_topmost,
            neutralized_overlays=overlays,
        )

    async def restore(self, hit: HitTestResult) -> None:
        """Restore pointer-events on any neutralized overlays."""
        if not hit.neutralized_overlays:
            return
        tokens = [o.token for o in hit.neutralized_overlays]
        await self._eval(_RESTORE_JS % json.dumps(tokens))
        log.info("hit_test_restored", count=len(tokens))

    async def _eval(self, expression: str) -> dict[str, Any]:
        """Evaluate JS in the page and return parsed JSON dict."""
        result = await self.session.send(
            "Runtime.evaluate",
            {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": False,
            },
        )
        exception = result.get("exceptionDetails")
        if exception:
            raise HitTestError(
                f"Hit-test JS threw: {exception.get('text', '')} "
                f"at line {exception.get('lineNumber')}"
            )
        value = result.get("result", {}).get("value") or {}
        if isinstance(value, dict):
            return value
        raise HitTestError(f"Hit-test returned unexpected type: {type(value).__name__}")
