"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║           STEALTH-RUNNER — Cookie Routes (HeyPiggy Session Persistenz)        ║
║                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ZWECK / PURPOSE:                                                            ║
║  ────────────────                                                            ║
║  Diese Datei implementiert die FastAPI-Router-Endpunkte für Cookie-         ║
║  Management: Extrahieren, Injizieren, und Verifizieren von HeyPiggy-        ║
║  Session-Cookies.                                                            ║
║                                                                              ║
║  ARCHITEKTUR-OVERVIEW:                                                       ║
║  ─────────────────────                                                       ║
║  ┌─────────────────────────────────────────────────────────────────────┐    ║
║  │  Endpoints (FastAPI Router, prefix="/cookies", tags=["cookies"])   │    ║
║  │  ├── POST /cookies/extract   → Cookies aus Browser extrahieren     │    ║
║  │  ├── POST /cookies/inject    → Cookies in Browser laden             │    ║
║  │  └── POST /cookies/verify    → Session-Status prüfen              │    ║
║  └─────────────────────────────────────────────────────────────────────┘    ║
║                                                                              ║
║  WARUM EIGENER ROUTER?                                                       ║
║  ─────────────────────                                                       ║
║  • Modularität: Cookie-Logik ist von Survey-Logik getrennt.                 ║
║  • Wiederverwendung: Router kann in anderen Projekten importiert werden.   ║
║  • Testbarkeit: Router kann isoliert getestet werden (ohne main.py).      ║
║  • Übersichtlichkeit: main.py bleibt schlank (nur Registrierung).         ║
║                                                                              ║
║  WARUM POST statt GET?                                                       ║
║  ─────────────────────                                                       ║
║  GET ist semantisch korrekt für Read-Operationen. ABER:                    ║
║  • POST /cookies/extract hat Seiteneffekte (Datei wird erstellt).        ║
║  • POST /cookies/inject hat Seiteneffekte (Browser-State wird geändert).║
║  • POST /cookies/verify hat Seiteneffekte (Navigation zum Dashboard).     ║
║  → Alle drei Endpoints verändern Zustand → POST ist korrekt.               ║
║                                                                              ║
║  WARUM extract und inject SEPARAT?                                           ║
║  ────────────────────────────────                                            ║
║  • Flexibilität: Client kann nur extrahieren (ohne zu injizieren).         ║
║  • Debuggbarkeit: Extrahierte Cookies können vor Injektion geprüft werden.║
║  • Sicherheit: Client kann Cookies vor Injektion validieren.              ║
║  • Recovery: Wenn Injektion fehlschlägt → Cookies sind noch gespeichert. ║
║                                                                              ║
║  SICHERHEIT / BANNED PATTERNS:                                               ║
║  ──────────────────────────────                                              ║
║  • KEINE Passwörter in Cookie-Dateien (nur Session-Tokens).                ║
║  • KEINE Session-IDs in Logs (nur Cookie-Datei-Pfad).                        ║
║  • Cookie-Datei in .gitignore (nicht ins Repository committen!).          ║
║  • NIEMALS Cookies auf öffentlichen Servern speichern (Datenschutz!).    ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

# ═══════════════════════════════════════════════════════════════════════════════
# IMPORTS: Was brauchen wir und WARUM?
# ═══════════════════════════════════════════════════════════════════════════════

# time: Zeit-Messung für Performance-Monitoring.
# WARUM? - time.time() gibt Unix-Timestamp (Sekunden mit Mikrosekunden).
#        - Wir messen elapsed_time für jeden Endpoint (wie lange dauert die Operation?).
#        - Nützlich für Performance-Tuning und Monitoring.
import time

# logging: Log-Ausgaben (nicht print!).
# WARUM? - Logs können in Dateien geschrieben werden (für Debugging).
#        - Log-Level (INFO, WARNING, ERROR) ermöglichen Filterung.
#        - Konsistenz: Playwright und andere Libraries verwenden logging.
#        - __name__ → Logger-Name enthält Modul-Pfad ("api.cookie_routes").
import logging

# Typ-Hinweise für bessere Code-Klarheit und IDE-Unterstützung.
# Dict, Any: Für flexible Dictionary-Typen (Cookie-Dictionaries haben unterschiedliche Felder).
from typing import Dict, Any

# APIRouter: FastAPI-Router für modulare Endpoints.
# WARUM? - Router können unabhängig definiert und in main.py registriert werden.
#        - Prefix und Tags werden im Router definiert (nicht pro Endpoint).
#        - Modularität: Diese Datei kann allein getestet werden.
from fastapi import APIRouter, HTTPException

# BrowserManager: Chrome-Verwaltung (Singleton, SINator-Style).
# WARUM? - Wir brauchen einen laufenden Chrome um Cookies zu extrahieren/injizieren.
#        - BrowserManager.start() startet/verwendet Chrome (oder wiederverwendet bestehenden).
#        - get_browser_manager() gibt Singleton-Instanz zurück (Port 9999).
from core.browser_manager import get_browser_manager

# CookieManager: Cookie-Verwaltung (Singleton).
# WARUM? - Extrahieren, Speichern, Laden, Injizieren, Verifizieren.
#        - get_cookie_manager() gibt Singleton-Instanz zurück (cookies_dir="./data").
from core.cookie_manager import get_cookie_manager, CookieManager

# Pydantic-Modelle für Request/Response Validation.
# WARUM? - FastAPI validiert Requests automatisch (422 bei ungültigen Daten).
#        - Response-Modelle garantieren korrektes JSON-Format.
#        - Siehe schemas.py für detaillierte Dokumentation jedes Modells.
from api.schemas import (
    # Request/Response für POST /cookies/extract
    CookieExtractRequest,      # profile_name, domain_filter, save_to_file, filename
    CookieExtractResponse,      # status, profile, cookies[], count, stats, saved_to, execution_time
    
    # Request/Response für POST /cookies/inject
    CookieInjectRequest,        # filename, verify_session
    CookieInjectResponse,       # status, injected_count, session_active, execution_time, error
    
    # Session Recovery (2026-05-08): Backup + Restore + Safe Extract
    BackupCreateRequest,        # working_dir, working_filename
    BackupCreateResponse,       # status, backed_up, count, backup_path, message
    RecoveryRequest,            # working_dir, working_filename
    RecoveryResponse,           # status, recovered, count, backup_source, restored_to, message
)

# Logger-Instanz für diese Datei.
# WARUM __name__? Logger-Name enthält Modul-Pfad ("api.cookie_routes").
# Ermöglicht gezieltes Logging-Level pro Modul.
logger = logging.getLogger(__name__)

# Router-Instanz erstellen.
# prefix="/cookies": ALLE Endpoints beginnen mit /cookies (z.B. /cookies/extract).
# tags=["Cookie Management"]: Swagger UI gruppiert diese Endpoints unter "Cookie Management".
router = APIRouter(prefix="/cookies", tags=["Cookie Management"])


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINT 1: POST /cookies/extract
# ═══════════════════════════════════════════════════════════════════════════════
# Extrahiert Cookies aus dem aktiven Browser (HeyPiggy-fokussiert).
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/extract", response_model=CookieExtractResponse)
async def extract_cookies(request: CookieExtractRequest):
    """
    Extrahiert Cookies aus dem aktuellen Browser (HeyPiggy-fokussiert).
    
    ABLAUF:
    1. Starte Zeit-Messung (elapsed_time).
    2. Hole BrowserManager-Singleton (get_browser_manager).
    3. Prüfe ob Chrome läuft (browser_mgr.is_running).
       Wenn nicht → HTTPException(400, "Browser nicht gestartet").
    4. Hole aktive Page (await browser_mgr.get_page()).
       Wenn Chrome nicht läuft → startet get_page() Chrome automatisch (Lazy-Start).
    5. Hole CookieManager-Singleton (get_cookie_manager).
    6. Extrahiere Cookies (await cookie_mgr.extract_cookies()).
       Filter optional nach Domain (request.domain_filter).
    7. Hole Cookie-Statistiken (cookie_mgr.get_cookie_stats()).
    8. Optional: Speichere Cookies in Datei (cookie_mgr.save_cookies()).
       Wenn request.save_to_file=True → speichere als JSON.
    9. Berechne elapsed_time = time.time() - start_time.
    10. Gib CookieExtractResponse zurück.
    
    WARUM Browser-Check VOR get_page()?
    → get_page() startet Chrome automatisch wenn nicht läuft (Lazy-Start).
    → Das ist gut für Automation, aber für Cookie-Extraktion sollte Chrome
    → bereits laufen (mit eingeloggtem User).
    → Wenn Chrome frisch gestartet wird → keine Cookies (nicht eingeloggt).
    → Der Check warnt den Client: "Browser nicht gestartet".
    → Client sollte vorher POST /browser/start oder /cookies/inject aufrufen.
    
    WARUM get_page() statt explizit start()?
    → get_page() ist die Haupt-API für Page-Zugriff.
    → Sie startet Chrome automatisch wenn nötig (convenience).
    → Für Cookie-Extraktion ist die Page egal (wir brauchen den Context).
    → Aber: Wir brauchen eine Page um den Context zu erreichen (Playwright-API).
    
    WARUM domain_filter default="heypiggy"?
    → HeyPiggy hat ~7 relevante Cookies.
    → ALLE Cookies (inkl. Google, Analytics, etc.) = HUNDERTE.
    → Filter reduziert Datenmenge und fokussiert auf relevante Cookies.
    → "heypiggy" matcht "heypiggy.com", ".heypiggy.com", etc.
    
    WARUM save_to_file default=True?
    → Persistenz: Cookies werden in JSON-Datei gespeichert.
    → Nach API-Restart können Cookies wieder injiziert werden.
    → Ohne Speicherung → Cookies gehen bei API-Restart verloren.
    → Client kann save_to_file=False setzen (nur in Response zurückgeben).
    
    WARUM stats in Response?
    → Schnelle Übersicht: "7 Cookies, 2 httpOnly, 5 secure".
    → Client kann prüfen: Wenn count=0 → Session nicht aktiv.
    → Wenn httpOnly=0 → Sicherheits-Bedenken.
    → Ohne stats → Client müsste alle Cookies parsen.
    
    WARUM execution_time?
    → Performance-Monitoring: Wie lange dauert die Extraktion?
    → Typisch: 0.5-2s (Playwright Cookie-Extraktion ist schnell).
    → Wenn >10s → möglicherweise Problem (langsamer Computer, viele Cookies).
    
    Args:
        request: CookieExtractRequest
            - profile_name: Browser-Profil (default: "default").
            - domain_filter: Domain-Filter (default: "heypiggy", None = alle).
            - save_to_file: In Datei speichern? (default: True).
            - filename: Dateiname (default: "heypiggy-cookies.json").
    
    Returns:
        CookieExtractResponse:
            - status: "success" oder "error".
            - profile: Verwendetes Profil.
            - cookies: Liste der extrahierten Cookie-Dicts.
            - count: Anzahl der Cookies.
            - stats: Statistiken (total, domains, httpOnly, secure, session).
            - saved_to: Pfad zur gespeicherten Datei (oder None).
            - execution_time: Dauer der Operation (z.B. "0.45s").
    
    Raises:
        HTTPException(400): Wenn Browser nicht gestartet ist.
        HTTPException(500): Bei unerwarteten Fehlern.
    
    Example:
        POST /cookies/extract
        {"domain_filter": "heypiggy", "save_to_file": true}
        → {"status": "success", "profile": "default", "cookies": [...],
            "count": 7, "stats": {"total": 7, ...}, "saved_to": "./data/heypiggy-cookies.json",
            "execution_time": "0.45s"}
    """
    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 1: Zeit-Messung starten
    # ═══════════════════════════════════════════════════════════════════════
    
    # WARUM time.time()? Unix-Timestamp in Sekunden (mit Mikrosekunden-Präzision).
    # Wir messen die Gesamtdauer des Endpoints (Performance-Monitoring).
    start_time = time.time()
    
    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 2: BrowserManager holen
    # ═══════════════════════════════════════════════════════════════════════
    
    # Singleton-Instanz des BrowserManagers (Port 9999, Profile 73).
    # WARUM Singleton? Es gibt nur EINEN Chrome-Prozess (keine Race Conditions).
    browser_mgr = get_browser_manager()
    
    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 3: Prüfen ob Chrome läuft
    # ═══════════════════════════════════════════════════════════════════════
    
    # WARUM is_running? Prüft ob Chrome aktiv ist (Playwright verbunden ODER CDP erreichbar).
    # Wenn nicht → Chrome wurde noch nicht gestartet (oder ist abgestürzt).
    # Für Cookie-Extraktion muss Chrome laufen UND eingeloggt sein.
    if not browser_mgr.is_running:
        # HTTPException(400): Bad Request — Browser ist nicht bereit.
        # WARUM 400 (nicht 500)? Der Client hat einen fehlerhaften Request gesendet
        # (Browser nicht gestartet). Das ist kein Server-Fehler.
        raise HTTPException(
            status_code=400,
            detail="Browser nicht gestartet. Rufe POST /browser/start auf."
        )
    
    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 4: Page holen (automatischer Start wenn nötig)
    # ═══════════════════════════════════════════════════════════════════════
    
    try:
        # Hole aktive Page (erster Tab im Browser).
        # WARUM await? get_page() ist async (startet Chrome wenn nötig).
        # Wenn Chrome läuft → gibt sofort die Page zurück.
        # Wenn Chrome nicht läuft → startet Chrome automatisch (Lazy-Start).
        # Hinweis: Wir haben oben is_running geprüft, aber get_page() ist sicherer.
        page = await browser_mgr.get_page()
        
        # ═══════════════════════════════════════════════════════════════════
        # SCHRITT 5: CookieManager holen
        # ═══════════════════════════════════════════════════════════════════
        
        # Singleton-Instanz des CookieManagers (cookies_dir="./data").
        cookie_mgr = get_cookie_manager()
        
        # ═══════════════════════════════════════════════════════════════════
        # SCHRITT 6: Cookies extrahieren
        # ═══════════════════════════════════════════════════════════════════
        
        # Extrahiere Cookies vom BrowserContext (via Page).
        # WARUM await? extract_cookies() ist async (Playwright API).
        # domain_filter="heypiggy" → nur HeyPiggy-relevante Cookies.
        # WARUM request.domain_filter? Client kann Filter überschreiben (z.B. None = alle).
        cookies = await cookie_mgr.extract_cookies(
            page,
            domain_filter=request.domain_filter
        )
        
        # ═══════════════════════════════════════════════════════════════════
        # SCHRITT 7: Statistiken generieren
        # ═══════════════════════════════════════════════════════════════════
        
        # Generiere Statistiken über die extrahierten Cookies.
        # WARUM? Schnelle Übersicht für den Client (kein manuelles Parsen nötig).
        stats = cookie_mgr.get_cookie_stats(cookies)
        
        # ═══════════════════════════════════════════════════════════════════
        # SCHRITT 8: Optional in Datei speichern
        # ═══════════════════════════════════════════════════════════════════
        
        # WARUM Optional? Client kann save_to_file=False setzen (nur in Response).
        # Default: True (Persistenz empfohlen).
        saved_to = None
        if request.save_to_file:
            # Speichere Cookies als JSON-Datei.
            # WARUM request.filename? Client kann Dateiname wählen (z.B. für Backups).
            # Default: "heypiggy-cookies.json".
            saved_to = cookie_mgr.save_cookies(cookies, filename=request.filename)
        
        # ═══════════════════════════════════════════════════════════════════
        # SCHRITT 9: Dauer berechnen
        # ═══════════════════════════════════════════════════════════════════
        
        # elapsed = aktuelle Zeit - Startzeit.
        # WARUM .2f? Zwei Dezimalstellen sind ausreichend (0.45s, 1.23s).
        elapsed = time.time() - start_time
        
        # ═══════════════════════════════════════════════════════════════════
        # SCHRITT 10: Response zurückgeben
        # ═══════════════════════════════════════════════════════════════════
        
        return CookieExtractResponse(
            status="success",              # Operation erfolgreich
            profile=request.profile_name,   # Bestätigung: welches Profil
            cookies=cookies,               # Liste der Cookie-Dicts
            count=len(cookies),            # Anzahl der Cookies
            stats=stats,                   # Statistiken (total, domains, etc.)
            saved_to=saved_to,             # Pfad zur gespeicherten Datei (oder None)
            execution_time=f"{elapsed:.2f}s",  # Dauer als String (human-readable)
        )
    
    except Exception as e:
        # ═══════════════════════════════════════════════════════════════════
        # FEHLERBEHANDLUNG
        # ═══════════════════════════════════════════════════════════════════
        
        # WARUM try/except um ALLES? Jeglicher Fehler (Playwright, Dateisystem,
        # Netzwerk) wird als HTTPException(500) zurückgegeben.
        # Client bekommt klare Fehlermeldung (nicht interner Server-Fehler mit HTML).
        
        # Dauer berechnen (auch bei Fehler — nützlich für Debugging).
        elapsed = time.time() - start_time
        
        # Logge Fehler (mit Stack-Trace für Debugging).
        logger.error(f"Cookie-Extraktion fehlgeschlagen: {e}")
        
        # HTTPException(500): Internal Server Error — unerwarteter Fehler.
        # detail=str(e): Die Fehlermeldung wird im Response Body angezeigt.
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINT 2: POST /cookies/inject
# ═══════════════════════════════════════════════════════════════════════════════
# Injiziert gespeicherte Cookies in den Browser.
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/inject", response_model=CookieInjectResponse)
async def inject_cookies(request: CookieInjectRequest):
    """
    Injiziert gespeicherte Cookies in den Browser.
    
    ABLAUF:
    1. Starte Zeit-Messung (elapsed_time).
    2. Hole BrowserManager-Singleton.
    3. Prüfe ob Chrome läuft (browser_mgr.is_running).
       Wenn nicht → HTTPException(400, "Browser nicht gestartet").
    4. Hole CookieManager-Singleton.
    5. Lade Cookies aus Datei (cookie_mgr.load_cookies()).
       Wenn Datei nicht existiert → FileNotFoundError → HTTPException(404).
    6. Hole BrowserContext (await browser_mgr.get_page().context).
       WARUM Context? Cookies werden im BrowserContext (nicht Page) gespeichert.
    7. Injiziere Cookies (await cookie_mgr.inject_cookies()).
       Robuste Einzel-Injektion (ein Fehler killt nicht alle).
    8. Optional: Verifiziere Session (cookie_mgr.verify_session()).
       Wenn verify_session=True → navigiere zum Dashboard und prüfe Login-Status.
    9. Berechne elapsed_time.
    10. Gib CookieInjectResponse zurück.
    
    WARUM Browser-Check?
    → Gleicher Grund wie bei extract: Chrome muss laufen um Cookies zu injizieren.
    → Wenn Chrome nicht läuft → keine Seite zum Injizieren (kein Context).
    → Client sollte vorher POST /browser/start aufrufen.
    
    WARUM FileNotFoundError abfangen?
    → Wenn Cookie-Datei nicht existiert → load_cookies() wirft FileNotFoundError.
    → HTTPException(404) ist der passende Status-Code (Resource not found).
    → Klare Fehlermeldung: "Cookie-Datei nicht gefunden. Rufe zuerst POST /cookies/extract auf.".
    → Der Client weiß SOFORT was zu tun ist (Extraktion vor Injektion).
    
    WARUM Context statt Page?
    → Playwright's Cookies sind im BrowserContext (nicht in der Page).
    → context.add_cookies() fügt Cookies zum Context hinzu (gilt für ALLE Pages).
    → page.context gibt den Context der Page zurück.
    → WARUM nicht browser_mgr._context? Private Attribute sollten nicht direkt
    → verwendet werden (Encapsulation). page.context ist die öffentliche API.
    
    WARUM verify_session default=True?
    → Bestätigung: Die injizierten Cookies funktionieren tatsächlich.
    → Wenn verify_session=False → Client weiß nicht ob Session aktiv ist.
    → Mögliches Szenario: Cookies abgelaufen → Injektion "erfolgreich" aber
    → Session tot → Client macht 10 Fehlversuche bevor er merkt dass Login nötig ist.
    → verify_session=True fängt das SOFORT ab.
    
    WARUM verify_session Zeit?
    → Navigation zum Dashboard + Prüfung dauert ~3-5s.
    → Das verlangsamt den Injektions-Endpoint.
    → Trade-off: Geschwindigkeit vs. Zuverlässigkeit.
    → Für Produktion: verify_session=True (Zuverlässigkeit wichtiger).
    → Für Debugging: verify_session=False (schneller).
    
    WARUM injected_count in Response?
    → Wenn injected_count < len(cookies) → einige Cookies waren ungültig.
    → Mögliche Ursachen: Domain-Mismatch, abgelaufene Cookies, falsches Format.
    → Client kann darauf reagieren: "Nur 5/7 Cookies injiziert → evtl. Problem".
    
    Args:
        request: CookieInjectRequest
            - filename: Dateiname der Cookies (default: "heypiggy-cookies.json").
            - verify_session: Session nach Injektion prüfen? (default: True).
    
    Returns:
        CookieInjectResponse:
            - status: "success", "failed", oder "error".
            - injected_count: Anzahl erfolgreich injizierter Cookies.
            - session_active: True wenn Session nach Injektion aktiv (eingeloggt).
            - execution_time: Dauer der Operation.
            - error: Fehlermeldung wenn Status="error".
    
    Raises:
        HTTPException(400): Wenn Browser nicht gestartet ist.
        HTTPException(404): Wenn Cookie-Datei nicht existiert.
        HTTPException(500): Bei unerwarteten Fehlern.
    
    Example:
        POST /cookies/inject
        {"filename": "heypiggy-cookies.json", "verify_session": true}
        → {"status": "success", "injected_count": 7, "session_active": true,
            "execution_time": "1.23s"}
    """
    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 1: Zeit-Messung starten
    # ═══════════════════════════════════════════════════════════════════════
    
    start_time = time.time()
    
    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 2: BrowserManager holen
    # ═══════════════════════════════════════════════════════════════════════
    
    browser_mgr = get_browser_manager()
    
    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 3: Prüfen ob Chrome läuft
    # ═══════════════════════════════════════════════════════════════════════
    
    if not browser_mgr.is_running:
        raise HTTPException(
            status_code=400,
            detail="Browser nicht gestartet. Rufe POST /browser/start auf."
        )
    
    try:
        # ═══════════════════════════════════════════════════════════════════
        # SCHRITT 4: CookieManager holen
        # ═══════════════════════════════════════════════════════════════════
        
        cookie_mgr = get_cookie_manager()
        
        # ═══════════════════════════════════════════════════════════════════
        # SCHRITT 5: Cookies laden
        # ═══════════════════════════════════════════════════════════════════
        
        # Lade Cookies aus JSON-Datei.
        # WARUM load_cookies()? Liest die zuvor gespeicherte JSON-Datei.
        # Wenn Datei nicht existiert → FileNotFoundError (wird unten abgefangen).
        cookies = cookie_mgr.load_cookies(filename=request.filename)
        
        # ═══════════════════════════════════════════════════════════════════
        # SCHRITT 6: BrowserContext holen
        # ═══════════════════════════════════════════════════════════════════
        
        # Hole aktive Page (automatischer Start wenn nötig).
        page = await browser_mgr.get_page()
        
        # Hole Context der Page (Cookies werden im Context gespeichert).
        # WARUM page.context? Öffentliche Playwright-API (nicht privates _context).
        context = page.context
        
        # ═══════════════════════════════════════════════════════════════════
        # SCHRITT 7: Cookies injizieren
        # ═══════════════════════════════════════════════════════════════════
        
        # Injiziere Cookies in den BrowserContext.
        # WARUM await? inject_cookies() ist async (Playwright API).
        # Einzelne Injektion: Ein Fehler killt nicht alle anderen Cookies.
        injected_count = await cookie_mgr.inject_cookies(context, cookies)
        
        # ═══════════════════════════════════════════════════════════════════
        # SCHRITT 8: Optional Session verifizieren
        # ═══════════════════════════════════════════════════════════════════
        
        # WARUM Optional? Client kann verify_session=False setzen (schneller).
        session_active = False
        if request.verify_session:
            # Verifiziere Session: Navigiere zum Dashboard und prüfe Login-Status.
            # WARUM await? verify_session() ist async (Navigation + DOM-Prüfung).
            session_active = await cookie_mgr.verify_session(page)
        
        # ═══════════════════════════════════════════════════════════════════
        # SCHRITT 9: Dauer berechnen
        # ═══════════════════════════════════════════════════════════════════
        
        elapsed = time.time() - start_time
        
        # ═══════════════════════════════════════════════════════════════════
        # SCHRITT 10: Response zurückgeben
        # ═══════════════════════════════════════════════════════════════════
        
        return CookieInjectResponse(
            status="success",                # Operation erfolgreich
            injected_count=injected_count,   # Anzahl injizierter Cookies
            session_active=session_active,  # Session aktiv? (nur wenn verify_session=True)
            execution_time=f"{elapsed:.2f}s",  # Dauer als String
        )
    
    except FileNotFoundError as e:
        # ═══════════════════════════════════════════════════════════════════
        # FEHLER: Cookie-Datei nicht gefunden
        # ═══════════════════════════════════════════════════════════════════
        
        # WARUM 404? Die Ressource (Cookie-Datei) existiert nicht.
        # Das ist ein Client-Fehler (falscher Dateiname oder nicht extrahiert).
        raise HTTPException(
            status_code=404,
            detail=f"Cookie-Datei nicht gefunden: {request.filename}. Rufe zuerst POST /cookies/extract auf."
        )
    
    except Exception as e:
        # ═══════════════════════════════════════════════════════════════════
        # FEHLER: Unerwarteter Fehler
        # ═══════════════════════════════════════════════════════════════════
        
        # Dauer berechnen (auch bei Fehler).
        elapsed = time.time() - start_time
        
        # Logge Fehler.
        logger.error(f"Cookie-Injektion fehlgeschlagen: {e}")
        
        # HTTPException(500): Internal Server Error.
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINT 3: POST /cookies/verify
# ═══════════════════════════════════════════════════════════════════════════════
# Prüft ob eine HeyPiggy-Session aktiv ist.
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/verify")
async def verify_session():
    """
    Prüft ob eine HeyPiggy-Session aktiv ist.
    
    ABLAUF:
    1. Hole BrowserManager-Singleton.
    2. Prüfe ob Chrome läuft (browser_mgr.is_running).
       Wenn nicht → HTTPException(400, "Browser nicht gestartet").
    3. Hole CookieManager-Singleton.
    4. Hole aktive Page (await browser_mgr.get_page()).
    5. Verifiziere Session (await cookie_mgr.verify_session(page)).
       Navigiert zum Dashboard und prüft "Abmelden"-Button.
    6. Gib Dict zurück: {"status": "success", "session_active": bool, "url": str}.
    
    WARUM kein Request-Body?
    → Keine Parameter nötig (kein Filter, keine Optionen).
    → Einfacher Call: POST /cookies/verify (leerer Body).
    → Wenn Parameter nötig werden (z.B. expected_url) → später hinzufügen.
    
    WARUM verify_session()?
    → Die BESTE Methode um zu prüfen ob Cookies funktionieren.
    → Echte Navigation + DOM-Prüfung (kein "sieht gut aus" Raten).
    → Wenn "Abmelden" sichtbar → Session ist definitiv aktiv.
    → Wenn "Anmelden" sichtbar → Session ist tot (neu einloggen nötig).
    
    WARUM {"status": "success", ...} statt Pydantic-Modell?
    → Einfachheit: Nur 3 Felder (status, session_active, url).
    → Kein komplexes Modell nötig (keine Optional-Felder, keine Validierung).
    → Aber: In Zukunft könnte ein Pydantic-Modell hinzugefügt werden
    → (für Konsistenz mit anderen Endpoints).
    
    WARUM url in Response?
    → Client kann prüfen: Auf welcher Seite sind wir?
    → Wenn url != "heypiggy.com" → evtl. Redirect oder Fehler.
    → Nützlich für Debugging: "Session aktiv aber auf falschem Dashboard?".
    
    WARUM nicht elapsed_time?
    → Verifikation ist schnell (~3-5s).
    → Nicht performance-kritisch (wird nicht so oft aufgerufen).
    → Wenn nötig → später hinzufügen.
    
    Returns:
        Dict: {"status": "success", "session_active": bool, "url": str}
        session_active=True → eingeloggt, "Abmelden" sichtbar.
        session_active=False → ausgeloggt, "Anmelden" sichtbar.
    
    Raises:
        HTTPException(400): Wenn Browser nicht gestartet ist.
        HTTPException(500): Bei unerwarteten Fehlern.
    
    Example:
        POST /cookies/verify
        → {"status": "success", "session_active": true,
            "url": "https://www.heypiggy.com/?page=dashboard"}
    """
    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 1: BrowserManager holen
    # ═══════════════════════════════════════════════════════════════════════
    
    browser_mgr = get_browser_manager()
    
    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 2: Prüfen ob Chrome läuft
    # ═══════════════════════════════════════════════════════════════════════
    
    if not browser_mgr.is_running:
        raise HTTPException(
            status_code=400,
            detail="Browser nicht gestartet."
        )
    
    try:
        # ═══════════════════════════════════════════════════════════════════
        # SCHRITT 3: CookieManager holen
        # ═══════════════════════════════════════════════════════════════════
        
        cookie_mgr = get_cookie_manager()
        
        # ═══════════════════════════════════════════════════════════════════
        # SCHRITT 4: Page holen
        # ═══════════════════════════════════════════════════════════════════
        
        # Hole aktive Page (automatischer Start wenn nötig).
        page = await browser_mgr.get_page()
        
        # ═══════════════════════════════════════════════════════════════════
        # SCHRITT 5: Session verifizieren
        # ═══════════════════════════════════════════════════════════════════
        
        # Verifiziere Session: Navigiere zum Dashboard und prüfe Login-Status.
        # WARUM await? verify_session() ist async (Navigation + DOM-Prüfung).
        # Rückgabe: True (eingeloggt) oder False (ausgeloggt).
        is_active = await cookie_mgr.verify_session(page)
        
        # ═══════════════════════════════════════════════════════════════════
        # SCHRITT 6: Response zurückgeben
        # ═══════════════════════════════════════════════════════════════════
        
        # Einfaches Dict (kein Pydantic-Modell nötig für 3 Felder).
        return {
            "status": "success",        # Operation erfolgreich (kein Fehler)
            "session_active": is_active,  # True = eingeloggt, False = ausgeloggt
            "url": page.url,             # Aktuelle URL (für Debugging)
        }
    
except Exception as e:
        # ═══════════════════════════════════════════════════════════════════════
        # FEHLERBEHANDLUNG
        # ═══════════════════════════════════════════════════════════════════════
        
        # Logge Fehler.
        logger.error(f"Session-Prüfung fehlgeschlagen: {e}")
        
        # HTTPException(500): Internal Server Error.
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINT 4: POST /cookies/backup (2026-05-08)
# ═══════════════════════════════════════════════════════════════════════════════
# Erstellt Read-Only Backup aus validierten Working-Cookies.
# WICHTIG: Nur aufrufen NACHDEM Session validiert und Cookies frisch extrahiert wurden!
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/backup", response_model=BackupCreateResponse)
async def create_cookie_backup(request: BackupCreateRequest):
    """
    Erstellt ein READ-ONLY Backup der aktuellen Working-Cookies.
    
    VORAUSSETZUNG:
    - POST /cookies/extract oder /cookies/extract-safe wurde erfolgreich ausgefuehrt.
    - Working-Cookies sind FRISCH und die Session ist VALIDE.
    
    Das Backup ist read-only (chmod 444/555). Der Agent KANN und DARF NICHT
    in das Backup schreiben. Er kann es NUR lesen (kopieren via /cookies/recover).
    
    WARUM READ-ONLY?
    - Verhindert versehentliches Ueberschreiben durch einen Agenten.
    - Backup ist IMMER der letzte bekannte gute Zustand.
    """
    try:
        result = CookieManager.create_backup(
            working_filename=request.working_filename,
            working_dir=request.working_dir
        )
        return BackupCreateResponse(**result)
    except Exception as e:
        logger.error(f"Backup failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINT 5: POST /cookies/recover (2026-05-08)
# ═══════════════════════════════════════════════════════════════════════════════
# Stellt Backup-Cookies im Working-Dir wieder her.
# WICHTIG: Browser muss danach NEU gestartet werden!
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/recover", response_model=RecoveryResponse)
async def recover_cookies(request: RecoveryRequest):
    """
    Session Recovery: Stellt saubere Backup-Cookies wieder her.
    
    ABLAUF:
    1. Prueft ob Backup existiert (~/.stealth/heypiggy-backup/heypiggy-cookies.json).
    2. Kopiert Backup -> Working-Dir (ueberschreibt kaputte Datei).
    3. Setzt Working-Datei auf schreibbar (chmod 644).
    4. Gibt Status zurueck.
    
    DANACH: Browser NEU starten (POST /browser/start oder /services/heypiggy/login).
    Die alten abgelaufenen Cookies wurden NICHT gespeichert.
    """
    try:
        result = CookieManager.recover_from_backup(
            working_filename=request.working_filename,
            working_dir=request.working_dir
        )
        return RecoveryResponse(**result)
    except Exception as e:
        logger.error(f"Recovery failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINT 6: POST /cookies/extract-safe (2026-05-08)
# ═══════════════════════════════════════════════════════════════════════════════
# Extrahiert Cookies NUR wenn Session AKTIV ist (Safe-Save).
# Verhindert: Ueberschreiben guter Cookies mit abgelaufenen.
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/extract-safe")
async def extract_cookies_safe(request: CookieExtractRequest):
    """
    SAFE Cookie Extract: Extrahiert NUR wenn Session validiert ist.
    
    NIEMALS speichern wenn Session abgelaufen ist!
    
    ABLAUF:
    1. Holt Page/Context vom BrowserManager.
    2. Extrahiert Cookies (wie /cookies/extract).
    3. Prueft Session via verify_session().
    4. Wenn Session AKTIV -> speichert normal.
    5. Wenn Session TOT -> NIEMALS speichern, gibt Error zurueck.
    
    WARUM das wichtig ist:
    - Ohne diesen Check: Agent extrahiert abgelaufene Cookies,
      ueberschreibt die guten Backup-Daten, alles ist zerschossen.
    - Mit diesem Check: Agent merkt "Session tot", speichert nix,
      und der Recovery-Button (/cookies/recover) bleibt wirksam.
    """
    try:
        browser_mgr = get_browser_manager()
        
        if not browser_mgr.is_running:
            raise HTTPException(
                status_code=400,
                detail="Browser nicht gestartet. Rufe POST /browser/start auf."
            )
        
        page = await browser_mgr.get_page()
        cookie_mgr = get_cookie_manager()
        cookies = await cookie_mgr.extract_cookies(
            page, domain_filter=request.domain_filter
        )
        
        safe_result = await cookie_mgr.safe_save_cookies(
            page, cookies, request.filename
        )
        
        if not safe_result.get("saved"):
            raise HTTPException(
                status_code=409,
                detail=safe_result.get("message",
                    "Cookie-Speicherung verweigert: Session abgelaufen. "
                    "Rufe /cookies/recover auf um Backup wiederherzustellen."
                )
            )
        
        stats = cookie_mgr.get_cookie_stats(cookies)
        
        return {
            "status": "success",
            "cookies": cookies,
            "count": len(cookies),
            "stats": stats,
            "saved_to": safe_result.get("filepath"),
            "message": safe_result.get("message"),
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Safe-Extract fehlgeschlagen: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# ENDE VON COOKIE_ROUTES.PY
# ═══════════════════════════════════════════════════════════════════════════════
# ZUSAMMENFASSUNG:
#
# Diese Datei implementiert 6 Cookie-Management-Endpoints:
#   1. POST /cookies/extract   → Cookies aus Browser extrahieren + speichern.
#   2. POST /cookies/inject    → Cookies aus Datei in Browser laden + verifizieren.
#   3. POST /cookies/verify    → Session-Status prüfen (eingeloggt/ausgeloggt).
#   4. POST /cookies/backup    → Backup aus validen Working-Cookies erstellen (read-only).
#   5. POST /cookies/recover   → Backup in Working-Dir wiederherstellen.
#   6. POST /cookies/extract-safe → Extrahiert NUR wenn Session lebt (verhindert Ueberschreiben).
#
# DESIGN-PRINZIPIEN:
#   1. Modularität: Router ist unabhängig von main.py (kann isoliert getestet werden).
#   2. Fail-Fast: Browser-Check VOR Operation (kein sinnloses Warten).
#   3. Klare Fehlermeldungen: Client weiß SOFORT was zu tun ist (z.B. "Rufe /browser/start auf").
#   4. Performance-Monitoring: execution_time für jede Operation.
#   5. Robustheit: Einzelne Cookie-Injektion (ein Fehler killt nicht alle).
#
# WORKFLOW (HEYPIGGY):
#   1. Manuell bei HeyPiggy einloggen (einmalig).
#   2. POST /cookies/extract → Cookies speichern (./data/heypiggy-cookies.json).
#   3. Bei jedem Start: POST /cookies/inject → Session aktivieren.
#   4. POST /cookies/verify → Prüfen ob Session noch gültig.
#   5. Wenn abgelaufen: Schritt 1 wiederholen (neu einloggen).
#
# REGISTRIERUNG IN MAIN.PY:
#   from api.cookie_routes import router as cookie_router
#   app.include_router(cookie_router)
# ═══════════════════════════════════════════════════════════════════════════════
