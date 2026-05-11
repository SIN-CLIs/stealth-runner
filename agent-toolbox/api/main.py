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
║    POST /services/heypiggy/login → Google OAuth Login (CUA-basiert)         ║
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
║  Alle schweren Imports (Playwright, survey-cli, openai) werden NICHT beim  ║
║  Startup geladen, sondern erst bei ERSTEM Zugriff (Lazy-Loading).         ║
║  WARUM?                                                                      ║
║  • API startet in <1s (statt 5-10s mit Playwright-Import).                 ║
║  • Wenn ein Modul fehlt (z.B. openai nicht installiert), crasht die API    ║
║    NICHT beim Start, sondern erst beim Zugriff auf den betroffenen Endpoint.║
║  • Fehlermeldung ist klar: "SurveyRunner requires openai. Install: ..."   ║
║  • Ermöglicht modulare Entwicklung: Browser-Endpoints funktionieren auch   ║
║    ohne survey-cli Dependencies.                                            ║
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
# → survey-cli/ ist ein separates Verzeichnis (kein Unterpaket von agent-toolbox).
# → Python findet es nicht automatisch wenn wir von agent-toolbox/api/main.py starten.
# → Lösung: Füge survey-cli/ zu sys.path hinzu (vor allen anderen Pfaden, Index 0).
# → AUCH: Füge agent-toolbox/ selbst hinzu damit "from api.schemas" funktioniert.
# WARNUNG: Keine circular imports! Reihenfolge der Imports ist wichtig.

# Füge agent-toolbox/ zu sys.path hinzu (Parent von api/).
# WARUM str()? sys.path erwartet Strings, Path ist ein Objekt.
sys.path.insert(0, str(Path(__file__).parent.parent))

# Füge survey-cli/ zu sys.path hinzu (Sibling von agent-toolbox/).
# WARUM? survey/ Module (runner.py, auth.py, chrome.py) sind hier.
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

    # ── Survey Schemas ──
    # Request/Response für POST /survey/run
    SurveyRunRequest,         # profile_name, max_surveys, provider_filter, headless, cdp_port
    SurveyRunResponse,        # status, profile, surveys_run, completed, total_earned, results, message
    SurveyResult,             # survey_id, status, provider, earned, elapsed_s, error

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

# survey_actions.py Router: Legacy Survey-Interaktionen (click-card, modal, etc.)
# Prefix: /survey (definiert in survey_actions.py: APIRouter(prefix="/survey"))
# DEPRECATED: Use survey_tools.py endpoints instead (POST /survey/open, /fill, /rate)
from api.survey_actions import router as survey_router

# survey_tools.py Router: MODERN Survey-Interaktionen (open, fill, rate)
# Prefix: /survey (definiert in survey_tools.py: APIRouter(prefix="/survey"))
# Diese Endpoints ersetzen den monolithischen POST /workflow/run-best
from api.survey_tools import router as survey_tools_router

# ── v2 kanonische Tools (cdp_universal + cdp_actuator + captcha_router) ──
# Top-Level Mount auf /v2/* — NICHT unter /survey, weil universal frame-übergreifend
# arbeitet und keine Survey-spezifischen Annahmen macht.
from api.survey_tools import universal_router_export

# cookie_routes.py Router: Cookie-Management (extract, inject, verify)
# Prefix: /cookies (definiert in cookie_routes.py)
from api.cookie_routes import router as cookie_router

# dashboard_routes.py Router: Dashboard-Scanning und Balance
# Prefix: /dashboard (definiert in dashboard_routes.py)
from api.dashboard_routes import router as dashboard_router

# captcha_routes.py Router: Captcha-Solver (slide, text, angular-drag-drop)
# Prefix: /captcha (definiert in captcha_routes.py)
# SR-74: POST /captcha/slide, SR-75: POST /captcha/text
from api.captcha_routes import router as captcha_router

# survey_universal_routes.py Router: Universal Survey-Automation
# Prefix: /survey (definiert in survey_universal_routes.py)
# SR-76: POST /survey/dashboard-scan, SR-77: POST /survey/universal-answer
from api.survey_universal_routes import router as survey_universal_router


# ═══════════════════════════════════════════════════════════════════════════════
# LAZY-LOADER: Schweren Code erst bei ERSTEM Zugriff laden
# ═══════════════════════════════════════════════════════════════════════════════
# WARUM Lazy-Loading?
# → Playwright ist SCHWER (Chromium-Binary, ~150MB). Import dauert 2-5s.
# → survey-cli hat Dependencies (openai, websocket-client). Import dauert 1-2s.
# → Wenn die API startet, brauchen wir Playwright NICHT sofort (nur wenn ein
#   Browser-Endpoint aufgerufen wird).
# → Mit Lazy-Loading: API startet in <1s. Ohne: 5-10s.
# → Wenn ein Modul fehlt (z.B. openai nicht installiert), crasht die API NICHT
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


def _get_survey_runner():
    """
    Lazy-Load SurveyRunner — Survey-Automation aus survey-cli.
    
    WARUM SurveyRunner lazy laden?
    → SurveyRunner benötigt openai (NVIDIA NIM / Nemotron API).
    → openai ist ein großes Paket (~50MB). Import dauert 1-2s.
    → Wenn die API nur für Browser-Automation verwendet wird (keine Surveys),
      brauchen wir openai nicht.
    → Lazy-Loading = API startet schneller, Module werden nur bei Bedarf geladen.
    
    WARUM SurveyRunner UND RunnerConfig zurückgeben?
    → SurveyRunner ist die HAUPT-Klasse (führt Surveys aus).
    → RunnerConfig ist die KONFIGURATION (max_surveys, cdp_port, etc.).
    → Beide werden vom Endpoint survey_run() benötigt.
    → Wir gebe ein Tupel zurück: (SurveyRunner, RunnerConfig).
    
    WARUM RuntimeError mit "Install openai package"?
    → Klare Fehlermeldung: Client weiß EXAKT was fehlt.
    → Ohne Hinweis → Client müsste raten oder Stack-Trace lesen.
    
    Returns:
        Tuple[Type[SurveyRunner], Type[RunnerConfig]]: Klassen für Survey-Ausführung.
    
    Raises:
        RuntimeError: Wenn openai nicht installiert ist.
    
    Example:
        SurveyRunner, RunnerConfig = _get_survey_runner()
        config = RunnerConfig(max_surveys=5)
        runner = SurveyRunner(config)
    """
    # Versuche survey-cli Module zu importieren.
    # survey.runner: Enthält SurveyRunner und RunnerConfig.
    try:
        from survey.runner import SurveyRunner, RunnerConfig
    except ImportError as e:
        # Import fehlgeschlagen (wahrscheinlich openai fehlt).
        raise RuntimeError(
            "SurveyRunner requires openai. Install openai package."
        ) from e
    
    # Gebe BEIDE Klassen zurück (Tuple).
    # Der Aufrufer muss beide entpacken: SurveyRunner, RunnerConfig = _get_survey_runner()
    return SurveyRunner, RunnerConfig


def _get_auth_flow():
    """
    Lazy-Load Auth-Flow Module — Google OAuth Login.
    
    WARUM Auth-Flow lazy laden?
    → Google OAuth Flow benötigt survey-cli Dependencies (cua-driver, etc.).
    → Diese sind schwer und nicht immer nötig (wenn Cookies funktionieren).
    → Lazy-Loading = schnellerer Startup, Module nur bei Login-Endpoint geladen.
    
    WARUM drei Klassen zurückgeben?
    → GoogleOAuthFlow: Haupt-Login-Logik (CUA-basiert wegen Shadow-DOM).
    → LoginVerifier: Prüft ob Login erfolgreich war (Dashboard-Elemente).
    → CuaAdapter: Adapter für cua-driver Kommunikation.
    → Alle drei werden von heypiggy_login() benötigt.
    
    WARUM f-string in Fehlermeldung?
    → {e} enthält die ORIGINALE ImportError-Meldung.
    → Das hilft beim Debuggen: "No module named 'survey.auth'" vs
      "No module named 'cua_driver'".
    
    Returns:
        Tuple[Type, Type, Type]: (GoogleOAuthFlow, LoginVerifier, CuaAdapter)
    
    Raises:
        RuntimeError: Wenn survey-cli Dependencies fehlen.
    
    Example:
        GoogleOAuthFlow, LoginVerifier, CuaAdapter = _get_auth_flow()
        flow = GoogleOAuthFlow(CuaAdapter(), LoginVerifier())
    """
    # Versuche survey.auth zu importieren.
    # Enthält GoogleOAuthFlow, LoginVerifier, CuaAdapter.
    try:
        from survey.auth import GoogleOAuthFlow, LoginVerifier, CuaAdapter
    except ImportError as e:
        # Import fehlgeschlagen (survey-cli nicht installiert oder fehlende Dependencies).
        raise RuntimeError(
            f"Auth modules require survey-cli dependencies. Import error: {e}"
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
# LEGACY — diese Endpoints werden durch survey_tools_router ersetzt.
app.include_router(survey_router)

# Registriere Survey-Tools-Router (prefix="/survey", tags=["survey-tools"]).
# MODERN Endpoints: POST /survey/open, /survey/fill, /survey/rate
# Diese ersetzen den monolithischen POST /workflow/run-best
app.include_router(survey_tools_router)

# Registriere Cookie-Router (prefix="/cookies", tags=["Cookie Management"]).
# Endpoints: POST /cookies/extract, POST /cookies/inject, POST /cookies/verify.
app.include_router(cookie_router)

# Registriere Dashboard-Router (prefix="/dashboard", tags=["Dashboard"]).
# Endpoints: POST /dashboard/scan, POST /dashboard/balance.
app.include_router(dashboard_router)

# Registriere Universal-v2-Router (prefix='/v2', tags=['universal-v2']).
# Endpoints: POST /v2/scan, /v2/click, /v2/fill, /v2/press_key, /v2/captcha/*
# Das ist der NEUE kanonische Pfad — siehe survey-cli/survey/cdp_universal.py
# und survey-cli/survey/cdp_actuator.py.
app.include_router(universal_router_export)

# Registriere Captcha-Router (prefix="/captcha", tags=["captcha"]).
# Endpoints: POST /captcha/slide, POST /captcha/text, POST /captcha/angular-drag-drop.
# SR-74, SR-75: Echte Solver-Integration aus stealth-captcha/solver/*
app.include_router(captcha_router)

# Registriere Survey-Universal-Router (prefix="/survey", tags=["survey-universal"]).
# Endpoints: POST /survey/dashboard-scan, POST /survey/universal-answer.
# SR-76, SR-77: Dashboard-Scanning und Universal Page-by-Page Answering
app.include_router(survey_universal_router)


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
        → {"running": true, "profile": "Profile 901 (Jeremy)", "last_used": 1778261390.45,
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
        {"pid": null, "cdp_port": 9999}
        → {"status": "success", "service": "heypiggy", "profile": "default",
            "message": "Login successful", "details": {"pid": 34852, "wid": 56640}}
    """
    try:
        # ═══════════════════════════════════════════════════════════════════════
        # SCHRITT 1: PID bestimmen (bestehenden Chrome verwenden oder neu starten)
        # ═══════════════════════════════════════════════════════════════════════
        
        # Initialisiere pid mit Request-Wert (kann None sein).
        pid = req.pid
        
        # Wenn keine PID angegeben → suche bestehenden Chrome.
        if pid is None:
            # Importiere subprocess nur hier (wird nicht immer gebraucht).
            import subprocess
            
            # lsof: List Open Files. "-i TCP:PORT" = zeige Netzwerk-Verbindungen auf diesem Port.
            # "-t" = nur PID ausgeben (keine Header, keine Extra-Info).
            # timeout=5s: Wenn lsof hängt → breche ab (sollte nicht passieren, aber Safety).
            result = subprocess.run(
                ["lsof", "-i", f"TCP:{req.cdp_port}", "-t"],
                capture_output=True,    # stdout/stderr in result.stdout/result.stderr
                text=True,              # Dekodiere als Text (statt Bytes)
                timeout=5               # Timeout in Sekunden
            )
            
            # result.stdout enthält PIDs (eine pro Zeile, wenn mehrere Prozesse auf Port hören).
            # Wir nehmen die ERSTE PID die wir finden (die Haupt-Chrome-Prozess).
            if result.stdout.strip():
                # Splitte in Zeilen und iteriere.
                for line in result.stdout.strip().split("\n"):
                    # Prüfe ob die Zeile eine gültige Integer-PID ist.
                    if line.strip().isdigit():
                        # Konvertiere zu int und verwende als PID.
                        pid = int(line.strip())
                        break  # Erste PID gefunden → aufhören.
        
        # ═══════════════════════════════════════════════════════════════════════
        # SCHRITT 2: Chrome starten wenn keine PID gefunden
        # ═══════════════════════════════════════════════════════════════════════
        
        if pid is None:
            # Lazy-Load ChromeLauncher (aus survey-cli).
            # WARUM survey.chrome? ChromeLauncher ist Teil der survey-cli Bibliothek.
            from survey.chrome import ChromeLauncher
            
            # Erstelle Launcher mit CDP-Port und Debug-Modus.
            # Debug=True → mehr Logging (nützlich für Troubleshooting).
            launcher = ChromeLauncher(port=req.cdp_port, debug=True)
            
            # Starte Chrome und navigiere zum HeyPiggy Dashboard.
            # launch_and_verify():
            # 1. Erstellt temporäres Profil-Verzeichnis.
            # 2. Startet Chrome als subprocess mit CDP-Port und Flags.
            # 3. Wartet bis CDP erreichbar ist (Polling auf /json/version).
            # 4. Navigiert zur angegebenen URL.
            # 5. Gibt {"ok": True, "pid": PID, "cdp_port": PORT} zurück.
            launch_result = launcher.launch_and_verify(
                url="https://www.heypiggy.com/?page=dashboard"
            )
            
            # Prüfe ob Start erfolgreich war.
            if not launch_result.get("ok"):
                # Start fehlgeschlagen → gebe Error-Response zurück.
                # Wir verwenden LoginResponse (nicht HTTPException) weil das ein
                # erwarteter Fehlerfall ist (Chrome konnte nicht starten).
                return LoginResponse(
                    status="error",
                    service="heypiggy",
                    profile=req.profile_name,
                    message=f"chrome_launch_failed: {launch_result.get('error', 'unknown')}",
                    details={"step": launch_result.get("step")},
                )
            
            # Extrahiere PID aus Launch-Ergebnis.
            pid = launch_result.get("pid")
        
        # ═══════════════════════════════════════════════════════════════════════
        # SCHRITT 3: Auth-Flow ausführen (CUA-basiert wegen Shadow-DOM)
        # ═══════════════════════════════════════════════════════════════════════
        
        # Lazy-Load Auth-Flow Module.
        # GoogleOAuthFlow: Haupt-Login-Logik.
        # LoginVerifier: Prüft ob Login erfolgreich war.
        # CuaAdapter: Kommunikation mit cua-driver.
        GoogleOAuthFlow, LoginVerifier, CuaAdapter = _get_auth_flow()
        
        # Erstelle Flow-Instanz.
        # CuaAdapter() = neuer Adapter für CUA-Kommunikation.
        # LoginVerifier() = neuer Verifier für Login-Prüfung.
        flow = GoogleOAuthFlow(CuaAdapter(), LoginVerifier())
        
        # Führe Login aus.
        # pid=pid → verwende den Chrome mit dieser PID (CUA spricht mit diesem Prozess).
        result = flow.execute(pid=pid)
        
        # ═══════════════════════════════════════════════════════════════════════
        # SCHRITT 4: Ergebnis verarbeiten
        # ═══════════════════════════════════════════════════════════════════════
        
        if result.status == "ok":
            # Login erfolgreich!
            # Gebe Success-Response mit pid und wid zurück.
            # pid = Chrome Prozess-ID (für spätere Calls).
            # wid = Window ID (für CUA-Operationen).
            return LoginResponse(
                status="success",
                service="heypiggy",
                profile=req.profile_name,
                message="Login successful",
                details={"pid": result.pid, "wid": result.wid},
            )
        
        elif result.status == "already_logged_in":
            # Bereits eingeloggt (Session noch gültig).
            # Kein erneuter Login nötig.
            return LoginResponse(
                status="already_logged_in",
                service="heypiggy",
                profile=req.profile_name,
                message="Already logged in",
                details={"pid": result.pid, "wid": result.wid},
            )
        
        else:
            # Login fehlgeschlagen.
            # result.reason enthält die Fehlermeldung (z.B. "shadow_dom_click_failed").
            return LoginResponse(
                status="error",
                service="heypiggy",
                profile=req.profile_name,
                message=result.reason or "unknown_error",
                details={"pid": pid},
            )
    
    except Exception as e:
        # Unerwarteter Fehler (z.B. ImportError, subprocess Error, etc.).
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════════
# SEKTION 3: SURVEY ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════
# Dieser Endpoint führt mehrere Surveys aus (aggregiert).
# Die einzelnen Survey-Aktionen (click-card, fill-text, etc.) sind im
# survey_router (survey_actions.py) definiert.
# ═══════════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════════


@app.post("/survey/run", response_model=SurveyRunResponse)
async def survey_run(req: SurveyRunRequest):
    """
    Führt mehrere Surveys auf dem HeyPiggy Dashboard aus.
    
    ABLAUF:
    1. Lazy-Load SurveyRunner und RunnerConfig.
    2. Erstelle RunnerConfig mit max_surveys und cdp_port.
    3. Wenn provider_filter gesetzt → filtere skip_providers Liste.
       (Nur erlaubte Provider ausführen, andere überspringen).
    4. Erstelle SurveyRunner mit Config.
    5. Rufe runner.run_loop() auf (führt Survey-Loop aus).
    6. Konvertiere Ergebnisse in Pydantic SurveyResult-Objekte.
    7. Berechne Statistiken:
       - total_earned = Summe aller positiven Rewards.
       - completed = Anzahl erfolgreich abgeschlossener Surveys.
    8. Gib aggregierte Response zurück.
    
    WARUM SurveyRunner lazy laden?
    → SurveyRunner benötigt openai (NVIDIA NIM API).
    → openai ist schwer (~50MB) und wird nur hier gebraucht.
    → Lazy-Loading = schnellerer Startup, Modul nur bei Bedarf geladen.
    
    WARUM provider_filter?
    → Manche Provider sind zuverlässiger (Qualtrics) als andere (Samplicio).
    → Client kann bevorzugte Provider angeben: ["qualtrics", "tolunastart"].
    → Implementation: Wir filtern die skip_providers Liste.
       Standard: skip_providers = ["samplicio"] (oft Disqualifikation).
       Wenn provider_filter = ["qualtrics"] → skip_providers wird geleert
       (außer Provider nicht in filter).
    
    WARUM total_earned nur positive Werte?
    → Screen-Out Surveys geben 0.0€ (oder manchmal 0.02€ Compensation).
    → Wir summieren nur >0 Werte um den tatsächlichen Gewinn zu zeigen.
    → Wenn total_earned = 0.0 → alle Surveys waren Screen-Out oder Fehler.
    
    WARUM elapsed_s?
    → Performance-Monitoring: Wie lange dauert ein Survey-Lauf?
    → Wenn elapsed_s / surveys_run > 300s → ineffizient (zu viele Screen-Outs).
    
    Args:
        req: SurveyRunRequest mit profile_name, max_surveys, provider_filter,
             headless, cdp_port.
    
    Returns:
        SurveyRunResponse: status, profile, surveys_run, completed,
                           total_earned, results[], message.
    
    Raises:
        HTTPException(500): Bei Fehlern im Survey-Runner.
    
    Example:
        POST /survey/run
        {"max_surveys": 5, "provider_filter": ["qualtrics", "tolunastart"]}
        → {"status": "success", "profile": "default", "surveys_run": 5,
            "completed": 3, "total_earned": 1.20,
            "results": [...], "message": "Ran 5 surveys, 3 completed, +1.20€"}
    """
    # Zeit-Messung für Performance-Tracking.
    # time.time() gibt Unix-Timestamp in Sekunden (mit Mikrosekunden-Präzision).
    start_time = time.time()
    
    try:
        # ═══════════════════════════════════════════════════════════════════════
        # SCHRITT 1: SurveyRunner laden
        # ═══════════════════════════════════════════════════════════════════════
        
        # Lazy-Load SurveyRunner und RunnerConfig.
        # Wenn openai nicht installiert → RuntimeError mit Install-Hinweis.
        SurveyRunner, RunnerConfig = _get_survey_runner()
        
        # ═══════════════════════════════════════════════════════════════════════
        # SCHRITT 2: Konfiguration erstellen
        # ═══════════════════════════════════════════════════════════════════════
        
        # Erstelle RunnerConfig mit Request-Parametern.
        # max_surveys: Maximale Anzahl Surveys (Safety-Limit gegen Endlosschleifen).
        # cdp_port: CDP-Port für Chrome-Kommunikation.
        config = RunnerConfig(
            max_surveys=req.max_surveys,
            cdp_port=req.cdp_port,
        )
        
        # Wenn provider_filter gesetzt → filtere skip_providers.
        # Logik: Wir entfernen Provider aus skip_providers die im Filter sind.
        # Beispiel:
        #   skip_providers = ["samplicio", "cint"] (Standard)
        #   provider_filter = ["qualtrics", "tolunastart"]
        #   Ergebnis: skip_providers = ["samplicio", "cint"] (keine Änderung,
        #             weil "qualtrics" und "tolunastart" nicht in skip_providers sind).
        #   Wenn provider_filter = ["samplicio"] → skip_providers wird geleert
        #   (weil "samplicio" aus skip_providers entfernt wird).
        if req.provider_filter:
            # Filtere skip_providers: Behalte nur Provider die NICHT im Filter sind.
            # Das ermöglicht es, bestimmte Provider explizit zu erlauben.
            config.skip_providers = [p for p in config.skip_providers
                                      if p not in req.provider_filter]
        
        # ═══════════════════════════════════════════════════════════════════════
        # SCHRITT 3: Survey ausführen
        # ═══════════════════════════════════════════════════════════════════════
        
        # Erstelle Runner mit Config.
        runner = SurveyRunner(config)
        
        # Führe Survey-Loop aus.
        # run_loop() navigiert zum Dashboard, scannt Surveys, führt sie aus,
        # und gibt eine Liste von Survey-Ergebnissen zurück.
        results = runner.run_loop(max_surveys=req.max_surveys)
        
        # ═══════════════════════════════════════════════════════════════════════
        # SCHRITT 4: Ergebnisse konvertieren
        # ═══════════════════════════════════════════════════════════════════════
        
        # Konvertiere interne Ergebnisse in Pydantic-Modelle (SurveyResult).
        # Das ist notwendig weil FastAPI Pydantic-Modelle für Response-Validation
        # benötigt. Interne Objekte könnten nicht Pydantic-kompatibel sein.
        survey_results = [
            SurveyResult(
                survey_id=r.survey_id,      # ID der Survey
                status=r.status,            # "completed", "screen_out", "error"
                provider=r.provider,        # "qualtrics", "tolunastart", etc.
                earned=r.earned,            # Verdiente Belohnung in EUR
                elapsed_s=r.elapsed_s,      # Dauer in Sekunden
                error=r.error,              # Fehlermeldung (None bei Erfolg)
            )
            for r in results  # List comprehension für alle Ergebnisse
        ]
        
        # ═══════════════════════════════════════════════════════════════════════
        # SCHRITT 5: Statistiken berechnen
        # ═══════════════════════════════════════════════════════════════════════
        
        # Summe aller positiven Rewards.
        # WARUM nur >0? Screen-Outs geben 0.0€ (oder 0.02€ Compensation).
        # Wir wollen den tatsächlichen Gewinn zeigen (nicht Compensation).
        total_earned = sum(r.earned for r in survey_results if r.earned > 0)
        
        # Anzahl erfolgreich abgeschlossener Surveys.
        # Status "completed" bedeutet: Survey wurde bis zum Ende ausgefüllt.
        completed = sum(1 for r in survey_results if r.status == "completed")
        
        # ═══════════════════════════════════════════════════════════════════════
        # SCHRITT 6: Response zurückgeben
        # ═══════════════════════════════════════════════════════════════════════
        
        return SurveyRunResponse(
            status="success",                   # Immer "success" wenn wir hier ankommen
            profile=req.profile_name,            # Bestätigung: welches Profil
            surveys_run=len(results),            # Anzahl gestarteter Surveys
            completed=completed,                 # Anzahl erfolgreicher Surveys
            total_earned=total_earned,           # Summe aller Rewards
            results=survey_results,              # Liste aller Ergebnisse
            # Human-readable Zusammenfassung.
            message=f"Ran {len(results)} surveys, {completed} completed, +{total_earned:.2f}€",
        )
    
    except Exception as e:
        # Fehler im Survey-Runner (z.B. openai API Fehler, Chrome nicht erreichbar).
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
# SEKTION 6: BACKGROUND SURVEY LOOP (24/7 Automated Earning)
# ═══════════════════════════════════════════════════════════════════════════════
# Dieser Abschnitt startet einen Background-Task beim API-Start der
# automatisch alle 5 Minuten Surveys scannt und ausführt.
# ═══════════════════════════════════════════════════════════════════════════════

import asyncio

# Global state für den Background-Task
_background_task: Optional[asyncio.Task] = None
_background_running: bool = False


async def _survey_loop():
    """
    24/7 Background Survey Loop — verdient Geld automatisch.
    
    ABLAUF (alle 5 Minuten):
      1. Prüfe ob Chrome läuft (health check).
      2. Scan Dashboard nach verfügbaren Surveys.
      3. Wähle beste Survey (höchster Reward, vertrauenswürdiger Provider).
      4. Führe Survey via LangGraph aus (POST /survey/run-graph Logik).
      5. Logge Ergebnis (earned, status, errors).
      6. Warte 5 Minuten → wiederhole.
    
    WARUM alle 5 Minuten?
      → HeyPiggy Dashboard aktualisiert Surveys ca. alle 5-15 Minuten.
      → Zu oft = Rate-Limiting / Account-Sperre.
      → Zu selten = verpasste Surveys (andere User schnappen sie sich).
    
    WARUM Background-Task?
      → FastAPI ist ein Web-Server — er muss Requests empfangen können.
      → Ein Background-Task läuft parallel (kein Blocking).
      → asyncio.create_task() = Fire-and-Forget, non-blocking.
    
    WARUM try/except im Loop?
      → Wenn eine Survey fehlschlägt → nicht den ganzen Loop crashen.
      → Logge Fehler → warte → versuche nächste Survey.
      → Ohne try/except → ein Fehler stoppt den 24/7 Loop.
    
    WARUM sleep(300) am Ende?
      → 300 Sekunden = 5 Minuten.
      → asyncio.sleep() ist non-blocking (anderen Tasks/Requests laufen weiter).
      → time.sleep() wäre BLOCKING → API würde einfrieren!
    
    WARUM _background_running Flag?
      → Beim Shutdown setzen wir _background_running = False.
      → Der Loop beendet sich selbst (graceful shutdown).
      → Wichtig: asyncio.Task.cancel() ist FORCEFUL → kann Daten verlieren.
    
    Returns:
        None (läuft unendlich bis _background_running = False)
    """
    global _background_running
    _background_running = True
    
    # Initial-Wartezeit: 30s nach API-Start damit alles initialisiert ist.
    await asyncio.sleep(30)
    
    while _background_running:
        try:
            # ═══════════════════════════════════════════════════════════════
            # SCHRITT 1: Chrome Health Check
            # ═══════════════════════════════════════════════════════════════
            # WARUM health check?
            # → Chrome crasht manchmal (Memory-Leak, Redirect-Chains, etc.).
            # → Wenn Chrome tot → Survey kann nicht ausgeführt werden.
            # → Wir starten Chrome neu wenn nötig (bm.start()).
            
            bm = _get_bm()
            health = await bm.health()
            
            if not health.get("running"):
                # Chrome läuft nicht → starte neu.
                # WARUM nicht einfach überspringen?
                # → Ohne Chrome → keine Surveys → kein Geld.
                # → Neustart ist besser als warten.
                print("[BG-LOOP] Chrome not running, starting...")
                await bm.start(
                    profile_name="default",
                    headless=os.getenv("BROWSER_HEADLESS", "true").lower() == "true",
                    cdp_port=9999,
                )
                await asyncio.sleep(5)  # Warte auf Chrome-Startup.
            
            # ═══════════════════════════════════════════════════════════════
            # SCHRITT 2: Dashboard scannen
            # ═══════════════════════════════════════════════════════════════
            # WARUM Dashboard scannen?
            # → Wir müssen wissen welche Surveys verfügbar sind.
            # → Dashboard-Router hat POST /dashboard/scan Endpoint.
            # → Wir rufen die Scan-Logik direkt auf (kein HTTP-Call nötig).
            
            # Lazy-Load Dashboard-Scanner
            from api.dashboard_routes import _scan_dashboard_impl
            
            scan_result = await _scan_dashboard_impl(
                cdp_port=9999,
                min_reward=0.05,  # Mindestens 5 Cent (sonst lohnt es sich nicht).
            )
            
            surveys = scan_result.get("surveys", [])
            
            if not surveys:
                print("[BG-LOOP] No surveys available, waiting...")
                await asyncio.sleep(300)
                continue
            
            # ═══════════════════════════════════════════════════════════════
            # SCHRITT 3: Beste Survey auswählen
            # ═══════════════════════════════════════════════════════════════
            # WARUM Score-basierte Auswahl?
            # → Nicht jede Survey ist gleich gut.
            # → Manche Provider disqualifizieren oft (Samplicio).
            # → Manche haben hohe Rewards aber lange Dauer.
            # → Score = reward * provider_trust (Erfahrungswerte).
            
            # Provider-Trust-Scores (basierend auf Erfahrungswerten).
            # Höher = besser (weniger Disqualifikation, höhere Erfolgsrate).
            provider_trust = {
                "qualtrics": 0.9,
                "tolunastart": 0.8,
                "cint": 0.7,
                "tivian": 0.7,
                "nfield": 0.6,
                "samplicio": 0.4,
                "purespectrum": 0.3,
                "ipsos": 0.5,
            }
            
            best_survey = None
            best_score = -1
            
            for survey in surveys:
                reward = survey.get("reward", 0)
                provider = survey.get("provider", "").lower()
                
                # Score = Reward * Trust
                # WARUM Multiplikation?
                # → Hoher Reward aber untrusted Provider = niedriger Score.
                # → Niedriger Reward aber trusted Provider = höherer Score.
                # → Beispiel: 0.50€ * 0.4 (Samplicio) = 0.20
                #            0.30€ * 0.9 (Qualtrics) = 0.27 → Qualtrics gewinnt!
                trust = provider_trust.get(provider, 0.5)
                score = reward * trust
                
                if score > best_score:
                    best_score = score
                    best_survey = survey
            
            if not best_survey:
                print("[BG-LOOP] No suitable survey found, waiting...")
                await asyncio.sleep(300)
                continue
            
            survey_id = best_survey.get("id", "")
            provider = best_survey.get("provider", "")
            reward = best_survey.get("reward", 0)
            
            print(f"[BG-LOOP] Selected survey {survey_id} ({provider}, +{reward:.2f}€)")
            
            # ═══════════════════════════════════════════════════════════════
            # SCHRITT 4: LangGraph Survey ausführen
            # ═══════════════════════════════════════════════════════════════
            # WARUM LangGraph statt manuellem Loop?
            # → LangGraph ist deterministisch (StateGraph).
            # → Jede Node ist atomar und getestet.
            # → Routing-Logik (route()) entscheidet autonom was als nächstes passiert.
            # → Bei 3× Fehlern → Delegation an Human (nicht Endlos-Loop).
            
            # WARUM graph.invoke() in Thread-Pool?
            # → LangGraph ist synchron (kein async/await).
            # → FastAPI ist async — blockierender Code würde einfrieren.
            # → asyncio.to_thread() führt synchronen Code in separatem Thread aus.
            # → Der Event-Loop bleibt responsiv (API kann weiter Requests empfangen).
            
            from survey.graph import create_graph, SurveyState
            from survey.command_registry import acquire_survey_lock, release_survey_lock

            # SURVEY LOCK — prevent parallel survey execution
            # ROOT CAUSE FIX (2026-05-10): Completion detection failed → loop continued
            # → background loop started next survey before old tab closed → 6 tabs stacked!
            if not acquire_survey_lock(survey_id):
                print(f"[BG-LOOP] Survey lock active — skipping survey {survey_id} (another survey running)")
                await asyncio.sleep(60)  # Wait 1 min before retry
                continue
            
            graph = create_graph()
            state = SurveyState(
                survey_id=survey_id,
                provider=provider,
                cdp_port=9999,
                max_iterations=15,
            )
            
            final = await asyncio.to_thread(graph.invoke, state)
            
            # RELEASE LOCK — survey finished
            release_survey_lock()
            
            # ═══════════════════════════════════════════════════════════════
            # SCHRITT 5: Ergebnis loggen
            # ═══════════════════════════════════════════════════════════════
            earned = final.balance_earned
            status = final.status
            errors = len(final.errors)
            
            if earned > 0:
                print(f"[BG-LOOP] SUCCESS: +{earned:.2f}€ (survey={survey_id}, provider={provider})")
            elif final.screen_out:
                print(f"[BG-LOOP] SCREEN-OUT: 0.00€ (survey={survey_id}, provider={provider})")
            elif errors > 0:
                print(f"[BG-LOOP] ERRORS: {errors} errors (survey={survey_id}, provider={provider})")
            else:
                print(f"[BG-LOOP] COMPLETED: No earnings (survey={survey_id}, status={status})")
            
            # TODO: Balance in Datei/DB loggen für Trend-Analyse.
            # TODO: Cash-out Trigger bei >= 5.00€.
            
        except Exception as e:
            # ═══════════════════════════════════════════════════════════════
            # FEHLERBEHANDLUNG: Logge Fehler aber crashe NICHT den Loop.
            # ═══════════════════════════════════════════════════════════════
            # WARUM try/except um den GESAMTEN Loop?
            # → Ein Fehler (z.B. Chrome crash, Network-Error) darf den 24/7 Loop nicht stoppen.
            # → Logge Fehler → warte 5 Min → versuche erneut.
            # → Ohne das → ein Fehler stoppt den Earning-Forever!
            
            print(f"[BG-LOOP] ERROR: {type(e).__name__}: {e}")
            # RELEASE LOCK even on error — survey tab is dead, unlock for next
            try:
                from survey.command_registry import release_survey_lock
                release_survey_lock()
            except Exception:
                pass
            # Warte trotzdem 5 Minuten (nicht sofort retry — könnte Rate-Limit sein).
        
        # Warte 5 Minuten bis zur nächsten Iteration.
        await asyncio.sleep(300)


@app.on_event("startup")
async def startup_event():
    """
    Startet den Background Survey Loop beim API-Start.
    
    WARUM startup event?
    → FastAPI ruft dies automatisch auf wenn der Server startet.
    → Der Loop läuft parallel zur API (kein Blocking).
    → Kein manueller Start nötig (set-and-forget).
    
    WARUM asyncio.create_task()?
    → Erstellt einen neuen Task im Event-Loop.
    → Der Task läuft im Hintergrund (parallel zu Endpoints).
    → Kein await nötig (Fire-and-Forget).
    """
    global _background_task
    print("[STARTUP] Starting background survey loop...")
    _background_task = asyncio.create_task(_survey_loop())
    print("[STARTUP] Background survey loop started!")


@app.on_event("shutdown")
async def shutdown_event():
    """
    Beendet den Background Survey Loop graceful.
    
    WARUM graceful shutdown?
    → Wenn die API stoppt (z.B. SIGTERM) → laufende Surveys abbrechen = Geld verlieren.
    → Wir setzen _background_running = False → Loop beendet sich selbst.
    → Danach warten wir max. 60s auf den Task.
    → Wenn der Task noch läuft → cancel() als letzter Ausweg.
    
    WARUM 60s Timeout?
    → Eine Survey dauert typisch 30-120s.
    → 60s = genug Zeit für den aktuellen Schritt zu beenden.
    → Aber nicht zu lange (Server-Shutdown sollte schnell sein).
    """
    global _background_running, _background_task
    print("[SHUTDOWN] Stopping background survey loop...")
    
    # Signalisiere dem Loop dass er stoppen soll.
    _background_running = False
    
    # Warte auf den Task (max. 60s).
    if _background_task:
        try:
            await asyncio.wait_for(_background_task, timeout=60)
        except asyncio.TimeoutError:
            # Loop hat sich nicht rechtzeitig beendet → Force-Cancel.
            print("[SHUTDOWN] Background loop did not stop gracefully, cancelling...")
            _background_task.cancel()
            try:
                await _background_task
            except asyncio.CancelledError:
                pass
    
    print("[SHUTDOWN] Background survey loop stopped.")


# ═══════════════════════════════════════════════════════════════════════════════
# ENDE DER MAIN.PY
# ═══════════════════════════════════════════════════════════════════════════════
# ZUSAMMENFASSUNG:
#
# Diese Datei ist der EINSTIEGSPUNKT für die gesamte FastAPI-Anwendung.
# Sie definiert:
#   - FastAPI App-Instanz (mit Title, Version, Docs-URLs).
#   - Router-Registrierung (survey, cookies, dashboard).
#   - Lazy-Loader für schwere Dependencies (Playwright, openai).
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
