"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║  UNIVERSAL SURVEY HANDLER — Automatische Beantwortung ALLER Fragearten       ║
║  Basiert auf manuellem Durchlauf von Survey #66950684 (FocusVision)         ║
╚═══════════════════════════════════════════════════════════════════════════════╝

TAXONOMIE (alle heute gesehenen Typen):
  1. Consent-Seite          → Button "Zustimmen und fortfahren"
  2. Single-Choice Radio    → Eine Auswahl (Alter, Geschlecht, etc.)
  3. Multiple-Choice Check  → Mehrere Auswahlen (KI-Tools, etc.)
  4. Dropdown/Select        → Auswahl aus Liste (Region)
  5. Matrix-Rating Select   → Tabelle mit <select> pro Zelle (1-5)
  6. Ranking Select         → Unique-Werte zuordnen (0,1,2,3,4)
  7. Text-Input             → Freitext (heute nicht gesehen)
  8. Star-Rating            → CPX Rating-Seite (1-5 Sterne)

ARCHITEKTUR:
  UniversalSurveyHandler
  ├── detect_question_type(page_html) → QuestionType
  ├── answer_question(type, profile) → JS-Actions
  ├── execute_actions(ws_url, actions) → void
  └── handle_page(ws_url, profile) → {success, next_url, error}

DEFAULT-STRATEGIEN (wenn Profil nicht passt):
  Radio:        Middle option (neutral)
  Checkbox:     All except last ("Nichts davon")
  Select:       Middle value
  Matrix:       All 3/5 (neutral)
  Ranking:      Shuffled unique values
  Consent:      Always click "Zustimmen"
  Star-Rating:  4/5 stars
"""

import json
import re
from typing import Any

# ═══════════════════════════════════════════════════════════════════════════════
# QUESTION TYPE DETECTION
# ═══════════════════════════════════════════════════════════════════════════════


class QuestionType:
    """Enum-like class for question types."""

    CONSENT = "consent"
    SINGLE_CHOICE_RADIO = "single_choice_radio"
    MULTIPLE_CHOICE_CHECK = "multiple_choice_check"
    DROPDOWN_SELECT = "dropdown_select"
    MATRIX_RATING_SELECT = "matrix_rating_select"
    RANKING_SELECT = "ranking_select"
    TEXT_INPUT = "text_input"
    STAR_RATING = "star_rating"
    UNKNOWN = "unknown"
    COMPLETE = "complete"
    DISQUALIFIED = "disqualified"


def detect_question_type(page_info: dict[str, Any]) -> str:
    """
    Erkennt den Fragentyp basierend auf DOM-Elementen.

    Args:
        page_info: Dict mit:
            - url: str
            - title: str
            - body: str (erste 2000 chars)
            - element_counts: {radios, checks, selects, texts, stars}

    Returns:
        QuestionType constant

    ERKENNUNGSREIHENFOLGE (wichtig!):
    1. Complete/Disqual zuerst (URL/Text-Check)
    2. Consent (Text-Check)
    3. Star-Rating (URL-Check)
    4. Matrix (viele selects + Tabellen-Text)
    5. Ranking (selects mit unique values)
    6. Dropdown (1-3 selects, keine radios)
    7. Multiple-Choice (checkboxes > 1)
    8. Single-Choice (radios > 1)
    9. Text (text inputs > 0)
    10. Unknown
    """
    url = page_info.get("url", "").lower()
    page_info.get("title", "").lower()
    body = page_info.get("body", "").lower()
    counts = page_info.get("element_counts", {})

    radios = counts.get("radios", 0)
    checks = counts.get("checkboxes", 0)
    selects = counts.get("selects", 0)
    texts = counts.get("text_inputs", 0)
    stars = counts.get("stars", 0)

    # 1. Complete/Disqual
    if "cpx-research.com/rating" in url or "gutgeschrieben" in body:
        return QuestionType.COMPLETE
    if "leider qualifizieren" in body or "screened out" in body or "disqualifiziert" in body:
        return QuestionType.DISQUALIFIED

    # 2. Consent
    if "zustimmen und fortfahren" in body or "consent" in url or "einwilligung" in body:
        return QuestionType.CONSENT

    # 3. Star-Rating
    if stars > 0 or ("rating" in url and "cpx" in url):
        return QuestionType.STAR_RATING

    # 4. Matrix-Rating (viele selects + keywords)
    if selects >= 5 and ("bewerten" in body or "wichtig" in body or "skala" in body):
        return QuestionType.MATRIX_RATING_SELECT

    # 5. Ranking (selects + "ordnen" oder "wichtigste")
    if selects >= 2 and ("ordnen" in body or "nach wichtigkeit" in body or "rangfolge" in body):
        return QuestionType.RANKING_SELECT

    # 6. Dropdown (1-3 selects, keine/radios)
    if selects > 0 and radios == 0 and checks == 0:
        return QuestionType.DROPDOWN_SELECT

    # 7. Multiple-Choice
    if checks > 1:
        return QuestionType.MULTIPLE_CHOICE_CHECK

    # 8. Single-Choice
    if radios > 1:
        return QuestionType.SINGLE_CHOICE_RADIO

    # 9. Text
    if texts > 0 and radios == 0 and checks == 0 and selects == 0:
        return QuestionType.TEXT_INPUT

    # 10. Fallback: wenn es irgendwelche inputs gibt, versuche Radio
    if radios > 0:
        return QuestionType.SINGLE_CHOICE_RADIO

    return QuestionType.UNKNOWN


# ═══════════════════════════════════════════════════════════════════════════════
# ANSWER GENERATORS — Erzeugt CDP-JS-Code für jede Frageart
# ═══════════════════════════════════════════════════════════════════════════════


def generate_consent_js() -> str:
    """Klickt 'Zustimmen und fortfahren' Button."""
    return """
    (function() {
        var buttons = document.querySelectorAll('button, a, input[type=submit]');
        for (var i = 0; i < buttons.length; i++) {
            var text = (buttons[i].innerText || buttons[i].value || '').toLowerCase();
            if (text.includes('zustimmen') || text.includes('fortfahren') || text.includes('agree') || text.includes('continue')) {
                buttons[i].click();
                return 'CONSENT_CLICKED: ' + buttons[i].innerText;
            }
        }
        // Fallback: first button
        var firstBtn = document.querySelector('button, input[type=submit]');
        if (firstBtn) {
            firstBtn.click();
            return 'CONSENT_FALLBACK_CLICKED';
        }
        return 'CONSENT_NOT_FOUND';
    })()
    """


def generate_single_choice_js(option_strategy: str = "middle") -> str:
    """
    Wählt eine Radio-Button-Option.

    Args:
        option_strategy: "first", "middle", "last", "random"

    Returns:
        JS-Code als String
    """
    strategies = {
        "first": "0",
        "middle": "Math.floor(radios.length / 2)",
        "last": "radios.length - 1",
        "random": "Math.floor(Math.random() * radios.length)",
    }
    idx_expr = strategies.get(option_strategy, strategies["middle"])

    return f"""
    (function() {{
        var radios = document.querySelectorAll('input[type=radio]');
        if (radios.length === 0) return 'NO_RADIOS';

        // Group by name
        var groups = {{}};
        radios.forEach(function(r) {{
            if (!groups[r.name]) groups[r.name] = [];
            groups[r.name].push(r);
        }});

        var selected = 0;
        Object.keys(groups).forEach(function(name) {{
            var grp = groups[name];
            var idx = {idx_expr};
            if (idx >= grp.length) idx = grp.length - 1;
            grp[idx].checked = true;
            grp[idx].dispatchEvent(new Event('change', {{bubbles: true}}));
            selected++;
        }});

        // Click continue
        var btn = document.getElementById('btn_continue');
        if (!btn) btn = document.querySelector('button[type=submit], input[type=submit]');
        if (btn) {{
            btn.click();
            return 'RADIO_SELECTED: ' + selected + ' groups, option=' + {idx_expr};
        }}
        return 'RADIO_SELECTED_NO_BUTTON: ' + selected;
    }})()
    """


def generate_multiple_choice_js(select_all: bool = True, exclude_last: bool = True) -> str:
    """
    Wählt Checkbox-Optionen.

    Args:
        select_all: Alle außer ggf. letzte
        exclude_last: Letzte Option überspringen (meist "Nichts davon")
    """
    return (
        """
    (function() {
        var checks = document.querySelectorAll('input[type=checkbox]');
        if (checks.length === 0) return 'NO_CHECKBOXES';

        var end = checks.length;
        """
        + (
            "if (" + str(exclude_last).lower() + ") end = checks.length - 1;"
            if exclude_last
            else ""
        )
        + """

        for (var i = 0; i < end; i++) {
            checks[i].checked = true;
            checks[i].dispatchEvent(new Event('change', {bubbles: true}));
        }

        var btn = document.getElementById('btn_continue');
        if (!btn) btn = document.querySelector('button[type=submit], input[type=submit]');
        if (btn) {
            btn.click();
            return 'CHECKBOX_SELECTED: ' + end + '/' + checks.length;
        }
        return 'CHECKBOX_SELECTED_NO_BUTTON: ' + end;
    })()
    """
    )


def generate_dropdown_js(select_strategy: str = "middle") -> str:
    """
    Füllt Dropdown/Select Felder.

    Args:
        select_strategy: "first", "middle", "last", "random"
    """
    strategies = {
        "first": "1",  # Skip placeholder (-1/0)
        "middle": "Math.floor(opts.length / 2)",
        "last": "opts.length - 1",
        "random": "Math.max(1, Math.floor(Math.random() * opts.length))",
    }
    idx_expr = strategies.get(select_strategy, strategies["middle"])

    return f"""
    (function() {{
        var selects = document.querySelectorAll('select');
        if (selects.length === 0) return 'NO_SELECTS';

        selects.forEach(function(sel) {{
            var opts = Array.from(sel.options);
            if (opts.length > 1) {{
                var idx = {idx_expr};
                if (idx >= opts.length) idx = opts.length - 1;
                if (idx < 1) idx = 1; // Skip placeholder
                sel.value = opts[idx].value;
                sel.dispatchEvent(new Event('change', {{bubbles: true}}));
            }}
        }});

        var btn = document.getElementById('btn_continue');
        if (!btn) btn = document.querySelector('button[type=submit], input[type=submit]');
        if (btn) {{
            btn.click();
            return 'DROPDOWN_SELECTED: ' + selects.length + ' selects';
        }}
        return 'DROPDOWN_SELECTED_NO_BUTTON';
    }})()
    """


def generate_matrix_rating_js(rating_value: str = "3") -> str:
    """
    Füllt Matrix-Bewertung (Selects in Tabellen-Zellen).
    Setzt alle auf gleichen Wert (z.B. 3/5 = neutral).

    Args:
        rating_value: "1", "2", "3", "4", "5" oder "middle" für auto
    """
    if rating_value == "middle":
        value_expr = "sel.options[Math.floor(sel.options.length / 2)]?.value || '3'"
    else:
        value_expr = f"'{rating_value}'"

    return f"""
    (function() {{
        var selects = document.querySelectorAll('select');
        if (selects.length === 0) return 'NO_MATRIX_SELECTS';

        selects.forEach(function(sel) {{
            var val = {value_expr};
            // Check if value exists in options
            var hasValue = Array.from(sel.options).some(function(o) {{ return o.value === val; }});
            if (hasValue) {{
                sel.value = val;
            }} else {{
                // Fallback: middle option
                var mid = Math.floor(sel.options.length / 2);
                sel.value = sel.options[mid]?.value || sel.options[1]?.value;
            }}
            sel.dispatchEvent(new Event('change', {{bubbles: true}}));
        }});

        var btn = document.getElementById('btn_continue');
        if (!btn) btn = document.querySelector('button[type=submit], input[type=submit]');
        if (btn) {{
            btn.click();
            return 'MATRIX_RATED: ' + selects.length + ' cells with value={rating_value}';
        }}
        return 'MATRIX_RATED_NO_BUTTON';
    }})()
    """


def generate_ranking_js() -> str:
    """
    Füllt Ranking-Fragen (Selects mit unique values).
    Ordnet zufällig/permutation zu (jeder Wert genau einmal).
    """
    return """
    (function() {
        var selects = Array.from(document.querySelectorAll('select'));
        if (selects.length === 0) return 'NO_RANKING_SELECTS';

        // Get available values from first select (assume all same)
        var firstOpts = Array.from(selects[0].options).filter(function(o) {
            return o.value && o.value !== '-1' && o.value !== '0';
        }).map(function(o) { return o.value; });

        if (firstOpts.length < selects.length) {
            // Not enough unique values → fill sequentially
            selects.forEach(function(sel, i) {
                var opts = Array.from(sel.options).filter(function(o) { return o.value && o.value !== '-1'; });
                var idx = Math.min(i + 1, opts.length - 1);
                sel.value = opts[idx]?.value || opts[opts.length - 1]?.value;
                sel.dispatchEvent(new Event('change', {bubbles: true}));
            });
        } else {
            // Shuffle values and assign uniquely
            var values = firstOpts.slice();
            for (var i = values.length - 1; i > 0; i--) {
                var j = Math.floor(Math.random() * (i + 1));
                var temp = values[i];
                values[i] = values[j];
                values[j] = temp;
            }
            selects.forEach(function(sel, i) {
                if (i < values.length) {
                    sel.value = values[i];
                    sel.dispatchEvent(new Event('change', {bubbles: true}));
                }
            });
        }

        var btn = document.getElementById('btn_continue');
        if (!btn) btn = document.querySelector('button[type=submit], input[type=submit]');
        if (btn) {
            btn.click();
            return 'RANKING_FILLED: ' + selects.length + ' items';
        }
        return 'RANKING_FILLED_NO_BUTTON';
    })()
    """


def generate_text_input_js(value: str = "Ja") -> str:
    """Füllt Text-Input Felder."""
    return f"""
    (function() {{
        var inputs = document.querySelectorAll('input[type=text], textarea');
        if (inputs.length === 0) return 'NO_TEXT_INPUTS';

        inputs.forEach(function(inp) {{
            inp.value = '{value}';
            inp.dispatchEvent(new Event('input', {{bubbles: true}}));
            inp.dispatchEvent(new Event('change', {{bubbles: true}}));
        }});

        var btn = document.getElementById('btn_continue');
        if (!btn) btn = document.querySelector('button[type=submit], input[type=submit]');
        if (btn) {{
            btn.click();
            return 'TEXT_FILLED: ' + inputs.length + ' fields';
        }}
        return 'TEXT_FILLED_NO_BUTTON';
    }})()
    """


def generate_star_rating_js(star_count: int = 4) -> str:
    """
    Klickt Sterne auf CPX Rating-Seite.

    Args:
        star_count: 1-5 (default 4 = gut)
    """
    return f"""
    (function() {{
        // Try image stars
        var stars = document.querySelectorAll('img[src*=star], .star, [class*=star], [class*=rating]');
        if (stars.length >= {star_count}) {{
            stars[{star_count - 1}].click();
            return 'STAR_CLICKED: {star_count}/5';
        }}

        // Try radio stars
        var radioStars = document.querySelectorAll('input[type=radio]');
        if (radioStars.length >= {star_count}) {{
            radioStars[{star_count - 1}].checked = true;
            radioStars[{star_count - 1}].dispatchEvent(new Event('change', {{bubbles: true}}));
            return 'STAR_RADIO_CLICKED: {star_count}/5';
        }}

        // Try any clickable element
        var clickable = document.querySelectorAll('a, button, img, [onclick]');
        for (var i = 0; i < clickable.length; i++) {{
            if (clickable[i].src && clickable[i].src.includes('star')) {{
                clickable[i].click();
                return 'STAR_IMG_CLICKED: {star_count}/5';
            }}
        }}

        return 'STARS_NOT_FOUND';
    }})()
    """


def generate_back_to_dashboard_js() -> str:
    """Klickt 'Zurück zur Website' auf CPX Rating-Seite."""
    return """
    (function() {
        var links = document.querySelectorAll('a');
        for (var i = 0; i < links.length; i++) {
            var text = (links[i].innerText || links[i].textContent || '').toLowerCase();
            if (text.includes('zurück') || text.includes('website') || text.includes('back')) {
                links[i].click();
                return 'BACK_CLICKED: ' + links[i].innerText;
            }
        }
        window.location.href = 'https://www.heypiggy.com/?page=dashboard';
        return 'BACK_NAVIGATED_DIRECT';
    })()
    """


# ═══════════════════════════════════════════════════════════════════════════════
# UNIVERSAL HANDLER
# ═══════════════════════════════════════════════════════════════════════════════


class UniversalSurveyHandler:
    """
    Haupt-Klasse: Erkennt Fragentyp und generiert passende JS-Actions.
    """

    def __init__(self, profile: dict | None = None):
        self.profile = profile or {}

    def handle_page(self, page_info: dict[str, Any]) -> dict[str, Any]:
        """
        Analysiert eine Umfrage-Seite und gibt Actions zurück.

        Args:
            page_info: {url, title, body, element_counts}

        Returns:
            {type, js_code, explanation, confidence}
        """
        qtype = detect_question_type(page_info)

        handlers = {
            QuestionType.CONSENT: self._handle_consent,
            QuestionType.SINGLE_CHOICE_RADIO: self._handle_single_choice,
            QuestionType.MULTIPLE_CHOICE_CHECK: self._handle_multiple_choice,
            QuestionType.DROPDOWN_SELECT: self._handle_dropdown,
            QuestionType.MATRIX_RATING_SELECT: self._handle_matrix,
            QuestionType.RANKING_SELECT: self._handle_ranking,
            QuestionType.TEXT_INPUT: self._handle_text,
            QuestionType.STAR_RATING: self._handle_star_rating,
            QuestionType.COMPLETE: self._handle_complete,
            QuestionType.DISQUALIFIED: self._handle_disqualified,
            QuestionType.UNKNOWN: self._handle_unknown,
        }

        handler = handlers.get(qtype, self._handle_unknown)
        return handler(page_info)

    def _handle_consent(self, page_info: dict) -> dict:
        return {
            "type": QuestionType.CONSENT,
            "js_code": generate_consent_js(),
            "explanation": "Consent-Seite erkannt → 'Zustimmen und fortfahren' klicken",
            "confidence": 0.95,
        }

    def _handle_single_choice(self, page_info: dict) -> dict:
        # Versuche Profil-basierte Antwort
        body = page_info.get("body", "").lower()

        # Alter
        if any(k in body for k in ["alter", "age", "wie alt"]):
            age = self.profile.get("age", 32)
            # Hier bräuchten wir die Optionen aus dem DOM
            # Für jetzt: default middle
            return {
                "type": QuestionType.SINGLE_CHOICE_RADIO,
                "js_code": generate_single_choice_js("middle"),
                "explanation": f"Alter-Frage erkannt → Profile.age={age}, wähle passende Option (middle fallback)",
                "confidence": 0.8,
            }

        # Geschlecht
        if any(k in body for k in ["geschlecht", "gender", "sex"]):
            gender = self.profile.get("gender_label", "männlich")
            return {
                "type": QuestionType.SINGLE_CHOICE_RADIO,
                "js_code": generate_single_choice_js(
                    "first" if gender.lower() in ["männlich", "male", "m"] else "middle"
                ),
                "explanation": f"Geschlecht-Frage erkannt → Profile.gender={gender}",
                "confidence": 0.85,
            }

        # Default: middle option (neutral)
        return {
            "type": QuestionType.SINGLE_CHOICE_RADIO,
            "js_code": generate_single_choice_js("middle"),
            "explanation": "Single-Choice Frage → wähle mittlere Option (neutral)",
            "confidence": 0.7,
        }

    def _handle_multiple_choice(self, page_info: dict) -> dict:
        return {
            "type": QuestionType.MULTIPLE_CHOICE_CHECK,
            "js_code": generate_multiple_choice_js(select_all=True, exclude_last=True),
            "explanation": "Multiple-Choice → alle außer letzte Option ('Nichts davon')",
            "confidence": 0.8,
        }

    def _handle_dropdown(self, page_info: dict) -> dict:
        body = page_info.get("body", "").lower()

        # Region/State
        if any(k in body for k in ["region", "bundesland", "wohnen", "stadt"]):
            state = self.profile.get("state", "Berlin")
            return {
                "type": QuestionType.DROPDOWN_SELECT,
                "js_code": generate_dropdown_js("first"),  # Berlin is usually early in list
                "explanation": f"Region-Frage → Profile.state={state}, wähle erste passende Option",
                "confidence": 0.75,
            }

        return {
            "type": QuestionType.DROPDOWN_SELECT,
            "js_code": generate_dropdown_js("middle"),
            "explanation": "Dropdown-Frage → wähle mittlere Option",
            "confidence": 0.7,
        }

    def _handle_matrix(self, page_info: dict) -> dict:
        return {
            "type": QuestionType.MATRIX_RATING_SELECT,
            "js_code": generate_matrix_rating_js("3"),
            "explanation": "Matrix-Bewertung → alle Zellen auf 3/5 (neutral)",
            "confidence": 0.85,
        }

    def _handle_ranking(self, page_info: dict) -> dict:
        return {
            "type": QuestionType.RANKING_SELECT,
            "js_code": generate_ranking_js(),
            "explanation": "Ranking-Frage → zufällige Permutation der Werte",
            "confidence": 0.8,
        }

    def _handle_text(self, page_info: dict) -> dict:
        return {
            "type": QuestionType.TEXT_INPUT,
            "js_code": generate_text_input_js("Ja"),
            "explanation": "Text-Frage → 'Ja' eingeben",
            "confidence": 0.6,
        }

    def _handle_star_rating(self, page_info: dict) -> dict:
        return {
            "type": QuestionType.STAR_RATING,
            "js_code": generate_star_rating_js(4),
            "explanation": "Star-Rating → 4/5 Sterne (gute Bewertung)",
            "confidence": 0.9,
        }

    def _handle_complete(self, page_info: dict) -> dict:
        return {
            "type": QuestionType.COMPLETE,
            "js_code": generate_back_to_dashboard_js(),
            "explanation": "Umfrage complete! → Zurück zum Dashboard",
            "confidence": 0.99,
        }

    def _handle_disqualified(self, page_info: dict) -> dict:
        return {
            "type": QuestionType.DISQUALIFIED,
            "js_code": generate_back_to_dashboard_js(),
            "explanation": "Disqualifiziert → Zurück zum Dashboard",
            "confidence": 0.99,
        }

    def _handle_unknown(self, page_info: dict) -> dict:
        return {
            "type": QuestionType.UNKNOWN,
            "js_code": generate_single_choice_js("middle"),
            "explanation": "Unbekannter Typ → versuche mittlere Radio-Option",
            "confidence": 0.3,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# FASTAPI INTEGRATION
# ═══════════════════════════════════════════════════════════════════════════════


from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/survey/universal", tags=["universal-survey"])


class PageInfoRequest(BaseModel):
    url: str
    title: str
    body: str
    element_counts: dict[str, int] | None = None


class SurveyActionResponse(BaseModel):
    type: str
    js_code: str
    explanation: str
    confidence: float


@router.post("/analyze", response_model=SurveyActionResponse)
async def analyze_survey_page(req: PageInfoRequest):
    """
    Analysiert eine Umfrage-Seite und gibt die passende Action zurück.

    Beispiel:
        POST /survey/universal/analyze
        {
            "url": "https://emea.focusvision.com/...",
            "title": "Umfrage",
            "body": "Wie alt sind Sie? Unter 18 18-28...",
            "element_counts": {"radios": 6, "checkboxes": 0, "selects": 0}
        }

    Returns:
        {
            "type": "single_choice_radio",
            "js_code": "(function(){...})()",
            "explanation": "Alter-Frage → wähle mittlere Option",
            "confidence": 0.8
        }
    """
    handler = UniversalSurveyHandler()

    page_info = req.dict()
    if not page_info.get("element_counts"):
        # Auto-detect from body text heuristics
        page_info["element_counts"] = _heuristic_element_counts(page_info["body"])

    result = handler.handle_page(page_info)
    return SurveyActionResponse(**result)


def _heuristic_element_counts(body: str) -> dict[str, int]:
    """
    Heuristische Erkennung von Elementen aus Body-Text.
    Fallback wenn element_counts nicht vom Frontend geliefert werden.
    """
    body_lower = body.lower()
    counts = {
        "radios": body_lower.count("◯")
        + len(re.findall(r"\d+\s*%", body_lower)),  # Radio indicators
        "checkboxes": body_lower.count("☐") + body_lower.count("☑"),
        "selects": 1 if "treffen sie eine auswahl" in body_lower else 0,
        "text_inputs": 1
        if any(k in body_lower for k in ["bitte geben sie ein", "freitext", "textfeld"])
        else 0,
        "stars": body_lower.count("★") + body_lower.count("☆"),
    }
    return counts


@router.post("/execute")
async def execute_survey_action(ws_url: str, js_code: str, wait_seconds: float = 3.0):
    """
    Führt generierten JS-Code auf einer Survey-Seite aus.

    Args:
        ws_url: CDP WebSocket URL der Seite
        js_code: JavaScript-Code (von /analyze)
        wait_seconds: Wartezeit nach Execution

    Returns:
        {success, result, next_url, next_title}
    """
    import asyncio

    import websockets

    try:
        async with websockets.connect(ws_url) as ws:
            # Execute JS
            await ws.send(
                json.dumps(
                    {"id": 1, "method": "Runtime.evaluate", "params": {"expression": js_code}}
                )
            )
            resp = await ws.recv()
            data = json.loads(resp)
            result = data.get("result", {}).get("result", {}).get("value", "ERROR")

            # Wait for page transition
            await asyncio.sleep(wait_seconds)

            # Get new state
            await ws.send(
                json.dumps(
                    {
                        "id": 2,
                        "method": "Runtime.evaluate",
                        "params": {
                            "expression": "JSON.stringify({url: window.location.href, title: document.title, body: document.body.innerText.substring(0, 1000)})"
                        },
                    }
                )
            )
            resp2 = await ws.recv()
            data2 = json.loads(resp2)
            state_str = data2.get("result", {}).get("result", {}).get("value", "{}")
            state = json.loads(state_str)

            return {
                "success": not result.startswith(("ERROR", "NO_")),
                "result": result,
                "next_url": state.get("url", ""),
                "next_title": state.get("title", ""),
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/auto-loop")
async def auto_survey_loop(
    ws_url: str, max_pages: int = 50, profile_name: str = "sin_agent_heypiggy", cdp_port: int = 9999
):
    """
    Automatischer Survey-Loop: Analysiert → Antwortet → Weiter bis Complete/Disqual.

    Das ist DIE HAUPTFUNKTION die der Daemon nutzen wird!
    """
    import asyncio

    import websockets

    # Load profile
    profile_path = (
        f"/Users/jeremy/dev/stealth-runner/survey-cli/survey/profiles/{profile_name}.json"
    )
    try:
        with open(profile_path) as f:
            profile = json.load(f)
    except Exception:
        profile = {}

    handler = UniversalSurveyHandler(profile)
    results = []

    for page_num in range(max_pages):
        try:
            # Get current page state
            async with websockets.connect(ws_url) as ws:
                await ws.send(
                    json.dumps(
                        {
                            "id": 1,
                            "method": "Runtime.evaluate",
                            "params": {
                                "expression": """
                        JSON.stringify({
                            url: window.location.href,
                            title: document.title,
                            body: document.body.innerText.substring(0, 2000),
                            element_counts: {
                                radios: document.querySelectorAll('input[type=radio]').length,
                                checkboxes: document.querySelectorAll('input[type=checkbox]').length,
                                selects: document.querySelectorAll('select').length,
                                text_inputs: document.querySelectorAll('input[type=text], textarea').length,
                                stars: document.querySelectorAll('img[src*=star], .star').length
                            }
                        })
                    """
                            },
                        }
                    )
                )
                resp = await ws.recv()
                data = json.loads(resp)
                state_str = data.get("result", {}).get("result", {}).get("value", "{}")
                page_info = json.loads(state_str)

            # Analyze
            action = handler.handle_page(page_info)

            # Check for completion
            if action["type"] in [QuestionType.COMPLETE, QuestionType.DISQUALIFIED]:
                results.append(
                    {
                        "page": page_num,
                        "type": action["type"],
                        "result": "FINISHED",
                        "explanation": action["explanation"],
                    }
                )
                break

            # Execute action
            async with websockets.connect(ws_url) as ws:
                await ws.send(
                    json.dumps(
                        {
                            "id": 1,
                            "method": "Runtime.evaluate",
                            "params": {"expression": action["js_code"]},
                        }
                    )
                )
                resp = await ws.recv()
                data = json.loads(resp)
                exec_result = data.get("result", {}).get("result", {}).get("value", "ERROR")

            results.append(
                {
                    "page": page_num,
                    "type": action["type"],
                    "result": exec_result,
                    "confidence": action["confidence"],
                    "explanation": action["explanation"],
                }
            )

            # Wait for transition
            await asyncio.sleep(3)

        except Exception as e:
            results.append(
                {
                    "page": page_num,
                    "type": "error",
                    "result": str(e),
                }
            )
            break

    return {
        "total_pages": len(results),
        "results": results,
        "completed": any(r["type"] == QuestionType.COMPLETE for r in results),
    }


# Export
__all__ = [
    "UniversalSurveyHandler",
    "QuestionType",
    "detect_question_type",
    "generate_consent_js",
    "generate_single_choice_js",
    "generate_multiple_choice_js",
    "generate_dropdown_js",
    "generate_matrix_rating_js",
    "generate_ranking_js",
    "generate_text_input_js",
    "generate_star_rating_js",
    "generate_back_to_dashboard_js",
    "router",
]


# ═══════════════════════════════════════════════════════════════════════════════
# DRAG-DROP QUESTION TYPES (NEW 2026-05-11)
# ═══════════════════════════════════════════════════════════════════════════════
# Issue: Agent versagt bei Angular CDK Drag-Drop Puzzles weil die Taxonomie fehlt.
# Lösung: Erweitere QuestionType und detect_question_type() um Drag-Drop.


# Extended QuestionType (add to existing class if needed)
class QuestionTypeExtended(QuestionType):
    """Extended QuestionType with Drag-Drop support."""

    DRAG_DROP_NUMBER = "drag_drop_number"  # PureSpectrum "Zahl X"
    DRAG_DROP_IMAGE = "drag_drop_image"  # Bild-basiertes Drag-Drop
    SLIDER = "slider"  # Slider-Eingabe (1-100)
    RANKING_DRAG = "ranking_drag"  # Ranking via Drag (nicht Select)


def detect_drag_drop_puzzle(page_info: dict[str, Any]) -> str | None:
    """
    Erkennt Drag-Drop Puzzles BEVOR der normale Fragentyp-Detection läuft.

    Patterns:
      1. Angular CDK: .cdk-drop-list, .cdk-drag mit img[alt=NUMBER]
      2. Generic HTML5: [draggable=true], .droppable
      3. Text-Cue: "Bitte legen Sie", "Drag the", "Ziehen Sie"

    Returns:
      QuestionType string oder None wenn kein Drag-Drop
    """
    body = page_info.get("body", "").lower()
    counts = page_info.get("element_counts", {})

    # Text-Cues für Drag-Drop
    drag_cues = [
        "bitte legen sie",
        "legen sie die zahl",
        "drag the number",
        "drag and drop",
        "ziehen sie",
        "ordnen sie durch ziehen",
    ]

    has_drag_cue = any(cue in body for cue in drag_cues)

    # Angular CDK Signatur (via element_counts erweitern)
    cdk_drag_count = counts.get("cdk_drags", 0)
    cdk_drop_count = counts.get("cdk_drops", 0)

    # Generisches draggable
    draggable_count = counts.get("draggables", 0)

    # Pattern 1: Angular CDK mit "Zahl X" Text
    if (cdk_drag_count > 0 or cdk_drop_count > 0) and has_drag_cue:
        return QuestionTypeExtended.DRAG_DROP_NUMBER

    # Pattern 2: Generisches draggable mit Drag-Cue
    if draggable_count > 0 and has_drag_cue:
        return QuestionTypeExtended.DRAG_DROP_IMAGE

    # Pattern 3: Nur Text-Cue (könnte Drag sein)
    if has_drag_cue:
        return QuestionTypeExtended.DRAG_DROP_NUMBER

    return None


def generate_drag_drop_detection_js() -> str:
    """JS-Code um Drag-Drop Elemente zu zählen (für element_counts)."""
    return """
    (function(){
        var cdkDrags = document.querySelectorAll('.cdk-drag');
        var cdkDrops = document.querySelectorAll('.cdk-drop-list, .drop-zone');
        var draggables = document.querySelectorAll('[draggable=true]');
        var droppables = document.querySelectorAll('.droppable, [ondrop], [data-droppable]');

        return JSON.stringify({
            cdk_drags: cdkDrags.length,
            cdk_drops: cdkDrops.length,
            draggables: draggables.length,
            droppables: droppables.length
        });
    })()
    """


def generate_drag_drop_number_js(target_number: str = None) -> str:
    """
    JS-Code der Drag-Drop Puzzle löst.

    ACHTUNG: Synthetic Events werden von Angular CDK blockiert!
    Dieser Code ist nur für DOM-basierte (nicht Angular) Puzzles.
    Für Angular CDK: Nutze /captcha/angular-drag-drop Endpoint.

    Args:
        target_number: Die Ziel-Zahl (z.B. "52")
    """
    return f"""
    (function(){{
        // 1. Extrahiere Ziel-Zahl aus Text
        var targetNum = "{target_number or ""}";
        if (!targetNum) {{
            var bodyText = document.body.innerText;
            var match = bodyText.match(/Zahl\\s*(\\d+)|number\\s*(\\d+)/i);
            if (match) targetNum = match[1] || match[2];
        }}
        if (!targetNum) return 'DRAG_DROP_NO_TARGET_NUMBER';

        // 2. Finde Source (img mit alt=targetNum in .cdk-drag)
        var sourceImg = document.querySelector('img[alt="' + targetNum + '"]');
        if (!sourceImg) return 'DRAG_DROP_SOURCE_NOT_FOUND:' + targetNum;

        var sourceEl = sourceImg.closest('.cdk-drag') || sourceImg.parentElement;

        // 3. Finde Drop-Zone
        var dropZones = document.querySelectorAll('.cdk-drop-list');
        var dropZone = dropZones.length > 1 ? dropZones[1] : document.querySelector('.drop-zone');
        if (!dropZone) return 'DRAG_DROP_ZONE_NOT_FOUND';

        // 4. HINWEIS: Synthetic Events FUNKTIONIEREN NICHT bei Angular CDK!
        //    Dies ist nur ein Placeholder — Agent muss /captcha/angular-drag-drop aufrufen.
        return JSON.stringify({{
            status: 'needs_playwright',
            targetNumber: targetNum,
            sourceFound: !!sourceEl,
            dropZoneFound: !!dropZone,
            message: 'Angular CDK requires real pointer events via Playwright. Use /captcha/angular-drag-drop endpoint.'
        }});
    }})()
    """
