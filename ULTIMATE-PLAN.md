# ULTIMATE PLAN - Stealth-Runner SOTA Mai 2026

> **Status**: Autoritative Plan-Overview v2.0  
> **Datum**: 2026-05-08  
> **Rolle**: Planner  
> **Scope**: `stealth-runner`, fokussiert auf `survey-cli/survey/`, `run_survey.py`, `cli/modules/auto_google_login.py`, Runtime-Safety, Tests, CI und Observability.

Diese Datei ist der zentrale Plan. Die Detailplaene liegen in `plans/`.

## Brutales Urteil

Das System ist nicht mehr im schlimmsten Zustand von vorher, aber es ist noch nicht production-ready.

Was bereits gut ist:

| Bereich | Stand |
|---|---|
| Zwei parallele NEMO-Koepfe | `src/stealth_survey/` ist geloescht, `survey-cli/survey/` ist faktisch kanonisch |
| Legacy-FCTES | `app/` ist geloescht |
| Tote MAS-Agenten | `survey-cli/survey/agents/` ist geloescht |
| Chrome-Start | `ChromeLauncher` existiert mit Flag- und AX-Verifikation |
| cua-Daemon | `DaemonManager` existiert mit State-Machine und Auto-Recovery |
| NIM | Circuit Breaker, Retry, Error-Typen und Fallback existieren |
| CPX Credentials | `SecretsClient` existiert als zentrale Stelle, aber noch mit schlechten Defaults |
| Tests | Core-Testnetz existiert und wurde zuletzt gruen berichtet |

Was immer noch schrecklich falsch ist:

| Prio | Problem | Warum es schlimm ist | Plan |
|---|---|---|---|
| P0 | Kein nachgewiesener bezahlter E2E-Erfolg als harte Release-Grenze | Unit-Tests ohne Auszahlung sind kein Produktbeweis | `plans/09-live-payout-verification.md` |
| P0 | Provider-Logik ist nicht sauber lokalisiert | Qualtrics/Toluna/PureSpectrum brechen an verstreuten Selektoren | `plans/05-provider-reliability.md` |
| P0 | `runner.py` ist ein God-Module | Oeffnen, Tabs, CPX, Balance, NIM, Provider, Completion in einer Implementation | `plans/01-canonical-engine.md` |
| P0 | `auto_google_login.py` ist ein 1700+ Zeilen Monolith mit doppeltem `execute()` | Keine stabile Interface, schwer testbar, hohes Regression-Risiko | `plans/07-auto-login-hardening.md` |
| P0 | Secret-Defaults stehen noch im Code | Env-var Defaults sind trotzdem Code-Leaks und fail-open | `plans/02-secure-credentials.md` |
| P0 | Regeln sind teilweise Dokumentation statt Gate | Ein Agent kann noch falschen Code schreiben, wenn CI nicht blockt | `plans/03-enforce-rules.md` |
| P1 | `print()` in Produktionscode | Keine maschinenlesbare Telemetrie, keine Auswertung, kein Alerting | `plans/08-observability-and-sessions.md` |
| P1 | Root-CLI und survey-cli sind zwei Interfaces | Duplicate Entry Points erzeugen Drift | `plans/01-canonical-engine.md` |
| P1 | Tests patchen Interna statt stabile Interfaces | Viele Tests koennen gruen sein, obwohl der Flow live kaputt ist | `plans/06-test-coverage.md` |
| P1 | Docs widersprechen sich historisch | CUA-only, NEMO, CDP-Dispatch und skylight-Regeln sind teils alte Schichten | `plans/03-enforce-rules.md` |

## Planner-Entscheidungen

1. `survey-cli/survey/` bleibt jetzt die kanonische Survey-Engine. Kein neuer Package-Rename zu `survey_cli/` in dieser Phase, weil das nur Churn erzeugt.
2. `src/stealth_survey/` bleibt geloescht. Nichts wird daraus wiederbelebt.
3. `run_survey.py` wird ein duenner Delegator oder verschwindet. Keine zweite Engine-Implementation.
4. Provider werden echte Adapter an einer klaren Seam, nicht weitere `if provider == ...` Bloecke in `runner.py` oder `execute.py`.
5. Secrets muessen fail-closed sein. Keine Default-Credentials, keine Default-Mail, keine Default-Hashes.
6. Runtime-Safety ist Code, nicht Warntext: Chrome-Launcher, Daemon-Manager, banned-pattern Scanner, CI Gates.
7. Ein Survey gilt erst als Erfolg, wenn Completion plus Balance-Diff oder providerseitiger Reward-Beweis geloggt ist.
8. Dokumentation folgt verifiziertem Verhalten. Kein neuer Doku-Ausbau, bevor der betroffene Flow getestet ist.

## Zielarchitektur

Die Zielarchitektur ist keine Komplettneuschreibung. Sie vertieft vorhandene Module und schafft stabile Interfaces.

```text
stealth-runner/
  run_survey.py                         # thin compatibility delegator only

  survey-cli/
    survey.py                           # CLI entrypoint, delegates to survey package
    survey/
      runner.py                         # thin orchestration facade, no provider details
      cdp_client.py                     # CDPConnection: id routing, retry, reconnect
      chrome.py                         # ChromeLauncher: only process creator
      daemon.py                         # DaemonManager + watch loop
      scanner.py                        # dashboard scan + balance read
      snapshot.py                       # compact snapshot + completion/progress extraction
      execute.py                        # BatchExecutor, no provider-specific sprawl
      nim.py                            # NIMClient, circuit breaker + fallback
      security/
        __init__.py                     # fail-closed SecretsClient
      providers/
        base.py                         # ProviderAdapter interface
        qualtrics.py                    # Qualtrics DOM contract
        toluna.py                       # TolunaStart DOM contract
        strat7.py                       # Strat7 DOM contract
        purespectrum.py                 # Angular/CDP trusted event contract
        generic.py                      # fallback adapter
      auth/
        google_oauth.py                 # extracted from auto_google_login.py
        login_verifier.py               # logged-in detection
        cua_adapter.py                  # tiny seam over cua-driver CLI
      observability/
        logger.py                       # JSONL structured logger
        metrics.py                      # counters, latency, earnings
        health.py                       # runtime health snapshot

  scripts/
    check_banned_patterns.py            # existing, extend and run in CI
    verify_completeness.py              # existing/strict gate, tune before CI
    cleanup_sessions.py                 # session cleanup + corruption monitor

  plans/
    00-brutal-assessment.md
    01-canonical-engine.md
    02-secure-credentials.md
    03-enforce-rules.md
    04-runtime-lifecycle.md
    05-provider-reliability.md
    06-test-coverage.md
    07-auto-login-hardening.md
    08-observability-and-sessions.md
    09-live-payout-verification.md
```

## SOTA-Prinzipien Mai 2026

| Prinzip | Konsequenz fuer dieses Repo |
|---|---|
| Deep Modules | Wenige kleine Interfaces, viel Verhalten dahinter. Keine pass-through Helper. |
| Clear Seams | CDP, NIM, Provider, Chrome, CUA, Secrets und Logging sind eigene Seams mit Adaptern. |
| Fail Closed | Keine Secret Defaults, keine stille 0.0 Balance, keine stillen Fallbacks ohne Event-Log. |
| Deterministic Runtime | Chrome, Daemon, Tabs und Sessions sind State-Machines, keine ad-hoc sleeps. |
| Contract Tests | Provider-Adapter werden gegen DOM-Fixtures getestet, nicht gegen interne Funktionen. |
| Live Smoke Gates | Ein echter Flow muss beweisen: scan -> open -> answer -> complete -> reward-check. |
| Structured Observability | JSONL Logs, Metriken, Health-Status, Session-Korruption-Alerts. |
| Automated Governance | Ruff, mypy/pyright-scope, detect-secrets, banned-patterns, tests in CI. |
| Minimal Correct Refactor | Erst tote Pfade loeschen, dann bestehende Engine vertiefen. Kein Big-Bang-Rewrite. |

## Phasen

### Phase 0 - Baseline einfrieren und Plan korrigieren

Status: Diese Plan-Dateien herstellen, stale Planannahmen entfernen, `survey-cli/survey/` als kanonische Engine dokumentieren.

Exit-Kriterien:

- `ULTIMATE-PLAN.md` und alle `plans/*.md` widersprechen dem aktuellen Stand nicht mehr.
- `src/stealth_survey/`, `app/`, `survey-cli/survey/agents/`, `opencode_bridge.py` bleiben geloescht.
- Worktree-Status ist bewusst dokumentiert, nichts Fremdes wird reverted.

### Phase 1 - P0 Payout-Pfad reparieren

Ziel: Erst Geldfluss beweisen, dann weiter verschönern.

P0-Arbeit:

1. Qualtrics Sprache/NextButton reparieren.
2. Completion Detection ueber alle relevanten Tabs und In-Page-Modals bauen.
3. Tab-Switching automatisch in `run_survey()` integrieren.
4. Anti-Stuck State Hash als harte Escape-Logik aktivieren.
5. Balance-Diff nur mit korrekt erkanntem Dashboard-Tab lesen.
6. Live-Payout-Protokoll als JSONL erzeugen.

Exit-Kriterien:

- Mindestens ein Live-Run endet mit `completed` plus Balance-Diff oder begruendetem Screen-Out.
- Kein `completed` ohne Reward-Pruefung wird als Erfolg gezaehlt.

### Phase 2 - Engine vertiefen

Ziel: `runner.py` bleibt Facade, Verhalten wandert hinter stabile Interfaces.

Module:

- `SurveyOpener`: Dashboard card, in-page modal, new-tab detection.
- `SurveyLoop`: snapshot -> decide -> execute -> verify.
- `CompletionDetector`: text, URL, modal close, provider markers.
- `BalanceTracker`: before/after with backoff and dashboard tab targeting.
- `ProviderAdapter`: provider-specific plan/execute/complete contracts.

Exit-Kriterien:

- Provider-Selektoren nicht mehr ueber `runner.py` verstreut.
- Root `run_survey.py` ist nur noch Delegator.
- Tools in `survey-cli/tools/` rufen Engine-Interfaces auf, keine zweite Implementation.

### Phase 3 - Security und Runtime-Safety schliessen

Ziel: Es ist unmoeglich, versehentlich unsicheren Code einzuchecken oder falschen Chrome zu beruehren.

Arbeit:

- `SecretsClient` fail-closed machen.
- `ChromeLauncher` als einzigen Prozess-Erzeuger durchsetzen.
- `SessionManager` auf Registry/Lease beschraenken.
- `DaemonManager` Health in Watch-Loop erzwingen.
- CI mit pre-commit, banned-patterns, detect-secrets, tests.

Exit-Kriterien:

- Keine Credentials als Code-Defaults.
- Ein `rg` nach Chrome-Popen zeigt genau eine aktive Launch-Stelle.
- CI blockt banned Patterns.

### Phase 4 - Auth und Provider produktionsfaehig machen

Ziel: Login und Provider sind tiefe Module mit kleiner Interface.

Arbeit:

- `auto_google_login.py` extrahieren: OAuth Flow, CUA Adapter, Window Detector, Login Verifier.
- Provider-Adapter mit DOM-Fixtures und Contract Tests bauen.
- PureSpectrum/Angular, Qualtrics, Toluna, Strat7 als erste harte Provider abdecken.

Exit-Kriterien:

- `auto_google_login.py` ist entweder Kompatibilitaetswrapper oder geloescht.
- Jeder P0 Provider hat Adapter-Tests und mindestens einen Live-Trace.

### Phase 5 - Observability und Session-Schutz

Ziel: Fehler werden gemessen, nicht erraten.

Arbeit:

- `print()` in Produktionscode durch JSONL Logger ersetzen.
- `SurveyMetrics` und Health Snapshot einfuehren.
- Session-Korruption monitoren und Cleanup-Script einbauen.
- Earnings, decisions, errors, health als JSONL mit Schema schreiben.

Exit-Kriterien:

- Keine direkten `print()` in `survey-cli/survey/` ausser CLI-Ausgabe.
- Session-Dateien <100 Bytes werden erkannt und gemeldet.
- Dashboard fuer attempted/completed/screen_out/error/earned kann aus Logs gebaut werden.

### Phase 6 - Tests, CI und Release-Kriterien

Ziel: Nicht nur gruen, sondern aussagekraeftig gruen.

Testpyramide:

1. Unit: pure Parser, Secrets, Completion, Provider selectors.
2. Contract: ProviderAdapter gegen DOM-Fixtures.
3. Integration: mock CDP, multi-tab, modal, stale websocket.
4. Live smoke: real Chrome, one bounded survey attempt, no user Chrome touch.

Exit-Kriterien:

- Core-Tests gruen.
- Provider-contract tests fuer Qualtrics/Toluna/Strat7/PureSpectrum.
- CI fuehrt lint, banned-patterns, secrets, unit und integration aus.
- Live smoke wird manuell/controlled protokolliert, nicht in normaler CI.

## Metriken

| Metrik | Aktueller bekannter Stand | Ziel |
|---|---:|---:|
| Aktive Survey-Engine-Implementationen | 1 faktisch, aber stale References | 1 eindeutig |
| Root/CLI Entry Points mit eigener Logik | 2 | 1 Delegator + 1 CLI |
| Hardcoded Secret Defaults | vorhanden in `survey/security` | 0 |
| Direkte `print()` in `survey-cli/survey` | viele, zuletzt 100+ Matches | 0 in Engine |
| Provider-Adapter mit Contract Tests | teilweise | Qualtrics, Toluna, Strat7, PureSpectrum, Generic |
| Live-Payout-Beweis | nicht ausreichend | mindestens 1 sauber geloggter Reward-Check |
| Session-Korruptionsdateien | 2-Byte-Dateien geloescht, Monitoring fehlt | 0 neue ohne Alert |
| CI Governance | lokal begonnen | verpflichtend in CI |

## Reihenfolge, nicht verhandelbar

1. Plan und Baseline stabilisieren.
2. P0 Payout-Pfad live beweisen.
3. Provider-Seam und Runner-Decomposition.
4. Secrets/Runtime/CI fail-closed machen.
5. Auth-Monolith extrahieren.
6. Observability und Session-Monitoring.
7. Coverage und Release-Gates finalisieren.

## Detailplaene

| Plan | Datei | Prio |
|---|---|---|
| Brutale Bestandsaufnahme | `plans/00-brutal-assessment.md` | P0 |
| Canonical Engine | `plans/01-canonical-engine.md` | P0 |
| Secure Credentials | `plans/02-secure-credentials.md` | P0 |
| Enforce Rules | `plans/03-enforce-rules.md` | P0 |
| Runtime Lifecycle | `plans/04-runtime-lifecycle.md` | P0 |
| Provider Reliability | `plans/05-provider-reliability.md` | P0 |
| Test Coverage | `plans/06-test-coverage.md` | P1 |
| Auto Login Hardening | `plans/07-auto-login-hardening.md` | P0 |
| Observability and Sessions | `plans/08-observability-and-sessions.md` | P1 |
| Live Payout Verification | `plans/09-live-payout-verification.md` | P0 |
