# ISSUE-SR-34: Survey Flow Test Suite

| Feld | Wert |
|------|------|
| **ID** | SR-34 |
| **Priority** | 🟡 P2 — Medium |
| **Status** | 📋 TODO |
| **Created** | 2026-05-06 |
| **Labels** | `testing`, `quality`, `ci` |
| **Plan** | `plan-sr-34-test-suite.md` |

## Problem
Keine Tests für Survey-Automation. Jede Änderung muss manuell gegen Live-Surveys getestet werden. Das ist riskant (verlorene Surveys = verlorenes Geld) und langsam. Es gibt keinen Unit-Test, Integration-Test oder Mock-Survey.

## Subissues

### SR-34.1 — Provider Detection Tests
- [ ] `test_detect_qualtrics()` — URL "eu.qualtrics.com/jfe/form/..." → "qualtrics"
- [ ] `test_detect_tolunastart()` — URL "survey.tolunastart.com/..." → "tolunastart"
- [ ] `test_detect_purespectrum()` — URL "screener.purespectrum.com/..." → "purespectrum"
- [ ] `test_detect_strat7()` — URL "...strat7audiences.com/..." → "strat7"
- [ ] `test_detect_unknown()` — URL "example.com" → "unknown"
- [ ] `test_detect_redirect_chain()` — CPX URL → final target

### SR-34.2 — Answer Pattern Tests
- [ ] `test_qualrics_radio_click()` — `input[type=radio]` .click() funktioniert
- [ ] `test_tolunastart_radio_click()` — `.cf-radio` JS .click() funktioniert
- [ ] `test_qualrics_next_button()` — `.NextButton.click()`
- [ ] `test_qualrics_textarea_fill()` — value + Event("input") + Event("change")
- [ ] `test_qualrics_matrix_fill()` — table.ChoiceStructure per-row radio

### SR-34.3 — Persona Tests
- [ ] `test_age_calculation()` — date_of_birth → age (32)
- [ ] `test_age_bracket()` — 32 → "31 bis 35 Jahre"
- [ ] `test_gender_resolve()` — "Sind Sie..." → "Männlich"
- [ ] `test_state_resolve()` — "Bundesland" → "Berlin"
- [ ] `test_income_resolve()` — household_income → "3000-4000"
- [ ] `test_education_avoid_screenout()` — Nicht Universitätsabschluss

### SR-34.4 — Mock Survey Server
- [ ] `tests/mock_survey.html` — Qualtrics-ähnliche Seite mit 3 Fragen
- [ ] `tests/mock_tolunastart.html` — TolunaStart-ähnliche Seite
- [ ] `tests/fixtures/` — HTML-Fixtures für jeden Provider
- [ ] Lokaler HTTP-Server für Tests: `python -m http.server`

### SR-34.5 — E2E Test (Mock)
- [ ] Chrome mit `--headless` für Test
- [ ] `Target.createTarget("http://localhost:8000/mock_survey.html")`
- [ ] 5 Fragen via CDP beantworten
- [ ] Completion prüfen
- [ ] Ergebnis: `{"status": "ok", "questions_answered": 5}`

## Acceptance Criteria
- [ ] 20+ Unit-Tests (Provider Detection + Persona + Answer Patterns)
- [ ] Mock-HTML für Qualtrics + TolunaStart
- [ ] E2E Test läuft in < 30 Sekunden
- [ ] `pytest` Exit-Code 0

## Betroffene Files
- `tests/test_provider_detect.py` → NEU
- `tests/test_answer_patterns.py` → NEU
- `tests/test_persona.py` → NEU
- `tests/test_e2e_survey.py` → NEU
- `tests/fixtures/mock_qualtrics.html` → NEU
- `tests/fixtures/mock_tolunastart.html` → NEU
