# STATE MANAGEMENT — Stealth-Runner Best Practices

> **Version**: 2026-05-08 v1.0
> **Scope**: Explizite Session-States, Transitionen, Recovery-Strategien
> **Status**: ACTIVE — Wird von ALLEN Modulen verwendet

---

## 1. EXPLIZITE STATE-MACHINE (Kein impliziter State!)

**GOLDENE REGEL**: Jede Session hat einen EXPLIZITEN State. NIEMALS implizit ("irgendwie läuft es").

### States

```python
class SessionState:
    """
    Explizite Zustandsmaschine für jede Chrome/Survey-Session.

    WARUM State-Machine?
      Implizite States ("irgendwie läuft es", "sollte eingeloggt sein") führen zu:
      - Race Conditions (Survey startet vor Login)
      - Resource Leaks (Chrome-Prozesse akkumulieren)
      - Falschen Entscheidungen (Agent denkt er ist eingeloggt, ist es aber nicht)
      - Datenverlust (Klick auf falschen Tab, falsches Element)

    WARUM Enum?
      - Typ-Sicherheit: IDE warnt bei falschem State
      - Keine Tippfehler: "HEALHTY" vs "HEALTHY"
      - Dokumentiert: Jeder State hat docstring
      - Erweiterbar: Neue States in einem Enum
    """

    CREATED   = "created"    # Chrome gestartet, noch nicht bereit
    HEALTHY   = "healthy"    # Chrome läuft, CDP erreichbar, Dashboard sichtbar
    LOGGED_IN = "logged_in"  # Login erfolgreich VERIFIZIERT (nicht vermutet!)
    RUNNING   = "running"    # Survey-Loop aktiv
    SURVEYING = "surveying"  # Eine Survey wird ausgeführt (innerhalb RUNNING)
    DEGRADED  = "degraded"   # Chrome läuft, aber Fehlerrate hoch (>5 errors)
    RECOVERING = "recovering" # Recovery-Phase nach CRASHED
    STOPPED   = "stopped"    # Chrome beendet, Session aufgeräumt
    CRASHED   = "crashed"    # Chrome abgestürzt, Recovery nötig
```

### Erlaubte Transitionen

```
CREATED ──→ HEALTHY ──→ LOGGED_IN ──→ RUNNING ──→ STOPPED
   │           │            │              │            ▲
   │           │            │              │            │
   │           ├──→ DEGRADED │              │            │
   │           │      │      │              │            │
   │           │      ▼      │              │            │
   │           │   RECOVERING│              │            │
   │           │      │      │              │            │
   │           │      ▼      │              │            │
   │           ├──→ HEALTHY  │              │            │
   │           │             │              │            │
   ├───────────┼─────────────┼──────────────┤            │
   │           │             │              │            │
   ├──→ CRASHED ←────────────┼──────────────┤            │
   │      │                   │              │            │
   │      ├──→ RECOVERING ──→ HEALTHY       │            │
   │      │                   │              │            │
   │      └──→ STOPPED        │              │            │
   │                          │              │            │
   └──────────────────────────┴──────────────┴──→ STOPPED

VERBOTENE Transitionen (ILLEGAL):
  ❌ RUNNING → CREATED      (Zurück zu Start ohne Neustart)
  ❌ CRASHED → LOGGED_IN    (Überspringt HEALTHY Check)
  ❌ STOPPED  → RUNNING     (Zurück ohne Neustart — muss CREATED werden)
  ❌ SURVEYING → DEGRADED   (Survey sollte erst beendet werden)
```

### Implementation

```python
import time, json
from enum import Enum

class SessionState(Enum):
    CREATED = "created"
    HEALTHY = "healthy"
    LOGGED_IN = "logged_in"
    RUNNING = "running"
    SURVEYING = "surveying"
    DEGRADED = "degraded"
    RECOVERING = "recovering"
    STOPPED = "stopped"
    CRASHED = "crashed"

# Erlaubte Transitionen
VALID_TRANSITIONS: Dict[SessionState, List[SessionState]] = {
    SessionState.CREATED:   [SessionState.HEALTHY, SessionState.STOPPED, SessionState.CRASHED],
    SessionState.HEALTHY:   [SessionState.LOGGED_IN, SessionState.DEGRADED, SessionState.STOPPED, SessionState.CRASHED],
    SessionState.LOGGED_IN: [SessionState.RUNNING, SessionState.DEGRADED, SessionState.STOPPED, SessionState.CRASHED],
    SessionState.RUNNING:   [SessionState.SURVEYING, SessionState.DEGRADED, SessionState.STOPPED, SessionState.CRASHED],
    SessionState.SURVEYING: [SessionState.RUNNING, SessionState.DEGRADED, SessionState.STOPPED, SessionState.CRASHED],
    SessionState.DEGRADED:  [SessionState.RECOVERING, SessionState.HEALTHY, SessionState.STOPPED, SessionState.CRASHED],
    SessionState.RECOVERING: [SessionState.HEALTHY, SessionState.STOPPED, SessionState.CRASHED],
    SessionState.STOPPED:   [SessionState.CREATED],
    SessionState.CRASHED:   [SessionState.RECOVERING, SessionState.STOPPED],
}

class SessionStateManager:
    """
    Verwalter Session-State mit Validierung, Logging und Persistenz.

    WARUM Klasse? Kapselt State + Validierung + Persistenz.
    WARUM nicht global? Testbar — Dependency Injection.

    Usage:
      >>> sm = SessionStateManager()
      >>> sm.transition(SessionState.HEALTHY)     # OK
      >>> sm.transition(SessionState.LOGGED_IN)   # OK
      >>> sm.transition(SessionState.CREATED)     # ❌ ValueError!
    """

    def __init__(self, state_file: str = "~/.stealth/session_state.json"):
        self.state_file = os.path.expanduser(state_file)
        self.history: List[Tuple[str, str, float]] = []  # (from, to, timestamp)

        # Lade letzten State aus Datei
        self.state = self._load_state()

    def _load_state(self) -> SessionState:
        """Lädt letzten State aus Persistenz."""
        try:
            with open(self.state_file) as f:
                d = json.loads(f.read())
                return SessionState(d.get("state", "stopped"))
        except (FileNotFoundError, json.JSONDecodeError):
            return SessionState.STOPPED

    def _save_state(self):
        """Persistiert aktuellen State."""
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
        with open(self.state_file, "w") as f:
            json.dump({
                "state": self.state.value,
                "history_count": len(self.history),
                "updated_at": time.time(),
            }, f)

    def transition(self, new_state: SessionState, reason: str = ""):
        """
        EXPLIZITE State-Transition mit Validierung.

        Args:
          new_state (SessionState): Ziel-State
          reason (str): Warum diese Transition? (für Logging)

        Raises:
          ValueError: Wenn Transition NICHT erlaubt ist.

        Side Effects:
          - Speichert State in Datei
          - Schreibt Transition in history
          - Loggt Transition in events.jsonl

        Example:
          >>> sm = SessionStateManager()
          >>> sm.transition(SessionState.HEALTHY, "Chrome started on port 9999")
          >>> sm.transition(SessionState.LOGGED_IN, "OAuth completed")
          >>> sm.transition(SessionState.RUNNING, "Survey loop started")
        """
        # Validierung
        allowed = VALID_TRANSITIONS.get(self.state, [])
        if new_state not in allowed:
            raise ValueError(
                f"ILLEGAL Transition: {self.state.value} → {new_state.value}\n"
                f"  Reason: {reason}\n"
                f"  Erlaubt: {[s.value for s in allowed]}"
            )

        # Transition durchführen
        old_state = self.state
        self.state = new_state
        timestamp = time.time()

        # History aufzeichnen
        self.history.append((old_state.value, new_state.value, timestamp))
        if len(self.history) > 1000:
            self.history = self.history[-500:]  # Trimmen (Speicher sparen)

        # Persistieren
        self._save_state()

        # Loggen
        log_event("state_transition", "info", {
            "from": old_state.value,
            "to": new_state.value,
            "reason": reason,
            "transition_count": len(self.history),
        })

    def can_transition(self, new_state: SessionState) -> bool:
        """Prüft ob Transition erlaubt ist (ohne sie auszuführen)."""
        return new_state in VALID_TRANSITIONS.get(self.state, [])

    def get_state_duration(self) -> float:
        """Wie lange sind wir schon in diesem State?"""
        if not self.history:
            return 0.0
        return time.time() - self.history[-1][2]
```

---

## 2. TRANSITION-REGELN (WANN in welchen State?)

### CREATED → HEALTHY

```python
# TRIGGER: Chrome wurde gestartet
# BEDINGUNGEN:
#   1. Chrome-Prozess läuft (pgrep -f "heypiggy-new")
#   2. CDP erreichbar (curl http://127.0.0.1:9999/json)
#   3. Mindestens 1 Tab offen (/json response hat >0 Einträge)
#   4. cua-driver Daemon läuft (pgrep -f "cua-driver serve")
#   5. Accessibility aktiv (system_profiler SPAccessibilityDataType)
if not is_chrome_alive(port):
    raise TransitionError("Chrome not running")
if not is_cdp_available(port):
    raise TransitionError("CDP not reachable")
if not is_cua_daemon_running():
    raise TransitionError("cua-driver daemon not running")
sm.transition(SessionState.HEALTHY, "All preconditions met")
```

### HEALTHY → LOGGED_IN

```python
# TRIGGER: Login erfolgreich verifiziert
# BEDINGUNGEN:
#   1. Dashboard-Tab existiert (find_dashboard_ws)
#   2. document.title enthält "Umfragen" ODER body enthält "Abmelden"
#   3. Balance-Wert lesbar (>0.00)
# VERIFIZIERUNG (nicht Annahme!):
#   - CDP Runtime.evaluate: document.title.includes('Umfragen')
#   - Falls FALSE → KEIN LOGIN → Nicht zu LOGGED_IN gehen!
logged_in = _verify_login_via_cdp()
if not logged_in:
    raise TransitionError("Login verification failed")
sm.transition(SessionState.LOGGED_IN, "Login verified via CDP")
```

### RUNNING → SURVEYING

```python
# TRIGGER: Eine Survey wurde gestartet
# BEDINGUNGEN:
#   1. Survey-Tab wurde erstellt (Target.createTarget)
#   2. Survey-Tab lädt (url enthält Survey-Provider-Domain)
#   3. Survey-URL erreichbar (<20s Page-Load)
# RÜCKKEHR: Survey beendet → SURVEYING → RUNNING
sm.transition(SessionState.SURVEYING, f"Survey {survey_id} started")
try:
    result = agent.run_survey(survey_id)
finally:
    sm.transition(SessionState.RUNNING, f"Survey {survey_id} ended: {result.status}")
```

### RUNNING → DEGRADED

```python
# TRIGGER: Mehr als 5 aufeinanderfolgende Fehler
# BEDINGUNGEN:
#   1. consecutive_errors >= 5
#   2. Chrome läuft noch (sonst wäre es CRASHED)
# WAS tun? Nicht weitermachen wie blind! Sondern:
#   - Login neu prüfen
#   - cua-driver Daemon prüfen
#   - Dashboard-Tab aktualisieren
#   - NIEMALS einfach DEGRADED → weiterlaufen!
if state["consecutive_errors"] >= 5:
    sm.transition(SessionState.DEGRADED, f"{state['consecutive_errors']} errors")
    # Recovery-Strategie einleiten
    if _try_recover():
        sm.transition(SessionState.RECOVERING, "Recovery started")
```

### CRASHED → RECOVERING

```python
# TRIGGER: Chrome nicht erreichbar (>60s)
# BEDINGUNGEN:
#   1. is_chrome_alive() = False
#   2. Letzter Healthy-Check >60s her
# WAS tun:
#   1. Alte Chrome-PID loggen (für Debugging)
#   2. Registry leeren (~/.stealth/sessions.json)
#   3. NEUEN Chrome starten mit korrekten Flags
#   4. Login ausführen
#   5. Zurück zu HEALTHY oder STOPPED (wenn Recovery fehlschlägt)
sm.transition(SessionState.CRASHED, "Chrome unreachable")
try:
    _clear_registry()
    _start_new_chrome()
    auto_google_login()
    sm.transition(SessionState.RECOVERING, "Recovery in progress")
    sm.transition(SessionState.HEALTHY, "Recovery successful")
except RecoveryFailed as e:
    sm.transition(SessionState.STOPPED, f"Recovery failed: {e}")
```

---

## 3. RECOVERY-STRATEGIEN

### R1: Login Recovery

```python
def recover_login(sm: SessionStateManager) -> bool:
    """
    Versucht Login wiederherzustellen.

    WARUM separate Funktion?
      Login kann aus VIELEN Gründen fehlschlagen — jeder braucht
      eine andere Recovery-Strategie.

    Returns:
      bool: True wenn Login wiederhergestellt.

    Strategien (in Reihenfolge):
      1. cua-driver Daemon restart (häufigstes Problem)
      2. Accessibility prüfen (zweithäufigstes Problem)
      3. Chrome mit korrekten Flags neustarten
      4. Keychain prüfen (Google Credentials noch da?)
      5. Google 2FA deaktiviert? (unwahrscheinlich)
    """
    # Strategie 1: Daemon restart
    if not is_cua_daemon_running():
        start_cua_daemon()
        time.sleep(2)
        if is_cua_daemon_running():
            if auto_google_login().get("status") == "ok":
                return True

    # Strategie 2: Accessibility
    if not check_accessibility():
        print("[RECOVER] Accessibility not available — cannot recover")
        return False

    # Strategie 3: Chrome neustart mit Flags
    safe_kill_bot()
    _start_chrome_with_flags()
    time.sleep(8)
    if auto_google_login().get("status") == "ok":
        return True

    # Strategie 4: Keychain check
    # Strategie 5: 2FA check
    return False
```

### R2: Chrome Crash Recovery

```python
def recover_chrome_crash(sm: SessionStateManager, port: int) -> bool:
    """
    Recovery nach Chrome-Crash.

    Steps:
      1. Zustand analysieren (was ist kaputt?)
      2. Alte Prozesse aufräumen
      3. Neuen Chrome starten
      4. Verifizieren

    Returns:
      bool: True wenn Chrome erfolgreich wiederhergestellt.
    """
    sm.transition(SessionState.CRASHED, "Chrome crash detected")

    # 1. Analyse: Warum ist Chrome gecrasht?
    crash_info = _analyze_crash(port)

    # 2. Aufräumen
    _cleanup_zombie_chrome()
    _clear_registry()

    # 3. Neustart
    pid = _start_chrome_with_flags(port=port)
    if not pid:
        sm.transition(SessionState.STOPPED, "Cannot restart Chrome")
        return False

    # 4. Verifizieren
    time.sleep(8)
    if not is_chrome_alive(port):
        sm.transition(SessionState.STOPPED, "Chrome startup failed")
        return False

    sm.transition(SessionState.HEALTHY, "Chrome recovered")
    return True
```

---

## 4. PERSISTENZ (State überleben)

```json
// ~/.stealth/session_state.json
{
  "state": "running",
  "state_since": 1746650000.0,
  "history": [
    ["stopped", "created", 1746649000.0, "Chrome started"],
    ["created", "healthy", 1746649005.0, "CDP reachable"],
    ["healthy", "logged_in", 1746649010.0, "OAuth completed"],
    ["logged_in", "running", 1746649015.0, "Survey loop started"],
    ["running", "surveying", 1746649030.0, "Survey 66846193 started"],
    ["surveying", "running", 1746649200.0, "Survey 66846193 completed"]
  ],
  "total_transitions": 6,
  "total_crashes": 0,
  "total_recoveries": 0,
  "updated_at": 1746650000.0
}
```

**WARUM Persistenz?**
- System-Crash: State überlebt und kann beim nächsten Start geladen werden
- Debugging: History zeigt was schief ging
- Monitoring: crash_count und recovery_count sind KPIs
- Agent-Wechsel: Anderer Agent übernimmt mit bekanntem State

---

## 5. ANTI-PATTERNS (NIEMALS tun!)

```python
# ❌ ANTI-PATTERN 1: Impliziter State
logged_in = False  # Nie gesetzt, nur vermutet
if logged_in:   # Immer False!

# ✅ EXPLIZITER State
sm.transition(SessionState.LOGGED_IN, reason="OAuth verified")

# ❌ ANTI-PATTERN 2: State ohne Validierung
state = "running"
def do_login():
    state = "logged_in"  # Kein Transition-Check — ILLEGAL möglich!

# ✅ VALIDIERTE Transition
sm.transition(SessionState.LOGGED_IN, "Login completed")

# ❌ ANTI-PATTERN 3: Im Leeren State weiterlaufen
sm.state = SessionState.CRASHED
# ... weiter Code... NIEMALS! Nach CRASHED = RECOVERING oder STOPPED

# ✅ RECOVERY einleiten
if sm.state == SessionState.CRASHED:
    recover_chrome_crash(sm, port)
    # Erst dann weitermachen
```

---

**Dieses Dokument ist LEBENDIG. Aktualisiere es nach jeder State-Machine-Änderung.**

*Letzte Aktualisierung: 2026-05-08*
