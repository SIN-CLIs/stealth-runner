"""survey/observability/visual_debug.py -- Visual Debug Report (SR-173 / #178).

PROBLEM STATEMENT (read this before you touch anything in here)
===============================================================
When a survey click lands a few pixels off the target, today we have to
reconstruct from JSONL events *where the agent thought the element was* vs.
*where it actually was on screen*. That takes 15+ min per incident. There are
exactly four coordinate-misalignment bug classes that this module is built to
make instantly visible (each one is also covered by a dedicated unit test in
`survey-cli/tests/test_visual_debug.py`):

    1. **iFrame-Offset-Bug.**
       The CDP Accessibility tree returns bounding boxes in the *iframe-local*
       coordinate space. We click in page-coords. If we forget to add the
       iframe's page-origin we silently miss by (frame_x, frame_y) pixels.
       Pollfish, Cint, Lucid all embed in iframes -- this is the #1 bug.

    2. **DPR-Mismatch (HiDPI / browser-zoom).**
       Page.captureScreenshot returns physical pixels: a 1280x720 logical
       viewport on a 2x device produces a 2560x1440 PNG. getContentQuads
       returns *logical* pixels. Naively drawing the bbox on the screenshot
       puts the rect at half size in the wrong place.

    3. **Scroll-Offset stale.**
       The snapshot was taken at scrollY=300; the click fires 200ms later
       after a lazy-loaded image pushed the page to scrollY=400. The click
       lands 100 px below the visual element.

    4. **Overlay z-index.**
       Element is in the AX-Tree as `visible`, but a modal sits on top with
       z-index 9999. The click hits the modal, not the target. AX-Tree alone
       cannot detect this -- we surface it visually so a human sees it in 5 s.

This module produces, **per executed step** (sampled), a single self-contained
HTML file with the screenshot embedded as a data: URL and an inline SVG
overlay drawing:

  - a red rectangle around the **target bbox** (translated into page coords
    AND scaled into screenshot-pixel coords -- both transforms tested);
  - a yellow crosshair at the **click point** (also in screenshot-pixel
    coords);
  - SVG `<title>` tooltips with ax_role / ax_name / ax_node_id;
  - a JSON evidence side-panel: verifier (SR-167) + attestation (SR-168)
    results + network-pending count + DOM hash before/after.

ARCHITECTURE
============
                                +-------------------+
   safe_executor.execute()      |   RunnerPolicy    |
       (sync, hot path)         |  sample-rate etc. |
            |                   +---------+---------+
            |  build VisualDebugFrame               |
            v                                       v
       VisualDebugDispatcher.submit(frame, policy, verifier_failed=...)
            |
            |  should_render() -> bool   (deterministic, blake2b hash of step_id)
            |
            |  Acquire bounded semaphore  --> on saturation: DROP (log + return None).
            |  Submit closure to ThreadPoolExecutor (2 workers, IO-bound work).
            v
       _render_worker(frame, out_path)
            |
            |  PIL.Image.open(screenshot) -> downscale if needed -> JPEG@quality
            |  Build inline SVG (deterministic, sorted JSON, no random ids)
            |  Build HTML template (string-format, no Jinja: ~12 LOC, vendoring noise)
            |  Write to <tmp>.html, then os.replace() to target  (atomic on POSIX)
            v
       debug-reports/YYYY-MM-DD/step-<step_id>.html

WHY THREAD-POOL, NOT asyncio.create_task
========================================
`safe_executor.SurveyFlowExecutor` runs in a *synchronous* LangGraph node
(see its module docstring: "synchronous websocket ... matches LangGraph node
execution"). There is no running event-loop to attach a task to. A bounded
`ThreadPoolExecutor` is the correct primitive:

  - non-blocking submit (returns Future immediately)
  - bounded back-pressure via BoundedSemaphore (drop-on-overflow, never block)
  - graceful shutdown via context-manager / atexit hook

The briefing in #178 originally said "asyncio.create_task". We diverge here
intentionally because the surrounding executor is sync. The non-blocking
guarantee from the briefing IS preserved -- in fact strengthened (a real
async-task on a saturated loop can still queue indefinitely; our semaphore
caps at `max_queue` hard).

PROTOCOL SHIMS FOR SR-167 / SR-168
==================================
`VerificationResult` (from SR-167 / #167) and `AttestationResult` (from
SR-168 / #168) are not yet merged on `main` at the time SR-173 was implemented.
We declare `typing.Protocol`-based shims here so:

  - this module compiles + tests run today;
  - once SR-167/168 land, the *only* change is replacing the Protocol import
    with a `from survey.reliability.verifier import VerificationResult` in
    the type-checker's eyes -- no run-time changes.

TODO(SR-167 / #167):  swap VerificationResultLike for the real dataclass.
TODO(SR-168 / #168):  swap AttestationResultLike for the real dataclass.

COST BUDGET (defended in PR review)
===================================
  Frame size budget:  <= 200 KB JPEG@70  + ~5 KB SVG/HTML/JSON  -> ~205 KB
  Prod sampling:      10 % of steps + 100 % of failures
  Expected steps/day: 10_000
  Expected renders:   ~1_500/day  (10 % sample + ~5 % failure rate)
  Storage/day:        ~300 MB pre-retention; daily aggregator uploads to
                      Vercel Blob with a 7-day signed URL.

BANNED METHODS -- NIEMALS VERWENDEN
===================================
- playstealth launch
- webauto-nodriver -- ABSOLUT BANNED
- cua-driver click (raw index)
- --remote-allow-origins=* (ohne Quotes)
- /tmp/heypiggy-bot (fixed profile)
- Hardcoded PIDs
- pkill -f "Google Chrome"
- killall Google Chrome
- skylight-cli click --element-index

RELATED ISSUES
==============
- #178 (SR-173)  -- this file.
- #167 (SR-167)  -- post-action verifier; provides VerificationResult.
- #168 (SR-168)  -- triple-channel attestation; provides AttestationResult.
- #172 (SR-172)  -- meta-tracker for the reliability push.
"""

from __future__ import annotations

import base64
import hashlib
import html
import io
import json
import logging
import os
import threading
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Protocol, runtime_checkable

# Pillow is a hard runtime dep for SR-173. We import lazily so that *importing*
# this module never fails -- only render() does, and only with a clear error.
# (Test suites that monkey-patch out the renderer can still import freely.)
try:
    from PIL import Image  # type: ignore[import-not-found]

    _PIL_AVAILABLE = True
except ImportError:  # pragma: no cover -- only hit on broken envs
    Image = None  # type: ignore[assignment,misc]
    _PIL_AVAILABLE = False

from survey.runner_policy import RunnerPolicy

logger = logging.getLogger(__name__)


# Geometry primitives
# Defined here, NOT in snapshot.py, because:
#  (a) snapshot.py already has 900+ lines and we should not bloat it for SR-173;
#  (b) Box/Point/ElementRef are *observability* concepts in our codebase --
#      the snapshot module only deals with CompactSnapshot today.
# TODO(SR-167 / #167): once verifier.py lands, consider promoting these to a
# shared `survey.geometry` module if more than two callers need them.

@dataclass(frozen=True, slots=True)
class Point:
    """A 2D point in *page* coordinates (CSS pixels, post-iframe-transform)."""

    x: float
    y: float

    def to_screenshot(self, dpr: float) -> "Point":
        """Convert page-coords -> screenshot-pixel-coords by DPR scaling.

        getContentQuads/AX-Tree return CSS px; Page.captureScreenshot writes
        physical px. Multiplying by DPR is the inverse of the browser's
        device-pixel mapping.
        """
        return Point(self.x * dpr, self.y * dpr)


@dataclass(frozen=True, slots=True)
class Box:
    """An axis-aligned bbox in *page* coordinates (CSS pixels)."""

    x: float
    y: float
    w: float
    h: float

    def translated(self, dx: float, dy: float) -> "Box":
        """Return a new Box shifted by (dx, dy). Pure / no mutation."""
        return Box(self.x + dx, self.y + dy, self.w, self.h)

    def to_screenshot(self, dpr: float) -> "Box":
        """DPR-scale into screenshot pixel coords."""
        return Box(self.x * dpr, self.y * dpr, self.w * dpr, self.h * dpr)


@dataclass(frozen=True, slots=True)
class ElementRef:
    """Stable reference to a DOM element as observed via CDP Accessibility.

    `frame_offset` is the *page-origin* of the iframe this element lives in
    -- (0, 0) for elements on the top frame. The renderer adds this to the
    raw bbox to produce final page coords. This is THE critical input for
    fixing the iFrame-Offset-Bug class.
    """

    ax_node_id: int
    ax_role: str
    ax_name: str
    backend_node_id: int | None = None
    frame_id: str | None = None  # CDP Page.FrameId; None => main frame
    frame_offset: Point = field(default_factory=lambda: Point(0.0, 0.0))


# Protocol shims for SR-167 / SR-168 result objects.
# `runtime_checkable` keeps `isinstance(x, VerificationResultLike)` working in
# tests where we hand-roll fake results. The fields here MUST match the
# upstream dataclass once it lands -- update this in lockstep when merging.

@runtime_checkable
class VerificationResultLike(Protocol):
    """Shape of `survey.reliability.verifier.VerificationResult` (SR-167)."""

    ok: bool
    reason: str | None


@runtime_checkable
class AttestationResultLike(Protocol):
    """Shape of `survey.reliability.attestation.AttestationResult` (SR-168)."""

    ok: bool
    channels_agreed: int
    channels_total: int
    disagreement: str | None


# VisualDebugFrame
@dataclass(frozen=True, slots=True)
class VisualDebugFrame:
    """All inputs needed to render one HTML debug report.

    Constructed by the *caller* (safe_executor hook) -- the renderer treats it
    as pure data. Keeping this frozen lets us schedule it across threads with
    zero locking.

    Fields:
        step_id:            stable identifier (used for sampling + filename).
        timestamp:          UTC, tz-aware (datetime.utcnow is deprecated).
        url:                page URL at the moment of action.
        screenshot_path:    absolute path to the full-page PNG that
                            captureScreenshot wrote. We do NOT keep the bytes
                            here -- the renderer reads + re-encodes them.
        screenshot_dpr:     devicePixelRatio at capture time. Read via CDP
                            `window.devicePixelRatio`. Drives bbox scaling.
        screenshot_size:    (width, height) in screenshot-pixel coords.
                            Used as the SVG viewBox; if not provided, the
                            renderer infers from the image header.
        target_element:     who we were targeting (ax_role/name + frame_offset).
        target_bbox:        bbox in *iframe-local* coords. Renderer applies
                            frame_offset -> page coords -> screenshot coords.
        click_point:        where we actually clicked, in *page* coords.
                            Already post-transformed by the caller.
        scroll_at_click:    page scrollX/scrollY at the moment of click; used
                            to detect stale-scroll bugs vs. snapshot time.
        scroll_at_snapshot: page scrollX/scrollY at the moment of snapshot.
        pre_dom_hash:       sha256 of innerHTML pre-action.
        post_dom_hash:      sha256 of innerHTML post-action.
        network_pending_at_click: # of in-flight requests (SR-169/174).
        verifier:           SR-167 result; None if SR-167 not yet wired.
        attestation:        SR-168 result; None if SR-168 not yet wired.
        overlay_warnings:   pre-computed warnings (e.g. "z-index 9999 covers
                            target"); rendered as red badges in the side panel.
    """

    step_id: str
    timestamp: datetime
    url: str
    screenshot_path: Path
    screenshot_dpr: float
    target_element: ElementRef
    target_bbox: Box
    click_point: Point
    pre_dom_hash: str
    post_dom_hash: str
    screenshot_size: tuple[int, int] | None = None
    scroll_at_click: Point = field(default_factory=lambda: Point(0.0, 0.0))
    scroll_at_snapshot: Point = field(default_factory=lambda: Point(0.0, 0.0))
    network_pending_at_click: int = 0
    verifier: VerificationResultLike | None = None
    attestation: AttestationResultLike | None = None
    overlay_warnings: tuple[str, ...] = ()

    @property
    def verifier_ok(self) -> bool:
        """True iff verifier is present AND says ok; conservative default = True
        when verifier is wired-but-None (we don't want missing-data => red).
        For policy decisions use `verifier_failed` instead which is unambiguous.
        """
        return self.verifier is None or bool(self.verifier.ok)

    @property
    def verifier_failed(self) -> bool:
        """True iff verifier ran AND reported failure. None / unwired => False."""
        return self.verifier is not None and not bool(self.verifier.ok)


# Sampling
def _stable_sample_decision(step_id: str, sample_rate: float) -> bool:
    """Deterministic sampling: same step_id always yields same decision.

    Uses blake2b (fast, stable across Python versions; unlike `hash()` which
    is salted per-process). Cardinality is 10_000 buckets, so the smallest
    addressable rate is 0.0001 = 0.01 %.
    """
    if sample_rate <= 0.0:
        return False
    if sample_rate >= 1.0:
        return True
    digest = hashlib.blake2b(step_id.encode("utf-8"), digest_size=4).digest()
    bucket = int.from_bytes(digest, "big") % 10_000
    return bucket < int(sample_rate * 10_000)


def should_render(
    step_id: str,
    policy: RunnerPolicy,
    *,
    verifier_failed: bool,
) -> bool:
    """Top-level sampling gate: combines failure-override + deterministic hash."""
    if verifier_failed and policy.visual_debug_on_failure:
        return True
    return _stable_sample_decision(step_id, policy.visual_debug_sample_rate)


# Coordinate transforms
def element_bbox_in_page_coords(element: ElementRef, raw_bbox: Box) -> Box:
    """Translate a raw (iframe-local) bbox into page coordinates.

    THIS IS THE iFrame-Offset-Bug fix. Every callsite that draws on the
    page-level screenshot MUST go through this function. Direct use of the
    raw bbox bypasses the transform and re-introduces the bug.

    Example::

        element = ElementRef(..., frame_offset=Point(200, 300))
        raw     = Box(50, 50, 120, 32)        # iframe-local
        page    = element_bbox_in_page_coords(element, raw)
        # -> Box(250, 350, 120, 32)
    """
    return raw_bbox.translated(element.frame_offset.x, element.frame_offset.y)


# Image compression
def _encode_jpeg(
    png_bytes: bytes,
    *,
    quality: int,
    max_bytes: int,
) -> tuple[bytes, tuple[int, int]]:
    """Re-encode a PNG screenshot as JPEG, shrinking quality until <= max_bytes.

    Returns (jpeg_bytes, (width, height)). Width/height are the IMAGE pixel
    dims (== screenshot pixels), used as the SVG viewBox.

    If after quality=10 we still exceed max_bytes, we return the smallest we
    got and log a warning. The HTML render still works; the file is just
    larger than budget -- a CI assertion in the test suite watches for this.
    """
    if not _PIL_AVAILABLE:
        raise RuntimeError(
            "Pillow is required for visual_debug rendering. "
            "Install: `pip install Pillow` (already in survey-cli requirements)."
        )
    img = Image.open(io.BytesIO(png_bytes))
    # Convert RGBA -> RGB on white background; JPEG has no alpha channel.
    if img.mode in ("RGBA", "LA"):
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[-1])
        img = bg
    elif img.mode != "RGB":
        img = img.convert("RGB")

    size = img.size  # (width, height) in screenshot pixels
    q = max(1, min(95, quality))
    out: bytes = b""
    while q >= 10:
        buf = io.BytesIO()
        # `optimize=True` runs an extra Huffman pass; +200 ms render, -5 % size.
        # `progressive=True` is irrelevant for embedded data: URLs but harmless.
        img.save(buf, format="JPEG", quality=q, optimize=True, progressive=True)
        out = buf.getvalue()
        if len(out) <= max_bytes:
            return out, size
        q -= 10
    logger.warning(
        "visual_debug: could not shrink screenshot under %d bytes (got %d at q=10)",
        max_bytes,
        len(out),
    )
    return out, size


# HTML / SVG rendering
# Minimal, self-contained HTML5 template. Inline CSS / SVG -- one file, no deps.
# We deliberately do NOT use Jinja: the template is ~12 placeholders, vendoring
# a templating engine for that is rope-around-the-neck.
_HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Visual Debug Report -- step {step_id_html}</title>
<style>
 :root {{
   --ok: #1f7a3a;
   --fail: #b00020;
   --bg: #0f1115;
   --panel: #181b22;
   --fg: #e7ebf0;
   --muted: #8a93a3;
 }}
 * {{ box-sizing: border-box; }}
 body {{
   margin: 0; background: var(--bg); color: var(--fg);
   font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto;
   font-size: 13px; line-height: 1.45;
 }}
 header {{
   padding: 12px 16px; border-bottom: 4px solid {status_color};
   display: flex; gap: 16px; align-items: center; flex-wrap: wrap;
 }}
 header h1 {{ font-size: 14px; margin: 0; font-weight: 600; }}
 header .pill {{
   padding: 2px 8px; border-radius: 10px; font-size: 11px;
   background: var(--panel); color: var(--muted);
 }}
 header .pill.bad  {{ background: var(--fail); color: #fff; }}
 header .pill.good {{ background: var(--ok);   color: #fff; }}
 main {{ display: grid; grid-template-columns: 1fr 360px; gap: 12px; padding: 12px; }}
 .stage {{
   position: relative; background: #000; border-radius: 6px; overflow: hidden;
 }}
 .stage img, .stage svg {{ display: block; width: 100%; height: auto; }}
 .stage svg {{ position: absolute; inset: 0; pointer-events: none; }}
 aside {{ background: var(--panel); border-radius: 6px; padding: 12px; }}
 aside h2 {{ font-size: 12px; margin: 0 0 6px; color: var(--muted);
            text-transform: uppercase; letter-spacing: 0.04em; }}
 aside section + section {{ margin-top: 14px; }}
 aside .kv {{ display: grid; grid-template-columns: 130px 1fr; gap: 4px 10px; }}
 aside .kv dt {{ color: var(--muted); font-weight: 500; }}
 aside .kv dd {{ margin: 0; word-break: break-all; }}
 aside pre {{
   background: #0a0c10; border-radius: 4px; padding: 8px;
   margin: 0; max-height: 220px; overflow: auto; font-size: 11px;
 }}
 .warn {{
   background: var(--fail); color: #fff; padding: 4px 8px; border-radius: 4px;
   margin: 4px 0; font-weight: 600;
 }}
</style>
</head>
<body>
<header>
  <h1>Visual Debug -- step {step_id_html}</h1>
  <span class="pill {status_pill_class}">{status_label}</span>
  <span class="pill">DPR {dpr_html}</span>
  <span class="pill">{url_short_html}</span>
  <span class="pill">{ts_html}</span>
</header>
<main>
  <div class="stage">
    <img alt="page screenshot at action time" src="data:image/jpeg;base64,{img_b64}">
    <svg viewBox="0 0 {sw} {sh}" preserveAspectRatio="xMidYMid meet"
         xmlns="http://www.w3.org/2000/svg" aria-label="overlay">
      <rect x="{bx}" y="{by}" width="{bw}" height="{bh}"
            fill="none" stroke="#ff3344" stroke-width="3" stroke-dasharray="6 4">
        <title>{bbox_title}</title>
      </rect>
      <g stroke="#ffd400" stroke-width="2">
        <line x1="{cx_minus}" y1="{cy}" x2="{cx_plus}" y2="{cy}"/>
        <line x1="{cx}" y1="{cy_minus}" x2="{cx}" y2="{cy_plus}"/>
        <circle cx="{cx}" cy="{cy}" r="7" fill="none">
          <title>click point page=({cp_page_x}, {cp_page_y})</title>
        </circle>
      </g>
    </svg>
  </div>
  <aside>
    {warnings_html}
    <section>
      <h2>Target Element</h2>
      <dl class="kv">
        <dt>role</dt><dd>{role_html}</dd>
        <dt>name</dt><dd>{name_html}</dd>
        <dt>ax_node_id</dt><dd>{ax_node_id}</dd>
        <dt>frame_id</dt><dd>{frame_id_html}</dd>
        <dt>frame_offset</dt><dd>({frame_off_x}, {frame_off_y})</dd>
      </dl>
    </section>
    <section>
      <h2>Geometry (page-coords)</h2>
      <dl class="kv">
        <dt>bbox</dt><dd>x={bb_page_x} y={bb_page_y} w={bb_page_w} h={bb_page_h}</dd>
        <dt>click</dt><dd>({cp_page_x}, {cp_page_y})</dd>
        <dt>scroll@snap</dt><dd>({ss_x}, {ss_y})</dd>
        <dt>scroll@click</dt><dd>({sc_x}, {sc_y})</dd>
      </dl>
    </section>
    <section>
      <h2>DOM Hash</h2>
      <dl class="kv">
        <dt>pre</dt><dd>{pre_hash_html}</dd>
        <dt>post</dt><dd>{post_hash_html}</dd>
      </dl>
    </section>
    <section>
      <h2>Verifier (SR-167)</h2>
      <pre>{verifier_json}</pre>
    </section>
    <section>
      <h2>Attestation (SR-168)</h2>
      <pre>{attestation_json}</pre>
    </section>
    <section>
      <h2>Network</h2>
      <dl class="kv">
        <dt>pending@click</dt><dd>{net_pending}</dd>
      </dl>
    </section>
  </aside>
</main>
</body>
</html>
"""


def _json_dump(obj: Any) -> str:
    """Serialize verifier/attestation Protocol values into JSON.

    Order is deterministic (sort_keys=True) so HTML reports are diff-able in
    PRs. Pure-dataclass objects are converted via `asdict`; anything else
    falls back to `str(...)` and never raises.
    """
    if obj is None:
        return "null"
    if is_dataclass(obj):
        try:
            return json.dumps(asdict(obj), sort_keys=True, indent=2, default=str)
        except Exception:  # pragma: no cover -- only weird non-serializable nested
            pass
    # Fallback: pull declared attrs of the Protocol.
    keys = [k for k in dir(obj) if not k.startswith("_") and not callable(getattr(obj, k))]
    return json.dumps(
        {k: getattr(obj, k) for k in keys},
        sort_keys=True,
        indent=2,
        default=str,
    )


def _format_num(v: float) -> str:
    """1-dp formatter -- keeps SVG/HTML byte-diffs minimal for PR reviews."""
    return f"{v:.1f}"


def render_html_report(
    frame: VisualDebugFrame,
    out_path: Path,
    *,
    jpeg_quality: int = 70,
    max_kb: int = 500,
) -> Path:
    """Render a self-contained HTML debug report for one step.

    Args:
        frame:        the data bundle to render.
        out_path:     destination path. Parent dirs are created. Write is
                      atomic: we write to a UUID-suffixed temp file in the
                      same dir, then `os.replace()`.
        jpeg_quality: starting JPEG quality (1..95). Renderer auto-shrinks
                      until the inlined image fits the size budget.
        max_kb:       budget for the final HTML file. The renderer shrinks
                      the JPEG (NOT the SVG) to meet this. If unachievable
                      a warning is logged; the file is still written.

    Returns:
        The absolute Path that was written.

    Atomicity:
        Critical for concurrent runs. We never write twice to the same final
        path -- a UUID is added to the temp path; rename is one syscall.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. Read + compress screenshot.
    png_bytes = Path(frame.screenshot_path).read_bytes()
    # Budget: reserve ~10 KB for HTML+SVG+JSON; rest is the image.
    img_budget = max(50_000, max_kb * 1024 - 10_000)
    jpeg_bytes, (sw, sh) = _encode_jpeg(
        png_bytes,
        quality=jpeg_quality,
        max_bytes=img_budget,
    )
    # Caller may have provided an explicit screenshot_size -- honour it.
    if frame.screenshot_size is not None:
        sw, sh = frame.screenshot_size

    # 2. Compute on-image coordinates.
    page_bbox = element_bbox_in_page_coords(frame.target_element, frame.target_bbox)
    img_bbox = page_bbox.to_screenshot(frame.screenshot_dpr)
    img_click = frame.click_point.to_screenshot(frame.screenshot_dpr)

    # 3. Status colour (verifier-driven).
    if frame.verifier_failed:
        status_color, status_label, status_pill = "var(--fail)", "FAIL", "bad"
    else:
        status_color, status_label, status_pill = "var(--ok)", "OK", "good"

    # 4. Warnings (pre-computed overlay_warnings).
    if frame.overlay_warnings:
        warnings_html = "\n".join(
            f'    <div class="warn">{html.escape(w)}</div>' for w in frame.overlay_warnings
        )
    else:
        warnings_html = ""

    # 5. Crosshair endpoints (page-coord units, scaled to screenshot already).
    crosshair = 14.0  # px each side of click in screenshot-space

    rendered = _HTML_TEMPLATE.format(
        step_id_html=html.escape(frame.step_id),
        status_color=status_color,
        status_label=status_label,
        status_pill_class=status_pill,
        dpr_html=html.escape(_format_num(frame.screenshot_dpr)),
        url_short_html=html.escape(frame.url[:80]),
        ts_html=html.escape(frame.timestamp.astimezone(timezone.utc).isoformat()),
        img_b64=base64.b64encode(jpeg_bytes).decode("ascii"),
        sw=int(sw),
        sh=int(sh),
        bx=_format_num(img_bbox.x),
        by=_format_num(img_bbox.y),
        bw=_format_num(img_bbox.w),
        bh=_format_num(img_bbox.h),
        bbox_title=html.escape(
            f"target bbox page=({_format_num(page_bbox.x)},{_format_num(page_bbox.y)}) "
            f"{_format_num(page_bbox.w)}x{_format_num(page_bbox.h)}"
        ),
        cx=_format_num(img_click.x),
        cy=_format_num(img_click.y),
        cx_minus=_format_num(img_click.x - crosshair),
        cx_plus=_format_num(img_click.x + crosshair),
        cy_minus=_format_num(img_click.y - crosshair),
        cy_plus=_format_num(img_click.y + crosshair),
        cp_page_x=_format_num(frame.click_point.x),
        cp_page_y=_format_num(frame.click_point.y),
        role_html=html.escape(frame.target_element.ax_role),
        name_html=html.escape(frame.target_element.ax_name),
        ax_node_id=frame.target_element.ax_node_id,
        frame_id_html=html.escape(frame.target_element.frame_id or "(main)"),
        frame_off_x=_format_num(frame.target_element.frame_offset.x),
        frame_off_y=_format_num(frame.target_element.frame_offset.y),
        bb_page_x=_format_num(page_bbox.x),
        bb_page_y=_format_num(page_bbox.y),
        bb_page_w=_format_num(page_bbox.w),
        bb_page_h=_format_num(page_bbox.h),
        ss_x=_format_num(frame.scroll_at_snapshot.x),
        ss_y=_format_num(frame.scroll_at_snapshot.y),
        sc_x=_format_num(frame.scroll_at_click.x),
        sc_y=_format_num(frame.scroll_at_click.y),
        pre_hash_html=html.escape(frame.pre_dom_hash[:32]),
        post_hash_html=html.escape(frame.post_dom_hash[:32]),
        verifier_json=html.escape(_json_dump(frame.verifier)),
        attestation_json=html.escape(_json_dump(frame.attestation)),
        net_pending=frame.network_pending_at_click,
        warnings_html=warnings_html,
    )

    # 6. Atomic write: tmp + os.replace (POSIX-atomic; Windows: also atomic since
    # Python 3.3 via MoveFileExW under the hood).
    tmp = out_path.with_name(f".{out_path.name}.{uuid.uuid4().hex}.tmp")
    tmp.write_text(rendered, encoding="utf-8")
    os.replace(tmp, out_path)

    return out_path


# Dispatcher (off-hot-path scheduling)
class VisualDebugDispatcher:
    """Schedules HTML rendering off the LangGraph hot path.

    USAGE
    -----
    Construct ONE dispatcher per runner process. Pass `policy=` so it can
    consult sample-rate + max-queue at runtime. Call `submit(frame, ...)` from
    inside `safe_executor` after each action; ignore the returned Future
    (it exists for tests + graceful shutdown).

    BACKPRESSURE
    ------------
    A BoundedSemaphore caps the number of in-flight renders at
    `policy.visual_debug_max_queue`. If the pool is saturated we DROP the
    frame and log a warning -- we NEVER block the caller. This is the entire
    point of moving rendering off the hot path.

    SHUTDOWN
    --------
    The dispatcher registers `_shutdown` as an atexit hook so pending renders
    complete on graceful exit. For an emergency shutdown call
    `dispatcher.close(wait=False)`.
    """

    def __init__(self, policy: RunnerPolicy):
        self._policy = policy
        self._executor = ThreadPoolExecutor(
            max_workers=policy.visual_debug_workers,
            thread_name_prefix="visdbg",
        )
        # `BoundedSemaphore(N)` -> up to N concurrent + queued renders.
        self._slots = threading.BoundedSemaphore(policy.visual_debug_max_queue)
        self._lock = threading.Lock()
        self._closed = False
        self._dropped = 0
        self._completed = 0
        self._failed = 0

    # public API
    def submit(
        self,
        frame: VisualDebugFrame,
        *,
        force: bool = False,
    ) -> Future[Path] | None:
        """Schedule a render. Returns the Future or None if skipped/dropped.

        Args:
            frame: the data bundle.
            force: bypass sampling -- used by callers that already decided
                   (e.g. integration tests). Production callers should let
                   the dispatcher decide via `should_render`.
        """
        if self._closed:
            return None

        if not force and not should_render(
            frame.step_id,
            self._policy,
            verifier_failed=frame.verifier_failed,
        ):
            return None

        # Non-blocking acquire. If full -> drop (do NOT block hot path).
        if not self._slots.acquire(blocking=False):
            with self._lock:
                self._dropped += 1
            logger.warning(
                "visual_debug: dropping frame step_id=%s (queue full at %d)",
                frame.step_id,
                self._policy.visual_debug_max_queue,
            )
            return None

        out_path = self._path_for(frame)
        future = self._executor.submit(self._render, frame, out_path)
        future.add_done_callback(self._on_done)
        return future

    def close(self, *, wait: bool = True) -> None:
        """Shut down the underlying pool. Idempotent."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
        self._executor.shutdown(wait=wait, cancel_futures=not wait)

    @property
    def stats(self) -> dict[str, int]:
        with self._lock:
            return {
                "dropped": self._dropped,
                "completed": self._completed,
                "failed": self._failed,
            }

    # internals
    def _path_for(self, frame: VisualDebugFrame) -> Path:
        day = frame.timestamp.astimezone(timezone.utc).strftime("%Y-%m-%d")
        # Sanitize step_id for filesystem use -- only [A-Za-z0-9_-] kept.
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in frame.step_id)
        return self._policy.visual_debug_output_dir / day / f"step-{safe}.html"

    def _render(self, frame: VisualDebugFrame, out_path: Path) -> Path:
        try:
            return render_html_report(
                frame,
                out_path,
                jpeg_quality=self._policy.visual_debug_jpeg_quality,
                max_kb=self._policy.visual_debug_max_kb,
            )
        except Exception:
            logger.exception("visual_debug: render failed for step_id=%s", frame.step_id)
            raise

    def _on_done(self, future: Future) -> None:
        # Always release the slot, even on error -- otherwise a single bad
        # frame would permanently shrink our queue.
        self._slots.release()
        with self._lock:
            if future.exception() is None:
                self._completed += 1
            else:
                self._failed += 1


@contextmanager
def dispatcher_scope(policy: RunnerPolicy) -> Iterator[VisualDebugDispatcher]:
    """Context-managed dispatcher -- preferred entry point in long-lived runners.

    Ensures `close()` runs on normal exit AND on exception, with `wait=True`
    so already-queued frames finish (we don't want to lose post-mortem
    evidence because a process is shutting down).
    """
    d = VisualDebugDispatcher(policy)
    try:
        yield d
    finally:
        d.close(wait=True)


__all__ = [
    "Point",
    "Box",
    "ElementRef",
    "VerificationResultLike",
    "AttestationResultLike",
    "VisualDebugFrame",
    "should_render",
    "element_bbox_in_page_coords",
    "render_html_report",
    "VisualDebugDispatcher",
    "dispatcher_scope",
]
