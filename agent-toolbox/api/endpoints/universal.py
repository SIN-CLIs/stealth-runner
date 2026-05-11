"""================================================================================
UNIVERSAL ENDPOINTS — FastAPI v2 für LangGraph-Tools (kanonischer Pfad)
================================================================================

ZWECK
-----
Stellt die NEUE, kanonische Tool-Registry für den LangGraph-Agenten bereit.
Jedes Tool ist ein FastAPI-Endpoint mit Pydantic-Schema in/out — keine
versteckten JS-Snippets, kein "execute generic action with @eN ref".

Diese v2-Endpoints ERSETZEN funktional folgende v1-Pfade:

  /survey/snapshot       → /v2/scan
  /survey/click          → /v2/click
  /survey/click-angular  → /v2/click           (ein einziger Click-Pfad!)
  /survey/fill-input     → /v2/fill
  /survey/verify         → /v2/verify          (lookup state vom letzten Scan)
  /survey/captcha/solve  → /v2/captcha/detect + /v2/captcha/solve

Die v1-Endpoints bleiben vorerst bestehen (Backward-Compat). Neue
LangGraph-Tools MÜSSEN aber gegen /v2/* programmieren. v1 wird im nächsten
Schritt mit ``@deprecated`` markiert.


ARCHITEKTUR
-----------
::

    LangGraph Node
         │
         ▼
    POST /v2/scan         ──► cdp_universal.scan_port()    ──► ScanResult
    POST /v2/click        ──► Actuator.click(stable_id)    ──► ActionResult
    POST /v2/fill         ──► Actuator.fill(stable_id,...)
    POST /v2/captcha/...  ──► CaptchaRouter.detect_and_solve()

State zwischen Calls:
  Wir halten KEINE persistenten Actuator-/Scanner-Instanzen über
  Request-Grenzen. Jeder Request öffnet eine eigene CDPConnection zum
  passenden Tab (via ``url_contains`` Selector). Das macht die API
  stateless und damit testbar/parallel-fähig. Caching macht der Client.


PUBLIC ENDPOINTS
----------------

POST /v2/scan
    Request:  {cdp_port:int=9999, url_contains:str=""}
    Response: {url, title, frame_count, element_count, elements:[...],
               captcha_frames:[...]}
    elements[i]: {stable_id, role, name, value, tag, state, bbox,
                  attrs, frame_url}

POST /v2/click
    Request:  {stable_id:str, cdp_port:int=9999, url_contains:str=""}
    Response: {success:bool, reason:str, before_hash, after_hash,
               new_url, elapsed_ms}

    Wenn success=False mit reason="unknown_stable_id" → vorher
    /v2/scan aufrufen, dann erneut versuchen.

POST /v2/fill
    Request:  {stable_id, value, clear:bool=True, cdp_port, url_contains}
    Response: {success, reason, elapsed_ms, typed}

POST /v2/press_key
    Request:  {key:str, modifiers:int=0, cdp_port, url_contains}
    Response: {success, reason, elapsed_ms}

POST /v2/captcha/detect
    Request:  {cdp_port, url_contains}
    Response: {found:bool, captcha_type, frame_id, frame_url, dom_hint}

POST /v2/captcha/solve
    Request:  {cdp_port, url_contains}
    Response: {solved:bool, captcha_type, token, reason, elapsed_ms}


BANNED
------
- KEINE neuen Endpoints, die direkt JS via Runtime.evaluate ausführen
- KEINE Endpoints, die ``stable_id`` ignorieren und stattdessen ``index``
  oder rohe CSS-Selektoren nehmen — das ist v1 Legacy und wird sterben.
================================================================================
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field


# Pfad-Hack: survey-cli muss importierbar sein
_workspace_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
_survey_cli_path = os.path.join(_workspace_root, "survey-cli")
if _survey_cli_path not in sys.path:
    sys.path.insert(0, _survey_cli_path)

from survey.cdp_client import CDPConnection  # noqa: E402
from survey.cdp_universal import scan as scan_full  # noqa: E402
from survey.cdp_actuator import Actuator  # noqa: E402
from survey.captcha_router import CaptchaRouter  # noqa: E402


router = APIRouter(prefix="/v2", tags=["universal-v2"])


# ── Hilfsfunktion: Tab-WebSocket auflösen ──────────────────────────────────


def _resolve_ws(cdp_port: int, url_contains: str) -> str:
    """Findet den passenden Page-Tab auf dem CDP-Port.

    Wenn ``url_contains`` leer → erster Page-Tab.
    Sonst → erster Page-Tab dessen URL den Substring enthält.
    Raises RuntimeError wenn nichts passt.
    """
    raw = urllib.request.urlopen(
        f"http://127.0.0.1:{cdp_port}/json/list", timeout=5
    ).read()
    pages = json.loads(raw)
    for p in pages:
        if p.get("type") != "page":
            continue
        if url_contains and url_contains not in p.get("url", ""):
            continue
        return p["webSocketDebuggerUrl"]
    raise RuntimeError(
        f"no page tab on port {cdp_port} matching {url_contains!r}"
    )


# ── Schemas ────────────────────────────────────────────────────────────────


class _Base(BaseModel):
    cdp_port: int = 9999
    url_contains: str = ""


class ScanReq(_Base):
    pass


class ScanResp(BaseModel):
    status: str
    url: str = ""
    title: str = ""
    frame_count: int = 0
    element_count: int = 0
    elements: list[dict[str, Any]] = Field(default_factory=list)
    captcha_frames: list[dict[str, str]] = Field(default_factory=list)
    reason: str = ""


class ClickReq(_Base):
    stable_id: str


class ClickResp(BaseModel):
    status: str
    success: bool = False
    reason: str = ""
    before_hash: str = ""
    after_hash: str = ""
    new_url: str = ""
    elapsed_ms: float = 0.0


class FillReq(_Base):
    stable_id: str
    value: str
    clear: bool = True


class FillResp(BaseModel):
    status: str
    success: bool = False
    reason: str = ""
    elapsed_ms: float = 0.0
    typed: str = ""


class PressKeyReq(_Base):
    key: str
    modifiers: int = 0


class PressKeyResp(BaseModel):
    status: str
    success: bool = False
    reason: str = ""
    elapsed_ms: float = 0.0


class CaptchaDetectReq(_Base):
    pass


class CaptchaDetectResp(BaseModel):
    status: str
    found: bool = False
    captcha_type: str = ""
    frame_id: str = ""
    frame_url: str = ""
    dom_hint: str = ""
    reason: str = ""


class CaptchaSolveReq(_Base):
    pass


class CaptchaSolveResp(BaseModel):
    status: str
    solved: bool = False
    captcha_type: str = ""
    token: str = ""
    reason: str = ""
    elapsed_ms: float = 0.0


# ── Endpoints ──────────────────────────────────────────────────────────────


@router.post("/scan", response_model=ScanResp)
def v2_scan(req: ScanReq) -> ScanResp:
    """Vollständiger AX+DOM-Scan eines Browser-Tabs (alle Frames + Shadow-DOM).

    Liefert flache Liste von ``UniversalElement``-Dicts. Jedes hat eine
    ``stable_id``, die für ``/v2/click`` und ``/v2/fill`` verwendet wird.
    """
    try:
        ws = _resolve_ws(req.cdp_port, req.url_contains)
        with CDPConnection(ws) as cdp:
            result = scan_full(cdp)
        # ScanResult.elements ist eine Liste von Dataclasses → dict-Cast
        elements_dicts = []
        for e in result.elements:
            elements_dicts.append({
                "stable_id": e.stable_id,
                "frame_id": e.frame_id,
                "role": e.role,
                "name": e.name,
                "value": e.value,
                "tag": e.tag,
                "text": e.text,
                "state": e.state,
                "bbox": e.bbox,
                "attrs": e.attrs,
                "frame_url": e.frame_url,
            })
        return ScanResp(
            status="ok",
            url=result.url,
            title=result.title,
            frame_count=result.frame_count,
            element_count=len(elements_dicts),
            elements=elements_dicts,
            captcha_frames=result.captcha_frames,
        )
    except Exception as e:
        return ScanResp(status="error", reason=str(e))


@router.post("/click", response_model=ClickResp)
def v2_click(req: ClickReq) -> ClickResp:
    """Echter Maus-Klick + Pflicht-Verify via DOM-Diff.

    Hinweis: Der Server scannt INTERNAL neu, um die ``stable_id`` aufzulösen.
    Das kostet einen zusätzlichen Roundtrip pro Klick, garantiert aber
    Konsistenz wenn der Client einen veralteten Scan hat.
    """
    try:
        ws = _resolve_ws(req.cdp_port, req.url_contains)
        with CDPConnection(ws) as cdp:
            actuator = Actuator(cdp)
            actuator.refresh_scan()
            result = actuator.click(req.stable_id)
        return ClickResp(
            status="ok" if result.success else "error",
            success=result.success,
            reason=result.reason,
            before_hash=result.before_hash,
            after_hash=result.after_hash,
            new_url=result.new_url,
            elapsed_ms=result.elapsed_ms,
        )
    except Exception as e:
        return ClickResp(status="error", reason=str(e))


@router.post("/fill", response_model=FillResp)
def v2_fill(req: FillReq) -> FillResp:
    """Tippt ``value`` in das Element via echte Tastenanschläge."""
    try:
        ws = _resolve_ws(req.cdp_port, req.url_contains)
        with CDPConnection(ws) as cdp:
            actuator = Actuator(cdp)
            actuator.refresh_scan()
            result = actuator.fill(req.stable_id, req.value, clear=req.clear)
        typed = ""
        if result.extra and "typed" in result.extra:
            typed = result.extra["typed"]
        return FillResp(
            status="ok" if result.success else "error",
            success=result.success,
            reason=result.reason,
            elapsed_ms=result.elapsed_ms,
            typed=typed,
        )
    except Exception as e:
        return FillResp(status="error", reason=str(e))


@router.post("/press_key", response_model=PressKeyResp)
def v2_press_key(req: PressKeyReq) -> PressKeyResp:
    """Globaler Tastendruck (Enter, Tab, Escape, ...)."""
    try:
        ws = _resolve_ws(req.cdp_port, req.url_contains)
        with CDPConnection(ws) as cdp:
            actuator = Actuator(cdp)
            result = actuator.press_key(req.key, modifiers=req.modifiers)
        return PressKeyResp(
            status="ok" if result.success else "error",
            success=result.success,
            reason=result.reason,
            elapsed_ms=result.elapsed_ms,
        )
    except Exception as e:
        return PressKeyResp(status="error", reason=str(e))


@router.post("/captcha/detect", response_model=CaptchaDetectResp)
def v2_captcha_detect(req: CaptchaDetectReq) -> CaptchaDetectResp:
    """Erkennt Captchas auf dem aktiven Tab (iframe-URL + DOM-Fallbacks)."""
    try:
        ws = _resolve_ws(req.cdp_port, req.url_contains)
        with CDPConnection(ws) as cdp:
            result = scan_full(cdp)
            router_obj = CaptchaRouter(cdp)
            det = router_obj.detect(result)
        if det is None:
            return CaptchaDetectResp(status="ok", found=False)
        return CaptchaDetectResp(
            status="ok",
            found=True,
            captcha_type=det.captcha_type,
            frame_id=det.frame_id,
            frame_url=det.frame_url,
            dom_hint=det.dom_hint,
        )
    except Exception as e:
        return CaptchaDetectResp(status="error", reason=str(e))


@router.post("/captcha/solve", response_model=CaptchaSolveResp)
def v2_captcha_solve(req: CaptchaSolveReq) -> CaptchaSolveResp:
    """Erkennt UND löst Captchas in einem Schritt.

    Wenn kein Captcha gefunden → solved=False, reason='no_captcha_found'.
    Wenn Captcha gefunden aber kein Solver → reason='no_solver_for_type'.
    """
    try:
        ws = _resolve_ws(req.cdp_port, req.url_contains)
        with CDPConnection(ws) as cdp:
            result = scan_full(cdp)
            router_obj = CaptchaRouter(cdp)
            solve_res = router_obj.detect_and_solve(result)
        if solve_res is None:
            return CaptchaSolveResp(
                status="ok", solved=False, reason="no_captcha_found"
            )
        return CaptchaSolveResp(
            status="ok" if solve_res.solved else "error",
            solved=solve_res.solved,
            captcha_type=solve_res.captcha_type,
            token=solve_res.token,
            reason=solve_res.reason,
            elapsed_ms=solve_res.elapsed_ms,
        )
    except Exception as e:
        return CaptchaSolveResp(status="error", reason=str(e))
