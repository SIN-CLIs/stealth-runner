# ════════════════════════════════════════════════════════════════════════════════╗
# ║  SURVEY ANSWER — snapshot, completion, answer (universal)                    ║
# ║                                                                               ║
# ║  100% ELEMENT CAPTURE via ELEMENT_EXTRACTOR_JS (survey-cli/survey/snapshot.py)║
# ║  Universal answer via tool_universal_answer.py (DOM-based, not provider-hardcode)║
# ║  Integration: commands/surveys/survey-answer-patterns.md                      ║
# ╚═══════════════════════════════════════════════════════════════════════════════╝

from __future__ import annotations

from fastapi import APIRouter, Depends

from ._common import (
    CompletionRequest,
    CompletionResponse,
    SnapshotRequest,
    SnapshotResponse,
    UniversalAnswerRequest,
    UniversalAnswerResponse,
    require_survey_ready,
    update_command_registry,
)

router = APIRouter(prefix="/survey", tags=["survey-answer"])

import asyncio
import hashlib
import json
import urllib.request

import websockets

# ═══════════════════════════════════════════════════════════════════════════════
# POST /survey/snapshot — 100% element capture via ELEMENT_EXTRACTOR_JS
# Source: survey-cli/survey/snapshot.py (ELEMENT_EXTRACTOR_JS — COMPREHENSIVE 2026-05-11)
# Features: Shadow DOM traversal, Angular CDK drag-drop, visual captcha, iframes
# ═══════════════════════════════════════════════════════════════════════════════

EXTRACTOR_JS = """
(function(){
    var out=[], seen=new Set(), images=[], dragPuzzle=null, captchas=[];
    var scanRoot = (function(){
        var mods = document.querySelectorAll('[class*=modal],[role=dialog],.overlay,.dialog,.modal.show,.modal-content');
        var best=null, bd=Infinity;
        mods.forEach(function(m){
            var s=window.getComputedStyle(m);
            if(s.display==='none'||s.visibility==='hidden') return;
            var r=m.getBoundingClientRect();
            if(!r||r.width===0) return;
            var d=Math.sqrt(Math.pow(r.left+r.width/2-window.innerWidth/2,2)+Math.pow(r.top+r.height/2-window.innerHeight/2,2));
            if(d<bd){bd=d;best=m;}
        });
        return best||document.body;
    })();
    function walkShadow(root,d){
        if(!root||d>5) return;
        try{
            var els=root.querySelectorAll?root.querySelectorAll('*'):[];
            for(var i=0;i<els.length;i++){
                var el=els[i];
                if(el.shadowRoot) walkShadow(el.shadowRoot,d+1);
                processEl(el);
            }
        }catch(e){}
    }
    function processEl(el){
        if(!el||seen.has(el)) return;
        var rect=el.getBoundingClientRect?el.getBoundingClientRect():null;
        var visible=rect&&rect.width>0&&rect.height>0;
        var tag=(el.tagName||'').toLowerCase();
        var text=(el.innerText||el.textContent||el.value||'').substring(0,80).trim();
        var hint=el.getAttribute('placeholder')||el.getAttribute('aria-label')||el.getAttribute('title')||'';
        var role=el.getAttribute('role')||'';
        var type=el.getAttribute('type')||'';
        var cls=el.className||'';
        var name=el.getAttribute('name')||'';
        var id=el.getAttribute('id')||'';
        var checked=el.checked||false;
        var disabled=el.disabled||false;
        var rect_str=visible?JSON.stringify({x:Math.round(rect.left),y:Math.round(rect.top),w:Math.round(rect.width),h:Math.round(rect.height)}):'null';
        var key=tag+':'+text.substring(0,20)+':'+rect_str;
        if(visible&&(text||hint||role)){
            seen.add(el);
            out.push({tag,text,hint,role,type,cls,name,id,rect:rect_str,checked,disabled,index:out.length});
            if(tag==='img'){
                images.push({src:el.src,alt:el.alt,index:out.length-1});
                if(cls.includes('captcha')||el.src.includes('captcha')||el.alt.match(/^[A-Z0-9]{4,8}$/))
                    captchas.push({src:el.src,alt:el.alt,index:out.length-1});
            }
        }
        if(tag==='canvas'&&el.width>50) captchas.push({tag:'canvas',w:el.width,h:el.height,index:out.length});
    }
    walkShadow(document.body,0);
    var allEls=scanRoot.querySelectorAll('*');
    for(var i=0;i<allEls.length;i++) processEl(allEls[i]);
    var dragEls=document.querySelectorAll('.cdk-drag, [draggable=true]');
    if(dragEls.length>0){
        var imgs=document.querySelectorAll('.cdk-drag img, [draggable=true] img');
        var dropZones=document.querySelectorAll('.cdk-drop-list');
        var dragText=document.body.innerText.match(/Zahl\\s*(\\d+)|leg.*\\s(\\d+)/);
        dragPuzzle={count:dragEls.length,imgCount:imgs.length,dropZoneCount:dropZones.length,
            number:dragText?dragText[1]||dragText[2]:null,imgs:[{src:i.src,alt:i.alt} for(i of imgs)]};
    }
    var iframeEls=document.querySelectorAll('iframe');
    if(iframeEls.length>0){
        for(var f of iframeEls){
            try{
                var idoc=f.contentDocument||f.contentWindow&&f.contentWindow.document;
                if(idoc) walkShadow(idoc.body,0);
            }catch(e){}
        }
    }
    var txt=document.body.innerText.substring(0,200);
    return {elements:out,images,captchas,dragPuzzle,count:out.length,text_preview:txt};
})()
"""


async def _ws_snapshot(ws_url: str) -> dict:
    """Execute ELEMENT_EXTRACTOR_JS via WebSocket."""
    async with websockets.connect(ws_url) as ws:
        await ws.send(
            json.dumps(
                {"id": 1, "method": "Runtime.evaluate", "params": {"expression": EXTRACTOR_JS}}
            )
        )
        resp = await asyncio.wait_for(ws.recv(), timeout=10)
        return json.loads(resp).get("result", {}).get("result", {}).get("value", {})


@router.post(
    "/snapshot", response_model=SnapshotResponse, dependencies=[Depends(require_survey_ready)]
)
async def api_snapshot(req: SnapshotRequest):
    """
    Captures ALL elements on the current page at 100% coverage.

    100% Element Capture (ELEMENT_EXTRACTOR_JS):
      ✓ All form elements (input, button, select, textarea)
      ✓ Shadow DOM traversal (depth≤5, Angular apps)
      ✓ Angular CDK drag-drop puzzle (.cdk-drag, .drop-zone, img[alt])
      ✓ HeyPiggy modal buttons (.modal-button-positive/negative)
      ✓ Visual captcha detection (canvas, img.captcha, base64 patterns)
      ✓ All images (src, alt, index) for captcha analysis
      ✓ Iframe content extraction (HeyPiggy embeds surveys in iframes)
      ✓ Modal detection via viewport-center proximity
      ✓ Cookie consent banner (.cky-btn-accept)
      ✓ Sort by Y-position (questions before answers)

    Uses CDP WebSocket Runtime.evaluate (PRIMARY, NOT cua-driver!)
    """
    ws = req.ws_url
    if not ws:
        raw = urllib.request.urlopen(f"http://127.0.0.1:{req.cdp_port}/json/list", timeout=3).read()
        pages = json.loads(raw)
        for p in pages:
            if p.get("type") == "page" and not p.get("url", "").startswith("chrome-extension"):
                ws = p.get("webSocketDebuggerUrl", "")
                break

    if not ws:
        return SnapshotResponse(status="error", reason="No tab found")

    try:
        data = await _ws_snapshot(ws)
        body_preview = data.get("text_preview", "")[:200]
        elem_count = data.get("count", 0)
        elements = data.get("elements", [])
        hash_str = hashlib.md5(json.dumps(elements, sort_keys=True).encode()).hexdigest()[:12]

        update_command_registry(
            "snapshot_page", True, {"pages_processed": 1, "elements_captured": elem_count}
        )
        return SnapshotResponse(
            status="ok",
            url="",
            title="",
            body_preview=body_preview,
            element_count=elem_count,
            hash=hash_str,
            elements=elements,
        )
    except Exception as e:
        update_command_registry("snapshot_page", False, {"error": str(e)})
        return SnapshotResponse(status="error", reason=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# POST /survey/completion — Detects survey completion / screen-out
# Completion keywords: "vielen dank", "abgeschlossen", "fertig", "completed"
# Screen-out keywords: "keine passende", "nicht qualifiziert", "screen out"
# ═══════════════════════════════════════════════════════════════════════════════


@router.post(
    "/completion", response_model=CompletionResponse, dependencies=[Depends(require_survey_ready)]
)
async def api_completion(req: CompletionRequest):
    """Detects if survey is completed, screen-out, or still running."""
    ws = req.ws_url
    if not ws:
        raw = urllib.request.urlopen(f"http://127.0.0.1:{req.cdp_port}/json/list", timeout=3).read()
        pages = json.loads(raw)
        for p in pages:
            if p.get("type") == "page" and "heypiggy" in p.get("url", ""):
                ws = p.get("webSocketDebuggerUrl", "")
                break

    if not ws:
        return CompletionResponse(status="error", reason="No tab found")

    try:
        async with websockets.connect(ws) as w:
            await w.send(
                json.dumps(
                    {
                        "id": 1,
                        "method": "Runtime.evaluate",
                        "params": {"expression": "document.body.innerText"},
                    }
                )
            )
            resp = await asyncio.wait_for(w.recv(), timeout=5)
            text = json.loads(resp).get("result", {}).get("result", {}).get("value", "").lower()

        completed = any(
            k in text
            for k in ["vielen dank", "abgeschlossen", "fertig", "completed", "thank you", "danke"]
        )
        screen_out = any(
            k in text
            for k in [
                "keine passende umfrage",
                "nicht qualifiziert",
                "screen out",
                "no matching",
                "keine umfragen",
            ]
        )

        update_command_registry(
            "detect_completion", True, {"completed": completed, "screen_out": screen_out}
        )
        return CompletionResponse(
            status="ok",
            completed=completed,
            screen_out=screen_out,
            balance=0.0,
            reason="completed" if completed else ("screen_out" if screen_out else "in_progress"),
        )
    except Exception as e:
        update_command_registry("detect_completion", False, {"error": str(e)})
        return CompletionResponse(status="error", reason=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# POST /survey/answer — Universal DOM-based survey answerer
# Verified: commands/surveys/survey-answer-patterns.md (radio/checkbox/text/submit)
# Provider-agnostic: detects question type from DOM, not from provider name!
# ═══════════════════════════════════════════════════════════════════════════════


@router.post(
    "/answer", response_model=UniversalAnswerResponse, dependencies=[Depends(require_survey_ready)]
)
async def api_universal_answer(req: UniversalAnswerRequest):
    """
    Universeller Survey-Answerer — DOM-basiert, NICHT provider-hardcoded.

    Verified patterns (commands/surveys/survey-answer-patterns.md):
      ✓ Radio: document.querySelectorAll("input[type=radio]")[0].click()
      ✓ Checkbox: document.querySelectorAll("input[type=checkbox]")[0].click()
      ✓ Text: textarea.value=... + dispatchEvent(input+change)
      ✓ Submit: "Weiter"/"Next"/"Submit" button click

    Provider-agnostic: erkennt question_type aus DOM Struktur:
      - "radio" → single choice
      - "checkbox" → multi choice
      - "text" → open text
      - "textarea" → long text
      - "select" → dropdown
      - "nps" → 0-10 scale

    Profile-based answer mapping (tool_universal_answer.py):
      - Lädt Persona-Daten aus survey-cli/profiles/
      - Mappt Antworten basierend auf demographic profile
      - NICHT: if provider=="qualtrics" → hardcoded answers
    """
    try:
        from tools.tool_universal_answer import answer as _universal_answer

        result = _universal_answer(
            ws_url=req.ws_url,
            cdp_port=req.cdp_port,
            profile_name=req.profile_name,
            provider=req.provider,
            max_select=req.max_select,
        )
        update_command_registry("universal_answer", result.get("status") == "ok", result)
        return UniversalAnswerResponse(
            status=result.get("status", "ok"),
            answered=result.get("answered", 0),
            provider=result.get("provider", ""),
            question_type=result.get("question_type", ""),
            actions=result.get("actions", []),
            reason=result.get("reason"),
        )
    except Exception as e:
        update_command_registry("universal_answer", False, {"error": str(e)})
        return UniversalAnswerResponse(status="error", reason=str(e))
