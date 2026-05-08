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

COMMANDS = {
    "click_next": "__CDP_CLICK_BUTTON__:Nächste",
    "click_element": "__CDP_CLICK__:input[type=radio]:{idx}",
    "fill_text": '''(function(v){
        var t=document.querySelector("textarea,input[type=text]");
        if(t){
            var proto = t.tagName === "TEXTAREA" ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
            var nativeSetter = Object.getOwnPropertyDescriptor(proto,'value').set;
            if(nativeSetter) nativeSetter.call(t,v); else t.value=v;
            t.dispatchEvent(new Event("input",{bubbles:true,cancelable:true}));
            t.dispatchEvent(new Event("change",{bubbles:true,cancelable:true}));
            t.dispatchEvent(new Event("blur",{bubbles:true,cancelable:true}));
        }
    })("{value}")''',
}

from .base import ProviderAdapter


class PureSpectrumAdapter(ProviderAdapter):
    """PureSpectrum adapter for Angular pages and captcha boundaries."""

    def __init__(self):
        super().__init__(
            name="purespectrum",
            url_patterns=["purespectrum.com", "purespectrum"],
            commands=COMMANDS,
            completion_markers=COMPLETION_MARKERS,
        )

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
    """Extract captcha img → NVIDIA Vision OCR → fill + CDP-click submit.

    Strategy (2026-05-06):
    1. Find captcha image via MULTIPLE strategies (not just position)
    2. Screenshot the specific img element (not a positional clip)
    3. High-res (scale=3) for better OCR
    4. Targeted prompt + result validation (4-8 alphanumeric chars)
    """
    try:
        ws = websocket.create_connection(ws_url, timeout=15)

        # Find captcha image: try multiple selectors
        ws.send(json.dumps({"id":0,"method":"Runtime.evaluate",
            "params":{"expression": """
(function() {
    // Strategy 1: Look for images inside captcha-related containers
    var captchaImg = document.querySelector('img[alt*=captcha],img[alt*=Captcha],img[alt*=code],img[class*=captcha],img[class*=code],img[class*=verify]');
    if(captchaImg) {
        var r = captchaImg.getBoundingClientRect();
        return JSON.stringify({x:r.x,y:r.y,w:r.width,h:r.height,strategy:'selector'});
    }
    // Strategy 2: Image near the text input, correct size range
    var input = document.querySelector('input[type=text]');
    var inputRect = input ? input.getBoundingClientRect() : null;
    var imgs = document.querySelectorAll('img');
    var best = null, bestDist = 99999;
    for(var i=0;i<imgs.length;i++) {
        var r = imgs[i].getBoundingClientRect();
        // Captcha: above/beside input, 80-400px wide, 30-120px tall
        if(r.width>=80 && r.width<=400 && r.height>=30 && r.height<=120) {
            var visible = r.width>0 && r.height>0 && imgs[i].offsetParent;
            if(!visible) continue;
            // Prefer image closest to input vertically
            if(inputRect) {
                var dist = Math.abs(r.y - inputRect.y) + Math.abs(r.x - inputRect.x);
                if(dist < bestDist) { bestDist = dist; best = r; }
            } else if(r.y < 600) { best = r; }
        }
    }
    if(best) return JSON.stringify({x:best.x,y:best.y,w:best.width,h:best.height,strategy:'positional'});
    return JSON.stringify({found:false});
})()
"""}}))
        r = json.loads(ws.recv())
        clip = json.loads(r.get("result",{}).get("result",{}).get("value","{}"))

        if clip.get("found") is False:
            ws.close()
            return {"success": False, "error": "No captcha image found (all strategies)"}

        x, y, w, h = clip["x"], clip["y"], clip["w"], clip["h"]
        strategy = clip.get("strategy", "?")
        if debug:
            print(f"  [CAPTCHA] Found via {strategy}: ({x:.0f},{y:.0f}) {w:.0f}×{h:.0f}")

        # Screenshot captcha area at HIGH RES (3× scale for clear OCR)
        ws.send(json.dumps({"id":1,"method":"Page.captureScreenshot",
            "params":{"format":"png","clip":{"x":max(0,x-5),"y":max(0,y-5),
                "width":min(w+10,1920),"height":min(h+10,1080),"scale":3}}}))
        r = json.loads(ws.recv())
        ws.close()
        b64 = r.get("result",{}).get("data","")

        if not b64 or len(b64) < 200:
            return {"success": False, "error": f"Screenshot empty ({len(b64)} chars)"}

        if debug:
            print(f"  [CAPTCHA] Screenshot: {len(b64)} chars base64, scale=3")

        # OCR via NVIDIA Vision
        api_key = os.getenv("NVIDIA_API_KEY")
        if not api_key:
            return {"success": False, "error": "NVIDIA_API_KEY not set"}

        client = OpenAI(api_key=api_key, base_url=NIM_BASE_URL)
        start = time.monotonic()

        # Targeted prompt: captcha recognition, ignore background noise
        resp = client.chat.completions.create(
            model=VISION_MODEL,
            messages=[{"role":"user","content":[
                {"type":"text","text":"This is a captcha image. Read ONLY the character sequence shown in the image. "
                 "Return the exact letters and numbers (uppercase) with NO spaces, NO punctuation, NO explanation. "
                 "The characters may be distorted, slanted, rotated, or have noise lines through them. "
                 "Ignore any background patterns. Examples: 'PURESPC', 'XKCD42', 'ABC123', 'r4nd0m'. "
                 "If uncertain, make your best guess — return only 4-8 alphanumeric characters."},
                {"type":"image_url","image_url":{"url":f"data:image/png;base64,{b64}"}}
            ]}],
            max_tokens=12, temperature=0.1)
        elapsed = (time.monotonic()-start)*1000
        raw = resp.choices[0].message.content.strip()
        # Extract only alphanumeric, uppercase, limit to 10 chars
        captcha = re.sub(r'[^a-zA-Z0-9]','',raw).upper()[:10]
        tokens = resp.usage.total_tokens if resp.usage else 0

        if debug:
            print(f"  [CAPTCHA] Raw: '{raw}' → Cleaned: '{captcha}' ({elapsed:.0f}ms, {tokens}tok)")

        # Validate: captcha must be 4-8 alphanumeric chars
        if len(captcha) < 3:
            return {"success": False, "error": f"OCR too short ({len(captcha)} chars): '{captcha}'", "raw": raw}
        if len(captcha) > 10:
            captcha = captcha[:10]

        # Fill input with native setter (Angular form binding)
        ws2 = websocket.create_connection(ws_url, timeout=15)
        ws2.send(json.dumps({"id":0,"method":"Runtime.evaluate",
            "params":{"expression": f"""
(function(){{
    var i = document.querySelector('input[type=text]');
    if(!i) return 'no input';
    // Angular native value setter
    var nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
    if(nativeSetter) nativeSetter.call(i,'{captcha}');
    else i.value = '{captcha}';
    i.dispatchEvent(new Event('input',{{bubbles:true,cancelable:true}}));
    i.dispatchEvent(new Event('change',{{bubbles:true,cancelable:true}}));
    i.dispatchEvent(new Event('blur',{{bubbles:true,cancelable:true}}));
    return 'filled:' + i.value;
}})();
"""}}))
        json.loads(ws2.recv()); ws2.close()

        # CDP-click submit (Nächste / Next button)
        cdp_click_button(ws_url, "Nächste")
        time.sleep(0.5)

        return {"success": True, "captcha_text": captcha, "tokens_used": tokens,
                "elapsed_ms": round(elapsed), "strategy": strategy}

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
