#!/usr/bin/env python3
"""╔═══════════════════════════════════════════════════════════════════════════════╗
║  SURVEY TOOLS FASTAPI WRAPPER — survey-cli/tools/ → FastAPI Endpoints          ║
║                                                                               ║
║  PFLICHT (aus AGENTS.md §GOLDENE REGEL):                                       ║
║  → NIE monolithische Endpoints bauen!                                         ║
║  → JEDES survey-cli/tool_*.py bekommt einen FastAPI-Wrapper                    ║
║  → Die Tools sind bereits getestet, profil-aware, provider-aware               ║
║  → Der Endpoint ist NUR ein Wrapper (max 20 Zeilen pro Endpoint)               ║
╚═══════════════════════════════════════════════════════════════════════════════╝"""

from __future__ import annotations

import json
import os
import sys
from typing import Dict, List, Optional, Any
import json, asyncio, websockets, urllib.request

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# ═══════════════════════════════════════════════════════════════════════════════
# IMPORT survey-cli/tools (REQUIRES survey-cli/ in PYTHONPATH)
# ═══════════════════════════════════════════════════════════════════════════════
# WARUM sys.path.insert?
# → survey-cli/ liegt im Workspace-Root, nicht in agent-toolbox/
# → FastAPI App (start_toolbox.py) hat survey-cli/ bereits im sys.path
# → Aber bei direktem Import in api/ kann der Path fehlen
# → Wir fügen ihn sicherheitshalber hinzu (kein ImportError)

_workspace_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))  # agent-toolbox/api/ → agent-toolbox/ → stealth-runner/
_survey_cli_path = os.path.join(_workspace_root, "survey-cli")
if _survey_cli_path not in sys.path:
    sys.path.insert(0, _survey_cli_path)

# Tool-Imports (survey-cli/tools/ sind bereits getestet, frozen=True)
from tools.tool_open_survey import open_survey, close_survey_tab
from tools.tool_fill_survey import SurveyFiller
from tools.tool_rate_survey import rate_survey

# Provider-specific tools (survey-cli/survey/providers/)
from survey.providers.purespectrum import solve_purespectrum_preflight

# LangGraph NEMO pipeline (survey-cli/survey/graph/)
from survey.graph import create_graph, SurveyState


# ═══════════════════════════════════════════════════════════════════════════════
# PYDANTIC SCHEMAS — Für jede Request/Response
# ═══════════════════════════════════════════════════════════════════════════════
# WARUM Schemas?
# → FastAPI validiert Requests automatisch (422 bei fehlenden Feldern)
# → Swagger UI zeigt Schemas an → Agent weiß was zu senden
# → Typ-Sicherheit: Pydantic prüft Typen zur Laufzeit


class OpenSurveyRequest(BaseModel):
    """POST /survey/open Request."""
    survey_id: str
    pid: int = 0
    wid: int = 0
    cdp_port: int = 9999
    wait_modal: float = 3.0
    wait_load: float = 5.0


class OpenSurveyResponse(BaseModel):
    """POST /survey/open Response."""
    status: str  # "ok" | "error"
    tab_id: Optional[str] = None
    ws_url: Optional[str] = None
    provider: Optional[str] = None
    url: Optional[str] = None
    modal_clicked: Optional[bool] = None
    flow: Optional[str] = None
    reason: Optional[str] = None
    stage: Optional[str] = None


class CloseSurveyRequest(BaseModel):
    """POST /survey/close Request."""
    tab_id: str
    cdp_port: int = 9999


class CloseSurveyResponse(BaseModel):
    """POST /survey/close Response."""
    status: str  # "ok" | "error"
    closed: bool
    tab_id: str
    reason: Optional[str] = None


class FillSurveyRequest(BaseModel):
    """POST /survey/fill Request."""
    # Compact Snapshot der aktuellen Seite (von survey-cli/snapshot.py)
    snapshot: Dict[str, Any]
    profile_name: str = "sin_agent_heypiggy"
    # Optional: Nemotron NIM Entscheidung statt Rule-based
    use_nim: bool = False


class FillSurveyResponse(BaseModel):
    """POST /survey/fill Response."""
    status: str  # "ok" | "error"
    actions: List[Dict[str, Any]] = []
    question_type: Optional[str] = None
    provider: Optional[str] = None
    confidence: Optional[float] = None
    reason: Optional[str] = None


class RateSurveyRequest(BaseModel):
    """POST /survey/rate Request."""
    cdp_port: int = 9999
    verify: bool = True


class RateSurveyResponse(BaseModel):
    """POST /survey/rate Response."""
    status: str  # "ok" | "not_found" | "error"
    bonus: float = 0.0
    tab_id: Optional[str] = None
    verified: Optional[bool] = None
    reason: Optional[str] = None


class PurespectrumPreflightRequest(BaseModel):
    """POST /survey/purespectrum-preflight Request."""
    tab_id: str
    ws_url: Optional[str] = None
    cdp_port: int = 9999
    debug: bool = False


class PurespectrumPreflightResponse(BaseModel):
    """POST /survey/purespectrum-preflight Response."""
    status: str  # "ok" | "error"
    success: bool
    steps: List[str] = []
    provider: Optional[str] = "purespectrum"
    captcha_text: Optional[str] = None
    tokens_used: Optional[int] = None
    error: Optional[str] = None


class RunGraphRequest(BaseModel):
    """POST /survey/run-graph Request."""
    survey_id: str
    provider: str = ""
    cdp_port: int = 9999
    max_iterations: int = 15


class RunGraphResponse(BaseModel):
    """POST /survey/run-graph Response."""
    status: str
    earned: float = 0.0
    survey_id: str = ""
    provider: str = ""
    iterations: int = 0
    errors: int = 0
    screen_out: bool = False
    completion_detected: bool = False


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTER
# ═══════════════════════════════════════════════════════════════════════════════

router = APIRouter(prefix="/survey", tags=["survey-tools"])


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINT: POST /survey/open
# Wrapper für tools.tool_open_survey.open_survey()
# 
# Flow:
#   1. CPX API → Survey URL holen
#   2. Dashboard Tab → clickSurvey() JS call
#   3. Modal-Button klicken via window.open interception + Target.createTarget
#      (CUA FAILS: Chrome Popup Blocker! CDP b.click() FAILS! Target.createTarget WIN!)
#   4. Survey-Tab Info zurückgeben
#   5. Kein Tab? → Fallback: _create_tab() via Target.createTarget

@router.post("/open", response_model=OpenSurveyResponse)
async def api_open_survey(req: OpenSurveyRequest):
    """
    Öffnet eine Survey vom HeyPiggy Dashboard.
    
    Kapselt: tools.tool_open_survey.open_survey()
    
    Args:
        survey_id: CPX Survey ID (z.B. "66844385")
        pid/wid: CUA Window ID für Modal-Handling (optional)
        cdp_port: CDP Port (default: 9999)
        wait_modal: Sekunden warten auf Modal (default: 3)
        wait_load: Sekunden warten auf Survey-Ladung (default: 5)
    
    Returns:
        OpenSurveyResponse:
          - status: "ok" oder "error"
          - tab_id: Tab-ID des Survey-Tabs
          - ws_url: WebSocket URL für CDP
          - provider: "qualtrics", "toluna", "cint", "nfield", ...
          - url: Aktuelle URL des Survey-Tabs
          - flow: "new_tab" | "in_page" | "fallback_new_tab"
    """
    result = open_survey(
        survey_id=req.survey_id,
        pid=req.pid,
        wid=req.wid,
        port=req.cdp_port,
        wait_modal=req.wait_modal,
        wait_load=req.wait_load,
    )
    return OpenSurveyResponse(**result)


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINT: POST /survey/close
# ═══════════════════════════════════════════════════════════════════════════════
# Wrapper für tools.tool_open_survey.close_survey_tab()

@router.post("/close", response_model=CloseSurveyResponse)
async def api_close_survey(req: CloseSurveyRequest):
    """
    Schließt einen Survey-Tab und kehrt zum Dashboard zurück.
    
    Kapselt: tools.tool_open_survey.close_survey_tab()
    
    Args:
        tab_id: Tab-ID des zu schließenden Survey-Tabs
        cdp_port: CDP Port (default: 9999)
    
    Returns:
        CloseSurveyResponse:
          - status: "ok" oder "error"
          - closed: True wenn Tab erfolgreich geschlossen
    """
    success = close_survey_tab(req.tab_id, req.cdp_port)
    return CloseSurveyResponse(
        status="ok" if success else "error",
        closed=success,
        tab_id=req.tab_id,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINT: POST /survey/fill
# ═══════════════════════════════════════════════════════════════════════════════
# Wrapper für tools.tool_fill_survey.SurveyFiller.decide_actions()
#
# Flow:
#   1. Compact Snapshot der aktuellen Seite
#   2. Question Classification (Rule-based oder Nemotron NIM)
#   3. Profile-Matching (Alter, Geschlecht, PLZ, etc.)
#   4. Fuzzy Option Matching
#   5. Actions Array zurückgeben

@router.post("/fill", response_model=FillSurveyResponse)
async def api_fill_survey(req: FillSurveyRequest):
    """
    Entscheidet die beste Antwort für eine Survey-Seite basierend auf Profil.
    
    Kapselt: tools.tool_fill_survey.SurveyFiller.decide_actions()
    
    Args:
        snapshot: Compact Snapshot der aktuellen Seite
          {
            "questions": ["Was ist Ihr Geschlecht?"],
            "options": [["Männlich", "Weiblich", "Divers"]],
            "input_fields": [],
            "provider": "qualtrics",
            "progress": "3/10"
          }
        profile_name: Profil-Name (default: "sin_agent_heypiggy")
        use_nim: Nemotron NIM für Entscheidung (default: False, rule-based)
    
    Returns:
        FillSurveyResponse:
          - status: "ok" oder "error"
          - actions: Liste von Actions (z.B. [{"type": "radio", "question_idx": 0, "option_idx": 0}])
          - question_type: "single_choice" | "multi_choice" | "text" | "matrix" | ...
          - confidence: 0.0-1.0
    """
    try:
        filler = SurveyFiller(req.profile_name)
        actions = filler.decide_actions(req.snapshot)
        
        # Question-Type aus Actions ableiten
        question_type = "unknown"
        if actions:
            first_action = actions[0]
            question_type = first_action.get("type", "unknown")
        
        return FillSurveyResponse(
            status="ok",
            actions=actions,
            question_type=question_type,
            provider=req.snapshot.get("provider"),
            confidence=0.85,  # TODO: Aus Nemotron oder Fuzzy-Matching ableiten
        )
    except Exception as e:
        return FillSurveyResponse(
            status="error",
            reason=str(e),
        )


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINT: POST /survey/rate
# ═══════════════════════════════════════════════════════════════════════════════
# Wrapper für tools.tool_rate_survey.rate_survey()
#
# Flow:
#   1. Scannt alle Tabs nach rating.php oder cpx-research URL
#   2. Klickt Rating-Button (4 Sterne sind meist pre-selected)
#   3. Verifiziert: Tab navigiert weg oder schließt sich
#   4. Gibt +0.01€ Bonus zurück

@router.post("/rate", response_model=RateSurveyResponse)
async def api_rate_survey(req: RateSurveyRequest):
    """
    Bewertet eine abgeschlossene Survey für +0.01€ Bonus.
    
    Kapselt: tools.tool_rate_survey.rate_survey()
    
    Args:
        cdp_port: CDP Port (default: 9999)
        verify: Verifizieren dass Rating wirklich abgeschickt wurde (default: True)
    
    Returns:
        RateSurveyResponse:
          - status: "ok" | "not_found" | "error"
          - bonus: 0.01€ wenn erfolgreich
          - tab_id: ID des Rating-Tabs
          - verified: True wenn Verifikation bestanden
    """
    result = rate_survey(port=req.cdp_port, verify=req.verify)
    return RateSurveyResponse(**result)


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER: Resolve ws_url from tab_id
# ═══════════════════════════════════════════════════════════════════════════════

def _resolve_ws_from_tab(tab_id: str, port: int = 9999) -> Optional[str]:
    """Get WebSocket URL for a specific tab_id."""
    try:
        pages = json.loads(urllib.request.urlopen(
            f"http://127.0.0.1:{port}/json", timeout=3).read())
        for p in pages:
            if p.get("id") == tab_id:
                return p.get("webSocketDebuggerUrl")
    except Exception:
        pass
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINT: POST /survey/purespectrum-preflight
# ═══════════════════════════════════════════════════════════════════════════════
# Wrapper für survey.providers.purespectrum.solve_purespectrum_preflight()
#
# Flow (survey-cli/survey/providers/purespectrum.py):
#   1. Cookie Consent (.cky-btn-accept click)
#   2. ROBOT textarea fill (min 5 words)
#   3. Text captcha → NVIDIA Vision OCR (base64 screenshot → llama-vision)
#   4. Drag puzzle (number box: "Bitte legen Sie die Zahl 52...")
#   5. Returns step-by-step results

@router.post("/purespectrum-preflight", response_model=PurespectrumPreflightResponse)
async def api_purespectrum_preflight(req: PurespectrumPreflightRequest):
    """
    Führt PureSpectrum preflight aus: cookie → ROBOT → captcha OCR → puzzle.
    
    Kapselt: survey.providers.purespectrum.solve_purespectrum_preflight()
    
    Args:
        tab_id: Tab-ID des Survey-Tabs (wird in ws_url aufgelöst)
        ws_url: Optional - direkt die CDP WebSocket URL
        cdp_port: CDP Port (default: 9999)
        debug: Debug-Output aktivieren (default: False)
    
    Returns:
        PurespectrumPreflightResponse:
          - status: "ok" oder "error"
          - success: True wenn alle Schritte erfolgreich
          - steps: ["cookie", "robot", "captcha:True", "puzzle:False"]
          - captcha_text: OCR erkannter Text (falls captcha vorhanden)
          - tokens_used: NVIDIA Vision Token-Verbrauch
    """
    ws_url = req.ws_url or _resolve_ws_from_tab(req.tab_id, req.cdp_port)
    if not ws_url:
        return PurespectrumPreflightResponse(
            status="error",
            success=False,
            error=f"Could not resolve WebSocket URL for tab {req.tab_id}",
        )
    
    result = solve_purespectrum_preflight(ws_url, debug=req.debug)
    
    return PurespectrumPreflightResponse(
        status="ok" if result.get("success") else "error",
        success=result.get("success", False),
        steps=result.get("steps", []),
        provider="purespectrum",
        captcha_text=result.get("captcha_text"),
        tokens_used=result.get("tokens_used"),
        error=result.get("error"),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINT: POST /survey/run-graph
# ═══════════════════════════════════════════════════════════════════════════════
# Wrapper für survey.graph.create_graph() + SurveyState.
#
# Flow:
#   1. ensure_chrome → open_survey → inject_cookies → snapshot → decide → execute → detect_completion
#   2. Full NEMO loop via LangGraph StateGraph.
#   3. Returns final SurveyState with status and earnings.

@router.post("/run-graph", response_model=RunGraphResponse)
async def api_run_survey_graph(req: RunGraphRequest):
    """
    Führt eine Survey durch die LangGraph-Pipeline aus.

    Kapselt: survey.graph.create_graph() + SurveyState

    Args:
        survey_id: HeyPiggy Survey-ID (z.B. "67064749")
        provider: Provider-Name (z.B. "purespectrum", "cint", "toluna")
        cdp_port: CDP Port (default: 9999)
        max_iterations: Maximale NEMO-Loop-Iterationen (default: 15)

    Returns:
        RunGraphResponse:
          - status: "completed" | "screen_out" | "error" | "delegated" | ...
          - earned: balance_after - balance_before (€)
          - survey_id: Survey-ID
          - provider: Provider-Name
          - iterations: Anzahl ausgeführter Iterationen
          - errors: Anzahl gesammelter Fehler
          - screen_out: True wenn disqualifiziert
          - completion_detected: True wenn Survey komplett
    """
    try:
        graph = create_graph()
        state = SurveyState(
            survey_id=req.survey_id,
            provider=req.provider,
            cdp_port=req.cdp_port,
            max_iterations=req.max_iterations,
        )

        # LangGraph ist synchron → in Thread-Pool ausführen
        final = await asyncio.to_thread(graph.invoke, state)

        return RunGraphResponse(
            status=final.status,
            earned=final.balance_earned,
            survey_id=final.survey_id,
            provider=final.provider,
            iterations=final.iteration,
            errors=len(final.errors),
            screen_out=final.screen_out,
            completion_detected=final.completion_detected,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORTS
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    "router",
    "OpenSurveyRequest", "OpenSurveyResponse",
    "CloseSurveyRequest", "CloseSurveyResponse",
    "FillSurveyRequest", "FillSurveyResponse",
    "RateSurveyRequest", "RateSurveyResponse",
    "PurespectrumPreflightRequest", "PurespectrumPreflightResponse",
    "RunGraphRequest", "RunGraphResponse",
    "solve_purespectrum_preflight",
]