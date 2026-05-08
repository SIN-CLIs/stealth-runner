# Plan 08: Observability and Sessions

> **Parent**: `ULTIMATE-PLAN.md`  
> **Phase**: 5  
> **Priority**: P1

## Ziel

Der Runtime-Zustand ist messbar: Survey-Versuche, Provider, Fehler, Balance, NIM, Chrome, Tabs, Sessions.

## Aktueller Stand

- Viele direkte `print()` Calls in `survey-cli/survey/`.
- Session-Korruption wurde bereinigt, aber Monitoring fehlt.
- Logs existieren teilweise, aber kein klares Schema als Interface.
- Kein Health Snapshot als stabile Machine-Ausgabe.

## Logger Interface

```python
class Logger:
    def event(self, name: str, **fields) -> None:
        """Append JSONL event with session_id, ts, level and schema_version."""

    def info(self, name: str, **fields) -> None: ...
    def warn(self, name: str, **fields) -> None: ...
    def error(self, name: str, **fields) -> None: ...
```

## Required Events

| Event | Required fields |
|---|---|
| `chrome_started` | pid, port, profile_dir |
| `chrome_verified` | pid, cdp_ok, ax_ok, flags |
| `daemon_health` | state, reason, restart_count |
| `survey_scanned` | count, providers, balance |
| `survey_opened` | survey_id, provider, mode, tab_id, url |
| `tab_switched` | from_tab, to_tab, reason |
| `snapshot_generated` | provider, ref_count, progress, hash |
| `nim_decision` | model, latency_ms, fallback, action_count |
| `action_executed` | provider, action, success, state_changed |
| `completion_detected` | status, reason, provider |
| `balance_read` | value, source, ignored_values |
| `survey_result` | survey_id, provider, status, earned, duration_ms |
| `session_corruption_detected` | path, size, action |

## Metrics

| Metric | Type |
|---|---|
| surveys_attempted | counter |
| surveys_completed | counter |
| surveys_screen_out | counter |
| surveys_error | counter |
| earned_total_eur | counter/gauge |
| nim_calls | counter |
| nim_failures | counter |
| nim_latency_ms | histogram |
| chrome_restarts | counter |
| cua_restarts | counter |
| stuck_aborts | counter |
| session_corruptions | counter |

## Session Protection

Problem: OpenCode session files koennen als 2-Byte JSON-Dateien entstehen. Bereinigung wurde gemacht, aber Schutz fehlt.

Plan:

1. `scripts/cleanup_sessions.py` bauen: dry-run, archive, delete.
2. JSON validieren, nicht nur filesize.
3. Monitor-Modus: neue Dateien <100 Bytes melden.
4. Health-Check integriert Disk und session corruption status.
5. Keine riesigen Session-Dateien automatisch loeschen; nur reporten/rotieren nach expliziter Regel.

## Print Replacement

Regel:

- CLI-Kommandos duerfen User-Ausgabe machen.
- Engine, Runner, Provider, Auth, Chrome, Daemon nutzen Logger.
- Tests koennen Logger in memory sink injizieren.

## Arbeitsschritte

1. `survey/observability/logger.py` bauen.
2. `SurveyMetrics` bauen.
3. `HealthChecker` bauen.
4. Session cleanup script bauen.
5. `runner.py`, `daemon.py`, `chrome.py`, `scanner.py`, `execute.py` schrittweise auf Logger migrieren.
6. Log schema dokumentieren.
7. Alert-Regeln definieren.

## Verification

```bash
rg "print\(" survey-cli/survey --glob '*.py'
python scripts/cleanup_sessions.py --dry-run ~/.local/share/opencode/sessions
pytest survey-cli/tests -q
```

## Exit-Kriterien

- Engine hat strukturierte JSONL-Events.
- Session-Korruption wird erkannt, nicht nur spaeter manuell gefunden.
- Survey-Erfolg/Fehler kann aus Logs rekonstruiert werden.
- Direkte `print()` sind auf CLI-Ausgabe begrenzt.
