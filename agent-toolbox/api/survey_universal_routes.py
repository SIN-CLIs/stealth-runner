"""
================================================================================
SURVEY UNIVERSAL ROUTES — FastAPI Endpoints für Survey-Automation (SR-76, SR-77)
================================================================================

ENDPOINTS:
  POST /survey/dashboard-scan   — Dashboard Scanner (Provider Detection)
  POST /survey/universal-answer — Universal Survey Answer Loop (NEMO Protocol)

ARCHITEKTUR:
  Client → FastAPI Router → survey-cli/survey/* → CDP → Chrome

WARUM EIGENE ROUTES?
  - Universelle Survey-Automation unabhängig von Provider
  - Dashboard-Scanning als separater Step (nicht an Answer gekoppelt)
  - Manual-Mode für Page-by-Page Fortschritt

BANNED METHODS — NIEMALS VERWENDEN (siehe /banned.md):
  ❌ playstealth launch
  ❌ webauto-nodriver — ABSOLUT BANNED
  ❌ hardcoded PIDs
  ❌ pkill -f "Google Chrome"
================================================================================
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

# Path setup für survey-cli
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "survey-cli"))


# ═══════════════════════════════════════════════════════════════════════════════
# PYDANTIC SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════


class DashboardScanRequest(BaseModel):
    """Request für POST /survey/dashboard-scan."""
    cdp_port: int = Field(default=9999, ge=1024, le=65535, description="CDP Port")
    skip_providers: List[str] = Field(
        default=["surveyrouter"],
        description="Provider die übersprungen werden sollen"
    )
    max_surveys: int = Field(default=15, ge=1, le=50, description="Max Surveys zum Scannen")


class SurveyEntry(BaseModel):
    """Einzelner Survey-Eintrag aus dem Dashboard-Scan."""
    id: str = Field(description="Survey ID")
    type: str = Field(description="Survey Type (okay, question, error)")
    provider: str = Field(description="Erkannter Provider")
    href: Optional[str] = Field(default=None, description="Survey URL")
    trust_score: float = Field(default=0.1, description="Trust Score 0.0-1.0")
    reward: Optional[float] = Field(default=None, description="Reward in EUR")
    duration: Optional[int] = Field(default=None, description="Geschätzte Dauer in Minuten")


class DashboardScanResponse(BaseModel):
    """Response für POST /survey/dashboard-scan."""
    status: Literal["ok", "error"] = Field(description="Ergebnis-Status")
    count: int = Field(default=0, description="Anzahl gefundener Surveys")
    viable_count: int = Field(default=0, description="Anzahl direkt startbarer Surveys")
    viable: List[SurveyEntry] = Field(default=[], description="Direkt startbare Surveys")
    pre_qualifiers: List[SurveyEntry] = Field(default=[], description="Pre-Qualifier Fragen")
    provider_counts: Dict[str, int] = Field(default={}, description="Surveys pro Provider")
    balance: Optional[float] = Field(default=None, description="Aktueller Kontostand EUR")
    reason: Optional[str] = Field(default=None, description="Fehler-Grund bei error")


class UniversalAnswerRequest(BaseModel):
    """Request für POST /survey/universal-answer."""
    cdp_ws_url: str = Field(..., description="CDP WebSocket URL der Survey-Page")
    manual_mode: bool = Field(
        default=True,
        description="True: Loop nur einmal pro Page (manual approval). False: Full auto-loop (DANGEROUS)"
    )
    max_pages: int = Field(default=50, ge=1, le=200, description="Max Pages pro Survey")
    profile: Dict[str, Any] = Field(
        default={},
        description="Antwort-Profil (z.B. {'age': '35', 'gender': 'male'})"
    )


class UniversalAnswerResponse(BaseModel):
    """Response für POST /survey/universal-answer."""
    status: Literal["in_progress", "completed", "disqualified", "error"] = Field(
        description="Aktueller Survey-Status"
    )
    pages_completed: int = Field(default=0, description="Abgeschlossene Seiten")
    current_page: Optional[int] = Field(default=None, description="Aktuelle Seite (1-based)")
    questions_answered: int = Field(default=0, description="Beantwortete Fragen")
    current_question_type: Optional[str] = Field(default=None, description="Aktueller Fragen-Typ")
    state_snapshot: Dict[str, Any] = Field(
        default={},
        description="State-Snapshot für Resumption"
    )
    elapsed_ms: float = Field(default=0.0, description="Laufzeit in ms")
    reason: Optional[str] = Field(default=None, description="Status-Details")


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTER
# ═══════════════════════════════════════════════════════════════════════════════

router = APIRouter(prefix="/survey", tags=["survey-universal"])


# ═══════════════════════════════════════════════════════════════════════════════
# LAZY-LOADERS
# ═══════════════════════════════════════════════════════════════════════════════


def _get_scanner():
    """Lazy-Load scanner.py Module."""
    try:
        from survey.scanner import (
            scan_dashboard,
            read_balance_with_backoff,
            detect_provider,
            get_trust_score,
            PROVIDER_TRUST_SCORES,
        )
        return {
            "scan_dashboard": scan_dashboard,
            "read_balance": read_balance_with_backoff,
            "detect_provider": detect_provider,
            "get_trust_score": get_trust_score,
            "PROVIDER_TRUST_SCORES": PROVIDER_TRUST_SCORES,
        }
    except ImportError as e:
        raise RuntimeError(f"Scanner requires survey-cli: {e}") from e


def _get_universal_handler():
    """Lazy-Load UniversalSurveyHandler."""
    try:
        from api.universal_survey_handler import (
            detect_question_type,
            QuestionType,
            generate_consent_js,
            generate_single_choice_js,
            generate_multiple_choice_js,
            generate_dropdown_js,
            generate_matrix_js,
            generate_ranking_js,
            generate_text_input_js,
            generate_star_rating_js,
        )
        return {
            "detect_question_type": detect_question_type,
            "QuestionType": QuestionType,
            "generators": {
                "consent": generate_consent_js,
                "single_choice_radio": generate_single_choice_js,
                "multiple_choice_check": generate_multiple_choice_js,
                "dropdown_select": generate_dropdown_js,
                "matrix_rating_select": generate_matrix_js,
                "ranking_select": generate_ranking_js,
                "text_input": generate_text_input_js,
                "star_rating": generate_star_rating_js,
            }
        }
    except ImportError as e:
        raise RuntimeError(f"UniversalSurveyHandler import failed: {e}") from e


def _get_cdp_connection(ws_url: str):
    """Erstellt eine sync CDPConnection."""
    try:
        from survey.cdp_client import CDPConnection
        return CDPConnection(ws_url)
    except ImportError as e:
        raise RuntimeError(f"CDPConnection requires survey-cli: {e}") from e


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/dashboard-scan", response_model=DashboardScanResponse)
async def scan_survey_dashboard(req: DashboardScanRequest) -> DashboardScanResponse:
    """
    Scannt das Survey-Dashboard nach verfügbaren Surveys.

    **Workflow:**
    1. Chrome CDP-Port verbinden
    2. Survey-IDs aus onclick-Handlern extrahieren
    3. Survey-Details via CPX API abrufen
    4. Provider-Erkennung via URL-Patterns
    5. Trust-Score berechnen
    6. Balance auslesen

    **Beispiel:**
    ```bash
    curl -X POST http://localhost:8000/survey/dashboard-scan \\
      -H "Content-Type: application/json" \\
      -d '{"cdp_port": 9999}'
    ```

    **Provider Trust Scores:**
    - Qualtrics: 0.9 (highest)
    - Toluna: 0.8
    - Cint: 0.7 (Cloudflare blocking risk)
    - PureSpectrum: 0.3 (high screen-out rate)
    """
    start = time.monotonic()
    
    try:
        scanner = _get_scanner()
    except RuntimeError as e:
        return DashboardScanResponse(status="error", reason=str(e))
    
    try:
        # Scan dashboard
        surveys = scanner["scan_dashboard"](
            port=req.cdp_port,
            skip_providers=req.skip_providers
        )
        
        if not surveys:
            return DashboardScanResponse(
                status="ok",
                count=0,
                viable_count=0,
                viable=[],
                pre_qualifiers=[],
                provider_counts={},
                balance=scanner["read_balance"](req.cdp_port)
            )
        
        # Kategorisieren
        viable = []
        pre_qualifiers = []
        provider_counts: Dict[str, int] = {}
        
        for s in surveys[:req.max_surveys]:
            provider = s.get("provider", "unknown")
            provider_counts[provider] = provider_counts.get(provider, 0) + 1
            
            entry = SurveyEntry(
                id=s.get("id", ""),
                type=s.get("type", "unknown"),
                provider=provider,
                href=s.get("href"),
                trust_score=s.get("trust_score", scanner["get_trust_score"](provider)),
                reward=s.get("reward"),
                duration=s.get("duration"),
            )
            
            if s.get("type") == "okay":
                viable.append(entry)
            elif s.get("type") == "question":
                pre_qualifiers.append(entry)
        
        # Balance auslesen
        balance = scanner["read_balance"](req.cdp_port)
        
        return DashboardScanResponse(
            status="ok",
            count=len(surveys),
            viable_count=len(viable),
            viable=viable[:15],
            pre_qualifiers=pre_qualifiers[:10],
            provider_counts=provider_counts,
            balance=balance,
        )
    
    except Exception as e:
        return DashboardScanResponse(status="error", reason=f"exception: {type(e).__name__}: {e}")


@router.post("/universal-answer", response_model=UniversalAnswerResponse)
async def universal_survey_answer(req: UniversalAnswerRequest) -> UniversalAnswerResponse:
    """
    Universeller Survey-Answerer (NEMO Protocol, Page-by-Page).

    **Workflow:**
    1. Page-Info via CDP laden (URL, Title, Body, Element Counts)
    2. Question-Type erkennen (Consent, Radio, Checkbox, Matrix, etc.)
    3. JS-Code für Antwort generieren (basierend auf Profil)
    4. JS ausführen via CDP Runtime.evaluate
    5. "Next" Button klicken
    6. Bei manual_mode: Pausieren für User-Approval

    **Beispiel:**
    ```bash
    curl -X POST http://localhost:8000/survey/universal-answer \\
      -H "Content-Type: application/json" \\
      -d '{"cdp_ws_url": "ws://127.0.0.1:9999/devtools/page/ABC", "manual_mode": true}'
    ```

    **Question Types:**
    - consent: Consent/GDPR acceptance
    - single_choice_radio: Single selection (Radio buttons)
    - multiple_choice_check: Multiple selections (Checkboxes)
    - dropdown_select: Dropdown/Select
    - matrix_rating_select: Matrix with selects (1-5 rating)
    - ranking_select: Ranking with unique values
    - text_input: Free text
    - star_rating: Star rating (CPX)
    """
    start = time.monotonic()
    
    try:
        handler = _get_universal_handler()
    except RuntimeError as e:
        return UniversalAnswerResponse(status="error", reason=str(e),
                                       elapsed_ms=(time.monotonic() - start) * 1000)
    
    try:
        cdp = _get_cdp_connection(req.cdp_ws_url)
    except RuntimeError as e:
        return UniversalAnswerResponse(status="error", reason=str(e),
                                       elapsed_ms=(time.monotonic() - start) * 1000)
    
    try:
        cdp.connect()
        
        # 1. Page-Info sammeln
        page_info_js = """
        (function() {
            var radios = document.querySelectorAll('input[type=radio]').length;
            var checkboxes = document.querySelectorAll('input[type=checkbox]').length;
            var selects = document.querySelectorAll('select').length;
            var text_inputs = document.querySelectorAll('input[type=text], textarea').length;
            var stars = document.querySelectorAll('.star, .rating-star, [data-rating]').length;
            
            return JSON.stringify({
                url: location.href,
                title: document.title,
                body: document.body.innerText.substring(0, 2000),
                element_counts: {
                    radios: radios,
                    checkboxes: checkboxes,
                    selects: selects,
                    text_inputs: text_inputs,
                    stars: stars
                }
            });
        })()
        """
        
        result = cdp.call("Runtime.evaluate", {"expression": page_info_js})
        page_info_str = result.get("result", {}).get("result", {}).get("value", "{}")
        
        import json
        page_info = json.loads(page_info_str)
        
        # 2. Question-Type erkennen
        q_type = handler["detect_question_type"](page_info)
        QuestionType = handler["QuestionType"]
        
        # 3. Check für Complete/Disqualified
        if q_type == QuestionType.COMPLETE:
            cdp.close()
            return UniversalAnswerResponse(
                status="completed",
                pages_completed=0,
                current_question_type=q_type,
                elapsed_ms=(time.monotonic() - start) * 1000,
                reason="Survey completed successfully"
            )
        
        if q_type == QuestionType.DISQUALIFIED:
            cdp.close()
            return UniversalAnswerResponse(
                status="disqualified",
                pages_completed=0,
                current_question_type=q_type,
                elapsed_ms=(time.monotonic() - start) * 1000,
                reason="Disqualified from survey"
            )
        
        # 4. JS für Antwort generieren
        generators = handler["generators"]
        if q_type in generators:
            answer_js = generators[q_type]()
        else:
            answer_js = None
        
        questions_answered = 0
        
        if answer_js:
            # 5. JS ausführen
            answer_result = cdp.call("Runtime.evaluate", {"expression": answer_js})
            answer_value = answer_result.get("result", {}).get("result", {}).get("value", "")
            questions_answered = 1
            
            # 6. Next-Button klicken (falls nicht manual_mode oder Consent)
            if not req.manual_mode or q_type == QuestionType.CONSENT:
                next_js = """
                (function() {
                    var btns = document.querySelectorAll('button, input[type=submit], a.next, .next-btn');
                    for (var i = 0; i < btns.length; i++) {
                        var text = (btns[i].innerText || btns[i].value || '').toLowerCase();
                        if (text.includes('next') || text.includes('weiter') || text.includes('continue') || 
                            text.includes('nächste') || text.includes('absenden') || text.includes('submit')) {
                            btns[i].click();
                            return 'NEXT_CLICKED: ' + text;
                        }
                    }
                    return 'NO_NEXT_FOUND';
                })()
                """
                cdp.call("Runtime.evaluate", {"expression": next_js})
        
        cdp.close()
        
        return UniversalAnswerResponse(
            status="in_progress",
            pages_completed=1 if questions_answered > 0 else 0,
            current_page=1,
            questions_answered=questions_answered,
            current_question_type=q_type,
            state_snapshot={
                "url": page_info.get("url"),
                "question_type": q_type,
                "manual_mode": req.manual_mode,
            },
            elapsed_ms=(time.monotonic() - start) * 1000,
            reason=f"Answered {q_type}, {'paused for manual approval' if req.manual_mode else 'auto-continuing'}"
        )
    
    except Exception as e:
        try:
            cdp.close()
        except Exception:
            pass
        return UniversalAnswerResponse(
            status="error",
            reason=f"exception: {type(e).__name__}: {e}",
            elapsed_ms=(time.monotonic() - start) * 1000
        )
