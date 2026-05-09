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

from fastapi import APIRouter
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


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTER
# ═══════════════════════════════════════════════════════════════════════════════

router = APIRouter(prefix="/survey", tags=["survey-tools"])


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINT: POST /survey/open
# ═══════════════════════════════════════════════════════════════════════════════
# Wrapper für tools.tool_open_survey.open_survey()
# 
# Flow:
#   1. CPX API → Survey URL holen
#   2. Dashboard Tab → clickSurvey() JS call
#   3. Modal-Button klicken (CUA oder CDP)
#   4. Neuer Tab? → Survey-Tab Info zurückgeben
#   5. Kein Tab? → Fallback: Neuen Tab erstellen

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
# EXPORTS
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    "router",
    "OpenSurveyRequest", "OpenSurveyResponse",
    "CloseSurveyRequest", "CloseSurveyResponse",
    "FillSurveyRequest", "FillSurveyResponse",
    "RateSurveyRequest", "RateSurveyResponse",
]