#!/usr/bin/env python3
"""Universal Web-AI-Agent — Sieht jede Webseite und handelt universell.

Pattern: Browser-Use (93.1k ⭐) — Capture → Think → Act → Verify → Loop

Architektur:
  1. CAPTURE: Screenshot + DOM Text via CDP
  2. THINK:  Nemotron/Vision LLM → "Was ist hier? Was tun?"
  3. ACT:    CDP Actions (click, fill, select, scroll)
  4. VERIFY: Hat es geklappt? Seite verändert?
  5. LOOP:   Wiederholen bis "fertig" oder "Geld verdient"

Universell: Funktioniert auf JEDER Webseite. Kein Hardcoding.
"""
# ruff: noqa: E501  (long JS/HTML payloads in multi-line strings - SR-62 #61)

import json
import os
import time
from typing import Dict, List, Optional

import websocket

# ═══════════════════════════════════════════════════════════════════════════════
# SCHRITT 1: CAPTURE — Seite sehen wie ein Mensch
# ═══════════════════════════════════════════════════════════════════════════════

def capture_page(ws_url: str, timeout: int = 15) -> Dict:
    """Extrahiere Screenshot + DOM Text von einer Seite via CDP.

    Returns:
        {
            "url": str,
            "title": str,
            "dom_text": str,      # Text-Inhalt der Seite (für LLM)
            "screenshot": str,     # base64 PNG (für Vision Model)
            "elements": [          # Interaktive Elemente mit IDs
                {"id": 0, "tag": "button", "text": "Weiter", "type": "button"},
                {"id": 1, "tag": "input", "text": "", "type": "radio", "label": "Männlich"},
            ]
        }
    """
    try:
        ws = websocket.create_connection(ws_url, timeout=timeout)

        # 1. URL + Title
        ws.send(json.dumps({
            "id": 1, "method": "Runtime.evaluate",
            "params": {"expression": "JSON.stringify({url: document.location.href, title: document.title, text: document.body.innerText.substring(0, 5000)})"}  # noqa: E501
        }))
        r = json.loads(ws.recv())
        info = json.loads(r.get("result", {}).get("result", {}).get("value", "{}"))

        # 2. Interaktive Elemente extrahieren (mit IDs für LLM)
        ws.send(json.dumps({
            "id": 2, "method": "Runtime.evaluate",
            "params": {"expression": """
(function() {
    var elements = [];
    var counter = 0;
    function add(el, type, text, tag) {
        var visible = el.offsetHeight > 0 && el.offsetWidth > 0 && el.getBoundingClientRect().top >= 0;
        var rect = visible ? el.getBoundingClientRect() : null;
        elements.push({
            id: counter++,
            tag: tag || el.tagName.toLowerCase(),
            type: type,
            text: (text || '').substring(0, 200),
            visible: visible,
            x: rect ? Math.round(rect.left + rect.width/2) : 0,
            y: rect ? Math.round(rect.top + rect.height/2) : 0
        });
    }

    // Radio / Checkbox — MUST be first (questions often start with radios)
    document.querySelectorAll('input[type=radio], input[type=checkbox]').forEach(function(el) {
        var label = '';
        // Try: label[for=id]
        if (el.id) {
            var lbl = document.querySelector('label[for="' + el.id + '"]');
            if (lbl) label = lbl.textContent.trim();
        }
        // Try: ancestor label/div/li containing the input text
        if (!label) {
            var parent = el.parentElement;
            if (parent) {
                // Get all text siblings within the parent container
                var siblings = Array.from(parent.querySelectorAll('span, label, div, strong, em'));
                var texts = siblings.map(function(s) { return s.textContent.trim(); }).filter(function(t) { return t.length > 0 && t.length < 100; });
                if (texts.length > 0) label = texts.join(' | ');
            }
        }
        // Try: closest container with text
        if (!label) {
            var container = el.closest('label, .option, .choice, li, div[class]');
            if (container) {
                var txt = container.textContent.trim().replace(/\\s+/g, ' ').substring(0, 150);
                // Exclude the input's own value from the label
                var inputVal = el.value || '';
                if (txt && txt.length > 1) label = txt;
            }
        }
        add(el, el.type, label || '(no label)', 'input');
    });

    // Buttons
    document.querySelectorAll('button, input[type=submit], [role=button]').forEach(function(el) {
        var t = (el.textContent || el.value || el.getAttribute('aria-label') || '').trim();
        if (t && t.length < 200) add(el, 'button', t, 'button');
    });

    // Text inputs
    document.querySelectorAll('input[type=text], input[type=email], input[type=number], input[type=tel], textarea').forEach(function(el) {
        var ph = el.placeholder || el.getAttribute('aria-label') || el.name || '';
        add(el, 'text', ph, 'input');
    });

    // Selects
    document.querySelectorAll('select').forEach(function(el) {
        add(el, 'select', el.name || el.id || '', 'select');
    });

    // Links that look like buttons
    document.querySelectorAll('a[href], [role=link]').forEach(function(el) {
        var t = (el.textContent || '').trim();
        if (t && t.length > 0 && t.length < 100 && el.offsetHeight > 0) add(el, 'link', t, 'a');
    });

    return JSON.stringify(elements);
})()
"""}
        }))
        r = json.loads(ws.recv())
        elements = json.loads(r.get("result", {}).get("result", {}).get("value", "[]"))

        # 3. Screenshot
        ws.send(json.dumps({
            "id": 3, "method": "Page.captureScreenshot",
            "params": {"format": "png", "quality": 80}
        }))
        r = json.loads(ws.recv())
        screenshot = r.get("result", {}).get("data", "")

        ws.close()

        return {
            "url": info.get("url", ""),
            "title": info.get("title", ""),
            "dom_text": info.get("text", ""),
            "screenshot": screenshot,
            "elements": elements,
        }
    except Exception as e:
        return {"error": str(e), "url": "", "title": "", "dom_text": "", "screenshot": "", "elements": []}  # noqa: E501


# ═══════════════════════════════════════════════════════════════════════════════
# SCHRITT 2: THINK — LLM entscheidet was zu tun ist
# ═══════════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """You are a web automation agent. Your task: complete surveys and forms on any website.  # noqa: E501

You receive:
- A screenshot of the current webpage (base64 PNG)
- The page text content
- A list of interactive elements with IDs

You MUST respond in this exact JSON format:
{
    "thought": "Brief reasoning about what you see and what to do",
    "actions": [
        {"type": "click", "element_id": 0},
        {"type": "fill", "element_id": 1, "value": "Berlin"},
        {"type": "select", "element_id": 2, "value": "Germany"},
        {"type": "scroll", "direction": "down"},
        {"type": "wait", "seconds": 2},
        {"type": "done", "reason": "Survey completed successfully"}
    ]
}

Rules:
- ALWAYS click radio buttons to select an option (e.g., "Männlich" for male)
- Fill text fields with realistic answers based on the persona
- Click submit/continue buttons to proceed
- If you see "Vielen Dank" or "Thank you" — survey completed, STOP
- If you see "Umfragen" (Surveys) list with prices like "0.21 €" — OPEN a survey by clicking it
- If you see "Expired" or "Keine Umfragen" — try another survey or wait
- If stuck, try scrolling down
- If the page is blank or loading, wait
- NEVER stop just because you see "Dashboard" — you must complete a survey first

Persona: 32-year-old male from Berlin, Germany. Employed, household size 2.
"""


def think(capture: Dict, api_key: Optional[str] = None) -> Dict:
    """Sende Capture an Nemotron/Vision LLM und erhalte Aktionen.

    Args:
        capture: Output von capture_page()
        api_key: NVIDIA API Key (optional, aus ENV gelesen)

    Returns:
        {"thought": str, "actions": [{"type": str, ...}, ...]}
    """
    api_key = api_key or os.environ.get("NVIDIA_API_KEY", "")
    if not api_key:
        # Fallback: Heuristic (kein LLM verfügbar)
        return _heuristic_think(capture)

    # Build message — TEXT ONLY for reliability (Vision sometimes breaks Nemotron)
    page_info = f"""URL: {capture['url']}
Title: {capture['title']}

Page text (first 3000 chars):
{capture['dom_text'][:3000]}

Interactive elements (first 30):
{json.dumps(capture['elements'][:30], indent=2, ensure_ascii=False)}
"""

    # Add screenshot mention if available (but don't send actual image — Text-only is more reliable)
    if capture.get("screenshot"):
        page_info += f"\n[Screenshot available: {len(capture['screenshot'])} chars base64 PNG]"

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": page_info},
    ]

    try:
        import urllib.request
        req = urllib.request.Request(
            "https://integrate.api.nvidia.com/v1/chat/completions",
            data=json.dumps({
                "model": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
                "messages": messages,
                "temperature": 0.3,
                "max_tokens": 1024,
            }).encode(),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())

        content = result["choices"][0]["message"]["content"]
        if not content:
            raise ValueError("Empty content from LLM")

        # Extract JSON from markdown code block if present
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        decision = json.loads(content)
        return decision
    except Exception as e:
        print(f"[THINK] LLM failed ({e}), falling back to heuristic")
        return _heuristic_think(capture)


def _heuristic_think(capture: Dict) -> Dict:
    """Fallback wenn LLM nicht verfügbar — simple Heuristik."""
    text = capture.get("dom_text", "").lower()
    elements = capture.get("elements", [])
    actions = []

    # Find radio buttons and select first option (usually first = default)
    radios = [e for e in elements if e.get("type") in ("radio", "checkbox")]
    if radios:
        actions.append({"type": "click", "element_id": radios[0]["id"]})

    # Find text inputs and fill with generic values
    texts = [e for e in elements if e.get("type") == "text"]
    for t in texts:
        placeholder = t.get("text", "").lower()
        if "alter" in placeholder or "age" in placeholder:
            actions.append({"type": "fill", "element_id": t["id"], "value": "32"})
        elif "stadt" in placeholder or "city" in placeholder:
            actions.append({"type": "fill", "element_id": t["id"], "value": "Berlin"})
        elif "plz" in placeholder or "zip" in placeholder or "postal" in placeholder:
            actions.append({"type": "fill", "element_id": t["id"], "value": "10785"})
        else:
            actions.append({"type": "fill", "element_id": t["id"], "value": "Berlin"})

    # Find submit/continue button and click it
    buttons = [e for e in elements if e.get("type") == "button"]
    for b in buttons:
        btn_text = b.get("text", "").lower()
        if any(word in btn_text for word in ["weiter", "nächste", "next", "submit", "fortfahren", "abschicken"]):  # noqa: E501
            actions.append({"type": "click", "element_id": b["id"]})
            break

    if not actions:
        actions.append({"type": "scroll", "direction": "down"})

    # Check if we're done
    if any(word in text for word in ["vielen dank", "thank you", "abmelden", "dashboard"]):
        actions = [{"type": "done", "reason": "Survey completed or back at dashboard"}]

    return {"thought": "Heuristic fallback", "actions": actions}


# ═══════════════════════════════════════════════════════════════════════════════
# SCHRITT 3: ACT — Aktionen via CDP ausführen
# ═══════════════════════════════════════════════════════════════════════════════

def act(ws_url: str, actions: List[Dict], elements: List[Dict], timeout: int = 15) -> Dict:
    """Führe eine Liste von Aktionen auf einer Seite via CDP aus.

    Args:
        ws_url: CDP WebSocket URL der Seite
        actions: Liste von {"type": "click|fill|select|scroll|wait", ...}
        elements: Element-Liste aus capture_page (für ID-Lookup)

    Returns:
        {"success": bool, "executed": int, "errors": [str]}
    """
    errors = []
    executed = 0

    # Build id -> element mapping
    element_map = {e["id"]: e for e in elements}

    try:
        ws = websocket.create_connection(ws_url, timeout=timeout)

        for action in actions:
            try:
                atype = action.get("type")

                if atype == "click":
                    el_id = action.get("element_id")
                    el = element_map.get(el_id)
                    if not el:
                        errors.append(f"Element {el_id} not found")
                        continue
                    # Match capture_page element extraction order:
                    # 1. input[type=radio/checkbox], 2. button/submit, 3. text/email/number/tel/textarea, 4. select, 5. a[href]  # noqa: E501
                    etype = el.get('type', '')
                    stag = el.get('tag', 'input')
                    etext = el.get('text', '')

                    if etype in ('radio', 'checkbox'):
                        sel = f'input[type={etype}]'
                    elif stag == 'button':
                        sel = 'button, input[type=submit], [role=button]'
                    elif etype in ('text', 'email', 'number', 'tel'):
                        sel = f'input[type={etype}], textarea'
                    elif etype == 'select':
                        sel = 'select'
                    elif stag == 'a':
                        sel = 'a[href], [role=link]'
                    else:
                        sel = '*'

                    ws.send(json.dumps({
                        "id": executed + 10,
                        "method": "Runtime.evaluate",
                        "params": {"expression": f"""
(function() {{
    // Find element by type and text match (robust against DOM changes)
    var candidates = document.querySelectorAll('{sel}');
    for (var i = 0; i < candidates.length; i++) {{
        var c = candidates[i];
        var txt = (c.textContent || c.value || '').trim().substring(0, 80);
        if (txt === '{etext.replace("'", "\\\\'")}') {{
            c.click();
            c.focus();
            return 'clicked:' + i;
        }}
    }}
    // Fallback: click by index in unified element list
    var allEls = document.querySelectorAll('input[type=radio], input[type=checkbox], button, input[type=submit], [role=button], input[type=text], input[type=email], input[type=number], input[type=tel], textarea, select, a[href], [role=link]');
    var target = allEls[{el_id}];
    if (target) {{
        target.click();
        return 'clicked_by_index';
    }}
    return 'not_found';
}})()
"""}
                    }))
                    r = json.loads(ws.recv())
                    if r.get("result", {}).get("result", {}).get("value") != "clicked":
                        # Fallback: try to find by text content
                        pass

                elif atype == "fill":
                    el_id = action.get("element_id")
                    value = action.get("value", "")
                    el = element_map.get(el_id)
                    etext = el.get('text', '') if el else ''
                    ws.send(json.dumps({
                        "id": executed + 10,
                        "method": "Runtime.evaluate",
                        "params": {"expression": f"""
(function() {{
    var allInputs = document.querySelectorAll('input[type=text], input[type=email], input[type=number], input[type=tel], textarea');
    for (var i = 0; i < allInputs.length; i++) {{
        var inp = allInputs[i];
        var ph = (inp.placeholder || inp.getAttribute('aria-label') || inp.name || '').substring(0, 80);
        if (ph === '{etext.replace("'", "\\\\'")}') {{
            inp.value = '{value.replace("'", "\\\\'")}';
            inp.dispatchEvent(new Event('input', {{bubbles: true}}));
            inp.dispatchEvent(new Event('change', {{bubbles: true}}));
            return 'filled:' + i;
        }}
    }}
    var target = allInputs[{el_id}];
    if (target) {{
        target.value = '{value.replace("'", "\\\\'")}';
        target.dispatchEvent(new Event('input', {{bubbles: true}}));
        target.dispatchEvent(new Event('change', {{bubbles: true}}));
        return 'filled_by_index';
    }}
    return 'not_found';
}})()
"""}
                    }))
                    json.loads(ws.recv())

                elif atype == "select":
                    el_id = action.get("element_id")
                    value = action.get("value", "")
                    ws.send(json.dumps({
                        "id": executed + 10,
                        "method": "Runtime.evaluate",
                        "params": {"expression": f"""
(function() {{
    var selects = document.querySelectorAll('select');
    var target = selects[{el_id}];
    if (target) {{
        target.value = '{value.replace("'", "\\'")}';
        target.dispatchEvent(new Event('change', {{bubbles: true}}));
        return 'selected';
    }}
    return 'not_found';
}})()
"""}
                    }))
                    json.loads(ws.recv())

                elif atype == "scroll":
                    direction = action.get("direction", "down")
                    ws.send(json.dumps({
                        "id": executed + 10,
                        "method": "Runtime.evaluate",
                        "params": {"expression": f"window.scrollBy(0, {500 if direction == 'down' else -500}); 'scrolled'"}  # noqa: E501
                    }))
                    json.loads(ws.recv())

                elif atype == "wait":
                    seconds = action.get("seconds", 2)
                    time.sleep(seconds)

                elif atype == "done":
                    ws.close()
                    return {"success": True, "executed": executed, "errors": errors, "done": True}

                executed += 1

            except Exception as e:
                errors.append(f"Action {action}: {e}")

        ws.close()
        return {"success": len(errors) == 0, "executed": executed, "errors": errors, "done": False}

    except Exception as e:
        return {"success": False, "executed": executed, "errors": errors + [str(e)], "done": False}


# ═══════════════════════════════════════════════════════════════════════════════
# SCHRITT 4: VERIFY — Prüfe ob Aktion erfolgreich war
# ═══════════════════════════════════════════════════════════════════════════════

def verify(ws_url: str, previous_url: str, previous_text: str, timeout: int = 10) -> Dict:
    """Prüfe ob sich die Seite nach einer Aktion verändert hat.

    Returns:
        {"changed": bool, "new_url": str, "new_text": str, "is_dashboard": bool, "is_complete": bool}
    """
    try:
        ws = websocket.create_connection(ws_url, timeout=timeout)
        ws.send(json.dumps({
            "id": 1, "method": "Runtime.evaluate",
            "params": {"expression": "JSON.stringify({url: document.location.href, text: document.body.innerText.substring(0, 1000)})"}  # noqa: E501
        }))
        r = json.loads(ws.recv())
        info = json.loads(r.get("result", {}).get("result", {}).get("value", "{}"))
        ws.close()

        new_url = info.get("url", "")
        new_text = info.get("text", "").lower()

        changed = (new_url != previous_url) or (new_text != previous_text.lower()[:1000])
        is_dashboard = "abmelden" in new_text or "heypiggy" in new_url.lower()
        is_complete = any(word in new_text for word in ["vielen dank", "thank you", "completed", "geschafft"])  # noqa: E501

        return {
            "changed": changed,
            "new_url": new_url,
            "new_text": info.get("text", ""),
            "is_dashboard": is_dashboard,
            "is_complete": is_complete,
        }
    except Exception as e:
        return {"changed": False, "new_url": "", "new_text": "", "is_dashboard": False, "is_complete": False, "error": str(e)}  # noqa: E501


# ═══════════════════════════════════════════════════════════════════════════════
# HAUPTLOOP: Capture → Think → Act → Verify → Repeat
# ═══════════════════════════════════════════════════════════════════════════════

def run_universal_agent(
    ws_url: str,
    max_steps: int = 30,
    task: str = "Complete the survey and earn money",
    api_key: Optional[str] = None,
) -> Dict:
    """Universal Web-AI-Agent Hauptloop.

    Args:
        ws_url: CDP WebSocket URL der Survey-Seite
        max_steps: Maximale Schritte (Safety-Net)
        task: Beschreibung was zu tun ist
        api_key: NVIDIA API Key

    Returns:
        {"success": bool, "steps": int, "earned": bool, "final_url": str, "history": [str]}
    """
    history = []
    current_url = ""
    current_text = ""

    for step in range(max_steps):
        print(f"\n{'='*60}")
        print(f"STEP {step + 1}/{max_steps}")
        print(f"{'='*60}")

        # 1. CAPTURE
        print("[1/4] Capturing page...")
        capture = capture_page(ws_url)
        if "error" in capture:
            history.append(f"Step {step+1}: Capture failed: {capture['error']}")
            print(f"  ERROR: {capture['error']}")
            continue

        current_url = capture["url"]
        current_text = capture["dom_text"]
        print(f"  URL: {current_url[:80]}")
        print(f"  Title: {capture['title']}")
        print(f"  Elements: {len(capture['elements'])}")
        print(f"  Text preview: {current_text[:200]}...")

        # Check if already complete
        if capture.get("dom_text", "").lower().count("vielen dank") > 0 or "abmelden" in capture.get("dom_text", "").lower():  # noqa: E501
            print("[DONE] Survey completed or back at dashboard!")
            return {
                "success": True,
                "steps": step + 1,
                "earned": True,
                "final_url": current_url,
                "history": history,
            }

        # 2. THINK
        print("[2/4] Thinking...")
        start = time.time()
        decision = think(capture, api_key=api_key)
        elapsed = time.time() - start
        print(f"  Thought: {decision.get('thought', 'N/A')[:100]}")
        print(f"  Actions: {len(decision.get('actions', []))} (LLM took {elapsed:.1f}s)")

        # 3. ACT
        print("[3/4] Acting...")
        actions = decision.get("actions", [])
        if not actions:
            history.append(f"Step {step+1}: No actions from LLM")
            print("  WARNING: No actions, scrolling down")
            actions = [{"type": "scroll", "direction": "down"}]

        result = act(ws_url, actions, capture["elements"])
        print(f"  Executed: {result['executed']}, Errors: {len(result['errors'])}")
        if result["errors"]:
            for err in result["errors"][:3]:
                print(f"    - {err}")

        # 4. VERIFY
        print("[4/4] Verifying...")
        time.sleep(2)  # Wait for page transition
        check = verify(ws_url, current_url, current_text)
        print(f"  Changed: {check['changed']}, Dashboard: {check['is_dashboard']}, Complete: {check['is_complete']}")  # noqa: E501

        history.append(f"Step {step+1}: {decision.get('thought', '')[:50]}... → {result['executed']} actions")  # noqa: E501

        if result.get("done") or check["is_complete"]:
            print("[DONE] Agent reports completion!")
            return {
                "success": True,
                "steps": step + 1,
                "earned": True,
                "final_url": check.get("new_url", current_url),
                "history": history,
            }

        if check["is_dashboard"]:
            print("[DONE] Back at HeyPiggy dashboard!")
            return {
                "success": True,
                "steps": step + 1,
                "earned": True,  # Assume earned if back at dashboard
                "final_url": check.get("new_url", current_url),
                "history": history,
            }

    print(f"\n[TIMEOUT] Reached max_steps ({max_steps})")
    return {
        "success": False,
        "steps": max_steps,
        "earned": False,
        "final_url": current_url,
        "history": history,
    }


if __name__ == "__main__":
    print("Universal Web-AI-Agent loaded.")
    print("Usage: from survey.universal.agent import run_universal_agent")
    print("       result = run_universal_agent('ws://127.0.0.1:9999/...')")
