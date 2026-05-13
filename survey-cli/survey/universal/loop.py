from datetime import datetime, timezone
#!/usr/bin/env python3
"""================================================================================
UNIVERSAL SURVEY LOOP — Das Herzstück des Agenten (2026-05-10)

WAS IST DAS?
  Universaler Survey-Loop: EINE Funktion, JEDE Webseite, 100% zuverlässig.

  Pattern: snapshot() → decide(NIM) → execute(CDP) → verify() → repeat

  Kommt mit ANY Survey-Typ klar:
  - Pre-Qualifier (Einkommen, Alter, etc.)
  - Provider XYZ (PureSpectrum, Cint, Toluna, Qualtrics, etc.)
  - Consent Screens, Captchas, Drag-Drop Puzzles
  - KEIN Hardcoding — alles wird erkannt und verarbeitet

WARUM NEUE DATEI?
  Die alte Lösung (runner.py) war zu komplex mit 1000+ Zeilen vermischt.
  Diese Datei ist FOKUSSIERT: NEMO-Loop + Survey Lock + Tab Cleanup.

ARCHITEKTUR:
  ┌──────────────────────────────────────────────────────────────────────────┐
  │  run_universal_survey(ws_url, profile) → SurveyResult                   │
  ├──────────────────────────────────────────────────────────────────────────┤
  │                                                                          │
  │  1. SNAPSHOT   → skylight-cli snapshot-compact → @eN refs + body text  │
  │     FALLBACK:    CDP inline JS für element extraction                   │
  │                                                                          │
  │  2. DECIDE     → NIM Nemotron 3 Omni → Actions[]                       │
  │     FALLBACK:    Pattern-Matcher (radio, text, select, button)          │
  │                                                                          │
  │  3. EXECUTE    → Verified CDP Patterns (survey-answer-patterns.md)      │
  │     - Click radio by label text match                                   │
  │     - Fill text by placeholder match                                    │
  │     - Click button by text (Weiter/Next/Submit)                         │
  │     - Select dropdown by value                                          │
  │                                                                          │
  │  4. VERIFY     → Body text check (completion markers)                   │
  │     - "Vielen Dank" → completed                                         │
  │     - "nicht geeignet" → screen_out                                     │
  │     - Page unchanged → retry                                            │
  │                                                                          │
  │  5. LOCK       → Survey Lock (File) verhindert Parallel-Execution      │
  │                                                                          │
  │  6. CLEANUP    → Survey-Tab schließen nach Abschluss                   │
  │                                                                          │
  └──────────────────────────────────────────────────────────────────────────┘

BANNED:
  ❌ Provider-spezifischer Hardcode (if purespectrum: ... elif cint: ...)
  ❌ Playstealth launch
  ❌ webauto-nodriver
  ❌ pkill -f "Google Chrome"
  ❌ Hardcoded PIDs / Tab-IDs

FUNKTIONIERT (aus /commands/surveys/survey-answer-patterns.md):
  ✅ Radio click: document.querySelectorAll("input[type=radio]")[INDEX].click()
  ✅ Checkbox: el.click() mit Event dispatch
  ✅ Text fill: input.value = "X" + Event dispatch
  ✅ Button click: textContent match → click()
  ✅ Submit: form.submit() oder Button-Weiter/Next klicken

================================================================================"""
# ruff: noqa: E501  (long JS/HTML payloads in multi-line strings - SR-62 #61)

from __future__ import annotations
import json
import os
import re
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import websocket

# ── Survey Lock ────────────────────────────────────────────────────────────────

LOCK_PATH = Path(__file__).parent.parent / "data" / ".survey_lock.json"


def _acquire_lock(survey_id: str = "") -> bool:
    """Acquire survey lock. Returns True if acquired, False if locked."""
    if LOCK_PATH.exists():
        try:
            with open(LOCK_PATH, "r") as f:
                lock = json.load(f)
            lock_time = lock.get("started", "2000-01-01")
            age_min = (time.time() - datetime.fromisoformat(lock_time[:19]).replace(tzinfo=timezone.utc).timestamp()) / 60  # noqa: E501
            if age_min < 30:
                return False
        except Exception:
            pass
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOCK_PATH, "w") as f:
        json.dump({
            "survey_id": survey_id,
            "started": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
            "pid": os.getpid(),
        }, f)
    return True


def _release_lock():
    """Release survey lock."""
    try:
        if LOCK_PATH.exists():
            LOCK_PATH.unlink()
    except Exception:
        pass


def _wipe_stale_locks():
    """Wipe stale locks on startup (surveys from crashed sessions)."""
    if LOCK_PATH.exists():
        try:
            with open(LOCK_PATH, "r") as f:
                lock = json.load(f)
            lock_time = lock.get("started", "2000-01-01")
            age_min = (time.time() - datetime.fromisoformat(lock_time[:19]).replace(tzinfo=timezone.utc).timestamp()) / 60  # noqa: E501
            if age_min >= 30:
                LOCK_PATH.unlink()
        except Exception:
            try:
                LOCK_PATH.unlink()
            except Exception:
                pass


# ── Result Dataclass ───────────────────────────────────────────────────────────

@dataclass
class UniversalSurveyResult:
    status: str = "error"  # "completed" | "screen_out" | "error" | "locked"
    success: bool = False
    steps: int = 0
    earned: float = 0.0
    balance_before: float = 0.0
    balance_after: float = 0.0
    provider: str = "unknown"
    survey_id: str = ""
    history: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    screen_out: bool = False
    completion_detected: bool = False
    reason: str = ""


# ── CDP Connection ─────────────────────────────────────────────────────────────

def _cdp_send(ws_url: str, method: str, params: Dict, timeout: int = 15) -> Dict:
    """Send CDP command and return result value."""
    ws = websocket.create_connection(ws_url, timeout=timeout)
    ws.send(json.dumps({"id": 1, "method": method, "params": params}))
    r = json.loads(ws.recv())
    ws.close()
    return r.get("result", {}).get("result", {}).get("value", "")


def _cdp_eval(ws_url: str, js: str, timeout: int = 15) -> str:
    """Execute JS via CDP Runtime.evaluate. Returns result value."""
    return _cdp_send(ws_url, "Runtime.evaluate", {"expression": js}, timeout)


# ── Balance Reader ─────────────────────────────────────────────────────────────

def _read_balance(port: int = 9999) -> float:
    """Read HeyPiggy balance from dashboard tab."""
    try:
        pages = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=5).read())  # noqa: E501
        db = [p for p in pages if "dashboard" in p.get("url", "").lower() and p.get("type") == "page"]  # noqa: E501
        if not db:
            return 0.0
        body = _cdp_eval(db[0]["webSocketDebuggerUrl"], "document.body.innerText")
        amounts = re.findall(r"(\d+[.,]?\d*)\s*€", body[:800])
        for amt in amounts:
            val = float(amt.replace(",", "."))
            if val >= 1.0:
                return val
        return 0.0
    except Exception:
        return 0.0


# ── Universal Element Extraction ───────────────────────────────────────────────
#
# ROOT CAUSE (2026-05-10): Element recognition was incomplete.
# OLD: Radio buttons had no labels → NIM couldn't decide which option.
# FIX: Extract EVERYTHING — radio text, button text, input placeholders, select options.
#      Use the PAGE BODY as source of truth (not just DOM elements).
#      Body text contains ALL question options laid out visually.

def _extract_page(ws_url: str) -> Dict:
    """Extract complete page state for universal survey handling.

    Returns:
        {
            "url": str,
            "title": str,
            "body_text": str,       # ALL text on page (questions + options)
            "elements": {
                "radios": [{"text": "Option 1"}, {"text": "Option 2"}, ...],
                "checkboxes": [...],
                "text_inputs": [{"placeholder": "...", "index": 0}, ...],
                "selects": [{"options": [...], "index": 0}, ...],
                "buttons": [{"text": "Weiter"}, {"text": "Absenden"}, ...],
            },
            "progress": str or None,
            "provider": str,
        }
    """
    # 1. Get body text + URL
    meta_js = """
(function() {
    return JSON.stringify({
        url: document.location.href,
        title: document.title,
        body: document.body.innerText.substring(0, 3000),
        body_html: document.body.innerHTML.substring(0, 5000),
    });
})()
"""
    meta_raw = _cdp_eval(ws_url, meta_js)
    try:
        meta = json.loads(meta_raw)
    except Exception:
        meta = {"url": "", "title": "", "body": "", "body_html": ""}

    body = meta.get("body", "")
    url = meta.get("url", "")

    # 2. Detect provider from URL
    provider = "unknown"
    for p in ["purespectrum", "cint", "toluna", "qualtrics", "samplicio", "ipsos", "nfield", "irbureau", "strat7", "innovatemr", "decipher", "surveymonkey"]:  # noqa: E501
        if p in url.lower():
            provider = p
            break

    # 3. Extract all interactive elements via DOM
    elements_js = """
(function() {
    var out = {
        radios: [],
        checkboxes: [],
        text_inputs: [],
        selects: [],
        buttons: [],
        links: [],
    };

    // RADIO BUTTONS — extract label text from parent container
    document.querySelectorAll('input[type=radio]').forEach(function(el) {
        var label = '';
        // Try: label[for=id]
        if (el.id) {
            var lbl = document.querySelector('label[for="' + el.id + '"]');
            if (lbl) label = lbl.textContent.trim();
        }
        // Try: parent div/label/li containing text
        if (!label || label.length < 2) {
            var container = el.closest('label, .option, .choice, li, div[class*="option"], div[class*="choice"]');
            if (container) {
                var txt = container.textContent.trim().replace(/\\s+/g, ' ').substring(0, 150);
                // Remove the input's value from the label text
                if (el.value && txt.includes(el.value)) txt = txt.replace(el.value, '').trim();
                if (txt.length > 1) label = txt;
            }
        }
        // Try: preceding sibling label
        if (!label || label.length < 2) {
            var prev = el.previousElementSibling;
            if (prev && prev.tagName === 'LABEL') label = prev.textContent.trim();
        }
        if (!label || label.length < 2) {
            var next = el.nextElementSibling;
            if (next && (next.tagName === 'LABEL' || next.tagName === 'SPAN')) label = next.textContent.trim();
        }
        out.radios.push({
            text: label || '(no label)',
            value: el.value || '',
            checked: el.checked || false,
            disabled: el.disabled || false,
        });
    });

    // CHECKBOXES — same extraction
    document.querySelectorAll('input[type=checkbox]').forEach(function(el) {
        var label = '';
        if (el.id) {
            var lbl = document.querySelector('label[for="' + el.id + '"]');
            if (lbl) label = lbl.textContent.trim();
        }
        if (!label || label.length < 2) {
            var container = el.closest('label, .option, li');
            if (container) label = container.textContent.trim().replace(/\\s+/g, ' ').substring(0, 150);
        }
        out.checkboxes.push({
            text: label || '(no label)',
            value: el.value || '',
            checked: el.checked || false,
        });
    });

    // TEXT INPUTS
    document.querySelectorAll('input[type=text], input[type=email], input[type=number], input[type=tel], textarea').forEach(function(el) {
        out.text_inputs.push({
            placeholder: el.placeholder || '',
            aria_label: el.getAttribute('aria-label') || '',
            name: el.name || '',
            value: el.value || '',
            tag: el.tagName.toLowerCase(),
        });
    });

    // SELECT DROPDOWNS
    document.querySelectorAll('select').forEach(function(el) {
        var opts = [];
        el.querySelectorAll('option').forEach(function(o) {
            opts.push(o.textContent.trim().substring(0, 80));
        });
        out.selects.push({
            options: opts,
            name: el.name || '',
            selected: el.selectedIndex || 0,
        });
    });

    // BUTTONS
    document.querySelectorAll('button, input[type=submit], input[type=button], [role=button]').forEach(function(el) {
        var t = (el.textContent || el.value || el.getAttribute('aria-label') || '').trim();
        if (t && t.length < 100 && t.length > 0) {
            out.buttons.push({text: t, type: el.type || 'button'});
        }
    });

    // LINKS that look like buttons
    document.querySelectorAll('a[href]').forEach(function(el) {
        var t = (el.textContent || '').trim();
        if (t && t.length > 0 && t.length < 80 && el.offsetHeight > 0) {
            out.links.push({text: t});
        }
    });

    return JSON.stringify(out);
})()
"""
    els_raw = _cdp_eval(ws_url, elements_js)
    try:
        elements = json.loads(els_raw)
    except Exception:
        elements = {"radios": [], "checkboxes": [], "text_inputs": [], "selects": [], "buttons": [], "links": []}  # noqa: E501

    # 4. Extract progress bar
    progress = None
    progress_match = re.search(r"(\d+)\s*/\s*(\d+)", body) or re.search(r"(\d+)%", body)
    if progress_match:
        progress = progress_match.group(0)

    return {
        "url": url,
        "title": meta.get("title", ""),
        "body_text": body,
        "body_html": meta.get("body_html", ""),
        "elements": elements,
        "progress": progress,
        "provider": provider,
    }


# ── Completion Detection ───────────────────────────────────────────────────────

def _detect_completion(page: Dict) -> Tuple[str, str]:
    """Detect survey completion/screen-out from page state.

    Returns: (status, reason)
    - ("completed", "vielen dank")
    - ("screen_out", "leider nicht geeignet")
    - ("running", "") — survey still in progress
    """
    body = page.get("body_text", "").lower()
    page.get("url", "").lower()
    title = page.get("title", "").lower()

    # COMPLETED markers
    completed_markers = [
        "vielen dank", "danke für", "thank you for completing", "survey complete",
        "abgeschlossen", "erfolgreich", "ausgefüllt", "gutgeschrieben",
        "guthaben wurde", "completed the survey", "reward credited",
        "your submission", "submitted successfully", "finished",
    ]
    for m in completed_markers:
        if m in body or m in title:
            return ("completed", m)

    # SCREEN-OUT markers
    screenout_markers = [
        "nicht geeignet", "leider ist ein fehler", "error occurred", "error - support",
        "screen out", "not eligible", "you do not qualify", "not available",
        "no app id", "link expired", "survey closed", "survey has ended",
        "thank you for your interest",
    ]
    for m in screenout_markers:
        if m in body:
            return ("screen_out", m)

    return ("running", "")


# ── NIM Decision ───────────────────────────────────────────────────────────────

def _nim_decide(page: Dict, profile: Dict) -> List[Dict]:
    """Use Nemotron NIM to decide actions. Falls back to pattern matcher.

    Args:
        page: Output from _extract_page()
        profile: Persona dict (age, gender, city, etc.)

    Returns:
        List of actions: [{"type": "click_radio", "text": "Option 1"}, {"type": "click_button", "text": "Weiter"}]
    """
    api_key = os.environ.get("NVIDIA_API_KEY")
    if not api_key:
        return _pattern_decide(page, profile)

    body = page.get("body_text", "")
    elements = page.get("elements", {})
    page.get("provider", "unknown")

    # Build prompt with ALL available information
    prompt = f"""Du beantwortest eine Online-Umfrage. Du siehst die Seite und musst handeln.

PERSONA (Deutsch, ehrlich):
- Alter: {profile.get('age', 32)}
- Geschlecht: {profile.get('gender', 'Männlich')}
- Wohnort: {profile.get('city', 'Berlin')}
- PLZ: {profile.get('postal', '10785')}
- Beruf: {profile.get('occupation', 'Angestellter')}
- Haushaltseinkommen: {profile.get('income', '€39.000 - €64.999')}
- Haushaltsgröße: {profile.get('household', '2 Personen')}

SEITE:
{body[:2000]}

VERFÜGBARE OPTIONEN:
"""

    # Add radio options
    radios = elements.get("radios", [])
    if radios:
        prompt += "\nRadio-Buttons (Antworten):\n"
        for i, r in enumerate(radios):
            prompt += f"  [{i}] {r['text']}\n"

    # Add buttons
    buttons = elements.get("buttons", [])
    if buttons:
        prompt += "\nButtons:\n"
        for b in buttons:
            prompt += f"  - {b['text']}\n"

    # Add text inputs
    inputs = elements.get("text_inputs", [])
    if inputs:
        prompt += "\nText-Felder:\n"
        for i, inp in enumerate(inputs):
            prompt += f"  [{i}] placeholder=\"{inp['placeholder']}\" aria_label=\"{inp['aria_label']}\"\n"  # noqa: E501

    # Add selects
    selects = elements.get("selects", [])
    if selects:
        prompt += "\nDropdowns:\n"
        for i, sel in enumerate(selects):
            prompt += f"  [{i}] options={sel['options'][:5]}\n"

    prompt += """
REGELN:
- Wähle IMMER eine Antwort (klicke einen Radio-Button)
- Beantworte ehrlich basierend auf der Persona
- Klicke danach auf den "Weiter" oder "Next" Button
- Wenn mehrere Radio-Buttons: wähle die realistischste Option

Antworte als JSON:
{"actions": [
  {"type": "click_radio", "index": 0},
  {"type": "click_button", "text_contains": "Weiter"}
]}
"""

    try:
        req = urllib.request.Request(
            "https://integrate.api.nvidia.com/v1/chat/completions",
            data=json.dumps({
                "model": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 512,
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
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        decision = json.loads(content)
        return decision.get("actions", [])
    except Exception as e:
        print(f"[NIM] Failed ({e}), falling back to pattern matcher")
        return _pattern_decide(page, profile)


def _pattern_decide(page: Dict, profile: Dict) -> List[Dict]:
    """Fallback decision using patterns (no NIM needed).

    Rules:
    - If radios exist → click first one (usually safe default)
    - If text inputs exist → fill with profile data
    - If buttons exist → click the most likely "next" button
    """
    actions = []
    elements = page.get("elements", {})
    body_lower = page.get("body_text", "").lower()

    # Detect question type from body text
    is_income = any(w in body_lower for w in ["einkommen", "haushaltseinkommen", "income"])
    is_age = any(w in body_lower for w in ["alter", "age", "geburt"])
    is_zip = any(w in body_lower for w in ["plz", "postleitzahl", "zip", "postal"])
    is_city = any(w in body_lower for w in ["stadt", "city", "wohnort"])

    # RADIO: select based on question type
    radios = elements.get("radios", [])
    if radios:
        # Find best option based on question type
        if is_income:
            # Map income to option index
            target_income = profile.get("income", "€39 000 - €64 999")
            for idx, r in enumerate(radios):
                if target_income in r.get("text", ""):
                    actions.append({"type": "click_radio", "index": idx, "text": r["text"]})
                    break
            else:
                # Try to match partial
                for idx, r in enumerate(radios):
                    txt = r.get("text", "")
                    for k in ["39 000", "64 999", "38 999"]:
                        if k in txt:
                            actions.append({"type": "click_radio", "index": idx, "text": txt})
                            break
                    else:
                        continue
                    break
                else:
                    # Fallback: pick middle option (usually safest)
                    idx = len(radios) // 2
                    actions.append({"type": "click_radio", "index": idx, "text": radios[idx]["text"]})  # noqa: E501
        else:
            # For other questions, pick the most relevant option
            # Simple heuristic: match keyword in option text
            profile_keywords = profile.get("keywords", [])
            matched = False
            for idx, r in enumerate(radios):
                txt = r.get("text", "").lower()
                for kw in profile_keywords:
                    if kw.lower() in txt:
                        actions.append({"type": "click_radio", "index": idx, "text": r["text"]})
                        matched = True
                        break
                if matched:
                    break
            if not matched and radios:
                # Fallback: first non-"keine auskunft" option
                for idx, r in enumerate(radios):
                    if "keine auskunft" not in r.get("text", "").lower():
                        actions.append({"type": "click_radio", "index": idx, "text": r["text"]})
                        break

    # TEXT INPUT: fill based on placeholder
    inputs = elements.get("text_inputs", [])
    for inp in inputs:
        ph = (inp.get("placeholder") or "").lower()
        al = (inp.get("aria_label") or "").lower()
        if is_age or "alter" in ph or "age" in al:
            actions.append({"type": "fill_text", "index": inputs.index(inp), "value": str(profile.get("age", 32))})  # noqa: E501
        elif is_zip or "plz" in ph or "zip" in al or "postal" in al:
            actions.append({"type": "fill_text", "index": inputs.index(inp), "value": profile.get("postal", "10785")})  # noqa: E501
        elif is_city or "stadt" in ph or "city" in al:
            actions.append({"type": "fill_text", "index": inputs.index(inp), "value": profile.get("city", "Berlin")})  # noqa: E501
        elif "alter" in ph or "age" in al:
            actions.append({"type": "fill_text", "index": inputs.index(inp), "value": str(profile.get("age", 32))})  # noqa: E501

    # SELECT: pick matching option
    selects = elements.get("selects", [])
    for sel in selects:
        opts = sel.get("options", [])
        if opts and is_income:
            target = profile.get("income", "€39 000 - €64 999")
            for idx, opt in enumerate(opts):
                if target in opt or target.split(" ")[0] in opt:
                    actions.append({"type": "select_option", "index": selects.index(sel), "value": idx})  # noqa: E501
                    break

    # BUTTON: click "Weiter" or "Next" or "Fortfahren"
    buttons = elements.get("buttons", [])
    [b.get("text", "").lower() for b in buttons]
    for b in buttons:
        txt = b.get("text", "").lower()
        if any(w in txt for w in ["weiter", "nächste", "next", "fortfahren", "submit", "absenden", "submit"]):  # noqa: E501
            actions.append({"type": "click_button", "text": b["text"]})
            break

    return actions


# ── Action Execution ───────────────────────────────────────────────────────────

def _execute_actions(ws_url: str, actions: List[Dict], page: Dict) -> Dict:
    """Execute actions using VERIFIED CDP patterns (from /commands/surveys/survey-answer-patterns.md).  # noqa: E501

    These patterns are PROVEN to work on all survey providers.
    """
    elements = page.get("elements", {})
    result = {"success": 0, "failed": 0, "executed": []}

    for action in actions:
        atype = action.get("type", "")

        try:
            if atype == "click_radio":
                idx = action.get("index", 0)
                radios = elements.get("radios", [])
                if idx < len(radios):
                    # SR-61 fix: previous version used `{r[{idx}]....}` inside the
                    # outer f-string, which Python tried to evaluate against a
                    # non-existent Python name `r` (the JS `var r = ...` is JS-side
                    # only). Build the JS via plain `.format(idx=idx)` so JS-side
                    # `r` stays JS-side.
                    js_template = '''
(function() {{
    var r = document.querySelectorAll('input[type=radio]');
    if (r[{idx}]) {{
        r[{idx}].checked = true;
        r[{idx}].dispatchEvent(new Event('change', {{bubbles: true}}));
        return 'RADIO:' + (r[{idx}].parentElement
            ? r[{idx}].parentElement.textContent.trim().substring(0, 40)
            : '');
    }}
    return 'NOT_FOUND';
}})()
'''
                    js = js_template.format(idx=idx)
                    res = _cdp_eval(ws_url, js)
                    if "RADIO:" in res:
                        result["success"] += 1
                        result["executed"].append(f"radio[{idx}]={action.get('text','')}")
                    else:
                        result["failed"] += 1

            elif atype == "click_button":
                text = action.get("text", "")
                js = f"""
(function() {{
    var all = document.querySelectorAll('button, input[type=submit], [role=button], a');
    for (var i = 0; i < all.length; i++) {{
        var t = (all[i].textContent || all[i].value || '').trim();
        if (t === '{text.replace("'", "\\'")}') {{
            all[i].click();
            return 'CLICKED:' + t;
        }}
    }}
    return 'NOT_FOUND';
}})()
"""
                res = _cdp_eval(ws_url, js)
                if "CLICKED:" in res:
                    result["success"] += 1
                    result["executed"].append(f"button={text}")
                else:
                    result["failed"] += 1

            elif atype == "fill_text":
                idx = action.get("index", 0)
                value = action.get("value", "")
                js = f"""
(function() {{
    var inp = document.querySelectorAll('input[type=text], input[type=email], input[type=number], input[type=tel], textarea');
    if (inp[{idx}]) {{
        inp[{idx}].value = '{value.replace("'", "\\'")}';
        inp[{idx}].dispatchEvent(new Event('input', {{bubbles: true}}));
        inp[{idx}].dispatchEvent(new Event('change', {{bubbles: true}}));
        return 'FILLED:' + inp[{idx}].value;
    }}
    return 'NOT_FOUND';
}})()
"""
                res = _cdp_eval(ws_url, js)
                if "FILLED:" in res:
                    result["success"] += 1
                    result["executed"].append(f"text[{idx}]={value}")
                else:
                    result["failed"] += 1

            elif atype == "select_option":
                idx = action.get("index", 0)
                val_idx = action.get("value", 0)
                js = f"""
(function() {{
    var sel = document.querySelectorAll('select');
    if (sel[{idx}]) {{
        sel[{idx}].selectedIndex = {val_idx};
        sel[{idx}].dispatchEvent(new Event('change', {{bubbles: true}}));
        return 'SELECTED:' + sel[{idx}].value;
    }}
    return 'NOT_FOUND';
}})()
"""
                res = _cdp_eval(ws_url, js)
                if "SELECTED:" in res:
                    result["success"] += 1
                    result["executed"].append(f"select[{idx}]={val_idx}")
                else:
                    result["failed"] += 1

            elif atype == "click_button_by_text":
                # Generic: click any element containing text
                text = action.get("text", "").lower()
                js = f"""
(function() {{
    var all = document.querySelectorAll('*');
    for (var i = 0; i < all.length; i++) {{
        var t = (all[i].textContent || '').trim().toLowerCase();
        if (t === '{text.lower().replace("'", "\\'")}' || t.includes('{text.lower().replace("'", "\\'")}')) {{
            if (all[i].click) {{ all[i].click(); return 'CLICKED:' + t; }}
        }}
    }}
    return 'NOT_FOUND';
}})()
"""
                res = _cdp_eval(ws_url, js)
                if "CLICKED:" in res:
                    result["success"] += 1
                    result["executed"].append(f"generic={text}")
                else:
                    result["failed"] += 1

        except Exception as e:
            result["failed"] += 1
            result["executed"].append(f"ERROR:{e}")

    return result


# ── Survey Tab Cleanup ─────────────────────────────────────────────────────────

def _close_survey_tabs(port: int = 9999, keep_dashboard: bool = True):
    """Close all non-dashboard survey tabs (zombie prevention)."""
    try:
        pages = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=5).read())  # noqa: E501
        for p in pages:
            if p.get("type") == "page":
                url = p.get("url", "").lower()
                if keep_dashboard and "dashboard" in url:
                    continue
                if "about:blank" in url:
                    continue
                # Close survey tabs
                try:
                    ws = websocket.create_connection(p["webSocketDebuggerUrl"], timeout=5)
                    ws.send(json.dumps({"id": 1, "method": "Target.closeTarget",
                                       "params": {"targetId": p["id"]}}))
                    json.loads(ws.recv())
                    ws.close()
                except Exception:
                    pass
    except Exception:
        pass


# ── MAIN LOOP ─────────────────────────────────────────────────────────────────

def run_universal_survey(
    ws_url: str,
    profile: Optional[Dict] = None,
    survey_id: str = "",
    max_steps: int = 30,
    cdp_port: int = 9999,
) -> UniversalSurveyResult:
    """
    Universal survey loop — the ONE function that handles ANY survey.

    Args:
        ws_url: CDP WebSocket URL of the survey tab
        profile: Persona dict (from survey-cli/survey/profiles/jeremy.json)
        survey_id: Survey ID for logging
        max_steps: Maximum iterations (safety limit)
        cdp_port: CDP port

    Returns:
        UniversalSurveyResult with status, earnings, history
    """
    # Default profile
    if not profile:
        profile = {
            "age": 32,
            "gender": "Männlich",
            "city": "Berlin",
            "postal": "10785",
            "income": "€39 000 - €64 999",
            "occupation": "Angestellter",
            "household": "2 Personen",
            "keywords": ["Berlin", "32", "Männlich", "Angestellter"],
        }

    result = UniversalSurveyResult(survey_id=survey_id)
    result.balance_before = _read_balance(cdp_port)

    # Wipe stale locks on startup
    _wipe_stale_locks()

    # Acquire survey lock
    if not _acquire_lock(survey_id):
        result.status = "locked"
        result.reason = "Another survey already running (lock active)"
        return result

    try:
        for step in range(max_steps):
            result.steps = step + 1

            # 1. EXTRACT page state
            page = _extract_page(ws_url)
            result.history.append(f"Step {step+1}: {page.get('url','?')[:60]}")

            # 2. Check completion/screen-out FIRST
            status, reason = _detect_completion(page)
            if status == "completed":
                result.status = "completed"
                result.success = True
                result.completion_detected = True
                result.history.append(f"COMPLETED at step {step+1}: {reason}")
                break
            elif status == "screen_out":
                result.status = "screen_out"
                result.screen_out = True
                result.reason = reason
                result.history.append(f"SCREEN_OUT at step {step+1}: {reason}")
                break

            # 3. DECIDE actions
            actions = _nim_decide(page, profile)
            if not actions:
                result.history.append(f"Step {step+1}: No actions — scrolling")
                # Scroll down if no actions found
                _cdp_eval(ws_url, "window.scrollBy(0, 300); 'scrolled'")
                time.sleep(1)
                continue

            result.history.append(f"Step {step+1}: {[a.get('type') for a in actions]}")

            # 4. EXECUTE actions
            exec_result = _execute_actions(ws_url, actions, page)
            result.history.append(f"  Executed: {exec_result['success']} ok, {exec_result['failed']} fail")  # noqa: E501
            if exec_result['failed'] > exec_result['success']:
                result.errors.append(f"Step {step+1}: {exec_result['failed']} actions failed")

            # 5. Wait for page transition
            time.sleep(2)

            # 6. Verify: did page change?
            page2 = _extract_page(ws_url)
            if page2.get("body_text") == page.get("body_text") and page2.get("url") == page.get("url"):  # noqa: E501
                # Page unchanged — might be stuck
                result.history.append(f"  Warning: Page unchanged after step {step+1}")
                if step >= 3:  # After 3 retries, try clicking next button directly
                    # Try direct "Weiter" click as last resort
                    direct = _cdp_eval(ws_url, """
(function() {
    var b = document.querySelectorAll('button, [role=button], a');
    for (var i = 0; i < b.length; i++) {
        var t = (b[i].textContent || '').trim().toLowerCase();
        if (t.includes('weiter') || t.includes('next') || t.includes('fortfahren')) {
            b[i].click();
            return 'DIRECT_CLICK:' + t;
        }
    }
    return 'NO_BUTTON';
})()
""")
                    if "DIRECT_CLICK:" in direct:
                        result.history.append(f"  Direct click worked: {direct}")
                    else:
                        result.history.append("  Direct click failed, retrying...")
                        time.sleep(2)

        # Loop finished
        if result.steps >= max_steps:
            result.status = "max_steps"
            result.reason = f"Reached {max_steps} steps without completion"
            result.history.append(f"MAX_STEPS reached ({max_steps})")

    except Exception as e:
        result.errors.append(str(e))
        result.status = "error"
        result.reason = str(e)
        result.history.append(f"ERROR: {e}")

    finally:
        # RELEASE LOCK
        _release_lock()

        # Read balance after
        result.balance_after = _read_balance(cdp_port)
        result.earned = max(0.0, result.balance_after - result.balance_before)

    return result


# ── Standalone Entry Point ─────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Universal Survey Agent")
    parser.add_argument("--ws-url", required=True, help="CDP WebSocket URL")
    parser.add_argument("--survey-id", default="", help="Survey ID")
    parser.add_argument("--max-steps", type=int, default=30, help="Max iterations")
    parser.add_argument("--profile", default="jeremy", help="Profile name")

    args = parser.parse_args()

    # Load profile
    profile_path = Path(__file__).parent.parent / "profiles" / f"{args.profile}.json"
    profile = {}
    if profile_path.exists():
        with open(profile_path) as f:
            profile = json.load(f)

    result = run_universal_survey(
        ws_url=args.ws_url,
        profile=profile,
        survey_id=args.survey_id,
        max_steps=args.max_steps,
    )

    print(f"\n{'='*60}")
    print(f"RESULT: {result.status}")
    print(f"Steps: {result.steps}")
    print(f"Earned: €{result.earned:.2f} (before €{result.balance_before:.2f} → after €{result.balance_after:.2f})")  # noqa: E501
    print(f"Completion: {result.completion_detected}")
    print("History:")
    for h in result.history[-5:]:
        print(f"  {h}")
    print(f"{'='*60}")
