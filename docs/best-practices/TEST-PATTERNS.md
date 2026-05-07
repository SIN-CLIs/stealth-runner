# TEST PATTERNS — Stealth-Runner Best Practices

> **Version**: 2026-05-08 v1.0
> **Scope**: Test-Strategie, Pyramid, Patterns, Coverage-Regeln
> **Status**: ACTIVE — 211 Tests in 15 Modulen, wachsend

---

## 1. TEST PYRAMIDE

```
         ╱ ╲
        ╱ E2E ╲          10% — Voller Flow mit echtem Chrome (langsam, teuer)
       ╱───────╲
      ╱Integration╲       20% — Mehrere Module, Mocked Chrome
     ╱─────────────╲
    ╱  Unit Tests   ╲     70% — Einzelne Funktionen, Mocked Dependencies
   ╱─────────────────╲
```

### Warum diese Verteilung?

```python
# UNIT TESTS (70%): Schnell (<1s), isoliert, verlässlich
# - Testen einzelne Funktionen
# - ALLE Dependencies gemockt
# - Läuft in <1ms pro Test
# - 211 existierende Tests = <1 Minute für komplette Suite

# INTEGRATION TESTS (20%): Mittel (1-10s), modul-übergreifend
# - Testen mehrere Module zusammen
# - Chrome/CDP gemockt (aber nicht die komplette Kette)
# - Läuft in ~1s pro Test

# E2E TESTS (10%): Langsam (10-60s), echter Chrome
# - Testen kompletten Flow mit echtem Chrome
# - Nur für KRITISCHE Pfade (Login, Survey-Start, Survey-Ende)
# - Läuft in ~30s pro Test
# - NICHT im CI/CD (nur manuell oder nightly)
```

---

## 2. TEST-MINIMUM: 3 Tests pro Funktion

**GOLDENE REGEL**: Jede Funktion hat MINDESTENS 3 Tests.

```python
def execute(pid=None, url="https://heypiggy.com/?page=dashboard"):
    """
    Hauptfunktion: Google OAuth Login.
    """
    ...

class TestAutoGoogleLogin:
    """
    Tests für execute().

    REGEL: 3 Tests pro Funktion = MINIMUM.
    - Happy Path (Erfolgreicher Fall)
    - Edge Case (Grenzfall)
    - Error Case (Fehlerfall)
    """

    # ── TEST 1: Happy Path ──
    def test_execute_already_logged_in(self, mock_windows):
        """
        Bereits eingeloggt → Sofortiger Return mit PID/WID.

        WARUM wichtig? Vermeidet unnötiges Chrome-Starten und OAuth.
        WARUM mock_windows? Kein echtes Chrome im Unit-Test.
        """
        mock_windows.return_value = [{
            "title": "Umfragen — HeyPiggy",
            "bounds": {"height": 800},
            "app_name": "Google Chrome",
            "pid": 12345,
            "window_id": 67890,
        }]
        result = execute()
        assert result["status"] == "ok"
        assert result["pid"] == 12345

    # ── TEST 2: Edge Case ──
    def test_execute_google_oauth_new_wid(self, mock_windows, mock_tree):
        """
        OAuth öffnet NEUE Window ID → Code findet neue WID.

        WARUM wichtig? BUG 5: Alter Code blieb auf Dashboard-WID.
        → Klick landete auf Dashboard statt OAuth Popup.
        → Dieses Test verhindert Regression von BUG 5.
        """
        mock_windows.side_effect = [
            [{"title": "Dashboard", "bounds": {"height": 800}, "pid": 99, "window_id": 10}],
            [{"title": "Anmelden – Google", "bounds": {"height": 600}, "pid": 99, "window_id": 20}],
        ]
        result = execute()
        assert result["status"] == "ok"

    # ── TEST 3: Error Case ──
    def test_execute_no_chrome_windows(self, mock_windows):
        """
        Keine Chrome-Windows gefunden → Error-Return.

        WARUM wichtig? Graceful degradation — kein Crash.
        WARUM nicht raise? execute() soll Fehler als Dict zurückgeben.
        """
        mock_windows.return_value = []  # Leere Liste — keine Windows
        result = execute()
        assert result["status"] == "error"
        assert "reason" in result
```

---

## 3. MOCKING-STRATEGIE

```python
# ============================================================================
# MOCKING — WAS wird gemockt, WAS nicht?
# ============================================================================

# WAS WIRD IMMER GEMOCKT:
#   → cua-driver Binary (subprocess.run)    — Kein echtes Binary im Test
#   → Google Chrome App                     — Kein echter Browser im Unit-Test
#   → CDP WebSocket (websocket.connect)     — Keine echte CDP-Verbindung
#   → NVIDIA NIM API (HTTP POST)            — Keine API-Kosten im Test
#   → Dateisystem (~/.stealth/*)            — Keine Persistenz im Test
#   → Umgebungsvariablen (os.getenv)        — Test-Isolierung
#   → time.sleep()                          — Kein echtes Warten im Test

# WAS WIRD NIE GEMOCKT:
#   → Eigene Funktionen (ausser beim Test des Callers)
#   → Dataclasses (SurveyResult, AgentConfig)
#   → Python Standardlib (json, re, os.path)
#   → Logging-Funktionen (wenn Logs getestet werden)

# BEISPIEL: Mock-Konfiguration für auto_google_login Tests
@pytest.fixture
def mock_windows(mocker):
    """Mock für _windows() → list_windows response."""
    return mocker.patch(
        "cli.modules.auto_google_login._windows",
        return_value=[]
    )

@pytest.fixture
def mock_tree(mocker):
    """Mock für _tree() → get_window_state response."""
    return mocker.patch(
        "cli.modules.auto_google_login._tree",
        return_value=""
    )

@pytest.fixture
def mock_run(mocker):
    """Mock für _run() → subprocess.run response."""
    mock = mocker.patch("cli.modules.auto_google_login._run")
    mock.return_value = mocker.MagicMock(
        stdout='{"status": "ok"}',
        stderr="",
        returncode=0
    )
    return mock

# BEISPIEL: Test mit allen Mocks
def test_complete_login_flow(mock_windows, mock_tree, mock_run):
    """
    Vollständiger Login-Flow mit allen gemockten Abhängigkeiten.

    WARUM alle mocks?
      Dieser Test läuft OHNE Chrome, OHNE cua-driver, OHNE Netzwerk.
      → <1ms statt 30s (echter Login)
      → Läuft in CI/CD ohne Chrome-Installation
    """
    # Setup: Mock konfigurieren
    mock_windows.return_value = [...]
    mock_tree.return_value = "..."
    mock_run.return_value.stdout = '{"windows": [...]}'

    # Ausführen
    result = execute()

    # Verifizieren
    assert result["status"] == "ok"
```

---

## 4. TEST-DATEIEN NEBEN SOURCE

```
cli/modules/
├── auto_google_login.py
├── auto_google_login_test.py      ← HIER (nicht in tests/)
├── session_manager.py
├── session_manager_test.py        ← HIER

src/stealth_survey/
├── survey_agent.py
├── survey_agent_test.py           ← HIER
├── nim_client.py
├── nim_client_test.py             ← HIER
├── compact_snapshot.py
├── compact_snapshot_test.py       ← HIER
├── batch_executor.py
├── batch_executor_test.py         ← HIER

survey-cli/
├── survey/
│   ├── runner.py
│   ├── runner_test.py             ← HIER
│   ├── scanner.py
│   ├── scanner_test.py            ← HIER
│   ├── chrome.py
│   ├── chrome_test.py             ← HIER
```

**WARUM neben Source?**
- Agent sieht sofort: "Oh, Test existiert"
- Kein Navigation durch `tests/` Verzeichnis
- Import-Pfad identisch (kein `sys.path` Hack)
- Wenn Datei verschoben wird → Test folgt automatisch

---

## 5. TEST-NAMING CONVENTION

```python
# FORMAT: test_{method}_{scenario}

# ✅ GOOD:
test_execute_already_logged_in()     # Klar: execute(), bereits eingeloggt
test_click_radio_single_option()     # Klar: click_radio(), eine Option
test_find_wid_no_chrome_windows()    # Klar: find_wid(), keine Fenster
test_survey_agent_timeout()          # Klar: SurveyAgent, Timeout-Fall

# ❌ BAD:
test_login1()                        # Unklar: Welches Szenario?
test_error()                          # Unklar: Welcher Fehler?
test_flow()                           # Unklar: Welcher Flow?
```

---

## 6. TEST-COVERAGE-REGELN

```python
# ============================================================================
# COVERAGE REGELN — Was MUSS getestet werden?
# ============================================================================

# MUSS (100% Coverage):
#   ✅ Jede public Funktion
#   ✅ Jeder BANNED-Pattern Guard (z.B. kein playstealth)
#   ✅ Jeder documented BUG (Regression Test!)
#   ✅ Jede Error-Handling Branch (try/except)
#   ✅ Jede Verify-Box (click_and_verify)

# SOLL (80% Coverage):
#   ✅ Edge Cases (leere Listen, None-Werte, Timeouts)
#   ✅ Konfiguration-Varianten (NIM an/aus, Debug an/aus)
#   ✅ Provider-spezifische Logik (Qualtrics, TolunaStart)

# KANN (60% Coverage):
#   ✅ Logging (wird es korrekt geloggt?)
#   ✅ Pretty-Printing (Ausgabe-Formatierung)

# Coverage-Check:
#   pytest --cov=cli/modules --cov=src/stealth_survey --cov=survey-cli/survey
#   → Sollte >80% Line Coverage sein
```

---

## 7. TESTS AUSFÜHREN

```bash
# Alle 211 Tests
python3 -m pytest survey-cli/tests/ -v

# Nur auto_google_login Tests
python3 -m pytest survey-cli/tests/test_auto_google_login.py -v

# Nur einen Test
python3 -m pytest survey-cli/tests/test_auto_google_login.py::TestAutoGoogleLogin::test_execute_already_logged_in -v

# Mit Coverage
python3 -m pytest survey-cli/tests/ --cov=cli/modules --cov=src/stealth_survey --cov-report=term

# Schnell (Exit bei erstem Fehler)
python3 -m pytest survey-cli/tests/ -x
```

---

## 8. TEST-ANTI-PATTERNS

```python
# ❌ ANTI-PATTERN 1: Echter Chrome im Unit-Test
def test_login():
    chrome = subprocess.run([...])  # Startet echten Chrome!
    # → 30s Laufzeit, braucht Chrome installiert, instabil

# ✅ RICHTIG: Mocked Chrome
def test_login(mock_chrome, mock_cdp):
    mock_chrome.return_value = {"pid": 99999}
    result = execute()
    assert result["status"] == "ok"

# ❌ ANTI-PATTERN 2: Keine Assertions
def test_execute():
    execute()  # Kein assert!
    # → Test "passed" immer — wertlos

# ✅ RICHTIG: Immer assert
def test_execute():
    result = execute()
    assert result is not None
    assert result["status"] in ("ok", "error")

# ❌ ANTI-PATTERN 3: Test hängt von anderen Tests ab
shared_state = None  # ❌ Global!

def test_a():
    global shared_state
    shared_state = execute()

def test_b():
    global shared_state
    assert shared_state["status"] == "ok"  # ❌ Hängt von test_a() ab!

# ✅ RICHTIG: Jeder Test ist unabhängig
def test_a():
    result = execute()
    assert result["status"] in ("ok", "error")

def test_b():
    result = execute()
    assert result["status"] in ("ok", "error")

# ❌ ANTI-PATTERN 4: time.sleep() in Tests
def test_click():
    click()
    time.sleep(5)  # ❌ Wartet 5 Sekunden!

# ✅ RICHTIG: Mock time.sleep()
def test_click(mocker):
    mock_sleep = mocker.patch("time.sleep")
    click()
    mock_sleep.assert_called_once_with(0.5)  # Verify korrekter Sleep
```

---

## 9. REGRESSION-TEST FÜR JEDEN BUG

```python
# REGEL: Jeder Bug-Fix = 1 Regression-Test

# BUG 1: list_windows returns DICT not ARRAY (behoben)
def test_bug1_list_windows_returns_dict(self):
    """
    Regression-Test für BUG 1.

    WAS: cua-driver gibt {"windows": [...]} zurück, nicht [...].
    FIX: windows = d.get("windows", []) if isinstance(d, dict) else []
    """
    # Simuliere falsche cua-driver Antwort
    mock_response = '{"windows": [{"pid": 99, "window_id": 10}]}'
    result = parse_windows(mock_response)
    assert len(result) == 1
    assert result[0]["pid"] == 99

# BUG 5: Google OAuth opens NEW WID (behoben)
def test_bug5_oauth_new_wid(self, mock_windows):
    """
    Regression-Test für BUG 5.

    WAS: Code blieb auf Dashboard-WID nach OAuth Popup.
    FIX: Nach click → neue WID finden.
    """
    mock_windows.side_effect = [
        [{"title": "Dashboard", "bounds": {"height": 800}, ...}],
        [{"title": "Anmelden", "bounds": {"height": 600}, ...}],
    ]
    result = execute()
    # Sicherstellen dass auf neue WID geklickt wurde
    assert result["status"] == "ok"
```

---

*Letzte Aktualisierung: 2026-05-08*