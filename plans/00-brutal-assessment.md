# Plan 00: Brutale Bestandsaufnahme

> **Parent**: `ULTIMATE-PLAN.md`  
> **Priority**: P0  
> **Zweck**: Klar benennen, was schlecht, falsch, gefaehrlich oder nur scheinbar geloest ist.

## Kurzfassung

Die groessten Katastrophen wurden begonnen zu entfernen: doppelte Engine, Legacy-FCTES und tote Agenten sind geloescht. Der aktuelle Hauptschaden ist jetzt nicht mehr "zu viele Engines", sondern: eine kanonische Engine mit zu vielen Verantwortlichkeiten, schwachen Provider-Seams, fail-open Secrets und zu wenig Live-Beweis.

## Was schrecklich falsch war oder noch ist

| Prio | Befund | Files | Ersetzen durch |
|---|---|---|---|
| P0 | Zwei NEMO-Koepfe mit denselben Klassen | `src/stealth_survey/`, `survey-cli/survey/` | Geloescht: `src/stealth_survey/`; jetzt `survey-cli/survey/` stabilisieren |
| P0 | Legacy-FCTES ohne aktiven Nutzen | `app/` | Geloescht halten; keine Wiederbelebung |
| P0 | Tote MAS-Agenten ohne Consumer | `survey-cli/survey/agents/` | Geloescht halten; echte Provider/Runtime-Seams bauen |
| P0 | Login-Monolith mit doppeltem Public Interface | `cli/modules/auto_google_login.py` | `survey/auth/google_oauth.py` + kleine Step-Interfaces |
| P0 | Runner als God-Module | `survey-cli/survey/runner.py` | `SurveyOpener`, `SurveyLoop`, `CompletionDetector`, `BalanceTracker` |
| P0 | Provider-Selektoren verstreut | `runner.py`, `execute.py`, `providers/*.py`, `tools/*.py` | `ProviderAdapter` Interface plus Contract Tests |
| P0 | Secret-Defaults im Code | `survey-cli/survey/security/__init__.py`, `auto_google_login.py` | fail-closed `SecretsClient`, `.env.example`, detect-secrets |
| P0 | Erfolg ohne Auszahlung denkbar | `runner.py`, `scanner.py` | Completion plus Balance/Reward-Verifikation |
| P1 | `print()` als Observability | `survey-cli/survey/*.py` | JSONL `Logger`, Metrics, Health Snapshot |
| P1 | Root-CLI macht eigene Arbeit | `run_survey.py`, `survey-cli/survey.py` | Root-Datei als Delegator |
| P1 | Tests patchen Interna | `survey-cli/tests/*.py` | Contract Tests an stabilen Interfaces |
| P1 | Docs widersprechen Runtime | `AGENTS.md`, `sinrules.md`, `brain.md`, `banned.md` | ADR + CI-Gates statt historische Warntexte |

## Deletion-Test

| Module | Wenn geloescht, was passiert? | Urteil |
|---|---|---|
| `src/stealth_survey/` | Komplexitaet bleibt in `survey-cli/survey/`, aber Doppelwartung verschwindet | Delete war korrekt |
| `app/` | Keine aktive Survey-Funktion verschwindet | Delete war korrekt |
| `survey-cli/survey/agents/` | Keine aktive Engine-Funktion verschwindet | Delete war korrekt |
| `run_survey.py` interne Logik | Komplexitaet muss in `survey-cli/survey.py`/Engine sein | Als Logiktraeger falsch |
| `auto_google_login.py` als Monolith | Login-Komplexitaet muss in Auth-Module zerlegt werden | Muss ersetzt werden |
| `ProviderAdapter` wenn nicht gebaut | Selektoren bleiben ueberall verstreut | Adapter-Seam ist notwendig |

## Architecture Terms

| Begriff | Anwendung hier |
|---|---|
| Module | `runner.py`, `ChromeLauncher`, `DaemonManager`, `ProviderAdapter`, `NIMClient` |
| Interface | Alles, was Caller wissen muessen: Args, Status, Fehler, Timing, Side Effects |
| Implementation | CDP Calls, JS Selectors, cua-driver CLI, retries, parsing |
| Seam | Provider, CDP, CUA, Secrets, Chrome, NIM, Logging |
| Adapter | QualtricsAdapter, CuaAdapter, ChromeLauncher, SecretsClient |
| Depth | Kleine Interface, viel Verhalten dahinter |
| Locality | Provider-Fehler wird in `providers/qualtrics.py` gefixt, nicht in 5 Dateien |
| Leverage | Engine kann Provider wechseln, ohne Runner umzuschreiben |

## Nicht nochmal machen

1. Keine zweite Engine fuer "sauberer" neu schreiben.
2. Keine Doku-Massenproduktion vor Flow-Re-Test.
3. Keine Default-Secrets in Code als "nur Fallback" tarnen.
4. Kein "completed" loggen, wenn kein Reward-/Balance-Check lief.
5. Keine Provider-Fixes in `runner.py` verstecken.
6. Keine Live-Browser-Aktionen ohne isoliertes Bot-Profil und Chrome-Safety.

## Exit-Kriterien

- Diese Bestandsaufnahme ist in `ULTIMATE-PLAN.md` verlinkt.
- Alle stale Planannahmen ueber `src/stealth_survey/` sind entfernt.
- Die naechste Arbeit priorisiert Payout-Pfad und Provider-Seam vor weiterer Kosmetik.
