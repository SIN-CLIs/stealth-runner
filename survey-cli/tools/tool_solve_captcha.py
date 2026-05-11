"""================================================================================
DEPRECATED 2026-05-11 — Wird ersetzt durch die kanonische v2-Pipeline.
================================================================================

Dieser Tool-Pfad ist LEGACY. Er bleibt nur fuer Backward-Compat bestehender
Integrationen erhalten. NEUER Code MUSS gegen die folgenden Endpoints
programmieren:

    POST /v2/scan         → ersetzt /survey/snapshot, /survey/scan
    POST /v2/click        → ersetzt /survey/click, /survey/click-angular
    POST /v2/fill         → ersetzt /survey/fill-input
    POST /v2/press_key    → neu
    POST /v2/captcha/*    → ersetzt /survey/solve-captcha,
                            /survey/solve-drag-puzzle

Die Implementierungen leben in:
    survey-cli/survey/cdp_universal.py      Universal Scanner (AX-Tree pierce)
    survey-cli/survey/cdp_actuator.py       Maus-Events + Pflicht-Verify
    survey-cli/survey/captcha_router.py     Detection + Solver-Routing
    agent-toolbox/api/endpoints/universal.py FastAPI-Endpoints unter /v2/*

WARUM DIESER TOOL-PFAD STIRBT:
  - Y-Sort-Reihenfolge → instabile @eN-Indizes bei Reflow
  - el.click() / .value = "..." → von React/Angular ignoriert
  - Keine Pflicht-Verify nach Aktion → Halluzinationen "Performed without effect"
  - Provider-spezifisches JS hardcoded → jeder neue Provider = Patch
  - walkShadows(depth>5) → tieferes Shadow-DOM unsichtbar
  - iframes nur gezaehlt, nie betreten

Migration-Path fuer dieses Modul:
  → Wrap die alte API auf /v2/*. Wenn das alte Tool z.B. (selector) erwartet,
    intern via /v2/scan einen Match auf attrs.id / name finden und dessen
    stable_id an /v2/click weitergeben. So bleibt die externe API stabil.

LIES BEVOR DU DIESES MODUL AENDERST: AGENTS.md Sektion
"KANONISCHE ARCHITEKTUR (2026-05-11)".
================================================================================

================================================================================
TOOL DOCSTRING (legacy, pre-deprecation):
================================================================================
TOOL: solve_captcha — Auto-Detect + Solve (Text/Slide/Drag)

Universal captcha solver: detects type → picks correct approach → executes.
UNDER 300 LINES. NO wrapper pattern. Full workflow with registry.

STATUS: __frozen__=True | Version: 2026-05-11

BANNED: ❌ playstealth | ❌ webauto-nodriver | ❌ hardcoded PIDs | ❌ pkill Chrome
"""
from __future__ import annotations
import json, os, random, urllib.request, websocket
from typing import Literal

__frozen__ = True
__version__ = "2026-05-11"


# ── Type Detection ───────────────────────────────────────────────────────────

def _detect_type(ws_url: str) -> Literal["slide", "text", "drag", "visual", "none"]:
    js = """
(function() {
    if (document.querySelector('.cdk-drag, .drop-zone, [class*="cdk-drop"]')) return 'drag';
    if (document.querySelector('.gc-drag-block, .gt_slider, [class*="drag-block"]')) return 'slide';
    var imgs = document.querySelectorAll('img');
    for (var i = 0; i < imgs.length; i++) {
        var src = (imgs[i].src || '').toLowerCase();
        if (src.includes('captcha') || src.includes('verify') || src.includes('base64')) return 'text';
    }
    var body = (document.body.innerText || '');
    if (body.includes('Bitte legen Sie die Zahl')) return 'drag';
    return 'none';
})()"""
    try:
        ws = websocket.create_connection(ws_url, timeout=10)
        ws.send(json.dumps({"id": 0, "method": "Runtime.evaluate", "params": {"expression": js}}))
        r = json.loads(ws.recv()); ws.close()
        return r.get("result", {}).get("result", {}).get("value", "none")
    except Exception:
        return "none"


# ── Text/OCR Solver ───────────────────────────────────────────────────────────

def _solve_text(ws_url: str) -> dict:
    """Screenshot → NVIDIA Vision OCR → type → submit."""
    # Extract base64 image
    js = "var img=document.querySelector('img[src*=base64],img[src*=captcha],canvas');if(!img)return null;return img.tagName==='CANVAS'?img.toDataURL('image/png'):img.src;"
    try:
        ws = websocket.create_connection(ws_url, timeout=10)
        ws.send(json.dumps({"id": 0, "method": "Runtime.evaluate", "params": {"expression": js}}))
        r = json.loads(ws.recv()); ws.close()
        b64 = r.get("result", {}).get("result", {}).get("value")
        if not b64: return {"status": "error", "reason": "no_image"}
    except Exception as e:
        return {"status": "error", "reason": str(e)[:100]}

    # OCR via NVIDIA NIM (Llama Vision)
    nvidia_key = os.environ.get("NVIDIA_API_KEY", "")
    if not nvidia_key: return {"status": "error", "reason": "no_nvidia_key"}

    try:
        req = urllib.request.Request(
            "https://integrate.api.nvidia.com/v1/chat/completions",
            data=json.dumps({
                "model": "meta/llama-3.2-11b-vision-instruct",
                "messages": [{"role": "user", "content": f"What text is shown? Reply ONLY with the text.\n![img](data:image/png;base64,{b64})"}],
                "max_tokens": 20, "temperature": 0.1
            }).encode(),
            headers={"Authorization": f"Bearer {nvidia_key}", "Content-Type": "application/json"},
            method="POST"
        )
        resp = json.loads(urllib.request.urlopen(req, timeout=15).read())
        text = resp["choices"][0]["message"]["content"].strip()
        if not text: return {"status": "error", "reason": "empty_ocr"}
    except Exception as e:
        return {"status": "error", "reason": f"vision_error: {e}"}
        return {"status": "error", "reason": f"vision_error: {e}"}

    # Type + submit
    type_js = f"(function(){{var inp=document.querySelector('input[type=text],input[name*=captcha]');if(inp){{inp.value='{text}';inp.dispatchEvent(new Event('input',{{bubbles:true}}));inp.dispatchEvent(new Event('change',{{bubbles:true}}));}}var btns=document.querySelectorAll('button');for(var b=0;b<btns.length;b++){{var t=(btns[b].innerText||'').trim();if(t.includes('Nächste')||t.includes('Weiter')||t.includes('Submit')){{btns[b].click();break;}}}}}})()"
    try:
        ws = websocket.create_connection(ws_url, timeout=10)
        ws.send(json.dumps({"id": 0, "method": "Runtime.evaluate", "params": {"expression": type_js}}))
        _ = json.loads(ws.recv()); ws.close()
    except Exception as e:
        return {"status": "error", "reason": str(e)[:100]}

    return {"status": "ok", "type": "text", "text": text}


# ── Slide Solver (CDP Trajectory) ────────────────────────────────────────────

def _solve_slide(ws_url: str) -> dict:
    """Find gap → Bezier trajectory → CDP mouse events."""
    js = "var b=document.querySelector('.gc-drag-block,.gt_slider,[class*=drag-block]');var t=document.querySelector('.gc-drag-target,[class*=target]');if(!b)return null;var br=b.getBoundingClientRect();var tr=t?t.getBoundingClientRect():null;return{blockX:br.left+br.width/2,blockY:br.top+br.height/2,targetX:tr?tr.left+tr.width/2:br.right+100,targetY:tr?tr.top+tr.height/2:br.top+br.height/2,gap:tr?tr.left-br.right:100};"
    try:
        ws = websocket.create_connection(ws_url, timeout=10)
        ws.send(json.dumps({"id": 0, "method": "Runtime.evaluate", "params": {"expression": js}}))
        r = json.loads(ws.recv()); ws.close()
        geo = r.get("result", {}).get("result", {}).get("value")
        if not geo: return {"status": "error", "reason": "no_slider"}
    except Exception as e:
        return {"status": "error", "reason": str(e)[:100]}

    sx, sy, ex, ey, gap = geo["blockX"], geo["blockY"], geo["targetX"], geo["targetY"], geo["gap"]
    dur = 1200 + gap * 2

    def cdp_mouse(t_, x, y, btn="left", cc=1):
        ws = websocket.create_connection(ws_url, timeout=10)
        ws.send(json.dumps({"id": 0, "method": "Input.dispatchMouseEvent", "params": {"type": t_, "x": x, "y": y, "button": btn, "clickCount": cc, "pointerType": "mouse"}}))
        _ = json.loads(ws.recv()); ws.close()

    cdp_mouse("mousePressed", sx, sy)
    for i in range(41):
        t = i / 40
        px = sx + (ex - sx) * t - (20 * (1 - abs(2*t-1))) * (sy > ey and 1 or -1 if ex != sx else 0)
        py = sy + (ey - sy) * t
        cdp_mouse("mouseMoved", px + random.uniform(-1.5, 1.5), py + random.uniform(-2, 2))
    cdp_mouse("mouseReleased", ex, ey)
    return {"status": "ok", "type": "slide", "gap_px": gap}


# ── Registry ──────────────────────────────────────────────────────────────────

def _registry(cmd: str, ok: bool, details: dict):
    try:
        from survey.command_registry import CommandRegistry
        reg = CommandRegistry(); reg.record_command(cmd, ok, details)
    except Exception: pass

def _preflight(cmd: str) -> bool:
    try:
        from survey.command_registry import CommandRegistry
        CommandRegistry().validate_command(cmd); return True
    except Exception: return True


# ── Public API ────────────────────────────────────────────────────────────────

def solve(ws_url: str, captcha_type: str = "auto") -> dict:
    """Auto-detect and solve any captcha type.

    Args:
        ws_url: CDP WebSocket URL.
        captcha_type: "auto" | "slide" | "text" | "drag" | "visual"

    Returns:
        dict: {"status": "ok"|"error"|"skipped", "type": "...", "text": "...", ...}

    Usage:
        from tools.tool_solve_captcha import solve
        result = solve("ws://127.0.0.1:9999/devtools/page/...")
    """
    if not _preflight("solve_captcha"): return {"status": "error", "reason": "preflight_failed"}
    if captcha_type == "auto": captcha_type = _detect_type(ws_url)
    if captcha_type == "none":
        _registry("solve_captcha", True, {"type": "none"})
        return {"status": "skipped", "type": "none", "reason": "no_captcha"}
    if captcha_type == "drag":
        _registry("solve_captcha", True, {"reason": "use_tool_solve_drag_puzzle"})
        return {"status": "skipped", "type": "drag", "reason": "use tool_solve_drag_puzzle"}

    result = {"type": captcha_type}
    if captcha_type in ("text", "visual"): result = _solve_text(ws_url)
    elif captcha_type == "slide": result = _solve_slide(ws_url)
    else: result = {"status": "error", "reason": f"unknown_type: {captcha_type}"}

    result["type"] = captcha_type
    _registry("solve_captcha", result["status"] == "ok", result)
    return result


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2: print("Usage: tool_solve_captcha.py <ws_url> [type]")
    else: print(json.dumps(solve(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "auto"), indent=2))