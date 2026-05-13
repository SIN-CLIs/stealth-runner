#!/usr/bin/env python3
"""
================================================================================
ANSWER_SURVEY — Universal Survey Answer Tool (MANUAL TESTING ONLY!)
================================================================================

WAS DAS TUT:
  Nimmt einen Survey-Tab WS URL und beantwortet EINE Seite nach der anderen.
  Erkennt universal: Consent, Fragen, Completion, Screen-Out.
  
  **DIES IST KEIN AUTO-RUN TOOL!**
  **FÜR MANUELLE TESTING — eine Seite nach der anderen, jeder Schritt verifiziert!**

FLOW (pro Seite):
  1. snapshot()      → Alle Elemente via CDP EXTRACTOR_JS (100% reliable)
  2. detect_page()   → Consent / Questions / Completion / Screen-Out
  3. answer_page()   → Universal answer logic (kein provider Hardcode!)
  4. click_submit()  → Submit/Next/Continue Button klicken
  5. detect_done()   → Survey komplett?
  6. repeat bis done → Maximum 30 Seiten, dann STOP

BEFOLGT:
  ✓ tool_snapshot.py (EXTRACTOR_JS) — 100% reliable element capture via CDP
  ✓ commands/surveys/survey-answer-patterns.md — verifizierte CDP JS patterns
  ✓ completion_detector.py — completion/screen-out detection
  ✓ Kein skylight-cli (NICHT IN BENUTZUNG!)
  ✓ Kein cua-driver (DEPRECATED, nur Popups)
  ✓ Kein auto-run (MANUAL TESTING ONLY)

VERIFIZIERTE PATTERNS (aus commands/surveys/survey-answer-patterns.md):
  - Radio Button: input[type=radio] -> checked + dispatchEvent(change)
  - Checkbox: input[type=checkbox] -> click() 
  - Text Input: value setzen + dispatchEvent(input + change)
  - Submit: document.querySelector("form").submit() ODER Button klicken
  - Click by Text: textContent === "Text" -> click()
  - Qualtrics: .NextButton.click()

BANNED:
  ❌ playstealth launch
  ❌ webauto-nodriver
  ❌ skylight-cli (NICHT BENUTZT!)
  ❌ cua-driver (nur Popups/Sheets)
  ❌ pkill -f "Google Chrome"
  ❌ Hardcoded PIDs

================================================================================"""

import asyncio
import json
import os
import subprocess
import time
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

# ═════════════════════════════════════════════════════════════════════════════
# IMPORTS — vorhandene tools nutzen
# ═════════════════════════════════════════════════════════════════════════════
sys_path = "/Users/jeremy/dev/stealth-runner/survey-cli"
import sys
sys.path.insert(0, sys_path)

from tools.tool_snapshot import EXTRACTOR_JS, snapshot, find_submit, find_unfilled
from survey.completion_detector import CompletionDetector
from survey.session_validator import validate_session

CHROME_PORT = 9999
REGISTRY_PATH = "/Users/jeremy/dev/stealth-runner/survey-cli/data/command_registry.json"
MAX_PAGES = 30  # Safety: Max Seiten pro Survey
STUCK_THRESHOLD = 3  # Wenn DOM-Hash 3x gleich = stuck!


# ═════════════════════════════════════════════════════════════════════════════
# VERIFIZIERTE CDP JS PATTERNS (aus commands/surveys/survey-answer-patterns.md)
# ═════════════════════════════════════════════════════════════════════════════

CDP_RADIO_JS = """
(function() {
    var r = document.querySelectorAll('input[type=radio]');
    if(r.length > 0) {
        // Mitte wählen (Index = floor(length/2) → neutral)
        var idx = Math.floor(r.length / 2);
        r[idx].checked = true;
        r[idx].dispatchEvent(new Event('change', {bubbles: true}));
        return 'RADIO:' + (r[idx].parentElement ? r[idx].parentElement.textContent.trim().substring(0, 30) : r[idx].name);
    }
    return 'NO_RADIO';
})()
"""

CDP_CHECKBOX_JS = """
(function() {
    var c = document.querySelectorAll('input[type=checkbox]:not(:checked)');
    var count = Math.min(c.length, 4); // Click up to 4 checkboxes for multi-select
    var clicked = [];
    for(var i = 0; i < count; i++) {
        c[i].checked = true;
        c[i].dispatchEvent(new Event('change', {bubbles: true}));
        c[i].dispatchEvent(new Event('click', {bubbles: true}));
        var lbl = c[i].closest('label');
        clicked.push(lbl ? lbl.textContent.trim().substring(0, 30) : c[i].value);
    }
    if(clicked.length > 0) return 'CHECKED:' + clicked.join(',');
    // Falls alles checked, toggle ein par aus/an
    var all = document.querySelectorAll('input[type=checkbox]');
    if(all.length > 1) {
        all[1].click();
        var lbl = all[1].closest('label');
        return 'TOGGLED:' + (lbl ? lbl.textContent.trim().substring(0, 30) : all[1].value);
    }
    return 'NO_CHECKBOX';
})()
"""

CDP_TEXT_JS = """
(function() {
    var inputs = document.querySelectorAll('input[type=text], input[type=number], input[type=email], input[type=tel]');
    for(var i = 0; i < inputs.length; i++) {
        var r = inputs[i].getBoundingClientRect();
        // Nur sichtbare Inputs unterhalb des Headers (y > 200)
        if(r.top > 200 && r.width > 50) {
            // Placeholder-basiert填 fill pattern
            var ph = (inputs[i].placeholder || '').toLowerCase();
            var name = (inputs[i].name || '').toLowerCase();
            var val = '';
            if(ph.includes('plz') || name.includes('plz') || name.includes('postal') || name.includes('zip')) {
                val = '10785'; // Berlin PLZ
            } else if(ph.includes('alter') || name.includes('age') || name.includes('jahr')) {
                val = '32'; // Alter
            } else if(ph.includes('email')) {
                val = 'jeremy@test.de';
            } else if(ph.includes('name') && name.includes('first')) {
                val = 'Jeremy';
            } else if(ph.includes('name') && name.includes('last')) {
                val = 'Schulze';
            } else {
                val = 'Test'; // Default
            }
            inputs[i].value = val;
            inputs[i].dispatchEvent(new Event('input', {bubbles: true}));
            inputs[i].dispatchEvent(new Event('change', {bubbles: true}));
            return 'TEXT:' + val;
        }
    }
    return 'NO_TEXT';
})()
"""

CDP_TEXTAREA_JS = """
(function() {
    var t = document.querySelector('textarea');
    if(t) {
        t.value = 'Keine weiteren Anmerkungen.';
        t.dispatchEvent(new Event('input', {bubbles: true}));
        t.dispatchEvent(new Event('change', {bubbles: true}));
        return 'TEXTAREA_OK';
    }
    return 'NO_TEXTAREA';
})()
"""

CDP_SUBMIT_JS = """
(function() {
    // Variante 1: Form submit
    var f = document.querySelector('form');
    if(f) { f.submit(); return 'SUBMIT_FORM'; }
    // Variante 2: NextButton (Qualtrics)
    var nb = document.querySelector('.NextButton, .btn-next, [class*=NextButton]');
    if(nb) { nb.click(); return 'NEXT_BTN'; }
    // Variante 3: Button mit German/French/English navigation text
    var patterns = [
        /^N[äa]chste$/i, /^Weiter$/i, /^Next$/i, /^Continue$/i,
        /^Submit$/i, /^Survey fortf/i, /^Teilnehmen$/i, /^Start$/i,
        /^Suivant$/i, /^Continuer$/i, /^Envoyer$/i
    ];
    var btns = document.querySelectorAll('button, a[href]');
    for(var i = 0; i < btns.length; i++) {
        var t = btns[i].textContent.trim();
        for(var p = 0; p < patterns.length; p++) {
            if(t.match(patterns[p])) {
                btns[i].click();
                return 'CLICKED:' + t;
            }
        }
    }
    return 'NO_SUBMIT';
})()
"""

CDP_CLICK_BY_TEXT_JS = """
(function(text) {
    var all = document.querySelectorAll('button, a, [role=button], input[type=submit]');
    for(var i = 0; i < all.length; i++) {
        var elText = (all[i].textContent || '').trim();
        // EXAKTE MATCH first, dann PARTIAL MATCH
        if(elText === text || elText.includes(text) || text.includes(elText)) {
            all[i].click();
            return 'CLICKED:' + elText;
        }
    }
    return 'NOT_FOUND:' + text;
})
"""


# ═════════════════════════════════════════════════════════════════════════════
# CAPTCHA SOLVER — PureSpectrum Visual Captcha via Llama 90B (NVIDIA NIM)
# ═════════════════════════════════════════════════════════════════════════════

async def solve_captcha(ws) -> str:
    """Detect and solve PureSpectrum captchas (ROBOT text + visual image).
    
    Strategy:
    - ROBOT captcha: type "ROBOT" in input field + click Nächste
    - Visual captcha: extract base64 PNG, send to Llama 90B, type result + click Nächste
    
    Model: meta/llama-3.2-90b-vision-instruct (NVIDIA NIM)
    API: https://integrate.api.nvidia.com/v1/chat/completions
    """
    import os, base64, urllib.request
    
    # Get page text to detect captcha type
    page_text = await cdp_execute_js(ws, 100, "document.body.innerText.substring(0, 500)")
    
    if "ROBOT" in page_text.upper() or "ich bin kein roboter" in page_text.lower():
        # ROBOT text captcha
        await cdp_execute_js(ws, 101, """
(function(){
    var inp = document.querySelector('input[type=text], input[type=password], textarea');
    if(inp) {
        inp.value = 'ROBOT';
        inp.dispatchEvent(new Event('input', {bubbles: true}));
        inp.dispatchEvent(new Event('change', {bubbles: true}));
        return 'ROBOT_FILLED';
    }
    // Try by placeholder
    var inputs = document.querySelectorAll('input');
    for(var i = 0; i < inputs.length; i++) {
        var ph = (inputs[i].placeholder || '').toLowerCase();
        if(ph.includes('robot') || ph.includes('best') || ph.includes('code')) {
            inputs[i].value = 'ROBOT';
            inputs[i].dispatchEvent(new Event('input', {bubbles: true}));
            return 'ROBOT_FILLED_BY_PLACEHOLDER';
        }
    }
    return 'ROBOT_INPUT_NOT_FOUND';
})()
""")
        await asyncio.sleep(0.5)
        await cdp_execute_js(ws, 102, """
(function(){
    var b = [...document.querySelectorAll('button')].find(function(b){
        return b.innerText.includes('N') && b.innerText.includes('chste');
    });
    if(b) { b.click(); return 'CLICKED:' + b.innerText; }
    return 'NOT_FOUND';
})()
""")
        await asyncio.sleep(3)
        return "ROBOT_SOLVED"
    
    # Visual captcha: extract base64 image
    captcha_data = await cdp_execute_js(ws, 110, """
(function(){
    // Find captcha image (base64 PNG)
    var imgs = document.querySelectorAll('img');
    for(var i = 0; i < imgs.length; i++) {
        var src = imgs[i].src;
        if(src.startsWith('data:image')) return src;
    }
    // Try to get from canvas
    var canvases = document.querySelectorAll('canvas');
    if(canvases.length > 0) return 'canvas:' + canvases[0].toDataURL('image/png');
    return 'NO_CAPTCHA_IMAGE';
})()
""")
    
    if not captcha_data or captcha_data == "NO_CAPTCHA_IMAGE" or not captcha_data.startswith("data:image"):
        return "CAPTCHA_NO_IMAGE"
    
    # Extract base64 and call Llama 90B
    try:
        b64 = captcha_data.split(",")[1] if "," in captcha_data else captcha_data.split("data:image/png;base64,")[1]
        img_bytes = base64.b64decode(b64)
    except Exception as e:
        return f"CAPTCHA_DECODE_ERROR:{e}"
    
    # Call NVIDIA NIM with Llama 90B Vision
    img_b64 = base64.b64encode(img_bytes).decode()
    payload = {
        "model": "meta/llama-3.2-90b-vision-instruct",
        "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
            {"type": "text", "text": "The image shows a CAPTCHA code. Read and return ONLY the characters shown, nothing else. Example: ABC123"}
        ]}],
        "max_tokens": 20
    }
    
    try:
        req = urllib.request.Request(
            "https://integrate.api.nvidia.com/v1/chat/completions",
            data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {os.environ['NVIDIA_API_KEY']}", "Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            code = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            if not code:
                # Try with 11B model as fallback
                payload["model"] = "meta/llama-3.2-11b-vision-instruct"
                req2 = urllib.request.Request(
                    "https://integrate.api.nvidia.com/v1/chat/completions",
                    data=json.dumps(payload).encode(),
                    headers={"Authorization": f"Bearer {os.environ['NVIDIA_API_KEY']}", "Content-Type": "application/json"},
                    method="POST"
                )
                with urllib.request.urlopen(req2, timeout=30) as resp2:
                    result2 = json.loads(resp2.read())
                    code = result2.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    except Exception as e:
        return f"CAPTCHA_API_ERROR:{e}"
    
    if not code:
        return "CAPTCHA_API_EMPTY"
    
    # Fill captcha and click Nächste
    await cdp_execute_js(ws, 120, f"""
(function(){{
    var inp = document.querySelector('input[type=text], textarea');
    if(!inp) {{ 
        // Try all inputs
        var inputs = document.querySelectorAll('input');
        for(var i = 0; i < inputs.length; i++) {{
            if(inputs[i].type !== 'checkbox' && inputs[i].type !== 'radio' && inputs[i].type !== 'hidden') {{
                inp = inputs[i]; break;
            }}
        }}
    }}
    if(inp) {{
        inp.value = '{code}';
        inp.dispatchEvent(new Event('input', {{bubbles: true}}));
        inp.dispatchEvent(new Event('change', {{bubbles: true}}));
        return 'FILLED:' + inp.value;
    }}
    return 'INPUT_NOT_FOUND';
}})()
""")
    await asyncio.sleep(0.5)
    
    await cdp_execute_js(ws, 121, """
(function(){
    var b = [...document.querySelectorAll('button')].find(function(b){
        return b.innerText.includes('N') && b.innerText.includes('chste');
    });
    if(b) { b.click(); return 'CLICKED:' + b.innerText; }
    return 'NOT_FOUND';
})()
""")
    
    await asyncio.sleep(3)
    return f"CAPTCHA_SOLVED:{code}"


# ═════════════════════════════════════════════════════════════════════════════
# DRAG-DROP SOLVER — PureSpectrum Angular CDK Puzzle (66%)
# ═════════════════════════════════════════════════════════════════════════════

async def solve_drag_drop(ws) -> str:
    """Solve PureSpectrum "Zahl X" Angular CDK drag-drop puzzle.
    
    Uses CDP Input.dispatchMouseEvent (Approach B) — REAL browser-level mouse events
    trigger Angular CDK's pointer event handlers. Verified working 2026-05-10.
    """
    import time
    
    # Extract target number
    number = await cdp_execute_js(ws, 200, """
(function(){
    var t = document.body.innerText;
    var m = t.match(/Bitte legen Sie die Zahl (\\d+)/);
    return m ? m[1] : null;
})()
""")
    
    if not number:
        return "DRAG_NO_NUMBER"
    
    # Get element positions
    coords = await cdp_execute_js(ws, 201, f"""
(function(){{
    var img = document.querySelector('img[alt="{number}"]');
    var dropZones = document.querySelectorAll('.cdk-drop-list');
    var dropZone = dropZones.length > 1 ? dropZones[1] : document.querySelector('.drop-zone');
    if(!img || !dropZone) return JSON.stringify({{error:'MISSING'}});
    var r1 = img.getBoundingClientRect();
    var r2 = dropZone.getBoundingClientRect();
    return JSON.stringify({{
        sx: r1.left + r1.width/2,
        sy: r1.top + r1.height/2,
        ex: r2.left + r2.width/2,
        ey: r2.top + r2.height/2
    }});
}})()
""")
    
    try:
        pos = json.loads(coords)
    except:
        return f"DRAG_PARSE_ERROR:{coords}"
    
    if pos.get("error"):
        return f"DRAG_ERROR:{pos['error']}"
    
    sx, sy = pos["sx"], pos["sy"]
    ex, ey = pos["ex"], pos["ey"]
    
    # Enable Input domain
    await ws.send(json.dumps({"id": 202, "method": "Input.enable"}))
    await asyncio.wait_for(ws.recv(), timeout=5)
    
    # mousePressed
    await ws.send(json.dumps({"id": 203, "method": "Input.dispatchMouseEvent",
        "params": {"type": "mousePressed", "x": sx, "y": sy, "button": "left", "clickCount": 1}}))
    await asyncio.wait_for(ws.recv(), timeout=5)
    await asyncio.sleep(0.3)
    
    # 10-step mouseMoved with arc
    for i in range(1, 11):
        t = i / 10
        ix = sx + (ex - sx) * t
        iy = sy + (ey - sy) * t
        arc_off = 20 * (1 - abs(2 * t - 1))
        iy -= arc_off
        await ws.send(json.dumps({"id": 203 + i, "method": "Input.dispatchMouseEvent",
            "params": {"type": "mouseMoved", "x": ix, "y": iy, "button": "left"}}))
        await asyncio.wait_for(ws.recv(), timeout=5)
        await asyncio.sleep(0.05)
    
    await asyncio.sleep(0.3)
    
    # mouseReleased
    await ws.send(json.dumps({"id": 220, "method": "Input.dispatchMouseEvent",
        "params": {"type": "mouseReleased", "x": ex, "y": ey, "button": "left", "clickCount": 1}}))
    await asyncio.wait_for(ws.recv(), timeout=5)
    
    await asyncio.sleep(2)
    
    # Verify and click Nächste
    verify = await cdp_execute_js(ws, 221, """
(function(){
    var dz = document.querySelectorAll('.cdk-drop-list');
    var tz = dz.length > 1 ? dz[1] : null;
    var child = tz ? tz.querySelector('img') : null;
    var btn = [...document.querySelectorAll('button')].find(function(b){
        return b.innerText.includes('N') && b.innerText.includes('chste');
    });
    return JSON.stringify({
        dropzoneHasImg: !!child,
        imgAlt: child ? child.getAttribute('alt') : null,
        btnDisabled: btn ? btn.disabled : null
    });
})()
""")
    
    try:
        v = json.loads(verify)
        if v.get("btnDisabled") is False:
            await cdp_execute_js(ws, 222, """
(function(){
    var b = [...document.querySelectorAll('button')].find(function(b){
        return b.innerText.includes('N') && b.innerText.includes('chste');
    });
    if(b) { b.click(); return 'CLICKED:' + b.innerText; }
    return 'NOT_FOUND';
})()
""")
            await asyncio.sleep(3)
            return f"DRAG_SOLVED:{number}->btn_enabled"
        return f"DRAG_FAILED:btn_disabled"
    except:
        return f"DRAG_VERIFY_ERROR:{verify}"


# ═════════════════════════════════════════════════════════════════════════════
# HELPER: CDP execute (async, mit event drain)
# ═════════════════════════════════════════════════════════════════════════════

async def cdp_eval(ws, msg_id, expression, timeout=15):
    """CDP Runtime.evaluate + response empfangen (ignoriert events)."""
    await ws.send(json.dumps({"id": msg_id, "method": "Runtime.evaluate", "params": {"expression": expression}}))
    deadline = asyncio.get_running_loop().time() + timeout
    for _ in range(200):
        remaining = max(0.1, deadline - asyncio.get_running_loop().time())
        if remaining <= 0:
            return None
        try:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=remaining))
            if msg.get("id") == msg_id:
                return msg
        except asyncio.TimeoutError:
            return None
    return None


async def cdp_execute_js(ws, msg_id, expression, timeout=20) -> str:
    """Fuehre JS aus, returne result value als String."""
    msg = await cdp_eval(ws, msg_id, expression, timeout)
    if msg:
        val = msg.get("result", {}).get("result", {}).get("value", "")
        return str(val) if val is not None else ""
    return ""


# ═════════════════════════════════════════════════════════════════════════════
# PAGE TYPE DETECTION
# ═════════════════════════════════════════════════════════════════════════════

def detect_page_type(snap: Dict) -> str:
    """
    Erkennt Seitentyp anhand bodyText + URL.
    
    Returns:
        "consent"    → Cookie/Privacy Banner
        "prequal"    → Pre-Qualifier (Alter, PLZ, etc.)
        "questions"  → Haupt-Survey (Fragen)
        "captcha"    → Captcha (ROBOT, Math, Puzzle)
        "completion" → Survey fertig
        "screen_out" → Disqualifiziert
        "unknown"    → Nicht erkannt
    """
    body = (snap.get("bodyText", "") or "").lower()
    url = (snap.get("url", "") or "").lower()
    
    # Screen-Out Keywords
    for kw in ["umfrage passt nicht", "leider", "nicht geeignet", "vorzeitig beendet",
               "screen out", "disqualifiz", "sorry, we could not", "not eligible",
               "keine passende umfrage", "nicht teilnehmen"]:
        if kw in body:
            return "screen_out"
    
    # Completion Keywords
    for kw in ["vielen dank", "thank you", "abgeschlossen", "completed", "fertig",
               "danke für", "survey complete", "ihre antworten", "rewarded"]:
        if kw in body:
            return "completion"
    
    # Consent / Cookie Banner
    if any(kw in body for kw in ["alle akzeptieren", "accept all", "cookie", "zustimmen",
                                  "privacy", "einwilligung", "consent"]):
        if any(kw in body for kw in ["akzeptieren", "accept", "zustim", "agree", "consent"]):
            return "consent"
    
    # Captcha
    if any(kw in body for kw in ["robot", "captcha", "ich bin kein roboter", "are you a robot",
                                  "bitte bestätigen", "verify you're human", "bitte geben sie den code ein",
                                  "geben sie ihre antwort"]):
        return "captcha"
    
    # Drag-Drop Puzzle (PureSpectrum Angular CDK)
    if "Bitte legen Sie die Zahl" in body and "Kästchen" in body:
        return "drag_drop"
    
    # Pre-Qualifier (kurze Fragen vor Survey-Start)
    if any(kw in body for kw in ["wie alt sind sie", "what is your age", "birth", "geburt",
                                  "postleitzahl", "plz", "postal code", "gender", "geschlecht"]):
        return "prequal"
    
    # Questions (normale Survey-Seiten)
    if any(kw in body for kw in ["frage", "question", "bitte wählen", "please select",
                                  "stimme zu", "stimmen sie zu", "nie", "immer", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]):
        return "questions"
    
    return "unknown"


def get_body_text(snap: Dict) -> str:
    """Hole bodyText aus Snapshot (CDP JS extractor)."""
    # EXTRACTOR_JS gibt bodyText nicht direkt zurueck
    # Also machen wir einen separaten eval
    return snap.get("bodyText", snap.get("text", ""))


# ═════════════════════════════════════════════════════════════════════════════
# ANSWER PAGE — Universal logic (KEIN provider Hardcode!)
# ═════════════════════════════════════════════════════════════════════════════

async def answer_page(ws, snap: Dict) -> Dict[str, str]:
    """
    Beantwortet EINE Survey-Seite basierend auf Element-Typen.
    
    KEIN provider-spezifischer Hardcode! Universal:
    1. Checkboxen zuerst (multi-select braucht Zeit)
    2. Radio-Buttons (einfache Auswahl)
    3. Text-Felder (PLZ, Name, etc.)
    4. Textareas (Kommentare)
    5. Captcha → Captcha-Solver (TODO: integrate)
    
    Returns:
        {"actions": ["RADIO:...", "TEXT:10785", ...], "status": "ok"}
    """
    actions = []
    page_type = detect_page_type(snap)
    
    # Consent: Click "Zustimmen und fortfahren" / "Accept" / "Agree"
    if page_type == "consent":
        # Versuche verschiedene Consent-Button-Texte (partial match!)
        consent_texts = [
            "Zustimmen",
            "Akzeptieren",
            "Einwilligen",
            "Fortfahren",
            "Accept",
            "Agree",
            "Alles akzeptieren",
        ]
        for text in consent_texts:
            result = await cdp_execute_js(ws, 10, CDP_CLICK_BY_TEXT_JS.replace("CLICKED", "") +
                                          f"'{text}')()")
            if result.startswith("CLICKED:"):
                actions.append(f"CONSENT:{result}")
                return {"actions": actions, "status": "ok", "type": "consent"}
        
        # Fallback: Button im sichtbaren Bereich clicken
        result = await cdp_execute_js(ws, 15, """
(function() {
    var btns = document.querySelectorAll('button');
    for(var i = 0; i < btns.length; i++) {
        var r = btns[i].getBoundingClientRect();
        if(r.top > 100 && r.top < 800 && r.width > 50) {
            btns[i].click();
            return 'BTN_CLICKED:' + btns[i].textContent.trim().substring(0, 40);
        }
    }
    return 'NO_BTN';
})()
""")
        actions.append(f"CONSENT_FALLBACK:{result}")
        return {"actions": actions, "status": "ok", "type": "consent"}
    
    # Captcha: Solve using NVIDIA NIM + Llama 90B vision
    if page_type == "captcha":
        captcha_result = await solve_captcha(ws)
        actions.append(f"CAPTCHA:{captcha_result}")
        return {"actions": actions, "status": "ok", "type": "captcha"}
    
    # Drag-Drop Puzzle: Angular CDK puzzle at 66%
    if page_type == "drag_drop":
        drag_result = await solve_drag_drop(ws)
        actions.append(f"DRAG_DROP:{drag_result}")
        return {"actions": actions, "status": "ok", "type": "drag_drop"}
    
    # Screen-out: Nichts machen, Survey ist vorbei
    if page_type == "screen_out":
        actions.append("SCREEN_OUT_DETECTED")
        return {"actions": actions, "status": "done", "type": "screen_out"}
    
    # Completion: Survey ist fertig
    if page_type == "completion":
        actions.append("COMPLETION_DETECTED")
        return {"actions": actions, "status": "done", "type": "completion"}
    
    # Questions / Pre-Qualifier — gleiche Logik
    elements = snap.get("elements", [])
    has_checkboxes = any(e.get("type", "").startswith("checkbox") for e in elements)
    has_radios = any(e.get("type", "").startswith("radio") for e in elements)
    has_text = any(e.get("type") == "input" for e in elements)
    has_textarea = any(e.get("type") == "textarea" for e in elements)
    
    # Reihenfolge: Checkboxen → Radios → Text → Textarea
    
    # 1. Checkboxen (multi-select, first unchecked)
    if has_checkboxes:
        result = await cdp_execute_js(ws, 20, CDP_CHECKBOX_JS)
        actions.append(f"CHECKBOX:{result}")
    
    # 2. Radio-Buttons (mittlere Option waehlen)
    if has_radios:
        result = await cdp_execute_js(ws, 21, CDP_RADIO_JS)
        actions.append(f"RADIO:{result}")
    
    # 3. Text Inputs (PLZ, Name, etc.)
    if has_text:
        result = await cdp_execute_js(ws, 22, CDP_TEXT_JS)
        actions.append(f"TEXT:{result}")
    
    # 4. Textarea (Kommentar-Felder)
    if has_textarea:
        result = await cdp_execute_js(ws, 23, CDP_TEXTAREA_JS)
        actions.append(f"TEXTAREA:{result}")
    
    return {"actions": actions, "status": "ok", "type": page_type}


# ═════════════════════════════════════════════════════════════════════════════
# SUBMIT — Click submit/next/continue button
# ═════════════════════════════════════════════════════════════════════════════

async def click_submit(ws, timeout=10) -> str:
    """Klicke Next/Weiter/Submit/Continue Button."""
    result = await cdp_execute_js(ws, 30, CDP_SUBMIT_JS, timeout)
    return result


# ═════════════════════════════════════════════════════════════════════════════
# SNAPSHOT via CDP (tool_snapshot.py EXTRACTOR_JS)
# ═════════════════════════════════════════════════════════════════════════════

async def capture_page(ws) -> Dict:
    """
    Erstellt DOM-Snapshot via CDP Runtime.evaluate mit EXTRACTOR_JS.
    
    Nutzt tool_snapshot.py:EXTRACTOR_JS (100% reliable, kein skylight-cli).
    Bietet: elements[], url, title, bodyText, hash.
    """
    await ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                              "params": {"expression": EXTRACTOR_JS, "returnByValue": True}}))
    
    deadline = asyncio.get_running_loop().time() + 15
    for _ in range(100):
        remaining = max(0.1, deadline - asyncio.get_running_loop().time())
        if remaining <= 0:
            return {"elements": [], "url": "", "title": "", "hash": "timeout"}
        try:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=remaining))
            if msg.get("id") == 1:
                data = msg.get("result", {}).get("result", {}).get("value", {})
                body_text = data.get("bodyText", "")
                dom_hash = hashlib.md5(body_text.encode()).hexdigest()[:12]
                return {
                    "elements": data.get("elements", []),
                    "url": data.get("url", ""),
                    "title": data.get("title", ""),
                    "hash": dom_hash,
                    "bodyText": body_text,
                }
        except asyncio.TimeoutError:
            return {"elements": [], "url": "", "title": "", "hash": "timeout"}
    return {"elements": [], "url": "", "title": "", "hash": "timeout"}


# ═════════════════════════════════════════════════════════════════════════════
# MAIN: answer_survey() — MANUELLE TESTING, nicht auto-run!
# ═════════════════════════════════════════════════════════════════════════════

async def answer_survey(survey_ws_url: str, max_pages: int = MAX_PAGES) -> Dict:
    """
    Haupt-Funktion: Beantwortet einen Survey Seite fuer Seite.
    
    MANUELLE TESTING: Dieser Loop ist fuer EINZELNE Survey-Sessions gedacht,
    NICHT fuer automatisierten Background-Daemon!
    
    Args:
        survey_ws_url: CDP WebSocket URL des Survey-Tabs
        max_pages: Max Seiten bevor STOP (Safety)
        
    Returns:
        {
            "status": "completed" | "screen_out" | "stuck" | "max_pages" | "error",
            "pages_processed": int,
            "actions": [str],
            "hashes": [str],
            "final_url": str,
        }
    """
    print(f"\n{'='*60}")
    print(f"  ANSWER_SURVEY — Manual Testing Mode")
    print(f"{'='*60}")
    print(f"  Survey Tab WS: {survey_ws_url[:60]}...")
    
    # Pre-Flight: Session validieren
    if not validate_session(CHROME_PORT):
        return {"status": "error", "reason": "Session invalid — cookies expired?"}
    print(f"  [PREFLIGHT] Session: OK")
    
    # Import websockets here
    import websockets
    
    results = {
        "status": "unknown",
        "pages_processed": 0,
        "actions": [],
        "hashes": [],
        "final_url": "",
    }
    
    hash_counts = {}  # Anti-Stuck: hash -> count
    
    async with websockets.connect(survey_ws_url) as ws:
        for page_num in range(1, max_pages + 1):
            print(f"\n  --- Page {page_num}/{max_pages} ---")
            
            # 1. Capture Page (CDP only, kein skylight-cli!)
            snap = await capture_page(ws)
            url = snap.get("url", "")
            dom_hash = snap.get("hash", "")
            elements = snap.get("elements", [])
            
            print(f"  [URL] {url[:80]}")
            print(f"  [HASH] {dom_hash}")
            print(f"  [ELEMENTS] {len(elements)} interaktive Elemente")
            
            results["final_url"] = url
            results["hashes"].append(dom_hash)
            
            # Anti-Stuck: Hash mehrfach gleich?
            hash_counts[dom_hash] = hash_counts.get(dom_hash, 0) + 1
            if hash_counts[dom_hash] >= STUCK_THRESHOLD:
                print(f"  [STUCK] Hash '{dom_hash}' seen {hash_counts[dom_hash]}x — STOP")
                results["status"] = "stuck"
                break
            
            # 2. Detect Page Type
            page_type = detect_page_type(snap)
            print(f"  [TYPE] {page_type}")
            
            if page_type in ("screen_out", "completion"):
                results["status"] = page_type
                print(f"  [DONE] {page_type.upper()}")
                break
            
            # 3. Answer Page (universal, kein provider hardcode!)
            answer_result = await answer_page(ws, snap)
            actions = answer_result.get("actions", [])
            for a in actions:
                print(f"    [ACTION] {a}")
                results["actions"].append(a)
            
            if answer_result.get("status") in ("done", "skipped"):
                results["status"] = answer_result.get("status")
                break
            
            # 4. Submit (Next / Continue / Submit)
            print(f"  [SUBMIT] Clicking submit button...")
            submit_result = await click_submit(ws)
            print(f"    [SUBMIT] {submit_result}")
            results["actions"].append(f"SUBMIT:{submit_result}")
            
            # Warten auf Naechste Seite (SPA transition)
            await asyncio.sleep(3)
            
            results["pages_processed"] = page_num
        
        # Max pages reached
        if results["status"] == "unknown":
            results["status"] = "max_pages"
    
    print(f"\n{'='*60}")
    print(f"  RESULT: {results['status'].upper()}")
    print(f"  Pages: {results['pages_processed']}")
    print(f"  Actions: {len(results['actions'])}")
    print(f"  Final URL: {results['final_url'][:100]}")
    print(f"{'='*60}")
    
    # Update Command Registry
    _update_registry("answer_survey", results["status"] in ("completed", "screen_out"), results)
    
    return results


def _update_registry(command_id: str, success: bool, result: Dict):
    """Update persistent command_registry.json after each run."""
    try:
        with open(REGISTRY_PATH) as f:
            registry = json.load(f)
    except:
        registry = {"version": "1.0.0", "commands": []}
    
    # SR-187: UTC-aware (naive utcnow() is deprecated in Py 3.12, gone in 3.14).
    # Keep historical "Z" suffix for command_registry.json wire-format stability.
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    
    # Find or create command entry
    found = False
    for cmd in registry["commands"]:
        if cmd["id"] == command_id:
            found = True
            cmd["success_count"] += 1 if success else cmd.get("success_count", 0)
            cmd["failure_count"] += 0 if success else cmd.get("failure_count", 0) + 1
            cmd["last_success"] = now if success else cmd.get("last_success", now)
            cmd["last_run"] = now
            cmd["status"] = "verified" if cmd["success_count"] >= 3 else "testing"
            if "last_result" not in cmd:
                cmd["last_result"] = {}
            cmd["last_result"]["pages_processed"] = result.get("pages_processed", 0)
            cmd["last_result"]["final_url"] = result.get("final_url", "")
            cmd["last_result"]["status"] = result.get("status", "")
            break
    
    if not found:
        registry["commands"].append({
            "id": command_id,
            "description": "Universal Survey Answer Tool (CDP only, no skylight-cli, manual testing)",
            "path": "survey-cli/commands/answer_survey.py",
            "success_count": 1 if success else 0,
            "failure_count": 0 if success else 1,
            "last_success": now if success else None,
            "last_run": now,
            "status": "testing",
            "notes": f"Manual testing: {result.get('pages_processed', 0)} pages, status={result.get('status','')}"
        })
    
    registry["last_updated"] = now
    
    with open(REGISTRY_PATH, "w") as f:
        json.dump(registry, f, indent=2)
    print(f"  [REGISTRY] Updated: {command_id} -> {'success' if success else 'failure'}")


# ═════════════════════════════════════════════════════════════════════════════
# CLI — MANUELLE TESTING ONLY!
# ═════════════════════════════════════════════���═══════════════════════════════

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python answer_survey.py <survey_ws_url>")
        print("Example: python answer_survey.py ws://127.0.0.1:9999/devtools/page/ABC123...")
        print("\n  MANUELLE TESTING — KEIN AUTO-RUN!")
        sys.exit(1)
    
    ws_url = sys.argv[1]
    
    if ws_url == "--test":
        # Selbst-Test: Survey Tab WS aus Chrome lesen
        pages = json.loads(subprocess.run(
            ["curl", "-s", f"http://127.0.0.1:{CHROME_PORT}/json/list"],
            capture_output=True, text=True).stdout)
        
        # Survey-Tab finden (nicht dashboard)
        survey_tab = None
        for p in pages:
            url = p.get("url", "")
            if "dashboard" not in url and "heypiggy" not in url and p.get("type") == "page":
                survey_tab = p
                break
        
        if not survey_tab:
            print("ERROR: Kein Survey-Tab gefunden (nur Dashboard?)")
            print("Tipp: Zuerst open_survey.py ausfuehren!")
            sys.exit(1)
        
        ws_url = survey_tab["webSocketDebuggerUrl"]
        print(f"Auto-detected Survey Tab: {survey_tab['url'][:80]}")
    
    result = asyncio.run(answer_survey(ws_url))
    
    print(f"\nFinal Status: {result['status']}")
    print(f"Pages Processed: {result['pages_processed']}")
    
    if result["status"] == "completed":
        print("  → Survey komplett! Balance pruefen!")
    elif result["status"] == "screen_out":
        print("  → Screen-Out erkannt. Nächster Survey.")
    elif result["status"] == "stuck":
        print("  → Stuck erkannt (DOM-Hash wiederholt). Nächster Survey.")
    elif result["status"] == "max_pages":
        print("  → Max Seiten erreicht (30). Timeout.")
    else:
        print(f"  → Unbekannter Status: {result.get('status')}")
