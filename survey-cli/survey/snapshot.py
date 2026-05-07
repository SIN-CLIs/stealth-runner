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
    modal_center: Optional[float] = None  # dist to viewport center, null = no modal

    def to_dict(self) -> Dict:
        return asdict(self)


# ── JS Element Extractor ───────────────────────────────

# MODIFIED: Scan ONLY the topmost visible modal overlay.
# Everything outside the active modal is dashboard/background — irrelevant.
# Multiple modals can stack (survey preview + account setup + rating prompt).
# We use element position (z-index, center-point) to find the TOPMOST modal.
ELEMENT_EXTRACTOR_JS = '''
(function(){
    var out = [];
    var seen = new Set();

    // ── Find TOPMOST modal overlay ──────────────────────────────────
    // Strategy: find element whose center is closest to viewport center.
    // The active survey modal will have its center near viewport center,
    // while background modals (rating prompt, account setup) are usually
    // on the sides or off-center.
    function getCenter(el) {
        var r = el.getBoundingClientRect();
        if (!r || r.width === 0 || r.height === 0) return null;
        return {x: r.left + r.width/2, y: r.top + r.height/2};
    }
    function distToCenter(c) {
        var vw = window.innerWidth, vh = window.innerHeight;
        var vc = {x: vw/2, y: vh/2};
        return Math.sqrt((c.x-vc.x)*(c.x-vc.x) + (c.y-vc.y)*(c.y-vc.y));
    }

    var modalCandidates = Array.from(document.querySelectorAll(
        '[class*=modal], [role=dialog], .overlay, .dialog'
    ));
    var topModal = null;
    var bestDist = Infinity;
    modalCandidates.forEach(function(m) {
        var s = window.getComputedStyle(m);
        if (s.display === 'none' || s.visibility === 'hidden') return;
        var c = getCenter(m);
        if (!c) return;
        var d = distToCenter(c);
        if (d < bestDist) { bestDist = d; topModal = m; }
    });

    // Fallback: if no modal found, scan whole document (new-tab survey)
    var scanRoot = topModal || document.body;

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
            inModal: !!topModal,
            y: rect ? Math.round(rect.y) : 0,
        };
        out.push(info);
    }

    // Buttons — ONLY inside topModal (or document body if no modal)
    scanRoot.querySelectorAll('button, input[type=submit], input[type=button], .NextButton, .bsbutton, [role=button]').forEach(function(el) {
        add(el, 'button');
    });

    // Radio buttons
    scanRoot.querySelectorAll('input[type=radio], .cf-radio').forEach(function(el) {
        add(el, el.checked ? 'radio-selected' : 'radio');
    });

    // Checkboxes
    scanRoot.querySelectorAll('input[type=checkbox], .cf-checkbox').forEach(function(el) {
        add(el, el.checked ? 'checkbox-checked' : 'checkbox');
    });

    // Text inputs
    scanRoot.querySelectorAll('input[type=text], input[type=number], input[type=email], input:not([type])').forEach(function(el) {
        add(el, 'textbox');
    });

    // Textareas
    scanRoot.querySelectorAll('textarea').forEach(function(el) {
        if (!el.classList.contains('g-recaptcha-response')) {
            add(el, 'textbox');
        }
    });

    // Selects (Qualtrics language picker, Angular dropdowns)
    scanRoot.querySelectorAll('select').forEach(function(el) {
        add(el, 'select');
    });

    // Qualtrics-specific: LabelWrapper, ChoiceStructure (radio groups)
    scanRoot.querySelectorAll('.LabelWrapper, .ChoiceStructure').forEach(function(el) {
        var inp = el.querySelector('input[type=radio], input[type=checkbox]');
        if (inp) {
            var txt = (el.textContent || '').trim().substring(0, 80);
            out.push({
                role: inp.checked ? 'radio-selected' : 'radio',
                tag: 'div', text: txt, label: '', name: inp.name || '',
                value: inp.value || '', type: 'radio',
                enabled: !inp.disabled, inModal: !!topModal,
            });
        }
    });
    // Qualtrics: ChoiceBody / QuestionBody for radio/text containers
    scanRoot.querySelectorAll('.QuestionBody .ChoiceRow, .ChoiceRow > label').forEach(function(el) {
        var inp = el.querySelector('input[type=radio]');
        if (inp) {
            var txt = (el.textContent || '').trim().substring(0, 80);
            out.push({
                role: inp.checked ? 'radio-selected' : 'radio',
                tag: 'label', text: txt, label: '', name: inp.name || '',
                value: inp.value || '', type: 'radio',
                enabled: !inp.disabled, inModal: !!topModal,
            });
        }
    });

    // Labels (for question detection)
    scanRoot.querySelectorAll('label, .QuestionText, .question-text, legend, strong').forEach(function(el) {
        var t = (el.innerText || el.textContent || '').trim();
        if (t && t.length > 3 && t.length < 200) {
            out.push({
                role: 'label', tag: el.tagName ? el.tagName.toLowerCase() : '',
                text: t, label: '', name: '', value: '', type: '',
                enabled: true, inModal: !!topModal,
            });
        }
    });

    // Sort by Y position (top-to-bottom) so answers come after questions
    out.sort(function(a, b) {
        return (a.y || 0) - (b.y || 0);
    });

    return JSON.stringify({elements: out, modalCenter: bestDist === Infinity ? null : bestDist});
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

    # New format: {elements: [...], modalCenter: number|null}
    # Legacy format: [...] (plain list, old tests) or "[]" (string)
    raw_val = r2.get("result", {}).get("result", {}).get("value", '{"elements":[]}')
    parsed = json.loads(raw_val)
    # Handle legacy list format (old tests) or string "[]"
    if isinstance(parsed, list):
        raw_elements = parsed
        modal_center = None
    elif isinstance(parsed, dict):
        raw_elements = parsed.get("elements", [])
        modal_center = parsed.get("modalCenter")
    else:
        raw_elements = []
        modal_center = None

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
        semantic["in_page_modal"] = modal_center is not None

    url = meta.get("url", "")
    provider = detect_provider(url)
    # In-page modal: URL is always dashboard, provider unknown until survey starts
    if modal_center is not None and provider == "heypiggy":
        provider = "in_page_modal"

    return CompactSnapshot(
        refs=refs,
        semantic=semantic,
        url=url,
        title=meta.get("title", ""),
        provider=provider,
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
        modal_center=modal_center,
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
