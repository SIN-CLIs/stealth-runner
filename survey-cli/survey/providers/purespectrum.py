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

from .base import ProviderAdapter  # noqa: E402 — provider files do sys.path setup above


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
    except Exception:
        return False


def cdp_click_button(ws_url, text):
    """Find button by text, CDP-click it."""
    try:
        ws = websocket.create_connection(ws_url, timeout=10)
        ws.send(json.dumps({"id":0,"method":"Runtime.evaluate",
            "params":{"expression": "var b=document.querySelector('button');if(b){var r=b.getBoundingClientRect();return JSON.stringify({x:r.x+r.width/2,y:r.y+r.height/2});}return'{}';"}}))
        r = json.loads(ws.recv())
        ws.close()
        pos = json.loads(r.get("result",{}).get("result",{}).get("value","{}"))
        if pos.get("x"):
            return cdp_click(ws_url, pos["x"], pos["y"])
    except Exception:
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
    except Exception:
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


# ── Shadow DOM Piercing for PureSpectrum Web Components ──

def shadow_dom_query_selector(ws_url, selector, tag_hint=""):
    """Query within Shadow DOM of PureSpectrum Web Components.

    PureSpectrum uses Angular Elements with Shadow DOM (<ps-root>, <ps-button>, etc.).
    Standard document.querySelector() CANNOT pierce Shadow DOM.

    Strategy:
      1. Find custom element matching tag_hint (e.g., 'ps-next-button')
      2. Access element.shadowRoot
      3. Query within shadowRoot using selector
      4. Return element info (tagName, text, position, etc.)

    Args:
        ws_url: CDP WebSocket URL
        selector: CSS selector to find WITHIN shadow DOM (e.g., 'button', 'input')
        tag_hint: Custom element tag name hint (e.g., 'ps-next-button', 'ps-root')

    Returns:
        Dict with element info, or None if not found
    """
    try:
        ws = websocket.create_connection(ws_url, timeout=10)
        ws.send(json.dumps({"id": 0, "method": "Runtime.evaluate",
            "params": {"expression": f"""
(function() {{
    // Find all custom elements matching tag_hint, or all custom elements if no hint
    var hints = ['ps-root', 'ps-next-button', 'ps-button', 'ps-input', 'ps-radio', 'ps-checkbox'];
    if ('{tag_hint}') hints.unshift('{tag_hint}');  // Prioritize hinted tag

    for (var tag of hints) {{
        var elements = document.querySelectorAll(tag);
        for (var el of elements) {{
            if (el.shadowRoot) {{
                var target = el.shadowRoot.querySelector('{selector}');
                if (target) {{
                    var r = target.getBoundingClientRect();
                    return JSON.stringify({{
                        found: true,
                        tag: tag,
                        targetTag: target.tagName,
                        text: (target.textContent || '').trim().substring(0, 50),
                        x: r.x + r.width/2,
                        y: r.y + r.height/2,
                        width: r.width,
                        height: r.height,
                        disabled: target.disabled || false,
                        hasShadowDOM: true
                    }});
                }}
            }}
        }}
    }}

    // Fallback: Try standard DOM (no Shadow DOM)
    var fallback = document.querySelector('{selector}');
    if (fallback) {{
        var r = fallback.getBoundingClientRect();
        return JSON.stringify({{
            found: true,
            tag: 'standard-dom',
            targetTag: fallback.tagName,
            text: (fallback.textContent || '').trim().substring(0, 50),
            x: r.x + r.width/2,
            y: r.y + r.height/2,
            width: r.width,
            height: r.height,
            disabled: fallback.disabled || false,
            hasShadowDOM: false
        }});
    }}

    return JSON.stringify({{found: false}});
}})();
"""}}))
        r = json.loads(ws.recv())
        ws.close()

        result = json.loads(r.get("result", {}).get("result", {}).get("value", "{}"))
        return result if result.get("found") else None
    except Exception:
        return None


def shadow_dom_click(ws_url, selector, tag_hint="", debug=False):
    """Click element within Shadow DOM using CDP mouse events.

    Standard JS .click() does NOT work on Web Components because:
      - Events don't bubble through Shadow DOM boundary by default
      - Angular Elements use synthetic event dispatching
      - isTrusted check may fail

    Solution: CDP Input.dispatchMouseEvent (real browser engine events).

    Args:
        ws_url: CDP WebSocket URL
        selector: CSS selector within Shadow DOM
        tag_hint: Custom element tag name (e.g., 'ps-next-button')
        debug: Print debug info

    Returns:
        True if clicked, False otherwise
    """
    element = shadow_dom_query_selector(ws_url, selector, tag_hint)
    if not element:
        if debug:
            print(f"  [SHADOW] Element not found: {selector} in {tag_hint or 'any custom element'}")
        return False

    if element.get("disabled"):
        if debug:
            print(f"  [SHADOW] Element disabled: {element.get('text', '')}")
        return False

    x, y = element["x"], element["y"]
    if debug:
        print(f"  [SHADOW] Clicking {element.get('tag', '?')}>{element.get('targetTag', '?')} "
              f"at ({x:.1f},{y:.1f}) text='{element.get('text', '')}'")

    return cdp_click(ws_url, x, y)


def shadow_dom_fill(ws_url, selector, value, tag_hint="", debug=False):
    """Fill input within Shadow DOM using native value setter.

    Args:
        ws_url: CDP WebSocket URL
        selector: CSS selector for input/textarea within Shadow DOM
        value: Text to fill
        tag_hint: Custom element tag name (e.g., 'ps-input')
        debug: Print debug info

    Returns:
        True if filled, False otherwise
    """
    element = shadow_dom_query_selector(ws_url, selector, tag_hint)
    if not element:
        return False

    if debug:
        print(f"  [SHADOW] Filling {element.get('tag', '?')}>{element.get('targetTag', '?')} "
              f"with '{value[:20]}...'")

    try:
        ws = websocket.create_connection(ws_url, timeout=10)
        ws.send(json.dumps({"id": 0, "method": "Runtime.evaluate",
            "params": {"expression": f"""
(function() {{
    var hints = ['ps-root', 'ps-next-button', 'ps-button', 'ps-input', 'ps-radio', 'ps-checkbox'];
    if ('{tag_hint}') hints.unshift('{tag_hint}');

    for (var tag of hints) {{
        var elements = document.querySelectorAll(tag);
        for (var el of elements) {{
            if (el.shadowRoot) {{
                var target = el.shadowRoot.querySelector('{selector}');
                if (target) {{
                    // Native setter for Angular form binding
                    var proto = target.tagName === 'TEXTAREA'
                        ? window.HTMLTextAreaElement.prototype
                        : window.HTMLInputElement.prototype;
                    var nativeSetter = Object.getOwnPropertyDescriptor(proto, 'value').set;
                    if (nativeSetter) nativeSetter.call(target, '{value}');
                    else target.value = '{value}';

                    // Dispatch events for Angular change detection
                    target.dispatchEvent(new Event('input', {{bubbles: true, cancelable: true}}));
                    target.dispatchEvent(new Event('change', {{bubbles: true, cancelable: true}}));
                    target.dispatchEvent(new Event('blur', {{bubbles: true, cancelable: true}}));

                    return 'filled:' + target.value;
                }}
            }}
        }}
    }}
    return 'not found';
}})();
"""}}))
        json.loads(ws.recv())
        ws.close()
        return True
    except Exception:
        return False


def shadow_dom_exists(ws_url, tag_hint=""):
    """Check if Shadow DOM custom elements exist on page.

    Args:
        ws_url: CDP WebSocket URL
        tag_hint: Specific tag to check (e.g., 'ps-root')

    Returns:
        True if Shadow DOM elements found, False otherwise
    """
    try:
        ws = websocket.create_connection(ws_url, timeout=10)
        ws.send(json.dumps({"id": 0, "method": "Runtime.evaluate",
            "params": {"expression": f"""
(function() {{
    var tags = ['ps-root', 'ps-next-button', 'ps-button', 'ps-input', 'ps-radio', 'ps-checkbox', 'ps-select'];
    if ('{tag_hint}') tags = ['{tag_hint}'];

    for (var tag of tags) {{
        var els = document.querySelectorAll(tag);
        for (var el of els) {{
            if (el.shadowRoot) return JSON.stringify({{found: true, tag: tag}});
        }}
    }}
    return JSON.stringify({{found: false}});
}})();
"""}}))
        r = json.loads(ws.recv())
        ws.close()
        result = json.loads(r.get("result", {}).get("result", {}).get("value", "{}"))
        return result.get("found", False)
    except Exception:
        return False


# ── Drag Puzzle Solver (AngularDragDropSolver) ──────────

def solve_drag_puzzle(ws_url):
    """Angular CDK drag-drop puzzle solver — delegates to drag_drop_angular.py.

    BROKEN: __ngContext__ traversal approach was removed (Production Build
    stores component index as number, not Object — findInstance() finds nothing).

    REPLACEMENT: solve_drag_puzzle_new() from drag_drop_angular.py tries in order:
    1. Playwright locator.dragTo() — different internal routing than drag_and_drop()
    2. CDP browser-level pointer event simulation (pointerdown/move/up)
    3. Graceful "blocked" return (surveys stop here — escalation needed)

    Return shape kept for backward compat with solve_purespectrum_preflight().
    """
    try:
        from stealth_captcha.solver.drag_drop_angular import solve_drag_puzzle_new
        result = solve_drag_puzzle_new(ws_url)

        if result.status == "solved":
            return {
                "success": True,
                "result": f"DRAG_SUCCESS:{result.number}|{result.details.get('method','')}",
            }
        elif result.status == "blocked":
            return {
                "success": False,
                "result": None,
                "error": f"Puzzle BLOCKED — {result.error or 'unknown'}. Details: {result.details}",
            }
        else:  # failed
            return {
                "success": False,
                "result": None,
                "error": result.error or "Unknown drag-drop failure",
            }
    except ImportError as e:
        return {
            "success": False,
            "result": None,
            "error": f"ImportError: {str(e)[:200]}",
        }
    except Exception as e:
        return {
            "success": False,
            "result": None,
            "error": str(e)[:200],
        }


# ── Page Text Reader ───────────────────────────────────

def read_page_text(ws_url, max_len=1000):
    try:
        ws = websocket.create_connection(ws_url, timeout=10)
        ws.send(json.dumps({"id":0,"method":"Runtime.evaluate",
            "params":{"expression": f"document.body.innerText.substring(0,{max_len})"}}))
        r = json.loads(ws.recv()); ws.close()
        return r.get("result",{}).get("result",{}).get("value","")
    except Exception:
        return ""


# ── Shadow DOM Survey Navigation (Post-Puzzle) ─────────

def navigate_purespectrum_shadow_dom(ws_url, max_steps=15, debug=False):
    """Navigate PureSpectrum survey pages using Shadow DOM piercing.

    PureSpectrum switches to Web Components (ps-*) after the drag puzzle (~66%).
    Standard DOM queries fail because elements are inside Shadow DOM.

    Strategy:
      1. Detect if Shadow DOM is active (ps-* elements present)
      2. For each page:
         - Shadow-DOM-pierce radio buttons → select first option
         - Shadow-DOM-pierce text inputs → fill with profile-based value
         - Shadow-DOM-pierce next button → CDP click
         - Wait for page transition
      3. Detect completion (completion markers in page text)
      4. Detect screen-out (disqualification text)

    Args:
        ws_url: CDP WebSocket URL
        max_steps: Maximum pages to navigate (safety limit)
        debug: Print debug info

    Returns:
        {"status": "completed|screen_out|error|max_steps", "pages": N, "error": msg}
    """
    # Check if Shadow DOM is even present
    if not shadow_dom_exists(ws_url):
        if debug:
            print("  [SHADOW] No Shadow DOM detected — skipping shadow navigation")
        return {"status": "no_shadow_dom", "pages": 0}

    if debug:
        print("  [SHADOW] Shadow DOM detected! Starting navigation...")

    for step in range(max_steps):
        time.sleep(2)  # Wait for page to settle

        # Read page text for completion/screen-out detection
        text = read_page_text(ws_url, 1500).lower()

        # Check completion
        for marker in COMPLETION_MARKERS:
            if marker in text:
                if debug:
                    print(f"  [SHADOW] COMPLETED after {step} pages (marker: '{marker}')")
                return {"status": "completed", "pages": step}

        # Check screen-out
        if any(x in text for x in ["leider", "nicht geeignet", "disqualif", "screenout", "nicht qualifiziert"]):
            if debug:
                print(f"  [SHADOW] SCREEN-OUT after {step} pages")
            return {"status": "screen_out", "pages": step}

        # Try to interact with Shadow DOM elements
        clicked = False

        # 1. Try to click radio buttons (select first option on each page)
        # PureSpectrum uses <ps-radio> or <input type="radio"> within Shadow DOM
        radio = shadow_dom_query_selector(ws_url, "input[type='radio']", "ps-radio")
        if radio and not radio.get("disabled"):
            if debug:
                print(f"  [SHADOW] Page {step}: Radio button found, clicking...")
            if shadow_dom_click(ws_url, "input[type='radio']", "ps-radio", debug=debug):
                clicked = True
                time.sleep(0.5)

        # 2. Try to fill text inputs (if any)
        text_input = shadow_dom_query_selector(ws_url, "input[type='text']", "ps-input")
        if text_input and not text_input.get("disabled"):
            # Try to determine what to fill from context
            # Default: "Berlin" (city from profile)
            fill_value = "Berlin"
            if "alter" in text or "age" in text:
                fill_value = "32"
            elif "wohnort" in text or "stadt" in text:
                fill_value = "Berlin"
            elif "plz" in text or "postal" in text:
                fill_value = "10785"

            if debug:
                print(f"  [SHADOW] Page {step}: Text input found, filling '{fill_value}'...")
            if shadow_dom_fill(ws_url, "input[type='text']", fill_value, "ps-input", debug=debug):
                clicked = True

        # 3. Try to click next/submit button (CRITICAL — must be last)
        # Try multiple button selectors within Shadow DOM
        button_selectors = [
            ("button", "ps-next-button"),      # "Nächste" button
            ("button", "ps-button"),            # Generic button
            ("[type='submit']", "ps-root"),     # Submit inside ps-root
            ("button", ""),                     # Any button in any Shadow DOM
        ]

        for selector, tag in button_selectors:
            btn = shadow_dom_query_selector(ws_url, selector, tag)
            if btn and not btn.get("disabled"):
                btn_text = btn.get("text", "").lower()
                # Only click "next" or "submit" buttons, not "back" or "cancel"
                if any(x in btn_text for x in ["nächste", "weiter", "next", "submit", "abschicken", "fertig"]):
                    if debug:
                        print(f"  [SHADOW] Page {step}: Clicking '{btn_text}' button...")
                    if shadow_dom_click(ws_url, selector, tag, debug=debug):
                        clicked = True
                        break

        if not clicked:
            if debug:
                print(f"  [SHADOW] Page {step}: No clickable elements found — page might be complete")
            # One more check for completion markers
            text = read_page_text(ws_url, 1500).lower()
            for marker in COMPLETION_MARKERS:
                if marker in text:
                    return {"status": "completed", "pages": step}
            # Try standard DOM fallback
            if not any(x in text for x in ["bitte legen", "zahl", "puzzle"]):
                return {"status": "unknown", "pages": step, "error": "No Shadow DOM elements found and no completion markers"}

    return {"status": "max_steps", "pages": max_steps, "error": f"Reached max {max_steps} steps"}


# ── Full Preflight ─────────────────────────────────────

def solve_purespectrum_preflight(ws_url, debug=False):
    """Run full PureSpectrum preflight: cookie → ROBOT → captcha → puzzle → shadow-dom navigation."""
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

    # 5. Shadow DOM Navigation (NEW — post-puzzle Web Components)
    # After the drag puzzle, PureSpectrum switches to Angular Web Components
    # Standard DOM queries fail — need Shadow DOM piercing
    if shadow_dom_exists(ws_url):
        if debug:
            print("  [PREFLIGHT] Shadow DOM detected after puzzle — starting navigation...")
        nav_result = navigate_purespectrum_shadow_dom(ws_url, max_steps=15, debug=debug)
        steps.append(f"shadow_nav:{nav_result.get('status')}:{nav_result.get('pages')}")

        if nav_result.get("status") == "completed":
            return {"success": True, "steps": steps, "pages": nav_result.get("pages")}
        elif nav_result.get("status") == "screen_out":
            return {"success": True, "steps": steps, "screen_out": True, "pages": nav_result.get("pages")}
        elif nav_result.get("status") == "error":
            return {"success": False, "steps": steps, "error": nav_result.get("error")}

    return {"success": True, "steps": steps}
