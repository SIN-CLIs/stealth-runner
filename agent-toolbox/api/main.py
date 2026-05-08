"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║           FastAPI Main Application — Agent-Toolbox API (stealth-runner)       ║
║                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ZWECK / PURPOSE:                                                            ║
║  ────────────────                                                            ║
║  Diese Datei ist der EINSTIEGSPUNKT für die gesamte FastAPI-Anwendung.      ║
║  Sie definiert ALLE Endpoints, registriert Router, und steuert den           ║
║  Browser-Lifecycle (Start, Stop, Health-Check).                              ║
║                                                                              ║
║  WARUM FASTAPI?                                                              ║
║  ───────────────                                                             ║
║  1. AUTO-VALIDATION via Pydantic:                                            ║
║     Wenn ein Client ein Feld vergisst oder falsch typisiert (z.B. String    ║
║     statt Integer), generiert FastAPI SOFORT einen 422-Fehler mit Details. ║
║     Ohne FastAPI → Runtime-Fehler irgendwo tief im Code, schwer debuggbar. ║
║  2. ASYNC-NATIVE: Playwright ist async (Browser-Automation erfordert async/ ║
║     await). FastAPI unterstützt async Endpoints nativ. Flask/Sync-Frameworks║
║     würden blockieren oder komplexe Threading-Logik erfordern.              ║
║  3. AUTO-DOKUMENTATION: /docs (Swagger UI) und /redoc werden AUTOMATISCH   ║
║     aus den Pydantic-Modellen generiert. Jeder Agent kann die API verstehen ║
║     ohne README zu lesen.                                                    ║
║  4. HIGH PERFORMANCE: Uvicorn (ASGI-Server) + FastAPI = einer der schnellsten║
║     Python-Web-Frameworks. Wichtig für schnelle Survey-Automation (viele   ║
║     Requests in kurzer Zeit).                                                ║
║                                                                              ║
║  ARCHITEKTUR-OVERVIEW:                                                       ║
║  ─────────────────────                                                       ║
║  ┌─────────────────────────────────────────────────────────────────────┐    ║
║  │  Client (curl, Python requests, Playwright, etc.)                   │    ║
║  │       │                                                             │    ║
║  │       ▼                                                             │    ║
║  │  ┌───────────────────────────────────────────────────────────────┐   │    ║
║  │  │  FastAPI App (Diese Datei)                                    │   │    ║
║  │  │  ├── Router: /browser/*     → Browser Lifecycle                │   │    ║
║  │  │  ├── Router: /survey/*    → Survey Actions (click, fill)     │   │    ║
║  │  │  ├── Router: /cookies/*   → Cookie Extract/Inject/Verify      │   │    ║
║  │  │  ├── Router: /dashboard/* → Scan + Balance                    │   │    ║
║  │  │  ├── Router: /services/*  → HeyPiggy Login                     │   │    ║
║  │  │  └── Router: /tools/*     → Navigate, Screenshot, Content    │   │    ║
║  │  └───────────────────────────────────────────────────────────────┘   │    ║
║  │       │                                                             │    ║
║  │       ▼                                                             │    ║
║  │  ┌───────────────────────────────────────────────────────────────┐   │    ║
║  │  │  Core Modules                                                 │   │    ║
║  │  │  ├── BrowserManager  → Chrome starten/stoppen (CDP Port 9999)│   │    ║
║  │  │  ├── CookieManager   → Cookies speichern/laden (JSON)       │   │    ║
║  │  │  └── survey_actions  → CDP-WebSocket JS-Execution           │   │    ║
║  │  └───────────────────────────────────────────────────────────────┘   │    ║
║  │       │                                                             │    ║
║  │       ▼                                                             │    ║
║  │  ┌───────────────────────────────────────────────────────────────┐   │    ║
║  │  │  Chrome Process (Bot-Profile, isoliert)                       │   │    ║
║  │  │  ├── CDP Port 9999  → DevTools Protocol                      │   │    ║
║  │  │  └── Playwright     → connect_over_cdp()                     │   │    ║
║  │  └───────────────────────────────────────────────────────────────┘   │    ║
║  └─────────────────────────────────────────────────────────────────────┘    ║
║                                                                              ║
║  SICHERHEIT / BANNED PATTERNS:                                               ║
║  ──────────────────────────────                                              ║
║  • KEINE hardcoded PIDs in Endpoints (PID kommt vom BrowserManager)          ║
║  • KEINE Passwörter in Request-Modellen (nur Tokens/Cookies)                ║
║  • KEINE Session-IDs in Logs (nur Cookie-Datei)                              ║
║  • KEIN pkill -f "Google Chrome" (tötet USER Chrome!)                        ║
║  • NIEMALS User-Chrome killen (nur /tmp/sinator-chrome-* Profile)           ║
║  • NIEMALS --remote-allow-origins="*" mit Quotes (zsh glob expansion!)      ║
║                                                                              ║
║  ENDPOINTS (Vollständige Liste):                                             ║
║  ──────────────────────────────                                              ║
║  BROWSER:                                                                    ║
║    POST /browser/start    → Chrome starten/wiederverwenden                   ║
║    POST /browser/stop     → Chrome stoppen                                   ║
║    GET  /browser/health   → Browser Status (running, idle_seconds)           ║
║  SERVICES:                                                                   ║
║    POST /services/heypiggy/login → HeyPiggy Login (cookie default, CUA fb) ║
║  SURVEY (aus survey_actions.py Router):                                     ║
║    POST /survey/click-card     → Survey-Karte klicken                        ║
║    GET  /survey/modal          → Modal-Inhalt lesen                         ║
║    POST /survey/click-button   → Button klicken                            ║
║    POST /survey/select-option  → Radio/Checkbox auswählen                  ║
║    POST /survey/fill-text      → Text eingeben                               ║
║    POST /survey/run-one        → Komplette Survey (Loop)                    ║
║  COOKIES (aus cookie_routes.py Router):                                      ║
║    POST /cookies/extract  → Cookies aus Browser extrahieren                  ║
║    POST /cookies/inject   → Cookies in Browser laden                        ║
║    POST /cookies/verify   → Session-Status prüfen                           ║
║  DASHBOARD (aus dashboard_routes.py Router):                                 ║
║    POST /dashboard/scan   → Surveys mit Rewards scannen                     ║
║    POST /dashboard/balance → Aktuellen Kontostand auslesen                  ║
║  TOOLS:                                                                      ║
║    POST /tools/extract-cookies → Cookies extrahieren (Legacy, siehe /cookies)║
║    POST /tools/navigate      → Zu URL navigieren                             ║
║    POST /tools/screenshot    → Screenshot machen                             ║
║    POST /tools/page-content  → Seiteninhalt extrahieren                      ║
║                                                                              ║
║  LAZY-LOADING PATTERN:                                                       ║
║  ──────────────────────                                                      ║
║  Alle schweren Imports (Playwright, cua-driver) werden NICHT beim          ║
║  Startup geladen, sondern erst bei ERSTEM Zugriff (Lazy-Loading).         ║
║  WARUM?                                                                      ║
║  • API startet in <1s (statt 5-10s mit Playwright-Import).                 ║
║  • Wenn ein Modul fehlt (z.B. Playwright nicht installiert), crasht die API ║
║    NICHT beim Start, sondern erst beim Zugriff auf den betroffenen Endpoint.║
║  • Fehlermeldung ist klar: "BrowserManager requires Playwright. Install: ..." ║
║  • Ermöglicht modulare Entwicklung: Browser-Endpoints funktionieren auch   ║
║    ohne schwere Dependencies (cua-driver nur für Login-Fallback).         ║
║                                                                              ║
║  FEHLERBEHANDLUNG:                                                           ║
║  ─────────────────                                                             ║
║  • Jeder Endpoint ist in try/except gewrappt.                                ║
║  • Bei Exception → HTTPException(status_code=500, detail=str(e)).           ║
║  • Globaler Exception Handler (@app.exception_handler) fängt ALLE unerwarteten ║
║    Exceptions und gibt JSON-ErrorResponse zurück.                            ║
║  • Keine rohen Tracebacks an Client (nur mit debug=True).                   ║
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

# os: Betriebssystem-Interaktion (Umgebungsvariablen, Pfad-Operationen).
# WARUM? BROWSER_HEADLESS wird aus os.getenv gelesen (für Docker/CI).
import os

# sys: System-spezifische Parameter (sys.path für Imports).
# WARUM? Wir fügen agent-toolbox/ und survey-cli/ zu sys.path hinzu
# damit relative Imports funktionieren (da survey-cli ein separates Paket ist).
import sys

# time: Zeit-Messung für Performance-Monitoring.
# WARUM? survey_run() misst elapsed_s für Statistiken.
import time

# Path: Objekt-orientierte Pfad-Manipulation (cross-platform).
# WARUM? Sicherer als String-Konkatenation (Path("a") / "b" funktioniert
# auf Windows UND Linux/Mac).
from pathlib import Path

# Optional: Ein Feld kann entweder einen Wert haben ODER None.
# WARUM? headless: Optional[bool] = None bedeutet "aus .env lesen".
from typing import Optional

# FastAPI: Das Web-Framework.
# FastAPI: Haupt-Klasse für die App.
# HTTPException: Für Fehler-Responses (404, 500, etc.).
# JSONResponse: Für manuelle JSON-Responses (z.B. im Exception Handler).
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

# ═══════════════════════════════════════════════════════════════════════════════
# PATH SETUP: Import-Pfade konfigurieren
# ═══════════════════════════════════════════════════════════════════════════════
# WARUM sys.path.insert?
# → survey/ ist ein Unterpaket von agent-toolbox (agent-toolbox/survey/).
# → Python findet es automatisch wenn wir von agent-toolbox/ starten.
# → ABER: survey-cli/ ist ein Fallback (alte Survey-CLI Module).
# → Wir fügen BEIDE hinzu: agent-toolbox/ zuerst (hat Vorrang!), dann survey-cli/.
# → Wenn ein Modul in agent-toolbox/survey/ existiert → wird verwendet.
# → Wenn nicht → Fallback zu survey-cli/survey/.
# WARNUNG: Keine circular imports! Reihenfolge der Imports ist wichtig.

# Füge agent-toolbox/ zu sys.path hinzu (Parent von api/).
# WARUM str()? sys.path erwartet Strings, Path ist ein Objekt.
sys.path.insert(0, str(Path(__file__).parent.parent))

# Füge survey-cli/ zu sys.path hinzu (Sibling von agent-toolbox/).
# WARUM Fallback? Manche Module (runner.py, scanner.py) sind noch in survey-cli/.
# → Wenn sie später nach agent-toolbox/ migriert werden → werden automatisch verwendet.
# → Weil agent-toolbox/ zuerst in sys.path steht (Zeile 172) hat es VORRANG.
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "survey-cli"))

# ═══════════════════════════════════════════════════════════════════════════════
# SCHEMA IMPORTS: Alle Pydantic-Modelle
# ═══════════════════════════════════════════════════════════════════════════════
# WARUM alle auf einmal importieren?
# → Zentrale Import-Stelle: Alle Schemas kommen aus api/schemas.py.
# → Wenn ein Schema fehlt → ImportError SOFORT beim Start (nicht erst bei Request).
# → Das ist OK weil schemas.py keine schweren Dependencies hat (nur pydantic).
from api.schemas import (
    # ── Browser Schemas ──
    # Request/Response für POST /browser/start
    BrowserStartRequest,      # profile_name, headless, cdp_port
    BrowserStartResponse,     # status, profile, headless, cdp_port, message
    # Response für POST /browser/stop
    BrowserStopResponse,      # status, message
    # Response für GET /browser/health
    BrowserHealthResponse,    # running, profile, last_used, idle_seconds

    # ── Login Schemas ──
    # Request für POST /services/heypiggy/login
    LoginRequest,             # profile_name, headless, timeout_ms, pid, cdp_port
    # Response für POST /services/heypiggy/login
    LoginResponse,            # status, service, profile, message, details

    # ── Cookie Schemas ──
    # Request/Response für POST /tools/extract-cookies (Legacy-Endpoint)
    CookieExtractRequest,     # profile_name, domain_filter, save_to_file, filename
    CookieExtractResponse,    # status, profile, cookies, count

    # ── Utility Schemas ──
    NavigateRequest,          # profile_name, url, wait_until
    NavigateResponse,         # status, profile, url, title
    ScreenshotRequest,        # profile_name, full_page, selector
    ScreenshotResponse,       # status, profile, base64_image, mime_type
    PageContentRequest,       # profile_name, selector, max_length
    PageContentResponse,      # status, profile, url, title, text, html_length

    # ── Error Schema ──
    ErrorResponse,            # status, error_code, message, details
)

# ═══════════════════════════════════════════════════════════════════════════════
# ROUTER IMPORTS: API-Sub-Router für spezialisierte Endpoints
# ═══════════════════════════════════════════════════════════════════════════════
# WARUM Router statt alles in main.py?
# → Modularität: survey_actions.py, cookie_routes.py, dashboard_routes.py
#   können unabhängig entwickelt und getestet werden.
# → Übersichtlichkeit: main.py bleibt schlank (~400 Lines statt 2000+).
# → FastAPI-Router erben Prefix und Tags (z.B. prefix="/survey", tags=["survey"]).

# survey_actions.py Router: Alle Survey-Interaktionen (click-card, modal, etc.)
# Prefix: /survey (definiert in survey_actions.py: APIRouter(prefix="/survey"))
from api.survey_actions import router as survey_router

# cookie_routes.py Router: Cookie-Management (extract, inject, verify)
# Prefix: /cookies (definiert in cookie_routes.py)
from api.cookie_routes import router as cookie_router

# dashboard_routes.py Router: Dashboard-Scanning und Balance
# Prefix: /dashboard (definiert in dashboard_routes.py)
from api.dashboard_routes import router as dashboard_router
from api.workflow_routes import router as workflow_router


# ═══════════════════════════════════════════════════════════════════════════════
# LAZY-LOADER: Schweren Code erst bei ERSTEM Zugriff laden
# ═══════════════════════════════════════════════════════════════════════════════
# WARUM Lazy-Loading?
# → Playwright ist SCHWER (Chromium-Binary, ~150MB). Import dauert 2-5s.
# → survey.chrome hat Dependency (websocket-client für CDP WebSocket).
# → Wenn die API startet, brauchen wir Playwright NICHT sofort (nur wenn ein
#   Browser-Endpoint aufgerufen wird).
# → Mit Lazy-Loading: API startet in <1s. Ohne: 5-10s.
# → Wenn ein Modul fehlt (z.B. websocket-client nicht installiert), crasht die API NICHT
#   beim Start, sondern erst beim Zugriff. Fehlermeldung ist klar und hilfreich.
#
# WIE funktioniert Lazy-Loading?
# → Jeder Loader ist eine Funktion die beim ERSTEN Aufruf importiert.
# → Ergebnis wird NICHT gecacht (kein Singleton-Muster).
# → Bei jedem Aufruf wird ein NEUES Objekt erstellt.
#   Das ist beabsichtigt: BrowserManager ist selbst ein Singleton
#   (siehe browser_manager.py).
#
# BANNED: Keine globalen schweren Imports (z.B. "from playwright import ...").
# → Das würde den Startup verlangsamen und die API zerbrechlich machen.


def _get_bm():
    """
    Lazy-Load BrowserManager — erstellt eine neue Instanz bei jedem Aufruf.
    
    WARUM "_get_bm" statt "bm"?
    → Naming-Konvention: "_" Prefix = interne Funktion (nicht für Clients).
    → "get" = Factory/Getter-Muster (erzeugt/erhält ein Objekt).
    → "bm" = Abkürzung für BrowserManager (kurz, da oft verwendet).
    
    WARUM try/except ImportError?
    → Wenn playwright nicht installiert ist → ImportError.
    → Wir fangen den ab und geben eine HELPFUL Fehlermeldung zurück.
    → Ohne try/except → roher ImportError, Client weiß nicht was zu tun ist.
    
    WARUM RuntimeError mit Install-Hinweis?
    → RuntimeError wird von FastAPI als 500-Fehler behandelt.
    → Die Message erscheint im Response Body (sichtbar für Client).
    → "Install: python3.11 -m pip install playwright && playwright install chromium"
      gibt dem Client eine konkrete Lösung.
    
    WARUM BrowserManager() jedes Mal neu?
    → BrowserManager ist SELBST ein Singleton (siehe browser_manager.py).
    → Mehrere Aufrufe von BrowserManager() geben dieselbe Instanz zurück.
    → Wir verlassen uns auf das Singleton-Muster im Core.
    
    Returns:
        BrowserManager-Instanz (Singleton aus core/browser_manager.py)
    
    Raises:
        RuntimeError: Wenn playwright nicht installiert ist.
    
    Example:
        bm = _get_bm()  # Erster Aufruf → lädt Playwright (2s)
        bm2 = _get_bm()  # Zweiter Aufruf → gibt dieselbe Instanz zurück (0ms)
    """
    # Versuche Playwright/BrowserManager zu importieren.
    # Wenn playwright nicht installiert → ImportError.
    try:
        # core.browser_manager: Unser BrowserManager (SINator-Style).
        # Siehe browser_manager.py für Details.
        from core.browser_manager import BrowserManager
    except ImportError as e:
        # Import fehlgeschlagen → gebe klare Fehlermeldung zurück.
        # Die Fehlermeldung enthält Installations-Anweisungen.
        raise RuntimeError(
            "BrowserManager requires playwright. Install: "
            "python3.11 -m pip install playwright && playwright install chromium"
        ) from e
    
    # Erstelle BrowserManager-Instanz.
    # AUCH wenn BrowserManager ein Singleton ist, rufen wir den Konstruktor auf.
    # Der Konstruktor gibt die Singleton-Instanz zurück (siehe browser_manager.py).
    return BrowserManager()


def _get_auth_flow():
    """
    Lazy-Load Auth-Flow Module — Google OAuth Login (CUA-Fallback).
    
    WARUM Auth-Flow lazy laden?
    → Google OAuth Flow benötigt cua-driver (macOS Accessibility Binary).
    → cua-driver ist ein externes Binary, nicht immer verfügbar.
    → Lazy-Loading = API startet schneller, Module nur bei CUA-Login geladen.
    
    WARUM survey.auth aus agent-toolbox/survey/ (NICHT survey-cli/)?
    → Wir haben auth/ Module in agent-toolbox/survey/ kopiert (Self-Contained).
    → sys.path hat agent-toolbox/ VOR survey-cli/ → agent-toolbox/survey/ gewinnt.
    → Wenn Module nicht in agent-toolbox/ → Fallback zu survey-cli/.
    
    WARUM drei Klassen zurückgeben?
    → GoogleOAuthFlow: Haupt-Login-Logik (CUA-basiert wegen Shadow-DOM).
    → LoginVerifier: Prüft ob Login erfolgreich war (Dashboard-Elemente).
    → CuaAdapter: Adapter für cua-driver Kommunikation.
    → Alle drei werden von heypiggy_login() im mode="cua" benötigt.
    
    Returns:
        Tuple[Type, Type, Type]: (GoogleOAuthFlow, LoginVerifier, CuaAdapter)
    
    Raises:
        RuntimeError: Wenn cua-driver fehlt oder survey.auth nicht importierbar.
    
    Example:
        GoogleOAuthFlow, LoginVerifier, CuaAdapter = _get_auth_flow()
        flow = GoogleOAuthFlow(CuaAdapter(), LoginVerifier())
    """
    # Versuche survey.auth zu importieren.
    # Enthält GoogleOAuthFlow, LoginVerifier, CuaAdapter.
    # AUFGRUND sys.path (agent-toolbox/ zuerst) wird agent-toolbox/survey/ verwendet.
    try:
        from survey.auth import GoogleOAuthFlow, LoginVerifier, CuaAdapter
    except ImportError as e:
        # Import fehlgeschlagen (cua-driver nicht installiert oder fehlende Dependencies).
        raise RuntimeError(
            f"Auth modules require cua-driver. Install: brew install cua-driver. Error: {e}"
        ) from e
    
    # Gebe alle drei Klassen zurück.
    return GoogleOAuthFlow, LoginVerifier, CuaAdapter


# ═══════════════════════════════════════════════════════════════════════════════
# DOTENV: Umgebungsvariablen aus .env Datei laden
# ═══════════════════════════════════════════════════════════════════════════════
# WARUM dotenv?
# → Ermöglicht Konfiguration via Datei statt Umgebungsvariablen.
# → .env Datei enthält z.B. BROWSER_HEADLESS=true, OPENAI_API_KEY=..., etc.
# → Wird NICHT ins Git committed (in .gitignore).
# → Wichtig für lokale Entwicklung: Jeder Entwickler kann eigene .env haben.
#
# WARUM load_dotenv hier?
# → Muss VOR der ersten Verwendung von os.getenv() aufgerufen werden.
# → os.getenv("BROWSER_HEADLESS") wird in browser_start() verwendet.
# → Wenn wir load_dotenv erst in browser_start() aufrufen würden → zu spät.
#
# WARUM Path(__file__).parent.parent / ".env"?
# → __file__ = api/main.py
# → parent = api/
# → parent.parent = agent-toolbox/
# → agent-toolbox/.env = die .env Datei im Projekt-Root.
# → Path("/a") / ".env" = Path("/a/.env") — plattform-unabhängig.

# python-dotenv Paket: Lädt .env Datei in os.environ.
from dotenv import load_dotenv

# Lade .env aus dem Projekt-Root (agent-toolbox/.env).
# Wenn .env nicht existiert → keine Fehlermeldung (load_dotenv ist robust).
load_dotenv(Path(__file__).parent.parent / ".env")


# ═══════════════════════════════════════════════════════════════════════════════
# FASTAPI APP INITIALISIERUNG
# ═══════════════════════════════════════════════════════════════════════════════
# WARUM FastAPI-Klasse?
# → FastAPI ist das Haupt-Objekt der Anwendung.
# → Es registriert Router, Endpoints, Middleware, Exception Handler.
# → Uvicorn (ASGI-Server) benötigt diese Instanz: uvicorn.run(app, ...).
#
# WARUM title/version/docs_url/redoc_url?
# → title: Name der API (erscheint in Swagger UI).
# → version: API-Version (für Versionierung und Breaking Changes).
# → docs_url: Pfad zur Swagger UI (Standard: /docs).
#   Wir setzen es explizit damit es dokumentiert ist (auch wenn es der Default ist).
# → redoc_url: Pfad zur ReDoc-Dokumentation (alternativ zu Swagger).
#
# WARUM description?
# → Erscheint in Swagger UI als Beschreibung der API.
# → Hilft Agenten (und Menschen) zu verstehen was diese API tut.

app = FastAPI(
    # API-Titel (erscheint in Swagger UI und ReDoc).
    title="Agent-Toolbox API",
    
    # API-Beschreibung (erscheint in Swagger UI).
    description="High-Performance Automation Endpoints for Browser, Login, and Survey Tasks",
    
    # API-Version (SemVer: MAJOR.MINOR.PATCH).
    # MAJOR: Breaking Changes (z.B. Endpoint entfernt).
    # MINOR: Neue Features (z.B. neuer Endpoint).
    # PATCH: Bugfixes (z.B. Fix in bestehendem Endpoint).
    version="1.0.0",
    
    # Swagger UI URL.
    # Standard ist /docs, wir setzen es explizit für Dokumentationszwecke.
    docs_url="/docs",
    
    # ReDoc URL (alternative Dokumentation, besser lesbar).
    redoc_url="/redoc",
)

# ═══════════════════════════════════════════════════════════════════════════════
# ROUTER REGISTRIERUNG: Sub-Router in Haupt-App einbinden
# ═══════════════════════════════════════════════════════════════════════════════
# WARUM app.include_router()?
# → FastAPI-Router können unabhängig definiert werden (in anderen Dateien).
# → Durch include_router() werden sie in die Haupt-App eingebunden.
# → Der Prefix und die Tags aus dem Router werden übernommen.
#
# WARUM survey_router zuerst?
# → Survey-Router hat die meisten Endpoints (7 Endpoints).
# → Er wird am häufigsten aufgerufen (Haupt-Anwendungsfall).
# → Reihenfolge hat KEINE technische Bedeutung (nur organisatorisch).
#
# WARUM cookie_router und dashboard_router?
# → cookie_router: /cookies/extract, /cookies/inject, /cookies/verify
# → dashboard_router: /dashboard/scan, /dashboard/balance
# → Beide wurden in vorherigen Commits hinzugefügt.
# → WARUM registerieren wir sie hier? Denn main.py ist der EINSTIEGSPUNKT.
#   Wenn Router nicht registriert sind → Endpoints sind NICHT erreichbar.

# Registriere Survey-Router (prefix="/survey", tags=["survey"]).
# Endpoints: POST /survey/click-card, GET /survey/modal, etc.
app.include_router(survey_router)

# Registriere Cookie-Router (prefix="/cookies", tags=["Cookie Management"]).
# Endpoints: POST /cookies/extract, POST /cookies/inject, POST /cookies/verify.
app.include_router(cookie_router)

# Registriere Dashboard-Router (prefix="/dashboard", tags=["Dashboard"]).
# Endpoints: POST /dashboard/scan, POST /dashboard/balance.
app.include_router(dashboard_router)

# Registriere Workflow-Router (prefix="/workflow", tags=["Workflow"]).
# Endpoints: POST /workflow/run-best.
app.include_router(workflow_router)


# ═══════════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════════
# SEKTION 1: BROWSER ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════
# Diese Endpoints steuern den Browser-Lifecycle:
# - Start: Chrome mit Profil-Kopie starten
# - Stop: Chrome beenden und aufräumen
# - Health: Status prüfen (läuft? wie lange idle?)
#
# DER BROWSER IST DIE FOUNDATION:
# Ohne laufenden Chrome funktionieren ALLE anderen Endpoints NICHT.
# Jeder Survey-Endpoint prüft zuerst ob Chrome läuft (via BrowserManager).
# ═══════════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════════


@app.post("/browser/start", response_model=BrowserStartResponse)
async def browser_start(req: BrowserStartRequest):
    """
    Startet Chrome oder verwendet eine bestehende Instanz.
    
    ABLAUF:
    1. Lazy-Load BrowserManager (Playwright wird hier erst geladen).
    2. Bestimme headless-Modus:
       - Wenn req.headless is not None → verwende req.headless (Request override).
       - Sonst → lese aus Umgebungsvariable BROWSER_HEADLESS ("true"/"false").
       - Sonst → default true (headless).
    3. Rufe bm.start() auf mit Profil, headless, CDP-Port.
    4. BrowserManager startet Chrome via subprocess mit CDP-Port 9999.
    5. Warte bis CDP erreichbar ist (Polling auf /json/version).
    6. Verbinde Playwright via connect_over_cdp().
    7. Injiziere Stealth-JS (Bot-Detection-Umgehung).
    8. Gebe Response zurück mit Status und Warm/Cold-Info.
    
    WARUM headless-Logik so komplex?
    → Drei Ebenen: Request-Override → Env-Variable → Default.
    → Das ermöglicht maximale Flexibilität:
      - Client kann explizit sichtbar/unsichtbar anfordern.
      - .env Datei kann Default setzen (für Docker: headless=true).
      - Wenn nichts gesetzt → headless=true (sicherster Default für Server).
    
    WARUM "warm" vs "cold"?
    → Warm = Chrome war bereits aktiv, wurde wiederverwendet (~0ms).
    → Cold = Chrome musste neu gestartet werden (~2-5s).
    → Performance-Monitoring: Wenn immer "cold" → evtl. Chrome crasht oder wird beendet.
    → BrowserManager trackt last_used Zeitstempel (siehe browser_manager.py).
    
    WARUM try/except um ALLES?
    → Jeder Fehler (Chrome starten fehlgeschlagen, Playwright nicht installiert,
      Port belegt, etc.) wird als HTTPException(500) zurückgegeben.
    → Client bekommt klare Fehlermeldung statt interner Server-Fehler (500).
    → Keine rohen Tracebacks (nur mit debug=True).
    
    Args:
        req: BrowserStartRequest mit profile_name, headless, cdp_port.
    
    Returns:
        BrowserStartResponse: status, profile, headless, cdp_port, message.
        Message enthält "(warm)" oder "(cold)" für Performance-Tracking.
    
    Raises:
        HTTPException(500): Wenn Chrome nicht gestartet werden kann.
    
    Example:
        POST /browser/start
        {"profile_name": "default", "headless": false}
        → {"status": "success", "profile": "default", "headless": false,
            "cdp_port": 9999, "message": "Browser started (cold)"}
    """
    # Versuche Browser zu starten.
    # Jeder Fehler wird als HTTPException(500) zurückgegeben.
    try:
        # Lazy-Load BrowserManager (Playwright wird hier erst importiert).
        # Wenn Playwright nicht installiert → RuntimeError mit Install-Hinweis.
        bm = _get_bm()
        
        # Bestimme headless-Modus (drei Ebenen).
        # Ebene 1: Request-Override (wenn Client explizit headless sendet).
        # Ebene 2: Umgebungsvariable BROWSER_HEADLESS (aus .env oder System).
        # Ebene 3: Default true (sicherster Default für Server-Umgebungen).
        headless = req.headless if req.headless is not None else (
            # os.getenv gibt String zurück (z.B. "true"). .lower() für Case-Insensitivity.
            # == "true" wandelt in Bool um.
            os.getenv("BROWSER_HEADLESS", "true").lower() == "true"
        )
        
        # Starte Browser (oder wiederverwende bestehende Instanz).
        # bm.start() ist async (await nötig wegen Playwright connect_over_cdp).
        # Rückgabe: BrowserContext (Playwright-Objekt für Tabs/Pages).
        ctx = await bm.start(
            profile_name=req.profile_name,  # Profil-Name (default: "default")
            headless=headless,              # Sichtbar oder unsichtbar
            cdp_port=req.cdp_port,          # CDP Port (default: 9999)
        )
        
        # Erstelle Response.
        # WARUM "warm" vs "cold"?
        # → bm._last_used > 0 bedeutet: Browser war bereits aktiv (wiederverwendet).
        # → bm._last_used == 0 bedeutet: Browser war inaktiv (neu gestartet).
        # → _last_used ist ein Unix-Timestamp (siehe browser_manager.py).
        # → ACHTUNG: _last_used ist ein internes Feld (eigentlich "private").
        #   Wir verwenden es hier nur für die Warm/Cold-Info.
        return BrowserStartResponse(
            status="success",              # Immer "success" wenn wir hier ankommen
            profile=req.profile_name,       # Bestätigung: welches Profil verwendet
            headless=headless,              # Tatsächlich verwendeter Modus
            cdp_port=req.cdp_port,          # Tatsächlich verwendeter Port
            # "warm" wenn _last_used > 0 (bereits aktiv), sonst "cold" (neu gestartet).
            message="Browser started (warm)" if bm._last_used > 0 else "Browser started (cold)",
        )
    
    except Exception as e:
        # Fehler beim Starten des Browsers.
        # Wir geben HTTPException(500) zurück mit der Fehlermeldung.
        # Die Fehlermeldung erscheint im Response Body unter "detail".
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/browser/stop", response_model=BrowserStopResponse)
async def browser_stop():
    """
    Beendet Chrome und räumt das temporäre Profil auf.
    
    ABLAUF:
    1. Lazy-Load BrowserManager.
    2. Rufe bm.stop() auf.
    3. BrowserManager:
       - Schließt Playwright-Browser (await browser.close()).
       - Stoppt Playwright (await playwright.stop()).
       - Beendet Chrome-Prozess (proc.terminate() / proc.kill()).
       - Löscht temporäres Profil-Verzeichnis (shutil.rmtree).
    4. Gibt Erfolgs-Response zurück.
    
    WARUM stop() wichtig?
    → Jeder Chrome-Prozess belegt ~200-500MB RAM.
    → Wenn Chrome nicht beendet wird → Memory-Leak.
    → Temp-Profil-Verzeichnis belegt ~50-100MB Disk.
    → Wenn nicht aufgeräumt → Disk-Full über Zeit.
    
    WARUM idempotent?
    → Wenn Chrome nicht läuft → bm.stop() gibt {"status": "not_running"} zurück.
    → Wir verpacken das in BrowserStopResponse(status="success").
    → Client kann stop() mehrfach aufrufen ohne Fehler.
    
    WARUM await?
    → bm.stop() ist async (Playwright close/stop sind async).
    → Ohne await → Race Condition: Response wird gesendet BEVOR Chrome beendet ist.
    
    Returns:
        BrowserStopResponse: status="success", message="Browser stopped".
    
    Raises:
        HTTPException(500): Wenn Aufräumen fehlschlägt (selten).
    
    Example:
        POST /browser/stop
        → {"status": "success", "message": "Browser stopped"}
    """
    # Versuche Browser zu stoppen.
    try:
        # Lazy-Load BrowserManager.
        bm = _get_bm()
        
        # Stoppe Browser (async wegen Playwright cleanup).
        await bm.stop()
        
        # Erfolgs-Response.
        return BrowserStopResponse(
            status="success",
            message="Browser stopped",
        )
    
    except Exception as e:
        # Fehler beim Stoppen (z.B. Chrome-Prozess hat sich selbst beendet).
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/browser/health", response_model=BrowserHealthResponse)
async def browser_health():
    """
    Prüft den aktuellen Zustand des Browsers.
    
    ABLAUF:
    1. Lazy-Load BrowserManager.
    2. Rufe bm.health() auf.
    3. BrowserManager prüft:
       - Läuft Chrome noch? (proc.poll() ist None → läuft).
       - Ist CDP erreichbar? (HTTP GET auf /json/version).
       - Wann war die letzte Nutzung? (last_used Timestamp).
    4. Berechne idle_seconds = time.time() - last_used.
    5. Gib Response zurück.
    
    WARUM health wichtig?
    → Client kann VOR einem Survey-Lauf prüfen ob Chrome läuft.
    → Wenn idle_seconds > 300 (5min) → Chrome könnte abgestürzt sein.
    → Wenn running=False → Client ruft POST /browser/start auf.
    
    WARUM GET statt POST?
    → Health ist eine READ-Operation (keine Seiteneffekte).
    → GET ist semantisch korrekt für Read-Only.
    → POST wäre falsch (keine Zustandsänderung).
    
    WARUM kein try/except?
    → bm.health() kann nicht fehlschlagen (nur Status-Abfrage, keine I/O).
    → Wenn bm.health() fehlschlägt → Server-Fehler (500) ist korrekt.
    
    Returns:
        BrowserHealthResponse: running, profile, last_used, idle_seconds.
    
    Example:
        GET /browser/health
        → {"running": true, "profile": "Profile 73", "last_used": 1778261390.45,
            "idle_seconds": 45.2}
    """
    # Lazy-Load BrowserManager.
    bm = _get_bm()
    
    # Rufe health() auf und gebe direkt zurück.
    # bm.health() gibt ein Dict zurück: {running, profile, last_used, idle_seconds}.
    # BrowserHealthResponse(**dict) entpackt das Dict in Keyword-Argumente.
    return BrowserHealthResponse(**await bm.health())


# ═══════════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════════
# SEKTION 2: SERVICE ENDPOINTS (HeyPiggy Login)
# ═══════════════════════════════════════════════════════════════════════════════
# Dieser Endpoint automatisiert den Google OAuth Login für HeyPiggy.
# DAS IST DER SCHWIERIGSTE ENDPOINT weil Google Shadow-DOM verwendet.
# ═══════════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════════


@app.post("/services/heypiggy/login", response_model=LoginResponse)
async def heypiggy_login(req: LoginRequest):
    """
    Loggt sich bei HeyPiggy via Google OAuth ein.
    
    ABLAUF:
    1. Wenn req.pid is None → Suche bestehenden Bot-Chrome via lsof.
       lsof -i TCP:PORT -t gibt die PID des Prozesses zurück der auf diesem Port hört.
    2. Wenn kein Chrome gefunden → starte neuen Chrome via ChromeLauncher.
       ChromeLauncher.launch_and_verify() startet Chrome mit CDP-Port und accessibility flags.
    3. Initialisiere Auth-Flow:
       GoogleOAuthFlow(CuaAdapter(), LoginVerifier()).
    4. Führe flow.execute(pid=pid) aus.
       Der Flow klickt Google-Login-Symbol, füllt Email, klickt Weiter,
       verarbeitet Keychain Auto-Fill, klickt Fortfahren, etc.
    5. Prüfe Ergebnis:
       - "ok" → Login erfolgreich.
       - "already_logged_in" → Bereits eingeloggt (Session gültig).
       - "error" → Fehlgeschlagen (Details in message).
    6. Gib Response zurück.
    
    WARUM so komplex?
    → Google OAuth verwendet Shadow-DOM (nicht via normales CDP/Playwright zugänglich).
    → CUA (macOS Accessibility) ist der EINZIGE Weg Shadow-DOM-Elemente zu erreichen.
    → Der Flow ist in survey/auth.py implementiert (wird lazy geladen).
    
    WARUM pid Optional?
    → Wenn gesetzt → verwende EXAKT diesen Chrome (Cookie-Persistenz).
    → Wenn None → suche bestehenden Chrome oder starte neuen.
    → Das ermöglicht Cookie-basierte Re-Login (Session bleibt bestehen).
    
    WARUM ChromeLauncher statt BrowserManager?
    → BrowserManager verwendet Playwright (CDP-basiert).
    → ChromeLauncher verwendet subprocess.Popen (für CUA-Kompatibilität).
    → CUA erfordert einen echten macOS-Prozess (nicht headless).
    → BrowserManager ist für CDP-basierte Operationen (Survey-Automation).
    → ChromeLauncher ist für CUA-basierte Operationen (Google Login).
    
    WARUM lsof?
    → lsof (List Open Files) zeigt welcher Prozess auf einem Port hört.
    → "lsof -i TCP:9999 -t" gibt nur die PID zurück (keine Extra-Output).
    → Das ist schneller und zuverlässiger als "ps aux | grep Chrome".
    → WARNUNG: lsof funktioniert nur auf macOS/Linux (nicht Windows).
    
    WARUM LoginVerifier?
    → Nach dem Login muss geprüft werden ob wir WIRKLICH eingeloggt sind.
    → LoginVerifier navigiert zum Dashboard und prüft auf "abmelden" Button.
    → Ohne Verifikation → Client denkt Login war OK, aber Session ist tot.
    
    Args:
        req: LoginRequest mit profile_name, headless, timeout_ms, pid, cdp_port.
    
    Returns:
        LoginResponse: status ("success"/"already_logged_in"/"error"),
                       service, profile, message, details (pid, wid).
    
    Raises:
        HTTPException(500): Bei unerwarteten Fehlern.
    
    Example:
        POST /services/heypiggy/login
        {"mode": "cookie", "cdp_port": 9999}
        → {"status": "already_logged_in", "service": "heypiggy", "profile": "default",
            "message": "Session valid via cookies", "details": {"pid": 34852}}
        
        POST /services/heypiggy/login
        {"mode": "cua", "cdp_port": 9999}
        → {"status": "success", "service": "heypiggy", "profile": "default",
            "message": "Login successful", "details": {"pid": 34852, "wid": 56640}}
    """
    try:
        # ═══════════════════════════════════════════════════════════════════════
        # MODE: COOKIE (Schneller Cookie-Inject + Session-Verify)
        # ═══════════════════════════════════════════════════════════════════════
        if req.mode == "cookie":
            # Lazy-Load CookieManager (nur im Cookie-Mode nötig).
            from core.cookie_manager import get_cookie_manager
            
            # CookieManager mit absolutem Pfad erstellen.
            # WARUM absoluter Pfad? API-CWD ist /Users/jeremy/dev/stealth-runner/
            # → ./data wäre /Users/jeremy/dev/stealth-runner/data/ (FALSCH).
            # → Absoluter Pfad: agent-toolbox/data/ (RICHTIG).
            from core.cookie_manager import CookieManager
            cookie_dir = Path(__file__).parent.parent / "data"
            cookie_mgr = CookieManager(cookies_dir=str(cookie_dir))
            
            # Lazy-Load BrowserManager (für Cookie-Inject).
            bm = _get_bm()
            
            # Browser starten (oder bestehenden verwenden).
            # bm.start() startet Chrome mit Profil-Kopie und CDP-Verbindung.
            ctx = await bm.start(profile_name=req.profile_name)
            
            # Cookies aus gespeicherter Datei laden und injecten.
            # load_cookies(filename) liest agent-toolbox/data/heypiggy-cookies.json.
            # inject_cookies(ctx, cookies) fügt sie in BrowserContext ein.
            try:
                cookies = cookie_mgr.load_cookies("heypiggy-cookies.json")
                if cookies:
                    await cookie_mgr.inject_cookies(ctx, cookies)
            except FileNotFoundError:
                # Cookie-Datei nicht vorhanden → Cookie-Login nicht möglich.
                cookie_path = cookie_dir / "heypiggy-cookies.json"
                return LoginResponse(
                    status="error",
                    service="heypiggy",
                    profile=req.profile_name,
                    message="No saved cookies found. Use mode='cua' for Google OAuth login.",
                    details={"mode": "cookie", "hint": f"No cookie file at {cookie_path}"},
                )
            
            # Seite neu laden damit Cookies wirksam werden.
            page = ctx.pages[0] if ctx.pages else await ctx.new_page()
            await page.goto("https://www.heypiggy.com/?page=dashboard")
            await page.wait_for_load_state("networkidle")
            
            # Session verifizieren: Prüfe ob "abmelden" oder Balance sichtbar.
            is_valid = await cookie_mgr.verify_session(ctx)
            
            if is_valid:
                # Session gültig! Cookies haben funktioniert.
                # PID aus BrowserManager holen (wenn verfügbar).
                pid_info = None
                if hasattr(bm, '_process') and bm._process:
                    pid_info = bm._process.pid
                
                return LoginResponse(
                    status="already_logged_in",
                    service="heypiggy",
                    profile=req.profile_name,
                    message="Session valid via cookies",
                    details={"pid": pid_info, "mode": "cookie"},
                )
            
            # Cookies haben NICHT funktioniert → Session abgelaufen.
            # Gib klare Fehlermeldung zurück mit Hinweis auf CUA-Mode.
            return LoginResponse(
                status="error",
                service="heypiggy",
                profile=req.profile_name,
                message="Cookie session expired. Retry with mode='cua' for Google OAuth fallback.",
                details={"mode": "cookie", "hint": "Use mode='cua' for full Google OAuth login"},
            )
        
        # ═══════════════════════════════════════════════════════════════════════
        # MODE: CUA (Vollständiger Google OAuth via macOS Accessibility)
        # ═══════════════════════════════════════════════════════════════════════
        # WARUM CUA? Google OAuth verwendet Shadow-DOM (nicht via CDP/Playwright).
        # CUA (Accessibility API) ist der EINZIGE Weg diese Elemente zu erreichen.
        # Dieser Mode klickt: Google-Login-Symbol → Email → Weiter → Fortfahren → Weiter.
        
        # Initialisiere pid mit Request-Wert (kann None sein).
        pid = req.pid
        
        # Wenn keine PID angegeben → suche bestehenden Chrome.
        if pid is None:
            import subprocess
            
            # lsof: List Open Files. "-i TCP:PORT" = zeige Netzwerk-Verbindungen auf diesem Port.
            # "-t" = nur PID ausgeben (keine Header, keine Extra-Info).
            result = subprocess.run(
                ["lsof", "-i", f"TCP:{req.cdp_port}", "-t"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.stdout.strip():
                for line in result.stdout.strip().split("\n"):
                    if line.strip().isdigit():
                        pid = int(line.strip())
                        break
        
        # Chrome starten wenn keine PID gefunden.
        if pid is None:
            # Lazy-Load ChromeLauncher (aus survey.chrome, jetzt in agent-toolbox/survey/).
            from survey.chrome import ChromeLauncher
            
            launcher = ChromeLauncher(port=req.cdp_port, debug=True)
            launch_result = launcher.launch_and_verify(
                url="https://www.heypiggy.com/?page=dashboard"
            )
            
            if not launch_result.get("ok"):
                return LoginResponse(
                    status="error",
                    service="heypiggy",
                    profile=req.profile_name,
                    message=f"chrome_launch_failed: {launch_result.get('error', 'unknown')}",
                    details={"step": launch_result.get("step"), "mode": "cua"},
                )
            
            pid = launch_result.get("pid")
        
        # Auth-Flow laden und ausführen.
        GoogleOAuthFlow, LoginVerifier, CuaAdapter = _get_auth_flow()
        flow = GoogleOAuthFlow(CuaAdapter(), LoginVerifier())
        result = flow.execute(pid=pid)
        
        # Ergebnis verarbeiten.
        if result.status == "ok":
            # Login erfolgreich! Cookies speichern für zukünftige Cookie-Logins.
            try:
                from core.cookie_manager import CookieManager
                cookie_dir = Path(__file__).parent.parent / "data"
                cookie_mgr = CookieManager(cookies_dir=str(cookie_dir))
                bm = _get_bm()
                ctx = await bm.start(profile_name=req.profile_name)
                page = ctx.pages[0] if ctx.pages else await ctx.new_page()
                await page.goto("https://www.heypiggy.com/?page=dashboard")
                await page.wait_for_load_state("networkidle")
                cookies = await cookie_mgr.extract_cookies(page, domain_filter="heypiggy")
                cookie_mgr.save_cookies(cookies, "heypiggy-cookies.json")
            except Exception:
                # Cookie-Extraktion ist nice-to-have, nicht kritisch.
                pass
            
            return LoginResponse(
                status="success",
                service="heypiggy",
                profile=req.profile_name,
                message="Login successful via CUA (Google OAuth)",
                details={"pid": result.pid, "wid": result.wid, "mode": "cua"},
            )
        
        elif result.status == "already_logged_in":
            return LoginResponse(
                status="already_logged_in",
                service="heypiggy",
                profile=req.profile_name,
                message="Already logged in (CUA verified)",
                details={"pid": result.pid, "wid": result.wid, "mode": "cua"},
            )
        
        else:
            return LoginResponse(
                status="error",
                service="heypiggy",
                profile=req.profile_name,
                message=result.reason or "unknown_error",
                details={"pid": pid, "mode": "cua"},
            )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════════
# SEKTION 4: TOOL ENDPOINTS (Legacy + Utilities)
# ═══════════════════════════════════════════════════════════════════════════════
# Diese Endpoints bieten generische Browser-Tools.
# Sie sind nicht survey-spezifisch, sondern allgemeine Automation-Utilities.
# ═══════════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════════


@app.post("/tools/extract-cookies", response_model=CookieExtractResponse)
async def extract_cookies(req: CookieExtractRequest):
    """
    Extrahiert Cookies aus dem aktiven Browser (Legacy-Endpoint).
    
    WICHTIG:
    → Dieser Endpoint ist LEGACY. Verwende stattdessen POST /cookies/extract
      (aus cookie_routes.py Router). Der neue Endpoint hat mehr Features:
      - Cookie-Statistiken (domains, httpOnly, secure, session).
      - Automatisches Speichern in Datei.
      - Session-Verifikation.
    → Dieser Endpoint bleibt für Abwärtskompatibilität.
    
    ABLAUF:
    1. Lazy-Load BrowserManager.
    2. Starte/verwende Browser (bm.start()).
    3. Extrahiere Cookies vom aktuellen Context (ctx.cookies()).
    4. Wenn domain_filter gesetzt → filtere Cookies nach Domain.
    5. Gib Response zurück.
    
    WARUM Legacy?
    → Ursprünglich in main.py definiert (vor cookie_routes.py existierte).
    → Wird beibehalten damit bestehende Clients nicht brechen.
    → Neue Clients sollten /cookies/extract verwenden.
    
    Args:
        req: CookieExtractRequest mit profile_name, domain_filter.
    
    Returns:
        CookieExtractResponse: status, profile, cookies[], count.
    
    Raises:
        HTTPException(500): Bei Fehlern.
    """
    try:
        # Lazy-Load BrowserManager.
        bm = _get_bm()
        
        # Starte/verwende Browser (gibt BrowserContext zurück).
        ctx = await bm.start(profile_name=req.profile_name)
        
        # Extrahiere alle Cookies vom BrowserContext.
        # ctx.cookies() gibt eine Liste von Cookie-Dicts zurück.
        cookies = await ctx.cookies()
        
        # Wenn domain_filter gesetzt → filtere Cookies.
        # "heypiggy" matcht "heypiggy.com", ".heypiggy.com", etc.
        if req.domain_filter:
            cookies = [
                c for c in cookies
                if req.domain_filter in (c.get("domain") or "")
            ]
        
        # Response mit Cookies und Anzahl.
        return CookieExtractResponse(
            status="success",
            profile=req.profile_name,
            cookies=cookies,
            count=len(cookies),
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/navigate", response_model=NavigateResponse)
async def navigate(req: NavigateRequest):
    """
    Navigiert den Browser zu einer URL.
    
    ABLAUF:
    1. Lazy-Load BrowserManager.
    2. Hole aktive Page (bm.get_page()).
    3. Rufe page.goto(url, wait_until=...) auf.
    4. Extrahiere Seiten-Titel.
    5. Gib Response zurück.
    
    WARUM Utility?
    → Generische Operation: Nicht survey-spezifisch.
    → Kann für Debugging, URL-Wechsel, etc. verwendet werden.
    → Analog zu page.goto() in Playwright.
    
    WARUM wait_until?
    → "load" = warte auf window.onload (schnell, aber evtl. nicht alles geladen).
    → "domcontentloaded" = warte auf DOMContentLoaded (schnell).
    → "networkidle" = warte bis Netzwerk idle ist (langsam, aber alles geladen).
    → "networkidle" ist default weil es die robusteste Option ist.
    
    Args:
        req: NavigateRequest mit profile_name, url, wait_until.
    
    Returns:
        NavigateResponse: status, profile, url, title.
    
    Raises:
        HTTPException(500): Bei Fehlern.
    """
    try:
        # Lazy-Load BrowserManager.
        bm = _get_bm()
        
        # Hole aktive Page (erster Tab im Browser).
        page = await bm.get_page()
        
        # Navigiere zu URL mit angegebener Wait-Strategie.
        await page.goto(req.url, wait_until=req.wait_until)
        
        # Extrahiere Seiten-Titel (asynchron, da Playwright async ist).
        title = await page.title()
        
        return NavigateResponse(
            status="success",
            profile=req.profile_name,
            url=req.url,
            title=title,
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/screenshot", response_model=ScreenshotResponse)
async def screenshot(req: ScreenshotRequest):
    """
    Macht einen Screenshot der aktuellen Seite oder eines Elements.
    
    ABLAUF:
    1. Lazy-Load BrowserManager.
    2. Hole aktive Page (bm.get_page()).
    3. Wenn selector gesetzt → finde Element und mache Element-Screenshot.
       Sonst → mache Page-Screenshot (full_page oder Viewport).
    4. Kodiere Bild als Base64.
    5. Gib Response zurück.
    
    WARUM base64?
    → JSON kann keine Binär-Daten direkt enthalten.
    → Base64 ist der Standard für Bilder in JSON.
    → Client kann base64 direkt in <img src="data:image/png;base64,..."> verwenden.
    
    WARUM selector Optional?
    → None = ganze Seite (häufigster Use-Case: "Was sehe ich gerade?").
    → Selector = spezifisches Element (z.B. "#error-message" für Fehler-Details).
    
    Args:
        req: ScreenshotRequest mit profile_name, full_page, selector.
    
    Returns:
        ScreenshotResponse: status, profile, base64_image, mime_type.
    
    Raises:
        HTTPException(404): Wenn Element (selector) nicht gefunden.
        HTTPException(500): Bei anderen Fehlern.
    """
    try:
        # Lazy-Load BrowserManager.
        bm = _get_bm()
        
        # Hole aktive Page.
        page = await bm.get_page()
        
        # Prüfe ob ein spezifisches Element gescreenshotet werden soll.
        if req.selector:
            # Versuche Element zu finden.
            element = await page.query_selector(req.selector)
            
            if not element:
                # Element nicht gefunden → 404 Fehler.
                raise HTTPException(
                    status_code=404,
                    detail=f"Element not found: {req.selector}"
                )
            
            # Mache Element-Screenshot.
            screenshot_bytes = await element.screenshot()
        else:
            # Mache Page-Screenshot (full_page oder Viewport).
            screenshot_bytes = await page.screenshot(full_page=req.full_page)
        
        # Kodiere Bild als Base64.
        # base64.b64encode() gibt Bytes zurück, .decode() wandelt in String.
        import base64
        base64_image = base64.b64encode(screenshot_bytes).decode()
        
        return ScreenshotResponse(
            status="success",
            profile=req.profile_name,
            base64_image=base64_image,
        )
    
    except HTTPException:
        # Re-raise HTTPException (404 Element not found).
        raise
    except Exception as e:
        # Andere Fehler → 500.
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/page-content", response_model=PageContentResponse)
async def page_content(req: PageContentRequest):
    """
    Extrahiert Text-Inhalt von der aktuellen Seite.
    
    ABLAUF:
    1. Lazy-Load BrowserManager.
    2. Hole aktive Page (bm.get_page()).
    3. Extrahiere URL und Titel.
    4. Wenn selector gesetzt → extrahiere Text/HTML vom Element.
       Sonst → extrahiere gesamten Body-Text und HTML.
    5. Begrenze Text auf max_length (Performance/Size-Limit).
    6. Gib Response zurück.
    
    WARUM max_length?
    → Lange Seiten (Dashboard mit vielen Surveys) können 10.000+ Zeichen haben.
    → 5000 ist ein Kompromiss: genug für die meisten Seiten,
      nicht zu groß für JSON-Response.
    → Client kann bei Bedarf erneut mit höherem max_length abfragen.
    
    WARUM text UND html_length?
    → text = der extrahierte Text (für Analyse, Keyword-Suche).
    → html_length = Länge des HTML (für Performance-Monitoring).
    → html_length hilft: Wenn plötzlich html_length=0 → Seite leer (Fehler).
    
    Args:
        req: PageContentRequest mit profile_name, selector, max_length.
    
    Returns:
        PageContentResponse: status, profile, url, title, text, html_length.
    
    Raises:
        HTTPException(404): Wenn Element (selector) nicht gefunden.
        HTTPException(500): Bei anderen Fehlern.
    """
    try:
        # Lazy-Load BrowserManager.
        bm = _get_bm()
        
        # Hole aktive Page.
        page = await bm.get_page()
        
        # Extrahiere aktuelle URL (kein await nötig, page.url ist synchron).
        url = page.url
        
        # Extrahiere Seiten-Titel (asynchron).
        title = await page.title()
        
        # Prüfe ob ein spezifisches Element extrahiert werden soll.
        if req.selector:
            # Versuche Element zu finden.
            element = await page.query_selector(req.selector)
            
            if not element:
                # Element nicht gefunden → 404 Fehler.
                raise HTTPException(
                    status_code=404,
                    detail=f"Element not found: {req.selector}"
                )
            
            # Extrahiere Text und HTML vom Element.
            text = await element.inner_text()
            html = await element.inner_html()
        else:
            # Extrahiere gesamten Body-Text und HTML.
            # inner_text("body") gibt den sichtbaren Text zurück (kein HTML).
            text = await page.inner_text("body")
            # content() gibt den vollständigen HTML-Quelltext zurück.
            html = await page.content()
        
        # Begrenze Text auf max_length.
        # WARUM [:max_length]? Slicing in Python ist sicher (kein IndexError).
        # Wenn Text kürzer als max_length → wird unverändert zurückgegeben.
        text = text[:req.max_length]
        
        return PageContentResponse(
            status="success",
            profile=req.profile_name,
            url=url,
            title=title,
            text=text,
            html_length=len(html),
        )
    
    except HTTPException:
        # Re-raise HTTPException (404 Element not found).
        raise
    except Exception as e:
        # Andere Fehler → 500.
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════════
# SEKTION 5: GLOBALER EXCEPTION HANDLER
# ═══════════════════════════════════════════════════════════════════════════════
# Fängt ALLE unerwarteten Exceptions die nicht von einzelnen Endpoints
# gefangen wurden. Gibt einheitliche JSON-ErrorResponse zurück.
# ═══════════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════════


@app.exception_handler(Exception)
async def generic_exception_handler(request, exc):
    """
    Globaler Exception-Handler für ALLE unerwarteten Fehler.
    
    WARUM globaler Handler?
    → Wenn ein Endpoint eine Exception nicht fängt (z.B. ImportError,
      AttributeError, KeyError), würde FastAPI einen internen Server-Fehler
      (500) zurückgeben mit rohem HTML (nicht JSON).
    → Der globale Handler fängt ALLE Exceptions und gibt JSON zurück.
    → Das ist wichtig für API-Clients die JSON erwarten (nicht HTML).
    
    WARUM JSONResponse statt HTTPException?
    → HTTPException ist für Endpoints (wir sind im Handler, nicht im Endpoint).
    → JSONResponse ermöglicht vollständige Kontrolle über den Response Body.
    → Wir geben ErrorResponse als JSON zurück (Pydantic-Modell).
    
    WARUM ErrorResponse?
    → Einheitliches Fehler-Format für ALLE Endpoints.
    → Client kann auf error_code prüfen (z.B. "internal_error").
    → Keine rohen Tracebacks (nur mit debug=True).
    
    Args:
        request: FastAPI Request-Objekt (wird nicht verwendet, aber erforderlich).
        exc: Die aufgetretene Exception.
    
    Returns:
        JSONResponse: status_code=500, content=ErrorResponse als JSON.
    
    Example:
        Wenn ein Endpoint "KeyError: 'survey_id'" wirft:
        → {"status": "error", "error_code": "internal_error",
            "message": "'survey_id'", "details": null}
    """
    # Erstelle ErrorResponse aus der Exception.
    error_response = ErrorResponse(
        status="error",
        error_code="internal_error",
        message=str(exc),
    )
    
    # Gib als JSON-Response zurück.
    # status_code=500: Internal Server Error (unerwarteter Fehler).
    # content=error_response.model_dump(): Pydantic-Modell als Dict (JSON-serialisierbar).
    return JSONResponse(
        status_code=500,
        content=error_response.model_dump(),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# ENDE DER MAIN.PY
# ═══════════════════════════════════════════════════════════════════════════════
# ZUSAMMENFASSUNG:
#
# Diese Datei ist der EINSTIEGSPUNKT für die gesamte FastAPI-Anwendung.
# Sie definiert:
#   - FastAPI App-Instanz (mit Title, Version, Docs-URLs).
#   - Router-Registrierung (survey, cookies, dashboard).
#   - Lazy-Loader für schwere Dependencies (Playwright, cua-driver).
#   - 10+ Endpoints für Browser, Login, Survey, Cookies, Tools.
#   - Globalen Exception-Handler für einheitliche Fehler-Responses.
#
# DESIGN-PRINZIPIEN:
#   1. Lazy-Loading: Schwere Module erst bei Bedarf laden.
#   2. Fail-Closed: Bei Fehlern → klare HTTPException mit Detail-Meldung.
#   3. Idempotent: Gleiche Requests → gleiche Ergebnisse (wo möglich).
#   4. Self-Documenting: FastAPI /docs zeigt ALLE Endpoints automatisch an.
#   5. Type-Safe: Pydantic validiert jeden Request vor Code-Ausführung.
#   6. Modular: Router in separaten Dateien (survey_actions.py, cookie_routes.py, etc.).
#
# START DER API:
#   uvicorn api.main:app --host 0.0.0.0 --port 8889 --reload
#   → App läuft auf http://localhost:8889
#   → Swagger UI: http://localhost:8889/docs
#   → ReDoc: http://localhost:8889/redoc
# ═══════════════════════════════════════════════════════════════════════════════
