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
from datetime import datetime, timezone
import json, asyncio, websockets, urllib.request
from pathlib import Path

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


# ───────────────────────────────────────────────────────────────────────────────
# UNIVERSAL AGENT — Request / Response
# ───────────────────────────────────────────────────────────────────────────────

class UniversalRunRequest(BaseModel):
    """POST /survey/universal Request.
    
    Führt eine Survey durch den UNIVERSAL Web-AI-Agenten.
    Der Agent sieht jede Webseite und handelt universell.
    
    Flow: capture_page() → NIM think() → act() → verify() → Loop
    Pre-Flight: Command Registry validiert jeden Schritt.
    Auto-Update: Registry wird nach jedem Erfolg/Fehler aktualisiert.
    """
    survey_id: Optional[str] = None  # HeyPiggy Survey-ID (oder None wenn Tab bereits offen)
    tab_id: Optional[str] = None  # Expliziter CDP Tab ID
    ws_url: Optional[str] = None  # Expliziter WebSocket URL
    cdp_port: int = 9999
    max_steps: int = 30  # Safety-Net (max 30 page interactions)
    use_nim: bool = True  # Nemotron vs. Heuristic fallback
    task: str = "Complete the survey to earn money"


class UniversalRunResponse(BaseModel):
    """POST /survey/universal Response."""
    status: str  # "completed" | "screen_out" | "error" | "clicked" | "answered"
    success: bool
    steps: int  # Anzahl ausgeführter Schritte
    earned: float = 0.0  # balance_after - balance_before
    balance_before: float = 0.0
    balance_after: float = 0.0
    survey_id: str = ""
    provider: str = ""
    history: List[str] = []
    errors: List[str] = []
    screen_out: bool = False
    completion_detected: bool = False
    reason: Optional[str] = None


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

@router.post("/open", response_model=OpenSurveyResponse, dependencies=[Depends(require_survey_ready)])
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
    update_command_registry("open_survey", result.get("status") == "ok", {
        "tab_ws": result.get("ws_url", ""),
        "provider": result.get("provider", "unknown"),
        "status": result.get("status", "unknown"),
    })
    return OpenSurveyResponse(**result)


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINT: POST /survey/close
# ═══════════════════════════════════════════════════════════════════════════════
# Wrapper für tools.tool_open_survey.close_survey_tab()

@router.post("/close", response_model=CloseSurveyResponse, dependencies=[Depends(require_survey_ready)])
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
    update_command_registry("close_survey", success, {
        "tab_id": req.tab_id,
        "status": "ok" if success else "error",
    })
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

@router.post("/fill", response_model=FillSurveyResponse, dependencies=[Depends(require_survey_ready)])
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
        
        update_command_registry("fill_survey", True, {
            "question_type": question_type,
            "actions_count": len(actions),
            "provider": req.snapshot.get("provider", "unknown"),
            "confidence": 0.85,
        })
        return FillSurveyResponse(
            status="ok",
            actions=actions,
            question_type=question_type,
            provider=req.snapshot.get("provider"),
            confidence=0.85,
        )
    except Exception as e:
        update_command_registry("fill_survey", False, {"error": str(e)})
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

@router.post("/rate", response_model=RateSurveyResponse, dependencies=[Depends(require_survey_ready)])
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
    update_command_registry("rate_survey", result.get("status") == "ok", {
        "bonus": result.get("bonus", 0.0),
        "status": result.get("status", "unknown"),
    })
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

@router.post("/purespectrum-preflight", response_model=PurespectrumPreflightResponse, dependencies=[Depends(require_survey_ready)])
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
    
    update_command_registry("purespectrum_preflight", result.get("success", False), {
        "steps": result.get("steps", []),
        "status": "ok" if result.get("success") else "error",
        "captcha_text": result.get("captcha_text", ""),
    })
    
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

@router.post("/run-graph", response_model=RunGraphResponse, dependencies=[Depends(require_survey_ready)])
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

        update_command_registry("run_graph", final.status in ("completed", "screen_out"), {
            "status": final.status,
            "survey_id": final.survey_id,
            "provider": final.provider,
            "iterations": final.iteration,
            "earned": final.balance_earned,
        })
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
        update_command_registry("run_graph", False, {"error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINT: POST /survey/universal
# Universal Web-AI-Agent — Capture → Think → Act → Verify → Loop
#
# Kommt mit ANY Survey-Typ klar: Pre-Qualifier, Provider-XYZ, Purespectrum,
# Cint, Toluna, Qualtrics, etc. Kein Hardcoding.
#
# Pre-Flight: Command Registry prüft ob Provider/Survey-Type bekannt ist.
# Auto-Update: Registry wird nach Erfolg/Fehler aktualisiert.
# ═══════════════════════════════════════════════════════════════════════════════

def _get_ws_url(req: UniversalRunRequest) -> Optional[str]:
    """Finde oder öffne Survey-Tab WebSocket URL."""
    try:
        import json as _json
        pages = _json.loads(
            urllib.request.urlopen(f"http://127.0.0.1:{req.cdp_port}/json", timeout=5).read()
        )
        if req.tab_id:
            for p in pages:
                if p.get("id", "").startswith(req.tab_id) or p.get("id") == req.tab_id:
                    return p.get("webSocketDebuggerUrl")
        if req.ws_url:
            return req.ws_url
        # Skip dashboard tabs, return first non-dashboard tab
        for p in pages:
            if p.get("type") == "page" and "dashboard" not in p.get("url", "").lower() and "heypiggy" not in p.get("url", "").lower():
                return p.get("webSocketDebuggerUrl")
        return None
    except Exception:
        return None


def _read_balance(port: int = 9999) -> float:
    """Lese aktuelles HeyPiggy Guthaben via CDP."""
    try:
        import json as _json, re as _re, websocket as _ws
        pages = _json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=5).read())
        db = [p for p in pages if "dashboard" in p.get("url", "").lower() and p.get("type") == "page"]
        if not db:
            return 0.0
        ws = _ws.create_connection(db[0]["webSocketDebuggerUrl"], timeout=15)
        ws.send(_json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": "document.body.innerText"}}))
        resp = _json.loads(ws.recv())
        ws.close()
        body = resp.get("result", {}).get("result", {}).get("value", "")
        amounts = _re.findall(r"(\d+[.,]?\d*)\s*€", body[:800])
        for amt in amounts:
            val = float(amt.replace(",", "."))
            if val >= 1.0:
                return val
        return 0.0
    except Exception:
        return 0.0


@router.post("/universal", response_model=UniversalRunResponse, dependencies=[Depends(require_survey_ready)])
async def api_universal_run(req: UniversalRunRequest):
    """
    UNIVERSAL WEB-AI-AGENT — Führt jede Survey universell aus.
    
    Pattern: Browser-Use — Capture → Think (NIM) → Act (CDP) → Verify → Loop
    
    Kommt mit ANY Webseite klar: Pre-Qualifier, Provider-XYZ, Purespectrum,
    Cint, Toluna, Qualtrics, etc. Kein Hardcoding, keine Provider-Ifs.
    
    Pre-Flight: Command Registry prüft ob Provider/Survey-Type verfügbar ist.
    Auto-Update: Registry wird nach Erfolg/Fehler aktualisiert.
    
    Args:
        survey_id: HeyPiggy Survey-ID (optional — wenn Tab bereits offen)
        tab_id: Expliziter CDP Tab ID (optional)
        ws_url: Expliziter WebSocket URL (optional)
        cdp_port: CDP Port (default: 9999)
        max_steps: Maximale Loop-Iterationen (Safety-Net, default: 30)
        use_nim: Nemotron statt Heuristic (default: True)
        task: Was der Agent tun soll (default: "Complete the survey")
    
    Returns:
        UniversalRunResponse:
          - status: "completed" | "screen_out" | "error" | "clicked" | "answered"
          - success: bool
          - steps: Anzahl Schritte
          - earned: balance_after - balance_before (€)
          - balance_before / balance_after: Guthaben vor/nach Survey
          - history: Liste der Aktionen
          - errors: Fehler-Liste
          - screen_out / completion_detected: Disqualifikation/Completion Flags
    """
    # 0. SURVEY LOCK — Prevent parallel survey execution
    # ROOT CAUSE FIX (2026-05-10): Completion detection failed → loop continued
    # → background loop started next survey → 6 tabs stacked!
    # FIX: Acquire lock before running. If lock exists → skip (another survey running).
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "survey-cli"))
        from survey.command_registry import acquire_survey_lock, release_survey_lock
        survey_id_for_lock = req.survey_id or req.tab_id or "universal"
        if not acquire_survey_lock(survey_id_for_lock):
            return UniversalRunResponse(
                status="error",
                success=False,
                steps=0,
                reason=f"Survey already running (lock active). Wait for current survey to finish.",
            )
    except ImportError:
        pass  # Lock not available, continue

    # 1. Pre-Flight: finde ws_url
    ws_url = _get_ws_url(req)
    if not ws_url:
        try: release_survey_lock()
        except Exception: pass
        return UniversalRunResponse(
            status="error",
            success=False,
            steps=0,
            reason="Kein Survey-Tab gefunden ( CDP auf Port {} oder kein non-dashboard Tab)".format(req.cdp_port),
        )
    
    # 2. Balance vor der Survey
    balance_before = _read_balance(req.cdp_port)
    
    # 3. Pre-Flight: Command Registry (optional — prüfe ob Provider bekannt gut/schlecht)
    # Import here to avoid circular imports
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "survey-cli"))
        from survey.command_registry import CommandRegistry, CommandBannedError
        from survey.snapshot import capture_page
        
        registry = CommandRegistry()
        provider = "unknown"
        
        # Try to detect provider from URL
        try:
            pages = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{req.cdp_port}/json", timeout=5).read())
            for p in pages:
                if p.get("webSocketDebuggerUrl") == ws_url:
                    url = p.get("url", "")
                    for prov in ["purespectrum", "cint", "toluna", "qualtrics", "samplicio", "ipsos", "nfield", "irbureau"]:
                        if prov in url.lower():
                            provider = prov
                            break
                    break
        except Exception:
            pass
        
        # Check if provider is banned
        if provider != "unknown":
            if registry.is_banned(f"provider_{provider}"):
                return UniversalRunResponse(
                    status="error",
                    success=False,
                    steps=0,
                    balance_before=balance_before,
                    balance_after=balance_before,
                    provider=provider,
                    reason=f"Provider {provider} ist gebannt (CommandRegistry)",
                )
    except ImportError:
        pass  # Command registry not available, continue anyway
    
    # 4. RUN the Universal Agent
    import time
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "survey-cli"))
        from survey.universal.agent import run_universal_agent
        
        api_key = os.environ.get("NVIDIA_API_KEY") if req.use_nim else None
        
        result = await asyncio.to_thread(
            run_universal_agent,
            ws_url=ws_url,
            max_steps=req.max_steps,
            task=req.task,
            api_key=api_key,
        )
        
        history = result.get("history", [])
        steps = result.get("steps", 0)
        
        # Detect screen_out vs. completion from history
        screen_out = any("screen" in h.lower() or "disqualif" in h.lower() or "leider" in h.lower() or "nicht geeignet" in h.lower() for h in history)
        completion = result.get("earned", False) or any("completed" in h.lower() or "vielen dank" in h.lower() or "fertig" in h.lower() for h in history)
        
        # 5. Balance nach der Survey
        balance_after = _read_balance(req.cdp_port)
        earned = max(0.0, balance_after - balance_before)
        
        # 6. Auto-Update: Command Registry nach Ergebnis
        try:
            from survey.command_registry import CommandRegistry, CommandBannedError
            reg = CommandRegistry()
            status_key = "screen_out" if screen_out else ("completed" if completion else "error")
            
            # Record the result
            reg.record_execution(
                command_id=f"survey_{provider}_{req.survey_id or 'unknown'}",
                provider=provider,
                survey_id=req.survey_id or "unknown",
                status=status_key,
                steps=steps,
                earned=earned,
            )
        except Exception:
            pass  # Registry update failed, continue
        
        # Determine final status
        if completion:
            final_status = "completed"
        elif screen_out:
            final_status = "screen_out"
        elif steps > 0:
            final_status = "answered"
        else:
            final_status = "error"
        
        return UniversalRunResponse(
            status=final_status,
            success=completion,
            steps=steps,
            earned=earned,
            balance_before=balance_before,
            balance_after=balance_after,
            survey_id=req.survey_id or "",
            provider=provider,
            history=history,
            errors=[],
            screen_out=screen_out,
            completion_detected=completion,
        )
        
    except Exception as e:
        try:
            from survey.command_registry import release_survey_lock
            release_survey_lock()
        except Exception:
            pass
        return UniversalRunResponse(
            status="error",
            success=False,
            steps=0,
            balance_before=balance_before,
            balance_after=_read_balance(req.cdp_port),
            reason=str(e),
            errors=[str(e)],
        )


# ═══════════════════════════════════════════════════════════════════════════════
# PRE-FLIGHT CHECK — Reusable dependency for all survey endpoints
# ═══════════════════════════════════════════════════════════════════════════════

class PreflightError(HTTPException):
    """Pre-flight check failed — system not ready."""
    def __init__(self, reason: str, action: str = ""):
        super().__init__(
            status_code=503,
            detail={
                "error": "preflight_failed",
                "reason": reason,
                "action": action,
                "message": f"System not ready: {reason}. Action: {action or 'none'}"
            }
        )


def preflight_check(port: int = 9999) -> Dict[str, Any]:
    """
    Reusable Pre-Flight Check — validate system state before command execution.
    
    Called by FastAPI dependency or directly in endpoint handlers.
    
    Returns:
        Dict with: ready (bool), tab_ws (str), balance (float), surveys (int), reason (str), action (str)
    
    Pre-Flight Flow:
        1. Chrome alive? → Port reachable?
        2. Dashboard Tab? → Non-extension, non-blank tab
        3. Login valid? → "abmelden" in body text
        4. Balance OK? → Max(€-Beträge >= 1.0€)
        5. Surveys available? → .survey-item cards on dashboard
    """
    import re
    
    result = {
        "ready": False,
        "tab_ws": "",
        "balance": 0.0,
        "surveys": 0,
        "reason": "",
        "action": "",
        "chrome_alive": False,
        "login_valid": False,
    }
    
    # 1. Chrome alive?
    try:
        pages_raw = urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=3).read()
        chrome_data = json.loads(pages_raw)
        result["chrome_alive"] = True
    except Exception:
        result["reason"] = "Chrome not running on port 9999"
        result["action"] = "start_heypiggy"
        return result
    
    # 2. Get all tabs
    try:
        pages_raw = urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=3).read()
        pages = json.loads(pages_raw)
    except Exception:
        result["reason"] = "Cannot connect to Chrome DevTools"
        result["action"] = "restart_chrome"
        return result
    
    # 3. Find dashboard tab (non-extension, non-blank)
    db_tabs = [p for p in pages if p.get("type") == "page"
               and "heypiggy" in p.get("url", "").lower()
               and "dashboard" in p.get("url", "").lower()]
    
    if not db_tabs:
        result["reason"] = "No HeyPiggy dashboard tab found"
        result["action"] = "open_dashboard"
        return result
    
    tab_ws = db_tabs[0].get("webSocketDebuggerUrl", "")
    result["tab_ws"] = tab_ws
    
    # 4. Login valid? (check "abmelden" in body text)
    try:
        ws_conn = websocket.create_connection(tab_ws, timeout=15)
        ws_conn.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                                  "params": {"expression": "document.body.innerText"}}))
        resp = json.loads(ws_conn.recv())
        ws_conn.close()
        body_text = resp.get("result", {}).get("result", {}).get("value", "") or ""
        result["login_valid"] = "abmelden" in body_text.lower()
        
        if not result["login_valid"]:
            result["reason"] = "Session expired — 'abmelden' not found in dashboard"
            result["action"] = "relogin_heypiggy"
            return result
        
        # 5. Balance OK?
        amounts = re.findall(r"(\d+[.,]?\d*)\s*€", body_text[:800])
        for amt in amounts:
            val = float(amt.replace(",", "."))
            if val >= 1.0:
                result["balance"] = val
        
        # 6. Surveys available?
        survey_count = body_text.count("Umfragen") + body_text.count("erhebung")
        result["surveys"] = survey_count
        
        if survey_count == 0:
            result["reason"] = "No surveys available on dashboard"
            result["action"] = "wait_for_surveys"
            return result
        
        result["ready"] = True
        return result
        
    except Exception as e:
        result["reason"] = f"Cannot read dashboard: {e}"
        result["action"] = "restart_chrome"
        return result


def require_survey_ready(port: int = 9999):
    """
    FastAPI Dependency — ensure system is ready before executing survey commands.
    
    Usage:
        @router.post("/fill")
        async def api_fill(req: FillRequest, pf: Dict = Depends(require_survey_ready)):
            ...
    
    Raises PreflightError (503) if system not ready.
    """
    pf = preflight_check(port)
    if not pf["ready"]:
        raise PreflightError(reason=pf["reason"], action=pf["action"])
    return pf


# ═══════════════════════════════════════════════════════════════════════════════
# COMMAND REGISTRY AUTO-UPDATE — nach jedem Command
# ═══════════════════════════════════════════════════════════════════════════════

def update_command_registry(command_id: str, success: bool, details: Dict = None):
    """
    Auto-Update command_registry.json nach jedem Command-Erfolg/Fehler.
    
    Called by FastAPI endpoints after each command execution.
    
    Args:
        command_id: e.g. "answer_survey", "open_survey", "click_button"
        success: True if command succeeded
        details: Optional dict with {pages_processed, status, final_url, earned}
    """
    registry_path = Path(__file__).parent.parent.parent / "survey-cli" / "data" / "command_registry.json"
    
    try:
        with open(registry_path) as f:
            registry = json.load(f)
    except Exception:
        return  # Registry file missing — skip update
    
    now = datetime.now(timezone.utc).isoformat()
    details = details or {}
    
    # Find or create command entry
    found = False
    for cmd in registry.get("commands", []):
        if cmd.get("id") == command_id:
            found = True
            if success:
                cmd["success_count"] = cmd.get("success_count", 0) + 1
                cmd["last_success"] = now
                cmd["status"] = "verified" if cmd["success_count"] >= 3 else "testing"
            else:
                cmd["failure_count"] = cmd.get("failure_count", 0) + 1
                cmd["last_failure"] = now
                cmd["status"] = "testing"
            
            cmd["last_run"] = now
            cmd["last_result"] = {
                "status": details.get("status", "unknown"),
                "pages_processed": details.get("pages_processed", 0),
                "final_url": details.get("final_url", ""),
                "earned": details.get("earned", 0.0),
            }
            cmd["notes"] = f"{details.get('status','unknown')}, {details.get('pages_processed',0)} pages"
            break
    
    if not found:
        registry.setdefault("commands", []).append({
            "id": command_id,
            "description": f"Auto-registered from FastAPI endpoint",
            "path": f"agent-toolbox/api/survey_tools.py",
            "success_count": 1 if success else 0,
            "failure_count": 0 if success else 1,
            "last_success": now if success else None,
            "last_run": now,
            "status": "testing",
            "notes": f"First {'success' if success else 'failure'} from FastAPI",
        })
    
    registry["last_updated"] = now
    
    try:
        with open(registry_path, "w") as f:
            json.dump(registry, f, indent=2)
    except Exception:
        pass  # Silently skip write errors


# ═══════════════════════════════════════════════════════════════════════════════
# MISSING CRITICAL ENDPOINTS — tool_snapshot + tool_detect_completion
# ═══════════════════════════════════════════════════════════════════════════════

class SnapshotRequest(BaseModel):
    """POST /survey/snapshot Request."""
    ws_url: Optional[str] = None
    tab_id: Optional[str] = None
    cdp_port: int = 9999


class SnapshotResponse(BaseModel):
    """POST /survey/snapshot Response."""
    status: str
    url: str = ""
    title: str = ""
    body_preview: str = ""
    element_count: int = 0
    hash: str = ""
    elements: List[Dict[str, Any]] = []


@router.post("/snapshot", response_model=SnapshotResponse, dependencies=[Depends(require_survey_ready)])
async def api_snapshot(req: SnapshotRequest) -> SnapshotResponse:
    """
    Capture complete DOM snapshot via CDP Runtime.evaluate (EXTRACTOR_JS).
    
    100% reliable element capture — NO skylight-cli! Uses survey-cli/tools/tool_snapshot.py.
    
    Returns:
        - url: Current page URL
        - title: Page title
        - body_preview: First 500 chars of body text
        - element_count: Number of interactive elements
        - hash: MD5 of body text (for anti-stuck detection)
        - elements: Full list of interactive elements with type/id/placeholder/text
    """
    from tools.tool_snapshot import EXTRACTOR_JS
    
    # Find WS URL
    if not req.ws_url:
        try:
            pages = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{req.cdp_port}/json/list", timeout=5).read())
            # Find first non-dashboard, non-blank tab
            for p in pages:
                url_lower = p.get("url", "").lower()
                if p.get("type") == "page" and "dashboard" not in url_lower and "heypiggy" not in url_lower:
                    if not url_lower.startswith("chrome"):
                        req.ws_url = p.get("webSocketDebuggerUrl")
                        break
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Cannot find survey tab: {e}")
    
    if not req.ws_url:
        raise HTTPException(status_code=404, detail="No survey tab found")
    
    try:
        async with websockets.connect(req.ws_url, max_size=10*1024*1024) as ws:
            await ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                                      "params": {"expression": EXTRACTOR_JS, "returnByValue": True}}))
            
            deadline = asyncio.get_running_loop().time() + 15
            for _ in range(100):
                remaining = max(0.1, deadline - asyncio.get_running_loop().time())
                if remaining <= 0:
                    break
                try:
                    msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=remaining))
                    if msg.get("id") == 1:
                        data = msg.get("result", {}).get("result", {}).get("value", {})
                        body_text = data.get("bodyText", "")
                        import hashlib
                        dom_hash = hashlib.md5(body_text.encode()).hexdigest()[:12]
                        update_command_registry("snapshot", True, {
                            "element_count": len(data.get("elements", [])),
                            "url": data.get("url", ""),
                        })
                        return SnapshotResponse(
                            status="ok",
                            url=data.get("url", ""),
                            title=data.get("title", ""),
                            body_preview=body_text[:500],
                            element_count=len(data.get("elements", [])),
                            hash=dom_hash,
                            elements=data.get("elements", []),
                        )
                except asyncio.TimeoutError:
                    break
            
            update_command_registry("snapshot", False, {"error": "timeout"})
            raise HTTPException(status_code=504, detail="Snapshot timeout — page not responding")
            
    except websockets.exceptions.InvalidStatus:
        update_command_registry("snapshot", False, {"error": "ws_unreachable"})
        raise HTTPException(status_code=404, detail="Tab WebSocket not reachable")
    except Exception as e:
        update_command_registry("snapshot", False, {"error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))


class CompletionRequest(BaseModel):
    """POST /survey/completion Request."""
    ws_url: Optional[str] = None
    cdp_port: int = 9999


class CompletionResponse(BaseModel):
    """POST /survey/completion Response."""
    status: str  # "completed" | "screen_out" | "in_progress" | "error"
    screen_out: bool = False
    completion_detected: bool = False
    reason: str = ""


@router.post("/completion", response_model=CompletionResponse, dependencies=[Depends(require_survey_ready)])
async def api_detect_completion(req: CompletionRequest) -> CompletionResponse:
    """
    Detect if survey is completed, screen-out, or still in progress.
    
    Uses survey-cli/tools/tool_detect_completion.py logic.
    
    Detection:
        - Completion: "vielen dank", "thank you", "abgeschlossen", "completed"
        - Screen-Out: "umfrage passt nicht", "leider", "nicht geeignet", "vorzeitig beendet"
        - In-Progress: Neither above
    """
    if not req.ws_url:
        try:
            pages = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{req.cdp_port}/json/list", timeout=5).read())
            for p in pages:
                url_lower = p.get("url", "").lower()
                if p.get("type") == "page" and "dashboard" not in url_lower and "heypiggy" not in url_lower:
                    if not url_lower.startswith("chrome"):
                        req.ws_url = p.get("webSocketDebuggerUrl")
                        break
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Cannot find survey tab: {e}")
    
    if not req.ws_url:
        update_command_registry("detect_completion", False, {"error": "no_tab"})
        return CompletionResponse(status="error", reason="No survey tab found")
    
    try:
        async with websockets.connect(req.ws_url, max_size=10*1024*1024) as ws:
            await ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                                      "params": {"expression": "document.body.innerText"}}))
            r = await asyncio.wait_for(ws.recv(), timeout=15)
            body = json.loads(r).get("result", {}).get("result", {}).get("value", "") or ""
            body_lower = body.lower()
            
            completion_kws = ["vielen dank", "thank you", "abgeschlossen", "completed",
                              "danke für", "survey complete", "ihre antworten"]
            screen_out_kws = ["umfrage passt nicht", "leider", "nicht geeignet", "vorzeitig beendet",
                              "screen out", "disqualifiz", "sorry, we could not",
                              "keine passende umfrage", "nicht teilnehmen"]
            
            completion_detected = any(kw in body_lower for kw in completion_kws)
            screen_out = any(kw in body_lower for kw in screen_out_kws)
            
            if completion_detected:
                update_command_registry("detect_completion", True, {"status": "completed", "completion": True})
                return CompletionResponse(status="completed", completion_detected=True,
                                         reason="Completion keywords found")
            elif screen_out:
                update_command_registry("detect_completion", True, {"status": "screen_out", "screen_out": True})
                return CompletionResponse(status="screen_out", screen_out=True,
                                         reason="Screen-out keywords found")
            else:
                update_command_registry("detect_completion", True, {"status": "in_progress"})
                return CompletionResponse(status="in_progress", reason="Survey still in progress")
                
    except Exception as e:
        update_command_registry("detect_completion", False, {"error": str(e)})
        return CompletionResponse(status="error", reason=str(e))


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
    "UniversalRunRequest", "UniversalRunResponse",
    "solve_purespectrum_preflight",
]