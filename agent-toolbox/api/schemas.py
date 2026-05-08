"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║           Pydantic Schemas für Agent-Toolbox API (stealth-runner)            ║
║                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ZWECK / PURPOSE:                                                            ║
║  ────────────────                                                            ║
║  Diese Datei definiert ALLE Datenstrukturen (Request/Response Models)        ║
║  für die FastAPI-Endpoints.                                                  ║
║                                                                              ║
║  WARUM PYDANTIC? (Warum nicht nur Dicts?)                                    ║
║  ─────────────────────────────────────────                                   ║
║  1. AUTO-VALIDATION: Wenn ein Client ein Feld vergisst oder falsch          ║
║     typisiert (z.B. String statt Integer), Pydantic wirft SOFORT einen         ║
║     sauberen 422-Fehler mit Detail-Meldung. Ohne Pydantic → Runtime-Fehler ║
║     irgendwo tief im Code, schwer zu debuggen.                              ║
║  2. SELF-DOCUMENTATION: FastAPI generiert /docs (Swagger UI) AUTOMATISCH     ║
║     aus diesen Modellen. Jeder Agent kann die API verstehen ohne README.    ║
║  3. TYPE SAFETY: IDEs (VSCode, PyCharm) zeigen Autocomplete für alle Felder. ║
║  4. SERIALIZATION: .model_dump() → JSON, .model_validate() → Objekt.       ║
║     Kein manuelles json.loads/json.dumps mehr nötig.                        ║
║                                                                              ║
║  WARUM Field(...) STATT Optional?                                              ║
║  ────────────────────────────────                                            ║
║  Field(description=...) wird von FastAPI /docs angezeigt.                    ║
║  Optional erlaubt None, was bei manchen Feldern gewollt ist (z.B. survey_id) ║
║  aber bei anderen (z.B. cdp_port) einen Default-Wert braucht.               ║
║                                                                              ║
║  ARCHITEKTUR-ENTSCHEIDUNGEN:                                                 ║
║  ────────────────────────────                                                ║
  ║  • cdp_port = 9999 DEFAULT: Chrome DevTools Protocol Port.                 ║
  ║    NICHT 9222 (Chrome Default) weil 9222 oft von User-Chrome belegt ist.    ║
  ║    Stealth-Runner Standard seit 2026-05-08: 9999 (nicht 9999 alt).           ║
║  • profile_name = "default" DEFAULT: Playwright-Profil-Name.                 ║
║    Kann auf "heypiggy" oder andere Profile erweitert werden.                  ║
║  • Literal[...] statt str: Enforced Enum-Werte bei API-Responses.           ║
║    Client kann nur "success" oder "error" senden, nicht "sucess" (Typo).    ║
║                                                                              ║
║  SICHERHEIT / BANNED PATTERNS:                                               ║
║  ──────────────────────────────                                              ║
║  • KEINE Hardcoded PIDs in Modellen (PID kommt vom BrowserManager)          ║
║  • KEINE Passwörter in Request-Modellen (nur Tokens/Cookies)                   ║
║  • KEINE Session-IDs in Logs (nur Cookie-Datei)                              ║
║                                                                              ║
║  DATEI-STRUKTUR:                                                               ║
║  ────────────────                                                              ║
║  1. Browser Schemas      → Start/Stop/Health                                  ║
║  2. Login Schemas        → HeyPiggy OAuth Flow                               ║
║  3. Survey Action Schemas → Click, Select, Fill, Run                         ║
║  4. Dashboard Schemas    → Scan, Balance                                     ║
║  5. Cookie Schemas       → Extract, Inject, Verify                           ║
║  6. Utility Schemas      → Navigate, Screenshot, Page Content                ║
║  7. Error Schema         → Generic Error Response                            ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

# ═══════════════════════════════════════════════════════════════════════════════
# IMPORTS: Was brauchen wir und WARUM?
# ═══════════════════════════════════════════════════════════════════════════════

# "from __future__ import annotations" ermöglicht Forward-References in Type Hints.
# WARUM? Ohne das müssten wir Klassen in spezifischer Reihenfolge definieren
# (BaseModel vor abgeleiteten Klassen). Mit annotations → Reihenfolge egal.
from __future__ import annotations

# Optional: Ein Feld kann entweder einen Wert haben ODER None.
# WARUM? survey_id: Optional[str] = None bedeutet "optional survey ID".
# Literal: Erlaubt NUR spezifische String-Werte (wie Enum aber besser für FastAPI).
# WARUM Literal["success", "error"] statt str?
#   → FastAPI zeigt nur "success" und "error" in Swagger UI an.
#   → Client kann keinen invaliden Status senden.
from typing import Optional, Literal, Dict, Any, List

# BaseModel: Basis für ALLE Pydantic-Modelle. Bietet .model_dump(), .model_validate().
# Field: Ermöglicht Metadaten wie description, default, ge (greater/equal), le (less/equal).
# WARUM Field() statt direkt = default?
#   → Field(description=...) erscheint in Swagger UI als Dokumentation.
#   → Field(ge=1, le=50) validiert: Wert muss zwischen 1 und 50 liegen.
from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════════════════════
# SEKTION 1: BROWSER SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════
# Diese Schemas steuern den Browser-Lifecycle: Starten, Stoppen, Health-Check.
# Der Browser ist die FOUNDATION für ALLE Automation — ohne Browser geht nichts.
# ═══════════════════════════════════════════════════════════════════════════════


class BrowserStartRequest(BaseModel):
    """
    Request-Body für POST /browser/start.
    
    Startet Chrome mit Playwright via CDP (Chrome DevTools Protocol).
    Chrome wird als Subprocess gestartet, Playwright verbindet über
    WebSocket mit dem CDP-Port.
    
    WICHTIGE FELDER:
    • profile_name: Name des Chrome-Profils (default "default").
      Aktuell nur "default" unterstützt. In Zukunft könnte "heypiggy"
      oder "gmail" hinzukommen für unterschiedliche Cookie-Sets.
    • headless: None = aus .env lesen, True/False = explizit setzen.
      headless=True = unsichtbar (schneller), headless=False = sichtbar (debug).
    • cdp_port: None = Default 9999 (siehe unten).
    
    WARUM headless Optional[Bool] statt bool?
    → None erlaubt es, aus der Umgebungsvariable BROWSER_HEADLESS zu lesen.
    → Das ist flexibler: .env-File steuert Default, Request kann überschreiben.
    """
    # profile_name: Name des Browser-Profils.
    # WARUM default="default"? Playwright erwartet einen Profil-Namen.
    # "default" ist der Standard-Name wenn nichts konfiguriert ist.
    profile_name: str = Field(
        default="default",
        description="Browser profile to use (default: 'default')"
    )
    
    # headless: Sichtbarer oder unsichtbarer Browser.
    # WARUM Optional[bool]? Weil None bedeutet "aus .env lesen".
    # Das ist ein Pattern für Umgebungs-Konfiguration mit Request-Override.
    headless: Optional[bool] = Field(
        default=None,
        description="Override headless mode. None=read from BROWSER_HEADLESS env var"
    )
    
    # cdp_port: Chrome DevTools Protocol Port.
    # WARUM default=None statt 9999?
    # → None bedeutet "Default des BrowserManagers verwenden".
    # → Der BrowserManager hat 9999 als Default (siehe browser_manager.py).
    # → So haben wir EINEN zentralen Default, nicht verteilt über mehrere Dateien.
    cdp_port: Optional[int] = Field(
        default=None,
        description="CDP debugging port. None = use BrowserManager default (9999)"
    )


class BrowserStartResponse(BaseModel):
    """
    Response für POST /browser/start.
    
    Bestätigt dass Chrome gestartet wurde und gibt Details zurück.
    
    WICHTIGE FELDER:
    • status: "success" oder "error". Literal enforced.
    • message: Human-readable Status. "Browser started (warm)" bedeutet
      Chrome war bereits aktiv und wurde wiederverwendet (schnell).
      "Browser started (cold)" bedeutet Chrome musste neu gestartet werden.
    
    WARUM message statt nur status?
    → Agents (und Menschen) können aus der Message den Zustand verstehen
      ohne zusätzliche Logik. "warm" vs "cold" ist wichtig für Performance-Analyse.
    """
    # status: Ergebnis des Start-Versuchs.
    # WARUM Literal? FastAPI validiert: nur "success" oder "error" erlaubt.
    # Das verhindert Typos wie "sucess" oder "succes".
    status: Literal["success", "error"] = Field(
        default="success",
        description="Operation result: 'success' or 'error'"
    )
    
    # profile: Welches Profil wurde verwendet.
    # WARUM dieses Feld? Bestätigung an den Client welches Profil aktiv ist.
    # Nützlich wenn der Client "default" sendet aber ein anderes Profil zurückkommt.
    profile: str = Field(
        description="Active browser profile name"
    )
    
    # headless: Tatsächlicher headless-Modus.
    # WARUM? Der Client sendet Optional[bool], aber die Response sagt
    # was TATSÄCHLICH verwendet wurde (z.B. aus .env gelesen).
    headless: bool = Field(
        description="Actual headless mode used"
    )
    
    # cdp_port: Tatsächlicher CDP-Port.
    # WARUM Optional? Wenn Status "error" ist, könnte der Port None sein
    # weil Chrome gar nicht gestartet wurde.
    cdp_port: Optional[int] = Field(
        description="CDP port Chrome is listening on"
    )
    
    # message: Human-readable Status mit Warm/Cold-Info.
    # WARUM "(warm)" vs "(cold)"?
    # → Warm = BrowserManager hat bestehende Instanz wiederverwendet (~0ms).
    # → Cold = Chrome musste neu gestartet werden (~2-5s).
    # Das hilft beim Performance-Monitoring und Debugging.
    message: str = Field(
        description="Human-readable status, e.g. 'Browser started (warm)'"
    )


class BrowserStopResponse(BaseModel):
    """
    Response für POST /browser/stop.
    
    Bestätigt dass Chrome beendet und aufgeräumt wurde.
    
    WARUM so einfach?
    → Stop ist idempotent: Wenn Chrome nicht läuft → success.
    → Keine zusätzlichen Daten nötig, nur Bestätigung.
    """
    # status: Ergebnis des Stop-Versuchs.
    # Immer "success" oder "error". "success" auch wenn Chrome nicht lief
    # (idempotent Operation).
    status: Literal["success", "error"] = Field(
        default="success",
        description="'success' (even if browser was not running — idempotent)"
    )
    
    # message: Kurze Bestätigung.
    message: str = Field(
        description="e.g. 'Browser stopped', 'Browser was not running'"
    )


class BrowserHealthResponse(BaseModel):
    """
    Response für GET /browser/health.
    
    Gibt den aktuellen Zustand des Browsers zurück.
    Nützlich für Monitoring und vor Operations-Entscheidungen.
    
    WICHTIGE FELDER:
    • running: True = Chrome ist aktiv. False = muss gestartet werden.
    • idle_seconds: Wie lange der Browser ungenutzt war.
      > 300s (5min) → könnte Memory-Leak haben, Neustart empfohlen.
    • last_used: Unix-Timestamp der letzten Nutzung.
      Nützlich für Auto-Cleanup-Logik.
    
    WARUM last_used als float?
    → time.time() gibt float (Sekunden mit Mikrosekunden).
    → So können wir exakte Zeitdifferenzen berechnen.
    """
    # running: Ist Chrome aktiv?
    # WARUM Bool? Einfache Ja/Nein-Entscheidung für den Client.
    # Wenn False → Client sollte POST /browser/start aufrufen.
    running: bool = Field(
        description="True if Chrome process is alive and CDP reachable"
    )
    
    # profile: Aktives Profil (oder None wenn nicht läuft).
    # WARUM Optional? Wenn Browser nicht läuft → kein Profil aktiv.
    profile: Optional[str] = Field(
        description="Active profile name, or None if not running"
    )
    
    # last_used: Unix-Timestamp der letzten Nutzung.
    # WARUM float? time.time() gibt float. Unix-Epoch in Sekunden.
    # Berechnung: idle_seconds = time.time() - last_used.
    last_used: Optional[float] = Field(
        description="Unix timestamp of last API call using the browser"
    )
    
    # idle_seconds: Sekunden seit letzter Nutzung.
    # WARUM dieses berechnete Feld? Convenience für den Client.
    # Client muss nicht selbst rechnen: idle = current_time - last_used.
    idle_seconds: Optional[float] = Field(
        description="Seconds since last use. >300s → consider restart"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# SEKTION 2: LOGIN SCHEMAS (HeyPiggy OAuth)
# ═══════════════════════════════════════════════════════════════════════════════
# Diese Schemas steuern den Login-Flow über Google OAuth.
# Der Login ist der SCHWIERIGSTE Teil weil Google Shadow-DOM und
# Anti-Bot-Maßnahmen verwendet.
# ═══════════════════════════════════════════════════════════════════════════════


class LoginRequest(BaseModel):
    """
    Request-Body für POST /services/heypiggy/login.
    
    Triggert den Google OAuth Login-Flow für HeyPiggy.
    
    ARCHITEKTUR:
    1. Wenn pid=None → Suche bestehenden Bot-Chrome via lsof Port-Scan.
    2. Wenn keiner gefunden → Starte neuen Chrome via ChromeLauncher.
    3. Führe GoogleOAuthFlow aus (CUA-basiert wegen Shadow-DOM).
    
    WICHTIGE FELDER:
    • pid: Bestehende Chrome PID. Wenn gesetzt, wird KEIN neuer Chrome gestartet.
      Das ist wichtig für Cookie-basierte Re-Login (Session persistieren).
    • cdp_port: Port für CDP-Kommunikation. MUSS mit Chrome übereinstimmen.
      Wenn Chrome auf 9999 läuft aber Request sendet 9223 → Verbindung fehlschlägt.
    
    WARUM timeout_ms default=30000?
    → Google OAuth kann langsam sein (Redirects, 2FA-Fenster, etc.).
    → 30s ist ein guter Kompromiss zwischen Robustheit und Wartezeit.
    """
    # profile_name: Profil für den Login.
    # WARUM? In Zukunft könnten unterschiedliche Profile unterschiedliche
    # Google-Accounts haben (z.B. zukunftsorientierte.energie@gmail.com).
    profile_name: str = Field(
        default="default",
        description="Browser profile for this login session"
    )
    
    # headless: Sichtbarer Login?
    # WARUM Optional? Gleiches Pattern wie BrowserStartRequest.
    # Google OAuth erfordert manchmal sichtbaren Browser (Anti-Bot).
    headless: Optional[bool] = Field(
        default=None,
        description="Headless override. None=use env default"
    )
    
    # timeout_ms: Maximale Wartezeit für Login.
    # WARUM 30000? Google OAuth kann 10-20s brauchen (Redirects, Keychain, etc.).
    # 30s deckt 95% der Fälle ab. Bei langsamer Verbindung → erhöhen.
    timeout_ms: int = Field(
        default=30000,
        description="Max wait time in milliseconds for login completion"
    )
    
    # pid: Bestehende Chrome Prozess-ID.
    # WARUM Optional[int]? Wenn None → System wird Chrome selbst finden/starten.
    # Wenn gesetzt → Verwende EXAKT diesen Prozess (wichtig für Cookie-Persistenz).
    # BANNED: Hardcoded PIDs (z.B. pid=71104). PIDs ändern sich bei jedem Start!
    pid: Optional[int] = Field(
        default=None,
        description="Existing Chrome PID (None = auto-detect/start new Chrome)"
    )
    
    # cdp_port: CDP Port.
    # WARUM default=9999? Stealth-Runner Standard seit 2026-05-08.
    # NICHT 9999 (alt, deprecated). NICHT 9222 (User-Chrome Konflikt).
    # MUSS mit tatsächlichem Chrome-Port übereinstimmen!
    cdp_port: int = Field(
        default=9999,
        description="CDP port for Chrome communication (must match actual Chrome port)"
    )

    # mode: Login-Methode.
    # WARUM "cookie" als Default? Cookies sind schneller und zuverlässiger.
    # WARUM "cua" als Fallback? Wenn Cookies abgelaufen sind → CUA-basiertes
    #   Google OAuth mit Passkey/Keychain (funktioniert auch bei Shadow-DOM).
    # WARUM beide Modi? Flexibilität: Cookies funktionieren meistens, aber
    #   manchmal läuft die Session ab. Dann brauchen wir CUA als Backup.
    mode: str = Field(
        default="cookie",
        description="Login method: 'cookie' (fast, inject saved cookies) or 'cua' (Google OAuth via macOS Accessibility)"
    )


class LoginResponse(BaseModel):
    """
    Response für POST /services/heypiggy/login.
    
    Ergebnis des Login-Versuchs.
    
    MÖGLICHE STATUS-WERTE:
    • "success"      → Login erfolgreich, Session ist aktiv.
    • "already_logged_in" → Bereits eingeloggt (Cookie-Session noch gültig).
    • "error"        → Login fehlgeschlagen (Details in message + details).
    
    WICHTIGE FELDER:
    • details: Dict mit zusätzlichen Infos (pid, wid, etc.).
      pid = Chrome Prozess-ID (für spätere Calls).
      wid = Window ID (für CUA-Operationen).
    
    WARUM details als Dict[str, Any]?
    → Flexibel: Kann pid, wid, screenshot_url, etc. enthalten.
    → Typsicher trotzdem weil Pydantic validiert.
    """
    # status: Ergebnis des Logins.
    # Mögliche Werte: "success", "already_logged_in", "error".
    # WARUM Literal? Enforced Enum → kein "succes" Typo möglich.
    status: Literal["success", "error", "already_logged_in"] = Field(
        default="success",
        description="'success', 'already_logged_in', or 'error'"
    )
    
    # service: Name des Services.
    # WARUM? In Zukunft könnten mehrere Services unterstützt werden
    # (HeyPiggy, Swagbucks, etc.). Das Feld identifiziert den Service.
    service: str = Field(
        description="Service name, e.g. 'heypiggy'"
    )
    
    # profile: Verwendetes Profil.
    profile: str = Field(
        description="Profile used for login"
    )
    
    # message: Human-readable Status.
    # Beispiele: "Login successful", "Already logged in", "Chrome not found".
    message: str = Field(
        description="Human-readable result message"
    )
    
    # details: Zusätzliche technische Details.
    # WARUM Optional? Bei "error" könnten details None sein.
    # Bei "success" enthält es pid und wid für weitere Automation.
    details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Technical details: pid, wid, error_info, etc."
    )


# ═══════════════════════════════════════════════════════════════════════════════
# SEKTION 3: SURVEY ACTION SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════
# Diese Schemas definieren die CRUD-ähnlichen Operationen für Surveys.
# Jeder Endpoint = EINE Aktion. Keine Megafunctions.
# 
# PHILOSOPHIE:
# - Kleine, atomare Operationen sind besser als große Blackbox-Runner.
# - Jede Aktion kann einzeln getestet, debuggt und retry-t werden.
# - Fehler sind isoliert: Wenn click-card fehlschlägt, ist nur diese Aktion betroffen.
# ═══════════════════════════════════════════════════════════════════════════════


class SurveyClickCardRequest(BaseModel):
    """
    Request für POST /survey/click-card.
    
    Klickt eine Survey-Karte auf dem HeyPiggy Dashboard an.
    
    ABLAUF:
    1. Suche Survey-Cards mit onclick="clickSurvey('ID')" Attribut.
    2. Wenn survey_id=None → Klicke ERSTE verfügbare Card.
    3. Wenn survey_id=String → Klicke Card mit passender ID.
    4. Card-Click öffnet ein MODAL mit "Umfrage starten" Button.
    
    WARUM survey_id Optional?
    → None = "Egal welche Survey, nimm die erste" (gut für Automation).
    → String = "Bestimmte Survey" (gut für gezielte Auswahl).
    """
    # survey_id: ID der zu klickenden Survey.
    # WARUM Optional? None = erste verfügbare Survey.
    # Wenn gesetzt → Suche Card mit onclick="clickSurvey('ID')".
    survey_id: Optional[str] = Field(
        default=None,
        description="Specific survey ID, or None = first available survey card"
    )
    
    # cdp_port: CDP Port.
    # WARUM 9999? Siehe BrowserStartRequest Erklärung.
    cdp_port: int = Field(
        default=9999,
        description="CDP port for Chrome communication"
    )
    
    # profile_name: Browser-Profil.
    # WARUM? Mehrere Profile könnten unterschiedliche Sessions haben.
    profile_name: str = Field(
        default="default",
        description="Browser profile name"
    )


class SurveyClickCardResponse(BaseModel):
    """
    Response für POST /survey/click-card.
    
    Ergebnis des Card-Clicks.
    
    MÖGLICHE STATUS-WERTE:
    • "success"    → Card geklickt, Modal ist sichtbar.
    • "no_surveys" → Keine Survey-Cards gefunden (Dashboard leer).
    • "error"      → Technischer Fehler (Chrome nicht erreichbar, etc.).
    
    WICHTIGE FELDER:
    • modal_visible: True = Modal geöffnet. False = Kein Modal (selten).
    • modal_buttons: Liste der Buttons im Modal.
      Erwartet: ["Umfrage starten", "Schließen"] oder ["Nächste", "Umfrage starten", "Schließen"].
      Der Client kann dann "Umfrage starten" klicken.
    
    WARUM modal_buttons als List[str]?
    → Der Client muss wissen WELCHE Buttons verfügbar sind.
    → Beispiel: Wenn nur "Schließen" da ist → Survey nicht verfügbar.
    """
    # status: Ergebnis des Clicks.
    status: Literal["success", "error", "no_surveys"] = Field(
        default="success",
        description="'success' (modal open), 'no_surveys' (empty dashboard), or 'error'"
    )
    
    # survey_id: ID der geklickten Survey.
    # WARUM Optional? Bei "no_surveys" oder "error" → keine ID verfügbar.
    # Bei "success" → "first_available" oder konkrete ID.
    survey_id: Optional[str] = Field(
        default=None,
        description="Clicked survey ID, or 'first_available', or None"
    )
    
    # modal_visible: Ist ein Modal geöffnet?
    # WARUM? Bestätigung dass der Click tatsächlich ein Modal geöffnet hat.
    # Manchmal clickt JavaScript nicht korrekt (Race Conditions).
    modal_visible: bool = Field(
        default=False,
        description="True if a modal dialog is visible after click"
    )
    
    # modal_text: Text-Inhalt des Modals (erste 500 Zeichen).
    # WARUM? Debugging: Was steht im Modal? Titel? Beschreibung?
    modal_text: Optional[str] = Field(
        default=None,
        description="Modal content text (first 500 chars)"
    )
    
    # modal_buttons: Verfügbare Buttons im Modal.
    # WARUM List[str]? Der Client muss entscheiden welchen Button er als nächstes klickt.
    # Erwartete Werte: "Umfrage starten", "Schließen", "Nächste".
    modal_buttons: List[str] = Field(
        default_factory=list,
        description="Available buttons in modal, e.g. ['Umfrage starten', 'Schließen']"
    )
    
    # message: Human-readable Status.
    message: str = Field(
        description="e.g. 'Clicked survey card (first_available)', 'No survey cards found'"
    )


class SurveyGetModalRequest(BaseModel):
    """
    Request für GET /survey/modal.
    
    Liest den aktuellen Modal-Inhalt oder Seiteninhalt.
    
    WARUM GET statt POST?
    → Dieser Endpoint hat KEINE Seiteneffekte (nur lesen).
    → GET ist semantisch korrekt für Read-Operationen (REST-Prinzip).
    → POST wäre falsch weil nichts verändert wird.
    
    WARUM brauchen wir einen eigenen Request-Body für GET?
    → FastAPI erlaubt GET mit Request-Body (nicht standard REST, aber praktisch).
    → Alternative: Query-Parameter (cdp_port=9999&profile=default).
    → Wir verwenden Body für Konsistenz mit anderen Endpoints.
    """
    # cdp_port: CDP Port für Chrome-Verbindung.
    cdp_port: int = Field(
        default=9999,
        description="CDP port for Chrome communication"
    )
    
    # profile_name: Browser-Profil.
    profile_name: str = Field(
        default="default",
        description="Browser profile name"
    )


class SurveyElement(BaseModel):
    """
    Einzelnes interaktives Element auf einer Survey-Seite.
    
    WIRD VERWENDET VON:
    • GET /survey/modal → Liste aller Elemente im Modal
    • POST /survey/run-one → Interne Analyse der Seite
    
    ELEMENT-TYPEN (role):
    • "radio"      → Radio Button (Single-Choice Frage)
    • "checkbox"   → Checkbox (Multi-Choice Frage)
    • "textbox"    → Text Input (Kurze Antwort)
    • "textarea"   → Textarea (Lange Antwort)
    • "button"     → Button (Weiter, Submit, etc.)
    • "select"     → Dropdown (Auswahl aus Liste)
    
    REFERENZ-SYSTEM (ref):
    • @r0, @r1, ... → Radio Buttons
    • @c0, @c1, ... → Checkboxes
    • @t0, @t1, ... → Text Inputs
    • @a0, @a1, ... → Textareas
    • @b0, @b1, ... → Buttons
    • @s0, @s1, ... → Selects
    
    WARUM dieses Referenz-System?
    → Statt komplexer XPath oder CSS-Selector → einfaches @r0.
    → Keine Index-Probleme (CUA-driver Indices sind instabil! siehe banned.md).
    → Sprach-neutral: @r0 funktioniert für alle Sprachen.
    
    WARUM selected Optional[bool]?
    → Nur Radio/Checkbox haben "selected" Zustand.
    → Textbox/Textarea haben keinen selected-Zustand → None.
    → So ist das Model universell für alle Element-Typen.
    """
    # ref: Eindeutige Referenz innerhalb der Seite.
    # Format: @<typ><index> → @r0 = erstes Radio, @b3 = vierter Button.
    ref: str = Field(
        description="Element reference, e.g. '@r0' for first radio, '@b3' for fourth button"
    )
    
    # role: Element-Typ (semantische Rolle).
    # Nicht der HTML-Tag, sondern die INTERAKTIVE Rolle.
    # Beispiel: <input type="radio"> → role="radio".
    role: str = Field(
        description="Element type: 'radio', 'checkbox', 'textbox', 'textarea', 'button', 'select'"
    )
    
    # text: Angezeigter Text / Label.
    # Beispiel: "Männlich", "Weiter", "Wie alt sind Sie?".
    # WARUM text statt label? Weil label ein HTML-Attribut ist,
    # text ist der tatsächlich sichtbare Text.
    text: str = Field(
        description="Visible text or label of the element"
    )
    
    # label: HTML label (optional).
    # WARUM Optional? Nicht alle Elemente haben ein <label> Tag.
    # Manche verwenden aria-label, placeholder, oder nur Text-Content.
    label: Optional[str] = Field(
        default=None,
        description="HTML label text, if available"
    )
    
    # value: HTML value Attribut oder aktueller Inhalt.
    # Beispiel: Radio mit value="male" → value="male".
    # Beispiel: Textbox mit "32" → value="32".
    value: Optional[str] = Field(
        default=None,
        description="HTML value attribute or current content"
    )
    
    # selected: Aktueller Auswahl-Zustand.
    # True = ausgewählt (Radio/Checkbox).
    # False = nicht ausgewählt.
    # None = nicht zutreffend (Textbox, Button, Select).
    selected: Optional[bool] = Field(
        default=None,
        description="True if selected (radio/checkbox), None for other types"
    )
    
    # visible: Ist das Element sichtbar?
    # WARUM? Manche Elemente sind im DOM aber nicht sichtbar (display:none).
    # Wir filtern unsichtbare Elemente aus, aber falls doch → false.
    visible: bool = Field(
        default=True,
        description="True if element is visible on page"
    )


class SurveyGetModalResponse(BaseModel):
    """
    Response für GET /survey/modal.
    
    Liefert den aktuellen Zustand der Survey-Seite.
    
    MÖGLICHE STATUS-WERTE:
    • "success"   → Seite analysiert, Elemente extrahiert.
    • "no_modal"  → Kein Modal geöffnet (Survey nicht gestartet).
    • "error"     → Technischer Fehler.
    
    WICHTIGE FELDER:
    • elements: Liste aller interaktiven Elemente.
      Der Client kann diese anzeigen oder automatisch ausfüllen.
    • provider: URL-Matched Provider-Name (qualtrics, tolunastart, samplicio).
      NUR für Logging/Statistiken — KEINE provider-spezifische Logik!
      Echte Framework-Erkennung passiert im NEMO Loop (Nemotron 3 Omni).
    • progress: Fortschritt innerhalb der Survey (z.B. "3/10").
      None = nicht erkannt oder Einzelseite.

    WARUM provider nur für Logging?
    → Die API ist ein DUMMER CDP-Wrapper — sie hat KEINE Intelligenz.
    → Provider-Name ist primitives URL-Matching: "qualtrics" in url.lower().
    → Das ist NICHT "Erkennung" — es ist nur ein Label für Debug-Logs.
    → Echte Framework-Erkennung: Nemotron 3 Omni analysiert DOM-Struktur.
    → Nemotron versteht "Weiter", "Männlich", "18-25" in JEDEM Framework.
    → Keine provider-spezifische Logik nötig — universell via Compact Snapshot.
    """
    # status: Ergebnis der Analyse.
    status: Literal["success", "error", "no_modal"] = Field(
        default="success",
        description="'success', 'no_modal' (survey not started), or 'error'"
    )
    
    # modal_visible: Ist ein Modal geöffnet?
    # WARUM? Unterscheidet zwischen "Seite analysiert" und "Modal-Inhalt".
    # Wenn False → elements sind die Seiten-Elemente (nicht Modal).
    modal_visible: bool = Field(
        default=False,
        description="True if a modal dialog is currently visible"
    )
    
    # elements: Liste aller interaktiven Elemente.
    # WARUM List[SurveyElement]? Typed Array → Client weiß genau was drin ist.
    elements: List[SurveyElement] = Field(
        default_factory=list,
        description="All interactive elements on current page/modal"
    )
    
    # text: Gesamter Text-Inhalt der Seite (erste 2000 Zeichen).
    # WARUM? Für Text-Suche, Keyword-Erkennung, Progress-Extraktion.
    text: str = Field(
        default="",
        description="Page text content (first 2000 chars)"
    )
    
    # page_title: Dokument-Titel.
    # WARUM? Debugging: Auf welcher Seite sind wir?
    # Beispiel: "Survey Page 3" vs "Disqualification".
    page_title: str = Field(
        default="",
        description="Current page title"
    )
    
    # provider: URL-Matched Provider-Label (NUR für Logging/Statistiken).
    # Werte: "heypiggy_modal", "qualtrics", "tolunastart", "samplicio", "unknown".
    # WARUM default="unknown"? Wenn URL keinen bekannten String enthält → unknown.
    # WARUM "Detected" im Description? Aus Kompatibilität — es ist NICHT echte Erkennung.
    #   Echte Erkennung passiert im NEMO Loop (Nemotron 3 Omni analysiert DOM-Struktur).
    #   Dieser Wert ist primitives URL-Matching: "qualtrics" in url.lower().
    provider: str = Field(
        default="unknown",
        description="URL-matched provider label (for logging only): 'qualtrics', 'tolunastart', 'samplicio', 'heypiggy_modal', 'unknown'. NOT functional detection — Nemotron 3 Omni handles universal framework recognition."
    )
    
    # progress: Fortschritt innerhalb der Survey.
    # Format: "current/total" z.B. "3/10".
    # WARUM Optional? Nicht alle Surveys zeigen Fortschritt an.
    # Manche haben nur "Weiter" ohne Seitennummer.
    progress: Optional[str] = Field(
        default=None,
        description="Survey progress, e.g. '3/10'. None if not detected"
    )
    
    # message: Human-readable Status.
    message: str = Field(
        description="e.g. 'Modal with 15 elements', 'No survey modal open'"
    )


class SurveyClickButtonRequest(BaseModel):
    """
    Request für POST /survey/click-button.
    
    Klickt einen Button auf der aktuellen Survey-Seite.
    
    ABLAUF:
    1. Suche Button mit passendem Label (case-insensitive, partial match).
    2. Simuliere Click via JavaScript (dispatchEvent).
    3. Warte timeout_ms Millisekunden.
    4. Vergleiche Seiteninhalt vor/nach → page_changed Flag.
    
    WICHTIGE FELDER:
    • button_label: Text des Buttons (z.B. "Weiter", "Umfrage starten", "Schließen").
      Case-insensitive: "weiter" matcht "Weiter".
      Partial match: "Weiter" matcht "Weiter →".
    • timeout_ms: Wartezeit NACH dem Click.
      WARUM 5000ms Default? Survey-Seiten brauchen Zeit zum Laden (AJAX, Redirects).
      Zu kurz → Seite noch nicht geladen, page_changed=false obwohl sich was änderte.
      Zu lang → API-Call dauert ewig. 5s ist ein guter Kompromiss.
    
    WARUM Partial Match?
    → Button-Labels variieren:
      "Weiter" vs "weiter" (Groß-/Kleinschreibung)
      "Weiter →" vs "Weiter" (Pfeile, Whitespace)
      "Umfrage starten" vs "Starten" (unterschiedliche Längen)
    → Exact match wäre zu fragil und bräche bei kleinen UI-Änderungen.
    """
    # button_label: Text des zu klickenden Buttons.
    # WARUM ... (Required)? Der Client MUSS angeben welchen Button er will.
    # Kein Default möglich (welcher Button? "Weiter"? "Submit"?).
    button_label: str = Field(
        ...,
        description="Button text to click (partial match, case-insensitive). E.g. 'Weiter', 'Umfrage starten'"
    )
    
    # cdp_port: CDP Port.
    cdp_port: int = Field(
        default=9999,
        description="CDP port for Chrome communication"
    )
    
    # profile_name: Browser-Profil.
    profile_name: str = Field(
        default="default",
        description="Browser profile name"
    )
    
    # timeout_ms: Wartezeit nach dem Click.
    # WARUM 5000? Siehe oben. Manche Seiten laden in 500ms, andere brauchen 3s.
    # 5000ms deckt 95% der Fälle ab. Bei langsamen Providern → erhöhen.
    timeout_ms: int = Field(
        default=5000,
        description="Wait time in milliseconds after click for page to load"
    )


class SurveyClickButtonResponse(BaseModel):
    """
    Response für POST /survey/click-button.
    
    Ergebnis des Button-Clicks.
    
    MÖGLICHE STATUS-WERTE:
    • "success"    → Button geklickt (unabhängig ob Seite sich änderte).
    • "not_found"  → Kein Button mit diesem Label gefunden.
    • "error"      → Technischer Fehler (Chrome nicht erreichbar).
    • "timeout"    → Timeout während des Clicks (selten).
    
    WICHTIGE FELDER:
    • page_changed: True = Seiteninhalt hat sich GEÄNDERT nach dem Click.
      False = Seite gleich (Button hat nichts bewirkt oder Modal geschlossen).
      Wichtig für Loop-Logik: Wenn page_changed=False → evtl. Retry nötig.
    • new_text: Neuer Seiteninhalt (first 500 chars).
      Nützlich für Debugging: Was steht jetzt auf der Seite?
    
    WARUM page_changed wichtig?
    → Manche Buttons schließen nur ein Modal (kein Seitenwechsel).
    → "Schließen" → page_changed=False.
    → "Weiter" → page_changed=True (neue Frage geladen).
    → Der Client kann entscheiden: Weiter mit nächster Aktion oder Warten.
    """
    # status: Ergebnis des Clicks.
    status: Literal["success", "error", "not_found", "timeout"] = Field(
        default="success",
        description="'success', 'not_found' (button not found), 'error', or 'timeout'"
    )
    
    # button_label: Welcher Button wurde geklickt (oder versucht zu klicken).
    # WARUM? Bestätigung an den Client: "Ja, ich habe 'Weiter' versucht".
    # Bei not_found → Client weiß welcher Button fehlte.
    button_label: str = Field(
        description="Button label that was clicked or attempted"
    )
    
    # page_changed: Hat sich die Seite geändert?
    # WARUM? Siehe oben. Kritischer Indikator für Loop-Logik.
    page_changed: bool = Field(
        default=False,
        description="True if page content changed after click (new question loaded)"
    )
    
    # new_text: Neuer Seiteninhalt.
    # WARUM nur 500 chars? Nicht zu viel Daten in Response (Performance).
    # Client kann bei Bedarf GET /survey/modal aufrufen für alle Elemente.
    new_text: str = Field(
        default="",
        description="New page content (first 500 chars) after click"
    )
    
    # message: Human-readable Status.
    message: str = Field(
        description="e.g. 'Clicked Weiter (page changed: true)', 'Button not found: Submit'"
    )


class SurveySelectOptionRequest(BaseModel):
    """
    Request für POST /survey/select-option.
    
    Wählt eine Radio-Button oder Checkbox-Option aus.
    
    ABLAUF:
    1. Suche Radio Buttons mit passendem Label/Text (case-insensitive, partial).
    2. Wenn nicht gefunden → Suche Checkboxes.
    3. Klicke das ERSTE passende Element.
    4. Warte wait_after_ms Millisekunden.
    
    WICHTIGE FELDER:
    • option_text: Text der Option (z.B. "Männlich", "Deutschland", "18-25 Jahre").
      Partial match: "Männlich" matcht "männlich" (case-insensitive).
    • wait_after_ms: Wartezeit NACH der Auswahl.
      WARUM 1000ms? Manche Survey-Seiten validieren die Auswahl sofort
      und aktivieren/deaktivieren den "Weiter"-Button. 1s ist ausreichend.
    
    WARUM Radio VOR Checkbox?
    → Die meisten Survey-Fragen sind Single-Choice (Radio).
    → Wir prüfen zuerst Radio, dann Checkbox als Fallback.
    → Das ist eine Heuristik die in >80% der Fälle korrekt ist.
    
    WARUM nur ERSTES passende Element?
    → Radio Buttons sind Single-Choice: Nur eine Auswahl möglich.
    → Wenn mehrere matchten wäre das ein UI-Bug (duplizierte Labels).
    → Bei Checkboxen (Multi-Choice) könnte man mehrere auswählen,
      aber das ist komplexer und selten nötig.
    """
    # option_text: Text der zu wählenden Option.
    # WARUM ... (Required)? Kein Default möglich (welche Option?).
    option_text: str = Field(
        ...,
        description="Option text to select (partial match, case-insensitive). E.g. 'Männlich', 'Deutschland'"
    )
    
    # cdp_port: CDP Port.
    cdp_port: int = Field(
        default=9999,
        description="CDP port for Chrome communication"
    )
    
    # profile_name: Browser-Profil.
    profile_name: str = Field(
        default="default",
        description="Browser profile name"
    )
    
    # wait_after_ms: Wartezeit nach Auswahl.
    wait_after_ms: int = Field(
        default=1000,
        description="Wait time in milliseconds after selection for UI to update"
    )


class SurveySelectOptionResponse(BaseModel):
    """
    Response für POST /survey/select-option.
    
    Ergebnis der Options-Auswahl.
    
    MÖGLICHE STATUS-WERTE:
    • "success"    → Option gefunden und ausgewählt.
    • "not_found"  → Keine Option mit diesem Text gefunden.
    • "error"      → Technischer Fehler.
    
    WICHTIGE FELDER:
    • selected: True = Element wurde geklickt.
      False = Nichts gefunden oder Fehler.
      Hinweis: "selected" sagt nicht ob die Survey-Engine die Auswahl AKZEPTIERT
      (manche Survey-Engines validieren und disqualifizieren).
      Es sagt nur: "Der Click wurde ausgeführt".
    
    WARUM selected Bool statt Literal?
    → Einfacher für Client-Logik: if response.selected → nächster Schritt.
    → Literal wäre möglich ("selected", "not_selected") aber Bool ist idiomascher.
    """
    # status: Ergebnis der Auswahl.
    status: Literal["success", "error", "not_found"] = Field(
        default="success",
        description="'success', 'not_found' (option not found), or 'error'"
    )
    
    # option_text: Welche Option wurde versucht auszuwählen.
    option_text: str = Field(
        description="Option text that was selected or attempted"
    )
    
    # selected: Wurde die Option tatsächlich geklickt?
    selected: bool = Field(
        default=False,
        description="True if the option element was clicked. Note: does NOT guarantee survey accepted the answer"
    )
    
    # message: Human-readable Status.
    message: str = Field(
        description="e.g. 'Selected: Männlich (radio)', 'Option not found: 99 Jahre'"
    )


class SurveyFillTextRequest(BaseModel):
    """
    Request für POST /survey/fill-text.
    
    Füllt ein Text-Input-Feld oder Textarea aus.
    
    ABLAUF:
    1. Suche Input-Feld mit passendem Label/Name/ID (case-insensitive, partial).
    2. Fokussiere das Feld (setzt Cursor).
    3. Setze value = gewünschter Text.
    4. Feuere 'input' und 'change' Events (wichtig für React/Vue/Angular!).
    5. Wenn nicht gefunden → Suche Textarea als Fallback.
    
    WICHTIGE FELDER:
    • input_label: Label/Name/ID des Feldes (z.B. "Alter", "E-Mail", "comment").
      Wir suchen in: id, name, aria-label, placeholder, und <label>-Text.
    • value: Einzutragender Wert.
      WARUM escaped wir intern? Einfache Anführungszeichen im Wert (z.B. "It's fine")
      würden das JavaScript brechen. Wir escapen sie zu "It\'s fine".
    
    WARUM Events feuern?
    → Moderne Frameworks (React, Vue, Angular) überwachen Input-Events
      um ihren internen State zu aktualisieren.
    → Nur value setzen reicht NICHT! Der Framework-State bleibt leer.
    → Wir dispatchieren 'input' und 'change' Events mit bubbles=true
      damit sie durch den DOM-Bubble-Mechanismus das Framework erreichen.
    
    WARUM Textarea Fallback?
    → Manche offene Fragen verwenden <textarea> statt <input>.
    → Der Client muss nicht wissen welcher Tag verwendet wird.
    → Wir versuchen zuerst Input, dann Textarea.
    """
    # input_label: Identifikation des Feldes.
    # WARUM ... (Required)? Kein Default möglich (welches Feld?).
    input_label: str = Field(
        ...,
        description="Input label, name, id, or aria-label to identify the field (partial match)"
    )
    
    # value: Wert der eingetragen werden soll.
    # WARUM ... (Required)? Kein Default möglich (was soll eingetragen werden?).
    value: str = Field(
        ...,
        description="Text value to enter into the field"
    )
    
    # cdp_port: CDP Port.
    cdp_port: int = Field(
        default=9999,
        description="CDP port for Chrome communication"
    )
    
    # profile_name: Browser-Profil.
    profile_name: str = Field(
        default="default",
        description="Browser profile name"
    )


class SurveyFillTextResponse(BaseModel):
    """
    Response für POST /survey/fill-text.
    
    Ergebnis der Text-Eingabe.
    
    MÖGLICHE STATUS-WERTE:
    • "success"    → Feld gefunden und ausgefüllt.
    • "not_found"  → Kein Feld mit diesem Label gefunden.
    • "error"      → Technischer Fehler.
    
    WICHTIGE FELDER:
    • value: Der eingetragene Wert (Echo für Bestätigung).
      Wenn der Client "32" sendet und "32" zurückkommt → OK.
      Wenn "" zurückkommt → möglicherweise Fehler.
    
    WARUM value in Response?
    → Bestätigung: Der Client kann prüfen ob der richtige Wert eingetragen wurde.
    → Wenn JavaScript das Feld nach dem Setzen überschreibt (validierung),
      sieht der Client den tatsächlichen Wert.
    """
    # status: Ergebnis der Eingabe.
    status: Literal["success", "error", "not_found"] = Field(
        default="success",
        description="'success', 'not_found' (field not found), or 'error'"
    )
    
    # input_label: Welches Feld wurde versucht zu füllen.
    input_label: str = Field(
        description="Field label that was filled or attempted"
    )
    
    # value: Eingetragener Wert.
    value: str = Field(
        description="Value that was entered (echo for confirmation)"
    )
    
    # message: Human-readable Status.
    message: str = Field(
        description="e.g. 'Filled: age=32', 'Field not found: phone_number'"
    )


class SurveyRunOneRequest(BaseModel):
    """
    Request für POST /survey/run-one.
    
    Führt EINE komplette Survey von Anfang bis Ende aus (Loop).
    
    ABLAUF:
    1. Survey Card klicken (öffnet Modal).
    2. "Umfrage starten" Button klicken.
    3. LOOP (max_pages Iterationen):
       a. Seiteninhalt lesen.
       b. Prüfe auf Completion ("Danke", "Fertig", "Vielen Dank").
       c. Prüfe auf Disqualifikation ("Screen Out", "Leider", "nicht qualifiziert").
       d. Auto-select: Wähle erste Radio/Checkbox Option.
       e. Auto-fill: Fülle leere Textfelder mit "test".
       f. Klicke "Weiter" / "Next" / "Submit".
    4. Gib Ergebnis zurück.
    
    WICHTIGE FELDER:
    • survey_id: Spezifische Survey oder None = erste verfügbare.
    • max_pages: Safety-Limit gegen Endlosschleifen.
      WARUM 20? Die meisten Surveys haben 5-15 Seiten.
      >20 deutet auf eine Endlosschleife oder sehr lange Survey hin.
      Bei 20+ → Abbruch mit Status "error".
    
    WARUM Auto-Select/Auto-Fill?
    → Dies ist ein DEMO/Proof-of-Concept Endpoint.
    → In Produktion würde ein AI-Model (Nemotron) die beste Antwort wählen.
    → Für jetzt: Wir wählen einfach die erste Option und füllen "test" ein.
    → WARNUNG: In Produktion → echte Antworten vom User oder AI!
    
    WARUM max_pages Limit?
    → Endlosschleifen verhindern. Wenn eine Survey hängt (Bug, Loop),
      brechen wir nach max_pages ab.
    → Schützt vor API-Timeouts und Resource-Leaks.
    """
    # survey_id: ID der Survey.
    # WARUM Optional? None = erste verfügbare Survey (einfachste Automatisierung).
    survey_id: Optional[str] = Field(
        default=None,
        description="Survey ID or None = first available survey"
    )
    
    # cdp_port: CDP Port.
    cdp_port: int = Field(
        default=9999,
        description="CDP port for Chrome communication"
    )
    
    # profile_name: Browser-Profil.
    profile_name: str = Field(
        default="default",
        description="Browser profile name"
    )
    
    # max_pages: Maximale Anzahl Seiten.
    # WARUM default=20? Siehe oben. Safety-Limit.
    max_pages: int = Field(
        default=20,
        description="Max survey pages before giving up (safety limit against infinite loops)"
    )


class SurveyRunOneResponse(BaseModel):
    """
    Response für POST /survey/run-one.
    
    Ergebnis der kompletten Survey-Ausführung.
    
    MÖGLICHE STATUS-WERTE:
    • "completed"   → Survey erfolgreich abgeschlossen (Danke-Seite erreicht).
    • "screen_out"  → Disqualifiziert (z.B. falsches Alter, falsche Region).
    • "error"       → Technischer Fehler oder max_pages erreicht.
    • "success"     → Generischer Erfolg (veraltet, lieber "completed" verwenden).
    
    WICHTIGE FELDER:
    • pages_completed: Anzahl beantworteter Seiten.
      Nützlich für Statistiken: "Survey mit 8 Seiten in 45s".
    • earned: Verdiente Belohnung in EUR.
      0.0 = keine Belohnung (Screen-Out oder Fehler).
      >0 = Belohnung wird dem Konto gutgeschrieben.
    • elapsed_s: Gesamtdauer in Sekunden.
      Nützlich für Performance-Monitoring.
    • error: Fehlermeldung wenn Status="error".
      None bei Erfolg.
    
    WARUM earned Float?
    → HeyPiggy zeigt Rewards mit 2 Dezimalstellen an (z.B. 0.35€).
    → Float ist ausreichend für Euro-Beträge (keine Finanz-Software).
    → Bei Bedarf könnte man Decimal verwenden für exakte Berechnungen.
    """
    # status: Endergebnis der Survey.
    status: Literal["success", "completed", "screen_out", "error"] = Field(
        default="success",
        description="'completed' (finished), 'screen_out' (disqualified), 'error' (technical failure), or 'success'"
    )
    
    # survey_id: ID der ausgeführten Survey.
    survey_id: str = Field(
        description="Survey ID that was executed"
    )
    
    # pages_completed: Anzahl beantworteter Seiten.
    pages_completed: int = Field(
        default=0,
        description="Number of survey pages answered"
    )
    
    # earned: Verdiente Belohnung in EUR.
    earned: float = Field(
        default=0.0,
        description="Earned reward in EUR (0.0 if screen_out or error)"
    )
    
    # elapsed_s: Gesamtdauer in Sekunden.
    elapsed_s: float = Field(
        default=0.0,
        description="Total execution time in seconds"
    )
    
    # error: Fehlermeldung.
    # WARUM Optional? Nur bei Status="error" gesetzt.
    # Bei Erfolg → None (sauberes Model).
    error: Optional[str] = Field(
        default=None,
        description="Error message if status='error', None otherwise"
    )
    
    # message: Human-readable Status.
    message: str = Field(
        description="e.g. 'Survey completed in 45.2s, earned 0.35€', 'Screen out on page 3'"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# SEKTION 4: DASHBOARD SCHEMAS (Scan + Balance)
# ═══════════════════════════════════════════════════════════════════════════════
# Diese Schemas steuern das Dashboard-Scanning:
# - Welche Surveys sind verfügbar?
# - Wie viel kann man verdienen?
# - Wie hoch ist der aktuelle Kontostand?
# ═══════════════════════════════════════════════════════════════════════════════


class DashboardSurvey(BaseModel):
    """
    Einzelner Survey-Eintrag auf dem HeyPiggy Dashboard.
    
    WIRD VERWENDET VON:
    • DashboardScanResponse.available_surveys → Liste aller verfügbaren Surveys.
    
    WICHTIGE FELDER:
    • reward_eur: Belohnung in EUR (z.B. 0.35€, 1.20€).
    • duration_min: Geschätzte Dauer in Minuten.
      Nützlich für ROI-Berechnung: reward / duration = €/min.
    • provider: Anzeige-Label vom Dashboard (qualtrics, tolunastart, etc.).
      Aus dem HeyPiggy Dashboard UI gescraped — NUR für Logging/Filter.
      Keine funktionale Framework-Erkennung (die macht Nemotron 3 Omni).
    
    WARUM duration_min Optional?
    → Nicht alle Surveys zeigen die Dauer an.
    → Wenn nicht sichtbar → None (nicht 0, denn 0 wäre falsch).
    
    WARUM survey_id als String?
    → HeyPiggy verwendet numerische IDs (z.B. "12345").
    → String ist flexibler: Kann auch alphanumerische IDs unterstützen.
    → Keine mathematischen Operationen nötig (kein Int-Vorteil).
    """
    # survey_id: Eindeutige ID der Survey.
    survey_id: str = Field(
        description="Survey ID as shown on dashboard"
    )
    
    # reward_eur: Belohnung in Euro.
    # WARUM float? HeyPiggy zeigt 2 Dezimalstellen (0.35€).
    # Float ist ausreichend für diese Genauigkeit.
    reward_eur: float = Field(
        description="Reward amount in EUR"
    )
    
    # duration_min: Geschätzte Dauer.
    # WARUM Optional[int]? Nicht immer sichtbar. Int weil Minuten ganze Zahlen sind.
    duration_min: Optional[int] = Field(
        default=None,
        description="Estimated duration in minutes. None if not displayed"
    )
    
    # provider: Dashboard-Anzeige-Label (NUR für Logging/Filter).
    # WARUM String statt Literal? Neue Provider-Labels können jederzeit hinzukommen.
    # WARUM "Provider" im Namen? Aus Kompatibilität — es ist KEINE echte Erkennung.
    #   Wert kommt vom HeyPiggy Dashboard UI (gescraped Text/Label).
    #   Echte Framework-Erkennung: Nemotron 3 Omni analysiert DOM-Struktur.
    #   Dieses Label ist nur ein String aus dem Dashboard — nicht funktional.
    provider: str = Field(
        default="unknown",
        description="Dashboard display label (for logging/filtering only): 'qualtrics', 'tolunastart', 'samplicio', 'cint', etc. NOT functional detection — Nemotron 3 Omni handles universal framework recognition via Compact Snapshot."
    )
    
    # title: Titel/Beschreibung der Survey.
    # WARUM? Hilft beim Erkennen des Themas (z.B. "Umfrage zu Lebensmitteln").
    # Nützlich für Filter: "Nur Surveys über Technologie".
    title: str = Field(
        default="",
        description="Survey title or description (first 100 chars)"
    )


class DashboardScanRequest(BaseModel):
    """
    Request für POST /dashboard/scan.
    
    Scannt das HeyPiggy Dashboard nach verfügbaren Surveys.
    
    WARUM nur cdp_port?
    → Der Scan liest nur den aktuellen Zustand des Dashboards.
    → Keine zusätzlichen Parameter nötig (kein Filter, keine Sortierung).
    → Das Dashboard zeigt ALLE verfügbaren Surveys an.
    
    WARUM POST statt GET?
    → Für Konsistenz mit anderen Endpoints (alle Survey-Calls sind POST).
    → GET mit Body ist nicht standard REST (manche Proxies blockieren das).
    → POST ist sicherer für zukünftige Erweiterungen (Filter-Body).
    """
    # cdp_port: CDP Port.
    cdp_port: int = Field(
        default=9999,
        description="CDP port for Chrome communication"
    )


class DashboardScanResponse(BaseModel):
    """
    Response für POST /dashboard/scan.
    
    Ergebnis des Dashboard-Scans.
    
    WICHTIGE FELDER:
    • balance_eur: Aktueller Kontostand.
      Wird aus dem Dashboard-Header/Sidebar extrahiert.
    • available_surveys: Liste aller verfügbaren Surveys mit Rewards.
      LEERE LISTE = kein Survey verfügbar (Dashboard leer).
    • total_rewards: Summe aller verfügbaren Rewards.
      Nützlich für Entscheidung: "Lohnt es sich heute Surveys zu machen?"
      Wenn total_rewards < 1.00€ → vielleicht morgen wieder versuchen.
    
    WARUM total_rewards berechnen?
    → Client muss nicht selbst summieren.
    → Sofortige Entscheidungsgrundlage: "Es gibt 3.50€ an Surveys".
    → Performance: Berechnung passiert Server-seitig (einmalig).
    
    WARUM balance_eur hier UND in /dashboard/balance?
    → Scan gibt beides auf einmal (Convenience).
    → Balance ist oft neben den Surveys sichtbar (ein Request reicht).
    → /dashboard/balance ist für gezielte Abfrage ohne Scan-Overhead.
    """
    # status: Ergebnis des Scans.
    status: Literal["success", "error"] = Field(
        default="success",
        description="'success' or 'error'"
    )
    
    # balance_eur: Aktueller Kontostand.
    balance_eur: float = Field(
        default=0.0,
        description="Current account balance in EUR"
    )
    
    # available_surveys: Liste aller verfügbaren Surveys.
    available_surveys: List[DashboardSurvey] = Field(
        default_factory=list,
        description="All available surveys with rewards"
    )
    
    # total_rewards: Summe aller Rewards.
    total_rewards: float = Field(
        default=0.0,
        description="Sum of all available rewards in EUR"
    )
    
    # message: Human-readable Zusammenfassung.
    message: str = Field(
        description="e.g. 'Found 5 surveys, total rewards: 3.50€'"
    )


class BalanceRequest(BaseModel):
    """
    Request für POST /dashboard/balance.
    
    Liest den aktuellen Kontostand aus.
    
    WARUM eigener Endpoint?
    → Schneller als /dashboard/scan (kein Survey-Scanning nötig).
    → Nützlich für periodische Abfrage (z.B. alle 5 Minuten).
    → Weniger Daten = weniger Netzwerk-Overhead.
    
    WARUM nur cdp_port?
    → Keine zusätzlichen Parameter nötig.
    → Der Kontostand ist immer an derselben Stelle im Dashboard.
    """
    # cdp_port: CDP Port.
    cdp_port: int = Field(
        default=9999,
        description="CDP port for Chrome communication"
    )


class BalanceResponse(BaseModel):
    """
    Response für POST /dashboard/balance.
    
    Aktueller Kontostand.
    
    WICHTIGE FELDER:
    • balance_eur: Der Betrag.
      0.0 = nicht lesbar oder tatsächlich 0.
      >0 = aktuelles Guthaben.
    • currency: Währung (immer "EUR" für HeyPiggy).
      WARUM? Zukunftssicherheit: Falls HeyPiggy andere Währungen unterstützt.
    
    WARUM currency String?
    → ISO 4217 Standard: "EUR", "USD", "GBP".
    → Ermöglicht Währungsumrechnung bei Bedarf.
    → Für HeyPiggy immer "EUR", aber Schema ist generisch.
    """
    # status: Ergebnis.
    status: Literal["success", "error"] = Field(
        default="success",
        description="'success' or 'error'"
    )
    
    # balance_eur: Der Betrag.
    balance_eur: float = Field(
        description="Current balance in EUR"
    )
    
    # currency: Währung.
    currency: str = Field(
        default="EUR",
        description="Currency code (ISO 4217). Always 'EUR' for HeyPiggy"
    )
    
    # message: Human-readable Status.
    message: str = Field(
        description="e.g. 'Balance: 12.35€', 'Balance not visible'"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# SEKTION 5: COOKIE SCHEMAS (Session Persistenz)
# ═══════════════════════════════════════════════════════════════════════════════
# Cookies sind der SCHLÜSSEL zur Session-Persistenz.
# Ohne Cookies müssten wir bei jedem Start neu einloggen (Google OAuth).
# Mit Cookies: Einmal einloggen → Cookies speichern → beliebig oft wiederverwenden.
# 
# ARCHITEKTUR:
# 1. POST /cookies/extract   → Cookies aus Browser holen + in JSON speichern.
# 2. POST /cookies/inject    → Cookies aus JSON in Browser laden.
# 3. POST /cookies/verify    → Prüfen ob Session noch aktiv ist.
# ═══════════════════════════════════════════════════════════════════════════════


class CookieExtractRequest(BaseModel):
    """
    Request für POST /cookies/extract.
    
    Extrahiert Cookies aus dem aktiven Browser.
    
    WICHTIGE FELDER:
    • domain_filter: Nur Cookies dieser Domain extrahieren.
      "heypiggy" = nur heypiggy.com Cookies (empfohlen).
      None = ALLE Cookies (kann groß sein, includes Google, etc.).
    • save_to_file: Soll in JSON-Datei gespeichert werden?
      True = ja (default), False = nur in Response zurückgeben.
    • filename: Dateiname für gespeicherte Cookies.
      Default: "heypiggy-cookies.json".
    
    WARUM domain_filter empfohlen?
    → HeyPiggy Cookies sind klein (~7 Cookies).
    → ALLE Cookies können HUNDERTE sein (Google, Analytics, etc.).
    → Kleinere Datei = schnelleres Laden, weniger Speicher.
    → Fokus auf relevante Cookies.
    
    WARUM save_to_file?
    → True: Cookies persistieren über API-Restarts.
    → False: Nur temporär (z.B. für Debugging).
    → Flexibilität für verschiedene Use-Cases.
    """
    # profile_name: Browser-Profil.
    profile_name: str = Field(
        default="default",
        description="Browser profile name"
    )
    
    # domain_filter: Domain-Filter für Cookies.
    # WARUM default="heypiggy"? Wir wollen primär HeyPiggy-Session-Cookies.
    # "heypiggy" matcht "heypiggy.com", ".heypiggy.com", etc.
    domain_filter: Optional[str] = Field(
        default="heypiggy",
        description="Domain filter (None = all domains, 'heypiggy' = only heypiggy.com)"
    )
    
    # save_to_file: In Datei speichern?
    save_to_file: bool = Field(
        default=True,
        description="Save extracted cookies to a JSON file"
    )
    
    # filename: Dateiname.
    # WARUM default "heypiggy-cookies.json"? Konvention: <service>-cookies.json.
    filename: str = Field(
        default="heypiggy-cookies.json",
        description="Filename for saved cookies (in ./data directory)"
    )


class CookieExtractResponse(BaseModel):
    """
    Response für POST /cookies/extract.
    
    Ergebnis der Cookie-Extraktion.
    
    WICHTIGE FELDER:
    • cookies: Liste aller extrahierten Cookies.
      Jedes Cookie ist ein Dict mit name, value, domain, path, etc.
    • count: Anzahl der Cookies.
      Nützlich für Validierung: "Erwartet ~7, bekommen 3 → Session unvollständig".
    • stats: Statistiken (total, domains, httpOnly, secure, session).
      Nützlich für schnelle Übersicht ohne alle Cookies zu parsen.
    • saved_to: Pfad zur gespeicherten Datei (oder None wenn nicht gespeichert).
    • execution_time: Dauer der Operation.
      Nützlich für Performance-Monitoring.
    
    WARUM stats Dict?
    → Schnelle Übersicht: "7 Cookies, 2 httpOnly, 5 secure".
    → Client kann prüfen: Wenn count=0 → Session nicht aktiv.
    → Wenn session_cookies=0 → alle Cookies haben Ablaufdatum (gut für Persistenz).
    
    WARUM execution_time String?
    → Human-readable: "0.45s".
    → Float wäre auch möglich, aber String ist selbsterklärend.
    → Format: "{seconds:.2f}s".
    """
    # status: Ergebnis.
    status: Literal["success", "error"] = Field(
        default="success",
        description="'success' or 'error'"
    )
    
    # profile: Verwendetes Profil.
    profile: str = Field(
        description="Browser profile used"
    )
    
    # cookies: Liste der Cookies.
    # WARUM List[Dict[str, Any]]? Jedes Cookie hat unterschiedliche Felder.
    # Beispiel: {"name": "PHPSESSID", "value": "abc123", "domain": "heypiggy.com"}
    # Pydantic könnte ein Cookie-Model definieren, aber Dict ist flexibler
    # für verschiedene Cookie-Formate (Playwright, Puppeteer, etc.).
    cookies: List[Dict[str, Any]] = Field(
        description="List of extracted cookie dictionaries"
    )
    
    # count: Anzahl.
    count: int = Field(
        description="Number of cookies extracted"
    )
    
    # stats: Statistiken.
    stats: Dict[str, Any] = Field(
        default_factory=dict,
        description="Cookie statistics: total, domains, httpOnly, secure, session"
    )
    
    # saved_to: Pfad zur Datei.
    # WARUM Optional? Wenn save_to_file=False → None.
    saved_to: Optional[str] = Field(
        default=None,
        description="Path to saved file, or None if not saved"
    )
    
    # execution_time: Dauer.
    execution_time: str = Field(
        default="",
        description="Execution time, e.g. '0.45s'"
    )


class CookieInjectRequest(BaseModel):
    """
    Request für POST /cookies/inject.
    
    Lädt gespeicherte Cookies in den Browser.
    
    WICHTIGE FELDER:
    • filename: Dateiname der Cookie-Datei.
      Default: "heypiggy-cookies.json".
    • verify_session: Soll nach dem Injizieren die Session geprüft werden?
      True = navigiere zum Dashboard und prüfe ob eingeloggt (empfohlen).
      False = nur injizieren, keine Prüfung (schneller).
    
    WARUM verify_session True?
    → Bestätigung dass die Session tatsächlich funktioniert.
    → Wenn Cookies abgelaufen → verify_session=false → Client denkt es klappt,
      aber beim nächsten Call ist Session tot.
    → verify_session=true fängt abgelaufene Cookies sofort ab.
    
    WARUM filename Parameter?
    → Mehrere Cookie-Sets möglich (heypiggy-cookies.json,
      heypiggy-cookies-backup.json, etc.).
    → Ermöglicht Cookie-Rotation und Backup-Strategien.
    """
    # filename: Quell-Datei.
    filename: str = Field(
        default="heypiggy-cookies.json",
        description="Filename of cookies to load (from ./data directory)"
    )
    
    # verify_session: Session prüfen?
    verify_session: bool = Field(
        default=True,
        description="Verify session after injection by navigating to dashboard"
    )


class CookieInjectResponse(BaseModel):
    """
    Response für POST /cookies/inject.
    
    Ergebnis der Cookie-Injektion.
    
    WICHTIGE FELDER:
    • injected_count: Anzahl erfolgreich injizierter Cookies.
      Weniger als erwartet → einige Cookies waren ungültig (domain mismatch, etc.).
    • session_active: True = Session funktioniert (User ist eingeloggt).
      False = Cookies haben nicht funktioniert (abgelaufen, falscher Browser, etc.).
    
    WARUM injected_count vs total_count?
    → injected_count = wie viele TATSÄCHLICH injiziert wurden.
    → Manche Cookies können fehlschlagen (falsche Domain für aktuelle Seite).
    → Wenn injected_count < count → einige Cookies waren ungültig.
    
    WARUM session_active Bool?
    → Der wichtigste Indikator für den Client.
    → True: Alles OK, kann mit Surveys fortfahren.
    → False: Neu einloggen nötig (POST /services/heypiggy/login).
    """
    # status: Ergebnis.
    status: Literal["success", "failed", "error"] = Field(
        default="success",
        description="'success' (all OK), 'failed' (session not active), 'error' (technical failure)"
    )
    
    # injected_count: Anzahl injizierter Cookies.
    injected_count: int = Field(
        default=0,
        description="Number of cookies successfully injected"
    )
    
    # session_active: Funktioniert die Session?
    session_active: bool = Field(
        default=False,
        description="True if session is active after injection (logged in)"
    )
    
    # execution_time: Dauer.
    execution_time: str = Field(
        default="",
        description="Execution time, e.g. '1.23s'"
    )
    
    # error: Fehlermeldung.
    error: Optional[str] = Field(
        default=None,
        description="Error message if status='error', None otherwise"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# SEKTION 5b: SESSION RECOVERY SCHEMAS (Backup + Recovery)
# ═══════════════════════════════════════════════════════════════════════════════
# 2026-05-08: Fail-Safe gegen Ueberschreiben guter Cookies mit abgelaufenen.
# ═══════════════════════════════════════════════════════════════════════════════


class BackupCreateRequest(BaseModel):
    working_dir: str = Field(default="data", description="Working directory")
    working_filename: str = Field(default="heypiggy-cookies.json", description="Cookie filename in working dir")


class BackupCreateResponse(BaseModel):
    status: str = Field(default="success", description="success or error")
    backed_up: bool = Field(default=False, description="Was backup created?")
    count: int = Field(default=0, description="Number of cookies backed up")
    backup_path: str = Field(default="", description="Path to backup file")
    message: str = Field(default="", description="Human-readable message")


class RecoveryRequest(BaseModel):
    working_dir: str = Field(default="data", description="Working directory to restore into")
    working_filename: str = Field(default="heypiggy-cookies.json", description="Cookie filename in working dir")


class RecoveryResponse(BaseModel):
    status: str = Field(default="success", description="success or error")
    recovered: bool = Field(default=False, description="Was recovery successful?")
    count: int = Field(default=0, description="Number of cookies restored")
    backup_source: str = Field(default="", description="Source backup path")
    restored_to: str = Field(default="", description="Target working path")
    message: str = Field(default="", description="Human-readable message")


# ═══════════════════════════════════════════════════════════════════════════════
# SEKTION 6: UTILITY SCHEMAS (Navigate, Screenshot, Page Content)
# ═══════════════════════════════════════════════════════════════════════════════
# Allgemeine Utility-Endpoints für Browser-Automation.
# Diese sind nicht survey-spezifisch, sondern generische Browser-Tools.
# ═══════════════════════════════════════════════════════════════════════════════


class NavigateRequest(BaseModel):
    """
    Request für POST /tools/navigate.
    
    Navigiert den Browser zu einer URL.
    
    WARUM Utility?
    → Generische Operation: Nicht survey-spezifisch.
    → Kann für Debugging, URL-Wechsel, etc. verwendet werden.
    → Analog zu page.goto() in Playwright.
    
    WARUM wait_until?
    → "load" = warte auf window.onload (schnell, aber evtl. nicht alles geladen).
    → "domcontentloaded" = warte auf DOMContentLoaded (schnell).
    → "networkidle" = warte bis Netzwerk idle ist (langsam, aber alles geladen).
    → "networkidle" ist default weil es die robusteste Option ist.
    """
    # profile_name: Browser-Profil.
    profile_name: str = Field(
        default="default",
        description="Browser profile name"
    )
    
    # url: Ziel-URL.
    # WARUM ... (Required)? Kein Default möglich (wohin navigieren?).
    url: str = Field(
        ...,
        description="URL to navigate to"
    )
    
    # wait_until: Warte-Bedingung.
    wait_until: str = Field(
        default="networkidle",
        description="Playwright load state: 'load', 'domcontentloaded', 'networkidle'"
    )


class NavigateResponse(BaseModel):
    """
    Response für POST /tools/navigate.
    
    Bestätigt Navigation und gibt neuen Seiten-Titel zurück.
    
    WARUM title Optional?
    → Bei manchen Seiten kann der Titel langsam geladen werden.
    → Wenn title=None → Client weiß dass Titel noch nicht verfügbar ist.
    → Nach kurzer Wartezeit kann Client erneut abfragen.
    """
    # status: Ergebnis.
    status: Literal["success", "error"] = Field(
        default="success",
        description="'success' or 'error'"
    )
    
    # profile: Verwendetes Profil.
    profile: str = Field(
        description="Browser profile used"
    )
    
    # url: Tatsächliche URL nach Navigation.
    # WARUM? Bestätigung: Wurde wirklich zu dieser URL navigiert?
    # Manche Seiten redirecten (z.B. http → https).
    url: str = Field(
        description="Final URL after navigation (may differ from request due to redirects)"
    )
    
    # title: Seiten-Titel.
    title: Optional[str] = Field(
        default=None,
        description="Page title after navigation"
    )


class ScreenshotRequest(BaseModel):
    """
    Request für POST /tools/screenshot.
    
    Macht einen Screenshot der aktuellen Seite oder eines Elements.
    
    WICHTIGE FELDER:
    • full_page: True = gesamte Seite, False = nur Viewport.
      WARUM False default? Viewport-Screenshots sind kleiner (schneller),
      full_page kann bei langen Seiten sehr groß sein.
    • selector: CSS-Selector für ein bestimmtes Element.
      None = ganze Seite. "#modal" = nur das Modal.
    
    WARUM base64?
    → JSON kann keine Binär-Daten direkt enthalten.
    → Base64 ist der Standard für Bilder in JSON.
    → Client kann base64 direkt in <img src="data:image/png;base64,..."> verwenden.
    
    WARUM selector Optional?
    → None = ganze Seite (häufigster Use-Case: "Was sehe ich gerade?").
    → Selector = spezifisches Element (z.B. "#error-message" für Fehler-Details).
    """
    # profile_name: Browser-Profil.
    profile_name: str = Field(
        default="default",
        description="Browser profile name"
    )
    
    # full_page: Gesamte Seite?
    full_page: bool = Field(
        default=False,
        description="True = full page screenshot, False = viewport only"
    )
    
    # selector: CSS-Selector für Element-Screenshot.
    # WARUM Optional? None = ganze Seite.
    selector: Optional[str] = Field(
        default=None,
        description="CSS selector to screenshot a specific element. None = full page"
    )


class ScreenshotResponse(BaseModel):
    """
    Response für POST /tools/screenshot.
    
    Screenshot als Base64-kodiertes PNG.
    
    WICHTIGE FELDER:
    • base64_image: Das Bild als Base64-String.
      Kann direkt in HTML eingebettet werden:
      <img src="data:image/png;base64,BASE64_STRING_HERE">
    • mime_type: Bildformat (immer "image/png" aktuell).
      WARUM? Zukunftssicherheit: Könnte auch JPEG, WebP unterstützen.
    
    WARUM base64_image statt URL?
    → Kein Dateisystem-Zugriff nötig (kein /tmp-Datei-Management).
    → Screenshot ist direkt in Response (ein Request = alles).
    → Kein Cleanup nötig (keine temporären Dateien).
    """
    # status: Ergebnis.
    status: Literal["success", "error"] = Field(
        default="success",
        description="'success' or 'error'"
    )
    
    # profile: Verwendetes Profil.
    profile: str = Field(
        description="Browser profile used"
    )
    
    # base64_image: Das Bild.
    base64_image: str = Field(
        description="Screenshot as base64-encoded PNG string"
    )
    
    # mime_type: Format.
    mime_type: str = Field(
        default="image/png",
        description="Image MIME type. Always 'image/png' currently"
    )


class PageContentRequest(BaseModel):
    """
    Request für POST /tools/page-content.
    
    Extrahiert Text/HTML von der aktuellen Seite.
    
    WICHTIGE FELDER:
    • selector: CSS-Selector für ein bestimmtes Element.
      None = gesamte Seite (<body>).
      "#modal" = nur Modal-Inhalt.
    • max_length: Maximale Länge des Textes.
      WARUM 5000? Lange Seiten (Dashboard mit vielen Surveys) können
      10.000+ Zeichen haben. 5000 ist ein Kompromiss:
      - Genug für die meisten Seiten.
      - Nicht zu groß für JSON-Response.
      - Client kann bei Bedarf erneut mit höherem max_length abfragen.
    
    WARUM text UND html_length?
    → text = der extrahierte Text (für Analyse, Keyword-Suche).
    → html_length = Länge des HTML (för Performance-Monitoring).
    → html_length hilft: Wenn plötzlich html_length=0 → Seite leer (Fehler).
    """
    # profile_name: Browser-Profil.
    profile_name: str = Field(
        default="default",
        description="Browser profile name"
    )
    
    # selector: CSS-Selector.
    selector: Optional[str] = Field(
        default=None,
        description="CSS selector to extract specific element. None = entire page"
    )
    
    # max_length: Maximale Text-Länge.
    # WARUM ge=1, le=50000? Mindestens 1 Zeichen, maximal 50000.
    # 50000 ist sehr groß (für extrem lange Seiten).
    # Pydantic validiert: Wenn Client 0 oder 50001 sendet → 422 Error.
    max_length: int = Field(
        default=5000,
        ge=1,
        le=50000,
        description="Max text length to return (1-50000 chars)"
    )


class PageContentResponse(BaseModel):
    """
    Response für POST /tools/page-content.
    
    Extrahierter Inhalt der Seite.
    
    WICHTIGE FELDER:
    • text: Der reine Text (kein HTML).
      Nützlich für Keyword-Suche, Text-Analyse, NLP.
    • html_length: Länge des HTML-Codes.
      Indikator für Seiten-Komplexität.
    • url: Aktuelle URL.
      Bestätigung: Auf welcher Seite sind wir wirklich?
    • title: Seiten-Titel.
    
    WARUM text statt html?
    → HTML ist groß (10x-50x mehr Daten als reiner Text).
    → Für die meisten Use-Cases braucht man nur den Text.
    → Wenn HTML nötig → kann man /tools/screenshot + OCR verwenden.
    → Oder Client ruft page.content() direkt via CDP.
    """
    # status: Ergebnis.
    status: Literal["success", "error"] = Field(
        default="success",
        description="'success' or 'error'"
    )
    
    # profile: Verwendetes Profil.
    profile: str = Field(
        description="Browser profile used"
    )
    
    # url: Aktuelle URL.
    url: str = Field(
        description="Current page URL after extraction"
    )
    
    # title: Seiten-Titel.
    title: str = Field(
        description="Current page title"
    )
    
    # text: Extrahierter Text.
    text: str = Field(
        description="Extracted text content (first max_length chars)"
    )
    
    # html_length: Länge des HTML.
    html_length: int = Field(
        description="Length of full HTML source (for complexity indicator)"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# SEKTION 7: ERROR SCHEMA (Generischer Fehler)
# ═══════════════════════════════════════════════════════════════════════════════
# Einheitliches Fehler-Format für ALLE Endpoints.
# Wird von FastAPI's exception_handler verwendet.
# ═══════════════════════════════════════════════════════════════════════════════


class ErrorResponse(BaseModel):
    """
    Generischer Fehler-Response.
    
    WIRD VERWENDET VON:
    • FastAPI exception_handler → bei unerwarteten Exceptions.
    • Alle Endpoints bei Status="error".
    
    WICHTIGE FELDER:
    • error_code: Maschinen-lesbarer Fehler-Code.
      "internal_error" = unerwarteter Server-Fehler.
      "validation_error" = Client hat ungültige Daten gesendet.
      "timeout_error" = Operation hat zu lange gedauert.
      etc.
    • message: Human-readable Fehlermeldung.
    • details: Zusätzliche technische Details (optional).
      Stack-Trace, Request-ID, etc. (nur im Debug-Modus!).
    
    WARUM error_code String statt Enum?
    → Flexibel: Neue Fehler-Codes können jederzeit hinzugefügt werden.
    → Client kann auf bekannte Codes prüfen ("internal_error").
    → Unbekannte Codes → generische Behandlung.
    
    WARUM details Optional[Dict]?
    → In Produktion: details=None (keine internen Infos leaken).
    → Im Debug-Modus: details=Stack-Trace (hilft beim Debugging).
    → Konfigurierbar über FastAPI-Settings.
    """
    # status: Immer "error".
    # WARUM Literal? Enforced: Kann nicht "success" oder "warning" sein.
    status: Literal["error"] = Field(
        default="error",
        description="Always 'error'"
    )
    
    # error_code: Maschinen-lesbarer Code.
    error_code: str = Field(
        description="Machine-readable error code, e.g. 'internal_error', 'validation_error', 'timeout_error'"
    )
    
    # message: Human-readable Fehlermeldung.
    message: str = Field(
        description="Human-readable error description"
    )
    
    # details: Zusätzliche technische Details.
    # WARUM Optional? Nicht immer verfügbar (sicherheits-/performance-relevant).
    details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional technical details (stack trace, request info). None in production"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# SEKTION 8: WORKFLOW SCHEMAS (Combined Operations)
# ═══════════════════════════════════════════════════════════════════════════════
# High-Level Workflows die mehrere Operationen kombinieren.
# Nützlich für einfache Clients die nicht selbst Session-Check + Scan + Click
# implementieren wollen.
# ═══════════════════════════════════════════════════════════════════════════════


class WorkflowRunBestRequest(BaseModel):
    """
    Request für POST /workflow/run-best.
    
    Führt einen kompletten Workflow aus:
    1. Prüft Session (Cookies).
    2. Injiziert Cookies wenn nötig.
    3. Scannt Dashboard nach Surveys.
    4. Wählt beste Survey (höchster Reward / kürzeste Dauer).
    5. Klickt Survey Card.
    6. Klickt "Umfrage starten".
    
    WARUM Workflow-Endpoint?
    → Einfacher: Ein Call statt 4-5 einzelnen Calls.
    → Robuster: Session-Check + Cookie-Injektion automatisch.
    → Optimiert: Beste Survey wird automatisch ausgewählt.
    
    WARUM max_reward_filter?
    → Client kann sagen "Nur Surveys mit >0.10€ Reward".
    → Filtert niedrig bezahlte Surveys aus (oft sehr lang).
    → Default 0.0 = alle Surveys (kein Filter).
    
    WARUM strategy?
    → "reward": Wähle Survey mit höchstem Reward (default).
    → "efficiency": Wähle Survey mit bestem Reward/Dauer-Verhältnis.
    → "duration": Wähle kürzeste Survey (schnell fertig).
    """
    cdp_port: int = Field(default=9999, description="CDP port for Chrome communication. Stealth-Runner standard: 9999")
    max_reward_filter: float = Field(default=0.0, description="Minimum reward in EUR to consider (0.0 = no filter)")
    strategy: Literal["reward", "efficiency", "duration"] = Field(default="efficiency", description="Survey selection strategy")


class WorkflowRunBestResponse(BaseModel):
    """
    Response für POST /workflow/run-best.
    
    Gibt das Ergebnis des kompletten Workflows zurück.
    
    WARUM so viele Felder?
    → Client sieht EXAKT was passiert ist (Session OK? Survey gefunden? Geklickt?).
    → Debugging: Wenn etwas fehlschlägt → Feld zeigt es an.
    → Statistiken: Balance, Rewards, etc. in einer Response.
    """
    status: Literal["success", "no_surveys", "session_expired", "error"] = Field(description="Overall workflow status")
    session_active: bool = Field(description="Was session active after cookie injection")
    balance_eur: float = Field(default=0.0, description="Current account balance")
    surveys_found: int = Field(default=0, description="Number of surveys found on dashboard")
    survey_selected: Optional[DashboardSurvey] = Field(default=None, description="Selected survey (if any)")
    card_clicked: bool = Field(default=False, description="Was survey card clicked successfully")
    modal_buttons: List[str] = Field(default_factory=list, description="Buttons visible in modal after click")
    message: str = Field(description="Human-readable summary of what happened")
    elapsed_s: float = Field(default=0.0, description="Total workflow execution time in seconds")


# ═══════════════════════════════════════════════════════════════════════════════
# ENDE DER SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════
# ZUSAMMENFASSUNG:
# 
# Diese Datei definiert 30+ Pydantic-Models für ALLE API-Operationen.
# Jedes Model hat:
#   - Klassen-Docstring mit Zweck, Ablauf, wichtige Felder, Entscheidungen.
#   - Field(description=...) für ALLE Felder (erscheint in Swagger UI).
#   - Optional[] für nullable Felder (kein Wert = None).
#   - Literal[] für Enum-Werte (Typsicherheit).
#   - ge/le für numerische Validierung (Range-Checks).
#
# DESIGN-PRINZIPIEN:
#   1. Fail-Closed: Bei Fehlern → ErrorResponse mit klaren Codes.
#   2. Idempotent: Gleicher Request → gleiches Ergebnis (keine Seiteneffekte bei GET).
#   3. Self-Documenting: FastAPI /docs zeigt ALLE Models automatisch an.
#   4. Type-Safe: Pydantic validiert jeden Request vor Code-Ausführung.
#   5. Extensible: Neue Felder können hinzugefügt werden ohne Breaking Changes.
# ═══════════════════════════════════════════════════════════════════════════════
