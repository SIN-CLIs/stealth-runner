# Plan 01: Canonical Engine

> **Parent**: `ULTIMATE-PLAN.md`  
> **Phase**: 1-2  
> **Priority**: P0  
> **Risk**: Mittel, weil Entry Points und Tests betroffen sind.

## Ziel

`survey-cli/survey/` ist die eine kanonische Survey-Engine. Alles andere ist Delegator, Adapter oder tot.

## Aktueller Stand

| Bereich | Stand |
|---|---|
| `src/stealth_survey/` | geloescht |
| `app/` | geloescht |
| `survey-cli/survey/agents/` | geloescht |
| `survey-cli/survey/opencode_bridge.py` | geloescht |
| `run_survey.py` | migriert, aber als zweiter Entry Point noch riskant |
| `survey-cli/survey.py` | Haupt-CLI, aber noch mit eigener Runtime-Logik |
| `survey-cli/survey/runner.py` | kanonischer Runner, aber zu gross |

## Problem

Die alte Zwei-Kopf-Krankheit ist nicht mehr aktiv, aber der verbleibende Kopf ist zu gross. `runner.py` traegt zu viele Rollen:

- Survey oeffnen
- Dashboard/CPX scannen
- In-page modal vs new-tab entscheiden
- CDP WebSocket wechseln
- Snapshot erzeugen
- NIM entscheiden lassen
- Aktionen ausfuehren
- Provider-Sonderfaelle kennen
- Completion erkennen
- Balance lesen
- Cash-out triggern
- Pre-Qualifier beantworten

Das ist zu viel Interface und zu wenig Locality.

## Ziel-Module

| Module | Interface | Implementation dahinter |
|---|---|---|
| `SurveyRunner` | `run_survey()`, `run_loop()` | Orchestriert nur noch |
| `SurveyOpener` | `open(survey_id, survey)` -> `SurveyTarget` | clickSurvey, modal, new-tab, tab activation |
| `SurveyLoop` | `run(target)` -> `SurveyResult` | snapshot -> decide -> execute -> verify |
| `CompletionDetector` | `detect(text, url, snapshot)` | Keywords, provider markers, modal close, redirect |
| `BalanceTracker` | `before()`, `after()`, `earned()` | Dashboard-tab targeting, backoff, filters |
| `ProviderRegistry` | `get(provider)` -> `ProviderAdapter` | URL detection, adapter fallback |
| `ToolFacade` | tool calls -> engine calls | Tools bleiben duenn |

## Arbeitsschritte

1. Root `run_survey.py` auf Delegation reduzieren.
2. `SurveyTarget` Dataclass einfuehren: `survey_id`, `provider`, `ws_url`, `tab_id`, `mode`, `url`.
3. `SurveyOpener` aus `runner.py` extrahieren.
4. `CompletionDetector` aus `snapshot.py`/`runner.py` konsolidieren.
5. `BalanceTracker` aus `scanner.py`/`runner.py` konsolidieren.
6. `ProviderRegistry` einfuehren und Provider-Entscheidungen aus dem Runner ziehen.
7. Tools in `survey-cli/tools/` nur noch als Facades auf Engine-Interfaces betreiben.
8. Alte Imports und stale Kommentare mit `rg` pruefen.

## Nicht tun

- Kein neuer Package-Name `survey_cli` jetzt. Das waere Churn ohne direkten Payout-Nutzen.
- Kein Big-Bang-Rewrite von `runner.py`.
- Keine neuen Helper, die nur eine Funktion weiterreichen.
- Keine Provider-Fixes in `runner.py` mehr.

## Tests

| Test | Zweck |
|---|---|
| `test_root_run_survey_delegates` | Root Entry Point macht keine eigene Engine-Logik |
| `test_survey_opener_new_tab` | New-tab wird erkannt und aktiviert |
| `test_survey_opener_in_page_modal` | In-page modal bleibt im Dashboard-WS |
| `test_completion_detector_keywords` | Completion ohne Provider-Adapter |
| `test_balance_tracker_ignores_level_values` | Kein 125-Euro-Fake-Balance |

## Verification

```bash
# Keine aktive alte Engine
rg "from src\.stealth_survey|import src\.stealth_survey" . --glob '*.py'

# Root script ist Delegator
rg "SurveyRunner|survey\." run_survey.py

# Provider-Sonderfaelle nicht im Runner verstecken
rg "qualtrics|toluna|strat7|purespectrum" survey-cli/survey/runner.py
```

## Exit-Kriterien

- `survey-cli/survey/runner.py` ist eine Orchestrierungs-Facade, nicht mehr Provider-/Tab-/Balance-Monolith.
- Root `run_survey.py` kann geloescht werden, ohne Engine-Features zu verlieren.
- Jede neue Funktionalitaet landet hinter einer echten Seam.
