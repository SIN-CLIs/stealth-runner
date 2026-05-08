# Plan 09: Live Payout Verification

> **Parent**: `ULTIMATE-PLAN.md`  
> **Phase**: 1  
> **Priority**: P0

## Ziel

Das System darf sich erst als funktionierend bezeichnen, wenn ein Live-Flow sauber bis Reward-Pruefung laeuft.

## Warum das P0 ist

Viele Tests und Fixes helfen nicht, wenn der reale Loop keine Auszahlung oder keinen belastbaren Screen-Out beweist. Ein `completed` ohne Balance/Reward-Check ist nur ein UI-Zustand, kein Erfolg.

## Erfolgskriterien

Ein Live-Versuch ist erfolgreich dokumentiert, wenn alle Felder vorhanden sind:

```json
{
  "event": "survey_result",
  "session_id": "...",
  "survey_id": "...",
  "provider": "qualtrics|toluna|strat7|...",
  "status": "completed|screen_out|blocked|error",
  "completion_reason": "...",
  "balance_before": 2.23,
  "balance_after": 2.26,
  "earned": 0.03,
  "reward_verified": true,
  "tabs_seen": 3,
  "tab_mode": "new_tab|in_page_modal",
  "duration_ms": 123456
}
```

Fuer `screen_out` muss `reward_verified` ebenfalls gesetzt sein, wenn Compensation erwartet wird. Fuer `blocked`/`error` muss ein klarer Grund geloggt sein.

## Minimaler Live Flow

1. Chrome mit `ChromeLauncher` starten/verifizieren.
2. Login verifizieren oder Login-Flow ausfuehren.
3. Dashboard scannen.
4. Einen passenden Survey waehlen.
5. Vorher Balance lesen.
6. Survey oeffnen: new-tab oder in-page modal erkennen.
7. ProviderAdapter nutzt snapshot -> action -> verify.
8. Completion/screen-out/block/error erkennen.
9. Dashboard-Tab finden.
10. Nachher Balance lesen.
11. JSONL Ergebnis schreiben.

## P0 Bugs, die vorher geschlossen werden muessen

| Issue | Fix |
|---|---|
| Qualtrics language stuck | `QualtricsAdapter` mit `.LabelWrapper` + `.NextButton` |
| Completion nicht erkannt | `CompletionDetector` tabs + modal + provider markers |
| Tab switching nicht automatisiert | `TabManager` und `SurveyOpener` |
| Anti-stuck fehlt | State hash + Strategy switch/abort |
| Balance Fake-Werte | `BalanceTracker` mit Kontextfilter und dashboard targeting |

## Safety

- Nur Bot-Chrome mit `/tmp/heypiggy-new-*`.
- Kein User-Chrome killen.
- Kein Live Smoke in normaler CI.
- Max attempts und max duration setzen.
- Bei CAPTCHA/blocked sauber abbrechen und loggen.

## Tests vor Live

```bash
pytest survey-cli/tests/test_chrome_launcher.py survey-cli/tests/test_daemon_manager.py -q
pytest survey-cli/tests/test_tool_find_new_tab.py survey-cli/tests/test_tool_detect_completion.py -q
pytest survey-cli/tests/test_balance.py survey-cli/tests/test_execute.py -q
python scripts/check_banned_patterns.py survey-cli cli run_survey.py
```

## Live-Run Command

Der konkrete Command wird erst nach ProviderAdapter- und Completion-Fixes finalisiert. Er muss bounded sein:

```bash
cd survey-cli
./survey.py run --max 1 --timeout 300 --jsonl logs/live-payout-smoke.jsonl
```

Falls die CLI diese Flags noch nicht hat, ist das Teil dieses Plans.

## Exit-Kriterien

- Ein Live Smoke Artefakt liegt in JSONL vor.
- Ergebnis ist nicht stuck.
- Erfolg wird nur mit `reward_verified=true` gezaehlt.
- Fehler wird mit provider, tab_mode, url, state_hash und reason dokumentiert.
