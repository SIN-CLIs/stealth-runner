"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║           STEALTH-RUNNER — Cookie Manager (HeyPiggy-Fokussiert)               ║
║                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ZWECK / PURPOSE:                                                            ║
║  ────────────────                                                            ║
║  Verwaltet HeyPiggy-Session-Cookies: Extrahieren, Speichern, Injizieren,      ║
║  und Verifizieren.                                                           ║
║                                                                              ║
║  WARUM COOKIE-MANAGEMENT?                                                     ║
║  ─────────────────────────                                                     ║
║  HeyPiggy verwendet Google OAuth für den Login. Google OAuth ist            ║
║  NICHT vollständig automatisierbar (Shadow-DOM, Anti-Bot, 2FA).            ║
║  Lösung: Einmal manuell einloggen → Cookies extrahieren → wiederverwenden.   ║
║                                                                              ║
║  OHNE COOKIE-PERSISTENZ:                                                     ║
║  ─────────────────────────                                                   ║
║  → Bei jedem Chrome-Neustart: Neu einloggen (Google OAuth = 2-5 Minuten).   ║
║  → Bei jedem API-Restart: Neu einloggen.                                    ║
║  → Zeitverlust, Rate-Limits, Account-Sperrung möglich.                       ║
║                                                                              ║
║  MIT COOKIE-PERSISTENZ:                                                      ║
║  ───────────────────────                                                     ║
║  → Einmalig: Manuell einloggen → Cookies speichern.                         ║
║  → Danach: Bei jedem Start → Cookies injizieren → sofort eingeloggt.        ║
║  → Zeitersparnis: ~2-5 Minuten pro Session.                                 ║
║  → Keine erneuten Login-Versuche (keine Rate-Limits).                       ║
║                                                                              ║
║  ARCHITEKTUR-OVERVIEW:                                                       ║
║  ─────────────────────                                                       ║
║  ┌─────────────────────────────────────────────────────────────────────┐    ║
║  │ CookieManager (Singleton)                                             │    ║
║  │ ├── extract_cookies(page, domain_filter) → List[Cookie]             │    ║
║  │ ├── save_cookies(cookies, filename) → filepath                    │    ║
║  │ ├── load_cookies(filename) → List[Cookie]                           │    ║
║  │ ├── inject_cookies(context, cookies) → int (injected_count)        │    ║
║  │ ├── verify_session(page) → bool (session_active)                   │    ║
║  │ └── get_cookie_stats(cookies) → Dict[str, Any] (statistics)        │    ║
║  └─────────────────────────────────────────────────────────────────────┘    ║
║                                                                              ║
║  DATEI-FORMAT (JSON):                                                        ║
║  ─────────────────────                                                         ║
║  Cookies werden als JSON gespeichert mit Metadaten:                           ║
║  {                                                                             ║
║    "metadata": {                                                               ║
║      "created_at": "2026-05-07T14:30:00",                                    ║
║      "count": 7,                                                               ║
║      "source": "heypiggy"                                                      ║
║    },                                                                          ║
║    "cookies": [                                                                ║
║      {"name": "PHPSESSID", "value": "abc123", "domain": "heypiggy.com"},     ║
║      ...                                                                       ║
║    ]                                                                           ║
║  }                                                                             ║
║                                                                              ║
║  WARUM JSON statt SQLite/Redis?                                              ║
║  ──────────────────────────────                                              ║
║  • JSON ist human-readable (einfach zu debuggen).                            ║
║  • Keine External Dependencies (sqlite3 ist Standard, aber Redis nicht).    ║
║  • Einfach zu versionieren (git diff zeigt Änderungen).                      ║
║  • Portabel: JSON-Datei kann auf andere Maschinen kopiert werden.            ║
║  • Einfach zu bearbeiten (Text-Editor).                                      ║
║                                                                              ║
║  SICHERHEIT / BANNED PATTERNS:                                               ║
║  ──────────────────────────────                                              ║
║  • KEINE Passwörter in Cookie-Datei (nur Session-Cookies wie PHPSESSID).     ║
║  • Cookie-Datei in .gitignore (nicht ins Repository commitieren!).            ║
║  • NIEMALS Cookies auf öffentlichen Servern speichern (Datenschutz!).       ║
║  • Session-Cookies (expires=-1) sind besonders wichtig (kein Ablaufdatum).   ║
║  • Secure-Flag Cookies nur über HTTPS senden (wird von Browser enforced).   ║
║                                                                              ║
║  HEYPIGGY SPEZIFISCHE COOKIES:                                               ║
║  ──────────────────────────────                                              ║
║  Wichtige Cookies (beobachtet bei manuellem Login):                           ║
║  • PHPSESSID        → Session-ID (wichtigste Cookie für Login-Status).     ║
║  • user_a_b_group   → A/B Testing Gruppe (nicht kritisch).                   ║
║  • lang_pig=de      → Spracheinstellung (Deutsch).                           ║
║  • user_id=2525530  → User-ID (identifiziert den Account).                  ║
║  • user_session     → Session-Token (zusätzliche Authentifizierung).        ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

# ═══════════════════════════════════════════════════════════════════════════════
# IMPORTS: Was brauchen wir und WARUM?
# ═══════════════════════════════════════════════════════════════════════════════

# json: JSON Serialisierung/Deserialisierung.
# WARUM? - Cookie-Dateien werden als JSON gespeichert (human-readable, portabel).
#        - json.dump() schreibt Dict/List als JSON-String in Datei.
#        - json.load() liest JSON-String aus Datei und gibt Dict/List zurück.
#        - Standard-Library (keine External Dependencies).
import json

# logging: Log-Ausgaben (nicht print!).
# WARUM? - Logs können in Dateien geschrieben werden (für Debugging und Monitoring).
#        - Log-Level (INFO, WARNING, ERROR) ermöglichen Filterung.
#        - Konsistenz: Playwright und andere Libraries verwenden logging.
#        - __name__ → Logger-Name enthält Modul-Pfad ("core.cookie_manager").
import logging

# Path: Objekt-orientierte Pfad-Manipulation (cross-platform).
# WARUM? - Sicherer als String-Konkatenation (Path("a") / "b" funktioniert
#          auf Windows UND Linux/Mac).
#        - Elegante Methoden: .mkdir(), .exists(), .rglob(), .unlink().
#        - Path.home() gibt Home-Verzeichnis zurück (plattform-unabhängig).
from pathlib import Path

import os
import shutil

# Typ-Hinweise für bessere Code-Klarheit und IDE-Unterstützung.
# List, Dict, Any: Flexible Typen für Cookie-Dictionaries (unterschiedliche Felder).
# Optional: Ein Wert ODER None (z.B. domain_filter=None = alle Domains).
from typing import List, Dict, Any, Optional

# datetime: Zeitstempel für Cookie-Metadaten.
# WARUM? - datetime.now().isoformat() gibt ISO 8601 Zeitstempel ("2026-05-07T14:30:00").
#        - Menschen-lesbar, standardisiert, sortierbar.
#        - Ermöglicht Erkennung veralteter Cookies ("Letztes Update vor 30 Tagen").
from datetime import datetime

# Playwright: Browser-Automation Library.
# BrowserContext: Ein Browser-Kontext (Profil, Cookies, LocalStorage).
# Page: Einzelne Browser-Tab/Seite.
# WARUM Playwright? - Einfache Cookie-API (context.cookies(), context.add_cookies()).
#                   - Async-native (kann in FastAPI Endpoints verwendet werden).
#                   - Standard für moderne Browser-Automation.
from playwright.async_api import BrowserContext, Page

# Logger-Instanz für diese Datei.
# WARUM __name__? Der Logger-Name enthält den Modul-Pfad ("core.cookie_manager").
# Ermöglicht gezieltes Logging-Level pro Modul (DEBUG für cookie_manager, INFO für Rest).
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# KLASSE: CookieManager
# ═══════════════════════════════════════════════════════════════════════════════
# Der CookieManager ist ein SINGLETON — es gibt NUR EINE Instanz pro Prozess.
# WARUM Singleton?
# → Einheitlicher Zugriff auf Cookie-Dateien (keine Race Conditions beim Schreiben).
# → Zentrale Konfiguration (cookies_dir, Dateiformat).
# → Wiederverwendung: Instanz wird gecacht, nicht bei jedem Aufruf neu erstellt.
# ═══════════════════════════════════════════════════════════════════════════════


class CookieManager:
    """
    Verwaltet Browser-Cookies für Session-Persistenz.
    
    Extrahiert, speichert, lädt und injiziert Cookies ohne dass ein
    erneutes Login nötig ist. HeyPiggy-spezifisch optimiert.
    
    LEBENSZYKLUS:
    1. Einmalig: Manuell bei HeyPiggy einloggen.
    2. Extraktion: extract_cookies() → alle Cookies vom Browser holen.
    3. Speicherung: save_cookies() → Cookies in JSON-Datei schreiben.
    4. Wiederverwendung: load_cookies() → Cookies aus Datei lesen.
    5. Injektion: inject_cookies() → Cookies in neuen Browser laden.
    6. Verifikation: verify_session() → prüfen ob Login noch gültig ist.
    
    THREAD-SAFETY / ASYNC-SAFETY:
    - CookieManager ist NICHT Thread-Safe (keine Locks beim Schreiben).
    - In FastAPI (Single-Threaded Async) ist das kein Problem.
    - Wenn mehrere Threads gleichzeitig schreiben → File-Corruption möglich!
    - Lösung: Lock um save_cookies() hinzufügen (wenn Multi-Threading nötig).
    
    ATTRIBUTES:
    - cookies_dir: Verzeichnis für Cookie-Dateien (default: ./data).
                   Wird automatisch erstellt wenn nicht existiert.
    
    Usage:
        manager = CookieManager(cookies_dir="./data")
        
        # Extrahieren (nach manuellem Login)
        cookies = await manager.extract_cookies(page, domain_filter="heypiggy")
        manager.save_cookies(cookies, "heypiggy-cookies.json")
        
        # Wiederverwenden (bei neuem Start)
        cookies = manager.load_cookies("heypiggy-cookies.json")
        await manager.inject_cookies(context, cookies)
        is_active = await manager.verify_session(page)
    """
    
    def __init__(self, cookies_dir: str = "./data"):
        """
        Initialisiert den Cookie-Manager.
        
        ABLAUF:
        1. Speichere cookies_dir als Path-Objekt.
        2. Erstelle Verzeichnis wenn nicht existiert (mkdir parents=True, exist_ok=True).
        
        WARUM cookies_dir="./data"?
        → "./data" = Unterverzeichnis im aktuellen Arbeitsverzeichnis.
        → Nicht im Repository-Root (Vermeidung von Accidental Commits).
        → In .gitignore: data/ → Cookie-Dateien werden nicht committed.
        
        WARUM Path statt str?
        → Path bietet Methoden wie .mkdir(), .exists(), / (Operator für Sub-Pfade).
        → Plattform-unabhängig (Windows: backslash, Linux/Mac: slash).
        
        WARUM mkdir(parents=True, exist_ok=True)?
        → parents=True: Erstelle auch übergeordnete Verzeichnisse (z.B. ./data/heypiggy).
        → exist_ok=True: Kein Fehler wenn Verzeichnis bereits existiert.
        → idempotent: Mehrfaches Aufrufen ist OK.
        
        Args:
            cookies_dir: Verzeichnis für Cookie-Dateien (default: "./data").
                         Wird automatisch erstellt wenn nicht existiert.
        
        Returns:
            CookieManager-Instanz.
        
        Example:
            manager = CookieManager("./data")
            # Verzeichnis ./data/ existiert jetzt (oder existierte bereits).
        """
        # Speichere Verzeichnis als Path-Objekt.
        # WARUM Path(cookies_dir)? Konvertiere String zu Path-Objekt
        # (ermöglicht .mkdir(), / Operator, etc.).
        self.cookies_dir = Path(cookies_dir)
        
        # Erstelle Verzeichnis wenn nicht existiert.
        # WARUM parents=True? Erstelle auch übergeordnete Verzeichnisse.
        # WARUM exist_ok=True? Kein Fehler wenn bereits existiert (idempotent).
        self.cookies_dir.mkdir(parents=True, exist_ok=True)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # METHODE: extract_cookies
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def extract_cookies(
        self,
        page: Page,
        domain_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Extrahiert alle Cookies der aktuellen Page.
        
        ABLAUF:
        1. Rufe page.context.cookies() auf (Playwright API).
           Gibt Liste aller Cookies im Context zurück.
        2. Wenn domain_filter gesetzt → filtere Cookies nach Domain.
           "heypiggy" matcht "heypiggy.com", ".heypiggy.com", etc.
        3. Logge Anzahl der extrahierten Cookies.
        4. Gib gefilterte (oder alle) Cookies zurück.
        
        WARUM page.context.cookies()?
        → Playwright's BrowserContext speichert alle Cookies.
        → page.context gibt den Context der Page zurück.
        → Alle Cookies = über alle Domains und Pages hinweg.
        
        WARUM domain_filter?
        → HeyPiggy hat ~7 relevante Cookies.
        → Alle Domains (inkl. Google, Analytics, etc.) = HUNDERTE Cookies.
        → Filter reduziert Datenmenge und fokussiert auf relevante Cookies.
        → "heypiggy" matcht Domain "heypiggy.com" und ".heypiggy.com".
        
        WARUM async?
        → page.context.cookies() ist eine Playwright-Methode (async).
        → Wir MÜSSEN await verwenden (sonst Coroutine-Objekt statt Liste).
        
        WARUM List[Dict[str, Any]]?
        → Jedes Cookie ist ein Dictionary mit verschiedenen Feldern.
        → Beispiel: {"name": "PHPSESSID", "value": "abc123", "domain": ".heypiggy.com"}
        → Felder variieren: name, value, domain, path, expires, httpOnly, secure, sameSite.
        → Dict[str, Any] ist flexibler als ein Pydantic-Model (Playwright gibt Dict zurück).
        
        Args:
            page: Playwright Page-Objekt (aus dem Cookies extrahiert werden).
            domain_filter: Optionaler Domain-Filter.
                - None = alle Cookies (kein Filter).
                - "heypiggy" = nur Cookies die "heypiggy" in der Domain haben.
                - ".heypiggy.com" = nur diese Domain (exakt).
        
        Returns:
            Liste von Cookie-Dictionaries.
            Beispiel: [{"name": "PHPSESSID", "value": "abc123", "domain": ".heypiggy.com"}, ...]
        
        Example:
            cookies = await manager.extract_cookies(page, domain_filter="heypiggy")
            # cookies = [{"name": "PHPSESSID", ...}, {"name": "user_id", ...}, ...]
            # Nur Cookies von heypiggy.com (nicht Google, Analytics, etc.).
        """
        # Extrahiere alle Cookies vom BrowserContext.
        # page.context gibt den BrowserContext zurück (enthält alle Cookies).
        # .cookies() gibt eine Liste von Cookie-Dicts zurück (Playwright API).
        cookies = await page.context.cookies()
        
        # Wenn domain_filter gesetzt → filtere Cookies.
        # WARUM if domain_filter? Ohne Filter → alle Cookies zurückgeben.
        # Mit Filter → nur Cookies die den Filter-String in der Domain haben.
        if domain_filter:
            # List comprehension: Filtere Cookies nach Domain.
            # c.get("domain", "") gibt die Domain zurück (oder leerer String wenn nicht vorhanden).
            # "heypiggy" in "www.heypiggy.com" → True (matcht).
            # "heypiggy" in ".heypiggy.com" → True (matcht).
            # "heypiggy" in "google.com" → False (nicht matcht).
            cookies = [
                c for c in cookies
                if domain_filter in (c.get("domain") or "")
            ]
        
        # Logge Anzahl der extrahierten Cookies.
        # WARUM? Monitoring: Wenn 0 Cookies → Session nicht aktiv (nicht eingeloggt).
        # Wenn 7 Cookies → normale HeyPiggy-Session.
        # Wenn 100+ Cookies → kein Filter angewendet (oder viele Domains).
        logger.info(
            f"{len(cookies)} Cookies extrahiert"
            + (f" (Filter: {domain_filter})" if domain_filter else "")
        )
        
        # Gib Cookies zurück.
        return cookies
    
    # ═══════════════════════════════════════════════════════════════════════════
    # METHODE: save_cookies
    # ═══════════════════════════════════════════════════════════════════════════
    
    def save_cookies(
        self,
        cookies: List[Dict[str, Any]],
        filename: str = "heypiggy-cookies.json"
    ) -> str:
        """
        Speichert Cookies in eine JSON-Datei.
        
        ABLAUF:
        1. Erstelle Datei-Pfad: cookies_dir / filename.
        2. Serialisiere Cookies (nur serialisierbare Felder).
        3. Füge Metadaten hinzu (created_at, count, source).
        4. Schreibe JSON-Datei (pretty-printed mit indent=2).
        5. Logge Speicherung.
        6. Gib Datei-Pfad zurück.
        
        WARUM serialisierbare Felder?
        → Playwright-Cookies können NICHT-serialisierbare Felder haben
        → (z.B. datetime-Objekte, Enum-Werte).
        → Wir extrahieren nur die wichtigsten Felder (name, value, domain, etc.).
        → Das garantiert dass json.dump() funktioniert (kein TypeError).
        
        WARUM Metadaten?
        → created_at: Zeitstempel für Versionierung ("Wie alt sind die Cookies?").
        → count: Anzahl der Cookies (Schnell-Check ohne Datei zu parsen).
        → source: Ursprung der Cookies ("heypiggy" für Filterung).
        → Hilft beim Debugging und Monitoring.
        
        WARUM indent=2?
        → Pretty-printed JSON ist human-readable (einfach zu debuggen).
        → Einfach zu bearbeiten im Text-Editor.
        → Git diff zeigt Änderungen klar (nicht alles in einer Zeile).
        → Kompromiss: Größere Datei, aber übersichtlicher.
        
        WARUM .json Erweiterung?
        → Klare Kennzeichnung: Es ist eine JSON-Datei.
        → Einfach zu parsen (jede Sprache hat JSON-Support).
        → Keine Binary-Format (portabel, versionierbar).
        
        WARUM Datei-Pfad zurückgeben?
        → Client weiß WO die Datei gespeichert wurde.
        → Nützlich für Logging: "Cookies gespeichert unter ./data/heypiggy-cookies.json".
        → Client kann Datei direkt lesen wenn nötig.
        
        Args:
            cookies: Liste von Cookie-Dictionaries (von extract_cookies()).
            filename: Dateiname für die Cookie-Datei (default: "heypiggy-cookies.json").
                      Wird im cookies_dir-Verzeichnis gespeichert.
        
        Returns:
            str: Absoluter Pfad zur gespeicherten Datei.
            Beispiel: "./data/heypiggy-cookies.json"
        
        Raises:
            TypeError: Wenn Cookies nicht-serialisierbare Felder enthalten
                      (sollte nicht passieren wegen unserer Filterung).
        
        Example:
            filepath = manager.save_cookies(cookies, "heypiggy-cookies.json")
            # Datei ./data/heypiggy-cookies.json wurde erstellt/überschrieben.
            # Enthält: {"metadata": {...}, "cookies": [...]}
        """
        # Erstelle Datei-Pfad.
        # cookies_dir / filename → Path-Objekt (plattform-unabhängig).
        # Beispiel: Path("./data") / "heypiggy-cookies.json" → Path("./data/heypiggy-cookies.json").
        filepath = self.cookies_dir / filename
        
        # Serialisiere Cookies (nur wichtige Felder).
        # WARUM nur diese Felder? Playwright-Cookies haben manchmal zusätzliche
        # Felder die nicht JSON-serialisierbar sind (z.B. datetime-Objekte).
        # Wir filtern auf die Standard-Cookie-Felder.
        serializable = []
        for c in cookies:
            # Erstelle sauberes Cookie-Dict mit garantierten Feldern.
            # WARUM .get() mit Default? Nicht alle Cookies haben alle Felder.
            # Beispiel: "sameSite" könnte fehlen → Default "None".
            serializable.append({
                "name": c.get("name"),           # Cookie-Name (z.B. "PHPSESSID")
                "value": c.get("value"),         # Cookie-Wert (z.B. "abc123")
                "domain": c.get("domain"),       # Domain (z.B. ".heypiggy.com")
                "path": c.get("path", "/"),      # Pfad (default: "/")
                "expires": c.get("expires", -1),  # Ablaufdatum (Unix-Timestamp, -1 = Session)
                "httpOnly": c.get("httpOnly", False),  # HttpOnly-Flag (nicht via JS zugänglich)
                "secure": c.get("secure", False),      # Secure-Flag (nur über HTTPS)
                "sameSite": c.get("sameSite", "None"),   # SameSite-Attribut (None, Lax, Strict)
            })
        
        # Erstelle Datenstruktur mit Metadaten.
        # WARUM Dict mit "metadata" und "cookies"? Klare Struktur:
        # - metadata: Informationen ÜBER die Cookies (Zeit, Anzahl, Quelle).
        # - cookies: Die eigentlichen Cookie-Daten.
        data = {
            "metadata": {
                # ISO 8601 Zeitstempel (z.B. "2026-05-07T14:30:00.123456").
                # datetime.now() gibt lokale Zeit zurück.
                # isoformat() gibt String im ISO 8601 Format.
                "created_at": datetime.now().isoformat(),
                
                # Anzahl der Cookies (Schnell-Check).
                "count": len(serializable),
                
                # Quelle der Cookies (für Filterung/Identifikation).
                "source": "heypiggy",
            },
            # Die serialisierten Cookies.
            "cookies": serializable,
        }
        
        # Schreibe JSON-Datei.
        # WARUM with open()? Kontext-Manager: Datei wird automatisch geschlossen
        # (auch bei Exceptions).
        # WARUM "w"? Write-Modus (überschreibt existierende Datei).
        # WARUM indent=2? Pretty-printed JSON (human-readable).
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
        
        # Logge Speicherung.
        # WARUM? Monitoring: Wurden Cookies gespeichert? Wie viele?
        logger.info(f"{len(serializable)} Cookies gespeichert: {filepath}")
        
        # Gib Datei-Pfad zurück.
        # WARUM str()? Client erwartet String (nicht Path-Objekt).
        return str(filepath)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # METHODE: load_cookies
    # ═══════════════════════════════════════════════════════════════════════════
    
    def load_cookies(
        self,
        filename: str = "heypiggy-cookies.json"
    ) -> List[Dict[str, Any]]:
        """
        Lädt Cookies aus einer JSON-Datei.
        
        ABLAUF:
        1. Erstelle Datei-Pfad: cookies_dir / filename.
        2. Prüfe ob Datei existiert (wenn nicht → FileNotFoundError).
        3. Öffne und parse JSON.
        4. Extrahiere Cookies aus "cookies"-Array (oder ganze Daten wenn kein "cookies").
        5. Logge Anzahl der geladenen Cookies.
        6. Gib Cookies zurück.
        
        WARUM FileNotFoundError?
        → Klare Fehlermeldung: Client weiß dass die Datei fehlt.
        → HTTP 404 ist der passende Status-Code.
        → Message: "Cookie-Datei nicht gefunden: ./data/heypiggy-cookies.json".
        
        WARUM data.get("cookies", data)?
        → Unser Format: {"metadata": {...}, "cookies": [...]}.
        → Aber manchmal könnte die Datei nur ein Array sein ([...]) (Legacy).
        → data.get("cookies", data) → wenn "cookies" existiert → verwende es.
        → Sonst → verwende die ganzen Daten (falls es ein Array ist).
        
        WARUM json.load() statt json.loads()?
        → json.load(f) liest aus einem File-Objekt.
        → json.loads(string) liest aus einem String.
        → Wir haben ein File-Objekt (f) → json.load() ist direkter.
        
        Args:
            filename: Dateiname der Cookie-Datei (default: "heypiggy-cookies.json").
                      Muss im cookies_dir-Verzeichnis existieren.
        
        Returns:
            Liste von Cookie-Dictionaries.
            Beispiel: [{"name": "PHPSESSID", "value": "abc123", ...}, ...]
        
        Raises:
            FileNotFoundError: Wenn die Datei nicht existiert.
            json.JSONDecodeError: Wenn die Datei kein gültiges JSON ist.
        
        Example:
            cookies = manager.load_cookies("heypiggy-cookies.json")
            # cookies = [{"name": "PHPSESSID", "value": "abc123", ...}, ...]
            # Wenn Datei nicht existiert → FileNotFoundError.
        """
        # Erstelle Datei-Pfad.
        filepath = self.cookies_dir / filename
        
        # Prüfe ob Datei existiert.
        # WARUM? Klare Fehlermeldung statt rohem FileNotFoundError.
        # Client kann FileNotFoundError fangen und "Bitte zuerst einloggen" anzeigen.
        if not filepath.exists():
            raise FileNotFoundError(f"Cookie-Datei nicht gefunden: {filepath}")
        
        # Öffne und parse JSON.
        # WARUM with open()? Kontext-Manager: Datei wird automatisch geschlossen.
        # WARUM "r"? Read-Modus (Standard, nur lesen).
        with open(filepath, "r") as f:
            data = json.load(f)
        
        # Extrahiere Cookies.
        # WARUM data.get("cookies", data)?
        # → Unser Format hat "cookies"-Array.
        # → Aber manche Dateien könnten nur ein Array sein (Legacy).
        # → Wenn "cookies" existiert → verwende es.
        # → Sonst → verwende die ganzen Daten (falls Array).
        cookies = data.get("cookies", data)
        
        # Logge Anzahl.
        logger.info(f"{len(cookies)} Cookies geladen: {filepath}")
        
        return cookies
    
    # ═══════════════════════════════════════════════════════════════════════════
    # METHODE: inject_cookies
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def inject_cookies(
        self,
        context: BrowserContext,
        cookies: List[Dict[str, Any]]
    ) -> int:
        """
        Injiziert Cookies in einen Browser-Context.
        
        ABLAUF:
        1. Iteriere über alle Cookies.
        2. Für jedes Cookie:
           a. Versuche context.add_cookies([cookie]) aufzurufen.
           b. Wenn erfolgreich → count += 1.
           c. Wenn Fehler → logge Warning (Cookie wird übersprungen).
        3. Logge Ergebnis (count/len).
        4. Gib injected_count zurück.
        
        WARUM einzeln injizieren?
        → context.add_cookies() erwartet eine Liste von Cookies.
        → Wenn EIN Cookie ungültig ist → ALLE scheitern (atomic).
        → Wir injizieren einzeln → ein ungültiges Cookie blockiert nicht die anderen.
        → Trade-off: Langsamer (mehr API-Calls), aber robuster.
        
        WARUM try/except pro Cookie?
        → Manche Cookies können ungültig sein (z.B. Domain-Mismatch).
        → Wenn Domain nicht zur aktuellen Seite passt → Playwright wirft Fehler.
        → Wir fangen den ab und fahren mit dem nächsten Cookie fort.
        → Das ist robust: Ein fehlerhaftes Cookie killt nicht alle anderen.
        
        WARUM List[Dict] statt einzelne Dicts?
        → Playwright's add_cookies() erwartet eine Liste.
        → Wir rufen es mit [cookie] auf (einelementige Liste).
        → Das ermöglicht die Einzel-Injektion (siehe oben).
        
        WARUM injected_count zurückgeben?
        → Client kann prüfen: "Wurden alle Cookies injiziert?"
        → Wenn injected_count < len(cookies) → einige waren ungültig.
        → Nützlich für Debugging: Welche Cookies waren ungültig?
        
        Args:
            context: Playwright BrowserContext (wo Cookies injiziert werden).
            cookies: Liste von Cookie-Dictionaries (von load_cookies() oder extract_cookies()).
        
        Returns:
            int: Anzahl erfolgreich injizierter Cookies.
            Beispiel: 7 (von 8 Cookies, 1 war ungültig).
        
        Example:
            count = await manager.inject_cookies(context, cookies)
            # count = 7 (von 8 Cookies, 1 ungültig wegen Domain-Mismatch).
        """
        # Zähler für erfolgreich injizierte Cookies.
        count = 0
        
        # Iteriere über alle Cookies.
        for cookie in cookies:
            try:
                # Versuche Cookie zu injizieren.
                # context.add_cookies() erwartet eine Liste von Cookie-Dicts.
                # Wir übergeben eine einelementige Liste [cookie].
                await context.add_cookies([cookie])
                
                # Erfolg! Zähler erhöhen.
                count += 1
            
            except Exception as e:
                # Fehler beim Injizieren dieses Cookies.
                # Mögliche Ursachen:
                # - Domain-Mismatch: Cookie-Domain passt nicht zur aktuellen Seite.
                # - Ungültiges Format: Fehlende Felder (name, value, domain).
                # - Secure-Flag: Cookie hat secure=True aber Seite ist HTTP.
                logger.warning(
                    f"Cookie-Injektion fehlgeschlagen für {cookie.get('name')}: {e}"
                )
                # NICHT raise → fahre mit nächstem Cookie fort.
        
        # Logge Ergebnis.
        logger.info(f"{count}/{len(cookies)} Cookies injiziert")
        
        return count
    
    # ═══════════════════════════════════════════════════════════════════════════
    # METHODE: verify_session
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def verify_session(
        self,
        page: Page,
        expected_url: str = "heypiggy.com"
    ) -> bool:
        """
        Prüft ob eine HeyPiggy-Session aktiv ist.
        
        ABLAUF:
        1. Navigiere zum Dashboard (https://www.heypiggy.com/?page=dashboard).
           wait_until="domcontentloaded" = warte bis DOM bereit (schnell).
           timeout=15000 = max 15s (langsames Internet).
        2. Warte 3s (dynamischer Content laden: Surveys, Balance, etc.).
        3. Extrahiere aktuelle URL und Body-Text.
        4. Prüfe Login-Indikatoren:
           a. expected_url in current_url → Wir sind auf heypiggy.com.
           b. "abmelden" in body_text.lower() → "Abmelden"-Button sichtbar (eingeloggt).
           c. "dashboard" in current_url.lower() → Dashboard-Seite.
           d. "anmelden" NOT in body_text.lower() → Kein "Anmelden"-Button (nicht ausgeloggt).
        5. Logge Ergebnis.
        6. Gib True/False zurück.
        
        WARUM domcontentloaded statt networkidle?
        → domcontentloaded = DOM ist bereit (schneller, ~1-3s).
        → networkidle = alle Netzwerk-Requests fertig (langsamer, ~3-10s).
        → Für Session-Check brauchen wir nur den DOM (nicht alle Bilder/Ads).
        
        WARUM 3s Wartezeit?
        → HeyPiggy lädt dynamisch Content (Surveys, Balance, etc.).
        → Der "Abmelden"-Button erscheint erst nach JavaScript-Ausführung.
        → 3s ist ein Kompromiss: lang genug für dynamischen Content,
        → kurz genug für schnellen Check.
        
        WARUM "abmelden" statt "logout"?
        → HeyPiggy ist auf Deutsch.
        → Der Button heißt "Abmelden" (nicht "Logout").
        → .lower() macht den Check case-insensitive ("ABMELDEN", "abmelden").
        
        WARUM "anmelden" NOT in body_text?
        → Wenn "Anmelden" sichtbar → wir sind AUSGELOGGT (Login-Seite).
        → Wenn "Anmelden" NICHT sichtbar → wir sind eingeloggt.
        → Das ist ein Negativ-Check (wichtig für Robustheit).
        
        WARUM expected_url Parameter?
        → Flexibilität: Könnte auch für andere Websites verwendet werden.
        → Default "heypiggy.com" = HeyPiggy-spezifisch.
        
        Args:
            page: Playwright Page-Objekt (zum Navigieren und Prüfen).
            expected_url: URL-Substring der auf eine aktive Session hinweist.
                          Default: "heypiggy.com".
        
        Returns:
            bool: True wenn Session aktiv (eingeloggt), False sonst.
        
        Example:
            is_active = await manager.verify_session(page)
            # is_active = True → "Abmelden" sichtbar, auf heypiggy.com/dashboard.
            # is_active = False → "Anmelden" sichtbar, auf heypiggy.com/login.
        """
        try:
            # Navigiere zum Dashboard.
            # wait_until="domcontentloaded": Warte bis DOM bereit (schnell).
            # timeout=15000: Max 15s (langsames Internet oder Server-Probleme).
            await page.goto(
                f"https://www.{expected_url}/?page=dashboard",
                wait_until="domcontentloaded",
                timeout=15000
            )
            
            # Warte 3s für dynamischen Content.
            # WARUM page.wait_for_timeout()? Playwright-Methode für Sleep.
            # Nicht time.sleep() (blocking) sondern async (nicht-blocking).
            await page.wait_for_timeout(3000)
            
            # Extrahiere aktuelle URL.
            # page.url ist synchron (kein await nötig).
            current_url = page.url
            
            # Extrahiere Body-Text (sichtbarer Text der Seite).
            # page.inner_text("body") gibt den Text zurück (kein HTML).
            body_text = await page.inner_text("body")
            
            # Prüfe Login-Indikatoren.
            # ALLE Bedingungen müssen erfüllt sein (AND-Logik):
            # 1. Wir sind auf heypiggy.com (nicht auf Google-Login oder Fehler-Seite).
            # 2. "Abmelden" ist sichtbar (eingeloggt-Indikator).
            # 3. Wir sind auf der Dashboard-Seite.
            # 4. "Anmelden" ist NICHT sichtbar (nicht ausgeloggt).
            is_logged_in = (
                expected_url in current_url          # Auf heypiggy.com?
                and "abmelden" in body_text.lower()  # Abmelden-Button sichtbar?
                and "dashboard" in current_url.lower()  # Auf Dashboard?
                and "anmelden" not in body_text.lower()  # Nicht auf Login-Seite?
            )
            
            # Logge Ergebnis.
            if is_logged_in:
                logger.info(f"HeyPiggy Session aktiv: {current_url}")
            else:
                logger.warning(f"HeyPiggy Session nicht aktiv: {current_url}")
            
            return is_logged_in
        
        except Exception as e:
            # Fehler beim Verifizieren (z.B. Timeout, Netzwerk-Fehler).
            logger.error(f"Session-Prüfung fehlgeschlagen: {e}")
            return False
    
    # ═══════════════════════════════════════════════════════════════════════════
    # SESSION RECOVERY PROTOCOL (2026-05-08)
    # ═══════════════════════════════════════════════════════════════════════════
    # NIEMALS gute Cookies mit abgelaufenen ueberschreiben!
    # ═══════════════════════════════════════════════════════════════════════════
    
    BACKUP_DIR = os.path.expanduser("~/.stealth/heypiggy-backup")
    BACKUP_FILE = "heypiggy-cookies.json"
    
    async def safe_save_cookies(
        self,
        page: Page,
        cookies: List[Dict[str, Any]],
        filename: str = "heypiggy-cookies.json"
    ) -> Dict[str, Any]:
        """
        Safe Cookie Save mit Session-Validierung.
        
        NIEMALS speichern wenn Session abgelaufen ist!

        ABLAUF:
        1. Validiere Session via verify_session().
        2. Wenn Session AKTIV -> speichere Cookies normal.
        3. Wenn Session TOT -> speichere NICHT, logge Fehler,
           gib Recovery-Hinweis zurueck.
        
        Returns:
            Dict mit status, saved, message keys.
        """
        is_active = await self.verify_session(page)
        
        if not is_active:
            logger.critical(
                "SESSION TOT: Cookies NICHT gespeichert! "
                "Rufe POST /cookies/recover auf um Backup wiederherzustellen."
            )
            return {
                "status": "error",
                "saved": False,
                "message": (
                    "Cookie-Speicherung VERWEIGERT: Session ist abgelaufen. "
                    "Diese abgelaufenen Cookies wuerden die guten Backup-Daten "
                    "ueberschreiben. Rufe POST /cookies/recover auf."
                ),
            }
        
        filepath = self.save_cookies(cookies, filename)
        logger.info(f"SAFE SAVE: {len(cookies)} Cookies gespeichert, Session validated")
        return {
            "status": "success",
            "saved": True,
            "filepath": filepath,
            "count": len(cookies),
            "message": f"{len(cookies)} Cookies gespeichert, Session validiert",
        }
    
    @staticmethod
    def recover_from_backup(
        working_filename: str = "heypiggy-cookies.json",
        working_dir: str = "data"
    ) -> Dict[str, Any]:
        """
        Session Recovery: Stellt saubere Backup-Cookies wieder her.
        
        NIEMALS die Backup-Datei schreiben (read-only)!
        NUR lesen und in Working-Dir kopieren.
        
        ABLAUF:
        1. Pruefe ob Backup existiert.
        2. Wenn Backup fehlt -> Error (manuelles Login noetig).
        3. Loesche/ueberschreibe die kaputte Working-Datei.
        4. Kopiere Backup -> Working-Dir.
        5. Setze Working-Datei auf schreibbar.
        
        Returns:
            Dict mit status, recovered, message keys.
        """
        backup_path = os.path.join(CookieManager.BACKUP_DIR, CookieManager.BACKUP_FILE)
        working_path = os.path.join(working_dir, working_filename)
        
        if not os.path.exists(backup_path):
            return {
                "status": "error",
                "recovered": False,
                "message": (
                    f"KEIN Backup gefunden: {backup_path}. "
                    "Manuelles Login erforderlich. "
                    "Nach Login: POST /cookies/extract -> POST /cookies/backup"
                ),
            }
        
        try:
            import shutil
            os.makedirs(working_dir, exist_ok=True)
            shutil.copy2(backup_path, working_path)
            os.chmod(working_path, 0o644)
            
            with open(backup_path) as f:
                data = json.load(f)
            cookie_count = data.get("metadata", {}).get("count", 0)
            
            logger.info(f"RECOVERY: {cookie_count} Cookies aus Backup wiederhergestellt")
            return {
                "status": "success",
                "recovered": True,
                "count": cookie_count,
                "backup_source": backup_path,
                "restored_to": working_path,
                "message": (
                    f"{cookie_count} Cookies aus Backup wiederhergestellt. "
                    "Starte Browser neu mit POST /browser/start oder POST /services/heypiggy/login"
                ),
            }
        except Exception as e:
            logger.error(f"Recovery fehlgeschlagen: {e}")
            return {
                "status": "error",
                "recovered": False,
                "message": f"Recovery fehlgeschlagen: {e}",
            }
    
    @staticmethod
    def create_backup(
        working_filename: str = "heypiggy-cookies.json",
        working_dir: str = "data"
    ) -> Dict[str, Any]:
        """
        Erstellt Backup aus aktuellen Working-Cookies.
        
        VORAUSSETZUNG: Session MUSS validiert sein (safe_save wurde aufgerufen).
        Backup wird READ-ONLY gespeichert (Agent darf NIE reinschreiben).
        
        Returns:
            Dict mit status, backed_up, message keys.
        """
        working_path = os.path.join(working_dir, working_filename)
        
        if not os.path.exists(working_path):
            return {
                "status": "error",
                "backed_up": False,
                "message": f"Keine Working-Cookies gefunden: {working_path}",
            }
        
        try:
            import shutil
            os.makedirs(CookieManager.BACKUP_DIR, exist_ok=True)
            
            with open(working_path) as f:
                data = json.load(f)
            
            backup_path = os.path.join(CookieManager.BACKUP_DIR, CookieManager.BACKUP_FILE)
            shutil.copy2(working_path, backup_path)
            
            os.chmod(backup_path, 0o444)
            os.chmod(CookieManager.BACKUP_DIR, 0o555)
            
            cookie_count = data.get("metadata", {}).get("count", 0)
            logger.info(f"BACKUP: {cookie_count} Cookies gesichert (read-only): {backup_path}")
            
            return {
                "status": "success",
                "backed_up": True,
                "count": cookie_count,
                "backup_path": backup_path,
                "message": f"{cookie_count} Cookies als Backup gesichert (read-only)",
            }
        except Exception as e:
            return {
                "status": "error",
                "backed_up": False,
                "message": f"Backup fehlgeschlagen: {e}",
            }
    
    # ═══════════════════════════════════════════════════════════════════════════
    # METHODE: get_cookie_stats
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_cookie_stats(
        self,
        cookies: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generiert Statistik über Cookies.
        
        ABLAUF:
        1. Zähle Cookies pro Domain (domains Dict).
        2. Zähle httpOnly-Cookies (nicht via JS zugänglich = sicherer).
        3. Zähle secure-Cookies (nur über HTTPS = sicherer).
        4. Zähle Session-Cookies (expires=-1 = kein Ablaufdatum).
        5. Gib Statistik-Dict zurück.
        
        WARUM Statistiken?
        → Schnelle Übersicht ohne alle Cookies zu parsen.
        → "7 Cookies, 2 httpOnly, 5 secure" → Session sieht gut aus.
        → "0 Cookies" → Session ist leer (nicht eingeloggt).
        → "0 httpOnly" → Sicherheits-Bedenken (alle Cookies via JS zugänglich).
        
        WARUM httpOnly wichtig?
        → httpOnly-Cookies können NICHT via JavaScript gelesen werden.
        → Schutz gegen XSS-Angriffe (Cross-Site Scripting).
        → Session-Cookies (PHPSESSID) SOLLTEN httpOnly sein.
        
        WARUM secure wichtig?
        → Secure-Cookies werden NUR über HTTPS gesendet.
        → Schutz gegen Man-in-the-Middle-Angriffe (HTTP-Sniffing).
        → In modernen Websites SOLLTEN alle Cookies secure sein.
        
        WARUM session_cookies?
        → Session-Cookies (expires=-1) haben kein Ablaufdatum.
        → Sie werden beim Schließen des Browsers gelöscht.
        → Aber: Chrome speichert sie im Profil (wenn "Continue where left off" aktiv).
        → Für Persistenz: Session-Cookies sind WICHTIG (Login-Status).
        → Wenn 0 session_cookies → alle Cookies haben Ablaufdatum (evtl. abgelaufen).
        
        Args:
            cookies: Liste von Cookie-Dictionaries (von extract_cookies() oder load_cookies()).
        
        Returns:
            Dict mit Statistiken:
            {
                "total": 7,              # Gesamtanzahl
                "domains": {            # Cookies pro Domain
                    ".heypiggy.com": 5,
                    "heypiggy.com": 2
                },
                "http_only": 2,         # httpOnly-Cookies
                "secure": 5,            # secure-Cookies
                "session_cookies": 3     # Session-Cookies (expires=-1)
            }
        
        Example:
            stats = manager.get_cookie_stats(cookies)
            # stats = {"total": 7, "domains": {...}, "http_only": 2, "secure": 5, "session_cookies": 3}
        """
        # Zähle Cookies pro Domain.
        # WARUM Dict? Domain → Anzahl (einfache Struktur).
        domains = {}
        for c in cookies:
            # c.get("domain", "unknown") → Domain oder "unknown" wenn nicht vorhanden.
            domain = c.get("domain", "unknown")
            # domains[domain] = domains.get(domain, 0) + 1 → Zähler erhöhen.
            domains[domain] = domains.get(domain, 0) + 1
        
        # Erstelle Statistik-Dict.
        return {
            # Gesamtanzahl der Cookies.
            "total": len(cookies),
            
            # Cookies pro Domain.
            "domains": domains,
            
            # Anzahl httpOnly-Cookies.
            # WARUM sum() mit Generator? Effizient (keine Zwischenliste).
            # c.get("httpOnly", False) → True wenn httpOnly, sonst False.
            # sum(True, False, True) → 2 (True=1, False=0).
            "http_only": sum(1 for c in cookies if c.get("httpOnly")),
            
            # Anzahl secure-Cookies.
            "secure": sum(1 for c in cookies if c.get("secure")),
            
            # Anzahl Session-Cookies (expires=-1).
            # WARUM -1? Playwright verwendet -1 für Session-Cookies (kein Ablaufdatum).
            "session_cookies": sum(1 for c in cookies if c.get("expires", -1) == -1),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON-INSTANZ und GETTER
# ═══════════════════════════════════════════════════════════════════════════════
# Diese Funktionen stellen sicher dass es nur EINE CookieManager-Instanz gibt.
# ═══════════════════════════════════════════════════════════════════════════════

# Globale Variable für die Singleton-Instanz.
# WARUM None? Beim ersten Aufruf wird die Instanz erstellt.
# WARUM global? Muss von get_cookie_manager() zugänglich sein.
_cookie_manager: Optional[CookieManager] = None


def get_cookie_manager() -> CookieManager:
    """
    Liefert die Singleton-Instanz des CookieManagers.
    
    WARUM Singleton?
    → Einheitlicher Zugriff auf Cookie-Dateien (keine Race Conditions).
    → Zentrale Konfiguration (cookies_dir = "./data").
    → Wiederverwendung: Instanz wird gecacht.
    
    WARUM Default-Instanz?
    → Bei Erstaufruf: CookieManager(cookies_dir="./data").
    → Standard-Verzeichnis für alle Cookie-Operationen.
    → Client kann spezifische Instanz erstellen wenn nötig.
    
    Returns:
        CookieManager: Die Singleton-Instanz (cookies_dir="./data").
    
    Example:
        cm = get_cookie_manager()
        # cm ist IMMER dieselbe Instanz.
    """
    # Zugriff auf globale Variable.
    global _cookie_manager
    
    # Wenn Instanz noch nicht existiert → erstelle sie.
    if _cookie_manager is None:
        _cookie_manager = CookieManager()
    
    return _cookie_manager


# ═══════════════════════════════════════════════════════════════════════════════
# ENDE VON COOKIE_MANAGER.PY
# ═══════════════════════════════════════════════════════════════════════════════
# ZUSAMMENFASSUNG:
#
# Diese Datei implementiert den CookieManager für Session-Persistenz:
#   - extract_cookies(): Cookies aus Browser holen (domain_filter unterstützt).
#   - save_cookies(): Cookies als JSON speichern (mit Metadaten).
#   - load_cookies(): Cookies aus JSON laden (mit Fehlerbehandlung).
#   - inject_cookies(): Cookies in Browser injizieren (robust: einzeln, mit Fallback).
#   - verify_session(): Prüfen ob Session noch aktiv ist (Dashboard-Check).
#   - get_cookie_stats(): Statistiken für Monitoring (httpOnly, secure, session).
#
# DESIGN-PRINZIPIEN:
#   1. Singleton: Eine Instanz pro Prozess (keine Race Conditions).
#   2. Fail-Safe: Einzelne Cookie-Injektion (ein Fehler killt nicht alle).
#   3. Idempotent: save_cookies() überschreibt (kein Append).
#   4. Self-Documenting: JSON-Format ist human-readable.
#   5. Security: Keine Passwörter, nur Session-Cookies.
#
# HEYPIGGY WORKFLOW:
#   1. Einmalig: Manuell einloggen.
#   2. POST /cookies/extract → Cookies speichern.
#   3. Bei jedem Start: POST /cookies/inject → Session aktivieren.
#   4. POST /cookies/verify → Prüfen ob Session noch gültig.
#   5. Wenn abgelaufen: Neu einloggen (Schritt 1 wiederholen).
# ═══════════════════════════════════════════════════════════════════════════════
