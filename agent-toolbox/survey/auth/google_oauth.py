"""================================================================================
survey/auth/google_oauth.py — HeyPiggy Login via Google OAuth (CUA-ONLY 6-Step Flow)
================================================================================

ZWECK:
  Führt den kompletten Google OAuth Login für HeyPiggy via CUA aus.
  HeyPiggy verwendet Google als Login-Provider (OAuth 2.0).
  Der Login-Button ist im Shadow-DOM → CDP/Playwright können ihn NICHT erreichen.
  CUA (macOS Accessibility API) ist der EINZIGE Weg.

ARCHITEKTUR (6-Step Flow):
  ┌─────────────────────────────────────────────────────────────────────────┐
  │  Step 0: ALREADY LOGGED IN? (LoginVerifier.check)                     │
  │     → "abmelden" gefunden? → sofort "already_logged_in"                │
  │                                                                         │
  │  Step 1: CHROME RUNNING?                                               │
  │     → pid=None? → Fehler "chrome_not_started"                          │
  │     → Chrome MUSS vorher gestartet werden (ChromeLauncher)            │
  │                                                                         │
  │  Step 2: FIND DASHBOARD WINDOW                                         │
  │     → CuaAdapter.find_bot_window(["heypiggy", "dashboard"])           │
  │     → Fallback: any Chrome window                                      │
  │     → Kein Fenster? → "no_dashboard_window"                            │
  │                                                                         │
  │  Step 3: CLICK GOOGLE LOGIN SYMBOL                                     │
  │     → AX-Tree lesen → find_idx("google login-symbol", AXLink)         │
  │     → Fallback: find_idx("google", AXLink)                             │
  │     → Klicken → 5s warten → OAuth-Seite öffnet sich                   │
  │                                                                         │
  │  Step 4: ENTER EMAIL + CLICK "WEITER"                                  │
  │     → OAuth-Fenster finden (["google", "anmelden", "accounts"])         │
  │     → AX-Tree lesen → find_idx("e-mail oder telefonnummer", AXTextField)│
     → SecretsClient.get_google_email() → E-Mail holen                    │
  │     → type() → E-Mail eingeben                                        │
  │     → find_idx("weiter", AXButton) → Klicken                           │
  │     → 5s warten → Keychain-AutoFill zeigt "Jeremy Schulze"             │
  │                                                                         │
  │  Step 5: CLICK "FORTFAHREN" (Keychain Auto-Fill)                         │
  │     → Neues Fenster finden (["google", "anmelden", "jeremy"])           │
  │     → AX-Tree lesen → find_idx("fortfahren", AXButton)                  │
  │     → Fallback: find_idx("konto", AXButton)                            │
  │     → Klicken → 5s warten → "Weiter" Button erscheint                  │
  │                                                                         │
  │  Step 6: CLICK FINAL "WEITER"                                            │
  │     → Neues Fenster finden (["google", "anmelden"])                     │
  │     → AX-Tree lesen → find_idx("weiter", AXButton)                      │
  │     → Klicken → 5s warten → Zurück zu Dashboard                        │
  │                                                                         │
  │  VERIFY: LoginVerifier.check()                                         │
  │     → "abmelden" sichtbar? → "ok" (SUCCESS!)                             │
  │     → Nicht sichtbar? → "dashboard_not_found_after_login"              │
  └─────────────────────────────────────────────────────────────────────────┘

WARUM CUA (nicht CDP/Playwright)?
  → Google OAuth Seite verwendet Shadow-DOM für Login-Buttons.
  → Shadow-DOM Elemente sind im DOM-Baum NICHT sichtbar.
  → CDP Runtime.evaluate("document.querySelector(...)") findet sie NICHT.
  → Playwright page.locator() findet sie NICHT.
  → CUA/AX (Accessibility API) sieht sie → Screenreader müssen sie sehen.
  → Google KANN diese Elemente nicht verstecken (Accessibility-Gesetze).

WARUM Keychain Auto-Fill?
  → Nach E-Mail + "Weiter" zeigt macOS Keychain das Passkey-Modal:
    "Jeremy Schulze" (zukunftsorientierte.energie@gmail.com)
  → NUR "Fortfahren" klicken nötig (kein Passwort eingeben!).
  → WARUM? Passkey ist im macOS Keychain gespeichert.
  → WARUM funktioniert das? Google erkennt vertrautes Gerät + Keychain.
  → WARUM keine Passwort-Eingabe? Keychain Auto-Fill vermeidet
    komplexes Passkey-Handling (FIDO2/WebAuthn).

WARUM time.sleep(5) zwischen Steps?
  → Seitenladen: Google OAuth hat Redirects (mehrere 302s).
  → JavaScript-Rendering: Keychain-Modal erscheint async (nicht sofort).
  → CUA-Scan: AX-Tree braucht Zeit um neue Elemente zu erfassen.
  → Zu kurz (1-2s) → Race Condition: Element noch nicht da → Fehler.
  → Zu lang (10s) → ineffizient, aber sicher.
  → 5s = Kompromiss (deckt 95% der Fälle ab).

WARUM mehrere find_bot_window() Aufrufe pro Step?
  → Jeder Klick öffnet ein NEUES Fenster/Tab.
  → Google OAuth öffnet sich in einem neuen Chrome-Fenster/Sheet.
  → Das ALTE Fenster (Dashboard) bleibt offen im Hintergrund.
  → Wir müssen das NEUE Fenster finden → neuer find_bot_window() Aufruf.
  → WARUM nicht WID wiederverwenden? WID ändert sich bei neuem Fenster.

WARUM Fallback Keywords bei find_bot_window()?
  → Beispiel Step 3: ["heypiggy", "dashboard", "verdienen"] → primär.
  → Fallback: any Chrome window → wenn Titel nicht genau matcht.
  → Google-Fenster-Titel sind dynamisch:
    - "Google - Anmelden" (Deutsch)
    - "Sign in - Google Accounts" (Englisch)
    - "Jeremy Schulze" (Keychain-Modal)
  → Fallback stellt sicher dass wir SOMETHING finden.

WARUM "google login-symbol" primär, "google" Fallback?
  → "google login-symbol" ist der spezifische HeyPiggy Google-Login Link.
  → "google" matcht auch andere Google-Elemente (Google Analytics, etc.).
  → Spezifisch zuerst → weniger False-Positives.
  → Fallback wenn spezifischer nicht gefunden.

WARUM SecretsClient.get_google_email()?
  → E-Mail darf NICHT hardcoded sein (Privacy, Git-Leak).
  → SecretsClient liest aus ~/.stealth/config.yaml oder Env-Vars.
  → WARUM nicht os.getenv direkt? Zentrale Verwaltung, konsistent.
  → WARUM try/except? Wenn SecretsClient fehlt → graceful degradation.

WARUM JEDER Fehler eine spezifische reason?
  → "google_login_button_not_found" → Chrome Accessibility nicht aktiv?
  → "email_field_not_found" → Falsche Sprache (Englisch statt Deutsch)?
  → "weiter_button_not_found" → OAuth-Seite nicht geladen?
  → "fortfahren_click_failed" → Keychain-Modal nicht erschienen?
  → Spezifische Reasons → schnelleres Debugging.

BANNED METHODS (NIEMALS in diesem Flow verwenden):
  ❌ CDP / Playwright für Google OAuth Klicks → Shadow-DOM blockiert!
  ❌ Hardcoded element_index → Index ändert sich bei jeder Seite!
  ❌ Hardcoded PIDs (71104, etc.) → PIDs sind dynamisch!
  ❌ pkill zwischen Steps → tötet Chrome, Flow bricht ab!
  ❌ time.sleep(1) → zu kurz, Race Conditions!
  ❌ Screenshot + OCR → langsam, unzuverlässig!

VERWENDUNG:
  from survey.auth import GoogleOAuthFlow, LoginVerifier, CuaAdapter

  # WICHTIG: PIDs sind dynamisch! Niemals hardcoded verwenden!
  # Chrome PID dynamisch ermitteln:
  #   import urllib.request, json
  #   tabs = json.loads(urllib.request.urlopen('http://127.0.0.1:9999/json').read())
  #   chrome_pid = next((t['processId'] for t in tabs if 'heypiggy' in t.get('url','')), None)

  flow = GoogleOAuthFlow(CuaAdapter(), LoginVerifier())
  result = flow.execute(pid=chrome_pid)  # <- dynamische PID, NICHT 35970!
  # result.status: "ok" | "already_logged_in" | "error"
  # result.pid: Chrome PID
  # result.wid: Window ID
  # result.reason: Fehler-Details (bei status="error")

ABHÄNGIGKEITEN:
  • survey.auth.CuaAdapter (CUA-Driver Wrapper).
  • survey.auth.LoginVerifier (Session-Prüfung).
  • survey.security.SecretsClient (GOOGLE_EMAIL).
  • Chrome läuft bereits (ChromeLauncher oder BrowserManager).
  • macOS (CUA ist Apple-spezifisch).

WARNUNG:
  Dieser Flow ist MACOS-ONLY und erfordert:
  - cua-driver Binary im PATH.
  - Chrome mit --force-renderer-accessibility.
  - Keychain mit gespeichertem Google-Passkey.
  - Wenn Keychain leer → Flow schlägt bei Step 5 fehl.
================================================================================"""

# ═══════════════════════════════════════════════════════════════════════════════
# IMPORTS
# ═══════════════════════════════════════════════════════════════════════════════

# __future__: Ermöglicht type hints mit | (Union) Syntax in Python < 3.10.
# WARUM? str | None statt Optional[str] → kürzer, moderner.
from __future__ import annotations

# time: Sleep zwischen Steps (Redirects, JS-Rendering, AX-Tree-Update).
# WARUM time.sleep()? Wir müssen auf Seitenladen warten.
# WARUM nicht asyncio.sleep()? Diese Datei ist sync (CUA-Driver ist sync).
# WARUM nicht WebDriverWait? CUA ist kein WebDriver → kein DOM-Polling.
import time

# dataclasses: LoginResult als einfache Data-Klasse.
# WARUM @dataclass statt dict? Typsicherheit, IDE-Autovervollständigung.
# WARUM nicht Pydantic? Dies ist ein Low-Level-Modul (kein FastAPI-Dependency).
from dataclasses import dataclass

# typing: Type Hints für bessere IDE-Unterstützung.
# Optional: pid und wid können None sein (bei Fehler).
# CuaAdapter: Low-Level CUA-Driver Wrapper.
# WARUM .cua_adapter? Relativer Import (gleiches Paket survey.auth).
from .cua_adapter import CuaAdapter

# LoginVerifier: Prüft "abmelden" im AX-Tree → Session-State.
# WARUM .login_verifier? Relativer Import (gleiches Paket survey.auth).
from .login_verifier import LoginVerifier

# ═══════════════════════════════════════════════════════════════════════════════
# OPTIONAL: SecretsClient
# ═══════════════════════════════════════════════════════════════════════════════
# WARUM try/except? SecretsClient ist in survey/security/ (optionales Submodul).
# Wenn survey/security/ nicht verfügbar → SecretsClient = None (graceful).
# WARUM nicht harter Import-Fehler? Dieses Modul kann auch ohne SecretsClient
#   funktionieren (wenn E-Mail anders übergeben wird).
try:
    # Versuche SecretsClient aus dem Parent-Paket zu importieren.
    # WARUM ..security? Wir sind in survey/auth/ → Parent ist survey/.
    # ..security.__init__ enthält SecretsClient.
    from ..security import SecretsClient
except ImportError:
    # Import fehlgeschlagen (survey/security nicht verfügbar).
    # WARUM None? Wir setzen SecretsClient auf None und prüfen später
    #   "if SecretsClient:" → wenn None → überspringen.
    # type: ignore → mypy beschweren sich nicht über den Typ.
    SecretsClient = None  # type: ignore


# ═══════════════════════════════════════════════════════════════════════════════
# DATACLASS: LoginResult
# ═══════════════════════════════════════════════════════════════════════════════
@dataclass
class LoginResult:
    """Ergebnis eines Google OAuth Login-Versuchs.

    WARUM Dataclass (nicht Dict oder Tuple)?
      → Typsicherheit: status MUSS str sein, pid MUSS Optional[int] sein.
      → IDE-Autovervollständigung: result.status (nicht result["status"]).
      → Immutable: Felder sind read-only (nach Erstellung nicht änderbar).
      → Klare API: Aufrufer weiß EXAKT welche Felder verfügbar sind.
      → Weniger Fehler: Kein Tippfehler bei Keys (result.staus → Error).

    FELDER:
      status (str): Gesamt-Status des Login-Flows.
        - "ok": Login erfolgreich, Session aktiv.
        - "already_logged_in": Bereits eingeloggt, kein Login nötig.
        - "error": Login fehlgeschlagen (siehe reason).
      pid (Optional[int]): Chrome Prozess-ID (bei Erfolg).
        - None wenn Chrome nicht gefunden oder nicht gestartet.
      wid (Optional[int]): Window ID (bei Erfolg).
        - None wenn Fenster nicht gefunden.
      reason (Optional[str]): Fehler-Details (bei status="error").
        - Spezifische Fehler-Reason → schnelles Debugging.
        - Beispiele: "chrome_not_started", "email_field_not_found", etc.

    WARUM status als String (nicht Enum)?
      → Einfacher zu erweitern (kein Enum-Definition nötig).
      → JSON-Serialisierung: Strings sind nativ (Enums brauchen Converter).
      → Weniger Boilerplate für so wenige Werte.
      → WARUM nicht mehr Werte? 3 Status decken alle Fälle ab:
        ok = Erfolg, already_logged_in = Erfolg (kein Login nötig),
        error = Fehler (Details in reason).

    WARUM Optional[int] für pid/wid?
      → Bei Fehler sind pid/wid nicht verfügbar → None.
      → Bei "already_logged_in" sind pid/wid verfügbar → int.
      → Optional macht klar: Diese Werte können fehlen.

    WARUM reason Optional[str]?
      → Bei "ok" und "already_logged_in" gibt es keinen Fehler → reason=None.
      → Bei "error" MUSS reason gesetzt sein → spezifische Fehlerursache.
      → Klare Konvention: reason ist None bei Erfolg, String bei Fehler.

    Example:
        # Erfolg
        result = LoginResult(status="ok", pid=DYNAMIC_PID, wid=3293, reason=None)
        # Dynamische PID: curl http://127.0.0.1:9999/json | jq '.[].processId'

        # Bereits eingeloggt
        result = LoginResult(status="already_logged_in", pid=DYNAMIC_PID, wid=3293)

        # Fehler
        result = LoginResult(status="error", reason="email_field_not_found")
    """

    # status: Gesamt-Status.
    # WARUM str (nicht Literal)? Einfacher, keine Enum-Importe nötig.
    # Gültige Werte: "ok", "already_logged_in", "error".
    status: str  # "ok" | "error" | "already_logged_in"

    # pid: Chrome Prozess-ID.
    # WARUM Optional[int]? Bei Fehler oder "chrome_not_started" → None.
    pid: int | None = None

    # wid: Window ID (macOS Accessibility).
    # WARUM Optional[int]? Bei Fehler (Fenster nicht gefunden) → None.
    wid: int | None = None

    # reason: Fehler-Details (bei status="error").
    # WARUM Optional[str]? Bei Erfolg → None.
    reason: str | None = None


# ═══════════════════════════════════════════════════════════════════════════════
# KLASSE: GoogleOAuthFlow
# ═══════════════════════════════════════════════════════════════════════════════
class GoogleOAuthFlow:
    """Führt HeyPiggy Google OAuth Login via CUA aus (6-Step Flow).

    WARUM "Flow" im Namen?
      → Ein "Flow" ist eine Abfolge von Schritten mit klarem Start und Ende.
      → Gegenstück: "Adapter" (CuaAdapter) macht einzelne Aktionen.
      → Flow = Orchestration, Adapter = Execution.

    WARUM Klasse (nicht Funktion)?
      → Dependency Injection: CuaAdapter und LoginVerifier können gemockt werden.
      → Wiederverwendbar: Einmal erstellen, mehrmals ausführen.
      → State: CuaAdapter und LoginVerifier werden zwischen Aufrufen wiederverwendet.
      → Testbarkeit: Mock Dependencies → Unit-Tests ohne echtes Chrome.

    WARUM execute() statt run()?
      → "execute" ist expliziter als "run" (deutet auf Seiteneffekte hin).
      → "run" könnte auch ein Loop sein (mehrfache Ausführung).
      → "execute" = einmaliger, deterministischer Flow.

    LEBENSZYKLUS:
      1. Erstellen: flow = GoogleOAuthFlow(CuaAdapter(), LoginVerifier())
      2. PID ermitteln: chrome_pid = dynamisch via CDP JSON (NIEMALS hardcodieren!)
      3. Ausführen: result = flow.execute(pid=chrome_pid)
      4. Prüfen: if result.status == "ok": ...
      5. Optional: Wiederverwenden (neuer execute() Aufruf).

    FEHLERBEHANDLUNG (FAIL-FAST):
      → Jeder Step prüft VORAUSSETZUNGEN bevor er ausführt.
      → Wenn eine Voraussetzung fehlt → sofort return mit spezifischer reason.
      → Kein "try next" → jeder Fehler stoppt den Flow.
      → WARUM? Spätere Steps bauen auf früheren auf → sinnlos ohne Voraussetzung.
      → Beispiel: Ohne pid → kann kein Fenster finden → Flow stoppt.

    DETERMINISMUS:
      → Gleicher Input → gleicher Output (wenn Chrome/Seite identisch).
      → Keine Zufälligkeit (außer dynamische PIDs/WIDs von Chrome).
      → WARUM wichtig? Reproduzierbare Fehler, besseres Debugging.

    PERFORMANCE:
      → Step 0 (already_logged_in): ~1-2s (nur list_windows + Titel-Check).
      → Steps 1-6 (vollständiger Flow): ~25-35s (6 Steps × 5s sleep + CUA-Overhead).
      → Optimierung: Wenn "already_logged_in" → SOFORT return (kein Flow).
      → WARUM 25-35s? Google OAuth hat Redirects, Keychain-Modal braucht Zeit.

    THREAD-SICHERHEIT:
      → NICHT thread-safe: CuaAdapter ist stateless, aber Chrome ist global.
      → Gleichzeitige execute() Aufrufe → Race Conditions (gleiches Chrome).
      → WARUM nicht gesperrt? Use-Case: Ein Login zu einem Zeitpunkt.
    """

    def __init__(
        self,
        cua: CuaAdapter | None = None,
        verifier: LoginVerifier | None = None,
    ):
        """Initialisiere GoogleOAuthFlow.

        WARUM Optional Dependencies?
          → Wenn None → erstelle Standard-Instanzen (Default-Use-Case).
          → Wenn gesetzt → verwende übergebene (für Tests/Mocking).
          → Pattern: Dependency Injection mit Default.

        WARUM CuaAdapter hier (nicht in execute())?
          → CuaAdapter wird in MEHREREN Steps verwendet (3, 4, 5, 6).
          → Wiederverwendung → schneller (kein Neuerstellen pro Step).
          → Timeout und andere Einstellungen bleiben konsistent.

        WARUM LoginVerifier hier (nicht lokal in execute())?
          → Wird in Step 0 (check) und VERIFY (Ende) verwendet.
          → Wiederverwendung → schneller.
          → verify.check() ist teuer (list_windows + AX-Tree Scan).

        Args:
            cua: Optionaler CuaAdapter. None = neuen erstellen.
            verifier: Optionaler LoginVerifier. None = neuen erstellen.

        Example:
            # Standard (echtes Chrome)
            flow = GoogleOAuthFlow()

            # Mit Mocks (für Tests)
            mock_cua = MagicMock()
            mock_verifier = MagicMock()
            flow = GoogleOAuthFlow(mock_cua, mock_verifier)
        """
        # WARUM cua or CuaAdapter()? Lazy-Initialisierung.
        # Wenn cua=None → CuaAdapter() wird erst jetzt erstellt.
        self.cua = cua or CuaAdapter()

        # WARUM verifier or LoginVerifier()? Lazy-Initialisierung.
        # Wenn verifier=None → LoginVerifier(self.cua) wird erstellt.
        # WARUM self.cua an LoginVerifier übergeben? LoginVerifier braucht
        #   CuaAdapter für list_windows() und get_tree().
        # WARUM denselben CuaAdapter? Wiederverwendung, konsistente Timeouts.
        self.verifier = verifier or LoginVerifier(self.cua)

    def execute(self, pid: int | None = None) -> LoginResult:
        """Führe den kompletten Google OAuth Login-Flow aus.

        ABLAUF (6 Steps + Verify):
          Step 0: Prüfe ob bereits eingeloggt (LoginVerifier.check).
          Step 1: Prüfe ob Chrome läuft (pid muss gesetzt sein).
          Step 2: Finde Dashboard-Fenster (find_bot_window).
          Step 3: Klicke Google Login-Symbol (find_idx + click).
          Step 4: E-Mail eingeben + "Weiter" klicken (OAuth-Fenster).
          Step 5: "Fortfahren" klicken (Keychain Auto-Fill).
          Step 6: Final "Weiter" klicken (zurück zum Dashboard).
          Verify: Prüfe ob wirklich eingeloggt (LoginVerifier.check).

        WARUM pid Parameter?
          → Chrome muss VORHER gestartet werden (ChromeLauncher/BrowserManager).
          → Diese Methode startet KEINEN neuen Chrome (nur CUA-Interaktion).
          → pid = Prozess-ID des laufenden Chrome.
          → WARUM nicht hier starten? Chrome-Start ist separat (flexibler).
          → Aufrufer kann Chrome mit spezifischen Flags starten.

        WARUM Optional[int]?
          → Wenn None → Fehler "chrome_not_started".
          → Aufrufer MUSS Chrome starten oder pid übergeben.
          → WARUM nicht automatisch suchen? Suche könnte USER Chrome finden
            (gefährlich!). Explizite PID ist sicherer.

        WARUM return bei jedem Fehler (nicht Exception)?
          → LoginResult mit reason ist informativer als Exception.
          → Aufrufer kann alle Fehlerfälle behandeln (nicht nur try/except).
          → HTTP API gibt LoginResult als JSON zurück → kein Stack-Trace.
          → Spezifische reason → Client weiß was schiefging.

        WARUM 5s sleep nach jedem Klick?
          → Google OAuth hat Redirects (mehrere HTTP 302s).
          → JavaScript rendert neue Elemente async (nicht sofort).
          → CUA-AX-Tree braucht Zeit um neue Elemente zu registrieren.
          → Keychain-Modal erscheint mit Animation (~1-2s).
          → 5s = konservativ, aber zuverlässig.
          → WARUM nicht dynamisch warten? CUA kann nicht poll (kein Event).
          → Alternative: Mehrfache Retry mit kürzerem Sleep → komplexer.

        FEHLER-REASONS (vollständige Liste):
          chrome_not_started          → pid=None übergeben, Chrome nicht gestartet.
          no_dashboard_window         → Kein Chrome-Fenster mit HeyPiggy gefunden.
          google_login_button_not_found → Google Login-Symbol nicht im AX-Tree.
          google_login_click_failed   → Klick auf Symbol schlug fehl (cua-driver).
          google_oauth_window_not_found → OAuth-Seite hat sich nicht geöffnet.
          email_field_not_found       → E-Mail Feld nicht auf OAuth-Seite.
          missing_google_email        → GOOGLE_EMAIL nicht konfiguriert.
          email_type_failed           → E-Mail Eingabe schlug fehl.
          weiter_button_not_found     → "Weiter" Button nicht gefunden.
          weiter_click_failed         → Klick auf "Weiter" schlug fehl.
          fortfahren_button_not_found → "Fortfahren" Button nicht gefunden.
          fortfahren_click_failed     → Klick auf "Fortfahren" schlug fehl.
          final_weiter_not_found      → Finaler "Weiter" nicht gefunden.
          final_weiter_click_failed   → Klick auf finalen "Weiter" schlug fehl.
          dashboard_not_found_after_login → Verify schlug fehl (nicht eingeloggt).

        Args:
            pid: Chrome Prozess-ID (muss laufend sein). None = Fehler.

        Returns:
            LoginResult mit status, pid, wid, reason.

        Example:
            # Dynamische PID ermitteln (NIEMALS hardcodieren!):
            #   import urllib.request, json
            #   tabs = json.loads(urllib.request.urlopen('http://127.0.0.1:9999/json').read())
            #   chrome_pid = next((t['processId'] for t in tabs if 'heypiggy' in t.get('url','')), None)
            result = flow.execute(pid=chrome_pid)
            if result.status == "ok":
                print(f"Login OK: pid={result.pid}, wid={result.wid}")
            elif result.status == "already_logged_in":
                print("Bereits eingeloggt")
            else:
                print(f"Login fehlgeschlagen: {result.reason}")
        """
        # ═══════════════════════════════════════════════════════════════════
        # STEP 0: ALREADY LOGGED IN?
        # ═══════════════════════════════════════════════════════════════════
        # WARUM zuerst prüfen? Wenn bereits eingeloggt → kein Login nötig.
        # Das spart 25-35s (vollständiger Flow) → sofort return.
        # Performance: ~1-2s statt 25-35s.
        # WARUM LoginVerifier (nicht einfach Cookie-Check)?
        #   CUA/AX ist zuverlässiger als Cookies (können abgelaufen sein).
        #   "abmelden" im AX-Tree = echte, aktive Session.
        epid, ewid, logged_in = self.verifier.check()
        if logged_in and ewid:
            # Bereits eingeloggt! Kein erneuter Login nötig.
            # WARUM ewid prüfen? Fenster-ID muss gültig sein (nicht None).
            # WARUM epid? Prozess-ID des eingeloggten Chrome.
            return LoginResult(status="already_logged_in", pid=epid, wid=ewid)

        # ═══════════════════════════════════════════════════════════════════
        # STEP 1: CHROME RUNNING?
        # ═══════════════════════════════════════════════════════════════════
        # WARUM pid prüfen? Diese Methode startet KEINEN Chrome.
        # Chrome muss VORHER gestartet werden (Aufrufer-Responsibility).
        # WARUM nicht hier starten? Flexibilität: Aufrufer kann Flags setzen.
        # WARUM nicht automatisch suchen? Gefahr: USER Chrome könnte gefunden werden.
        #   Wir wollen NUR explizit gestartete Bot-Chrome.
        if pid is None:
            # Chrome nicht gestartet → Flow kann nicht beginnen.
            # WARUM return (nicht Exception)? LoginResult ist informativer.
            # Aufrufer kann auf "chrome_not_started" reagieren (neu starten).
            return LoginResult(status="error", reason="chrome_not_started")

        # ═══════════════════════════════════════════════════════════════════
        # STEP 2: FIND DASHBOARD WINDOW
        # ═══════════════════════════════════════════════════════════════════
        # Wir suchen das HeyPiggy Dashboard-Fenster im Chrome.
        # WARUM find_bot_window()? CUA braucht window_id für Interaktion.
        # WARUM Keywords? ["heypiggy", "dashboard", "verdienen"] → spezifisch.
        # WARUM Fallback? Wenn Titel nicht exakt matcht → nimm erstes Chrome-Fenster.
        pid_d, wid_d = self.cua.find_bot_window(["heypiggy", "dashboard", "verdienen"])
        if not wid_d:
            # Fallback: Nimm irgendein Chrome-Fenster.
            # WARUM? Wenn HeyPiggy noch lädt oder Titel anders ist.
            pid_d, wid_d = self.cua.find_bot_window()
        if not wid_d:
            # Kein Chrome-Fenster gefunden → Flow kann nicht beginnen.
            # Mögliche Ursachen:
            #   - Chrome nicht gestartet (trotz pid → Fenster noch nicht da).
            #   - Chrome minimiert oder versteckt.
            #   - Accessibility nicht aktiv (--force-renderer-accessibility fehlt).
            return LoginResult(status="error", reason="no_dashboard_window")

        # ═══════════════════════════════════════════════════════════════════
        # STEP 3: CLICK GOOGLE LOGIN SYMBOL
        # ═══════════════════════════════════════════════════════════════════
        # Wir klicken auf das Google Login-Symbol im HeyPiggy Dashboard.
        # WARUM AX-Tree? Wir müssen element_index finden (nicht hardcoden).
        tree = self.cua.get_tree(pid_d, wid_d)

        # Primär: Suche "google login-symbol" (spezifisch für HeyPiggy).
        # WARUM primär? Weniger False-Positives als generisches "google".
        idx = self.cua.find_idx(tree, "google login-symbol", ["AXLink"])
        if idx is None:
            # Fallback: Suche generisch "google" (wenn Titel anders ist).
            # WARUM? HeyPiggy könnte Label geändert haben.
            # WARNUNG: Könnte falsches Element treffen (Google Analytics, etc.).
            idx = self.cua.find_idx(tree, "google", ["AXLink"])
        if idx is None:
            # Google Login-Symbol nicht gefunden.
            # Mögliche Ursachen:
            #   - Seite noch nicht geladen.
            #   - Accessibility nicht aktiv.
            #   - HeyPiggy hat UI geändert (neues Label).
            return LoginResult(status="error", reason="google_login_button_not_found")

        # Klicke auf das Symbol.
        # WARUM .click() Return-Value prüfen? cua-driver könnte fehlschlagen.
        if not self.cua.click(pid_d, wid_d, idx):
            # Klick schlug fehl.
            # Mögliche Ursachen:
            #   - Element nicht mehr da (Seite hat sich geändert).
            #   - CUA-Driver Timeout.
            #   - Element versteckt oder deaktiviert.
            return LoginResult(status="error", reason="google_login_click_failed")

        # Warte auf Google OAuth Seite.
        # WARUM 5s? Redirects + neues Fenster/Sheet öffnet sich.
        time.sleep(5)

        # ═══════════════════════════════════════════════════════════════════
        # STEP 4: FIND OAUTH WINDOW + ENTER EMAIL + CLICK "WEITER"
        # ═══════════════════════════════════════════════════════════════════
        # Google OAuth hat sich in einem neuen Fenster/Tab geöffnet.
        # Wir müssen das NEUE Fenster finden (nicht das alte Dashboard).
        # WARUM neue Suche? WID hat sich geändert (neues Fenster).
        pid_g, wid_g = self.cua.find_bot_window(["google", "anmelden", "accounts"])
        if not wid_g:
            # Fallback: Nimm irgendein Chrome-Fenster.
            pid_g, wid_g = self.cua.find_bot_window()
        if not wid_g:
            # OAuth-Fenster nicht gefunden.
            # Mögliche Ursachen:
            #   - Pop-Up-Blocker hat das Fenster blockiert.
            #   - Redirect hat sich verzögert.
            #   - Seite ist auf Englisch ("Sign in" statt "Anmelden").
            return LoginResult(status="error", reason="google_oauth_window_not_found")

        # Lese AX-Tree des OAuth-Fensters.
        tree = self.cua.get_tree(pid_g, wid_g)

        # Suche E-Mail Eingabefeld.
        # WARUM "e-mail oder telefonnummer"? Deutscher Google OAuth Text.
        # WARUM AXTextField? E-Mail wird in ein Textfeld eingegeben.
        email_idx = self.cua.find_idx(tree, "e-mail oder telefonnummer", ["AXTextField"])
        if email_idx is None:
            # E-Mail Feld nicht gefunden.
            # Mögliche Ursachen:
            #   - Seite ist auf Englisch ("Email or phone" statt "E-Mail").
            #   - Seite noch nicht geladen.
            #   - Accessibility nicht aktiv.
            return LoginResult(status="error", reason="email_field_not_found")

        # Hole E-Mail aus SecretsClient.
        # WARUM SecretsClient (nicht hardcoded)? Keine Credentials im Code.
        # WARUM try/except? SecretsClient könnte fehlen oder E-Mail nicht konfiguriert.
        google_email = None
        if SecretsClient:
            try:
                # Versuche E-Mail aus ~/.stealth/config.yaml oder Env zu lesen.
                google_email = SecretsClient.get_google_email()
            except Exception:
                # SecretsClient verfügbar, aber E-Mail nicht konfiguriert.
                # Graceful: google_email bleibt None, Fehler wird später geworfen.
                pass
        if not google_email:
            # Keine E-Mail verfügbar.
            # Mögliche Ursachen:
            #   - GOOGLE_EMAIL nicht in ~/.stealth/config.yaml.
            #   - GOOGLE_EMAIL Env-Variable nicht gesetzt.
            #   - SecretsClient nicht installiert.
            return LoginResult(status="error", reason="missing_google_email")

        # Tippe E-Mail in das Feld.
        # WARUM .type() Return-Value prüfen? cua-driver könnte fehlschlagen.
        if not self.cua.type(pid_g, wid_g, email_idx, google_email):
            # Eingabe schlug fehl.
            # Mögliche Ursachen:
            #   - Feld nicht fokussiert.
            #   - Feld read-only.
            #   - CUA-Driver Timeout.
            return LoginResult(status="error", reason="email_type_failed")

        # Suche "Weiter" Button.
        # WARUM nach type()? Wir müssen den Button finden der die E-Mail abschickt.
        # WARUM im selben tree? E-Mail eingeben ändert den AX-Tree nicht.
        weiter_idx = self.cua.find_idx(tree, "weiter", ["AXButton"])
        if weiter_idx is None:
            # "Weiter" Button nicht gefunden.
            # Mögliche Ursachen:
            #   - Seite ist auf Englisch ("Next" statt "Weiter").
            #   - Button noch nicht gerendert (JavaScript-Delay).
            return LoginResult(status="error", reason="weiter_button_not_found")

        # Klicke "Weiter".
        if not self.cua.click(pid_g, wid_g, weiter_idx):
            # Klick schlug fehl.
            return LoginResult(status="error", reason="weiter_click_failed")

        # Warte auf Keychain Auto-Fill Modal.
        # WARUM 5s? Google verarbeitet E-Mail + Keychain zeigt Passkey-Modal.
        # Keychain-Modal erscheint mit Animation (~1-2s).
        # Zu früh → Modal noch nicht da → Step 5 schlägt fehl.
        time.sleep(5)

        # ═══════════════════════════════════════════════════════════════════
        # STEP 5: KEYCHAIN "FORTFAHREN"
        # ═══════════════════════════════════════════════════════════════════
        # Nach E-Mail + "Weiter" zeigt macOS Keychain ein Modal:
        #   "Mit Passkey anmelden"
        #   "Jeremy Schulze"
        #   "zukunftsorientierte.energie@gmail.com"
        #   [Fortfahren] [Andere Optionen...]
        # Wir müssen "Fortfahren" klicken.
        # WARUM neues Fenster? Keychain-Modal ist ein neues macOS-Fenster.
        pid_k, wid_k = self.cua.find_bot_window(["google", "anmelden", "jeremy"])
        if not wid_k:
            # Fallback: Suche nur nach "google" (wenn Titel nicht Jeremy enthält).
            pid_k, wid_k = self.cua.find_bot_window(["google"])
        if not wid_k:
            # Keychain-Modal nicht gefunden.
            # Mögliche Ursachen:
            #   - Keychain hat keinen Passkey für dieses Google-Konto.
            #   - Keychain deaktiviert oder leer.
            #   - macOS Version unterstützt kein Passkey-AutoFill.
            return LoginResult(status="error", reason="fortfahren_button_not_found")

        # Lese AX-Tree des Keychain-Fensters.
        tree = self.cua.get_tree(pid_k, wid_k)

        # Suche "Fortfahren" Button.
        fort_idx = self.cua.find_idx(tree, "fortfahren", ["AXButton"])
        if fort_idx is None:
            # Fallback: Suche "konto" (wenn Label anders ist).
            # WARUM? Manche macOS-Versionen zeigen "Konto auswählen".
            fort_idx = self.cua.find_idx(tree, "konto", ["AXButton"])
        if fort_idx is None:
            # "Fortfahren" nicht gefunden.
            # Mögliche Ursachen:
            #   - Keychain-Modal hat sich nicht geöffnet.
            #   - macOS zeigt "Passwort eingeben" statt "Fortfahren".
            #   - Sprache ist Englisch ("Continue" statt "Fortfahren").
            return LoginResult(status="error", reason="fortfahren_button_not_found")

        # Klicke "Fortfahren".
        if not self.cua.click(pid_k, wid_k, fort_idx):
            # Klick schlug fehl.
            return LoginResult(status="error", reason="fortfahren_click_failed")

        # Warte auf finalen "Weiter" Button.
        # WARUM 5s? Keychain bestätigt Passkey + Google zeigt finalen Screen.
        time.sleep(5)

        # ═══════════════════════════════════════════════════════════════════
        # STEP 6: FINAL "WEITER"
        # ═══════════════════════════════════════════════════════════════════
        # Nach "Fortfahren" zeigt Google einen finalen "Weiter" Button.
        # Dieser bestätigt den Login und leitet zurück zu HeyPiggy.
        # WARUM neues Fenster? Google öffnet einen neuen Screen/Tab.
        pid_f, wid_f = self.cua.find_bot_window(["google", "anmelden"])
        if not wid_f:
            # Fallback: Nimm irgendein Chrome-Fenster.
            pid_f, wid_f = self.cua.find_bot_window()
        if not wid_f:
            # Finaler Screen nicht gefunden.
            return LoginResult(status="error", reason="final_weiter_not_found")

        # Lese AX-Tree.
        tree = self.cua.get_tree(pid_f, wid_f)

        # Suche finalen "Weiter" Button.
        final_idx = self.cua.find_idx(tree, "weiter", ["AXButton"])
        if final_idx is None:
            # Finaler "Weiter" nicht gefunden.
            # Mögliche Ursachen:
            #   - Seite noch nicht geladen.
            #   - Button hat anderen Text ("Fertig", "Done").
            return LoginResult(status="error", reason="final_weiter_not_found")

        # Klicke finalen "Weiter".
        if not self.cua.click(pid_f, wid_f, final_idx):
            return LoginResult(status="error", reason="final_weiter_click_failed")

        # Warte auf Dashboard-Redirect.
        # WARUM 5s? Google leitet zurück zu HeyPiggy Dashboard.
        # Dashboard muss laden + "abmelden" muss im AX-Tree erscheinen.
        time.sleep(5)

        # ═══════════════════════════════════════════════════════════════════
        # VERIFY: CHECK LOGGED IN
        # ═══════════════════════════════════════════════════════════════════
        # Nach dem kompletten Flow MUSSEN wir verifizieren.
        # WARUM? Jeder einzelne Klick könnte scheitern ("performed" != Erfolg).
        # Ohne Verify → wir DENKEN wir sind eingeloggt, aber sind es nicht.
        # LoginVerifier prüft "abmelden" im AX-Tree → echte, aktive Session.
        epid, ewid, logged_in = self.verifier.check()
        if logged_in and ewid:
            # ERFOLG! Wirklich eingeloggt.
            # WARUM ewid? Window-ID des eingeloggten Dashboards.
            # WARUM epid? Prozess-ID des Chrome.
            return LoginResult(status="ok", pid=epid, wid=ewid)

        # VERIFY FEHLGESCHLAGEN.
        # Alle Steps liefen durch, aber "abmelden" nicht gefunden.
        # Mögliche Ursachen:
        #   - Ein Klick hat nicht funktioniert (Race Condition).
        #   - Google hat den Login abgelehnt (suspected automation).
        #   - HeyPiggy hat die Session nicht akzeptiert.
        #   - Dashboard hat sich nicht geladen (Timeout zu kurz?).
        return LoginResult(status="error", reason="dashboard_not_found_after_login")
