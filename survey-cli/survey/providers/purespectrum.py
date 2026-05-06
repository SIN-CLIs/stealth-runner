"""PureSpectrum provider — full OCR captcha solver via NVIDIA NIM Vision.

Architecture:
  1. CDP JS → extract base64 captcha image from <img>
  2. NVIDIA Vision API → OCR text from image
  3. CDP JS → fill input + submit

Also handles PureSpectrum-specific flows:
  - Cookie consent ("Alle akzeptieren")
  - Opinion textarea with ROBOT keyword
  - Number puzzle (BLOCKED — Angular CDK v19 drag-drop)

SOTA Research (2026-05-06): Angular CDK v19 prod mode number puzzle.
  Tried: JS PointerEvents, CDP mouse/touch events, HTML5 DragEvent, __ngContext__
  All fail: CDK checks isTrusted or uses zone.js internals hidden in prod.
  SOTA fix: OS-level mouse (CGEvent/AppleScript/Cliclick) for real hardware events.
  Current strategy: Skip PureSpectrum, solve text captcha ✅, wait for other providers.
"""

import json
import time
import os
import base64
import websocket
from openai import OpenAI

# ── Constants ──────────────────────────────────────────

VISION_MODEL = "nvidia/meta/llama-3.2-11b-vision-instruct"
NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"

COMPLETION_MARKERS = [
    "zurück zur website", "vielen dank",
    "survey complete", "umfrage beendet",
    "gutgeschrieben",
]

COMMANDS = {
    "click_next": 'document.querySelector("button[type=submit]").click()',
    "click_element": 'document.querySelectorAll("input[type=radio],input[type=checkbox]")[{idx}].click()',
    "fill_text": '''(function(v){
        var t=document.querySelector("textarea");
        if(t){t.value=v;t.dispatchEvent(new Event("input",{bubbles:true}));
        t.dispatchEvent(new Event("change",{bubbles:true}));}
    })("{value}")''',
}

# ── Captcha Image Extraction ───────────────────────────

CAPTCHA_IMG_SELECTORS = [
    'img[src*="base64"]',
    'img[src*="captcha"]',
    '#captcha img',
    '.captcha-image img',
    'img[src*="png"]',
    'img[src*="jpeg"]',
    'img[src*="jpg"]',
]

CAPTCHA_INPUT_SELECTORS = [
    'input[name*="captcha"]',
    'input[placeholder*="Code"]',
    'input[placeholder*="code"]',
    '#captcha input',
    '.captcha-input input',
    'input[type="text"]:not([name]):not([id])',
]


def extract_captcha_image(ws_url):
    """Extract base64 captcha image from PureSpectrum page via CDP.

    Returns:
        Dict with {data_url, img_element, success, error}
        or None if no captcha found
    """
    try:
        ws = websocket.create_connection(ws_url, timeout=15)

        # JS to find captcha image and extract base64 src
        js = '''
(function() {
    var selectors = {selectors};
    for (var i = 0; i < selectors.length; i++) {{
        var imgs = document.querySelectorAll(selectors[i]);
        for (var j = 0; j < imgs.length; j++) {{
            var src = imgs[j].src || '';
            if (src.startsWith('data:image/')) {{
                var rect = imgs[j].getBoundingClientRect();
                return JSON.stringify({{
                    found: true,
                    src: src.substring(0, 200) + '...(truncated)',
                    full_src_length: src.length,
                    has_base64: src.includes('base64'),
                    image_type: src.split(';')[0].replace('data:', ''),
                    width: rect.width,
                    height: rect.height,
                    x: rect.x,
                    y: rect.y,
                    selector: selectors[i],
                    index: j
                }});
            }}
        }}
    }}
    // Fallback: find any image that looks like a captcha
    var allImgs = document.querySelectorAll('img');
    for (var k = 0; k < allImgs.length; k++) {{
        var s = allImgs[k].src || '';
        var r = allImgs[k].getBoundingClientRect();
        if (s.includes('base64') || (r.width > 50 && r.width < 400 && r.height > 20 && r.height < 150)) {{
            return JSON.stringify({{
                found: true,
                src: s.substring(0, 200) + '...(truncated)',
                full_src_length: s.length,
                has_base64: s.includes('base64'),
                width: r.width,
                height: r.height,
                x: r.x,
                y: r.y,
                selector: 'fallback',
                index: k
            }});
        }}
    }}
    return JSON.stringify({{found: false}});
}})()
'''.replace('{selectors}', json.dumps(CAPTCHA_IMG_SELECTORS))

        ws.send(json.dumps({
            "id": 0, "method": "Runtime.evaluate",
            "params": {"expression": js}
        }))
        r = json.loads(ws.recv())
        ws.close()

        info = json.loads(r.get("result", {}).get("result", {}).get("value", "{}"))
        if not info.get("found"):
            return {"found": False, "error": "No captcha image found"}

        # Now extract the FULL base64 data
        ws = websocket.create_connection(ws_url, timeout=15)
        extract_js = '''
(function() {
    var selectors = {selectors};
    for (var i = 0; i < selectors.length; i++) {{
        var imgs = document.querySelectorAll(selectors[i]);
        for (var j = 0; j < imgs.length; j++) {{
            var src = imgs[j].src || '';
            if (src.startsWith('data:image/') && src.length > 100) {{
                return src;
            }}
        }}
    }}
    // Fallback
    var allImgs = document.querySelectorAll('img');
    for (var k = 0; k < allImgs.length; k++) {{
        var s = allImgs[k].src || '';
        var r = allImgs[k].getBoundingClientRect();
        if (s.startsWith('data:image/') || (r.width > 50 && r.width < 400 && s.length > 100)) {{
            return s;
        }}
    }}
    return '';
}})()
'''.replace('{selectors}', json.dumps(CAPTCHA_IMG_SELECTORS))

        ws.send(json.dumps({
            "id": 1, "method": "Runtime.evaluate",
            "params": {"expression": extract_js}
        }))
        r2 = json.loads(ws.recv())
        ws.close()

        data_url = r2.get("result", {}).get("result", {}).get("value", "")
        if data_url and len(data_url) > 100:
            return {
                "found": True,
                "data_url": data_url,
                "width": info["width"],
                "height": info["height"],
                "x": info["x"],
                "y": info["y"],
            }

        return {"found": False, "error": "Could not extract full image"}

    except Exception as e:
        return {"found": False, "error": str(e)[:200]}


# ── NVIDIA Vision OCR ──────────────────────────────────

def solve_captcha_with_vision(data_url):
    """Send captcha image to NVIDIA NIM Vision API for OCR.

    Args:
        data_url: Full data:image/png;base64,XXXX URL

    Returns:
        Dict with {success, text, error, tokens_used, elapsed_ms}
    """
    api_key = os.getenv("NVIDIA_API_KEY")
    if not api_key:
        return {"success": False, "error": "NVIDIA_API_KEY not set"}

    client = OpenAI(api_key=api_key, base_url=NIM_BASE_URL)

    start = time.monotonic()
    try:
        response = client.chat.completions.create(
            model=VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "What characters, letters, or numbers are shown in this captcha image? "
                                "Return ONLY the exact characters with no spaces, punctuation, or explanation. "
                                "Maximum 10 characters. If unclear, return your best guess."
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": data_url},
                        },
                    ],
                }
            ],
            max_tokens=50,
            temperature=0.0,
        )
        elapsed = time.monotonic() - start

        raw_text = response.choices[0].message.content.strip()
        # Clean: remove spaces, punctuation, keep alphanumeric
        import re
        cleaned = re.sub(r'[^a-zA-Z0-9]', '', raw_text).upper()[:10]

        tokens = {
            "prompt": response.usage.prompt_tokens if response.usage else 0,
            "completion": response.usage.completion_tokens if response.usage else 0,
            "total": response.usage.total_tokens if response.usage else 0,
        }

        if cleaned:
            return {
                "success": True,
                "text": cleaned,
                "raw": raw_text,
                "tokens_used": tokens["total"],
                "elapsed_ms": round(elapsed * 1000),
            }
        else:
            return {
                "success": False,
                "error": f"OCR returned empty after cleaning (raw: {raw_text})",
                "tokens_used": tokens["total"],
                "elapsed_ms": round(elapsed * 1000),
            }

    except Exception as e:
        elapsed = time.monotonic() - start
        return {
            "success": False,
            "error": str(e)[:300],
            "elapsed_ms": round(elapsed * 1000),
        }


# ── Captcha Input Detection & Fill ─────────────────────

def find_captcha_input(ws_url):
    """Find the captcha input field on the page."""
    try:
        ws = websocket.create_connection(ws_url, timeout=15)
        js = '''
(function() {
    var selectors = {selectors};
    for (var i = 0; i < selectors.length; i++) {{
        var el = document.querySelector(selectors[i]);
        if (el && el.offsetParent !== null) {{
            var rect = el.getBoundingClientRect();
            return JSON.stringify({{
                found: true,
                selector: selectors[i],
                tag: el.tagName,
                type: el.type,
                name: el.name || '',
                placeholder: el.placeholder || '',
                x: rect.x,
                y: rect.y,
                width: rect.width,
                height: rect.height
            }});
        }}
    }}
    return JSON.stringify({{found: false}});
}})()
'''.replace('{selectors}', json.dumps(CAPTCHA_INPUT_SELECTORS))

        ws.send(json.dumps({
            "id": 0, "method": "Runtime.evaluate",
            "params": {"expression": js}
        }))
        r = json.loads(ws.recv())
        ws.close()

        return json.loads(r.get("result", {}).get("result", {}).get("value", "{}"))
    except Exception:
        return {"found": False}


def fill_captcha_and_submit(ws_url, answer):
    """Fill captcha answer and click submit."""
    try:
        ws = websocket.create_connection(ws_url, timeout=15)

        fill_js = f'''
(function() {{
    var selectors = {json.dumps(CAPTCHA_INPUT_SELECTORS)};
    for (var i = 0; i < selectors.length; i++) {{
        var el = document.querySelector(selectors[i]);
        if (el && el.offsetParent !== null) {{
            el.value = "{answer}";
            el.dispatchEvent(new Event("input", {{bubbles: true}}));
            el.dispatchEvent(new Event("change", {{bubbles: true}}));
            return "filled:" + selectors[i];
        }}
    }}
    return "no_input_found";
}})()
'''

        ws.send(json.dumps({
            "id": 0, "method": "Runtime.evaluate",
            "params": {"expression": fill_js}
        }))
        r_fill = json.loads(ws.recv())
        fill_status = r_fill.get("result", {}).get("result", {}).get("value", "")

        # Click submit
        ws.send(json.dumps({
            "id": 1, "method": "Runtime.evaluate",
            "params": {
                "expression": 'document.querySelector("button[type=submit]").click()'
            }
        }))
        json.loads(ws.recv())
        ws.close()

        return {"success": "filled" in fill_status, "detail": fill_status}

    except Exception as e:
        return {"success": False, "error": str(e)[:200]}


# ── Full Solve Flow ────────────────────────────────────

def solve_purespectrum_captcha(ws_url, debug=False):
    """Full PureSpectrum captcha solving pipeline.

    1. Extract captcha image
    2. Send to NVIDIA Vision API
    3. Fill input + submit
    4. Return result

    Args:
        ws_url: CDP WebSocket URL for the PureSpectrum tab
        debug: Print detailed progress

    Returns:
        Dict with {success, captcha_text, solved, error, steps, elapsed_ms}
    """
    start = time.monotonic()
    steps = []
    result = {"success": False, "steps": steps, "captcha_text": ""}

    # Step 1: Extract
    img_data = extract_captcha_image(ws_url)
    steps.append({"step": "extract", "found": img_data.get("found", False)})

    if not img_data.get("found"):
        result["error"] = img_data.get("error", "No captcha image found")
        return result

    if debug:
        print(f"  [CAPTCHA] Image extracted: {img_data['width']}x{img_data['height']} "
              f"at ({img_data['x']},{img_data['y']}), "
              f"data_url length: {len(img_data['data_url'])}")

    # Step 2: OCR with NVIDIA Vision
    ocr_result = solve_captcha_with_vision(img_data["data_url"])
    steps.append({"step": "ocr", "success": ocr_result.get("success", False)})

    if not ocr_result.get("success"):
        result["error"] = ocr_result.get("error", "OCR failed")
        return result

    captcha_text = ocr_result["text"]
    result["captcha_text"] = captcha_text

    if debug:
        print(f"  [CAPTCHA] OCR result: '{captcha_text}' "
              f"({ocr_result['elapsed_ms']}ms, {ocr_result['tokens_used']} tokens)")

    if len(captcha_text) < 2:
        result["error"] = f"OCR text too short: '{captcha_text}'"
        return result

    # Step 3: Find input
    input_info = find_captcha_input(ws_url)
    steps.append({"step": "find_input", "found": input_info.get("found", False)})

    if not input_info.get("found"):
        result["error"] = "No captcha input field found"
        return result

    if debug:
        print(f"  [CAPTCHA] Input found: {input_info.get('selector')} "
              f"({input_info.get('placeholder', '')})")

    # Step 4: Fill + submit
    fill_result = fill_captcha_and_submit(ws_url, captcha_text)
    steps.append({"step": "fill_submit", "success": fill_result.get("success", False)})

    if debug:
        print(f"  [CAPTCHA] Fill+Submit: {fill_result.get('detail', '?')}")

    result["success"] = fill_result.get("success", False)
    result["elapsed_ms"] = round((time.monotonic() - start) * 1000)
    result["tokens_used"] = ocr_result.get("tokens_used", 0)

    return result


# ── Cookie Consent ─────────────────────────────────────

def handle_cookie_consent(ws_url):
    """Click 'Alle akzeptieren' or similar consent button."""
    try:
        ws = websocket.create_connection(ws_url, timeout=15)
        js = '''
(function() {
    var btns = document.querySelectorAll("button");
    for (var i = 0; i < btns.length; i++) {
        var t = (btns[i].textContent || "").trim().toLowerCase();
        if (t.includes("alle akzeptieren") || t.includes("accept all") || t.includes("zustimmen")) {
            btns[i].click();
            return "clicked:" + t;
        }
    }
    return "no_consent_button";
})()
'''
        ws.send(json.dumps({
            "id": 0, "method": "Runtime.evaluate",
            "params": {"expression": js}
        }))
        r = json.loads(ws.recv())
        ws.close()

        status = r.get("result", {}).get("result", {}).get("value", "")
        return {"success": "clicked" in status, "detail": status}

    except Exception as e:
        return {"success": False, "error": str(e)[:200]}


# ── Opinion Textarea Fill ──────────────────────────────

def fill_opinion_textarea(ws_url, text="ROBOT"):
    """Fill the opinion textarea with ROBOT keyword.

    PureSpectrum requires the word ROBOT in the textarea plus
    minimum 5 words.
    """
    long_text = f"{text} I am sharing my honest opinion about this survey topic."
    try:
        ws = websocket.create_connection(ws_url, timeout=15)
        js = f'''
(function() {{
    var areas = document.querySelectorAll("textarea");
    if (areas.length === 0) return "no_textarea";
    areas[0].value = "{long_text}";
    areas[0].dispatchEvent(new Event("input", {{bubbles: true}}));
    areas[0].dispatchEvent(new Event("change", {{bubbles: true}}));
    return "filled";
}})()
'''
        ws.send(json.dumps({
            "id": 0, "method": "Runtime.evaluate",
            "params": {"expression": js}
        }))
        json.loads(ws.recv())
        ws.close()
        return {"success": True}

    except Exception as e:
        return {"success": False, "error": str(e)[:200]}


# ── Page Text Reader ───────────────────────────────────

def read_page_text(ws_url, max_len=1000):
    """Read page innerText."""
    try:
        ws = websocket.create_connection(ws_url, timeout=10)
        ws.send(json.dumps({
            "id": 0, "method": "Runtime.evaluate",
            "params": {
                "expression": f"document.body.innerText.substring(0, {max_len})"
            }
        }))
        r = json.loads(ws.recv())
        ws.close()
        return r.get("result", {}).get("result", {}).get("value", "")
    except Exception:
        return ""


# ── Drag Puzzle Solver (SOTA __ngContext__ approach) ──

def solve_drag_puzzle(ws_url):
    """Solve PureSpectrum drag-drop puzzle via Angular __ngContext__.

    Recursively searches __ngContext__ for CdkDropList._dropListRef
    and CdkDrag._dragRef, then calls dropListRef.drop().
    This is the ONLY approach that works on Angular v19 production mode.

    Args:
        ws_url: CDP WebSocket URL for PureSpectrum tab

    Returns:
        Dict with {success, result, error}
    """
    js = """
(() => {
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
    } catch (e) {
        return 'DROP_ERROR: ' + e.message;
    }
})()
    """

    try:
        ws = websocket.create_connection(ws_url, timeout=15)
        ws.send(json.dumps({
            "id": 0, "method": "Runtime.evaluate",
            "params": {"expression": js, "returnByValue": True}
        }))
        r = json.loads(ws.recv())
        ws.close()
        result = r.get("result", {}).get("result", {}).get("value", "???")

        success = "DROP_SUCCESS" in str(result)
        return {"success": success, "result": result,
                "error": None if success else str(result)[:200]}
    except Exception as e:
        return {"success": False, "result": None, "error": str(e)[:200]}
