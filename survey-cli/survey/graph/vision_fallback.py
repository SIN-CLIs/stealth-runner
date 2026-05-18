"""================================================================================
VISION FALLBACK — Set-of-Mark perception layer for the decide node [SR-239]
================================================================================

WHAT THIS MODULE IS
-------------------
A small, isolated, optional helper that the survey graph's `decide_node`
can call when the DOM-only path runs out of plausible options.

For every iteration the graph already builds `state.universal_elements`
from the AX tree. Most of the time the LLM (Nemotron-3) plus the
heuristic fallback can pick a sensible click target straight from those
elements. They cannot when:

  * the AX tree is empty or unhelpful (Shadow DOM 3+ layers deep, custom
    web components that don't expose semantics),
  * the relevant control is rendered on a `<canvas>` (drawing-based
    forms, signature widgets, hotspot questions),
  * the page changed visually but the DOM did not (`no_dom_change_count
    >= 1` after a click that should have advanced).

For exactly those cases we have a Vision-LLM (Qwen2.5-VL on NVIDIA NIM)
already wired up by `survey/captcha/nim_secondary_solver.py`. The trick
is reusing it as a *general* perception layer with a Set-of-Mark
overlay — number every candidate region on the screenshot, ask the
model "which mark should I click", parse a bounded integer back.

DESIGN GUARDRAILS
-----------------
1. **Pure helpers, no imports of networking libraries at module load.**
   Everything is testable on a sandbox without the OpenAI / NIM client
   installed; the actual VLM call is hidden behind a `VisionBackend`
   protocol that the test suite stubs out.
2. **No mutation of state inside the helpers.** `decide_node` decides
   whether to call us and what to do with the result. We only return
   structured data.
3. **Conservative trigger.** We only ever recommend running the VLM
   when the DOM path is genuinely lost. False positives cost real
   tokens; missing the trigger costs 1 iteration of the loop, which is
   recoverable.
4. **Coordinate output, NOT new selectors.** The result is either an
   existing `stable_id` (the mark we drew on top of an existing AX
   element) OR raw `(x, y)` page coordinates that `cdp_actuator.click_at`
   can consume. We never invent a CSS selector — that's the bug we are
   here to avoid.

PUBLIC API
----------
- `should_use_vision_fallback(state) -> bool`
- `build_set_of_mark(elements, viewport=...) -> SetOfMarkPlan`
- `parse_vlm_response(raw, plan) -> VisionDecision | None`
- `VisionBackend` protocol — the seam the real Qwen2.5-VL client plugs
  into.

The helper that wires it all together (`run_vision_fallback`) takes a
`VisionBackend` instance and returns a `VisionDecision`. The default
backend is built lazily and only when actually needed; sandbox /
testing code passes its own.

WHY HERE AND NOT IN nodes.py?
-----------------------------
`nodes.py` is already 1.5k lines. Putting the fallback logic next door
keeps that file small enough to read, and lets us own the test surface
in `tests/test_vision_fallback.py` cleanly.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional, Protocol, Sequence

logger = logging.getLogger(__name__)

# ── Triggering ────────────────────────────────────────────────────────────────


# When the DOM-only decide path produced no plausible candidate AND the
# previous iteration's click did not move the DOM, we fall back to vision.
# Threshold = 1 (not 2!) because the captcha node already triggers at 2 and
# should be the FIRST defence; vision picks up cases where the captcha
# router decided "this isn't a captcha" but the page still didn't advance.
DEFAULT_NO_DOM_CHANGE_THRESHOLD = 1


# Maximum number of marks we render on a single screenshot. WebVoyager
# uses ~15-20; more than that overwhelms a 7B vision model. Empirically
# 30 is the breakpoint where Qwen2.5-VL starts confusing close marks.
MAX_MARKS_PER_FRAME = 25


def should_use_vision_fallback(
    state: Any,
    *,
    no_dom_change_threshold: int = DEFAULT_NO_DOM_CHANGE_THRESHOLD,
    require_empty_dom_decision: bool = True,
) -> bool:
    """Return True iff calling the vision model is the right next step.

    The trigger is intentionally narrow:
      * `state.no_dom_change_count >= threshold` — the previous click did
        not advance the page, so picking another DOM target is unlikely
        to help.
      * AND (when `require_empty_dom_decision`) the current iteration
        produced no decision through the DOM path. This avoids paying
        for a VLM call when the DOM path picked something — even if that
        something turns out to fail later, the cheap retry costs less
        than a Qwen2.5-VL invocation.

    `state` is duck-typed: we only read attributes. This keeps the helper
    importable from tests that don't want to bring up the full SurveyState
    dataclass.
    """
    no_dom_change = int(getattr(state, "no_dom_change_count", 0) or 0)
    if no_dom_change < no_dom_change_threshold:
        return False
    if require_empty_dom_decision:
        decision = getattr(state, "decision", None) or {}
        if decision and decision.get("action"):
            return False
    elements = getattr(state, "universal_elements", None) or []
    # If the AX tree is genuinely empty we MUST fall back to vision,
    # regardless of `require_empty_dom_decision`.
    if not elements:
        return True
    return True


# ── Set-of-Mark plan ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class MarkedElement:
    """One numbered mark on the rendered screenshot."""

    mark: int
    stable_id: str
    role: str
    name: str
    bbox: dict  # {x, y, width, height} in CSS px

    @property
    def center(self) -> tuple[float, float]:
        return (
            float(self.bbox.get("x", 0)) + float(self.bbox.get("width", 0)) / 2.0,
            float(self.bbox.get("y", 0)) + float(self.bbox.get("height", 0)) / 2.0,
        )


@dataclass(frozen=True)
class SetOfMarkPlan:
    """Everything `decide_node` needs to render and explain a SoM frame.

    The plan is "vision-ready" but does NOT yet include the rendered PNG
    or the actual VLM call. Tests can build a plan, assert on its shape,
    and then drive `parse_vlm_response` with synthetic raw text.
    """

    marks: tuple[MarkedElement, ...]
    skipped_count: int  # how many candidates we dropped (max-marks limit)
    viewport: tuple[int, int]  # (width, height) CSS px the snapshot covers

    @property
    def is_empty(self) -> bool:
        return len(self.marks) == 0

    def find(self, mark: int) -> Optional[MarkedElement]:
        for m in self.marks:
            if m.mark == mark:
                return m
        return None


# Roles we never bother numbering — they cannot be the answer to "what
# should I click next" so marking them dilutes the prompt budget.
_NON_ACTIONABLE_ROLES = frozenset({
    "list",
    "listitem",
    "paragraph",
    "heading",
    "image",
    "static",
    "generic",
    "presentation",
    "none",
    "",
})


def _is_in_viewport(bbox: dict, viewport: tuple[int, int]) -> bool:
    """A bbox of `{x:0, y:0, width:0, height:0}` (no layout) drops out;
    same for boxes that sit entirely above / below / left / right of
    the visible viewport.
    """
    try:
        x = float(bbox.get("x", 0))
        y = float(bbox.get("y", 0))
        w = float(bbox.get("width", 0))
        h = float(bbox.get("height", 0))
    except (TypeError, ValueError):
        return False
    if w <= 0 or h <= 0:
        return False
    vw, vh = viewport
    if x + w <= 0 or y + h <= 0:
        return False
    if x >= vw or y >= vh:
        return False
    return True


def build_set_of_mark(
    elements: Sequence[dict],
    *,
    viewport: tuple[int, int] = (1280, 800),
    max_marks: int = MAX_MARKS_PER_FRAME,
    avoid_stable_id: str = "",
) -> SetOfMarkPlan:
    """Pick at most `max_marks` actionable elements and assign mark ids.

    Filtering rules (in order):
      1. Drop disabled elements.
      2. Drop the element we just tried (`avoid_stable_id`).
      3. Drop elements without a usable bbox (no layout / off-screen).
      4. Drop non-actionable roles (heading, paragraph, generic, …).
      5. Drop duplicates by `stable_id` (defensive — should not happen
         but a buggy snapshot has bitten us before).

    Order preservation: the input order is the visual order returned by
    cdp_universal.scan(). We keep that order so mark numbering reads
    top-to-bottom on the screenshot — easier on the VLM, easier for a
    human reading the eval logs.
    """
    seen_ids: set[str] = set()
    if avoid_stable_id:
        seen_ids.add(avoid_stable_id)

    marks: list[MarkedElement] = []
    skipped = 0

    for el in elements:
        sid = str(el.get("stable_id") or "")
        if not sid or sid in seen_ids:
            continue
        state = el.get("state") or {}
        if state.get("disabled"):
            continue
        role = str(el.get("role") or "")
        if role in _NON_ACTIONABLE_ROLES:
            continue
        bbox = el.get("bbox") or {}
        if not _is_in_viewport(bbox, viewport):
            continue

        if len(marks) >= max_marks:
            skipped += 1
            continue

        seen_ids.add(sid)
        marks.append(
            MarkedElement(
                mark=len(marks) + 1,
                stable_id=sid,
                role=role,
                name=str(el.get("name") or ""),
                bbox=dict(bbox),
            )
        )

    return SetOfMarkPlan(
        marks=tuple(marks),
        skipped_count=skipped,
        viewport=viewport,
    )


# ── VLM contract & parsing ────────────────────────────────────────────────────


@dataclass(frozen=True)
class VisionDecision:
    """The narrow result we hand back to `decide_node`.

    Either `stable_id` is set (we mapped a mark back to an AX element
    `decide_node` can use directly), or `coords` is set (the model
    pointed at a region the AX tree did not name; the caller is expected
    to feed that into `cdp_actuator.click_at`).
    """

    action: str  # "click" | "wait" | "abandon"
    stable_id: Optional[str] = None
    coords: Optional[tuple[float, float]] = None
    reason: str = "vision_fallback"
    raw_mark: Optional[int] = None
    confidence: float = 0.0

    def is_actionable(self) -> bool:
        return self.action == "click" and (self.stable_id or self.coords)


# Conservative regex: a JSON object with at minimum a "mark" integer.
# We also accept "x" / "y" pairs for off-DOM hits.
_MARK_RE = re.compile(r'"mark"\s*:\s*(\d+)')
_COORD_RE = re.compile(r'"x"\s*:\s*([+-]?[\d.]+)\s*,\s*"y"\s*:\s*([+-]?[\d.]+)')
_CONFIDENCE_RE = re.compile(r'"confidence"\s*:\s*([+-]?[\d.]+)')


def parse_vlm_response(raw: str, plan: SetOfMarkPlan) -> Optional[VisionDecision]:
    """Best-effort parse of the Qwen2.5-VL output. Returns None if the
    response is unusable (no mark, no coords, or pointed at a mark we
    didn't render).

    The model is prompted to return JSON. We accept a few non-JSON-but-
    obviously-correct shapes (markdown-wrapped, leading prose) so a
    sloppy generation doesn't waste a whole iteration.
    """
    if not raw or not isinstance(raw, str):
        return None

    # Markdown-fence stripping. ```json ... ``` is by far the most common
    # leak from chat-tuned models.
    body = raw.strip()
    if body.startswith("```"):
        lines = [ln for ln in body.splitlines() if not ln.strip().startswith("```")]
        body = "\n".join(lines).strip()

    # Try strict JSON first — clean wins are common enough to be worth it.
    payload: Optional[dict] = None
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        # Fall through to regex extraction.
        payload = None

    confidence = 0.0
    if isinstance(payload, dict):
        if "confidence" in payload:
            try:
                confidence = float(payload["confidence"])
            except (TypeError, ValueError):
                confidence = 0.0
    else:
        m_conf = _CONFIDENCE_RE.search(body)
        if m_conf:
            try:
                confidence = float(m_conf.group(1))
            except ValueError:
                confidence = 0.0

    # Path 1: structured mark.
    mark_id: Optional[int] = None
    if isinstance(payload, dict) and "mark" in payload:
        try:
            mark_id = int(payload["mark"])
        except (TypeError, ValueError):
            mark_id = None
    if mark_id is None:
        m = _MARK_RE.search(body)
        if m:
            try:
                mark_id = int(m.group(1))
            except ValueError:
                mark_id = None

    if mark_id is not None:
        marked = plan.find(mark_id)
        if marked is None:
            logger.warning(
                "vision_fallback: VLM returned mark=%d which we did not "
                "render (rendered %d marks).", mark_id, len(plan.marks),
            )
            return None
        return VisionDecision(
            action="click",
            stable_id=marked.stable_id,
            raw_mark=mark_id,
            confidence=confidence,
            reason=f"vision:mark={mark_id}",
        )

    # Path 2: bare coordinates. Allowed for off-DOM elements (canvas).
    cx: Optional[float] = None
    cy: Optional[float] = None
    if isinstance(payload, dict) and isinstance(payload.get("x"), (int, float)):
        cx = float(payload["x"])
        cy = float(payload.get("y", 0))
    else:
        m_xy = _COORD_RE.search(body)
        if m_xy:
            cx = float(m_xy.group(1))
            cy = float(m_xy.group(2))

    if cx is not None and cy is not None:
        vw, vh = plan.viewport
        if not (0 <= cx <= vw and 0 <= cy <= vh):
            logger.warning(
                "vision_fallback: VLM returned (%.1f,%.1f) outside viewport "
                "(%dx%d) — discarding.", cx, cy, vw, vh,
            )
            return None
        return VisionDecision(
            action="click",
            coords=(cx, cy),
            confidence=confidence,
            reason="vision:coords",
        )

    return None


# ── Backend seam ──────────────────────────────────────────────────────────────


class VisionBackend(Protocol):
    """The injectable seam between `run_vision_fallback` and the actual
    multimodal model. Production code passes the Qwen2.5-VL client built
    on top of `survey/captcha/nim_secondary_solver.py`. Tests pass a
    deterministic stub.
    """

    def query(
        self,
        *,
        screenshot_b64: str,
        plan: SetOfMarkPlan,
        prompt: str,
    ) -> str:
        ...


DEFAULT_PROMPT = (
    "You are inspecting a survey page where the previous click did not "
    "advance the form. Each numbered red box marks a candidate UI element. "
    "Return ONLY a JSON object {\"mark\": <int>, \"confidence\": <0..1>, "
    "\"reason\": \"<short>\"} where mark is the box you would click next "
    "to keep the survey moving. If NONE of the boxes is the right answer "
    "but you can see a clear coordinate to click on the page (e.g. on a "
    "<canvas> control), return {\"x\": <int>, \"y\": <int>, "
    "\"confidence\": <0..1>}. Do NOT invent marks that are not visible."
)


def run_vision_fallback(
    *,
    backend: VisionBackend,
    screenshot_b64: str,
    plan: SetOfMarkPlan,
    prompt: str = DEFAULT_PROMPT,
) -> Optional[VisionDecision]:
    """Drive the full backend → parse loop. Pure orchestration.

    Returns None when the plan is empty (caller should fall through to
    "wait") OR when the VLM output cannot be parsed. The caller decides
    how to log/escalate either failure mode.
    """
    if plan.is_empty:
        return None
    raw = backend.query(
        screenshot_b64=screenshot_b64,
        plan=plan,
        prompt=prompt,
    )
    return parse_vlm_response(raw, plan)


__all__ = [
    "DEFAULT_NO_DOM_CHANGE_THRESHOLD",
    "DEFAULT_PROMPT",
    "MAX_MARKS_PER_FRAME",
    "MarkedElement",
    "SetOfMarkPlan",
    "VisionBackend",
    "VisionDecision",
    "build_set_of_mark",
    "parse_vlm_response",
    "run_vision_fallback",
    "should_use_vision_fallback",
]
