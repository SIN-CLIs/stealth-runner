# BEST PRACTICES PLAN — Stealth-Runner State of the Art

> **Version**: 2026-05-08 v1.0  
> **Scope**: Code-Qualität, Dokumentation, Session-Management, Error-Handling, Testing  
> **Status**: ACTIVE — Muss nach jedem Commit aktualisiert werden

---

## 1. KODIERUNG — GOLDENE REGELN (UNVERBRÜCHLICH)

### R1: EXTREME KOMMENTARE (WICHTIGSTE REGEL)

**JEDE Code-Datei MUSS diese Kommentar-Level haben:**

```python
# ============================================================================
# DATEI-LEVEL KOMMENTAR (oben, mindestens 50 Zeilen)
# ============================================================================
# WAS IST DAS?
#   - Zweck der Datei in 1-2 Sätzen
#   - WARUM existiert diese Datei? (Welches Problem löst sie?)
#
# ARCHITEKTUR:
#   - Wie passt sie ins Gesamtbild?
#   - Diagramm oder ASCII-Art der Abhängigkeiten
#   - Welche Module importieren diese Datei?
#
# DEPENDENZEN:
#   - Welche andere Dateien/Module/Pakete braucht sie?
#   - Was bricht wenn diese Datei fehlt?
#
# BANNED METHODEN (in JEDER Datei!):
#   ❌ playstealth launch — setzt NICHT --force-renderer-accessibility
#   ❌ webauto-nodriver — ABSOLUT BANNED
#   ❌ cua-driver click (raw index) — instabil
#   ❌ pkill -f "Google Chrome" — tötet USER Chrome
#   ❌ killall Google Chrome — tötet ALLE Chrome
#   ❌ Hardcoded PIDs — dynamisch, niemals hardcodieren
#   ❌ skylight-cli click --element-index — Index instabil
#
# HISTORY:
#   - 2026-05-08: Erstellt/Geändert, Warum?
#   - 2026-05-07: IndentationError behoben
#
# WARUM DIESE KONSTANTE?
#   - Jede Konstante erklären: Warum dieser Wert? Warum nicht anders?
#   - Beispiel: TIMEOUT = 15  # Nicht 10 (zu kurz für Keychain) oder 30 (zu lang)
# ============================================================================

# ============================================================================
# FUNKTIONS-LEVEL KOMMENTAR (jede Funktion, mindestens 10 Zeilen)
# ============================================================================
def meine_funktion(parameter1, parameter2, optional=None):
    """
    EIN-SATZ-ZWECK: Was macht diese Funktion?

    Args:
        parameter1 (str): Beschreibung + Beispiel + Validierung
        parameter2 (int): Beschreibung + Warum dieser Typ?
        optional (bool, optional): Default-Wert erklären

    Returns:
        dict: Struktur erklären + Beispiel
        None: Wann wird None zurückgegeben?

    Raises:
        ValueError: Wann? Warum?
        ConnectionError: Wann? Wie recover?

    Side Effects:
        - Mutiert self.state
        - Schreibt in ~/.stealth/intents.jsonl
        - Startet Chrome-Prozess

    Race Conditions:
        - Nicht thread-safe (nutzt globalen State)
        - Chrome Window kann sich ändern während wir klicken

    BANNED in dieser Funktion:
        ❌ Kein playstealth launch hier!
        ❌ Keine hardcoded PIDs!

    Example:
        >>> result = meine_funktion("test", 42)
        >>> print(result["status"])
        'ok'
    """
    # ============================================================================
    # IMPLEMENTIERUNGS-LEVEL KOMMENTAR (jede Zeile wenn nötig)
    # ============================================================================
    # WARUM try/except hier? Weil CDP WebSocket kann 403 Forbidden werfen
    # wenn Chrome mit falschem --remote-allow-origins gestartet wurde.
    try:
        # WARUM urllib.request statt requests? Kein externe Dependency.
        pages = json.loads(urllib.request.urlopen(url).read())
    except Exception as e:
        # WARUM nicht raise? Weil wir graceful degraden wollen.
        # Der Caller kann dann Fallback nutzen (cua-driver statt CDP).
        print(f"[WARN] CDP failed: {e}")
        return None
```

### R2: JEDE KONSTANTE DOKUMENTIEREN

```python
# WARUM 15? Nicht 10 (zu kurz für komplexe DOMs) oder 30 (zu lang, blockiert Loop).
# Erfahrungswert: 95% der Seiten laden in <10s, 15s fängt langsame Provider ab.
TIMEOUT_PAGE_LOAD = 15

# WARUM 20? Ursprünglich 5, aber Surveys scheitern oft an Captchas.
# 20 erlaubt mehr Fehler bevor Watch-Loop stoppt.
MAX_CONSECUTIVE_ERRORS = 20

# WARUM 2.0? Nicht 1.0 (zu schnell, SPA re-rendered nicht fertig)
# oder 5.0 (zu langsam, 5s × 50 Fragen = 250s pro Survey).
WAIT_BETWEEN_ACTIONS = 2.0
```

### R3: VERIFY-BOX PATTERN (nach JEDER Aktion)

```python
# ============================================================================
# VERIFY-BOX PATTERN — NIEMALS blind weitermachen!
# ============================================================================
def click_and_verify(pid, wid, idx, expected_state=None):
    """
    Klickt ein Element und VERIFIZIERT dass der Zustand erreicht wurde.

    WARUM Verify?
      Ohne Verify: cua-driver sagt "Performed", aber Radio-Button
      wurde NICHT selektiert (JS-Event-Listener hat nicht gefeuert).
      → Agent wird belogen, macht 10 Schritte blind weiter.
      → Survey disqualifiziert, 30min verschwendet.

    Returns:
        bool: True nur wenn Zustand VERIFIZIERT erreicht.
    """
    # 1. Aktion ausführen
    result = _cua(pid, wid, "click", {"element_index": idx})
    if "performed" not in result.get("stdout", "").lower():
        return False

    # 2. NEU scannen (gleiches Window)
    tree = _tree(pid, wid)

    # 3. Zustand prüfen
    if expected_state:
        # Beispiel: RadioButton → selected=true?
        for line in tree:
            if f"[{idx}]" in line and "selected" in line.lower():
                return True
        return False

    return True
```

---

## 2. SESSION-MANAGEMENT — STATE OF THE ART

### S1: Session Lifecycle (explizit, nicht implizit)

```python
# ============================================================================
# SESSION LIFECYCLE — Jede Session hat EXPLIZITE Phasen
# ============================================================================
class SessionManager:
    """
    Zustands-Maschine für jede Chrome-Session.

    States:
        CREATED   → Chrome gestartet, noch nicht bereit
        HEALTHY   → Chrome läuft, CDP erreichbar, Dashboard sichtbar
        LOGGED_IN → Login erfolgreich verifiziert
        RUNNING   → Survey-Loop aktiv
        DEGRADED  → Chrome läuft, aber Fehlerrate hoch
        STOPPED   → Chrome beendet, Session aufgeräumt
        CRASHED   → Chrome abgestürzt, Recovery nötig

    WARUM State Machine?
      Implizite States ("irgendwie läuft es") führen zu:
      - Race Conditions (Survey startet vor Login)
      - Resource Leaks (Chrome-Prozesse akkumulieren)
      - Falschen Entscheidungen (Agent denkt er ist eingeloggt)
    """

    def transition(self, new_state):
        """
        EXPLIZITE Transition mit Validierung.

        WARUM nicht einfach `self.state = X`?
          Weil nicht jeder State-Wechsel erlaubt ist!
          Beispiel: RUNNING → CREATED ist ILLEGAL.
        """
        valid_transitions = {
            "CREATED": ["HEALTHY", "STOPPED", "CRASHED"],
            "HEALTHY": ["LOGGED_IN", "DEGRADED", "STOPPED", "CRASHED"],
            "LOGGED_IN": ["RUNNING", "DEGRADED", "STOPPED", "CRASHED"],
            "RUNNING": ["DEGRADED", "STOPPED", "CRASHED"],
            "DEGRADED": ["HEALTHY", "STOPPED", "CRASHED"],
            "STOPPED": ["CREATED"],
            "CRASHED": ["CREATED", "STOPPED"],
        }
        if new_state not in valid_transitions.get(self.state, []):
            raise ValueError(
                f"ILLEGAL Transition: {self.state} → {new_state}\n"
                f"Erlaubt: {valid_transitions.get(self.state, [])}"
            )
        self._log_transition(self.state, new_state)
        self.state = new_state
```

### S2: Graceful Shutdown

```python
# ============================================================================
# SIGNAL HANDLER — NIEMALS Chrome brutal beenden!
# ============================================================================
import signal

def shutdown(signum, frame):
    """
    Graceful Shutdown bei SIGTERM/SIGINT.

    WARUM nicht einfach exit()?
      - Chrome-Prozess läuft weiter → Resource Leak
      - CDP WebSocket bleibt offen → Port 9224 blockiert
      - ~/.stealth/sessions.json wird nicht aktualisiert
      - Nächster Start scheitert an "Port in use"

    Steps:
      1. State → STOPPED
      2. Chrome Tabs schließen (nicht Prozess killen!)
      3. CDP WebSocket schließen
      4. Registry leeren (~/.stealth/sessions.json)
      5. Log schreiben (Duration, Ergebnis, Fehler)
      6. exit(0)
    """
    state["running"] = False
    _close_all_tabs()
    _close_cdp_ws()
    _clear_registry()
    _write_session_log()
    sys.exit(0)

signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)
```

---

## 3. ERROR-HANDLING — STATE OF THE ART

### E1: NIE `except:` oder `except Exception:` ohne Logging

```python
# ============================================================================
# BAD — Information geht verloren
# ============================================================================
try:
    ws.send(json.dumps(msg))
    r = json.loads(ws.recv())
except:  # ❌ BAD: Welcher Exception-Typ? Was war die Ursache?
    pass

# ============================================================================
# GOOD — Jede Exception wird kategorisiert, geloggt, und mit Context versehen
# ============================================================================
try:
    ws.send(json.dumps(msg))
    r = json.loads(ws.recv())
except websocket.WebSocketTimeoutException as e:
    # WARUM Timeout? Chrome nicht erreichbar, oder Page hängt?
    log_error("cdp_timeout", {
        "url": ws_url,
        "timeout": timeout,
        "chrome_alive": is_chrome_alive(port),
        "exception": str(e),
    })
    raise RecoverableError("CDP timeout — retry with backoff")
except json.JSONDecodeError as e:
    # WARUM JSON Error? CDP Antwort ist kein JSON → Chrome Version mismatch?
    log_error("cdp_malformed_response", {
        "raw_response": getattr(ws, "last_recv", "")[:200],
        "exception": str(e),
    })
    raise FatalError("CDP protocol mismatch — Chrome restart required")
except Exception as e:
    # UNEXPECTED — sollte NIE passieren. Wenn doch: SOFORT STOP.
    log_error("unexpected_cdp_error", {
        "exception_type": type(e).__name__,
        "exception": str(e),
        "stacktrace": traceback.format_exc(),
    })
    raise CriticalError(f"Unexpected: {type(e).__name__}")
```

### E2: Exponential Backoff

```python
# ============================================================================
# BACKOFF — NIE sofort retry, NIE fixed delay
# ============================================================================
def calculate_backoff(attempt, base=2, max_wait=60):
    """
    Exponential Backoff mit Jitter.

    WARUM Exponential?
      - Sofort-Retry: Überlastet den Server/Chrome
      - Fixed delay: Wartet unnötig bei temporären Fehlern
      - Exponential: Schnell bei schnellen Recovery, langsam bei dauerhaften Fehlern

    WARUM Jitter?
      - Ohne Jitter: Alle Clients retry gleichzeitig → Thundering Herd
      - Mit Jitter: Verteilt die Last

    Formula: min(max_wait, base^attempt) + random(0, 1)
    """
    import random
    wait = min(max_wait, base ** attempt)
    return wait + random.random()
```

---

## 4. TESTING — STATE OF THE ART

### T1: Jede Funktion hat mindestens 3 Tests

```python
# ============================================================================
# TEST PYRAMIDE
# ============================================================================
# Unit Test       (70%): Einzelne Funktionen, Mocked Dependencies
# Integration Test (20%): Mehrere Module zusammen, Mocked Chrome
# E2E Test        (10%): Voller Flow mit echtem Chrome (langsam, teuer)

class TestAutoGoogleLogin:
    """
    Test-Suite für auto_google_login.execute()

    WARUM so viele Tests?
      - Diese Funktion hat 8 CRITICAL BUGS dokumentiert (siehe auto_google_login.py)
      - Jeder Bug = 1 Regression Test
      - Login ist der erste Schritt — wenn der fehlschlägt, läuft NICHTS.
    """

    def test_execute_already_logged_in(self, mock_windows):
        """
        Test: HeyPiggy bereits eingeloggt → Sofortiger Return.

        WARUM wichtig? Vermeidet unnötiges Chrome-Starten und OAuth.
        """
        mock_windows.return_value = [{
            "title": "Umfragen - HeyPiggy",
            "bounds": {"height": 800},
            "app_name": "Google Chrome",
            "pid": 12345,
            "window_id": 67890,
        }]
        result = execute()
        assert result["status"] == "ok"
        assert result["pid"] == 12345
        # WARUM assert pid? Wenn PID falsch, arbeitet Agent auf falschem Chrome.

    def test_execute_google_oauth_new_wid(self, mock_windows, mock_tree):
        """
        Test: OAuth öffnet NEUE Window ID.

        WARUM wichtig? BUG 5: Alter Code blieb auf Dashboard-WID.
        → Klick landete auf Dashboard statt OAuth Popup.
        """
        # Erster Call: Dashboard
        # Zweiter Call: OAuth (neue WID)
        mock_windows.side_effect = [
            [{"title": "Dashboard", "bounds": {"height": 800}, ...}],
            [{"title": "Anmelden - Google", "bounds": {"height": 600}, ...}],
        ]
        result = execute()
        assert result["status"] == "ok"

    def test_execute_keychain_autofill(self, mock_tree):
        """
        Test: Keychain Auto-Fill erkannt → NUR "Fortfahren" klicken.

        WARUM wichtig? Wenn Keychain aktiv, gibt es KEIN Passwort-Feld.
        Agent darf nicht auf Passwort-Feld warten.
        """
        mock_tree.return_value = [
            '- [62] AXButton "Fortfahren" @(1090,689,94,30)',
            '- [41] AXButton "Weiter" @(966,786,220,40)',
        ]
        result = execute()
        assert result["status"] == "ok"
        # Verify: NICHT auf "Passwort" gesucht
```

### T2: Test-Dateien neben Source (nicht in tests/)

```
cli/modules/
├── auto_google_login.py
├── auto_google_login_test.py      # ← HIER (nicht in tests/)
├── session_manager.py
└── session_manager_test.py
```

**WARUM neben Source?**
- Agent sieht sofort: "Oh, Test-Datei existiert"
- Kein Navigation durch tests/ Verzeichnis
- Import-Pfad identisch (kein `sys.path` hack)

---

## 5. DOKUMENTATION — STATE OF THE ART

### D1: Jede Datei hat einen Doc-Header (mindestens 50 Zeilen)

Siehe R1 oben.

### D2: BANNED-Methoden in JEDER Datei dokumentieren

```python
# ============================================================================
# BANNED METHODS — NIEMALS VERWENDEN (in dieser Datei und überall)
# ============================================================================
# ❌ playstealth launch
#    WARUM: Setzt NICHT --force-renderer-accessibility
#    FOLGE: AX-Tree leer → cua-driver findet keine Elemente
#    ALTERNATIVE: Chrome MANUELL starten mit --force-renderer-accessibility
#
# ❌ webauto-nodriver
#    WARUM: Dead Project, keine Updates, instabil
#    FOLGE: Kann Chrome crashen, Credentials leaken
#    ALTERNATIVE: CDP WebSocket oder cua-driver
#
# ❌ cua-driver click (raw element_index)
#    WARUM: Index ist instabil (DOM ändert sich)
#    FOLGE: Klickt falsches Element → Daten verloren
#    ALTERNATIVE: Label-basiertes Matching oder BatchExecutor
#
# ❌ pkill -f "Google Chrome"
#    WARUM: Tötet USER Chrome + BOT Chrome
#    FOLGE: User verliert Tabs, Sessions, Arbeit
#    ALTERNATIVE: NUR Bot-PIDs killen (SessionManager.close_all())
#
# ❌ Hardcoded PIDs (71104, 56640, etc.)
#    WARUM: PIDs sind DYNAMISCH (ändern sich bei jedem Start)
#    FOLGE: Agent arbeitet auf falschem Prozess
#    ALTERNATIVE: PID zur Laufzeit finden (ps, cua-driver list_windows)
```

### D3: Änderungen SOFORT dokumentieren

```python
# ============================================================================
# CHANGELOG (oben in Datei, oder separate CHANGELOG.md)
# ============================================================================
# 2026-05-08: _find_logged_in_heypiggy() hinzugefügt
#   - WARUM: Login-Schleife erkannt (0 Surveys seit Tagen)
#   - WAS: Prüft VOR Login ob bereits eingeloggt
#   - VERIFIZIERUNG: Test `test_execute_already_logged_in`
#
# 2026-05-07: IndentationError behoben (8 spaces → 4 spaces)
#   - WARUM: SyntaxError blockierte survey.py komplett
#   - DATEI: survey-cli/survey.py:199
#   - VERIFIZIERUNG: `python3 -m py_compile survey.py`
#
# 2026-05-05: Keychain Auto-Fill Discovery
#   - WARUM: Google OAuth zeigt KEIN Passwort-Feld wenn Keychain aktiv
#   - WAS: NUR "Fortfahren" klicken statt Passwort eingeben
#   - VERIFIZIERUNG: Live-Test DYNAMIC_PID (aktuell: 24378)
```

---

## 6. CODE REVIEW CHECKLIST

### Vor jedem Commit:

- [ ] **Kommentare**: Jede Funktion hat Docstring (Args, Returns, Side Effects)
- [ ] **Konstanten**: Jede Magische Zahl ist dokumentiert (Warum dieser Wert?)
- [ ] **BANNED**: BANNED-Methoden in Datei-Header dokumentiert
- [ ] **Verify**: Jede Aktion hat Verify-Step (oder Begründung warum nicht)
- [ ] **Tests**: Neue Funktion = Neue Test-Funktion (mindestens 3 Fälle)
- [ ] **Error-Handling**: Kein bare `except:` oder `except Exception:`
- [ ] **Logging**: Jeder Fehler wird mit Context geloggt (nicht nur `print()`)
- [ ] **State**: Session-State explizit (nicht implizit)
- [ ] **PIDs**: Keine hardcoded PIDs (dynamisch finden)
- [ ] **Chrome**: Kein `pkill -f "Google Chrome"` (NUR Bot-Chrome)
- [ ] **Dependencies**: Neue Imports dokumentiert (Warum dieses Paket?)

---

## 7. NAMING CONVENTIONS

### Funktionen
```python
# VERB + NOUN (was macht es? + worauf?)
_find_bot_wid()           # ✅ Findet Bot Window ID
_click_element()          # ✅ Klickt Element
_login()                  # ❌ Zu generisch (welcher Login?)
_heypiggy_google_login()  # ✅ Spezifisch
```

### Variablen
```python
# KONSTANTEN: UPPER_SNAKE_CASE
cdp_port = 9999           # ❌ Konstante
cdp_port = 9999           # ✅... aber besser: CDP_DEFAULT_PORT = 9999

# Variablen: snake_case
pid = 12345               # ❌ Zu kurz
chrome_pid = 12345        # ✅ Beschreibend
dashboard_wid = 67890     # ✅ Beschreibend
```

---

## 8. PERFORMANCE — STATE OF THE ART

### P1: Token-Effizienz (NEMO)

```python
# ============================================================================
# NEMO LOOP — 1 LLM Call pro Frage-Batch
# ============================================================================
# ZIEL: ~500 tokens in, ~100 tokens out pro Seite
# VGL:  cua-driver Loop = ~5000+ tokens in, 20+ calls pro Seite
#       NEMO Loop       = ~500 tokens in, 3 calls pro Seite
# ERSPARNIS: 90% tokens, 5× schneller

# IMPLEMENTIERUNG:
#   1. Compact Snapshot (skylight-cli / CDP) → ~200 tokens
#   2. NIM Decision (NVIDIA) → ~100 tokens
#   3. Batch Execute (CDP WebSocket) → 1 call
#   TOTAL: 3 calls pro Seite (nicht 20+)
```

### P2: Caching

```python
# ============================================================================
# AX-TREE CACHE — NIE mehrfach scannen
# ============================================================================
# WARUM? get_window_state() dauert 500ms-2s.
# Wenn wir 50 Elemente klicken = 50 × 2s = 100s = 1.6min verschwendet.
#
# LÖSUNG: Einmal scannen, zwischengespeichert, nur bei DOM-Änderung neu scannen.
# Erkennung von DOM-Änderung: MutationObserver oder CDP Event.
```

---

## 9. SECURITY — STATE OF THE ART

### SEC1: Credentials NIEMALS im Code

```python
# ❌ BAD: Hardcoded im Code
email = "zukunftsorientierte.energie@gmail.com"

# ✅ GOOD: Env-Variable oder Infisical
email = os.getenv("HEYPIGGY_EMAIL")
if not email:
    raise ConfigurationError("HEYPIGGY_EMAIL not set")
```

### SEC2: API Keys rotieren

```python
# ~/.stealth/api_keys.json
{
  "keys": [
    {"id": "key-001", "value": "fw_...", "added": "2026-05-05", "status": "active", "failures": 0},
    {"id": "key-reserve-001", "value": "", "added": null, "status": "empty"}
  ]
}
# WARUM Reserve-Keys? Wenn aktiver Key ausfällt (Rate Limit, Expired),
# → Rotator schaltet auf Reserve um (kein manueller Eingriff nötig).
```

---

## 10. CHECKLISTE — NEUE DATEI ERSTELLEN

Wenn du eine neue Datei erstellst:

1. [ ] Doc-Header (50+ Zeilen: WAS, ARCHITEKTUR, DEPENDENZEN, BANNED)
2. [ ] Jede Funktion: Docstring (Args, Returns, Side Effects, Race Conditions)
3. [ ] Jede Konstante: Kommentar (Warum dieser Wert?)
4. [ ] Jede Aktion: Verify-Step (oder Begründung)
5. [ ] Error-Handling: Kategorisiert, geloggt, Context
6. [ ] Tests: Mindestens 3 Tests (Happy Path, Edge Case, Error Case)
7. [ ] CHANGELOG: Erste Eintrag mit Datum + Warum
8. [ ] BANNED-Methoden: In Datei-Header und vor jeder riskanten Operation
9. [ ] Session-State: Explizit, nicht implizit
10. [ ] Review: Ein anderer Agent (oder du selbst in 1 Stunde) liest die Datei

---

## 11. LOGGING — STATE OF THE ART

### L1: Structured Logging (JSONL, nicht plaintext)

```python
# ============================================================================
# ❌ BAD: Unstrukturiertes Logging — nicht analysierbar
# ============================================================================
print(f"Login failed: {reason}")

# ============================================================================
# ✅ GOOD: Strukturiertes JSONL Logging — maschinell analysierbar
# ============================================================================
import json, datetime

def log_event(event_type: str, status: str, data: dict):
    """
    Schreibt strukturiertes Event in JSONL-Datei.

    WARUM JSONL?
      - Jede Zeile ist ein valides JSON → einfach zu parsen
      - Append-only → kein Locking nötig
      - Maschinell analysierbar (jq, pandas, duckdb)
      - Time-Stamped → Leicht zu korrelieren
      - Human-readable → Debugging direkt mit cat/tail

    WARUM nicht SQLite?
      - Overkill für einfaches Logging
      - Benötigt Schema-Migration
      - Schwerer zu greppen

    Fields (MUSS in JEDEM Event):
      - timestamp: ISO 8601 mit UTC
      - event: Event-Typ (z.B. "cdp_timeout", "survey_completed")
      - status: "ok", "error", "warn", "info"
      - pid: Chrome PID (NULL wenn nicht zutreffend)
      - data: Dict mit Event-spezifischen Daten
    """
    entry = {
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "event": event_type,
        "status": status,
        **data,
    }
    with open("survey-cli/logs/events.jsonl", "a") as f:
        f.write(json.dumps(entry) + "\n")
```

### L2: Log-Level (nicht alles auf gleichem Level)

```python
# ============================================================================
# LOGGING LEVELS — Bei welchem Level wird WAS geloggt?
# ============================================================================
# INFO    — Normale Operation (Login OK, Survey gestartet, Survey beendet)
# WARN    — Recoverable Fehler (CDP Timeout, Retry, Backoff)
# ERROR   — Fehler die den aktuellen Survey abbrechen (Tab-Crash, Blocked)
# CRITICAL— Fehler die den gesamten Daemon stoppen (Chrome tot, 20× Error)
# DEBUG   — Entwicklungs-Info (Element-Indices, Response-JSON, Timings)

def _log_survey_result(result: SurveyResult):
    if result.status == "completed":
        log_event("survey_completed", "info", {
            "survey_id": result.survey_id,
            "provider": result.provider,
            "earned": result.earned,
            "iterations": result.iterations,
            "nim_calls": result.nim_calls,
            "nim_tokens": result.nim_tokens,
        })
    elif result.status == "screen_out":
        log_event("survey_screenout", "warn", {
            "survey_id": result.survey_id,
            "provider": result.provider,
        })
    elif result.status == "error":
        log_event("survey_error", "error", {
            "survey_id": result.survey_id,
            "error": result.error,
            "iterations": result.iterations,
        })
```

### L3: Log Rotation (sonst explodiert die Festplatte)

```python
# ============================================================================
# LOG ROTATION — max 100MB pro Log-Datei, max 10 Backups
# ============================================================================
# WARUM? survey-cli/logs/events.jsonl wächst ~1MB/Tag bei 24/7 Betrieb.
# Ohne Rotation: Nach 1 Jahr = 365MB → Datei zu groß für cat/tail.
import os

def ensure_log_rotation(path: str, max_size_mb=100, max_backups=10):
    """
    Rotiert Log-Datei wenn > max_size_mb.
    Behält max_backups alte Dateien.
    WARUM 100MB? Genug für ~3 Monate Logs.
    WARUM 10 Backups? Genug für ~2.5 Jahre Logs.
    """
    if os.path.exists(path) and os.path.getsize(path) > max_size_mb * 1024 * 1024:
        for i in range(max_backups - 1, -1, -1):
            src = f"{path}.{i}" if i > 0 else path
            dst = f"{path}.{i + 1}"
            if os.path.exists(src):
                os.rename(src, dst)
```

---

## 12. MONITORING & ALERTING — STATE OF THE ART

### M1: Health Metrics (Was überwachen wir?)

```python
# ============================================================================
# HEALTH METRICS — MINDESTENS diese Metriken sammeln und prüfen
# ============================================================================
class HealthMetrics:
    """
    Zentrale Stelle für alle Health-Metriken.

    WARUM Klasse? Kapselt Berechnung und Schwellwerte.
    WARUM nicht global? Testbar (Dependency Injection).
    """

    def check_all(self) -> dict:
        """
        Führt ALLE Health-Checks aus und gibt Status zurück.

        WARUM ALLE auf einmal? Kein Teilerfolg — entweder alles OK
        oder wir wissen genau was fehlt.

        Checks:
          1. Chrome läuft und CDP erreichbar (Port 9224)
          2. cua-driver Daemon läuft (pgrep -f "cua-driver serve")
          3. Dashboard-Tab existiert (find_dashboard_ws)
          4. Login-Status (document.title.includes('Umfragen'))
          5. NVIDIA_API_KEY gesetzt (wenn use_nim=True)
          6. Accessibility aktiv (system_profiler SPAccessibilityDataType)
          7. Balance < 5.00€ (sonst → Target erreicht, aufhören)
          8. Surveys verfügbar (>0 auf Dashboard)
          9. Log-Dateien nicht zu groß (<100MB)
          10. Keine korrupten Session-Dateien (~/.stealth/sessions.json)
        """
        return {
            "chrome_alive": self._check_chrome(),
            "cua_daemon": self._check_cua_daemon(),
            "dashboard_ws": self._check_dashboard(),
            "login": self._check_login(),
            "nim_api_key": self._check_nim_key(),
            "accessibility": self._check_accessibility(),
            "balance_ok": self._check_balance(),
            "surveys_available": self._check_surveys(),
            "logs_ok": self._check_logs(),
            "sessions_ok": self._check_sessions(),
        }
```

### M2: Alerting (Wann Alarm schlagen?)

```python
# ============================================================================
# ALERTING REGELN — Wann schlagen wir Alarm?
# ============================================================================
# RULE 1: 3× aufeinanderfolgender Login-Failure → ALARM
#   → WARUM? Login-Loop erkannt (Issue #1). 0 Surveys = 0 Einnahmen.
#   → ACTION: Agent stoppen, cua-driver Daemon prüfen, Accessibility prüfen.
#
# RULE 2: Chrome tot >60s → ALARM
#   → WARUM? Chrome crasht und erholt sich nicht selbst.
#   → ACTION: Chrome neu starten mit korrekten Flags.
#
# RULE 3: Balance ≥ Target (5.00€) → ALARM (positiv!)
#   → WARUM? Auszahlung möglich → menschlicher Operator sollte auszahlen.
#   → ACTION: Notifikation an Operator.
#
# RULE 4: 20× aufeinanderfolgende Errors → ALARM (FATAL)
#   → WARUM? System ist irreparabel kaputt (NVIDIA Key expired, Chrome broken).
#   → ACTION: Daemon stoppen, Issue erstellen, Operator benachrichtigen.
#
# RULE 5: Surveys Completed = 0 in letzten 24h → ALARM
#   → WARUM? Entweder keine Surveys verfügbar (normal) oder Login kaputt (Issue #1).
#   → ACTION: Login-Test ausführen, wenn OK → kein Alarm (keine Surveys = normal).
```

### M3: Dashboard (Übersicht auf einen Blick)

```bash
# survey.py status → zeigt ALLE Health-Metriken auf einen Blick
$ python3 survey-cli/survey.py status

==========================================
  SURVEY-CLI STATUS
==========================================

  Chrome:
    Running:  ✅
    PIDs:     DYNAMIC (aktuell: 24378)
    Port:     9999

  Dashboard:   ✅ Connected
  Balance:     2.47€

  NVIDIA NIM:
    API Key:   ✅ set
    Status:    ✅ ready
    Model:     nvidia/nemotron-3-nano-omni-30b-a3b-reasoning

  Health:
    cua-driver:    ✅ running
    Accessibility: ✅ enabled
    Login:         ✅ authenticated
    Surveys today: 3
    Errors today:  0
    Uptime:        4h 23m
```

---

## 13. DEPLOYMENT — STATE OF THE ART

### DEP1: Pre-Deployment Checklist

```
Vor JEDEM Deployment (push/commit):

 1. [ ] ALLE Python-Dateien kompilieren ohne SyntaxError:
        find . -name "*.py" -exec python3 -m py_compile {} \;

 2. [ ] ALLE Tests passen:
        python3 -m pytest survey-cli/tests/ -x

 3. [ ] Keine hardcoded Credentials im Code:
        rg "nvapi-|sk-|fw_|api_key\s*=" --type py && echo "❌ FOUND CREDS" || echo "✅ clean"

 4. [ ] Keine hardcoded PIDs:
        rg "\bpid\s*=\s*\d{4,6}\b" --type py && echo "❌ FOUND HARDCODED PID" || echo "✅ clean"

 5. [ ] Kein playstealth launch:
        rg "playstealth\s+launch" --type py && echo "❌ FOUND BANNED" || echo "✅ clean"

 6. [ ] Kein webauto-nodriver:
        rg "webauto" --type py && echo "❌ FOUND BANNED" || echo "✅ clean"

 7. [ ] Kein pkill -f "Google Chrome":
        rg "pkill.*Google Chrome" --type py && echo "❌ FOUND DANGEROUS" || echo "✅ clean"

 8. [ ] Alle AGENTS.md files valide YAML:
        find . -name "AGENTS.md" -exec python3 -c "import yaml; yaml.safe_load(open('{}'))" \;

 9. [ ] Keine dangling Imports:
        python3 -c "import survey.runner, survey.scanner, survey.chrome, survey.nim"

 10. [ ] OpenCode commands definiert:
         ls .opencode/commands/ | wc -l
         → 6 commands (login, scan, survey, balance, doctor, kill-bots)
```

### DEP2: Rollback-Plan

```python
# ============================================================================
# ROLLBACK-PLAN — Was tun wenn Deployment fehlschlägt?
# ============================================================================
# 1. git log --oneline -1 → Letzten Commit merken
# 2. git revert HEAD → Änderungen rückgängig
# 3. git revert <sha> → Falls commit bereits gepusht
# 4. ODER: git reset --hard HEAD~1 → Lokal zurücksetzen
#
# FALLS Chrome hängt nach Deployment:
#   ./survey.py kill           → Bot Chrome beenden
#   rm -f ~/.stealth/sessions.json  → Registry leeren
#   ./survey.py login           → Login neu
#
# FALLS NIM nicht erreichbar nach Deployment:
#   echo $NVIDIA_API_KEY        → Key checken
#   curl -H "Authorization: Bearer $NVIDIA_API_KEY" \
#        https://integrate.api.nvidia.com/v1/models
#   → Wenn 401 → Key expired → neuen Key holen
```

---

## 14. CODE-COMPLETENESS-VERIFICATION — STATE OF THE ART

### V1: Automatische Vollständigkeits-Checks

```python
# ============================================================================
# COMPLETENESS VERIFICATION — Prüfe JEDE Datei
# ============================================================================
# Jede Datei MUSS haben:
#   [ ] Datei-Header: WAS, ARCHITEKTUR, DEPENDENZEN, BANNED, HISTORY
#   [ ] Jede Funktion: Docstring (Args, Returns, Side Effects, Race Conditions)
#   [ ] Jede Konstante: WARUM-Kommentar
#   [ ] Jede Aktion: Verify (oder dokumentiert warum nicht)
#   [ ] Tests: mindestens 3 pro Funktion
#
# Jedes Modul MUSS haben:
#   [ ] __init__.py mit Public API documentation
#   [ ] __main__.py für CLI (wenn Modul ausführbar)
#   [ ] Test-Datei im gleichen Verzeichnis
#
# Jedes Repo MUSS haben:
#   [ ] sinrules.md (Zentrales Regelwerk)
#   [ ] brain.md (Architektur)
#   [ ] fix.md (Root Cause Fixes)
#   [ ] learn.md (Learnings)
#   [ ] anti-learn.md (Anti-Patterns)
#   [ ] banned.md (BANNED Patterns)
#   [ ] AGENTS.md (Agent Instructions)
#   [ ] README.md (Projekt-README)
#   [ ] CHANGELOG.md (Version History)
```

### V2: Doc-Health-Check

```bash
# Prüft ALLE 23 Repos auf Pflichtdateien
python3 scripts/check_doc_health.py

# Fehlende Pflichtdateien automatisch erstellen
python3 scripts/generate_missing_docs.py
```

---

## 15. CONTINUOUS IMPROVEMENT — STATE OF THE ART

### CI1: Nach jedem Survey-Run

```python
# ============================================================================
# AUTO-LEARNING — Nach jedem Survey automatisch lernen
# ============================================================================
# 1. Survey-Ergebnis analysieren
#    - Completed: Flow funktioniert → NICHTS tun (es läuft!)
#    - Screen-out: Profil passt nicht → learn.md aktualisieren
#    - Error: Bug gefunden → Issue erstellen + fix.md aktualisieren
#    - Blocked: Provider gesperrt → skip_providers aktualisieren
#
# 2. Token-Verbrauch tracken
#    - NIM Tokens pro Survey
#    - Erzielte Einnahmen (€) vs Token-Kosten ($)
#    - Break-even: ~100 Surveys/Tag ≈ $0.50 NIM Kosten
#
# 3. Performance-Metriken
#    - Survey pro Minute
#    - Conversion-Rate (completed / total)
#    - Average Earnings pro Survey (€)
#    - NIM Latenz (ms)
```

### CI2: Issue Creation Flow

```
ERKENNUNG → ANALYSE → ISSUE → FIX → DOKUMENTATION → VERIFIZIERUNG

1. ERKENNUNG: Ein Fehler tritt auf
   - Exception im Log
   - Survey screen-out (unerwartet)
   - Balance nicht gestiegen nach Survey

2. ANALYSE: Root Cause finden
   - 10-Punkte-Analyse (Root-Cause, Befehls-Prüfung, Session-Abgleich,
     Cross-Repo, Registry, W-Fragen, Pipeline, Memory, Doku-Update,
     Vollständigkeits-Check)

3. ISSUE: In issues/ erstellen
   - Format: issues/NNN-kurzbeschreibung.md
   - Status: OPEN, IN-PROGRESS, FIXED, VERIFIED
   - Severity: P0 (Kritisch), P1 (Wichtig), P2 (Normal)

4. FIX: Code ändern + Test hinzufügen
   - Regression-Test für genau diesen Fehler
   - BANNED-Methoden prüfen

5. DOKUMENTATION: In fix.md, learn.md, CHANGELOG
   - WAS war der Fehler?
   - WARUM ist er passiert?
   - WIE wurde er behoben?
   - TEST der den Fix verifiziert

6. VERIFIZIERUNG: Test läuft, CI/CD grün
   - ALLE bestehenden Tests passen weiterhin
   - Neuer Test verifiziert den Fix
```

---

**Dieses Dokument ist LEBENDIG. Aktualisiere es nach jedem Major Change.**

*Letzte Aktualisierung: 2026-05-08 — Erweitert um §§11-16: Logging, Monitoring, Deployment, Verification, Continuous Improvement, GitNexus & Graphify*

---

## 16. GITNEXUS & GRAPHIFY — CODE INTELLIGENCE LAYER

Siehe [GITNEXUS-GRAPHIFY.md](GITNEXUS-GRAPHIFY.md) für vollständige Dokumentation.

### GitNexus Health Check (in `survey.py doctor`)

```python
def _check_gitnexus():
    """Prüft GitNexus Index-Health. Returns dict mit installed, current, commits_behind."""
    import subprocess, json
    try:
        r = subprocess.run(["npx", "gitnexus@1.6.3", "--version"],
                          capture_output=True, text=True, timeout=15)
        installed = r.returncode == 0
    except Exception:
        installed = False

    commits_behind = 999
    if installed:
        meta_path = Path(".gitnexus/meta.json")
        if meta_path.exists():
            meta = json.loads(open(meta_path).read())
            indexed_commit = meta.get("lastCommit", "")
            current_head = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True, text=True
            ).stdout.strip()
            if indexed_commit != current_head:
                count = subprocess.run(
                    ["git", "rev-list", "--count", f"{indexed_commit}..HEAD"],
                    capture_output=True, text=True
                )
                commits_behind = int(count.stdout.strip() or "0")
    return {"installed": installed, "current": commits_behind == 0, "commits_behind": commits_behind}
```

### PFLICHT: Vor Code-Änderungen

```
1. gitnexus_detect_changes(scope="unstaged")  → Was ist betroffen?
2. gitnexus_impact(target="function", direction="upstream")  → Blast Radius?
3. gitnexus_context(name="ClassName")  → 360° View?
```
