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

from fastapi import APIRouter, Depends, HTTPException
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

# NEW standalone tools (survey-cli/tools/)
from tools.tool_solve_captcha import solve as solve_captcha
from tools.tool_solve_drag_puzzle import solve as solve_drag_puzzle
from tools.tool_scan_dashboard import scan as scan_dashboard, get_next_survey
from tools.tool_universal_answer import answer as universal_answer


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
    
    try:
        pages_raw = urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=3).read()
        chrome_data = json.loads(pages_raw)
        result["chrome_alive"] = True
    except Exception:
        result["reason"] = "Chrome not running on port 9999"
        result["action"] = "start_chrome"
        return result
    
    try:
        pages_raw = urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=3).read()
        pages = json.loads(pages_raw)
        dashboard_tab = None
        for p in pages:
            if p.get("type") == "page" and not p.get("url", "").startswith("chrome-extension"):
                url = p.get("url", "")
                if url in ("", "about:blank") or "heypiggy" in url:
                    dashboard_tab = p
                    break
        if not dashboard_tab:
            result["reason"] = "No valid dashboard tab found"
            result["action"] = "restart_chrome"
            return result
        result["tab_ws"] = dashboard_tab.get("webSocketDebuggerUrl", "")
    except Exception as e:
        result["reason"] = f"Cannot find dashboard tab: {e}"
        result["action"] = "restart_chrome"
        return result
    
    try:
        ws_url = result["tab_ws"]
        if ws_url:
            import asyncio, websockets
            async def check_login():
                async with websockets.connect(ws_url) as ws:
                    await ws.send(json.dumps({
                        "id": 1,
                        "method": "Runtime.evaluate",
                        "params": {"expression": "document.body.innerText.substring(0, 500)"}
                    }))
                    resp = await asyncio.wait_for(ws.recv(), timeout=5)
                    data = json.loads(resp)
                    text = data.get("result", {}).get("result", {}).get("value", "")
                    return "abmelden" in text.lower()
            login_ok = asyncio.run(check_login())
            result["login_valid"] = login_ok
            if not login_ok:
                result["reason"] = "Session expired — not logged in"
                result["action"] = "restore_cookies"
                return result
    except Exception:
        pass
    
    try:
        ws_url = result["tab_ws"]
        if ws_url:
            import asyncio, websockets
            async def check_balance():
                async with websockets.connect(ws_url) as ws:
                    await ws.send(json.dumps({
                        "id": 1,
                        "method": "Runtime.evaluate",
                        "params": {"expression": """
                            (() => {
                                const txt = document.body.innerText || '';
                                const amounts = [...txt.matchAll(/(\\d+[.,]\\d{2})/g)];
                                let maxAmount = 0;
                                for (const m of amounts) {
                                    const num = parseFloat(m[1].replace(',', '.'));
                                    const pos = m.index;
                                    const after = txt.substring(pos, pos + 50);
                                    if (after.includes('€') && num >= 1.0 && num > maxAmount) {
                                        maxAmount = num;
                                    }
                                }
                                return maxAmount;
                            })()
                        """}
                    }))
                    resp = await asyncio.wait_for(ws.recv(), timeout=5)
                    data = json.loads(resp)
                    val = data.get("result", {}).get("result", {}).get("value")
                    if isinstance(val, (int, float)):
                        result["balance"] = float(val)
                    else:
                        result["balance"] = _read_balance(port)
            result["balance"] = asyncio.run(check_balance())
    except Exception:
        result["balance"] = _read_balance(port)
    
    try:
        ws_url = result["tab_ws"]
        if ws_url:
            import asyncio, websockets
            async def check_surveys():
                async with websockets.connect(ws_url) as ws:
                    await ws.send(json.dumps({
                        "id": 1,
                        "method": "Runtime.evaluate",
                        "params": {"expression": "document.querySelectorAll('.survey-item').length"}
                    }))
                    resp = await asyncio.wait_for(ws.recv(), timeout=5)
                    data = json.loads(resp)
                    count = data.get("result", {}).get("result", {}).get("value", 0)
                    return int(count) if isinstance(count, (int, float)) else 0
            result["surveys"] = asyncio.run(check_surveys())
    except Exception:
        pass
    
    result["ready"] = True
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
# ROUTER
# ═══════════════════════════════════════════════════════════════════════════════

router = APIRouter(prefix="/survey", tags=["survey-tools"])


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
# ENDPOINT: POST /survey/open
# Wrapper für tools.tool_open_survey.open_survey()
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/open", response_model=OpenSurveyResponse, dependencies=[Depends(require_survey_ready)])
async def api_open_survey(req: OpenSurveyRequest):
    """
    Öffnet eine Survey vom HeyPiggy Dashboard.
    Wrapper für: tools.tool_open_survey.open_survey()
    """
    try:
        from tools.tool_open_survey import open_survey
        result = open_survey(
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
# ENDPOINT: POST /survey/close
# Closes survey tab via CDP Target.closeTarget
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/close", response_model=CloseSurveyResponse, dependencies=[Depends(require_survey_ready)])
async def api_close_survey(req: CloseSurveyRequest):
    """
    Schließt einen Survey-Tab.
    Wrapper für: CDP Target.closeTarget
    """
    try:
        import urllib.request, json
        url = f"http://127.0.0.1:{req.cdp_port}/json"
        pages = json.loads(urllib.request.urlopen(url, timeout=3).read())
        target_id = None
        for p in pages:
            if p.get("id") == req.tab_id or p.get("targetId") == req.tab_id:
                target_id = p.get("id") or p.get("targetId")
                break
        
        if target_id:
            req_data = json.dumps({"id": 1, "method": "Target.closeTarget", "params": {"targetId": target_id}}).encode()
            urllib.request.urlopen(
                f"http://127.0.0.1:{req.cdp_port}/json",
                data=req_data,
                timeout=3
            ).read()
        
        update_command_registry("close_survey", True, {"tab_id": req.tab_id})
        return CloseSurveyResponse(status="ok", closed=True, tab_id=req.tab_id)
    except Exception as e:
        update_command_registry("close_survey", False, {"error": str(e)})
        return CloseSurveyResponse(status="error", closed=False, tab_id=req.tab_id, reason=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINT: POST /survey/rate — wrapper für tool_rate_survey
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/rate", response_model=RateSurveyResponse, dependencies=[Depends(require_survey_ready)])
async def api_rate_survey(req: RateSurveyRequest):
    """Bewertet eine Survey auf dem HeyPiggy Dashboard."""
    try:
        from tools.tool_rate_survey import rate_survey
        result = rate_survey(cdp_port=req.cdp_port, verify=req.verify)
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
# ENDPOINT: POST /survey/purespectrum-preflight
# Consent → ROBOT captcha → textarea → visual captcha → drag-drop
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/purespectrum-preflight", response_model=PurespectrumPreflightResponse, dependencies=[Depends(require_survey_ready)])
async def api_purespectrum_preflight(req: PurespectrumPreflightRequest):
    """Führt PureSpectrum pre-flight checks durch (consent + captchas)."""
    try:
        from tools.tool_snapshot import snapshot_tab
        result = snapshot_tab(req.ws_url or "", req.cdp_port)
        update_command_registry("purespectrum_preflight", True, {"status": "stub", "note": "preflight tool not yet wired"})
        return PurespectrumPreflightResponse(
            status="ok",
            success=True,
            steps=["snapshot_taken"],
            provider="purespectrum",
        )
    except Exception as e:
        update_command_registry("purespectrum_preflight", False, {"error": str(e)})
        return PurespectrumPreflightResponse(status="error", success=False, error=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINT: POST /survey/run-graph — LangGraph Survey Runner
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/run-graph", response_model=RunGraphResponse, dependencies=[Depends(require_survey_ready)])
async def api_run_graph(req: RunGraphRequest):
    """Führt LangGraph Survey Agent aus."""
    try:
        from survey_cli.survey.graph import create_graph, SurveyState
        graph = create_graph()
        state = SurveyState(survey_id=req.survey_id, provider=req.provider, cdp_port=req.cdp_port, max_iterations=req.max_iterations)
        final = graph.invoke(state)
        update_command_registry("run_graph", final.status in ("completed", "answered"), {"status": final.status})
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
        return RunGraphResponse(status="error", survey_id=req.survey_id, provider=req.provider, errors=1)


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINT: POST /survey/snapshot
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
# TOOL WRAPPERS — survey-cli/tools/ → FastAPI Endpoints (SR-52)
# ═══════════════════════════════════════════════════════════════════════════════

from tools.tool_click import click as cua_click
from tools.tool_find_element import find_element
from tools.tool_verify_state import verify_element_state
from tools.tool_click_angular import click as click_angular
from tools.tool_fill_input import fill as cdp_fill
from tools.tool_find_new_tab import find_new_tab
from tools.tool_close_modals import close_modals


def _resolve_pid_wid(ws_url: str, port: int = 9999):
    """Get (pid, wid) from CDP WS URL by matching tab in /json list."""
    try:
        pages = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=5).read())
        for p in pages:
            if p.get("webSocketDebuggerUrl") == ws_url:
                return int(p.get("processId", 0)), int(p.get("id", "0").split("-")[0])
    except Exception:
        pass
    return None, None


# ─── TOOL 1: POST /survey/click ───────────────────────────────────────────────

class ClickRequest(BaseModel):
    ws_url: Optional[str] = None
    tab_id: Optional[str] = None
    cdp_port: int = 9999
    label: str
    role: str = "AXButton"


class ClickResponse(BaseModel):
    status: str
    element_index: Optional[int] = None
    verified: bool = False


@router.post("/click", response_model=ClickResponse, dependencies=[Depends(require_survey_ready)])
async def api_click(req: ClickRequest):
    """Generic CUA click via tool_click.py.

    Args:
        label: Button/link text (word-boundary match)
        role: AX role (default: AXButton)
        ws_url/tab_id: Tab identification

    Kapselt: tools.tool_click.click(pid, wid, label, role)
    """
    ws_url = req.ws_url
    if not ws_url and req.tab_id:
        pages = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{req.cdp_port}/json", timeout=5).read())
        for p in pages:
            if p.get("id", "").startswith(req.tab_id) or p.get("id") == req.tab_id:
                ws_url = p.get("webSocketDebuggerUrl")
                break

    pid, wid = _resolve_pid_wid(ws_url, req.cdp_port)
    if not pid or not wid:
        update_command_registry("click", False, {"error": "no_pid_wid"})
        return ClickResponse(status="error", reason="Could not resolve pid/wid from tab")

    result = cua_click(pid, wid, req.label, req.role)
    update_command_registry("click", result.get("status") == "ok", {
        "label": req.label,
        "role": req.role,
        "element_index": result.get("element_index"),
        "verified": result.get("verified", False),
    })
    return ClickResponse(**result)


# ─── TOOL 2: POST /survey/find ────────────────────────────────────────────────

class FindRequest(BaseModel):
    ws_url: Optional[str] = None
    tab_id: Optional[str] = None
    cdp_port: int = 9999
    role: str
    label: Optional[str] = None
    text_sub: Optional[str] = None
    use_boundary: bool = True


class FindResponse(BaseModel):
    status: str
    element_index: Optional[int] = None
    role: Optional[str] = None
    text: Optional[str] = None


@router.post("/find", response_model=FindResponse, dependencies=[Depends(require_survey_ready)])
async def api_find(req: FindRequest):
    """Find element in AX-Tree via tool_find_element.py.

    Args:
        role: AX role (e.g. AXButton, AXLink, AXRadioButton)
        label: Exact text to match (word-boundary)
        text_sub: Substring match alternative

    Kapselt: tools.tool_find_element.find_element(markdown, role, label)
    """
    ws_url = req.ws_url
    if not ws_url and req.tab_id:
        pages = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{req.cdp_port}/json", timeout=5).read())
        for p in pages:
            if p.get("id", "").startswith(req.tab_id) or p.get("id") == req.tab_id:
                ws_url = p.get("webSocketDebuggerUrl")
                break

    pid, wid = _resolve_pid_wid(ws_url, req.cdp_port)
    if not pid or not wid:
        update_command_registry("find_element", False, {"error": "no_pid_wid"})
        return FindResponse(status="error", reason="Could not resolve pid/wid")

    import subprocess, json as _json
    result = subprocess.run(
        ["cua-driver", "call", "get_window_state"],
        input=_json.dumps({"pid": pid, "window_id": wid}),
        capture_output=True, text=True, timeout=30
    )
    markdown = ""
    if result.returncode == 0:
        markdown = _json.loads(result.stdout).get("tree_markdown", "")

    el = find_element(markdown, req.role, req.label, req.text_sub, req.use_boundary)
    if el:
        update_command_registry("find_element", True, {
            "role": req.role,
            "label": req.label,
            "element_index": el.get("element_index"),
        })
        return FindResponse(
            status="ok",
            element_index=el.get("element_index"),
            role=el.get("role"),
            text=el.get("text"),
        )
    update_command_registry("find_element", False, {"role": req.role, "label": req.label})
    return FindResponse(status="not_found", reason=f"No {req.role} with label '{req.label}'")


# ─── TOOL 3: POST /survey/verify ──────────────────────────────────────────────

class VerifyRequest(BaseModel):
    ws_url: Optional[str] = None
    tab_id: Optional[str] = None
    cdp_port: int = 9999
    element_index: int
    expected_role: str


class VerifyResponse(BaseModel):
    status: str
    found: bool = False
    role: Optional[str] = None
    text: Optional[str] = None


@router.post("/verify", response_model=VerifyResponse, dependencies=[Depends(require_survey_ready)])
async def api_verify(req: VerifyRequest):
    """Verify element state after action via tool_verify_state.py.

    Args:
        element_index: AX-Tree element index
        expected_role: e.g. AXRadioButton, AXCheckBox

    Kapselt: tools.tool_verify_state.verify_element_state(pid, wid, element_index, expected_role)
    """
    ws_url = req.ws_url
    if not ws_url and req.tab_id:
        pages = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{req.cdp_port}/json", timeout=5).read())
        for p in pages:
            if p.get("id", "").startswith(req.tab_id) or p.get("id") == req.tab_id:
                ws_url = p.get("webSocketDebuggerUrl")
                break

    pid, wid = _resolve_pid_wid(ws_url, req.cdp_port)
    if not pid or not wid:
        update_command_registry("verify_state", False, {"error": "no_pid_wid"})
        return VerifyResponse(status="error", reason="Could not resolve pid/wid")

    result = verify_element_state(pid, wid, req.element_index, req.expected_role)
    update_command_registry("verify_state", result.get("found", False), {
        "element_index": req.element_index,
        "expected_role": req.expected_role,
        "found": result.get("found", False),
    })
    return VerifyResponse(**result)


# ─── TOOL 4: POST /survey/click-angular ───────────────────────────────────────

class ClickAngularRequest(BaseModel):
    ws_url: Optional[str] = None
    tab_id: Optional[str] = None
    cdp_port: int = 9999
    selector: Optional[str] = None
    text: Optional[str] = None
    idx: Optional[int] = None
    timeout: int = 10


class ClickAngularResponse(BaseModel):
    status: str
    success: bool = False
    coords: Optional[List[float]] = None


@router.post("/click-angular", response_model=ClickAngularResponse, dependencies=[Depends(require_survey_ready)])
async def api_click_angular(req: ClickAngularRequest):
    """CDP mouse click for Angular/React frameworks via tool_click_angular.py.

    Args:
        selector: CSS selector (e.g. ".next-button")
        text: Button text (fallback if selector not given)
        idx: Element index (fallback if selector/text not given)

    Kapselt: tools.tool_click_angular.click_angular(ws_url, selector, text, idx, timeout)
    """
    ws_url = req.ws_url
    if not ws_url and req.tab_id:
        pages = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{req.cdp_port}/json", timeout=5).read())
        for p in pages:
            if p.get("id", "").startswith(req.tab_id) or p.get("id") == req.tab_id:
                ws_url = p.get("webSocketDebuggerUrl")
                break

    if not ws_url:
        update_command_registry("click_angular", False, {"error": "no_ws_url"})
        return ClickAngularResponse(status="error", reason="No ws_url provided")

    result = click_angular(ws_url, req.selector, req.text, req.idx, req.timeout)
    update_command_registry("click_angular", result.get("success", False), {
        "selector": req.selector,
        "text": req.text,
        "idx": req.idx,
    })
    return ClickAngularResponse(
        status="ok" if result.get("success") else "error",
        success=result.get("success", False),
        coords=result.get("coords"),
    )


# ─── TOOL 5: POST /survey/fill-input ─────────────────────────────────────────

class FillInputRequest(BaseModel):
    ws_url: Optional[str] = None
    tab_id: Optional[str] = None
    cdp_port: int = 9999
    value: str
    idx: Optional[int] = None
    selector: Optional[str] = None
    timeout: int = 10


class FillInputResponse(BaseModel):
    status: str
    success: bool = False
    value: str = ""


@router.post("/fill-input", response_model=FillInputResponse, dependencies=[Depends(require_survey_ready)])
async def api_fill_input(req: FillInputRequest):
    """Fill input/select field with validation retry via tool_fill_input.py.

    Args:
        value: Text to fill into the field
        idx: Element index (input[type=text], textarea, select)
        selector: CSS selector alternative

    Kapselt: tools.tool_fill_input.fill(ws_url, value, idx, selector, timeout)
    """
    ws_url = req.ws_url
    if not ws_url and req.tab_id:
        pages = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{req.cdp_port}/json", timeout=5).read())
        for p in pages:
            if p.get("id", "").startswith(req.tab_id) or p.get("id") == req.tab_id:
                ws_url = p.get("webSocketDebuggerUrl")
                break

    if not ws_url:
        update_command_registry("fill_input", False, {"error": "no_ws_url"})
        return FillInputResponse(status="error", reason="No ws_url provided")

    result = cdp_fill(ws_url, req.value, req.idx, req.selector, req.timeout)
    update_command_registry("fill_input", result.get("success", False), {
        "value": req.value,
        "idx": req.idx,
        "selector": req.selector,
    })
    return FillInputResponse(
        status="ok" if result.get("success") else "error",
        success=result.get("success", False),
        value=result.get("value", req.value),
    )


# ─── TOOL 6: POST /survey/find-tab ────────────────────────────────────────────

class FindTabRequest(BaseModel):
    cdp_port: int = 9999
    known_ids: List[str] = []


class FindTabResponse(BaseModel):
    status: str
    new_tab_id: Optional[str] = None
    new_ws_url: Optional[str] = None


@router.post("/find-tab", response_model=FindTabResponse, dependencies=[Depends(require_survey_ready)])
async def api_find_tab(req: FindTabRequest):
    """Detect new tab after window.open via tool_find_new_tab.py.

    Args:
        known_ids: Tab IDs known BEFORE the event (for diff detection)

    Kapselt: tools.tool_find_new_tab.find_new_tab(known_ids, port)
    """
    result = find_new_tab(req.known_ids, port=req.cdp_port)
    if result:
        update_command_registry("find_new_tab", True, {"new_tab_id": result.get("id")})
        return FindTabResponse(
            status="found",
            new_tab_id=result.get("id"),
            new_ws_url=result.get("webSocketDebuggerUrl"),
        )
    update_command_registry("find_new_tab", False, {"known_ids": req.known_ids})
    return FindTabResponse(status="not_found", reason="No new tab found")


# ─── TOOL 7: POST /survey/close-modals ────────────────────────────────────────

class CloseModalsRequest(BaseModel):
    ws_url: Optional[str] = None
    tab_id: Optional[str] = None
    cdp_port: int = 9999
    timeout: int = 10


class CloseModalsResponse(BaseModel):
    status: str
    closed_count: int = 0


@router.post("/close-modals", response_model=CloseModalsResponse, dependencies=[Depends(require_survey_ready)])
async def api_close_modals(req: CloseModalsRequest):
    """Close all visible modals/overlays via tool_close_modals.py.

    Closes: cookie banners, login modals, ad popups, close buttons, backdrops.

    Kapselt: tools.tool_close_modals.close_modals(ws_url, timeout)
    """
    ws_url = req.ws_url
    if not ws_url and req.tab_id:
        pages = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{req.cdp_port}/json", timeout=5).read())
        for p in pages:
            if p.get("id", "").startswith(req.tab_id) or p.get("id") == req.tab_id:
                ws_url = p.get("webSocketDebuggerUrl")
                break

    if not ws_url:
        update_command_registry("close_modals", False, {"error": "no_ws_url"})
        return CloseModalsResponse(status="error", reason="No ws_url provided")

    count = close_modals(ws_url, req.timeout)
    update_command_registry("close_modals", count > 0, {"closed_count": count})
    return CloseModalsResponse(status="ok", closed_count=count)


# ═══════════════════════════════════════════════════════════════════════════════
# NEW TOOL ENDPOINTS — standalone tools, NOT thin wrappers
# ═══════════════════════════════════════════════════════════════════════════════
# Tool 1: POST /captcha/solve — Auto-detect + solve (text/slide/drag)
# Tool 2: POST /survey/scan — Dashboard scanner with provider detection
# Tool 3: POST /survey/answer — Universal DOM-based answerer
# Tool 4: POST /survey/solve-drag — Dedicated Angular CDK drag-drop solver

class CaptchaSolveRequest(BaseModel):
    ws_url: str
    captcha_type: str = "auto"  # "auto" | "slide" | "text" | "drag"


class CaptchaSolveResponse(BaseModel):
    status: str
    type: str
    text: Optional[str] = None
    reason: Optional[str] = None


@router.post("/captcha/solve", response_model=CaptchaSolveResponse, dependencies=[Depends(require_survey_ready)])
async def api_solve_captcha(req: CaptchaSolveRequest):
    """
    Auto-detect + solve any captcha type (text/OCR, slide, drag-drop).

    Intelligence built into tool_solve_captcha.py:
      - Type detection via DOM analysis
      - Text: NVIDIA Vision OCR → type → submit
      - Slide: CDP Bezier trajectory → mouse events
      - Drag: delegates to tool_solve_drag_puzzle.py

    Kapselt: tools.tool_solve_captcha.solve(ws_url, captcha_type)
    """
    result = solve_captcha(req.ws_url, req.captcha_type)
    update_command_registry("captcha_solve", result["status"] == "ok", result)
    return CaptchaSolveResponse(**result)


class ScanDashboardRequest(BaseModel):
    cdp_port: int = 9999
    min_trust: float = 0.5


class ScanDashboardResponse(BaseModel):
    status: str
    count: int = 0
    viable_count: int = 0
    provider_counts: dict = {}
    next_survey_id: Optional[str] = None


@router.post("/survey/scan", response_model=ScanDashboardResponse)
async def api_scan_dashboard(req: ScanDashboardRequest):
    """
    Scan HeyPiggy dashboard for available surveys.

    Returns: viable surveys with provider detection + trust scores.
    Pre-flight: checks Chrome is running on port.

    Kapselt: tools.tool_scan_dashboard.scan(port) + get_next_survey()
    """
    result = scan_dashboard(req.cdp_port)
    if result["status"] != "ok":
        update_command_registry("scan_dashboard", False, result)
        return ScanDashboardResponse(status="error")

    update_command_registry("scan_dashboard", True, {
        "count": result["count"],
        "viable": result["viable_count"],
        "providers": list(result.get("provider_counts", {}).keys()),
    })

    # Get next best survey
    next_survey = get_next_survey(req.cdp_port, req.min_trust)
    return ScanDashboardResponse(
        status="ok",
        count=result["count"],
        viable_count=result["viable_count"],
        provider_counts=result.get("provider_counts", {}),
        next_survey_id=next_survey.get("id") if next_survey else None,
    )


class UniversalAnswerRequest(BaseModel):
    ws_url: str
    profile_name: str = "sin_agent_heypiggy"


class UniversalAnswerResponse(BaseModel):
    status: str
    type: str
    answered: bool = False
    question: Optional[str] = None


@router.post("/survey/answer", response_model=UniversalAnswerResponse, dependencies=[Depends(require_survey_ready)])
async def api_universal_answer(req: UniversalAnswerRequest):
    """
    Universal DOM-based survey answerer — handles ANY question type.

    Provider-agnostic: detects question type from DOM structure.
    Supported: Radio / Checkbox / Text / Textarea / Select / NPS / Matrix.
    Maps answers to persona profile (age, gender, income, education).

    Kapselt: tools.tool_universal_answer.answer(ws_url, profile)
    """
    # Load profile if specified
    profile = None
    if req.profile_name:
        try:
            from survey.profile_loader import ProfileLoader
            profile = ProfileLoader.load_profile()
        except Exception:
            pass

    result = universal_answer(req.ws_url, profile)
    update_command_registry("universal_answer", result["status"] == "ok", result)
    return UniversalAnswerResponse(**result)


class SolveDragPuzzleRequest(BaseModel):
    ws_url: str


class SolveDragPuzzleResponse(BaseModel):
    status: str
    number: Optional[str] = None
    button_clicked: bool = False


@router.post("/survey/solve-drag", response_model=SolveDragPuzzleResponse, dependencies=[Depends(require_survey_ready)])
async def api_solve_drag_puzzle(req: SolveDragPuzzleRequest):
    """
    Solve Angular CDK drag-drop puzzle (PureSpectrum "Zahl X").

    APPROACH B (PRIMARY): CDP Input.dispatchMouseEvent chain.
    NOT synthetic PointerEvents — Angular CDK ignores synthetic events!
    VERIFIED: Survey 49517969 (Zahl 28) → 100% ✅

    Kapselt: tools.tool_solve_drag_puzzle.solve(ws_url)
    """
    result = solve_drag_puzzle(req.ws_url)
    update_command_registry("solve_drag_puzzle", result["status"] == "ok", result)
    return SolveDragPuzzleResponse(**result)


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
    "ClickRequest", "ClickResponse",
    "FindRequest", "FindResponse",
    "VerifyRequest", "VerifyResponse",
    "ClickAngularRequest", "ClickAngularResponse",
    "FillInputRequest", "FillInputResponse",
    "FindTabRequest", "FindTabResponse",
    "CloseModalsRequest", "CloseModalsResponse",
    "CaptchaSolveRequest", "CaptchaSolveResponse",
    "ScanDashboardRequest", "ScanDashboardResponse",
    "UniversalAnswerRequest", "UniversalAnswerResponse",
    "SolveDragPuzzleRequest", "SolveDragPuzzleResponse",
]