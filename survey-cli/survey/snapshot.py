"""Compact DOM Snapshot — @eN token-efficient element references.

Extracts interactive elements via CDP Runtime.evaluate.
Inspired by Vercel agent-browser's compact snapshot format.
"""

import json
import time
import websocket
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from .scanner import detect_provider


@dataclass
class CompactSnapshot:
    """Compact DOM snapshot for LLM consumption."""
    refs: Dict[str, Dict] = field(default_factory=dict)
    semantic: Dict[str, Any] = field(default_factory=dict)
    url: str = ""
    title: str = ""
    provider: str = "unknown"
    timestamp: str = ""

    def to_dict(self) -> Dict:
        return asdict(self)


# ── JS Element Extractor ───────────────────────────────

ELEMENT_EXTRACTOR_JS = '''
(function(){
    var out = [];
    var seen = new Set();

    function add(el, role) {
        if (!el || seen.has(el)) return;
        seen.add(el);
        var rect = el.getBoundingClientRect ? el.getBoundingClientRect() : null;
        var visible = rect && rect.width > 0 && rect.height > 0;
        var info = {
            role: role,
            tag: el.tagName ? el.tagName.toLowerCase() : '',
            text: (el.innerText || el.textContent || el.value || '').substring(0, 80).trim(),
            label: (el.getAttribute('aria-label') || el.getAttribute('placeholder') || '').substring(0, 80),
            name: (el.getAttribute('name') || '').substring(0, 60),
            value: el.value || '',
            type: el.type || '',
            enabled: !el.disabled && visible,
        };
        out.push(info);
    }

    // Buttons
    document.querySelectorAll('button, input[type=submit], input[type=button], .NextButton, .bsbutton, [role=button]').forEach(function(el) {
        add(el, 'button');
    });

    // Radio buttons
    document.querySelectorAll('input[type=radio], .cf-radio').forEach(function(el) {
        add(el, el.checked ? 'radio-selected' : 'radio');
    });

    // Checkboxes
    document.querySelectorAll('input[type=checkbox], .cf-checkbox').forEach(function(el) {
        add(el, el.checked ? 'checkbox-checked' : 'checkbox');
    });

    // Text inputs
    document.querySelectorAll('input[type=text], input[type=number], input[type=email], input:not([type])').forEach(function(el) {
        add(el, 'textbox');
    });

    // Textareas
    document.querySelectorAll('textarea').forEach(function(el) {
        if (!el.classList.contains('g-recaptcha-response')) {
            add(el, 'textbox');
        }
    });

    // Selects
    document.querySelectorAll('select').forEach(function(el) {
        add(el, 'select');
    });

    // Labels (for question detection)
    document.querySelectorAll('label, .QuestionText, .question-text, legend, strong').forEach(function(el) {
        var t = (el.innerText || el.textContent || '').trim();
        if (t && t.length > 3 && t.length < 200) {
            out.push({
                role: 'label', tag: el.tagName ? el.tagName.toLowerCase() : '',
                text: t, label: '', name: '', value: '', type: '',
                enabled: true,
            });
        }
    });

    return JSON.stringify(out);
})()
'''


# ── Generator ──────────────────────────────────────────

def generate_snapshot(ws_url, include_semantic=True):
    """Generate compact snapshot from CDP WebSocket URL.

    Args:
        ws_url: CDP WebSocket debugger URL
        include_semantic: Whether to extract semantic info

    Returns:
        CompactSnapshot with @eN refs
    """
    ws = websocket.create_connection(ws_url, timeout=15)

    # Get page metadata
    ws.send(json.dumps({
        "id": 0, "method": "Runtime.evaluate",
        "params": {
            "expression": "(function(){return JSON.stringify({url:document.location.href,title:document.title,innerText:document.body.innerText.substring(0,500)});})()"
        }
    }))
    r = json.loads(ws.recv())
    meta = json.loads(r.get("result", {}).get("result", {}).get("value", "{}"))

    # Extract elements
    ws.send(json.dumps({
        "id": 1, "method": "Runtime.evaluate",
        "params": {"expression": ELEMENT_EXTRACTOR_JS}
    }))
    r2 = json.loads(ws.recv())
    ws.close()

    raw_elements = json.loads(
        r2.get("result", {}).get("result", {}).get("value", "[]")
    )

    # Build @eN refs
    refs = {}
    for i, el in enumerate(raw_elements):
        refs[f"@e{i}"] = {
            "role": el.get("role", "unknown"),
            "text": el.get("text", ""),
            "label": el.get("label", ""),
            "name": el.get("name", ""),
            "tag": el.get("tag", ""),
            "type": el.get("type", ""),
            "enabled": el.get("enabled", True),
        }

    # Semantic info
    semantic = {}
    if include_semantic:
        semantic["questions"] = _detect_questions(raw_elements)
        semantic["progress"] = _detect_progress(raw_elements)
        semantic["buttons"] = [
            e.get("text") for e in raw_elements
            if e.get("role") == "button" and e.get("text")
        ][:5]

    url = meta.get("url", "")
    provider = detect_provider(url)

    return CompactSnapshot(
        refs=refs,
        semantic=semantic,
        url=url,
        title=meta.get("title", ""),
        provider=provider,
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
    )


# ── Helpers ────────────────────────────────────────────

def _detect_questions(elements):
    """Extract question texts."""
    questions = []
    for el in elements:
        if el.get("role") == "label":
            text = el.get("text", "").strip()
            if text and len(text) > 5 and "powered by" not in text.lower():
                questions.append(text)
    return questions


def _detect_progress(elements):
    """Detect survey progress."""
    for el in elements:
        text = el.get("text", "")
        if "%" in text and any(c.isdigit() for c in text):
            return text.strip()
    return "?"


def detect_completion(text):
    """SOTA: Check if survey is completed based on page text.

    Provider-specific completion patterns (2026-05-06):
    - German surveys: heypiggy, Samplicio DE
    - English surveys: Qualtrics, Toluna, Cint, PureSpectrum
    - All major panel providers covered
    """
    text_lower = text.lower()

    # ✅ SURVEY COMPLETED — all providers
    completion_markers = [
        # German
        "zurück zur website", "zurück zur umfrage", "gutgeschrieben",
        "guthaben wurde", "vielen dank", "danke für", "umfrage beendet",
        "abgeschlossen", "erfolgreich", "ausgefüllt",
        # English (Qualtrics, Toluna, Cint, PureSpectrum, Samplicio)
        "thank you for completing", "thank you for your",
        "survey complete", "completed the survey", "successfully submitted",
        "your response has been recorded", "you have completed",
        "points have been credited", "points credited", "reward credited",
        "thank you for participating", "thanks for completing",
        "your submission", "submitted successfully",
        "finished", "complete!", "completed!",
        # Progress/checking
        "finished checking", "survey has ended",
    ]
    for m in completion_markers:
        if m in text_lower:
            return True

    return False


def detect_progress(text: str) -> Tuple[bool, str]:
    """SOTA: Detect survey progress state.

    Returns (progressed, status):
    - ('advanced', 'progressed') = page advanced to next question
    - ('stuck', reason) = page is stuck or regressed
    - ('loading', 'loading') = page still loading
    - ('error', 'error_page') = error screen-out page
    - ('captcha', 'captcha') = captcha detected
    """
    text_lower = text.lower()

    # Check for error pages first
    error_markers = [
        "screen out", "you do not qualify", "not eligible",
        "no app id was specified", "unable to start survey",
        "survey has ended", "survey closed", "link expired",
        "leider ist ein fehler", "error occurred",
        "thank you for your interest",
    ]
    for m in error_markers:
        if m in text_lower:
            return False, "error_page"

    # Loading indicators
    loading_markers = ["loading", "just getting things ready", "won't be long",
                       "bitte warten", "wird geladen", "please wait"]
    for m in loading_markers:
        if m in text_lower:
            return False, "loading"

    # Captcha
    captcha_markers = ["captcha", "ich bin kein roboter", "i am not a robot",
                       "not a robot", "human check", "human verification"]
    for m in captcha_markers:
        if m in text_lower:
            return False, "captcha"

    # Progress bar (common in Qualtrics, Cint)
    progress_patterns = [
        r"(\d+)\s*/\s*\d+",  # "3/10" progress
        r"fortschritt.*?(\d+)%",  # German progress
        r"progress.*?(\d+)%",
        r"[████░░░░▓▓▒]",
    ]
    for pat in progress_patterns:
        if re.search(pat, text_lower):
            return True, "progressed"

    # Question indicators (page advanced)
    question_markers = [
        "wie", "was", "wann", "warum",  # German question words
        "how often", "how many", "do you", "would you", "please select",
        "bitte auswählen", "stimmen sie zu", "meinungen",
        "radio", "checkbox", "submit", "next", "weiter",
    ]
    question_count = sum(1 for m in question_markers if m in text_lower)
    if question_count >= 2:
        return True, "progressed"

    return True, "unknown"
