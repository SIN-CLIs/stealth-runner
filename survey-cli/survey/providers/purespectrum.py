"""PureSpectrum provider — captcha OCR + drag puzzle solver.

SOTA: CDP mouse clicks for Angular v19 (JS .click() ignored).
OCR: base64 img extraction → NVIDIA Vision API.
Drag: __ngContext__ recursive search → dropListRef.drop().
"""

import json
import time
import os
import re
import websocket
from openai import OpenAI

VISION_MODEL = "meta/llama-3.2-11b-vision-instruct"
NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"

COMPLETION_MARKERS = ["zurück zur website", "vielen dank", "gutgeschrieben"]

# ── CDP Mouse Click (Angular-proof) ────────────────────

def cdp_click(ws_url, x, y):
    """CDP Input.dispatchMouseEvent — real OS event (isTrusted=true)."""
    try:
        ws = websocket.create_connection(ws_url, timeout=10)
        for et in ["mouseMoved", "mousePressed", "mouseReleased"]:
            ws.send(json.dumps({"id":0,"method":"Input.dispatchMouseEvent",
                "params":{"type":et,"x":x,"y":y,"button":"left","clickCount":1}}))
            json.loads(ws.recv())
        ws.close()
        return True
    except:
        return False


def cdp_click_button(ws_url, text):
    """Find button by text, CDP-click it."""
    try:
        ws = websocket.create_connection(ws_url, timeout=10)
        ws.send(json.dumps({"id":0,"method":"Runtime.evaluate",
            "params":{"expression": f"var b=document.querySelector('button');if(b){{var r=b.getBoundingClientRect();return JSON.stringify({{x:r.x+r.width/2,y:r.y+r.height/2}});}}return'{{}}';"}}))
        r = json.loads(ws.recv())
        ws.close()
        pos = json.loads(r.get("result",{}).get("result",{}).get("value","{}"))
        if pos.get("x"):
            return cdp_click(ws_url, pos["x"], pos["y"])
    except:
        pass
    return False


# ── Cookie Consent ─────────────────────────────────────

def handle_cookie_consent(ws_url):
    try:
        ws = websocket.create_connection(ws_url, timeout=15)
        ws.send(json.dumps({"id":0,"method":"Runtime.evaluate",
            "params":{"expression": "var b=document.querySelector('button');if(b){b.click();return'clicked';}return'none';"}}))
        r = json.loads(ws.recv()); ws.close()
        return {"success": "clicked" in str(r.get("result",{}).get("result",{}).get("value",""))}
    except Exception as e:
        return {"success": False, "error": str(e)[:100]}


# ── ROBOT Textarea Fill ────────────────────────────────

def fill_opinion_textarea(ws_url):
    try:
        ws = websocket.create_connection(ws_url, timeout=15)
        ws.send(json.dumps({"id":0,"method":"Runtime.evaluate",
            "params":{"expression": "var t=document.querySelector('textarea');if(t){t.value='ROBOT I enjoy sharing my opinion about this topic.';t.dispatchEvent(new Event('input',{bubbles:true}));t.dispatchEvent(new Event('change',{bubbles:true}));return'filled';}return'none';"}}))
        json.loads(ws.recv()); ws.close()
        return True
    except:
        return False


# ── Text Captcha OCR ───────────────────────────────────

def solve_text_captcha(ws_url, debug=False):
    """Extract base64 captcha img → NVIDIA Vision OCR → fill + CDP-click submit."""
    try:
        ws = websocket.create_connection(ws_url, timeout=15)
        
        # Find captcha image position for CLIPPED screenshot
        ws.send(json.dumps({"id":0,"method":"Runtime.evaluate",
            "params":{"expression": """
(function() {
    // Find captcha image: medium size, visible, near text input
    var input = document.querySelector('input[type=text]');
    var inputY = input ? input.getBoundingClientRect().y : 500;
    var imgs = document.querySelectorAll('img');
    for (var i=0;i<imgs.length;i++) {
        var r = imgs[i].getBoundingClientRect();
        // Captcha is ABOVE the input field, 50-200px wide, 20-80px tall
        if (r.width>50 && r.width<300 && r.height>20 && r.height<100 && r.y < inputY && imgs[i].offsetParent) {
            return JSON.stringify({x:r.x-5, y:r.y-5, w:r.width+10, h:r.height+10, found:true});
        }
    }
    return JSON.stringify({found:false});
})()
"""}}))
        r = json.loads(ws.recv())
        clip = json.loads(r.get("result",{}).get("result",{}).get("value","{}"))
        
        if not clip.get("found"):
            ws.close()
            return {"success": False, "error": "No captcha image found for clipping"}
        
        # Screenshot with clip (2x scale for better OCR)
        ws.send(json.dumps({"id":1,"method":"Page.captureScreenshot",
            "params":{"format":"png","clip":{"x":max(0,clip["x"]),"y":max(0,clip["y"]),
                "width":clip["w"],"height":clip["h"],"scale":3}}}))
        r = json.loads(ws.recv())
        ws.close()
        b64 = r.get("result",{}).get("data","")
        
        if not b64 or len(b64) < 100:
            return {"success": False, "error": "Screenshot empty"}
        
        if debug:
            print(f"  [CAPTCHA] Clip screenshot: {len(b64)} chars base64")
        
        # OCR
        api_key = os.getenv("NVIDIA_API_KEY")
        if not api_key:
            return {"success": False, "error": "NVIDIA_API_KEY not set"}

        client = OpenAI(api_key=api_key, base_url=NIM_BASE_URL)
        start = time.monotonic()
        resp = client.chat.completions.create(
            model=VISION_MODEL,
            messages=[{"role":"user","content":[
                {"type":"text","text":"Read the captcha. Return ONLY the letters and numbers. No spaces, no explanation. Max 8 chars. The characters may be distorted, slanted, or have lines through them."},
                {"type":"image_url","image_url":{"url":f"data:image/png;base64,{b64}"}}
            ]}],
            max_tokens=15, temperature=0.0)
        elapsed = (time.monotonic()-start)*1000
        raw = resp.choices[0].message.content.strip()
        captcha = re.sub(r'[^a-zA-Z0-9]','',raw).upper()[:10]
        tokens = resp.usage.total_tokens if resp.usage else 0

        if debug:
            print(f"  [CAPTCHA] OCR: '{captcha}' ({elapsed:.0f}ms, {tokens}tok)")

        if len(captcha) < 2:
            return {"success": False, "error": f"OCR too short: {captcha}", "raw": raw}

        # Fill input
        ws = websocket.create_connection(ws_url, timeout=15)
        ws.send(json.dumps({"id":0,"method":"Runtime.evaluate",
            "params":{"expression": f"var i=document.querySelector('input[type=text]');if(i){{i.value='{captcha}';i.dispatchEvent(new Event('input',{{bubbles:true}}));i.dispatchEvent(new Event('change',{{bubbles:true}}));}}"}}))
        json.loads(ws.recv()); ws.close()

        # CDP-click submit
        cdp_click_button(ws_url, "Nächste")
        time.sleep(0.5)

        return {"success": True, "captcha_text": captcha, "tokens_used": tokens,
                "elapsed_ms": round(elapsed)}

    except Exception as e:
        return {"success": False, "error": str(e)[:200]}


# ── Drag Puzzle Solver (__ngContext__) ─────────────────

def solve_drag_puzzle(ws_url):
    """Recursive __ngContext__ search → dropListRef.drop()."""
    js = """(() => {
    function findInstance(root, propertyName) {
        if (!root || typeof root !== 'object') return null;
        if (root.hasOwnProperty(propertyName)) return root;
        for (let key of Object.keys(root)) {
            try { const res = findInstance(root[key], propertyName); if (res) return res; } catch (e) {}
        }
        return null;
    }
    const dropListEl = document.querySelector('.cdk-drop-list');
    if (!dropListEl) return 'NO_DROPLIST';
    const dragEls = document.querySelectorAll('.cdk-drag');
    if (!dragEls.length) return 'NO_DRAGELS';
    const ctx = dropListEl.__ngContext__;
    if (!ctx) return 'NO_CTX';
    const dropListDir = findInstance(ctx, '_dropListRef');
    if (!dropListDir) return 'NO_DROPLISTDIR';
    const dropListRef = dropListDir._dropListRef;
    if (!dropListRef) return 'NO_DROPLISTREF';
    const firstDragEl = dragEls[0];
    const dragCtx = firstDragEl.__ngContext__;
    const dragDir = findInstance(dragCtx, '_dragRef');
    if (!dragDir) return 'NO_DRAGDIR';
    const dragRef = dragDir._dragRef;
    if (!dragRef) return 'NO_DRAGREF';
    try {
        dropListRef.enter(dragRef, dragRef.element.nativeElement, 0);
        dropListRef.drop(dragRef, 0);
        return 'DROP_SUCCESS:' + (dragRef.element.nativeElement.textContent || '').trim();
    } catch (e) { return 'DROP_ERROR: ' + e.message; }
})()"""
    try:
        ws = websocket.create_connection(ws_url, timeout=15)
        ws.send(json.dumps({"id":0,"method":"Runtime.evaluate",
            "params":{"expression": js, "returnByValue": True}}))
        r = json.loads(ws.recv()); ws.close()
        result = r.get("result",{}).get("result",{}).get("value","???")
        return {"success": "DROP_SUCCESS" in str(result), "result": result}
    except Exception as e:
        return {"success": False, "result": None, "error": str(e)[:200]}


# ── Page Text Reader ───────────────────────────────────

def read_page_text(ws_url, max_len=1000):
    try:
        ws = websocket.create_connection(ws_url, timeout=10)
        ws.send(json.dumps({"id":0,"method":"Runtime.evaluate",
            "params":{"expression": f"document.body.innerText.substring(0,{max_len})"}}))
        r = json.loads(ws.recv()); ws.close()
        return r.get("result",{}).get("result",{}).get("value","")
    except:
        return ""


# ── Full Preflight ─────────────────────────────────────

def solve_purespectrum_preflight(ws_url, debug=False):
    """Run full PureSpectrum preflight: cookie → ROBOT → captcha → puzzle."""
    steps = []

    # 1. Cookie
    handle_cookie_consent(ws_url)
    steps.append("cookie")
    time.sleep(2)

    # 2. ROBOT
    text = read_page_text(ws_url, 2000)
    if "ROBOT" in text:
        fill_opinion_textarea(ws_url)
        time.sleep(1)
        cdp_click_button(ws_url, "Nächste")
        steps.append("robot")
        time.sleep(5)

    # 3. Text captcha
    text = read_page_text(ws_url, 2000)
    if "Code" in text and ("eingeben" in text or "captcha" in text.lower()):
        result = solve_text_captcha(ws_url, debug=debug)
        steps.append(f"captcha:{result.get('success')}")
        if not result.get("success"):
            return {"success": False, "steps": steps, "error": result.get("error")}
        time.sleep(5)

    # 4. Drag puzzle
    text = read_page_text(ws_url, 2000)
    if "Bitte legen Sie die Zahl" in text:
        result = solve_drag_puzzle(ws_url)
        steps.append(f"puzzle:{result.get('success')}")
        if not result.get("success"):
            return {"success": False, "steps": steps, "error": result.get("error")}
        time.sleep(5)

    return {"success": True, "steps": steps}
