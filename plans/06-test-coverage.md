# Plan 06: Test Coverage and Verification

> **Parent**: `ULTIMATE-PLAN.md`  
> **Phase**: 6  
> **Priority**: P1

## Ziel

Tests sollen echte Produktionsrisiken abdecken, nicht nur Mocks gruener machen.

## Problem

Es gibt viele Tests, aber die groessten Risiken liegen an runtime Seams:

- Browser tabs wechseln.
- Provider DOM unterscheidet sich live.
- Completion wird nicht erkannt.
- Balance liest falsche Zahlen.
- cua-driver/Chrome/NIM fallen partiell aus.
- Tests patchen oft interne Funktionen statt stabile Interfaces.

## Testpyramide

| Ebene | Zweck | Beispiele |
|---|---|---|
| Unit | Pure logic | parsing, completion keywords, state hash, secret validation |
| Contract | Adapter Interface | ProviderAdapter gegen DOM fixtures |
| Integration | Multi-module flow | mock CDP tabs, stale websocket, modal/new-tab |
| Live smoke | begrenzter Real-Run | one Chrome, one survey attempt, no user Chrome touch |

## Mindest-Contracts

### ProviderAdapter Contract

Jeder Adapter muss testen:

1. `matches()` erkennt richtige URL/DOM.
2. `plan_actions()` erzeugt semantische Actions.
3. `execute_action()` nutzt provider-korrekte Methode.
4. `detect_completion()` unterscheidet completed/screen_out/blocked/error.

### Runtime Contract

1. Chrome startet nur mit Pflichtflags.
2. Daemon recovered von DEGRADED.
3. TabManager erkennt new-tab und in-page modal.
4. CDPConnection routet Responses per ID und reconnectet.
5. BalanceTracker ignoriert Level/Min/Reward-Card Werte.

### Auth Contract

1. Bereits eingeloggt -> kein OAuth.
2. Fresh OAuth -> 6-Step Flow.
3. Keychain present -> Fortfahren.
4. Keychain missing -> Password-Fallback oder sauberer Fehler.
5. Wrong window -> nicht klicken.

## Live Smoke Gate

Nicht in normaler CI. Manuell oder nightly auf isolierter Maschine.

Kriterien:

1. Chrome Bot-Profil `/tmp/heypiggy-new-*`.
2. `--force-renderer-accessibility` und `--remote-allow-origins="*"` verifiziert.
3. Dashboard eingeloggt.
4. Ein Survey wird versucht.
5. Ergebnis ist `completed`, `screen_out`, `blocked`, oder `error`, aber nie stuck ohne Grund.
6. Balance before/after wird geloggt.
7. Logs enthalten session_id, survey_id, provider, tabs, earned.

## Arbeitsschritte

1. Coverage-Audit nach aktueller Loeschung neu laufen lassen.
2. DOM-Fixtures fuer Provider anlegen.
3. Contract-Test-Basis fuer ProviderAdapter bauen.
4. Integration-Test fuer new-tab switching bauen.
5. Integration-Test fuer in-page modal bauen.
6. CompletionDetector Edge Cases testen.
7. Auth-Step Tests aus `auto_google_login.py` extrahieren.
8. CI auf unit + contract + integration ohne Live Smoke setzen.

## Verification

```bash
pytest survey-cli/tests -q
pytest --cov=survey --cov-report=term-missing survey-cli/tests
python scripts/check_banned_patterns.py survey-cli cli run_survey.py
```

## Exit-Kriterien

- Kein P0-Provider ohne Contract Tests.
- Kein Runtime-Seam ohne Fehlerpfad-Test.
- Live Smoke Ergebnis wird als Artefakt/JSONL dokumentiert.
- Coverage-Ziel ist mindestens 90 Prozent fuer neue/beruehrte Module, aber wichtiger ist Seam-Abdeckung.
