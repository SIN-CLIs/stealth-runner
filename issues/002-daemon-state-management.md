# Issue #2: Daemon State Management — Daemon gestoppt, keine Recovery (P0)

> **Status**: OPEN  
> **Severity**: 🔴 P0  
> **Reporter**: Automated Analysis  
> **Erstellt**: 2026-05-08 00:20 UTC  
> **Betroffene Dateien**: `~/.stealth/daemon_state.json`, `survey-cli/survey.py`, `cli/modules/session_manager.py`

---

## Problem-Beschreibung

`~/.stealth/daemon_state.json`:
```json
{"running": false, "stopped_at": "2026-05-07T06:53:14.807058", "surveys_completed": 0}
```

**Impact**: Keine Survey-Automatisierung läuft. Watch-Loop bricht ab oder fehlschlägt.

**WARUM ist das ein Problem?**
- cua-driver Daemon = Session-Cache + AX-Tree Zugriff
- Ohne Daemon: Keine CUA-Interaktionen möglich
- Ohne CUA: Login schlägt fehl (Issue #1)
- Ohne Login: Keine Surveys

---

## Root-Cause-Analyse

### Ursache 1: Kein Auto-Restart
Der Watch-Loop (`cmd_watch()`) prüft OB Chrome läuft, aber NICHT ob der Daemon läuft:
```python
if not is_chrome_alive(args.port):
    # ... wartet, versucht es später
    # Aber: is_cua_daemon_running()? NICHT geprüft!
```

### Ursache 2: Kein Health-Check vor Aktionen
Jede cua-driver Aktion sollte VORHER prüfen:
1. Ist cua-driver Daemon erreichbar? (`pgrep -f "cua-driver serve"`)
2. Ist Chrome erreichbar? (`curl http://127.0.0.1:9999/json`)
3. Ist Dashboard sichtbar? (`list_windows`)

Aktuell: Schritte 1+2 werden übersprungen oder nicht erzwungen.

### Ursache 3: Keine Graceful Shutdown Recovery
Wenn Daemon crasht (SIGKILL, OOM, etc.):
- `daemon_state.json` bleibt auf `running: false`
- Niemand restartet ihn automatisch
- Nächster Agent sieht `running: false` aber weiß nicht WARUM

---

## Vorgeschlagener Fix

### State Machine für Daemon
```python
class DaemonManager:
    """
    Verwaltet cua-driver Daemon Lifecycle.

    States:
        STOPPED     → Daemon nicht laufend
        STARTING    → Start-Befehl ausgeführt, noch nicht verifiziert
        HEALTHY     → Daemon läuft, Health-Check OK
        DEGRADED    → Daemon läuft, aber langsam/errors
        FAILED      → Start fehlgeschlagen oder Crash

    Auto-Actions:
        STOPPED → Auto-Start (wenn Config auto_start=True)
        FAILED  → Auto-Restart mit Backoff (max 3 Versuche)
        DEGRADED → Log Warning, continue
    """

    def ensure_running(self):
        """
        Prüft Daemon-State und restartet falls nötig.

        Returns:
            bool: True wenn Daemon HEALTHY, False wenn FAILED (nach 3 Retries)
        """
        state = self.read_state()
        if state == "HEALTHY":
            return True

        if state in ("STOPPED", "FAILED"):
            for attempt in range(3):
                self.transition("STARTING")
                if self._start_daemon():
                    time.sleep(2)  # Warten bis Daemon bereit
                    if self._health_check():
                        self.transition("HEALTHY")
                        return True
                # Backoff: 2s, 4s, 8s
                time.sleep(2 ** attempt)
            self.transition("FAILED")
            return False

        return False

    def _health_check(self):
        """
        Daemon Health-Check: list_windows aufrufen.

        WARUM list_windows?
          Einfachster Call — wenn der funktioniert, funktioniert alles.
        """
        try:
            r = subprocess.run(
                ["cua-driver", "call", "list_windows"],
                capture_output=True, text=True, timeout=10
            )
            return r.returncode == 0 and "windows" in r.stdout
        except Exception:
            return False
```

### Watch-Loop Integration
```python
def cmd_watch(args):
    # VOR dem Loop: Daemon sicherstellen
    daemon = DaemonManager()
    if not daemon.ensure_running():
        print("[WATCH] ❌ CRITICAL: Daemon not available after 3 retries")
        log_session("watch_stop", "error", {"reason": "daemon_unavailable"})
        return  # STOP

    # Jede Iteration: Health-Check
    while state["running"]:
        if not daemon.health_check():
            print("[WATCH] ⚠️  Daemon degraded — attempting restart...")
            if not daemon.ensure_running():
                print("[WATCH] ❌ Daemon dead — stopping")
                break
        # ... rest of loop
```

---

## Akzeptanzkriterien

- [ ] `daemon_state.json` hat korrekten State (nicht nur `running: false`)
- [ ] Watch-Loop prüft Daemon VOR jeder Aktion
- [ ] Auto-Restart mit Exponential Backoff (max 3 Versuche)
- [ ] Health-Check: `list_windows` als Canary
- [ ] Graceful Shutdown schreibt korrekten State
- [ ] Test: `test_daemon_restart_after_crash` muss passen

---

**Nächster Schritt**: `DaemonManager` implementieren + in `cmd_watch()` integrieren.

*Letzte Aktualisierung: 2026-05-08 00:20 UTC*
