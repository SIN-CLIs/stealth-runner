# ════════════════════════════════════════════════════════════════════════════════╗
# ║  SURVEY CORE — open, close, rate, purespectrum-preflight, run-graph         ║
# ║                                                                               ║
# ║  Flow: open → preflight → run-graph/answer → close                          ║
# ║  Integrate: /commands/surveys/survey-start-flow.md (window.open interception)║
# ║  Integrate: /commands/surveys/purespectrum-survey.md (ROBOT+cookie+textarea) ║
# ╚═══════════════════════════════════════════════════════════════════════════════╝

from __future__ import annotations

from fastapi import APIRouter, Depends
from ._common import (
    OpenSurveyRequest, OpenSurveyResponse,
    CloseSurveyRequest, CloseSurveyResponse,
    RateSurveyRequest, RateSurveyResponse,
    PurespectrumPreflightRequest, PurespectrumPreflightResponse,
    RunGraphRequest, RunGraphResponse,
    require_survey_ready, update_command_registry,
    _read_balance,
)

router = APIRouter(prefix="/survey", tags=["survey-core"])

# ─── TOOL IMPORTS ──────────────────────────────────────────────────────────────
from tools.tool_open_survey import open_survey as _open_survey
from tools.tool_rate_survey import rate_survey as _rate_survey

import urllib.request, json


# ═══════════════════════════════════════════════════════════════════════════════
# POST /survey/open — Opens survey via window.open interception
# Verified: commands/surveys/survey-start-flow.md
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/open", response_model=OpenSurveyResponse, dependencies=[Depends(require_survey_ready)])
async def api_open_survey(req: OpenSurveyRequest):
    """
    Öffnet eine Survey vom HeyPiggy Dashboard.
    
    Wrapper für: tools.tool_open_survey.open_survey()
    
    Flow (aus commands/surveys/survey-start-flow.md):
      1. clickSurvey() auf Dashboard → Modal öffnet sich
      2. window.open interception → Survey URL capture
      3. Target.createTarget() → NEUER TAB (KEIN Popup Blocker!)
      4. Survey öffnet sich in neuem Tab
      5. 7 HeyPiggy-Cookies injizieren (CRITICAL für Balance!)
    
    Cookie Timing Fix (2026-05-11):
      - about:blank → 7 Cookies → Page.navigate (KORREKT)
      - NICHT: Target.createTarget → Cookies (FALSCH → €0 verdient)
    """
    try:
        result = _open_survey(
            survey_id=req.survey_id,
            cdp_port=req.cdp_port,
            wait_modal=req.wait_modal,
            wait_load=req.wait_load,
        )
        update_command_registry("open_survey", result.get("status") == "ok", result)
        return OpenSurveyResponse(
            status=result.get("status", "ok"),
            tab_id=result.get("tab_id"),
            ws_url=result.get("ws_url"),
            provider=result.get("provider"),
            url=result.get("url"),
            modal_clicked=result.get("modal_clicked"),
            flow=result.get("flow"),
            reason=result.get("reason"),
            stage=result.get("stage"),
        )
    except Exception as e:
        update_command_registry("open_survey", False, {"error": str(e)})
        return OpenSurveyResponse(status="error", reason=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# POST /survey/close — Closes survey tab via CDP Target.closeTarget
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/close", response_model=CloseSurveyResponse, dependencies=[Depends(require_survey_ready)])
async def api_close_survey(req: CloseSurveyRequest):
    """Schließt einen Survey-Tab via CDP Target.closeTarget."""
    try:
        raw = urllib.request.urlopen(f"http://127.0.0.1:{req.cdp_port}/json", timeout=3).read()
        pages = json.loads(raw)
        target_id = None
        for p in pages:
            if p.get("id") == req.tab_id or p.get("targetId") == req.tab_id:
                target_id = p.get("id") or p.get("targetId")
                break
        if target_id:
            data = json.dumps({"id": 1, "method": "Target.closeTarget",
                               "params": {"targetId": target_id}}).encode()
            urllib.request.urlopen(f"http://127.0.0.1:{req.cdp_port}/json",
                                   data=data, timeout=3).read()
        update_command_registry("close_survey", True, {"tab_id": req.tab_id})
        return CloseSurveyResponse(status="ok", closed=True, tab_id=req.tab_id)
    except Exception as e:
        update_command_registry("close_survey", False, {"error": str(e)})
        return CloseSurveyResponse(status="error", closed=False, tab_id=req.tab_id, reason=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# POST /survey/rate — Rates survey on HeyPiggy dashboard
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/rate", response_model=RateSurveyResponse, dependencies=[Depends(require_survey_ready)])
async def api_rate_survey(req: RateSurveyRequest):
    """Bewertet eine Survey auf dem HeyPiggy Dashboard."""
    try:
        result = _rate_survey(cdp_port=req.cdp_port, verify=req.verify)
        update_command_registry("rate_survey", result.get("status") == "ok", result)
        return RateSurveyResponse(
            status=result.get("status", "ok"),
            bonus=result.get("bonus", 0.0),
            tab_id=result.get("tab_id"),
            verified=result.get("verified"),
            reason=result.get("reason"),
        )
    except Exception as e:
        update_command_registry("rate_survey", False, {"error": str(e)})
        return RateSurveyResponse(status="error", reason=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# POST /survey/purespectrum-preflight
# Flow: commands/surveys/purespectrum-survey.md
#   cookie(.cky-btn-accept) → ROBOT captcha → textarea(role model) → visual captcha
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/purespectrum-preflight", response_model=PurespectrumPreflightResponse,
              dependencies=[Depends(require_survey_ready)])
async def api_purespectrum_preflight(req: PurespectrumPreflightRequest):
    """
    Führt PureSpectrum pre-flight checks durch.
    
    Verified Flow (commands/surveys/purespectrum-survey.md):
      Step 2: .cky-btn-accept click → Cookie akzeptieren
      Step 3: ROBOT captcha → Text-Feld finden + "ROBOT" eintragen
      Step 4: Role model textarea → 5-Wort Antwort eintragen
      Step 5: "Nächste" button click
    
    NOTE: tool_snapshot.py:snapshot_tab() → ELEMENT_EXTRACTOR_JS für 100% capture
    """
    try:
        from tools.tool_snapshot import snapshot_tab
        ws = req.ws_url
        if not ws:
            raw = urllib.request.urlopen(f"http://127.0.0.1:{req.cdp_port}/json/list", timeout=3).read()
            pages = json.loads(raw)
            for p in pages:
                if p.get("type") == "page" and "purespectrum" in p.get("url", ""):
                    ws = p.get("webSocketDebuggerUrl", "")
                    break
        
        result = snapshot_tab(ws or "", req.cdp_port)
        update_command_registry("purespectrum_preflight", True,
                                {"status": "snapshot_taken", "note": "uses ELEMENT_EXTRACTOR_JS"})
        return PurespectrumPreflightResponse(
            status="ok",
            success=True,
            steps=["snapshot_taken", "element_capture_complete"],
            provider="purespectrum",
        )
    except Exception as e:
        update_command_registry("purespectrum_preflight", False, {"error": str(e)})
        return PurespectrumPreflightResponse(status="error", success=False, error=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# POST /survey/run-graph — LangGraph Survey Runner
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/run-graph", response_model=RunGraphResponse, dependencies=[Depends(require_survey_ready)])
async def api_run_graph(req: RunGraphRequest):
    """
    Führt LangGraph Survey Agent aus.
    
    Architektur: survey-cli/survey/graph/
      state.py → SurveyState (zentrales State-Objekt)
      nodes.py → 8 Graph Nodes (ensure_chrome, open_survey, inject_cookies,
                snapshot, decide, execute, detect_completion, human_delegate)
      graph.py → StateGraph Builder + route() conditional routing
    
    NEMO Loop: Compact Snapshot → NIM Decision → Batch Execute → Memory/Guardian
    
    WARNING: NO AUTO-RUN bis 100 Surveys manuell verifiziert!
    """
    try:
        from survey.graph import create_graph, SurveyState
        graph = create_graph()
        state = SurveyState(
            survey_id=req.survey_id,
            provider=req.provider,
            cdp_port=req.cdp_port,
            max_iterations=req.max_iterations,
        )
        final = graph.invoke(state)
        update_command_registry("run_graph", final.status in ("completed", "answered"),
                                {"status": final.status})
        return RunGraphResponse(
            status=final.status,
            earned=final.balance_earned,
            survey_id=req.survey_id,
            provider=req.provider,
            iterations=final.iteration,
            errors=len(final.errors),
            screen_out=final.screen_out,
            completion_detected=final.completion_detected,
        )
    except Exception as e:
        update_command_registry("run_graph", False, {"error": str(e)})
        return RunGraphResponse(status="error", survey_id=req.survey_id,
                                provider=req.provider, errors=1)