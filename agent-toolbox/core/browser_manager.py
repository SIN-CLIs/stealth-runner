"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║              STEALTH-RUNNER — Browser Manager (SINator-Style)                ║
║                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ZWECK / PURPOSE:                                                            ║
║  ────────────────                                                            ║
║  Warm-Browser-Singleton der Chrome mit KOPIERTEM User-Profil startet         ║
║  und Playwright via CDP (Chrome DevTools Protocol) verbindet.              ║
║                                                                              ║
║  WAS IST "WARM-BROWSER"?                                                     ║
║  ───────────────────────                                                     ║
║  Ein "warmer" Browser ist ein bereits laufender Chrome-Prozess.              ║
║  Anstatt Chrome bei JEDEM Request neu zu starten (kalt = 5-10s),            ║
║  halten wir Chrome im Hintergrund aktiv.                                   ║
║  Vorteile:                                                                   ║
║    • Schneller: Nächster Request = sofort bereit (kein Startup).           ║
║    • Cookie-Persistenz: Cookies bleiben im Browser erhalten (Session).     ║
║    • Memory-Effizient: Ein Prozess statt Hunderte.                         ║
║                                                                              ║
║  WARUM PROFIL KOPIEREN (NICHT SYMLINK)?                                      ║
║  ─────────────────────────────────────                                       ║
║  Chrome verschlüsselt Cookies mit dem REALEN PFAD als Schlüssel.           ║
║  • Kopieren  → Cookies funktionieren (neuer Pfad = neuer Schlüssel,        ║
║                aber Chrome liest den Pfad aus dem Profil und entschlüsselt). ║
║  • Symlink   → BANNED (siehe banned.md). Der Pfad bleibt derselbe,         ║
║                Chrome denkt es ist derselbe Profil-Pfad → Schlüssel        ║
║                stimmt NICHT überein → Cookies korrupt.                       ║
║  • Frisches Profil → Keine Cookies, keine Session, immer neu einloggen.    ║
║                                                                              ║
║  ARCHITEKTUR-OVERVIEW:                                                       ║
║  ─────────────────────                                                       ║
║  ┌─────────────────────────────────────────────────────────────────────┐    ║
║  │ BrowserManager (Singleton)                                           │    ║
║  │ ├── __init__()         → Konfiguration (Chrome-Pfad, Profil, Port) │    ║
║  │ ├── start()            → Profil kopieren → Chrome starten → CDP    │    ║
║  │ │                       warten → Playwright verbinden → Stealth     │    ║
║  │ ├── get_page()         → Aktive Page zurückgeben (oder neue)       │    ║
║  │ ├── stop()             → Chrome beenden → Temp-Profil löschen    │    ║
║  │ ├── health()           → Status: läuft? idle-seit?                   │    ║
║  │ ├── _copy_profile()    → Profil 73 → /tmp/sinator-chrome-XXXX      │    ║
║  │ ├── _launch_chrome()   → subprocess.Popen mit CDP-Port 9999        │    ║
║  │ ├── _wait_for_cdp()    → Polling auf /json/version (max 15s)       │    ║
║  │ ├── _inject_stealth()  → navigator.webdriver überschreiben         │    ║
║  │ └── _cleanup()         → Alles aufräumen (Browser, Playwright,    │    ║
║  │                         Temp-Profil)                                │    ║
║  └─────────────────────────────────────────────────────────────────────┘    ║
║                                                                              ║
║  SICHERHEIT / BANNED PATTERNS:                                               ║
║  ──────────────────────────────                                              ║
║  • NUR /tmp/sinator-chrome-* oder /tmp/heypiggy-new-* Profile               ║
║    → NIEMALS User-Chrome Profil modifizieren!                                ║
║  • NIEMALS User-Chrome killen (kein pkill -f "Google Chrome")                ║
║    → Nur EIGENE Chrome-Prozesse (mit --user-data-dir=/tmp/...) beenden.    ║
║  • Lock-Files entfernen VOR Start (verhindert "Profile in use" Fehler)     ║
║    → Chrome lockt das Profil beim Start. Wenn abgestürzt → Lock bleibt.    ║
║    → Wir löschen *.lock und Singleton* Dateien vor dem Start.              ║
║  • --remote-allow-origins=* OHNE Quotes (zsh glob expansion!)                ║
║    → subprocess.Popen BYPASSED zsh → kein glob expansion.                  ║
║    → Mit Quotes würde Chrome literal "*" empfangen → 403 Forbidden.        ║
║  • --force-renderer-accessibility MUSS gesetzt sein                         ║
║    → Ohne dieses Flag ist der AX-Tree LEER (CUA-driver sieht nichts).      ║
║                                                                              ║
║  CDP PORT 9999:                                                              ║
║  ──────────────                                                              ║
║  WARUM 9999 statt 9222 (Chrome Default)?                                     ║
║  → 9222 wird oft vom SINator-Chrome belegt (Profile 901).                     ║
║  → 9999 ist der Bot-Chrome-Port für HeyPiggy (Profile 901 Kopie).           ║
║  → Wir verwenden 9999 als isolierten Bot-Chrome-Port.                        ║
║  → Wichtig: API-Server läuft auf 8889 um Konflikt zu vermeiden.             ║
║                                                                              ║
║  PLAYWRIGHT CONNECT_OVER_CDP():                                              ║
║  ──────────────────────────────                                              ║
║  WARUM nicht BrowserType.launch()?                                           ║
║  → BrowserType.launch() startet einen NEUEN Chrome (kein existierendes       ║
║    Profil).                                                                  ║
║  → connect_over_cdp() verbindet mit einem BEREITS LAUFENDEN Chrome.        ║
║    Das ermöglicht:                                                           ║
║    • Verwendung eines kopierten Profils (mit --user-data-dir).               ║
║    • Mehrere Verbindungen zum selben Chrome (Reuse).                       ║
║    • CDP-Features direkt zugänglich (nicht nur Playwright-API).            ║
║                                                                              ║
║  STEALTH-JS INJECTION:                                                       ║
║  ─────────────────────                                                       ║
║  Wir injizieren JavaScript in JEDE neue Page um Bot-Detection zu            ║
║  umgehen:                                                                    ║
║  • navigator.webdriver = undefined (Playwright setzt dies auf true)        ║
║  • navigator.plugins = [1,2,3,4,5] (echte Browser haben Plugins)           ║
║  • navigator.languages = ['de-DE', 'de', 'en-US', 'en'] (Sprach-Profile)   ║
║  • window.chrome = {...} (Chrome-spezifische Objekte)                      ║
║  • Permissions-API override (Notification-Permission)                        ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

# ═══════════════════════════════════════════════════════════════════════════════
# IMPORTS: Was brauchen wir und WARUM?
# ═══════════════════════════════════════════════════════════════════════════════

# os: Betriebssystem-Interaktion.
# WARUM? - os.path.join() für plattform-unabhängige Pfade (Windows vs Linux/Mac).
#        - os.makedirs() für Verzeichnis-Erstellung.
#        - os.path.exists() für Existenz-Prüfung.
#        - os.getenv() für Umgebungsvariablen (optional).
import os

# shutil: Hoch-Level Datei-Operationen.
# WARUM? - shutil.copy2() kopiert Dateien MIT Metadaten (Timestamps, Permissions).
#          Das ist wichtig damit Chrome die Dateien als "gültig" erkennt.
#        - shutil.copytree() kopiert VERZEICHNISSE rekursiv (für Profil-Kopie).
#        - shutil.rmtree() löscht Verzeichnisse rekursiv (für Cleanup).
import shutil

# subprocess: Externe Prozesse starten.
# WARUM? - subprocess.Popen() startet Chrome als eigenständigen Prozess.
#          Wir brauchen Popen (nicht run/call) damit Chrome im Hintergrund läuft.
#        - proc.terminate() sendet SIGTERM (sanftes Beenden).
#        - proc.kill() sendet SIGKILL (hartes Beenden, wenn SIGTERM nicht klappt).
import subprocess

# time: Zeit-Messung und Sleep.
# WARUM? - time.time() für Unix-Timestamps (last_used, Performance-Monitoring).
#        - time.sleep() wird in _wait_for_cdp() NICHT verwendet (asyncio.sleep).
import time

# json: JSON Serialisierung/Deserialisierung.
# WARUM? - urllib.request liest /json/version als JSON.
#        - Wir parsen die Antwort um CDP-Version zu prüfen.
import json

# logging: Log-Ausgaben (nicht print!).
# WARUM? - Logs können in Dateien geschrieben werden (für Debugging).
#        - Log-Level (INFO, WARNING, ERROR) ermöglichen Filterung.
#        - Playwright und andere Libraries verwenden logging (Konsistenz).
import logging

# asyncio: Asynchrone Programmierung.
# WARUM? - Playwright ist async (alle Operationen sind await-basiert).
#        - _wait_for_cdp() verwendet asyncio.sleep() (nicht-blocking).
#        - FastAPI ist async (Endpoints müssen async sein).
import asyncio

# Path: Objekt-orientierte Pfad-Manipulation.
# WARUM? - Plattform-unabhängig: Path("a") / "b" funktioniert auf Windows und Mac.
#        - Elegante Methoden: .exists(), .mkdir(), .rglob(), .touch(), .unlink().
from pathlib import Path

# Typ-Hinweise für bessere Code-Klarheit und IDE-Unterstützung.
# Optional: Ein Wert ODER None (z.B. Browser kann None sein wenn nicht gestartet).
# Dict, Any: Für flexible Dictionary-Typen (health() Rückgabe).
from typing import Optional, Dict, Any

# Typ-Hinweise fuer Proxy-Unterstuetzung (SR-151)
# TYPE_CHECKING: Import nur fuer Type-Hints (nicht zur Laufzeit).
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .network.proxy_pool import ProxyEntry

# Playwright: Browser-Automation Library.
# async_playwright: Async-Kontext-Manager für Playwright.
# Browser: Playwright Browser-Instanz (verbunden via CDP).
# BrowserContext: Ein Browser-Kontext (Profil, Cookies, LocalStorage).
# Page: Einzelne Browser-Tab/Seite.
# WARUM Playwright? - CDP-basiert (kein Selenium-WebDriver overhead).
#                   - Native async Unterstützung (kein Threading nötig).
#                   - Moderne API (autowaiting, locators, etc.).
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

# Logger-Instanz für diese Datei.
# WARUM __name__? - Der Logger-Name enthält den Modul-Pfad ("core.browser_manager").
#                   - Ermöglicht gezieltes Logging-Level pro Modul.
#                   - Wenn wir logging.getLogger("core.browser_manager").setLevel(DEBUG)
#                     setzen → nur dieses Modul loggt Debug-Infos.
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# KLASSE: BrowserManager
# ═══════════════════════════════════════════════════════════════════════════════
# Der BrowserManager ist ein SINGLETON — es gibt NUR EINE Instanz pro Prozess.
# WARUM Singleton?
# → Ein Chrome-Prozess verbraucht ~200-500MB RAM.
# → Mehrere Chrome-Prozesse = Memory-Leak und Port-Konflikte.
# → Singleton stellt sicher: Maximal EIN Chrome läuft gleichzeitig.
# → Wiederverwendung: Wenn Chrome bereits läuft → verwende ihn (warm start).
#
# WARUM keine @singleton Decorator?
# → Explizites Singleton-Muster (global Variable _browser_manager).
# → Klarer: Man sieht SOFORT dass es ein Singleton ist.
# → Flexibler: Man kann mehrere BrowserManager-Instanzen für Tests erstellen.
#   (Der get_browser_manager() ist der Singleton-Getter).
# ═══════════════════════════════════════════════════════════════════════════════


class BrowserManager:
    """
    Warm-Browser-Singleton mit Chrome-Profil-Kopie (SINator-Style).
    
    Hält eine Browser-Instanz im Hintergrund und vermeidet teure Neustarts.
    Das Profil wird beim ERSTEN Start KOPIERT (nicht verlinkt) und
    wiederverwendet bis stop() aufgerufen wird.
    
    LEBENSZYKLUS:
    1. Instanziierung: __init__() → Konfiguration speichern (kein Chrome starten).
    2. Start: start() → Profil kopieren, Chrome starten, Playwright verbinden.
    3. Nutzung: get_page() → Page-Objekt für Automation.
    4. Wiederverwendung: start() erneut → Warm-Start (kein Neustart).
    5. Stop: stop() → Chrome beenden, Playwright stoppen, Temp-Profil löschen.
    
    THREAD-SAFETY / ASYNC-SAFETY:
    - BrowserManager ist NICHT Thread-Safe (keine Locks).
    - In FastAPI (Single-Threaded Async) ist das kein Problem.
    - Wenn mehrere Threads verwendet werden → Lock um start()/stop() hinzufügen.
    
    ATTRIBUTES (öffentlich):
    - chrome_path: Pfad zur Chrome Binary (z.B. "/Applications/Google Chrome.app/...").
    - profile_name: Name des Profil-Ordners (z.B. "Profile 901 (Jeremy)").
    - cdp_port: Port für Chrome DevTools Protocol (default: 9999).
    - headless: Sichtbarer oder unsichtbarer Modus (default: False für Debugging).
    
    ATTRIBUTES (privat — beginnen mit _):
    - _playwright: Playwright-Instanz (async_playwright().start()).
    - _browser: Playwright Browser-Instanz (connect_over_cdp()).
    - _context: Playwright BrowserContext (erster Context des Browsers).
    - _temp_profile_dir: Pfad zum temporären Profil-Verzeichnis (/tmp/sinator-chrome-XXXX).
    - _chrome_proc: subprocess.Popen-Objekt des Chrome-Prozesses.
    - _is_running: Bool-Flag ob Chrome aktiv ist (inklusive externe Instanzen).
    - _last_used: Unix-Timestamp der letzten Nutzung (für Health-Check).
    
    Usage:
        manager = BrowserManager()  # ODER get_browser_manager() für Singleton
        await manager.start()       # Chrome starten (oder wiederverwenden)
        page = await manager.get_page()  # Page-Objekt holen
        await page.goto("https://...")   # Automation
        await manager.stop()        # Aufräumen
    """
    
    def __init__(
        self,
        chrome_path: Optional[str] = None,
        proxy: Optional["ProxyEntry"] = None,
        source_profile: Optional[str] = None,
        profile_name: str = "Profile 901 (Jeremy)",
        cdp_port: int = 9999,
        headless: bool = False,
    ):
        """
        Initialisiert den Browser-Manager (startet NOCH KEINEN Chrome!).
        
        Dieser Konstruktor speichert NUR die Konfiguration.
        Chrome wird erst bei start() gestartet (Lazy-Start).
        
        WARUM Lazy-Start?
        → FastAPI startet schneller wenn Chrome nicht sofort gestartet wird.
        → Client entscheidet WANN Chrome starten (z.B. erst bei erstem Request).
        → Ressourcen-Schonung: Wenn API läuft aber nie Browser-Endpoints
          aufgerufen werden → kein Chrome nötig.
        
        Args:
            chrome_path: Pfad zur Chrome Binary.
                Default: macOS Standard-Pfad.
                WARUM macOS? Weil das Projekt primär auf macOS entwickelt wird.
                Für Linux: "/usr/bin/google-chrome" oder "/usr/bin/chromium".
                Für Windows: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe".
            source_profile: Pfad zum Chrome user-data-dir (Quelle für Profil-Kopie).
                Default: macOS Standard-Pfad unter ~/Library/Application Support/.
                WARUM? Chrome speichert Profile standardmäßig dort.
                Wir kopieren von dort nach /tmp/.
            profile_name: Name des Profil-Ordners INNERHALB des user-data-dir.
                Default: "Profile 901 (Jeremy)".
                WARUM "Profile 901 (Jeremy)"? Das ist das Profil mit der HeyPiggy-Session.
            cdp_port: Port für Chrome DevTools Protocol.
                Default: 9999.
                WARUM 9999? Siehe Modul-Docstring (nicht 9222 wegen SINator-Chrome Konflikt).
            headless: Headless-Modus.
                Default: False.
                WARUM False? Sichtbarer Browser ist einfacher zu debuggen.
                Für Produktion (Docker, Server) → True setzen.
                ABER: CUA (macOS Accessibility) erfordert sichtbaren Browser!
                → Wenn Google OAuth Login geplant ist → headless=False.
        
        Returns:
            BrowserManager-Instanz (nicht gestartet).
        
        Example:
            manager = BrowserManager(
                profile_name="Profile 901 (Jeremy)",
                cdp_port=9999,
                headless=False
            )
            # Chrome läuft NOCH NICHT!
        """
        # ═══════════════════════════════════════════════════════════════════════
        # KONFIGURATION (öffentliche Attribute)
        # ═══════════════════════════════════════════════════════════════════════
        
        # chrome_path: Pfad zur Chrome Binary.
        # WARUM "or" Operator? Wenn None → verwende Default-Pfad.
        # macOS-Pfad: /Applications/Google Chrome.app/Contents/MacOS/Google Chrome
        # Hinweis: Leerzeichen im Pfad sind OK (wird von subprocess.Popen korrekt gehandhabt).
        self.chrome_path = chrome_path or "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        
        # source_user_data_dir: Pfad zum Chrome user-data-dir.
        # WARUM Path.home()? Gibt das Home-Verzeichnis des aktuellen Users zurück.
        # ~/Library/Application Support/Google/Chrome = macOS Standard.
        # Hinweis: Path("~/...") funktioniert NICHT ohne expanduser()!
        self.source_user_data_dir = source_profile or str(
            Path.home() / "Library/Application Support/Google/Chrome"
        )
        
        # profile_name: Name des Profil-Ordners.
        # WARUM String? Chrome verwendet Ordner-Namen wie "Profile 901 (Jeremy)".
        # Der Ordner liegt INNERHALB von user-data-dir/.
        self.profile_name = profile_name
        
        # cdp_port: CDP Port.
        # WARUM int? Port ist eine Integer-Zahl (0-65535).
        # 9999 ist ein High-Port (kein Root-Rechte nötig).
        self.cdp_port = cdp_port
        
        # headless: Sichtbar oder unsichtbar.
        # WARUM bool? Einfache Ja/Nein-Entscheidung.
        # False = sichtbar (empfohlen für Debugging und CUA).
        # True = unsichtbar (schneller, weniger Ressourcen).
        self.headless = headless

        # ═══════════════════════════════════════════════════════════════════════
        # PROXY SUPPORT (SR-151)
        # ═══════════════════════════════════════════════════════════════════════
        
        # proxy: Optional ProxyEntry fuer Proxy-Server Support.
        # WARUM? Anti-Detection Layer 3 (Network). Datacenter IPs werden geblockt.
        # Wenn gesetzt → Chrome startet mit --proxy-server Flag.
        # Format: "http://user:pass@host:port" oder "socks5://..."
        self.proxy: Optional["ProxyEntry"] = proxy
        
        # ═══════════════════════════════════════════════════════════════════════
        # ZUSTAND (private Attribute — beginnen mit _)
        # ═══════════════════════════════════════════════════════════════════════
        
        # _playwright: Playwright-Instanz.
        # WARUM Optional? Wird erst bei start() erstellt (Lazy).
        # async_playwright().start() gibt ein Playwright-Objekt zurück.
        self._playwright: Optional[async_playwright] = None
        
        # _browser: Playwright Browser-Instanz.
        # WARUM Optional? Wird erst bei start() verbunden (connect_over_cdp).
        # Browser repräsentiert die Verbindung zum laufenden Chrome.
        self._browser: Optional[Browser] = None
        
        # _context: Playwright BrowserContext.
        # WARUM Optional? Wird aus _browser.contexts[0] geholt (Lazy).
        # Context = Profil + Cookies + LocalStorage + Permissions.
        self._context: Optional[BrowserContext] = None
        
        # _temp_profile_dir: Pfad zum temporären Profil-Verzeichnis.
        # WARUM Optional? Wird erst bei _copy_profile() erstellt.
        # Format: /tmp/sinator-chrome-{timestamp}
        # WARUM /tmp? - Wird beim Neustart automatisch geleert (macOS/Linux).
        #              - Schnelles Dateisystem (oft tmpfs/RAM-Disk).
        #              - Keine Berechtigungs-Probleme (world-writable).
        self._temp_profile_dir: Optional[str] = None
        
        # _chrome_proc: subprocess.Popen-Objekt.
        # WARUM Optional? Wird erst bei _launch_chrome() erstellt.
        # Popen repräsentiert den laufenden Chrome-Prozess.
        # proc.poll() → None = läuft, sonst = Exit-Code.
        self._chrome_proc: Optional[subprocess.Popen] = None
        
        # _is_running: Flag ob Chrome aktiv ist.
        # WARUM Bool? Schnelle Prüfung ohne System-Calls.
        # True wenn: _browser ist nicht None ODER CDP erreichbar.
        # False wenn: Nichts läuft.
        self._is_running: bool = False
        
        # _last_used: Unix-Timestamp der letzten Nutzung.
        # WARUM float? time.time() gibt float (Sekunden mit Mikrosekunden).
        # 0.0 = noch nie verwendet (Chrome nie gestartet).
        # Wird bei jedem get_page() und start() aktualisiert.
        self._last_used: float = 0.0
    
    # ═══════════════════════════════════════════════════════════════════════════
    # METHODE: set_proxy (SR-151)
    # ═══════════════════════════════════════════════════════════════════════════
    
    def set_proxy(self, proxy: Optional["ProxyEntry"]) -> None:
        """
        Setzt den Proxy fuer den naechsten Browser-Start.
        
        WICHTIG: Dieser Proxy wird erst beim NAECHSTEN start() verwendet!
        Wenn Chrome bereits laeuft, muss stop() + start() aufgerufen werden.
        
        Args:
            proxy: ProxyEntry Objekt oder None fuer direkten Zugang.
            
        Example:
            from agent_toolbox.core.network import get_proxy_pool
            pool = get_proxy_pool()
            proxy = pool.pick(persona={"country": "DE"})
            manager.set_proxy(proxy)
            await manager.stop()
            await manager.start()  # Startet mit neuem Proxy
        """
        self.proxy = proxy
        if proxy:
            logger.info(f"Proxy gesetzt: {proxy.label} ({proxy.country})")
        else:
            logger.info("Proxy deaktiviert (direkter Zugang)")
    
        # ═══════════════════════════════════════════════════════════════════════════
    # EIGENSCHAFT (Property): is_running
    # ═══════════════════════════════════════════════════════════════════════════
    
    @property
    def is_running(self) -> bool:
        """
        Prüft ob Chrome aktiv ist.
        
        PRÜFUNG IN REIHENFOLGE:
        1. Wenn _is_running=True UND _browser ist nicht None → True.
           (Playwright ist verbunden → Chrome läuft definitiv).
        2. Sonst: Prüfe ob CDP-Port erreichbar ist (_check_cdp_alive).
           (Chrome könnte laufen aber Playwright nicht verbunden sein).
        
        WARUM zwei Prüfungen?
        → Playwright-Verbindung ist der zuverlässigste Indikator.
        → CDP-Port-Check ist Fallback (wenn Playwright disconnected ist).
        → Kombination = robust: Auch wenn Playwright crasht erkennen wir Chrome.
        
        WARUM Property statt Methode?
        → Eigenschaft (keine Klammern) → liest sich wie ein Attribut.
        → is_running ist ein ZUSTAND, keine Aktion.
        → Konsistent mit anderen Attributen (headless, cdp_port).
        
        Returns:
            True wenn Chrome läuft (Playwright verbunden ODER CDP erreichbar).
            False wenn Chrome nicht läuft.
        
        Example:
            if manager.is_running:
                print("Chrome läuft bereits")
            else:
                await manager.start()
        """
        # Prüfung 1: Playwright ist verbunden.
        # Wenn _browser nicht None ist → Chrome läuft definitiv.
        if self._is_running and self._browser is not None:
            return True
        
        # Prüfung 2: Fallback — CDP-Port erreichbar?
        # Wenn Chrome läuft aber Playwright disconnected ist.
        return self._check_cdp_alive()
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PRIVATE METHODE: _check_cdp_alive
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _check_cdp_alive(self) -> bool:
        """
        Prüft ob Chrome auf dem CDP-Port erreichbar ist.
        
        ABLAUF:
        1. HTTP GET auf http://127.0.0.1:{cdp_port}/json/version.
        2. Wenn erfolgreich (HTTP 200) → Chrome läuft.
        3. Wenn Fehler (ConnectionRefused, Timeout, etc.) → Chrome läuft nicht.
        
        WARUM /json/version?
        → CDP HTTP API Endpunkt der Chrome-Version zurückgibt.
        → Leichter als WebSocket-Verbindung aufbauen (kein Handshake).
        → Schnell: Keine großen Daten, nur ein kleines JSON.
        
        WARUM timeout=1s?
        → Wenn Chrome nicht läuft → ConnectionRefused sofort (wenige ms).
        → Wenn Chrome läuft aber langsam → 1s ist ausreichend.
        → Wir wollen nicht lange warten (Health-Check soll schnell sein).
        
        WARUM urllib.request statt requests/aiohttp?
        → Keine External Dependencies (urllib ist in Standard-Library).
        → Einfach und synchron (Health-Check muss nicht async sein).
        → Für ein einfaches HTTP GET ist urllib ausreichend.
        
        Returns:
            True wenn CDP erreichbar (Chrome läuft).
            False wenn CDP nicht erreichbar (Chrome nicht läuft).
        
        Example:
            alive = self._check_cdp_alive()
            # True → Chrome auf Port 9999 erreichbar.
            # False → Kein Chrome auf Port 9999.
        """
        try:
            # Importiere urllib.request lokal (wird selten gebraucht).
            import urllib.request
            
            # HTTP GET auf /json/version (CDP HTTP API).
            # WARUM f-string? Dynamische Port-Nummer einfügen.
            # WARUM timeout=1? Schneller Check, kein langes Warten.
            urllib.request.urlopen(
                f"http://127.0.0.1:{self.cdp_port}/json/version",
                timeout=1
            )
            
            # Wenn kein Exception → Chrome ist erreichbar.
            return True
        
        except Exception:
            # Jeglicher Fehler = Chrome nicht erreichbar.
            # Mögliche Fehler:
            # - ConnectionRefusedError: Kein Prozess auf diesem Port.
            # - TimeoutError: Prozess antwortet nicht (hängt/abgestürzt).
            # - urllib.error.URLError: Netzwerk-Fehler.
            # Wir fangen ALLE Exceptions (fail-closed).
            return False
    
    # ═══════════════════════════════════════════════════════════════════════════
    # ÖFFENTLICHE METHODE: start
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def start(self, profile_name=None, headless=None, cdp_port=None) -> BrowserContext:
        """
        Startet Chrome mit kopiertem Profil und verbindet Playwright via CDP.
        
        ABLAUF:
        1. Konfiguration aktualisieren (Runtime-Overrides).
        2. Wenn Chrome bereits läuft (warm) → gib bestehenden Context zurück.
        3. Wenn CDP erreichbar aber Playwright nicht verbunden → verbinde Playwright.
        4. Wenn Chrome nicht läuft (cold):
           a. Profil kopieren (_copy_profile).
           b. Chrome starten (_launch_chrome).
           c. Auf CDP warten (_wait_for_cdp).
           d. Playwright verbinden (connect_over_cdp).
           e. Stealth-JS injizieren (_inject_stealth).
        5. _is_running = True, _last_used = time.time().
        6. Gib BrowserContext zurück.
        
        WARUM Runtime-Overrides (profile_name, headless, cdp_port)?
        → Client kann Parameter bei JEDEM Aufruf ändern (nicht nur bei __init__).
        → Beispiel: Erster Aufruf mit headless=False (Debugging),
        → zweiter Aufruf mit headless=True (Schnelligkeit).
        → Wenn Parameter None → verwende gespeicherte Werte (kein Override).
        
        WARUM warm vs cold?
        → Warm: Chrome läuft bereits → nur Context zurückgeben (~0ms).
        → Cold: Chrome muss gestartet werden → ~2-5s.
        → Performance-Kritisch: Survey-Automation macht viele Requests.
        
        WARUM _check_cdp_alive Fallback?
        → Chrome könnte extern gestartet worden sein (nicht von uns).
        → Beispiel: User hat Chrome manuell mit --remote-debugging-port=9999 gestartet.
        → Wir verbinden Playwright mit diesem Chrome (wiederverwenden).
        
        Args:
            profile_name: Profil-Name (Override, None = verwende gespeicherten).
            headless: Headless-Modus (Override, None = verwende gespeicherten).
            cdp_port: CDP-Port (Override, None = verwende gespeicherten).
        
        Returns:
            BrowserContext: Playwright BrowserContext für Automation.
            Enthält: Cookies, LocalStorage, Permissions, Pages.
        
        Raises:
            TimeoutError: Wenn CDP nicht innerhalb von 15s erreichbar ist.
            FileNotFoundError: Wenn Profil nicht gefunden wird.
            RuntimeError: Wenn Playwright nicht installiert ist.
        
        Example:
            ctx = await manager.start()
            page = ctx.pages[0]  # Erster Tab
            await page.goto("https://www.heypiggy.com")
        """
        # ═══════════════════════════════════════════════════════════════════════
        # SCHRITT 1: Konfiguration aktualisieren (Runtime-Overrides)
        # ═══════════════════════════════════════════════════════════════════════
        
        # Wenn Client einen neuen Profil-Namen angibt → aktualisieren.
        # WARUM? Ermöglicht Profil-Wechsel ohne neue Instanz zu erstellen.
        if profile_name:
            self.profile_name = profile_name
        
        # Wenn Client headless ändert → aktualisieren.
        # WARUM? Ermöglicht sichtbar→unsichtbar Wechsel.
        if headless is not None:
            self.headless = headless

        # ═══════════════════════════════════════════════════════════════════════
        # Wenn Client CDP-Port ändert → aktualisieren.
        # WARNUNG: Wenn Chrome bereits auf altem Port läuft → Konflikt!
        # Der Client muss sicherstellen dass alter Chrome beendet wurde.
        if cdp_port:
            self.cdp_port = cdp_port
        
        # ═══════════════════════════════════════════════════════════════════════
        # SCHRITT 2: Warm-Start Prüfung
        # ═══════════════════════════════════════════════════════════════════════
        
        # Wenn Chrome läuft UND Playwright verbunden ist → warm start.
        # _is_running = True → Chrome wurde von uns gestartet ODER verbindet.
        # _context ist nicht None → Playwright ist verbunden und Context verfügbar.
        if self._is_running and self._context is not None:
            # Logge Warm-Start (nützlich für Performance-Monitoring).
            logger.info("Browser läuft bereits, verwende bestehende Instanz")
            
            # Aktualisiere last_used Timestamp (für Health-Check idle_seconds).
            self._last_used = time.time()
            
            # Gib bestehenden Context zurück.
            return self._context
        
        # ═══════════════════════════════════════════════════════════════════════
        # SCHRITT 3: Fallback — CDP erreichbar aber Playwright nicht verbunden?
        # ═══════════════════════════════════════════════════════════════════════
        
        # Prüfe ob Chrome extern läuft (nicht von uns gestartet).
        # Wenn ja → verbinde Playwright (kein Neustart nötig).
        if self._check_cdp_alive() and not self._is_running:
            logger.info("Chrome läuft bereits (CDP erreichbar), verbinde Playwright...")
            
            try:
                # Starte Playwright (async Kontext-Manager).
                # async_playwright().start() gibt eine Playwright-Instanz zurück.
                self._playwright = await async_playwright().start()
                
                # Verbinde mit laufendem Chrome via CDP.
                # connect_over_cdp() erwartet: "http://host:port" (kein /json!).
                # WARUM http://? Playwright spricht CDP HTTP API (nicht WebSocket).
                self._browser = await self._playwright.chromium.connect_over_cdp(
                    f"http://127.0.0.1:{self.cdp_port}"
                )
                
                # Hole den ersten Context (oder erstelle einen neuen).
                # Browser.contexts ist eine Liste aller Contexte.
                # Wenn Chrome frisch gestartet wurde → contexts[0] existiert.
                # Wenn Chrome ohne Playwright gestartet wurde → evtl. leer.
                self._context = (
                    self._browser.contexts[0]
                    if self._browser.contexts
                    else await self._browser.new_context()
                )
                
                # Markiere als laufend.
                self._is_running = True
                self._last_used = time.time()
                
                # Injiziere Stealth-JS (Bot-Detection-Umgehung).
                await self._inject_stealth()
                
                logger.info("Mit bestehendem Chrome verbunden")
                return self._context
            
            except Exception as e:
                # Verbindung fehlgeschlagen → Chrome ist evtl. nicht kompatibel.
                # Logge Warnung und fahre mit Neustart fort.
                logger.warning(f"Verbindung zu bestehendem Chrome fehlgeschlagen: {e}")
                # Weiter mit Neustart (nicht return, sondern nächster Block).
        
        # ═══════════════════════════════════════════════════════════════════════
        # SCHRITT 4: Cold-Start (Chrome muss neu gestartet werden)
        # ═══════════════════════════════════════════════════════════════════════
        
        logger.info("Starte Browser mit Profil-Kopie...")
        
        # Zeit-Messung für Performance-Monitoring.
        # WARUM start_time? Wir wissen wissen wie lange der Start dauert.
        # Bei >10s → möglicherweise Problem (langsames Dateisystem, etc.).
        start_time = time.time()
        
        try:
            # ── Phase 4a: Profil kopieren ──
            # Kopiere Chrome-Profil in temporäres Verzeichnis.
            # WARUM? Siehe Modul-Docstring: Cookies funktionieren nur mit Kopie.
            self._temp_profile_dir = self._copy_profile()
            
            # ── Phase 4b: Chrome starten ──
            # Starte Chrome als subprocess mit CDP-Port und Flags.
            self._chrome_proc = self._launch_chrome()
            
            # ── Phase 4c: Auf CDP warten ──
            # Polling-Loop: Prüfe alle 1s ob CDP erreichbar ist.
            # Max 15 Versuche = max 15s Wartezeit.
            await self._wait_for_cdp(max_retries=15)
            
            # ── Phase 4d: Playwright verbinden ──
            # Starte Playwright und verbinde mit Chrome.
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.connect_over_cdp(
                f"http://127.0.0.1:{self.cdp_port}"
            )
            
            # Hole ersten Context (oder erstelle neuen).
            self._context = (
                self._browser.contexts[0]
                if self._browser.contexts
                else await self._browser.new_context()
            )
            
            # ── Phase 4e: Stealth-JS injizieren ──
            # Überschreibe navigator.webdriver und andere Bot-Detection-Properties.
            await self._inject_stealth()
            
            # Markiere als laufend.
            self._is_running = True
            self._last_used = time.time()
            
            # Berechne verstrichene Zeit.
            elapsed = time.time() - start_time
            logger.info(f"Browser gestartet in {elapsed:.2f}s")
            
            return self._context
        
        except Exception as e:
            # Fehler beim Starten → räume auf und gebe Fehler weiter.
            logger.error(f"Browser-Start fehlgeschlagen: {e}")
            
            # Aufräumen: Browser beenden, Temp-Profil löschen, etc.
            await self._cleanup()
            
            # Fehler weitergeben (Client bekommt Exception).
            raise
    
    # ═══════════════════════════════════════════════════════════════════════════
    # ÖFFENTLICHE METHODE: get_page
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def get_page(self) -> Page:
        """
        Liefert eine Playwright Page für Automation.
        
        ABLAUF:
        1. Wenn Chrome nicht läuft → starte Chrome (start()).
        2. Wenn Chrome läuft aber Playwright nicht verbunden → verbinde Playwright.
        3. Aktualisiere _last_used Timestamp.
        4. Wenn Context Pages hat → gib erste Page zurück.
        5. Sonst → erstelle neue Page (neuer Tab).
        
        WARUM start() in get_page()?
        → Convenience: Client muss nicht explizit start() aufrufen.
        → get_page() ist der HAUPTEINSTIEGSPUNKT für Automation.
        → "Just give me a page" — der Rest passiert automatisch.
        
        WARUM Playwright-Reconnect in get_page()?
        → Playwright könnte disconnected sein (Netzwerk, Timeout, etc.).
        → Chrome läuft aber Playwright-Verbindung ist tot.
        → Wir reconnecten automatisch (transparent für Client).
        
        WARUM erste Page?
        → Chrome startet mit einer Page (about:blank oder Start-URL).
        → Die meisten Use-Cases brauchen nur EINEN Tab.
        → Wenn mehrere Tabs nötig → ctx.new_page() manuell aufrufen.
        
        Returns:
            Page: Playwright Page-Objekt für Automation.
            Methoden: goto(), click(), fill(), screenshot(), etc.
        
        Raises:
            RuntimeError: Wenn Chrome nicht gestartet werden kann.
        
        Example:
            page = await manager.get_page()
            await page.goto("https://www.heypiggy.com")
            await page.click("#login-button")
        """
        # Prüfe ob Chrome läuft.
        # WARUM nicht if self._is_running? Weil _is_running nicht zuverlässig ist
        # wenn Chrome extern gestartet wurde.
        if not self.is_running:
            # Chrome läuft nicht → starte.
            # await ist wichtig: start() ist async.
            await self.start()
        
        # Prüfe ob Playwright verbunden ist (Context ist None).
        # Das kann passieren wenn Chrome läuft aber Playwright disconnected ist.
        elif self._context is None and self._check_cdp_alive():
            # Chrome läuft, aber Playwright nicht verbunden → reconnect.
            logger.info("CDP erreichbar, verbinde Playwright...")
            
            # Starte Playwright.
            self._playwright = await async_playwright().start()
            
            # Verbinde mit Chrome.
            self._browser = await self._playwright.chromium.connect_over_cdp(
                f"http://127.0.0.1:{self.cdp_port}"
            )
            
            # Hole oder erstelle Context.
            self._context = (
                self._browser.contexts[0]
                if self._browser.contexts
                else await self._browser.new_context()
            )
            
            # Markiere als laufend.
            self._is_running = True
            
            # Injiziere Stealth-JS (wichtig nach Reconnect!).
            await self._inject_stealth()
        
        # Aktualisiere last_used (Performance-Monitoring).
        self._last_used = time.time()
        
        # Hole alle Pages (Tabs) im Context.
        pages = self._context.pages
        
        # Wenn Pages vorhanden → gib erste zurück.
        # WARUM erste? Chrome startet mit einer Page (about:blank).
        # Die meisten Use-Cases verwenden nur einen Tab.
        if pages:
            return pages[0]
        
        # Keine Pages → erstelle neue (neuer Tab).
        # Selten: Wenn Chrome frisch gestartet und Page geschlossen wurde.
        return await self._context.new_page()
    
    # ═══════════════════════════════════════════════════════════════════════════
    # ÖFFENTLICHE METHODE: stop
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def stop(self) -> Dict[str, Any]:
        """
        Beendet Chrome und räumt das temporäre Profil auf.
        
        ABLAUF:
        1. Prüfe ob Chrome läuft (is_running).
        2. Wenn nicht → gib {"status": "not_running"} zurück (idempotent).
        3. Rufe _cleanup() auf (beendet Browser, Playwright, Chrome, Temp-Profil).
        4. Gib Erfolgs-Response zurück.
        
        WARUM idempotent?
        → Mehrfaches Aufrufen ist OK (kein Fehler).
        → Wenn Chrome bereits beendet → "not_running".
        → Wichtig für robuste Clients: Können stop() mehrfach aufrufen.
        
        WARUM async?
        → Playwright close/stop sind async.
        → _cleanup() ist async.
        → Ohne await → Race Condition.
        
        WARUM nicht einfach proc.kill()?
        → _cleanup() macht MEHR als nur proc.kill():
        - Browser.close() (graceful, speichert State).
        - playwright.stop() (beendet Playwright-Prozess).
        - proc.terminate() → proc.kill() (hartes Beenden wenn nötig).
        - shutil.rmtree() (löscht Temp-Profil).
        - State zurücksetzen (_is_running = False, etc.).
        
        Returns:
            Dict mit status und cleanup_info.
            {"status": "stopped", "temp_profile_cleaned": "/tmp/sinator-chrome-..."}
            oder {"status": "not_running"}.
        
        Example:
            result = await manager.stop()
            # result = {"status": "stopped", "temp_profile_cleaned": "/tmp/..."}
        """
        # Prüfe ob Chrome läuft.
        if not self.is_running:
            # Chrome läuft nicht → idempotent, kein Fehler.
            return {"status": "not_running"}
        
        # Logge Beendigung.
        logger.info("Beende Browser & räume auf...")
        
        # Räume auf (beendet alles und löscht Temp-Profil).
        await self._cleanup()
        
        # Erfolgs-Response.
        return {
            "status": "stopped",
            "temp_profile_cleaned": self._temp_profile_dir,
        }
    
    # ═══════════════════════════════════════════════════════════════════════════
    # ÖFFENTLICHE METHODE: health
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def health(self) -> dict:
        """
        Gibt den aktuellen Zustand des Browsers zurück.
        
        PRÜFUNG:
        1. _check_cdp_alive(): Ist CDP-Port erreichbar?
        2. Kombiniere mit Playwright-Zustand (_browser, _context).
        3. Berechne idle_seconds = time.time() - _last_used.
        
        WICHTIGE FELDER:
        • running: True wenn Chrome aktiv (Playwright verbunden ODER CDP erreichbar).
        • profile: Aktives Profil (z.B. "Profile 901 (Jeremy)").
        • last_used: Unix-Timestamp der letzten Nutzung.
        • idle_seconds: Sekunden seit letzter Nutzung.
          > 300s (5min) → könnte Memory-Leak haben, Neustart empfohlen.
        • cdp_port: Aktueller CDP-Port.
        • cdp_reachable: True wenn CDP-Port erreichbar (auch ohne Playwright).
        
        WARUM cdp_reachable separat?
        → cdp_reachable=True, running=False → Chrome läuft aber Playwright disconnected.
        → Client sollte get_page() aufrufen (reconnectet automatisch).
        → cdp_reachable=False, running=False → Chrome tot, start() nötig.
        
        Returns:
            Dict mit Health-Informationen.
        
        Example:
            health = await manager.health()
            # health = {
            #   "running": True,
            #   "profile": "Profile 901 (Jeremy)",
            #   "last_used": 1778261390.45,
            #   "idle_seconds": 45.2,
            #   "cdp_port": 9999,
            #   "cdp_reachable": True,
            # }
        """
        # Prüfe CDP-Erreichbarkeit (unabhängig von Playwright).
        cdp_alive = self._check_cdp_alive()
        
        # Berechne idle_seconds (wenn last_used > 0).
        # WARUM if self._last_used else None? Wenn Chrome nie gestartet wurde
        # → idle_seconds ist nicht sinnvoll (None).
        idle_seconds = time.time() - self._last_used if self._last_used else None
        
        return {
            # running: Chrome aktiv?
            # True wenn Playwright verbunden ODER CDP erreichbar.
            "running": (self._browser is not None and self._context is not None) or cdp_alive,
            
            # profile: Aktives Profil.
            "profile": self.profile_name,
            
            # last_used: Unix-Timestamp.
            "last_used": self._last_used,
            
            # idle_seconds: Sekunden seit letzter Nutzung.
            "idle_seconds": idle_seconds,
            
            # cdp_port: Aktueller Port.
            "cdp_port": self.cdp_port,
            
            # cdp_reachable: CDP unabhängig erreichbar?
            "cdp_reachable": cdp_alive,
        }
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PRIVATE METHODE: _copy_profile
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _copy_profile(self) -> str:
        """
        Kopiert Chrome-Profil in ein temporäres Verzeichnis.
        
        ABLAUF:
        1. Erstelle temporäres Verzeichnis: /tmp/sinator-chrome-{timestamp}.
        2. Kopiere "Local State" Datei (Metadaten, Profil-Liste).
        3. Kopiere "Last Version" Datei (optional, Chrome Versions-Info).
        4. Kopiere Profil-Ordner rekursiv (z.B. "Profile 901 (Jeremy)").
        5. Erstelle "First Run" Datei (verhindert Welcome-Dialog).
        6. Lösche Lock-Dateien (*.lock, Singleton*) → verhindert "Profile in use".
        
        WARUM /tmp/sinator-chrome-{timestamp}?
        → /tmp/ wird beim System-Neustart automatisch geleert (Cleanup).
        → timestamp macht jeden Start eindeutig (keine Konflikte).
        → "sinator-chrome-" als Präfix → eindeutig identifizierbar.
        
        WARUM "Local State" kopieren?
        → Enthält die Profil-Liste (welche Profile existieren).
        → Chrome liest "Local State" um zu wissen welches Profil zu laden.
        → Ohne "Local State" → Chrome erkennt das Profil nicht.
        
        WARUM Lock-Dateien löschen?
        → Chrome erstellt Lock-Dateien beim Start (.lock, SingletonSocket, etc.).
        → Wenn Chrome abstürzt → Lock-Dateien bleiben zurück.
        → Beim nächsten Start: "Profile is in use by another process" Fehler.
        → Wir löschen sie VOR dem Start → verhindert diesen Fehler.
        
        WARUM shutil.copytree(symlinks=True)?
        → Chrome verwendet Symlinks innerhalb des Profils (z.B. für Cache).
        → symlinks=True → kopiere Symlinks als Symlinks (nicht dereferenzieren).
        → Das spart Platz und verhindert Broken-Symlink-Probleme.
        
        WARUM ignore_dangling_symlinks=True?
        → Manche Symlinks im Profil zeigen auf nicht-existierende Dateien
          (z.B. wenn das Original-Profil verändert wurde).
        → Ohne ignore_dangling=True → copytree wirft Fehler.
        → Mit ignore_dangling=True → ignoriere defekte Symlinks (kopiere nicht).
        
        Returns:
            str: Pfad zum temporären Profil-Verzeichnis.
        
        Raises:
            FileNotFoundError: Wenn Quell-Profil nicht existiert.
        
        Example:
            temp_dir = self._copy_profile()
            # temp_dir = "/tmp/sinator-chrome-1778261390"
        """
        # Erstelle temporäres Verzeichnis mit eindeutigem Namen.
        # WARUM int(time.time())? Unix-Timestamp als Integer (keine Dezimalstellen).
        # Eindeutig pro Sekunde (mehrere Starts pro Sekunde → gleicher Name,
        # aber das ist OK weil wir nur EINEN Chrome gleichzeitig haben).
        temp_dir = f"/tmp/sinator-chrome-{int(time.time())}"
        
        # Quell-Profil-Pfad (innerhalb des user-data-dir).
        # Beispiel: ~/Library/Application Support/Google/Chrome/Profile 901 (Jeremy)
        source_profile = os.path.join(self.source_user_data_dir, self.profile_name)
        
        # Logge Kopiervorgang (nützlich für Debugging).
        logger.info(f"Kopiere Profil: {source_profile} → {temp_dir}")
        
        # Erstelle Ziel-Verzeichnis (existiert noch nicht → makedirs).
        # exist_ok=True → kein Fehler wenn Verzeichnis bereits existiert.
        os.makedirs(temp_dir, exist_ok=True)
        
        # ── Kopiere "Local State" ──
        # "Local State" ist eine JSON-Datei mit Chrome-Metadaten.
        # Enthält: Profil-Liste, Einstellungen, etc.
        local_state_src = os.path.join(self.source_user_data_dir, "Local State")
        if os.path.exists(local_state_src):
            # shutil.copy2 kopiert Datei MIT Metadaten (Timestamps).
            # WARUM? Chrome prüft Timestamps um zu wissen ob das Profil aktuell ist.
            shutil.copy2(local_state_src, os.path.join(temp_dir, "Local State"))
            logger.info("Local State kopiert")
        
        # ── Kopiere "Last Version" (optional) ──
        # "Last Version" enthält die Chrome-Versionsnummer.
        # Nicht kritisch, aber nützlich für Chrome-Kompatibilität.
        last_version_src = os.path.join(self.source_user_data_dir, "Last Version")
        if os.path.exists(last_version_src):
            shutil.copy2(last_version_src, os.path.join(temp_dir, "Last Version"))
        
        # ── Kopiere Profil-Ordner rekursiv ──
        # shutil.copytree kopiert ein ganzes Verzeichnis rekursiv.
        # WARUM symlinks=True? Chrome verwendet Symlinks (siehe oben).
        # WARUM ignore_dangling_symlinks=True? Defekte Symlinks ignorieren.
        if os.path.exists(source_profile):
            shutil.copytree(
                source_profile,
                os.path.join(temp_dir, self.profile_name),
                symlinks=True,                   # Symlinks als Symlinks kopieren
                ignore_dangling_symlinks=True,  # Defekte Symlinks ignorieren
            )
            logger.info(f"{self.profile_name} kopiert")
        else:
            # Profil nicht gefunden → Fehler.
            # WARUM FileNotFoundError? Klare Fehlermeldung: "Profil X nicht unter Y".
            raise FileNotFoundError(f"Profil nicht gefunden: {source_profile}")
        
        # ── Erstelle "First Run" Datei ──
        # "First Run" ist eine leere Datei die Chrome beim ersten Start sucht.
        # Wenn vorhanden → überspringe Welcome-Dialog ("Willkommen bei Chrome").
        # WARUM Path.touch()? Erstellt leere Datei wenn nicht existiert.
        Path(os.path.join(temp_dir, "First Run")).touch()
        
        # ── Lösche Lock-Dateien ──
        # Lock-Dateien verhindern "Profile in use" Fehler bei abgestürztem Chrome.
        # Wir löschen sie VOR dem Start.
        # Muster: *.lock, Singleton* (SingletonSocket, SingletonLock, etc.).
        for pattern in ["*.lock", "Singleton*"]:
            # Path.rglob(pattern) → rekursive Suche nach Dateien die Muster matchen.
            for f in Path(temp_dir).rglob(pattern):
                # f.unlink() → Datei löschen.
                # missing_ok=True → kein Fehler wenn Datei nicht existiert
                # (könnte zwischen Suche und Löschen verschwinden).
                f.unlink(missing_ok=True)
        
        return temp_dir
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PRIVATE METHODE: _launch_chrome
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _launch_chrome(self) -> subprocess.Popen:
        """
        Startet Chrome als Subprocess mit CDP-Debugging.
        
        ABLAUF:
        1. Baue Argument-Liste für Chrome.
        2. Füge --user-data-dir und --profile-directory hinzu.
        3. Füge --remote-debugging-port für CDP hinzu.
        4. Füge --remote-allow-origins=* für WebSocket-Auth hinzu.
        5. Füge --no-first-run und --no-default-browser-check hinzu.
        6. Füge --window-size und --lang hinzu.
        7. Optional: Füge --headless=new hinzu.
        8. Starte Chrome via subprocess.Popen.
        
        WARUM subprocess.Popen statt os.system()?
        → Popen gibt ein Prozess-Objekt zurück (PID, stdin, stdout, stderr).
        → Wir können proc.terminate() und proc.kill() aufrufen.
        → Kein Shell-Injection-Risiko (Argumente als Liste, nicht String).
        → stdout/stderr können umgeleitet werden (DEVNULL = verbergen).
        
        WARUM DEVNULL für stdout/stderr?
        → Chrome ist sehr gesprächig (hunderte Log-Zeilen).
        → Ohne Umleitung → Logs erscheinen im Terminal (unübersichtlich).
        → Mit DEVNULL → Logs werden verworfen (außer debug=True).
        → WARNUNG: Wenn Chrome crasht → keine Crash-Logs!
        → Für Debugging: stdout=PIPE, stderr=PIPE und Logs in Datei schreiben.
        
        WARUM --remote-allow-origins=* OHNE Quotes?
        → subprocess.Popen BYPASSED die Shell (zsh/bash).
        → Keine glob expansion (zsh würde "*" expandieren).
        → Chrome erhält literal "*" und erlaubt ALLE Origins.
        → MIT Quotes ("*") → Chrome erhält literal "\"*\"" (mit Quotes)
        → → Origin-Check schlägt fehl → 403 Forbidden.
        
        WARUM --force-renderer-accessibility NICHT hier?
        → Wird vom ChromeLauncher (survey/chrome.py) gesetzt.
        → BrowserManager verwendet connect_over_cdp (kein CUA).
        → CUA (macOS Accessibility) erfordert --force-renderer-accessibility
        → aber BrowserManager ist CDP-basiert (nicht CUA).
        → Für Survey-Automation ist CDP ausreichend.
        → Für Google OAuth Login ist CUA nötig (wird von ChromeLauncher gehandhabt).
        
        WARUM --no-first-run?
        → Verhindert "Willkommen bei Chrome" Dialog.
        → Der Dialog blockiert Automation (Maus-Klick nötig).
        
        WARUM --no-default-browser-check?
        → Verhindert "Chrome als Standard-Browser setzen?" Dialog.
        → Auch dieser Dialog blockiert Automation.
        
        WARUM --window-size=1280,800?
        → Standard-Viewport-Größe.
        → Manche Websites verwenden Responsive Design (mobile bei kleinem Fenster).
        → 1280x800 = Desktop-Größe (keine mobile Version).
        
        WARUM --lang=de-DE?
        → HeyPiggy ist auf Deutsch.
        → Deutsche Sprache = deutsche UI-Elemente ("Weiter", "Abmelden", etc.).
        → Wichtig für Text-Matching in Automation.
        
        Returns:
            subprocess.Popen: Der gestartete Chrome-Prozess.
            proc.pid → Prozess-ID (PID).
            proc.poll() → None wenn läuft, sonst Exit-Code.
        
        Raises:
            FileNotFoundError: Wenn Chrome-Binary nicht gefunden wird.
        
        Example:
            proc = self._launch_chrome()
            # proc.pid = 12345
            # Chrome läuft jetzt auf Port 9999.
        """
        # Baue Chrome-Argument-Liste.
        # WARUM Liste statt String? subprocess.Popen mit Liste = sicherer
        # (kein Shell-Injection, keine Leerzeichen-Probleme).
        args = [
            # Chrome-Binary-Pfad.
            self.chrome_path,
            
            # --user-data-dir: Pfad zum Profil-Verzeichnis.
            # WARUM? Chrome speichert ALLE Daten hier (Cookies, History, etc.).
            # Wir verwenden das KOPIERTE Temp-Profil (nicht Original!).
            f"--user-data-dir={self._temp_profile_dir}",
            
            # --profile-directory: Name des Profil-Ordners INNERHALB von user-data-dir.
            # WARUM? Chrome kann mehrere Profile haben ("Default", "Profile 1", etc.).
            # Wir starten mit einem spezifischen Profil.
            f"--profile-directory={self.profile_name}",
            
            # --remote-debugging-port: CDP-Port.
            # WARUM? Playwright verbindet über diesen Port mit Chrome.
            f"--remote-debugging-port={self.cdp_port}",
            
            # --remote-allow-origins: Erlaubt ALLE Origins für CDP WebSocket.
            # WARUM "*"? Playwright verbindet von localhost mit Chrome.
            # Chrome 111+ erfordert Origin-Header-Matching.
            # "*" = erlaube alle Origins (inkl. localhost).
            # WICHTIG: OHNE Quotes! subprocess bypassed Shell.
            "--remote-allow-origins=*",
            
            # --no-first-run: Überspringe Willkommen-Dialog.
            "--no-first-run",
            
            # --no-default-browser-check: Überspringe Standard-Browser-Dialog.
            "--no-default-browser-check",
            
            # --window-size: Viewport-Größe.
            "--window-size=1280,800",
            
            # --lang: Sprache (für deutsche UI-Elemente).
            "--lang=de-DE",
        ]
        
        # ═══════════════════════════════════════════════════════════════════════
        # PROXY SUPPORT (SR-151)
        # ═══════════════════════════════════════════════════════════════════════
        # Wenn Proxy gesetzt → fuege --proxy-server und --proxy-bypass-list hinzu.
        # WARUM? Anti-Detection Layer 3: Residential Proxies verbergen Datacenter IP.
        # WARUM --proxy-bypass-list? Localhost-Anfragen sollen NICHT ueber Proxy gehen
        # (CDP-Verbindung, lokale APIs, etc.).
        if self.proxy is not None:
            args.append(f"--proxy-server={self.proxy.url}")
            args.append("--proxy-bypass-list=localhost,127.0.0.1,<local>")
            logger.info(f"Proxy aktiviert: {self.proxy.label} ({self.proxy.country})")
        
        # Optional: Headless-Modus.
        # WARUM --headless=new? "new" ist der moderne Headless-Modus (Chrome 109+).
        # Der alte --headless ist deprecated.
        # Unterschied: --headless=new unterstützt moderne Features (Extensions, etc.).
        if self.headless:
            args.append("--headless=new")
        
        # Logge Start-Kommando (nur erste 3 Argumente, der Rest ist lang).
        # WARUM nur 3? chrome_path + user-data-dir + profile-directory = identifiziert
        # den Start eindeutig. Der Rest ist immer gleich.
        logger.info(f"Starte Chrome: {' '.join(args[:3])}...")
        
        # Starte Chrome als Subprocess.
        # stdout=DEVNULL, stderr=DEVNULL → Chrome-Logs werden verworfen.
        # WARUM? Chrome ist sehr gesprächig (hunderte Zeilen).
        # Wenn du Debug-Logs brauchst → auf PIPE umstellen und in Datei schreiben.
        proc = subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        
        return proc
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PRIVATE METHODE: _wait_for_cdp
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def _wait_for_cdp(self, max_retries: int = 15):
        """
        Wartet bis der CDP-Endpoint erreichbar ist.
        
        ABLAUF:
        1. Schleife von 0 bis max_retries-1.
        2. Jede Iteration: HTTP GET auf /json/version (1s Timeout).
        3. Wenn erfolgreich → Logge und return (Chrome ist bereit).
        4. Wenn Fehler → asyncio.sleep(1) und nächste Iteration.
        5. Nach max_retries Fehlversuchen → TimeoutError.
        
        WARUM Polling statt Event/Callback?
        → Chrome gibt kein Event wenn CDP bereit ist.
        → Wir müssen aktiv prüfen (Polling-Loop).
        → Alternative: Festes Sleep von 5s (aber manchmal braucht Chrome 2s,
        manchmal 10s → Polling ist effizienter).
        
        WARUM asyncio.sleep() statt time.sleep()?
        → async def → wir können time.sleep() nicht verwenden (blocking).
        → asyncio.sleep(1) gibt die Kontrolle zurück (nicht-blocking).
        → Andere Tasks können währenddessen laufen.
        
        WARUM 1s Sleep pro Iteration?
        → Chrome braucht typischerweise 2-5s bis CDP bereit ist.
        → 1s Intervall = ausreichend schnell (nicht zu viele Requests).
        → Weniger Sleep = mehr Requests (unnötig).
        → Mehr Sleep = langsamer (Chrome könnte bereits nach 2s bereit sein).
        
        WARUM urllib.request.urlopen (synchron) in async Funktion?
        → Der HTTP-Request ist sehr schnell (~1-10ms).
        → Kein asyncio-HTTP-Client nötig (kein großer Performance-Unterschied).
        → Einfacher: Keine External Dependencies (aiohttp, httpx, etc.).
        
        Args:
            max_retries: Maximale Anzahl Versuche (default: 15).
                Bei 1s Sleep pro Iteration = max 15s Wartezeit.
        
        Raises:
            TimeoutError: Wenn CDP nach max_retries nicht erreichbar ist.
        
        Example:
            await self._wait_for_cdp(max_retries=15)
            # Wenn erfolgreich: Chrome ist bereit.
            # Wenn fehlgeschlagen: TimeoutError nach 15s.
        """
        # Schleife über max_retries Iterationen.
        for i in range(max_retries):
            try:
                # Importiere urllib.request lokal (wird nur hier gebraucht).
                import urllib.request
                
                # HTTP GET auf /json/version (CDP HTTP API).
                # WARUM timeout=2? Länger als _check_cdp_alive (dort 1s).
                # Hier haben wir mehr Zeit (wir warten ja schon).
                urllib.request.urlopen(
                    f"http://127.0.0.1:{self.cdp_port}/json/version",
                    timeout=2
                )
                
                # Erfolg! CDP ist erreichbar.
                logger.info(f"CDP erreichbar nach {i+1}s")
                return  # Funktion beenden (Chrome ist bereit).
            
            except Exception:
                # Fehler (ConnectionRefused, Timeout, etc.).
                # Chrome ist noch nicht bereit → warte 1s.
                pass
            
            # Warte 1s (nicht-blocking).
            # WARUM await? async def Funktion → asyncio.sleep ist await-basiert.
            await asyncio.sleep(1)
        
        # Alle Versuche fehlgeschlagen → TimeoutError.
        # WARUM TimeoutError? Standard-Exception für Zeitüberschreitungen.
        # Client kann darauf reagieren (Retry, Fehlermeldung, etc.).
        raise TimeoutError(
            f"CDP nicht erreichbar nach {max_retries}s auf Port {self.cdp_port}"
        )
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PRIVATE METHODE: _inject_stealth
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def _inject_stealth(self):
        """
        Injiziert Stealth-JavaScript in alle neuen Pages.
        
        ABLAUF:
        1. Definiere Stealth-JS String.
        2. context.add_init_script() → JS wird in JEDE neue Page injiziert.
        
        WAS MACHT DAS STEALTH-JS?
        1. navigator.webdriver = undefined
           → Playwright setzt navigator.webdriver = true (Bot-Detection!).
           → Wir setzen es auf undefined (wie ein echter Browser).
        2. navigator.plugins = [1, 2, 3, 4, 5]
           → Echte Browser haben Plugins (Flash, PDF, etc.).
           → Playwright hat keine Plugins → Bot-Detection erkennt das.
        3. navigator.languages = ['de-DE', 'de', 'en-US', 'en']
           → Sprach-Profil für deutsche Websites (HeyPiggy).
        4. window.chrome = {...}
           → Chrome-spezifische Objekte (runtime, loadTimes, csi, app).
           → Fehlende window.chrome Objekte = Bot-Indikator.
        5. Permissions-API override
           → Überschreibt Notification.permission Abfrage.
           → Verhindert "Allow Notifications?" Popups.
        
        WARUM add_init_script()?
        → JS wird AUTOMATISCH in JEDE neue Page injiziert (vor DOM-Ready).
        → Kein manuelles Injizieren pro Page nötig.
        → Wenn eine neue Page geöffnet wird → Stealth-JS ist bereits da.
        
        WARUM nicht stealth-Plugin (playwright-stealth)?
        → playwright-stealth ist ein externes Paket (zusätzliche Dependency).
        → Unser Stealth-JS ist schlank (~20 Lines) und ausreichend.
        → Weniger Dependencies = weniger Schwachstellen.
        → Wir haben vollständige Kontrolle über das JS.
        
        WARUM "undefined" statt "false" für webdriver?
        → Echte Browser haben navigator.webdriver = undefined (nicht false).
        → false wäre ein Wert → Bot-Detection könnte "false" erkennen.
        → undefined = Property existiert nicht (wie in echten Browsern vor Chrome 63).
        
        Raises:
            RuntimeError: Wenn _context None ist (nicht verbunden).
        
        Example:
            await self._inject_stealth()
            # Jetzt sind alle neuen Pages "getarnt".
        """
        # Stealth-JavaScript (als Python-String).
        # WARUM Triple-Quotes? Multi-Line String ohne Escape-Probleme.
        # WARUM Kommentare im JS? Dokumentation WAS jede Zeile macht.
        stealth_js = """
        // ═══════════════════════════════════════════════════════════════
        // STEALTH JS — Bot-Detection-Umgehung
        // ═══════════════════════════════════════════════════════════════
        
        // 1. navigator.webdriver überschreiben.
        // Playwright setzt navigator.webdriver = true (erkennbar für Bots).
        // Echte Browser (vor Chrome 63) haben navigator.webdriver = undefined.
        // Wir setzen es auf undefined → nicht erkennbar.
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        
        // 2. navigator.plugins faken.
        // Echte Browser haben Plugins (Flash, PDF Viewer, etc.).
        // Playwright hat keine Plugins → leeres Array = Bot-Indikator.
        // Wir setzen ein Array mit Dummy-Werten → sieht echt aus.
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        
        // 3. navigator.languages setzen.
        // Sprach-Profil für deutsche Websites (HeyPiggy).
        // Reihenfolge: Deutsch (Deutschland), Deutsch, Englisch (USA), Englisch.
        Object.defineProperty(navigator, 'languages', { get: () => ['de-DE', 'de', 'en-US', 'en'] });
        
        // 4. window.chrome faken.
        // Chrome-spezifische Objekte die in echten Chrome existieren.
        // Fehlende window.chrome Objekte = Bot-Indikator.
        window.chrome = {
            runtime: {},           // Chrome Extension Runtime
            loadTimes: function() {},  // Chrome Load Times API (deprecated)
            csi: function() {},    // Chrome CSI (Chrome Startup Info)
            app: {}                // Chrome App API
        };
        
        // 5. Permissions-API überschreiben.
        // Verhindert "Allow Notifications?" Popups.
        // Echte Seiten fragen nach Notification.permission.
        // Wir geben den tatsächlichen Wert zurück (nicht "prompt" forced).
        (() => {
            // Originale query Funktion speichern.
            const originalQuery = window.navigator.permissions.query;
            
            // Überschreiben mit neuer Funktion.
            window.navigator.permissions.query = (parameters) => {
                // Wenn es um Notifications geht → gib tatsächlichen Wert zurück.
                if (parameters.name === 'notifications') {
                    return Promise.resolve({
                        state: Notification.permission  // 'granted', 'denied', oder 'default'
                    });
                }
                // Für alle anderen Permissions → originale Funktion verwenden.
                return originalQuery(parameters);
            };
        })();
        """
        
        # Injiziere JS in den Context.
        # WARUM if self._context? Sicherheit: Nur wenn Context existiert.
        # Wenn _context None → würde AttributeError werfen.
        if self._context:
            # add_init_script() → JS wird in JEDE neue Page AUTOMATISCH injiziert.
            await self._context.add_init_script(stealth_js)
            logger.info("Stealth-JS injiziert")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PRIVATE METHODE: _cleanup
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def _cleanup(self):
        """
        Räumt Chrome, Playwright und Temp-Profil auf.
        
        ABLAUF:
        1. Browser schließen (await browser.close()).
        2. Playwright stoppen (await playwright.stop()).
        3. Chrome-Prozess beenden (terminate → kill).
        4. Temp-Profil-Verzeichnis löschen (shutil.rmtree).
        5. State zurücksetzen (_is_running=False, _browser=None, etc.).
        
        WARUM async?
        → browser.close() und playwright.stop() sind async.
        → Ohne await → Race Condition (Cleanup läuft nicht zu Ende).
        
        WARUM mehrere try/except Blöcke?
        → Jeder Schritt kann unabhängig fehlschlagen.
        → Wenn browser.close() fehlschlägt → trotzdem playwright.stop() aufrufen.
        → Wenn playwright.stop() fehlschlägt → trotzdem proc.kill() aufrufen.
        → Kein einzelner try/except um ALLES (würde bei erstem Fehler abbrechen).
        
        WARUM proc.terminate() dann proc.kill()?
        → terminate() sendet SIGTERM (sanftes Beenden).
        → Chrome hat 5s Zeit zum Beenden (proc.wait(timeout=5)).
        → Wenn nicht beendet → kill() sendet SIGKILL (hartes Beenden).
        → SIGKILL kann nicht ignoriert werden (Chrome wird IMMER beendet).
        
        WARUM shutil.rmtree(ignore_errors=True)?
        → Wenn Temp-Profil bereits gelöscht wurde (oder nicht existiert)
        → → ignore_errors=True → kein Fehler.
        → Auch wenn einzelne Dateien schreibgeschützt sind → ignoriere.
        
        WARUM State zurücksetzen?
        → Wenn Cleanup erfolgreich war → alle Referenzen auf None setzen.
        → Verhindert Memory-Leaks (Referenzen auf tote Objekte).
        → Wichtig für Wiederverwendung: Nächster start() → Cold-Start.
        
        Raises:
            Keine. ALLE Exceptions werden abgefangen (Logging).
        
        Example:
            await self._cleanup()
            # Chrome ist beendet, Playwright gestoppt, Temp-Profil gelöscht.
        """
        # ── Schritt 1: Browser schließen ──
        try:
            if self._browser:
                # browser.close() beendet Playwright-Verbindung gracefully.
                # WARUM await? async Methode.
                await self._browser.close()
                logger.info("Browser geschlossen")
        except Exception as e:
            # Fehler beim Schließen (z.B. Verbindung bereits tot).
            logger.warning(f"Browser close Fehler: {e}")
        
        # ── Schritt 2: Playwright stoppen ──
        try:
            if self._playwright:
                # playwright.stop() beendet den Playwright-Prozess.
                await self._playwright.stop()
        except Exception:
            # Fehler beim Stoppen (z.B. bereits gestoppt).
            # Kein Logging nötig (nicht kritisch).
            pass
        
        # ── Schritt 3: Chrome-Prozess beenden ──
        try:
            if self._chrome_proc:
                # SIGTERM senden (sanftes Beenden).
                self._chrome_proc.terminate()
                
                # Warte bis Chrome beendet (max 5s).
                try:
                    self._chrome_proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # Chrome hat sich nicht innerhalb von 5s beendet.
                    # SIGKILL senden (hartes Beenden).
                    self._chrome_proc.kill()
                
                logger.info("Chrome-Prozess beendet")
        except Exception as e:
            # Fehler beim Beenden (z.B. Prozess existiert nicht mehr).
            logger.warning(f"Chrome kill Fehler: {e}")
        
        # ── Schritt 4: Temp-Profil löschen ──
        try:
            if self._temp_profile_dir and os.path.exists(self._temp_profile_dir):
                # shutil.rmtree löscht Verzeichnis rekursiv.
                # ignore_errors=True → keine Fehler wenn Dateien schreibgeschützt.
                shutil.rmtree(self._temp_profile_dir, ignore_errors=True)
                logger.info(f"Temp-Profil aufgeräumt: {self._temp_profile_dir}")
        except Exception as e:
            # Fehler beim Löschen (z.B. Datei in Verwendung).
            logger.warning(f"Cleanup Fehler: {e}")
        
        # ── Schritt 5: State zurücksetzen ──
        # Alle Referenzen auf None setzen (verhindert Memory-Leaks).
        self._is_running = False      # Chrome ist nicht mehr aktiv.
        self._browser = None          # Kein Browser-Objekt mehr.
        self._context = None          # Kein Context mehr.
        self._playwright = None       # Kein Playwright mehr.
        self._chrome_proc = None      # Kein Prozess mehr.
        self._temp_profile_dir = None  # Kein Temp-Profil mehr.


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON-INSTANZ und GETTER
# ═══════════════════════════════════════════════════════════════════════════════
# Diese Funktionen stellen sicher dass es nur EINE BrowserManager-Instanz gibt.
# ═══════════════════════════════════════════════════════════════════════════════

# Globale Variable für die Singleton-Instanz.
# WARUM None? Beim ersten Aufruf wird die Instanz erstellt.
# WARUM global? Muss von get_browser_manager() und anderen Funktionen zugänglich sein.
_browser_manager: Optional[BrowserManager] = None


def get_browser_manager() -> BrowserManager:
    """
    Liefert die Singleton-Instanz des BrowserManagers.
    
    WARUM Singleton?
    → Maximal EIN Chrome-Prozess gleichzeitig (Ressourcen-Schonung).
    → Wiederverwendung: Wenn Chrome bereits läuft → verwende ihn.
    → Konsistenz: Alle Endpoints verwenden denselben Browser.
    
    WARUM nicht einfach BrowserManager()?
    → Jeder Aufruf von BrowserManager() erstellt eine NEUE Instanz.
    → Neue Instanz = neuer Chrome-Prozess (Memory-Leak!).
    → get_browser_manager() stellt sicher: Immer dieselbe Instanz.
    
    WARUM global _browser_manager?
    → Die Instanz muss zwischen Aufrufen persistieren.
    → Wenn wir keine globale Variable verwenden → Instanz wird nach Funktionsende
    → zerstört (Garbage Collection) → Chrome läuft aber Referenz ist weg.
    
    WARUM cdp_port=9999?
    → Default-Port für Bot-Chrome (nicht 9222 wegen SINator-Chrome Konflikt).
    → Kann über BrowserManager(cdp_port=...) geändert werden.
    
    Returns:
        BrowserManager: Die Singleton-Instanz (Port 9999, Profile 901 (Jeremy)).
    
    Example:
        bm = get_browser_manager()
        # bm ist IMMER dieselbe Instanz (auch bei mehreren Aufrufen).
        
        bm2 = get_browser_manager()
        # bm is bm2 → True (dasselbe Objekt).
    """
    # Zugriff auf globale Variable (sonst würde eine lokale Variable erstellt).
    global _browser_manager
    
    # Wenn Instanz noch nicht existiert → erstelle sie.
    if _browser_manager is None:
        # Erstelle BrowserManager mit Default-Parametern.
        # cdp_port=9999, profile="Profile 901 (Jeremy)": HeyPiggy Bot-Chrome Port.
        _browser_manager = BrowserManager(cdp_port=9999, profile_name="Profile 901 (Jeremy)")
    
    # Gib die Singleton-Instanz zurück.
    return _browser_manager


# ═══════════════════════════════════════════════════════════════════════════════
# ENDE VON BROWSER_MANAGER.PY
# ═══════════════════════════════════════════════════════════════════════════════
# ZUSAMMENFASSUNG:
#
# Diese Datei implementiert den BrowserManager (SINator-Style):
#   - Profil-Kopie (NICHT Symlink!) für funktionierende Cookies.
#   - Chrome als subprocess mit CDP-Port 9999.
#   - Playwright connect_over_cdp() für Browser-Automation.
#   - Stealth-JS Injection für Bot-Detection-Umgehung.
#   - Warm-Start (Wiederverwendung) statt Cold-Start.
#   - Cleanup: Chrome beenden, Playwright stoppen, Temp-Profil löschen.
#
# DESIGN-PRINZIPIEN:
#   1. Singleton: Maximal EIN Chrome-Prozess.
#   2. Lazy-Start: Chrome erst bei Bedarf starten.
#   3. Fail-Closed: Bei Fehlern → Cleanup und Exception.
#   4. Idempotent: stop() mehrfach aufrufbar.
#   5. Self-Healing: get_page() reconnectet automatisch.
#   6. Resource-Safe: Temp-Profil wird IMMER gelöscht.
#
# WICHTIGE METHODEN (Public API):
#   - start(): Chrome starten/wiederverwenden.
#   - get_page(): Page-Objekt für Automation.
#   - stop(): Chrome beenden und aufräumen.
#   - health(): Status-Check (läuft? idle-seit?).
#
# WICHTIGE PRIVATE METHODEN:
#   - _copy_profile(): Profil 73 → /tmp/sinator-chrome-XXXX.
#   - _launch_chrome(): subprocess.Popen mit Flags.
#   - _wait_for_cdp(): Polling auf /json/version.
#   - _inject_stealth(): Bot-Detection-Umgehung.
#   - _cleanup(): Alles aufräumen.
# ═══════════════════════════════════════════════════════════════════════════════
