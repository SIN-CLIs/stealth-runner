# ISSUE-SR-28: CDP Survey Module — CUA-Driver → CDP WebSocket Rewrite

| Feld | Wert |
|------|------|
| **ID** | SR-28 |
| **Priority** | 🔴 P0 — Critical |
| **Status** | 📋 TODO |
| **Created** | 2026-05-06 |
| **Assignee** | — |
| **Labels** | `module`, `cdp`, `refactor`, `performance` |
| **Plan** | `plan-sr-28-cdp-survey-module.md` |

## Problem
Der `survey_heypiggy.py` Flow nutzt `cua-driver call` für ALLE Interaktionen (click, set_value, get_window_state). Das ist extrem langsam (~500ms pro Call) und erfordert einen laufenden CUA-Daemon. Die heutigen Survey-Sessions haben gezeigt: **CDP WebSocket direkt ist >10× schneller** und braucht keinen externen Prozess.

## Ziel
Ein `cli/modules/survey_cdp.py` Modul das:
1. Survey-URLs via CDP `Target.createTarget` öffnet
2. Den Provider erkennt (Qualtrics, TolunaStart, PureSpectrum, etc.)
3. Fragen via `Runtime.evaluate` beantwortet (per Provider-Pattern)
4. Completion erkennt und Balance aktualisiert

## Subissues

### SR-28.1 — CDP WebSocket Client Basis
- [ ] `Surveymodule` Klasse mit `connect(port=9999)`, `eval(js)`, `close()`
- [ ] `create_target(url)` → tab_id
- [ ] `get_tab_ws(tab_id)` → webSocketDebuggerUrl
- [ ] `wait_for_load(tab_id, timeout=10)` → page ready

### SR-28.2 — Provider Pattern Registry
- [ ] `ProviderPattern` Dataclass: provider_name, url_pattern, click_next_selector, radio_selector, checkbox_selector, textarea_selector
- [ ] Quellen aus `/commands/` extrahieren:
  - `QualtricsPattern` — `.NextButton`, `input[type=radio]`, `input[type=checkbox]`, `textarea.InputText`
  - `TolunaStartPattern` — `button`, `.cf-radio`, `.cf-checkbox`, `input[type=number]`
  - `Strat7Pattern` — `.bsbutton`, `input[type=radio]`
  - `BrandAmbassadorPattern` — `.submit-btn`, `input[type=radio]` + hidden inputs
- [ ] `detect_provider(url) → ProviderPattern` — URL-Match → Pattern

### SR-28.3 — Answer Engine
- [ ] `answer_radio(ws, index)` → klickt Radio-Button
- [ ] `answer_checkbox(ws, indices)` → klickt Checkboxen
- [ ] `answer_textarea(ws, text)` → füllt Textarea mit Event-Dispatch
- [ ] `answer_matrix(ws, ratings_per_row)` → Matrix-Tabelle ausfüllen
- [ ] `click_next(ws, provider)` → provider-spezifischer Next-Button
- [ ] `get_question_text(ws)` → liest aktuelle Frage

### SR-28.4 — Full Flow Runner
- [ ] `run_survey(survey_id)` → `Target.createTarget` → Wait → Loop bis Completion
- [ ] Completion-Erkennung: "Zurück zur Website" / rating.php detection
- [ ] `find_rating_tab()` → rate survey → +0.01€
- [ ] Return `{"status": "ok", "earned": X, "provider": "..."}`

### SR-28.5 — Demographics Auto-Fill
- [ ] Persona-Daten aus `persona.py` oder `config/profile.json`
- [ ] `fill_demographics(ws, provider, persona)` → Alter, Geschlecht, Wohnort, Einkommen, etc.
- [ ] Frage-Erkennung per Keyword: "Alter", "Geschlecht", "Bundesland", "Einkommen"

## Acceptance Criteria
- [ ] Qualtrics-Survey (21-Page HUK) läuft vollautomatisch
- [ ] TolunaStart-Survey läuft vollautomatisch
- [ ] Provider-Detection funktioniert bei allen 6 bekannten Providern
- [ ] Keine CUA-Driver-Abhängigkeit mehr
- [ ] Runtime < 5 Minuten für Qualtrics 21-Page Survey

## Betroffene Files
- `cli/modules/survey_cdp.py` → NEU
- `cli/modules/provider_patterns.py` → NEU
- `app/flows/learning/survey_heypiggy.py` → Refactor
- `commands/surveys/*.md` → Referenz

## Dependencies
- SR-32 (Provider Auto-Detect)
- SR-33 (Persona System)
