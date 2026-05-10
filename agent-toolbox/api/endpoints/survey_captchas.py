# ════════════════════════════════════════════════════════════════════════════════╗
# ║  CAPTCHA + DRAG-DROP — solve captcha, solve drag puzzle                      ║
# ║                                                                               ║
# ║  Verified: commands/captcha/ + commands/surveys/purespectrum-drag-puzzle.md  ║
# ║  Integration: stealth-captcha/src/stealth_captcha/solver/                    ║
# ╚═══════════════════════════════════════════════════════════════════════════════╝

from __future__ import annotations

from fastapi import APIRouter, Depends
from ._common import (
    CaptchaSolveRequest, CaptchaSolveResponse,
    SolveDragPuzzleRequest, SolveDragPuzzleResponse,
    require_survey_ready, update_command_registry,
)

router = APIRouter(prefix="/survey", tags=["captcha"])

import json, asyncio, websockets, urllib.request

# ─── TOOL IMPORTS ──────────────────────────────────────────────────────────────
from tools.tool_solve_captcha import solve as _solve_captcha
from tools.tool_solve_drag_puzzle import solve as _solve_drag_puzzle


def _get_ws(port: int) -> str:
    """Find first survey tab WebSocket."""
    raw = urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=3).read()
    pages = json.loads(raw)
    for p in pages:
        if p.get("type") == "page" and not p.get("url", "").startswith("chrome-extension"):
            url = p.get("url", "")
            if url and "heypiggy" not in url:
                return p.get("webSocketDebuggerUrl", "")
    return ""


# ═══════════════════════════════════════════════════════════════════════════════
# POST /survey/captcha/solve — Auto-detect + solve captcha
# Tool: survey-cli/tools/tool_solve_captcha.py (174 lines, standalone)
# Verified: commands/captcha/WORKING-SOLUTION.md
#
# Captcha Types:
#   - text/visual: screenshot → NVIDIA Vision OCR → type → submit
#   - slide: CDP Bezier trajectory → Input.dispatchMouseEvent
#   - drag: delegates to tool_solve_drag_puzzle.py
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/captcha/solve", response_model=CaptchaSolveResponse, dependencies=[Depends(require_survey_ready)])
async def api_solve_captcha(req: CaptchaSolveRequest):
    """
    Auto-detects and solves captchas on survey pages.
    
    Tool: survey-cli/tools/tool_solve_captcha.py (174 lines, frozen=True)
    
    Auto-Detection Flow:
      1. CDP Runtime.evaluate → check for captcha elements (canvas, img, input[placeholder*=captcha])
      2. Classify type: slide / text / visual / drag / none
      3. Solve via appropriate method:
         - text/visual → screenshot + NVIDIA Vision OCR (meta/llama-3.2-90b-vision-instruct)
         - slide → CDP Bezier trajectory + Input.dispatchMouseEvent
         - drag → delegation to tool_solve_drag_puzzle
    
    Backend: stealth-captcha/src/stealth_captcha/solver/text.py:PixtralCaptchaBackend
    API: https://integrate.api.nvidia.com/v1/chat/completions
    """
    try:
        ws = req.ws_url or _get_ws(req.cdp_port)
        result = _solve_captcha(ws_url=ws, cdp_port=req.cdp_port)
        solved = result.get("status") in ("solved", "ok")
        update_command_registry("solve_captcha", solved, result)
        return CaptchaSolveResponse(
            status="solved" if solved else "error",
            solved=solved,
            captcha_type=result.get("captcha_type", req.captcha_type),
            answer=result.get("answer"),
            reason=result.get("reason"),
        )
    except Exception as e:
        update_command_registry("solve_captcha", False, {"error": str(e)})
        return CaptchaSolveResponse(status="error", solved=False, reason=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# POST /survey/solve-drag — Angular CDK drag-drop puzzle solver
# Tool: survey-cli/tools/tool_solve_drag_puzzle.py (147 lines, APPROACH B verified)
# Verified: commands/surveys/purespectrum-drag-puzzle.md (E2E: Survey 49517969 "Zahl 28")
#
# Why APPROACH B works:
#   - Angular CDK (ab v7) uses @HostListener('pointerdown/move/up') — PointerEvents only
#   - CDP Input.dispatchMouseEvent → native browser engine mouse events
#   - These propagate to Angular's pointer event handlers (NOT synthetic JS!)
#   - NOT: dispatchEvent(MouseEvent) → ignored by CDK
#   - NOT: dispatchEvent(PointerEvent) → blocked by Angular
#   - NOT: __ngContext__ traversal → Production Build returns Number, not Object
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/solve-drag", response_model=SolveDragPuzzleResponse, dependencies=[Depends(require_survey_ready)])
async def api_solve_drag(req: SolveDragPuzzleRequest):
    """
    Solves Angular CDK drag-drop puzzles (PureSpectrum "Zahl X").
    
    Tool: survey-cli/tools/tool_solve_drag_puzzle.py (147 lines, APPROACH B PRIMARY)
    
    APPROACH B (verified 2026-05-10):
      1. CDP Runtime.evaluate → extract puzzle number from text ("Zahl 52")
      2. Find target image: img[alt="52"] in .cdk-drag container
      3. Find drop zone: second .cdk-drop-list (NOT id="dropZoneList"!)
      4. CDP Input.dispatchMouseEvent chain:
         - mousePressed at img center
         - 10× mouseMoved with arc offset (realistic movement)
         - mouseReleased at drop zone center
      5. Verify: drop zone has img OR "Nächste" button enabled
    
    E2E Test: Survey 49517969 (PureSpectrum) → 66% → "Zahl 28" puzzle
    → Approach B → 100% → screen-out (€0, but puzzle SOLVED ✅)
    
    BANNED Methods (from purespectrum-drag-puzzle.md):
      ❌ MouseEvents dispatchEvent → CDK ignores
      ❌ pointermove/pointerup on img element → CDK listens on document.body
      ❌ __ngContext__ traversal → returns Number (not Object) in Production Build
      ❌ window.ng.getComponent() → Debug-API only in Dev-Mode
      ❌ id="dropZoneList" → wrong selector, use .cdk-drop-list class
    """
    try:
        ws = req.ws_url or _get_ws(req.cdp_port)
        result = _solve_drag_puzzle(ws_url=ws, cdp_port=req.cdp_port)
        solved = result.get("status") == "solved"
        update_command_registry("solve_drag_puzzle", solved, result)
        return SolveDragPuzzleResponse(
            status="solved" if solved else "failed",
            solved=solved,
            puzzle_number=result.get("number"),
            approach=result.get("approach"),
            reason=result.get("reason"),
        )
    except Exception as e:
        update_command_registry("solve_drag_puzzle", False, {"error": str(e)})
        return SolveDragPuzzleResponse(status="error", solved=False, reason=str(e))