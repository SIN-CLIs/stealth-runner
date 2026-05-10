# ════════════════════════════════════════════════════════════════════════════════╗
# ║  SURVEY ACTIONS — click, find, verify, fill-input, click-angular, close-modals║
# ║                                                                               ║
# ║  Wrapper für survey-cli/tools/: tool_click, tool_find_element, etc.          ║
# ║  Provider-agnostic, DOM-based interaction via CDP WebSocket                  ║
# ╚═══════════════════════════════════════════════════════════════════════════════╝

from __future__ import annotations

from fastapi import APIRouter, Depends
from ._common import (
    ClickRequest, ClickResponse,
    FindRequest, FindResponse,
    VerifyRequest, VerifyResponse,
    ClickAngularRequest, ClickAngularResponse,
    FillInputRequest, FillInputResponse,
    FindTabRequest, FindTabResponse,
    CloseModalsRequest, CloseModalsResponse,
    require_survey_ready, update_command_registry,
)

router = APIRouter(prefix="/survey", tags=["survey-actions"])

import json, asyncio, websockets, urllib.request

# ─── TOOL IMPORTS ──────────────────────────────────────────────────────────────
from tools.tool_click import click as _cua_click
from tools.tool_find_element import find_element as _find_element
from tools.tool_verify_state import verify_element_state as _verify_state
from tools.tool_click_angular import click as _click_angular
from tools.tool_fill_input import fill as _cdp_fill
from tools.tool_find_new_tab import find_new_tab as _find_new_tab
from tools.tool_close_modals import close_modals as _close_modals


async def _ws_evaluate(ws_url: str, expression: str) -> str:
    """Execute JS via CDP WebSocket and return result value."""
    async with websockets.connect(ws_url) as ws:
        await ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                                  "params": {"expression": expression}}))
        resp = await asyncio.wait_for(ws.recv(), timeout=5)
        return json.loads(resp).get("result", {}).get("result", {}).get("value", "")


def _get_ws(port: int, pattern: str = "heypiggy") -> str:
    """Find WebSocket URL by URL pattern."""
    raw = urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=3).read()
    pages = json.loads(raw)
    for p in pages:
        if p.get("type") == "page" and pattern in p.get("url", ""):
            return p.get("webSocketDebuggerUrl", "")
    for p in pages:
        if p.get("type") == "page" and not p.get("url", "").startswith("chrome-extension"):
            return p.get("webSocketDebuggerUrl", "")
    return ""


# ═══════════════════════════════════════════════════════════════════════════════
# POST /survey/click — Click element by CSS selector via CDP JS
# Tool: survey-cli/tools/tool_click.py
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/click", response_model=ClickResponse, dependencies=[Depends(require_survey_ready)])
async def api_click(req: ClickRequest):
    """Click element by CSS selector via CDP WebSocket."""
    try:
        ws = req.ws_url or _get_ws(req.cdp_port)
        if not ws:
            return ClickResponse(status="error", reason="No tab found")
        
        safe_sel = req.selector.replace("\\", "\\\\").replace("'", "\\'")
        js = f"(function(){{var el=document.querySelector('{safe_sel}');if(el){{el.click();return 'OK:'+el.tagName;}}return 'NIX';}})()"
        result = await _ws_evaluate(ws, js)
        
        clicked = result.startswith("OK:")
        update_command_registry("click_element", clicked, {"selector": req.selector})
        return ClickResponse(
            status="ok" if clicked else "error",
            clicked=clicked,
            element=result if clicked else None,
            reason=None if clicked else f"Element not found: {req.selector}",
        )
    except Exception as e:
        update_command_registry("click_element", False, {"error": str(e)})
        return ClickResponse(status="error", reason=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# POST /survey/find — Find elements by CSS selector
# Tool: survey-cli/tools/tool_find_element.py
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/find", response_model=FindResponse, dependencies=[Depends(require_survey_ready)])
async def api_find(req: FindRequest):
    """Find all elements matching CSS selector."""
    try:
        ws = req.ws_url or _get_ws(req.cdp_port)
        if not ws:
            return FindResponse(status="error", reason="No tab found")
        
        escaped = req.selector.replace("'", "\\'")
        js = f"(function(){{var els=document.querySelectorAll('{escaped}');return JSON.stringify({{count:els.length,items:[].slice.call(els).map(function(e,{{return {{tag:e.tagName,text:(e.innerText||e.textContent||'').trim().substring(0,50),type:e.type,role:e.getAttribute('role')||''}}}}))}});}})()"
        result = await _ws_evaluate(ws, js)
        data = json.loads(result) if result and result != "NIX" else {"count": 0, "items": []}
        
        update_command_registry("find_elements", True, {"count": data.get("count", 0)})
        return FindResponse(
            status="ok",
            found=data.get("count", 0) > 0,
            count=data.get("count", 0),
            elements=data.get("items", []),
        )
    except Exception as e:
        update_command_registry("find_elements", False, {"error": str(e)})
        return FindResponse(status="error", reason=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# POST /survey/verify — Verify element state after action
# Tool: survey-cli/tools/tool_verify_state.py
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/verify", response_model=VerifyResponse, dependencies=[Depends(require_survey_ready)])
async def api_verify(req: VerifyRequest):
    """Verify element exists and has expected state."""
    try:
        ws = req.ws_url or _get_ws(req.cdp_port)
        if not ws:
            return VerifyResponse(status="error", reason="No tab found")
        
        escaped = req.selector.replace("'", "\\'")
        js = f"(function(){{var el=document.querySelector('{escaped}');if(!el)return JSON.stringify({{found:false}});var checked=el.checked||false;var disabled=el.disabled||false;var value=el.value||'';var text=(el.innerText||el.textContent||'').trim().substring(0,50);return JSON.stringify({{found:true,checked,disabled,value,text}});}})()"
        result = await _ws_evaluate(ws, js)
        data = json.loads(result) if result else {"found": False}
        
        state_ok = data.get("found", False)
        if req.expected_state == "checked":
            state_ok = state_ok and data.get("checked", False)
        elif req.expected_state == "enabled":
            state_ok = state_ok and not data.get("disabled", True)
        
        update_command_registry("verify_state", state_ok, data)
        return VerifyResponse(
            status="ok",
            verified=state_ok,
            current_state=json.dumps(data),
        )
    except Exception as e:
        update_command_registry("verify_state", False, {"error": str(e)})
        return VerifyResponse(status="error", reason=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# POST /survey/click-angular — Click Angular element via CDP JS + dispatchEvent
# Tool: survey-cli/tools/tool_click_angular.py
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/click-angular", response_model=ClickAngularResponse, dependencies=[Depends(require_survey_ready)])
async def api_click_angular(req: ClickAngularRequest):
    """Click element in Angular apps via click() + dispatchEvent."""
    try:
        ws = req.ws_url or _get_ws(req.cdp_port)
        if not ws:
            return ClickAngularResponse(status="error", reason="No tab found")
        
        escaped = req.selector.replace("'", "\\'")
        js = f"(function(){{var el=document.querySelector('{escaped}');if(el){{el.click();el.dispatchEvent(new Event('change',{{bubbles:true}}));return 'OK';}}return 'NIX';}})()"
        result = await _ws_evaluate(ws, js)
        
        clicked = result == "OK"
        update_command_registry("click_angular", clicked, {"selector": req.selector})
        return ClickAngularResponse(status="ok" if clicked else "error", clicked=clicked)
    except Exception as e:
        update_command_registry("click_angular", False, {"error": str(e)})
        return ClickAngularResponse(status="error", reason=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# POST /survey/fill-input — Fill text input via CDP JS NativeInputValueSetter
# Tool: survey-cli/tools/tool_fill_input.py
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/fill-input", response_model=FillInputResponse, dependencies=[Depends(require_survey_ready)])
async def api_fill_input(req: FillInputRequest):
    """Fill text input using CDP NativeInputValueSetter (bypasses React/Angular)."""
    try:
        ws = req.ws_url or _get_ws(req.cdp_port)
        if not ws:
            return FillInputResponse(status="error", reason="No tab found")
        
        escaped_sel = req.selector.replace("'", "\\'")
        escaped_val = req.value.replace("\\", "\\\\").replace("'", "\\'")
        js = f"(function(){{var el=document.querySelector('{escaped_sel}');if(!el)return 'NIX';el.focus();el.value='{escaped_val}';el.dispatchEvent(new Event('input',{{bubbles:true}}));el.dispatchEvent(new Event('change',{{bubbles:true}}));return 'OK:'+el.value;}})()"
        result = await _ws_evaluate(ws, js)
        
        filled = result.startswith("OK:")
        update_command_registry("fill_input", filled, {"selector": req.selector})
        return FillInputResponse(status="ok" if filled else "error", filled=filled)
    except Exception as e:
        update_command_registry("fill_input", False, {"error": str(e)})
        return FillInputResponse(status="error", reason=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# POST /survey/find-tab — Find tab by URL pattern
# Tool: survey-cli/tools/tool_find_new_tab.py
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/find-tab", response_model=FindTabResponse, dependencies=[Depends(require_survey_ready)])
async def api_find_tab(req: FindTabRequest):
    """Find tab matching URL pattern."""
    try:
        result = _find_new_tab(req.url_pattern or "", req.cdp_port)
        found = bool(result.get("tab_id"))
        update_command_registry("find_tab", found, result)
        return FindTabResponse(
            status="ok" if found else "not_found",
            tab_id=result.get("tab_id"),
            ws_url=result.get("ws_url"),
            url=result.get("url"),
        )
    except Exception as e:
        update_command_registry("find_tab", False, {"error": str(e)})
        return FindTabResponse(status="error", reason=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# POST /survey/close-modals — Close all modals/overlays
# Tool: survey-cli/tools/tool_close_modals.py
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/close-modals", response_model=CloseModalsResponse, dependencies=[Depends(require_survey_ready)])
async def api_close_modals(req: CloseModalsRequest):
    """Close all visible modals, overlays, and popups."""
    try:
        result = _close_modals(ws_url=req.ws_url, cdp_port=req.cdp_port)
        closed = result.get("closed_count", 0) > 0
        update_command_registry("close_modals", closed, result)
        return CloseModalsResponse(
            status="ok",
            closed_count=result.get("closed_count", 0),
            reason=result.get("reason"),
        )
    except Exception as e:
        update_command_registry("close_modals", False, {"error": str(e)})
        return CloseModalsResponse(status="error", reason=str(e))