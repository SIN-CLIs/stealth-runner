"""DOM-based gap detection — 100x more accurate than vision models.

WARUM: Vision-Modelle können KEINE präzisen Pixel-Koordinaten liefern
(CAPTCHA-X Research, siehe py-packages/research/). Ein Drag um 5 Pixel
zu wenig → Captcha-Fail. getBoundingClientRect() ist Ground-Truth.
Dieses Modul berechnet den exakten Offset aus DOM-Element-Positionen.

ARCHITEKTUR: Runtime.evaluate ruft getBoundingClientRect() auf block + target.
Berechnung: delta_x = target_center.x - block_center.x.
Selektoren sind konfigurierbar (Provider-Agnostic):
  - GoCaptcha:   .gc-drag-block → .gc-drag-target
  - NetEase:     .yidun--block → .yidun--target
  - GeeTest:     .gt_slider_knob → .gt_slice
Keine Vision-API, keine Kosten, keine Latenz.

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
  - NetEase:     .yidun_slider → .yidun_slide-target
  - GeeTest v3:  .gt_slider_knob → .gt_slider_bg
  - GeeTest v4:  .geetest_slider_button → .geetest_slider_bg
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from stealth_captcha.cdp.client import CDPSession
from stealth_captcha.exceptions import GapDetectionError
from stealth_captcha.telemetry import get_logger

log = get_logger(__name__)


@dataclass(slots=True, frozen=True)
class GapGeometry:
    """The measured gap between drag block and target.

    Attributes:
        block_box: (x, y, w, h) of the drag block.
        target_box: (x, y, w, h) of the target zone.
        block_center: (x, y) center of the drag block.
        target_center: (x, y) center of the target zone.
        delta_x: pixels to move horizontally (target_center.x - block_center.x).
        delta_y: pixels to move vertically (target_center.y - block_center.y).
    """

    block_box: tuple[float, float, float, float]
    target_box: tuple[float, float, float, float]
    block_center: tuple[float, float]
    target_center: tuple[float, float]
    delta_x: float
    delta_y: float


# JS snippet: runs getBoundingClientRect on block and target
_GAP_JS = r"""
(() => {
  const blockSel = %s;
  const targetSel = %s;
  const block = document.querySelector(blockSel);
  const target = document.querySelector(targetSel);
  if (!block) return { ok: false, reason: 'block_not_found: ' + blockSel };
  if (!target) return { ok: false, reason: 'target_not_found: ' + targetSel };
  const b = block.getBoundingClientRect();
  const t = target.getBoundingClientRect();
  return {
    ok: true,
    block: [b.left, b.top, b.width, b.height],
    target: [t.left, t.top, t.width, t.height],
  };
})()
"""


@dataclass(slots=True)
class GapDetector:
    """Detect the drag offset by reading DOM bounding rects.

    Usage:
        detector = GapDetector(session)
        gap = await detector.detect()
        print(f"Drag {gap.delta_x:.0f}px right, {gap.delta_y:.0f}px down")
    """

    session: CDPSession
    block_selector: str = ".gc-drag-block"
    target_selector: str = ".gc-drag-target"

    async def detect(self) -> GapGeometry:
        """Measure the gap from block to target.

        Returns:
            GapGeometry with pixel-precise delta.

        Raises:
            GapDetectionError: if the block or target cannot be found in the DOM.
        """
        expr = _GAP_JS % (
            json.dumps(self.block_selector),
            json.dumps(self.target_selector),
        )
        res = await self._eval(expr)

        if not res or not res.get("ok"):
            raise GapDetectionError(
                f"Gap detection failed: {res.get('reason') if res else 'empty result'}"
            )

        b = res["block"]
        t = res["target"]

        bcx = b[0] + b[2] / 2
        bcy = b[1] + b[3] / 2
        tcx = t[0] + t[2] / 2
        tcy = t[1] + t[3] / 2

        gap = GapGeometry(
            block_box=(b[0], b[1], b[2], b[3]),
            target_box=(t[0], t[1], t[2], t[3]),
            block_center=(bcx, bcy),
            target_center=(tcx, tcy),
            delta_x=tcx - bcx,
            delta_y=tcy - bcy,
        )

        log.info(
            "gap_detected",
            delta_x=round(gap.delta_x, 1),
            delta_y=round(gap.delta_y, 1),
        )
        return gap

    async def _eval(self, expression: str) -> dict[str, Any]:
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
            raise GapDetectionError(
                f"Gap-detect JS threw: {exception.get('text', '')} "
                f"at line {exception.get('lineNumber')}"
            )
        return result.get("result", {}).get("value") or {}
