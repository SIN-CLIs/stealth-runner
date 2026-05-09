# Plan 04: Runtime Lifecycle

> **Parent**: `ULTIMATE-PLAN.md`  
> **Phase**: 3  
> **Priority**: P0

## Ziel

Chrome, cua-driver, Tabs und Sessions werden deterministisch verwaltet. Kein User-Chrome wird beruehrt.

## Aktueller Stand

Gut:

- `ChromeLauncher` existiert.
- Mandatory Flags werden verifiziert.
- `DaemonManager` existiert mit State-Machine.
- Watch-Loop hat Health-Checks.

Noch schlecht:

- Mehrere Wrapper/Funktionen koennen Chrome-Lifecycle verwalten.
- `SessionManager` und accessibility helpers haben noch eigene Prozess-/Kill-Logik.
- Tab-Lifecycle ist noch mit Runner-Logik vermischt.

## Ziel-Seams

| Seam | Interface | Darf Prozess anfassen? |
|---|---|---|
| `ChromeLauncher` | `launch_and_verify(url)` | Ja, einzige Stelle |
| `ChromeLease` | `pid`, `port`, `profile_dir`, `started_at` | Nein |
| `ChromeCleanup` | `close_bot_chrome(lease)` | Ja, nur Bot-Profil |
| `DaemonManager` | `ensure_healthy()` | cua-driver only |
| `TabManager` | `list_tabs()`, `activate()`, `find_active_survey()` | Nein, CDP only |
| `SessionRegistry` | save/load lease | Nein |

## Regeln

1. Genau eine aktive `subprocess.Popen(... Chrome ...)` Stelle.
2. Nur timestamped `~/tmp/chrome-instance-B (Profil 902 Kopie)` Profile.
3. Kill nur fuer Main-Prozesse mit passendem Bot-Profil.
4. Erst SIGTERM, dann nach Timeout SIGKILL-Fallback.
5. Kein `pkill`, kein `killall`, keine hardcoded PIDs.
6. Nach jeder Browser-Aktion Status pruefen: Tab, URL, Body/Text, enabled/disabled.

## Arbeitsschritte

1. `ChromeLauncher` als einzige Prozess-Erzeugung markieren und per scanner erzwingen.
2. `survey/daemon.py::launch_chrome()` und `survey/accessibility.py::launch_chrome_with_accessibility()` als reine Wrapper lassen oder entfernen.
3. `cli/modules/session_manager.py` auf `ChromeLauncher` delegieren.
4. Bot-Kill-Logik in `ChromeCleanup` konsolidieren.
5. `TabManager` aus `runner.py` extrahieren.
6. Daemon health in jedem Watch-Zyklus loggen.
7. Runtime-state in JSONL schreiben: chrome_started, chrome_verified, daemon_degraded, tab_switched.

## Tests

| Test | Erwartung |
|---|---|
| launcher flags | beide Pflichtflags immer gesetzt |
| launch verification fails | kein stiller Erfolg |
| cleanup bot only | User-Chrome Pattern wird ignoriert |
| daemon restart | DEGRADED -> STARTING -> HEALTHY |
| tab manager | new-tab und in-page modal unterscheiden |

## Verification

```bash
rg "subprocess\.Popen\(.*Chrome|Google Chrome" survey-cli cli --glob '*.py'
rg "pkill|killall|os\.kill\([^\n]+,\s*9\)" survey-cli cli --glob '*.py'
pytest survey-cli/tests/test_chrome_launcher.py survey-cli/tests/test_daemon_manager.py -q
```

## Exit-Kriterien

- Kein zweiter Chrome-Prozess-Erzeuger.
- Kein User-Chrome-Kill-Pfad.
- Tab-Switching ist eigene getestete Runtime-Komponente.
