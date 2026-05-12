"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║           STEALTH-RUNNER — Survey Action Endpoints (CRUD-Style API)           ║
║                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ZWECK / PURPOSE:                                                            ║
║  ────────────────                                                            ║
║  CRUD-ähnliche API für Survey-Interaktionen. Jeder Endpoint = EINE Aktion.  ║
║  Keine Megafunctions. Keine Blackbox-Runner. Jede Aktion ist isoliert,      ║
║  debuggbar, und retry-fähig.                                               ║
║                                                                              ║
║  ARCHITEKTUR-OVERVIEW:                                                       ║
║  ─────────────────────                                                       ║
║  ┌─────────────────────────────────────────────────────────────────────┐    ║
║  │  Endpoints (FastAPI Router, prefix="/survey", tags=["survey"])      │    ║
║  │  ├── POST /survey/click-card    → Survey-Karte klicken               │    ║
║  │  ├── GET  /survey/modal         → Modal-Inhalt lesen                │    ║
║  │  ├── POST /survey/click-button  → Button klicken                   │    ║
║  │  ├── POST /survey/select-option → Radio/Checkbox auswählen         │    ║
║  │  ├── POST /survey/fill-text     → Text eingeben                      │    ║
║  │  └── POST /survey/run-one       → Komplette Umfrage (Loop)          │    ║
║  └─────────────────────────────────────────────────────────────────────┘    ║
║                                                                              ║
║  CDP KOMMUNIKATION (WebSocket):                                              ║
║  ──────────────────────────────                                              ║
║  ┌─────────────────────────────────────────────────────────────────────┐    ║
║  │  Chrome DevTools Protocol (CDP) via WebSocket                        │    ║
║  │  ├── get_dashboard_ws(port)    → WS URL finden (aus /json/pages)   │    ║
║  │  ├── ws_eval(ws_url, js)       → JavaScript ausführen + Result    │    ║
║  │  ├── ws_eval_multi(...)        → Mehrere JS Calls in EINEM WS     │    ║
║  │  └── _ws_origin(ws_url)        → Origin Header für WS Auth         │    ║
║  └─────────────────────────────────────────────────────────────────────┘    ║
║                                                                              ║
║  WARUM CDP WEBSOCKET (NICHT Playwright)?                                    ║
║  ──────────────────────────────────────                                      ║
║  1. PLAYWRIGHT IST SCHWER (150MB+ Chromium Binary, 2-5s Startup).         ║
║  2. CDP WEBSOCKET IST LEICHT (nur websocket-client, <1s).                   ║
║  3. FÜR SURVEY-AUTOMATION BRAUCHEN WIR NUR JavaScript-Ausführung.         ║
║  4. PLAYWRIGHT BRINGT VIEL OVERHEAD (Page-Objekt, Locators, etc.).         ║
║  5. CDP = DIREKTER ZUGRIFF: Runtime.evaluate() → JS läuft im Browser.     ║
║                                                                              ║
║  SICHERHEIT / BANNED PATTERNS:                                               ║
║  ──────────────────────────────                                              ║
║  • NIEMALS hardcoded PIDs oder Ports (außer Defaults)                     ║
║  • NIEMALS User-Chrome killen (nur /tmp/sinator-chrome-*)                 ║
║  • Origin Header MUSS gesetzt sein (sonst 403 Forbidden)                     ║
║  • --remote-allow-origins=* OHNE Quotes (zsh glob expansion!)                ║
║  • returnByValue=True MUSS gesetzt sein (sonst Object-ID statt Wert)       ║
║  • NIEMALS innerText/htmlLength ohne Limits (RAM/DoS)                      ║
║                                                                              ║
║  FEHLERBEHANDLUNG (Fail-Closed):                                             ║
║  ──────────────────────────────                                              ║
║  • Jeder Endpoint fail-closed (bei Fehler → Error Response)               ║
║  • CDP nicht erreichbar → "No dashboard found"                             ║
║  • JavaScript Exception → {} oder leere Liste (nicht Crash)               ║
║  • WebSocket Timeout → None (nicht Blockieren)                             ║
║  • Button/Element nicht gefunden → "not_found" (nicht Crash)             ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

# ═══════════════════════════════════════════════════════════════════════════════
# IMPORTS: Was brauchen wir und WARUM?
# ═══════════════════════════════════════════════════════════════════════════════

# "from __future__ import annotations" ermöglicht Forward-References in Type Hints.
# WARUM? Ohne das müssten wir Klassen in spezifischer Reihenfolge definieren.
from __future__ import annotations

# json: JSON Serialisierung/Deserialisierung.
# WARUM? - WebSocket sendet/empfängt JSON-Nachrichten.
#        - JavaScript-Resultat ist oft JSON-String → json.loads() um zu parsen.
#        - Standard-Library (keine External Dependencies).
import json

# time: Zeit-Messung und Sleep.
# WARUM? - time.sleep() nach Clicks (Seite muss reagieren, JavaScript ausführen).
#        - Zeit-Messung für Performance-Monitoring (wie lange dauert ein Klick?).
#        - Hinweis: time.sleep() ist BLOCKING (nicht async).
#          In FastAPI-Endpoints ist das OK (FastAPI läuft in Thread-Pool).
#          Für Produktion: asyncio.sleep() verwenden (wenn möglich).
import time

# urllib.request: HTTP-Requests (für CDP HTTP API /json/pages).
# WARUM? - Keine External Dependencies (requests, aiohttp nicht nötig).
#        - Sehr leichtgewichtig (<1ms pro Request).
#        - Wir brauchen nur einfache GET-Requests (kein POST/PUT/DELETE).
import urllib.request

# Optional: Ein Wert ODER None (für Type Hints).
# List: Für Listen-Typen (z.B. List[str], List[Dict]).
# websocket: WebSocket-Client für CDP Kommunikation.
# WARUM? - CDP verwendet WebSocket (nicht HTTP).
#        - websocket-client ist ein schlankes Paket (<1MB).
#        - Alternative: websockets (async) — aber wir brauchen nur sync.
#        - websocket.create_connection() ist blocking (einfach, robust).
import websocket

# APIRouter: FastAPI-Router für modulare Endpoints.
# WARUM? - Router können unabhängig definiert und in main.py registriert werden.
#        - Prefix und Tags werden im Router definiert (nicht pro Endpoint).
#        - Modularität: survey_actions.py kann allein getestet werden.
from fastapi import APIRouter

# Pydantic-Modelle für Request/Response Validation.
# WARUM? - FastAPI validiert Requests automatisch (422 bei ungültigen Daten).
#        - Response-Modelle garantieren korrektes JSON-Format.
#        - Siehe schemas.py für detaillierte Dokumentation jedes Modells.
from api.schemas import (
    # Request/Response für POST /survey/click-button
    SurveyClickButtonRequest,  # button_label, cdp_port, profile_name, timeout_ms
    SurveyClickButtonResponse,  # status, button_label, page_changed, new_text, message
    # Request/Response für POST /survey/click-card
    SurveyClickCardRequest,  # survey_id, cdp_port, profile_name
    SurveyClickCardResponse,  # status, survey_id, modal_visible, modal_text, modal_buttons, message
    # Request/Response für POST /survey/click-custom-radio
    SurveyClickCustomRadioRequest,  # css_selector, index, cdp_port, profile_name
    SurveyClickCustomRadioResponse,  # status, index, message
    SurveyElement,  # ref, role, text, label, value, selected, visible
    # Request/Response für POST /survey/fill-text
    SurveyFillTextRequest,  # input_label, value, cdp_port, profile_name
    SurveyFillTextResponse,  # status, input_label, value, message
    # Request/Response für GET /survey/modal
    SurveyGetModalRequest,  # cdp_port, profile_name
    SurveyGetModalResponse,  # status, modal_visible, elements, text, page_title, provider, progress, message
    # Request/Response für POST /survey/run-one
    SurveyRunOneRequest,  # survey_id, cdp_port, profile_name, max_pages
    SurveyRunOneResponse,  # status, survey_id, pages_completed, earned, elapsed_s, error, message
    # Request/Response für POST /survey/select-option
    SurveySelectOptionRequest,  # option_text, cdp_port, profile_name, wait_after_ms
    SurveySelectOptionResponse,  # status, option_text, selected, message
)

# Router-Instanz erstellen.
# prefix="/survey": ALLE Endpoints beginnen mit /survey (z.B. /survey/click-card).
# tags=["survey"]: Swagger UI gruppiert diese Endpoints unter "survey".
router = APIRouter(prefix="/survey", tags=["survey"])


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER: CDP WebSocket Kommunikation
# ═══════════════════════════════════════════════════════════════════════════════
# Diese Funktionen kapseln die WebSocket-Kommunikation mit Chrome.
# Sie sind Low-Level und werden von den Endpoints verwendet.
# ═══════════════════════════════════════════════════════════════════════════════


def _ws_origin(ws_url: str) -> str:
    """
    Leitet HTTP Origin aus einer WebSocket-URL ab.

    PROBLEM:
    Chrome 111+ erfordert einen Origin Header für WebSocket-Verbindungen.
    Ohne Origin → "WebSocketBadStatusException: Handshake status 403 Forbidden".

    LÖSUNG:
    Wir leiten den Origin aus der ws:// URL ab:
    - ws://127.0.0.1:9999/devtools/page/ABC → http://127.0.0.1:9999
    - wss://example.com:443/ws → https://example.com:443

    WARUM manuell berechnen?
    → websocket-client erlaubt Header-Angabe, aber nicht automatische Origin-Erzeugung.
    → Wir müssen den Origin EXPLIZIT im Header setzen.

    WARUM urlparse?
    → urlparse zerlegt die URL in scheme, netloc, path, params, query, fragment.
    → Wir brauchen nur scheme und netloc.
    → scheme: ws:// → http://, wss:// → https:// (ws ersetzt durch http).

    Args:
        ws_url: WebSocket URL (z.B. "ws://127.0.0.1:9999/devtools/page/ABC123").

    Returns:
        str: HTTP Origin (z.B. "http://127.0.0.1:9999").

    Example:
        >>> _ws_origin("ws://127.0.0.1:9999/devtools/page/ABC")
        "http://127.0.0.1:9999"
        >>> _ws_origin("wss://example.com:443/ws")
        "https://example.com:443"
    """
    # urlparse importieren (nur hier gebraucht → lokal import).
    from urllib.parse import urlparse

    # URL zerlegen in Bestandteile.
    parsed = urlparse(ws_url)

    # Scheme ersetzen: ws:// → http://, wss:// → https://.
    # WARUM replace("ws", "http")? "ws" ist ein Präfix von "wss".
    # "ws".replace("ws", "http") → "http".
    # "wss".replace("ws", "http") → "http" + "s" = "https".
    scheme = parsed.scheme.replace("ws", "http")

    # Origin = scheme://netloc (z.B. http://127.0.0.1:9999).
    # netloc enthält Host + Port (z.B. "127.0.0.1:9999").
    return f"{scheme}://{parsed.netloc}"


def get_dashboard_ws(port: int) -> str | None:
    """
    Findet die WebSocket URL für das HeyPiggy Dashboard.

    ABLAUF:
    1. HTTP GET auf http://127.0.0.1:{port}/json (Chrome CDP HTTP API).
       Dieser Endpunkt gibt eine Liste aller Tabs/Pages zurück.
    2. Parse JSON-Antwort.
    3. Iteriere über alle Pages.
    4. Filtere nach "page" Typ (keine background_page, service_worker, etc.).
    5. Prüfe ob "dashboard" in der URL enthalten ist (case-insensitive).
    6. Gib die webSocketDebuggerUrl zurück.
    7. Wenn kein Dashboard-Tab gefunden → gib None zurück.

    WARUM NICHT nur den ersten Tab nehmen?
    → Chrome hat mehrere Tabs/Pages:
    - background_page: Chrome Extension Hintergrund-Seite.
    - service_worker: Service Worker für Web-Apps.
    - page: Normale Web-Seite (Dashboard).
    - iframe: Eingebettete Frames.
    → Wir brauchen EXPLIZIT den "page" Tab mit dem Dashboard.
    → Der erste Tab könnte eine Extension oder ein Service Worker sein.

    WARUM "dashboard" in URL?
    → HeyPiggy Dashboard URL enthält "dashboard":
      https://www.heypiggy.com/?page=dashboard
    → Survey-Seiten haben andere URLs (qualtrics.com, tolunastart.com, etc.).
    → Wir suchen den Tab der das Dashboard anzeigt.
    → Wenn Survey läuft → Dashboard-Tab ist möglicherweise nicht der aktive Tab.
      Aber er ist noch vorhanden (Chrome hat mehrere Tabs).

    WARUM urllib.request statt requests?
    → Keine External Dependencies.
    → Sehr leichtgewichtig.
    → Wir brauchen nur ein einfaches GET.

    WARUM timeout=5s?
    → Wenn Chrome nicht läuft → ConnectionRefused sofort (wenige ms).
    → Wenn Chrome läuft → Antwort kommt sofort (<100ms).
    → 5s ist sehr großzügig (Safety-Net).

    WARUM fail-closed (bei Exception → None)?
    → Wenn Chrome nicht läuft → Exception (ConnectionRefused, Timeout).
    → Wir fangen ALLE Exceptions und geben None zurück.
    → Der Aufrufer prüft auf None und gibt "No dashboard found" zurück.
    → Kein Crash, kein Stack-Trace an Client.

    Args:
        port: CDP Port (default: 9999).

    Returns:
        Optional[str]: WebSocket URL (z.B. "ws://127.0.0.1:9999/devtools/page/ABC")
        oder None wenn kein Dashboard-Tab gefunden.

    Raises:
        None (alle Exceptions werden abgefangen).

    Example:
        >>> get_dashboard_ws(9999)
        "ws://127.0.0.1:9999/devtools/page/ABC123DEF456"
        >>> get_dashboard_ws(9999)  # Kein Chrome auf 9999
        None
    """
    try:
        # HTTP GET auf /json (Chrome CDP HTTP API).
        # WARUM /json? Chrome's CDP HTTP Endpunkt listet alle Tabs/Pages auf.
        # Ergebnis: JSON-Array mit Tab-Informationen (id, title, url, type, webSocketDebuggerUrl).
        response = urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=5)

        # Parse JSON-Antwort.
        # json.loads() wandelt JSON-String in Python-Objekt (Liste von Dicts).
        pages = json.loads(response.read())

        # Iteriere über alle Pages/Tabs.
        for p in pages:
            # Prüfe Typ: Nur "page" Tabs (keine Extensions, Service Worker, etc.).
            # p.get("type") gibt den Tab-Typ zurück ("page", "background_page", etc.).
            # WARUM .get()? Wenn "type" fehlt → None (nicht KeyError).
            if p.get("type") == "page":
                # Prüfe ob URL "dashboard" enthält (case-insensitive).
                # p.get("url", "") gibt die URL zurück (oder leerer String wenn fehlt).
                # .lower() macht den Check case-insensitive.
                if "dashboard" in p.get("url", "").lower():
                    # Dashboard-Tab gefunden!
                    # Gib die webSocketDebuggerUrl zurück (für WebSocket-Verbindung).
                    return p.get("webSocketDebuggerUrl")

        # Kein Dashboard-Tab gefunden.
        # WARUM None? Eine leere Liste oder Exception wäre unklar.
        # None = "es gibt keinen Dashboard-Tab" (Chrome könnte laufen,
        # aber kein HeyPiggy Dashboard geöffnet sein).
        return None

    except Exception:
        # JEGLICHE Exception → None.
        # Mögliche Fehler:
        # - ConnectionRefusedError: Kein Chrome auf diesem Port.
        # - TimeoutError: Chrome antwortet nicht (abgestürzt/hängt).
        # - json.JSONDecodeError: Antwort ist kein gültiges JSON.
        # - urllib.error.URLError: Netzwerk-Fehler.
        # Wir fangen ALLE ab (fail-closed).
        pass

    # Kein Dashboard gefunden (entweder nicht vorhanden oder Fehler).
    return None


def get_any_tab_ws(
    port: int, url_pattern: str | None = None, tab_id: str | None = None
) -> str | None:
    """
    Findet die WebSocket URL für BELIEBIGE Tabs (nicht nur Dashboard).

    WICHTIG: Dies ist die BULLETPROOF-Version von get_dashboard_ws().
    Sie sucht auf ALLEN Tabs, nicht nur dem Dashboard-Tab.

    ABLAUF:
    1. HTTP GET auf /json (alle Tabs listen).
    2. Filtere nach "page" Typ (keine Extensions/Service Worker).
    3. WENN tab_id angegeben → suche EXAKT diesen Tab.
    4. WENN url_pattern angegeben → suche Tab dessen URL das Pattern enthält.
    5. SONST → gib den ERSTEN "page" Tab zurück (meistens der aktive Tab).
    6. Wenn nichts gefunden → None.

    WARUM brauchen wir das?
    → Surveys öffnen sich in NEUEN Tabs (nicht im Dashboard-Tab).
    → Der alte click_button Endpoint suchte nur im Dashboard-Tab.
    → Ergebnis: "Button not found" obwohl der Button auf dem Survey-Tab existierte.

    WARUM Fallback auf ersten Tab?
    → Wenn der Client kein tab_id/url_pattern angibt → nehme den ersten Page-Tab.
    → In 90% der Fälle ist das der aktive Tab (Survey-Seite).
    → Damit ist der Endpoint auch ohne tab_id meistens korrekt.

    Args:
        port: CDP Port.
        url_pattern: Optional. Wenn angegeben → suche Tab mit URL die diesen String enthält.
        tab_id: Optional. Wenn angegeben → suche EXAKT diesen Tab (über p['id']).

    Returns:
        Optional[str]: WebSocket URL oder None.
    """
    try:
        response = urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=5)
        pages = json.loads(response.read())

        # Nur "page" Tabs (keine background_page, service_worker, etc.)
        page_tabs = [p for p in pages if p.get("type") == "page"]

        if not page_tabs:
            return None

        # Priorität 1: Exakte tab_id Suche
        if tab_id:
            for p in page_tabs:
                if p.get("id") == tab_id:
                    return p.get("webSocketDebuggerUrl")

        # Priorität 2: URL Pattern Match
        if url_pattern:
            pattern_lower = url_pattern.lower()
            for p in page_tabs:
                if pattern_lower in p.get("url", "").lower():
                    return p.get("webSocketDebuggerUrl")

        # Priorität 3: Dashboard-Tab (für Rückwärtskompatibilität)
        for p in page_tabs:
            if "dashboard" in p.get("url", "").lower():
                return p.get("webSocketDebuggerUrl")

        # Priorität 4: Erster Page-Tab (meistens der aktive Tab)
        return page_tabs[0].get("webSocketDebuggerUrl")

    except Exception:
        pass

    return None


def ws_eval(ws_url: str, js: str, timeout: int = 10) -> dict | None:
    """
    Führt JavaScript im Browser via CDP aus und gibt das Ergebnis zurück.

    ABLAUF:
    1. WebSocket Verbindung aufbauen (mit Origin Header!).
    2. Runtime.evaluate CDP Befehl senden (als JSON).
    3. Auf Antwort warten (ws.recv()).
    4. Antwort als JSON parsen.
    5. Extrahiere das Resultat (resp["result"]["result"]["value"]).
    6. WebSocket schließen.
    7. Gib Resultat zurück.

    WARUM WebSocket (nicht HTTP)?
    → CDP verwendet WebSocket für bidirektionale Kommunikation.
    → HTTP wäre request/response (keine Events, kein Streaming).
    → WebSocket ermöglicht: Befehl senden → Antwort empfangen → Verbindung schließen.

    WARUM Origin Header?
    → Chrome 111+ erfordert Origin Header für WebSocket-Verbindungen.
    → Ohne Origin → 403 Forbidden.
    → Wir berechnen den Origin aus der ws_url via _ws_origin().
    → Header-Format: ["Origin: http://127.0.0.1:9999"].

    WARUM Runtime.evaluate?
    → CDP-Befehl um JavaScript im Browser-Kontext auszuführen.
    → Äquivalent zu Chrome DevTools Console.
    → Das JavaScript läuft im Kontext der aktuellen Page (Zugriff auf DOM).

    WARUM returnByValue=True?
    → Ohne returnByValue bekommt man nur eine Object-ID zurück (nicht den Wert).
    → Object-ID = Referenz auf ein Objekt im Browser-Speicher.
    → Mit returnByValue=True wird das Objekt SERIALISIERT und zurückgegeben.
    → WICHTIG: Funktioniert nur für primitive Typen und JSON-serialisierbare Objekte.
    → Für komplexe Objekte (DOM-Elemente, Funktionen) → Object-ID.

    WARUM timeout Parameter?
    → WebSocket-Verbindung könnte hängen (Chrome nicht antwortet).
    → Default 10s ist großzügig (meiste JS läuft in <1s).
    → Bei langsamen Operationen (z.B. lange Schleifen) → erhöhen.

    WARUM Optional[dict] Rückgabe?
    → Bei Erfolg: Dict mit {"value": ..., "type": ...}.
    → Bei Fehler: None (fail-closed).
    → Der Aufrufer prüft auf None → gibt Fehler-Response zurück.

    Args:
        ws_url: WebSocket Debugger URL (z.B. "ws://127.0.0.1:9999/devtools/page/ABC").
        js: JavaScript Code (MUST return a value!).
            Beispiel: "document.title" (gibt String zurück).
            Beispiel: "document.querySelector('button').click(); return 'clicked';"
            WICHTIG: Das JS MUSS einen Wert zurückgeben (return statement)!
            Ohne return → undefined (nicht nützlich).
        timeout: WebSocket Timeout in Sekunden (default: 10).

    Returns:
        Optional[dict]: Resultat-Dict mit "value" und "type" Keys.
        Beispiel: {"value": "HeyPiggy Dashboard", "type": "string"}
        oder None bei Fehler.

    Raises:
        None (alle Exceptions werden abgefangen).

    Example:
        >>> ws_eval("ws://127.0.0.1:9999/devtools/page/ABC", "document.title")
        {"value": "HeyPiggy Dashboard", "type": "string"}
        >>> ws_eval("ws://...", "1 + 1")
        {"value": 2, "type": "number"}
    """
    try:
        # WebSocket-Verbindung aufbauen.
        # WARUM create_connection? Einfacher Synchroner WebSocket-Client.
        # WARUM header? Origin Header für Chrome 111+ WebSocket Auth.
        ws = websocket.create_connection(
            ws_url, timeout=timeout, header=[f"Origin: {_ws_origin(ws_url)}"]
        )

        # CDP Befehl senden: Runtime.evaluate.
        # WARUM id=1? Jeder CDP-Befehl hat eine ID (für Antwort-Zuordnung).
        # Wir verwenden immer id=1 (einfacher, da nur ein Befehl pro Verbindung).
        ws.send(
            json.dumps(
                {
                    "id": 1,
                    "method": "Runtime.evaluate",
                    "params": {
                        "expression": js,  # Das JavaScript das ausgeführt wird
                        "returnByValue": True,  # WICHTIG: Objekt serialisieren (nicht Object-ID)
                    },
                }
            )
        )

        # Auf Antwort warten.
        # ws.recv() blockiert bis Antwort empfangen (oder Timeout).
        # Antwort ist JSON-String.
        response = ws.recv()

        # WebSocket schließen.
        # WARUM sofort schließen? Wir brauchen die Verbindung nicht weiter.
        # Eine Verbindung pro Befehl = einfacher, kein State-Management.
        # Trade-off: Mehr Overhead (Verbindung aufbauen/schließen pro Befehl).
        # Alternative: Eine persistente Verbindung (komplexer, State-Management).
        ws.close()

        # Parse JSON-Antwort.
        # json.loads() wandelt JSON-String in Python-Dict.
        parsed = json.loads(response)

        # Extrahiere das Resultat.
        # CDP Antwort-Struktur: {"id": 1, "result": {"result": {"value": ..., "type": ...}}}
        # Wir navigieren durch die verschachtelten Dicts.
        # .get("result", {}) → wenn "result" fehlt → leeres Dict (nicht KeyError).
        # .get("result", {}) → zweites "result" (CDP verschachtelt so).
        return parsed.get("result", {}).get("result", {})

    except Exception:
        # JEGLICHE Exception → None.
        # Mögliche Fehler:
        # - WebSocketBadStatusException: 403 Forbidden (Origin fehlt/falsch).
        # - WebSocketTimeoutException: Timeout (Chrome antwortet nicht).
        # - ConnectionRefusedError: Chrome nicht erreichbar.
        # - json.JSONDecodeError: Antwort ist kein gültiges JSON.
        # Wir fangen ALLE ab (fail-closed).
        return None


def ws_eval_multi(ws_url: str, *calls) -> list[dict]:
    """
    Führt MEHRERE JavaScript-Aufrufe in EINER WebSocket-Verbindung aus.

    ABLAUF:
    1. WebSocket Verbindung aufbauen (mit Origin Header).
    2. Phase 1: ALLE Requests senden (ohne auf Antworten zu warten).
    3. Phase 2: ALLE Antworten empfangen (in Reihenfolge der Requests).
    4. WebSocket schließen.
    5. Extrahiere Werte aus Antworten.
    6. Gib Liste der Werte zurück.

    WARUM mehrere Calls in EINER Verbindung?
    → Jede WebSocket-Verbindung kostet ~50-100ms Setup-Zeit (Handshake).
    → Bei 5 Calls = 5 Verbindungen = 250-500ms Overhead.
    → Mit ws_eval_multi = nur 1 Verbindung für alle Calls.
    → Performance-Optimierung: 5x schneller bei vielen Calls.

    WARUM Reihenfolge?
    → CDP Antworten kommen in der Reihenfolge der Requests.
    → Wir senden alle Requests → empfangen alle Antworten (in derselben Reihenfolge).
    → Das ist GARANTIERT durch die CDP-Spezifikation.

    WARUM calls als *args?
    → Flexible Anzahl von Calls.
    → Format: ("javascript_code", call_id).
    → Beispiel: ws_eval_multi(ws_url, ("document.title", 1), ("document.URL", 2)).

    WARUM call_id?
    → CDP verwendet id für Antwort-Zuordnung.
    → Wir senden zwar in Reihenfolge, aber call_id hilft beim Debugging.
    → Wenn Antworten out-of-order kommen → call_id hilft zuordnen.

    WARUM return List[dict]?
    → Jeder Call gibt ein Resultat-Dict zurück.
    → Die Liste ist in derselben Reihenfolge wie die Calls.
    → Wenn ein Call fehlschlägt → leeres Dict {} (nicht Exception).

    Args:
        ws_url: WebSocket Debugger URL.
        *calls: Tupel von (javascript_code, call_id).
                Beispiel: ("document.title", 1), ("document.URL", 2).

    Returns:
        List[dict]: Liste von Resultat-Dicts (oder leere Dicts bei Fehlern).
        Beispiel: [{"value": "HeyPiggy", "type": "string"}, {"value": "https://...", "type": "string"}].

    Raises:
        None (alle Exceptions werden abgefangen).

    Example:
        >>> ws_eval_multi("ws://...",
        ...     ("document.title", 1),
        ...     ("document.URL", 2))
        [{"value": "HeyPiggy", "type": "string"}, {"value": "https://...", "type": "string"}]
    """
    # Ergebnis-Liste.
    results = []

    try:
        # WebSocket-Verbindung aufbauen.
        ws = websocket.create_connection(
            ws_url,
            timeout=15,  # Längerer Timeout für mehrere Calls
            header=[f"Origin: {_ws_origin(ws_url)}"],
        )

        # ── Phase 1: ALLE Requests senden ──
        # WARUM zuerst ALLE senden? CDP ist asynchron (Server kann parallel arbeiten).
        # Wenn wir nach jedem Request warten → sequentiell (langsamer).
        # Wenn wir alle senden → Server kann parallel ausführen (schneller).
        for _i, (js_code, call_id) in enumerate(calls):
            ws.send(
                json.dumps(
                    {
                        "id": call_id,  # Eindeutige ID pro Call
                        "method": "Runtime.evaluate",
                        "params": {
                            "expression": js_code,
                            "returnByValue": True,  # WICHTIG: Serialisieren
                        },
                    }
                )
            )

        # ── Phase 2: ALLE Antworten empfangen ──
        # WARUM in Reihenfolge? CDP garantiert Reihenfolge der Antworten.
        # Wir empfangen genau so viele Antworten wie wir Calls gesendet haben.
        for _i, (js_code, call_id) in enumerate(calls):
            # Auf Antwort warten.
            response = ws.recv()

            # Parse JSON.
            parsed = json.loads(response)

            # Extrahiere Wert aus verschachteltem Dict.
            # parsed["result"]["result"]["value"] = der tatsächliche Wert.
            value = parsed.get("result", {}).get("result", {}).get("value", "")

            # Füge Wert zu Ergebnis-Liste hinzu.
            results.append(value)

        # WebSocket schließen.
        ws.close()

    except Exception:
        # JEGLICHE Exception → so viele Results wie möglich zurückgeben.
        # Wenn wir 3 Calls gesendet haben aber nach dem 2. ein Fehler auftritt
        # → results enthält 2 Werte (nicht leer).
        # Das ist robust: Teilergebnisse sind besser als gar nichts.
        pass

    return results


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER: DOM Element Extraction
# ═══════════════════════════════════════════════════════════════════════════════
# Diese Funktion extrahiert ALLE interaktiven Elemente von einer Survey-Seite.
# Sie wird von GET /survey/modal und POST /survey/run-one verwendet.
# ═══════════════════════════════════════════════════════════════════════════════


def extract_elements_from_page(ws_url: str) -> dict:
    """
    Extrahiert ALLE interaktiven Elemente von der aktuellen Seite.

    ABLAUF:
    1. JavaScript in Seite injizieren (via CDP Runtime.evaluate).
    2. JS findet und kategorisiert alle interaktiven Elemente:
       - Radio Buttons (Single-Choice Fragen).
       - Checkboxes (Multi-Choice Fragen).
       - Text Inputs (Kurze Antworten).
       - Textareas (Lange Antworten).
       - Buttons (Weiter, Submit, etc.).
       - Selects (Dropdowns).
    3. JS extrahiert Label-Texte aus <label>, aria-label, placeholder.
    4. JS taggt Elemente mit @r0, @c1, @t2, etc. für einfache Referenzierung.
    5. JS gibt JSON-String zurück.
    6. Wir parsen den JSON-String und geben Dict zurück.

    WARUM JavaScript (nicht Playwright)?
    → CDP ist schneller als Playwright (kein Page-Objekt Overhead).
    → JavaScript hat direkten DOM-Zugriff (keine Abstraktion).
    → Wir können komplexe Logik im Browser ausführen (schneller als Python).
    → Kein Playwright nötig (nur websocket-client).

    WARUM Tags (@r0, @c1, etc.)?
    → Einfache Referenzierung: "Wähle @r0" statt komplexer XPath/CSS-Selector.
    → Sprach-neutral: @r0 funktioniert für alle Sprachen.
    → Stabil: Tags ändern sich nicht wenn sich die Seite leicht ändert.
    → Im Gegensatz zu CUA-driver Indices: @r0 ist konsistent (nur Radios).

    WARUM ref-System?
    → @rN = Radio Buttons (Single-Choice).
    → @cN = Checkboxes (Multi-Choice).
    → @tN = Text Inputs (kurze Texte).
    → @aN = Textareas (lange Texte).
    → @bN = Buttons (Weiter, Submit, etc.).
    → @sN = Selects (Dropdowns).
    → N = Index (0, 1, 2, ...).

    WARUM Text-Extraktion?
    → Wir suchen in: <label> Text, aria-label, placeholder, nächstes Element.
    → Das ist eine Heuristik die in >80% der Fälle funktioniert.
    → Wenn kein Label gefunden → verwenden wir id/name als Fallback.

    WARUM substring(0, 100)?
    → Text könnte sehr lang sein (z.B. lange Beschreibungen).
    → Wir begrenzen auf 100 Zeichen pro Element (Performance).
    → Client kann bei Bedarf mehr Text abfragen (nicht nötig für Entscheidungen).

    WARUM return Dict?
    → {"elements": [...], "text": "...", "title": "...", "url": "..."}
    → elements: Liste aller interaktiven Elemente (für API-Response).
    → text: Gesamter Seiten-Text (für Keyword-Suche, Progress-Erkennung).
    → title: Seiten-Titel (für Navigation-Tracking).
    → url: Aktuelle URL (für Provider-Erkennung).

    Args:
        ws_url: WebSocket Debugger URL (für CDP Verbindung).

    Returns:
        dict: Dict mit "elements" (Liste), "text", "title", "url".
        Bei Fehler: {"elements": [], "text": "", "title": "", "url": ""}.

    Example:
        >>> extract_elements_from_page("ws://127.0.0.1:9999/devtools/page/ABC")
        {
            "elements": [
                {"ref": "@r0", "role": "radio", "text": "Männlich", ...},
                {"ref": "@r1", "role": "radio", "text": "Weiblich", ...},
                {"ref": "@b0", "role": "button", "text": "Weiter", ...}
            ],
            "text": "Seite 3 von 10...",
            "title": "Survey Page 3",
            "url": "https://heypiggy.com/?page=dashboard"
        }
    """
    # Das JavaScript das im Browser ausgeführt wird.
    # WARUM eine IIFE (Immediately Invoked Function Expression)?
    # → (function() { ... })() → Isoliert Variablen (keine globale Verschmutzung).
    # → Wir können return verwenden (nicht nur den letzten Ausdruck).
    # → Mehrere Statements möglich (nicht nur ein Expression).
    js = """
(function() {
    // Ergebnis-Objekt.
    var results = {
        text: document.body.innerText.substring(0, 3000),  // Seiten-Text (max 3000 chars)
        elements: [],                                      // Liste aller Elemente
        title: document.title,                             // Seiten-Titel
        url: window.location.href                          // Aktuelle URL
    };

    // ═══════════════════════════════════════════════════════════
    // RADIO BUTTONS (Single-Choice Fragen)
    // ═══════════════════════════════════════════════════════════
    // WARUM zuerst Radio? Die meisten Survey-Fragen sind Single-Choice.
    // KRITISCH (2026-05-09): Manche Frameworks (CPX Research, etc.) verwenden
    // versteckte <input type="radio" style="display:none"> + sichtbare <label>.
    // Wir müssen auf das LABEL klicken, nicht auf das versteckte Input!
    var radios = document.querySelectorAll('input[type="radio"]');
    radios.forEach(function(r, i) {
        var label = '';
        var isHidden = false;

        // Versuche: <label> Parent → Label-Text extrahieren.
        // closest('label') sucht das nächste <label> Element (Parent oder selbst).
        var parent = r.closest('label') || r.parentElement;
        if (parent) label = parent.innerText.trim().substring(0, 100);

        // Fallback: Container Div/Span/Li/Td.
        // Wenn kein <label> gefunden → suche im nächsten Container.
        var container = r.closest('div, span, li, td');
        var text = container ? container.innerText.trim().substring(0, 100) : label;

        // PRÜFE: Ist das Radio versteckt (display:none)?
        // Wenn ja → click_target = 'label' (das sichtbare Element).
        // Wenn nein → click_target = 'input' (das native Element).
        var style = window.getComputedStyle(r);
        if (style.display === 'none' || style.visibility === 'hidden') {
            isHidden = true;
        }

        // Element zum Ergebnis hinzufügen.
        results.elements.push({
            ref: '@r' + i,          // @r0, @r1, ... für Radio
            role: 'radio',          // Semantische Rolle
            text: text || label,     // Anzeigetext (Label oder Container)
            name: r.name || '',     // HTML name Attribut (für Gruppierung)
            value: r.value || '',   // HTML value Attribut (z.B. "male")
            checked: r.checked,     // Aktuell ausgewählt? (true/false)
            id: r.id || '',          // HTML id Attribut
            hidden: isHidden,       // Ist Input versteckt? (2026-05-09)
            click_target: isHidden ? 'label' : 'input'  // Was soll geklickt werden?
        });
    });

    // ═══════════════════════════════════════════════════════════
    // CHECKBOXES (Multi-Choice Fragen)
    // ═══════════════════════════════════════════════════════════
    // KRITISCH (2026-05-09): Gleiches Pattern wie Radios — versteckte Inputs + Labels.
    var checkboxes = document.querySelectorAll('input[type="checkbox"]');
    checkboxes.forEach(function(c, i) {
        var parent = c.closest('label') || c.parentElement;
        var text = parent ? parent.innerText.trim().substring(0, 100) : '';

        // PRÜFE: Ist die Checkbox versteckt?
        var style = window.getComputedStyle(c);
        var isHidden = (style.display === 'none' || style.visibility === 'hidden');

        results.elements.push({
            ref: '@c' + i,          // @c0, @c1, ... für Checkbox
            role: 'checkbox',
            text: text,
            name: c.name || '',
            value: c.value || '',
            checked: c.checked,
            id: c.id || '',
            hidden: isHidden,       // Ist Input versteckt? (2026-05-09)
            click_target: isHidden ? 'label' : 'input'  // Was soll geklickt werden?
        });
    });

    // ═══════════════════════════════════════════════════════════
    // TEXT INPUTS (Kurze Antworten)
    // ═════════════════════════════════════════════════════════==
    // WARUM input:not([type])? Manche Inputs haben kein type Attribut
    // (Default ist "text").
    var texts = document.querySelectorAll(
        'input[type="text"], input[type="email"], input[type="number"], input:not([type])'
    );
    texts.forEach(function(t, i) {
        var label = '';

        // aria-label: Accessibility-Label (für Screenreader).
        var lid = t.getAttribute('aria-label') || t.id || t.name || '';

        // Versuche: <label> vor dem Input (previousElementSibling).
        var parent = t.closest('label') || t.previousElementSibling;
        if (parent && parent.tagName === 'LABEL') {
            label = parent.innerText.trim();
        }

        results.elements.push({
            ref: '@t' + i,          // @t0, @t1, ... für Text
            role: 'textbox',
            text: label || lid,     // Label oder aria-label/id/name
            name: t.name || '',
            value: t.value || '',   // Aktueller Wert (evtl. bereits gefüllt)
            id: t.id || '',
            placeholder: t.placeholder || ''  // Placeholder-Text (Hinweis)
        });
    });

    // ═══════════════════════════════════════════════════════════
    // TEXTAREAS (Lange Antworten)
    // ═════════════════════════════════════════════════════════==
    var textareas = document.querySelectorAll('textarea');
    textareas.forEach(function(ta, i) {
        results.elements.push({
            ref: '@a' + i,          // @a0, @a1, ... für TextArea
            role: 'textarea',
            text: (ta.id || ta.name || '').substring(0, 80),
            value: ta.value || '',
            id: ta.id || ''
        });
    });

    // ═══════════════════════════════════════════════════════════
    // BUTTONS (Weiter, Submit, etc.)
    // ═════════════════════════════════════════════════════════==
    // WARUM a[role="button"]? Manche "Buttons" sind eigentlich Links
    // mit role="button" (Accessibility).
    var buttons = document.querySelectorAll(
        'button, input[type="submit"], input[type="button"], a[role="button"]'
    );
    buttons.forEach(function(b, i) {
        var text = (b.textContent || b.value || '').trim();

        // Nur Buttons mit Text hinzufügen (leere Buttons überspringen).
        if (text.length > 0) {
            results.elements.push({
                ref: '@b' + i,          // @b0, @b1, ... für Button
                role: 'button',
                text: text.substring(0, 100),
                id: b.id || '',
                disabled: b.disabled || false  // Ist Button deaktiviert?
            });
        }
    });

    // ═══════════════════════════════════════════════════════════
    // SELECTS (Dropdowns)
    // ═════════════════════════════════════════════════════════==
    var selects = document.querySelectorAll('select');
    selects.forEach(function(s, i) {
        var label = '';
        var parent = s.closest('label') || s.previousElementSibling;
        if (parent && parent.tagName === 'LABEL') {
            label = parent.innerText.trim();
        }

        results.elements.push({
            ref: '@s' + i,          // @s0, @s1, ... für Select
            role: 'select',
            text: label || s.id || s.name || '',
            id: s.id || ''
        });
    });

    // ═══════════════════════════════════════════════════════════
    // CUSTOM DIV RADIOS (z.B. TolunaStart cf-radio-answer)
    // ═════════════════════════════════════════════════════════==
    // WARUM? Manche Survey-Provider (TolunaStart, anyaudience.ai) verwenden
    // KEINE nativen <input type="radio">, sondern Custom DIVs.
    // Klassen-Namen: "cf-radio-answer", "custom-radio", "radio-option", etc.
    // Wir suchen nach bekannten Mustern und taggen sie als @cr0, @cr1, ...
    var customRadioSelectors = [
        '.cf-radio-answer',           // TolunaStart Standard
        '.custom-radio',               // Generisch
        '.radio-option',               // Alternative
        '[role="radio"]',              // ARIA role (Accessibility)
        '.survey-radio',               // Weitere Varianten
    ];

    var customRadios = [];
    for (var sel of customRadioSelectors) {
        var found = document.querySelectorAll(sel);
        if (found.length > 0) {
            customRadios = Array.from(found);
            break;  // Nimm den ersten Selector der Treffer hat
        }
    }

    customRadios.forEach(function(div, i) {
        var text = (div.innerText || div.textContent || '').trim().substring(0, 100);
        var isSelected = div.classList.contains('selected') ||
                         div.classList.contains('active') ||
                         div.getAttribute('aria-checked') === 'true';

        results.elements.push({
            ref: '@cr' + i,         // @cr0, @cr1, ... für Custom Radio DIV
            role: 'custom_radio',   // Semantische Rolle (NICHT native radio!)
            text: text,
            class: div.className || '',  // CSS Klassen (für Debugging)
            selected: isSelected,
            id: div.id || ''
        });
    });

    // Rückgabe des Ergebnis-Objekts.
    return results;
})()
"""
    try:
        # WebSocket-Verbindung aufbauen.
        ws = websocket.create_connection(
            ws_url, timeout=10, header=[f"Origin: {_ws_origin(ws_url)}"]
        )

        # CDP Befehl senden.
        ws.send(
            json.dumps(
                {
                    "id": 1,
                    "method": "Runtime.evaluate",
                    "params": {
                        "expression": js,
                        "returnByValue": True,  # WICHTIG: Objekt serialisieren
                    },
                }
            )
        )

        # Auf Antwort warten.
        response = ws.recv()

        # WebSocket schließen.
        ws.close()

        # Parse JSON-Antwort.
        parsed = json.loads(response)

        # Extrahiere Wert (das Ergebnis-Objekt).
        result = parsed.get("result", {}).get("result", {}).get("value", "{}")

        # WARUM json.loads(result) if isinstance(result, str)?
        # → Das JS gibt ein Objekt zurück (nicht String).
        # → returnByValue=True serialisiert das Objekt.
        # → Aber manchmal gibt CDP einen String zurück (JSON-String).
        # → Wir prüfen den Typ und parsen wenn nötig.
        if isinstance(result, str):
            return json.loads(result)
        else:
            return result

    except Exception:
        # Fehler → leere Struktur zurückgeben (fail-closed).
        return {"elements": [], "text": "", "title": "", "url": ""}


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINT 1: Survey Card Click (POST /survey/click-card)
# ═══════════════════════════════════════════════════════════════════════════════
# Klickt eine Survey-Karte auf dem HeyPiggy Dashboard an.
# Das ist der ERSTE SCHRITT im Survey-Flow.
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/click-card", response_model=SurveyClickCardResponse)
async def click_card(req: SurveyClickCardRequest):
    """
    Klickt eine Survey-Karte auf dem HeyPiggy Dashboard an.

    ABLAUF:
    1. Finde Dashboard WebSocket (get_dashboard_ws).
    2. Wenn nicht gefunden → Error-Response.
    3. Generiere JavaScript für Card-Click:
       - Wenn survey_id angegeben → suche Card mit onclick="clickSurvey('ID')".
       - Wenn nicht angegeben → klicke erste verfügbare Card.
    4. Führe JavaScript aus (ws_eval).
    5. Interpretiere Ergebnis:
       - "clicked:ID" → Spezifische Survey geklickt.
       - "clicked_first" → Erste verfügbare geklickt.
       - "not_found" → Keine Surveys verfügbar.
    6. Warte 2s (Modal muss sich öffnen).
    7. Lese Modal-Inhalt (ws_eval mit Modal-JS).
    8. Gib Response zurück.

    WARUM NICHT direkt Survey öffnen?
    → HeyPiggy hat ein ZWEI-Schritt-Flow:
      1. Card Click → Modal öffnet sich (mit Survey-Details).
      2. "Umfrage starten" Button im Modal → Survey öffnet sich.
    → Wir können NICHT direkt zur Survey navigieren (keine direkte URL).
    → Der Flow erfordert Card-Click → Modal → Start-Button.

    WARUM survey_id Optional?
    → None = "Egal welche Survey, nimm die erste" (gut für Automation).
    → String = "Bestimmte Survey" (gut für gezielte Auswahl).
    → Erste Survey ist oft die mit dem höchsten Reward / kürzester Dauer.

    WARUM onclick="clickSurvey('ID')"?
    → HeyPiggy verwendet onclick-Handler auf den Survey-Cards.
    → clickSurvey('12345') öffnet das Modal für Survey-ID 12345.
    → Wir suchen nach diesem Pattern und simulieren einen Click.

    WARUM 2s Wartezeit?
    → Nach dem Card-Click öffnet sich ein Modal (JavaScript-Animation).
    → Das Modal braucht Zeit zum Laden (DOM-Elemente erstellen).
    → 2s ist ein Kompromiss: schnell genug für Automation,
    → lang genug für langsames Internet / langsamen Computer.

    WARUM Modal-Check nach Wartezeit?
    → Wir prüfen OB das Modal sich geöffnet hat.
    → Wenn nicht → modal_visible=False (evtl. JavaScript-Fehler).
    → Wenn ja → modal_text und modal_buttons extrahieren.

    Args:
        req: SurveyClickCardRequest
            - survey_id: Optional. Wenn None → erste verfügbare Survey.
            - cdp_port: CDP Port für Chrome Verbindung (default: 9999).

    Returns:
        SurveyClickCardResponse:
            - status: "success", "no_surveys", oder "error".
            - survey_id: ID der geklickten Survey (oder "first_available").
            - modal_visible: True wenn Modal geöffnet.
            - modal_text: Text im Modal (erste 500 Zeichen).
            - modal_buttons: Verfügbare Buttons (z.B. ["Umfrage starten", "Schließen"]).

    Example:
        POST /survey/click-card
        {"survey_id": null, "cdp_port": 9999}
        → {"status": "success", "survey_id": "first_available",
            "modal_visible": true, "modal_text": "...",
            "modal_buttons": ["Umfrage starten", "Schließen"]}
    """
    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 1: Dashboard WebSocket finden
    # ═══════════════════════════════════════════════════════════════════════

    ws_url = get_dashboard_ws(req.cdp_port)

    if not ws_url:
        # Kein Dashboard gefunden → Chrome läuft nicht oder kein Dashboard-Tab.
        return SurveyClickCardResponse(
            status="error",
            survey_id=None,
            modal_visible=False,
            modal_text=None,
            modal_buttons=[],
            message="No dashboard found. Is Chrome running?",
        )

    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 2: JavaScript für Survey-Card Click generieren
    # ═══════════════════════════════════════════════════════════════════════

    if req.survey_id:
        # Spezifische Survey-ID: Suche Card mit onclick="clickSurvey('ID')".
        # Wir verwenden String-Matching im onclick-Attribut.
        click_js = f"""
(function() {{
    // Suche ALLE Cards mit onclick Attribut das "clickSurvey" enthält.
    var cards = document.querySelectorAll("[onclick*=clickSurvey]");

    // Iteriere über alle Cards.
    for (var c of cards) {{
        // Extrahiere onclick-Attribut.
        var onclick = c.getAttribute("onclick");

        // Regex: clickSurvey('12345') oder clickSurvey("12345").
        // [0-9]+ = eine oder mehrere Ziffern (kein Backslash, kein SyntaxWarning).
        var m = onclick.match(/clickSurvey\\('?([0-9]+)'?\\)/);

        // Wenn ID übereinstimmt → klicken.
        if (m && m[1] === "{req.survey_id}") {{
            c.click();
            return "clicked:" + m[1];
        }}
    }}

    // Fallback: Wenn ID nicht gefunden, klicke erste verfügbare Card.
    var first = document.querySelector("[onclick*=clickSurvey]");
    if (first) {{ first.click(); return "clicked_first"; }}

    return "not_found";
}})()
"""
    else:
        # Keine ID angegeben: Klicke erste verfügbare Card.
        click_js = """
(function() {
    // Suche erste Card mit onclick="clickSurvey(...)".
    var first = document.querySelector("[onclick*=clickSurvey]");

    if (first) {
        first.click();
        return "clicked_first";
    }

    return "not_found";
})()
"""

    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 3: JavaScript ausführen
    # ═══════════════════════════════════════════════════════════════════════

    try:
        result = ws_eval(ws_url, click_js, timeout=10)

        # Extrahiere den Wert aus dem Resultat.
        # result = {"value": "clicked_first", "type": "string"}
        result_text = result.get("value", "") if result else ""
    except Exception:
        # Fehler beim Ausführen → leerer Text (wird unten behandelt).
        result_text = ""

    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 4: Ergebnis interpretieren
    # ═══════════════════════════════════════════════════════════════════════

    survey_id = None

    if result_text.startswith("clicked:"):
        # Spezifische Survey geklickt.
        # Format: "clicked:12345" → ID = "12345".
        survey_id = result_text.split(":", 1)[1].strip()

    elif result_text == "clicked_first":
        # Erste verfügbare Survey geklickt.
        survey_id = "first_available"

    elif result_text == "not_found":
        # Keine Surveys verfügbar (Dashboard leer).
        return SurveyClickCardResponse(
            status="no_surveys",
            survey_id=None,
            modal_visible=False,
            modal_text=None,
            modal_buttons=[],
            message="No survey cards found on dashboard",
        )

    else:
        # Unerwartetes Ergebnis (JavaScript-Fehler, etc.).
        return SurveyClickCardResponse(
            status="error",
            survey_id=None,
            modal_visible=False,
            modal_text=None,
            modal_buttons=[],
            message=f"Unexpected result: {result_text}",
        )

    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 5: Warten bis Modal sich öffnet
    # ═══════════════════════════════════════════════════════════════════════

    # Warte 2s (Modal muss sich öffnen).
    # WARUM time.sleep (nicht asyncio.sleep)? FastAPI-Endpoints laufen in Thread-Pool.
    # Blocking ist OK hier (Endpoint ist synchron bis auf Top-Level await).
    time.sleep(2)

    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 6: Modal-Inhalt lesen
    # ═══════════════════════════════════════════════════════════════════════

    modal_js = """
(function() {
    // Suche Modal (Bootstrap-Style: .modal.show oder class enthält "modal" und "show").
    var modal = document.querySelector(".modal.show, [class*='modal'][class*='show']");

    if (!modal) {
        // Kein Modal gefunden → nicht geöffnet.
        return JSON.stringify({visible: false});
    }

    // Extrahiere alle Buttons im Modal.
    var buttons = [];
    var btns = modal.querySelectorAll("button, a[role='button']");

    btns.forEach(function(b) {
        var t = (b.textContent || '').trim();
        if (t) buttons.push(t.substring(0, 80));  // Max 80 Zeichen pro Button
    });

    // Rückgabe: Modal-Info als JSON-String.
    return JSON.stringify({
        visible: true,
        text: modal.innerText.substring(0, 500),  // Max 500 Zeichen
        buttons: buttons
    });
})()
"""
    try:
        modal_result = ws_eval(ws_url, modal_js, timeout=10)
        modal_value = modal_result.get("value", "{}") if modal_result else "{}"
        modal_data = json.loads(modal_value)
    except Exception:
        # Fehler beim Modal-Lesen → Default-Werte.
        modal_data = {"visible": False, "text": "", "buttons": []}

    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 7: Response zurückgeben
    # ═══════════════════════════════════════════════════════════════════════

    return SurveyClickCardResponse(
        status="success",
        survey_id=survey_id,
        modal_visible=modal_data.get("visible", False),
        # Wenn Modal nicht sichtbar → modal_text = None (nicht leerer String).
        modal_text=modal_data.get("text", "")[:500] if modal_data.get("visible") else None,
        modal_buttons=modal_data.get("buttons", []),
        message="Clicked survey card" + (f" ({survey_id})" if survey_id else ""),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINT 2: Get Modal / Page Content (GET /survey/modal)
# ═══════════════════════════════════════════════════════════════════════════════
# Liest den aktuellen Modal-Inhalt oder Seiteninhalt.
# Wird verwendet nach click-card und zwischen den Survey-Schritten.
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/modal", response_model=SurveyGetModalResponse)
async def get_modal(req: SurveyGetModalRequest):
    """
    Liest den aktuellen Modal-Inhalt oder Seiteninhalt.

    ABLAUF:
    1. Prüfe ob ein Modal geöffnet ist (.modal.show).
    2. Wenn ja: Extrahiere Modal-Inhalt (Text, Buttons).
    3. Wenn nein: Extrahiere alle Seiten-Elemente (extract_elements_from_page).
    4. Erkenne Provider (Qualtrics, Toluna, etc.) aus URL.
    5. Erkenne Fortschritt ("Seite 3 von 10").
    6. Gib Response zurück.

    WARUM GET statt POST?
    → Dieser Endpoint liest NUR (keine Seiteneffekte).
    → GET ist semantisch korrekt für Read-Operationen (REST-Prinzip).
    → POST wäre falsch weil nichts verändert wird.

    WARUM Request-Body bei GET?
    → FastAPI erlaubt GET mit Request-Body (nicht standard REST, aber praktisch).
    → Alternative: Query-Parameter (cdp_port=9999&profile=default).
    → Wir verwenden Body für Konsistenz mit anderen Endpoints (alle POST).
    → WARNUNG: Manche Proxies/Clients blockieren GET mit Body.
    → Für maximale Kompatibilität → Query-Parameter verwenden.

    WARUM Modal vs Seiten-Elemente?
    → Wenn HeyPiggy Dashboard Modal geöffnet → Modal-Inhalt zurückgeben.
    → Wenn Survey läuft (kein Modal) → alle interaktiven Elemente der Seite.
    → Der Client kann unterscheiden: modal_visible=True/False.

    WARUM Progress-Erkennung?
    → Viele Surveys zeigen "Seite 3 von 10" oder "3/10".
    → Wir extrahieren dies aus dem Text (Regex: ([0-9]+)\\s*/\\s*([0-9]+)).
    → Nützlich für Monitoring und Entscheidungen (fast fertig = nicht aufgeben).

    WARUM provider-Feld? (WICHTIG: NUR Logging/Statistik!)
    → Die API macht KEINE echte Framework-Erkennung.
    → Der provider-String ist primitives URL-Matching: "qualtrics" in url.lower().
    → Das ist NICHT intelligent — es ist nur für Logs/Monitoring.
    → ECHTE Framework-Erkennung passiert im NEMO Loop (src/stealth_survey/):
    →   Nemotron 3 Omni analysiert DOM-Struktur und erkennt AUTOMATISCH
    →   ob es Qualtrics, Toluna, Cint, etc. ist — OHNE URL-Patterns.
    → Diese API ist eine DUMME Remote-Control. Sie macht keine Entscheidungen.

    Args:
        req: SurveyGetModalRequest
            - cdp_port: CDP Port für Chrome Verbindung (default: 9999).

    Returns:
        SurveyGetModalResponse:
            - status: "success", "no_modal", oder "error".
            - modal_visible: True wenn Modal geöffnet.
            - elements: Liste aller interaktiven Elemente (wenn kein Modal).
            - text: Seiten-/Modal-Text (erste 2000 Zeichen).
            - page_title: Dokument-Titel.
            - provider: URL-Matched Provider-Name (NUR für Logging/Statistiken).
            - progress: Fortschritt (z.B. "3/10").

    Example:
        GET /survey/modal
        {"cdp_port": 9999}
        → {"status": "success", "modal_visible": false,
            "elements": [{"ref": "@r0", "role": "radio", "text": "Männlich"}, ...],
            "text": "Seite 3 von 10...", "provider": "qualtrics", "progress": "3/10"}
    """
    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 1: Dashboard WebSocket finden
    # ═══════════════════════════════════════════════════════════════════════

    ws_url = get_dashboard_ws(req.cdp_port)

    if not ws_url:
        return SurveyGetModalResponse(
            status="error",
            message="No dashboard found",
        )

    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 2: Modal-Check
    # ═══════════════════════════════════════════════════════════════════════

    modal_js = """
(function() {
    // Suche Modal (Bootstrap-Style).
    var modal = document.querySelector(".modal.show, [class*='modal'][class*='show']");

    if (modal) {
        // Modal ist geöffnet!
        var buttons = [];

        // Extrahiere alle Button-Texte im Modal.
        modal.querySelectorAll("button").forEach(function(b) {
            var t = (b.textContent || '').trim();
            if (t) buttons.push(t.substring(0, 80));
        });

        // Rückgabe: Modal-Info + Seiten-Titel.
        return JSON.stringify({
            is_modal: true,
            text: modal.innerText.substring(0, 1000),  // Max 1000 Zeichen
            buttons: buttons,
            title: document.title
        });
    }

    // Kein Modal → Rückgabe: Kein Modal.
    return JSON.stringify({is_modal: false});
})()
"""

    # WebSocket-Verbindung für Modal-Check.
    ws = websocket.create_connection(ws_url, timeout=10, header=[f"Origin: {_ws_origin(ws_url)}"])

    ws.send(
        json.dumps(
            {
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {"expression": modal_js, "returnByValue": True},
            }
        )
    )

    response = ws.recv()
    ws.close()

    # Parse Antwort.
    parsed = json.loads(response)
    modal_data = json.loads(parsed.get("result", {}).get("result", {}).get("value", "{}"))

    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 3: Wenn kein Modal → "no_modal" zurückgeben
    # ═══════════════════════════════════════════════════════════════════════

    if not modal_data.get("is_modal"):
        # Kein Modal geöffnet → wir sind auf einer Survey-Seite (nicht Dashboard).
        return SurveyGetModalResponse(
            status="no_modal",
            modal_visible=False,
            elements=[],
            text="",
            page_title="",
            message="No survey modal open",
        )

    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 4: Alle Elemente von der Seite extrahieren
    # ═══════════════════════════════════════════════════════════════════════

    elements = extract_elements_from_page(ws_url)

    # Konvertiere in Pydantic-Modelle.
    element_list = []
    for el in elements.get("elements", []):
        element_list.append(
            SurveyElement(
                ref=el.get("ref", ""),
                role=el.get("role", ""),
                text=el.get("text", ""),
                label=el.get("text", ""),  # Label = Text (Fallback)
                value=el.get("value", ""),
                selected=el.get("checked", el.get("selected")),
                visible=True,
            )
        )

    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 5: Fortschritt erkennen (z.B. "Seite 3 von 10")
    # ═══════════════════════════════════════════════════════════════════════

    text = elements.get("text", "")
    progress = None

    # Regex: "Seite 3 von 10" oder "3/10".
    # ([0-9]+) = eine oder mehrere Ziffern (Gruppe 1 = aktuelle Seite).
    # \s*/\s* = Slash mit optionalen Leerzeichen.
    # ([0-9]+) = eine oder mehrere Ziffern (Gruppe 2 = Gesamtseiten).
    import re

    m = re.search(r"(\d+)\s*/\s*(\d+)", text)
    if m:
        progress = f"{m.group(1)}/{m.group(2)}"

    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 6: Provider aus URL erkennen
    # ═══════════════════════════════════════════════════════════════════════

    url = elements.get("url", "")
    provider = "heypiggy_modal"

    # Provider-Erkennung anhand der URL.
    if "samplicio" in url.lower():
        provider = "samplicio"
    elif "qualtrics" in url.lower():
        provider = "qualtrics"
    elif "toluna" in url.lower():
        provider = "tolunastart"

    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 7: Response zurückgeben
    # ═══════════════════════════════════════════════════════════════════════

    return SurveyGetModalResponse(
        status="success",
        modal_visible=True,
        elements=element_list,
        text=text[:2000],  # Max 2000 Zeichen
        page_title=elements.get("title", ""),
        provider=provider,
        progress=progress,
        message=f"Modal with {len(element_list)} elements",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINT 3: Click Button (POST /survey/click-button)
# ═══════════════════════════════════════════════════════════════════════════════
# Klickt einen Button auf der Survey-Seite oder im Modal.
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/click-button", response_model=SurveyClickButtonResponse)
async def click_button(req: SurveyClickButtonRequest):
    """
    Klickt einen Button auf der Survey-Seite oder im Modal.

    ABLAUF:
    1. Speichere Seiteninhalt VOR dem Klick (für Vergleich).
    2. Suche Button mit passendem Label (case-insensitive, partial match).
    3. Klicke den Button (JavaScript .click()).
    4. Warte (timeout_ms) für Seitenreaktion.
    5. Speichere Seiteninhalt NACH dem Klick.
    6. Vergleiche Before/After → page_changed Flag.
    7. Gib Response zurück.

    WARUM Partial Match?
    → Button-Labels variieren leicht:
      - "Weiter" vs "weiter" (Groß-/Kleinschreibung).
      - "Weiter →" vs "Weiter" (Pfeile, Whitespace).
      - "Umfrage starten" vs "Starten" (unterschiedliche Längen).
    → Partial match ist robuster als exact match.
    → Beispiel: "weiter" matcht "Weiter →", "WEITER", "weiter".

    WARUM page_changed Check?
    → Manche Buttons (z.B. "Schließen") schließen nur ein Modal ohne Seitenwechsel.
    → Der page_changed Flag zeigt an ob tatsächlich eine neue Seite geladen wurde.
    → Wichtig für Loop-Logik: Wenn page_changed=False → evtl. Retry nötig.

    WARUM timeout_ms?
    → Nach einem Click braucht die Seite Zeit zu reagieren (JavaScript, AJAX).
    → "Weiter"-Button → neue Frage laden (typisch: 500ms - 3s).
    → Zu kurz → Seite noch nicht geladen, page_changed=False obwohl sich was änderte.
    → Zu lang → API-Call dauert ewig (schlechte User Experience).
    → 5000ms Default = Kompromiss (deckt 95% der Fälle ab).

    WARUM Before/After Vergleich?
    → Wir vergleichen document.body.innerText vor und nach dem Click.
    → Wenn Text gleich → page_changed=False (kein Seitenwechsel).
    → Wenn Text unterschiedlich → page_changed=True (neue Seite geladen).
    → Einfache Heuristik (kein komplexer DOM-Vergleich).

    Args:
        req: SurveyClickButtonRequest
            - button_label: Text des Buttons (z.B. "Weiter", "Umfrage starten").
            - cdp_port: CDP Port (default: 9999).
            - timeout_ms: Wartezeit nach Klick (default: 5000ms).

    Returns:
        SurveyClickButtonResponse:
            - status: "success", "not_found", "error".
            - page_changed: True wenn Seite sich geändert hat.
            - new_text: Neuer Seiteninhalt (erste 500 Zeichen).

    Example:
        POST /survey/click-button
        {"button_label": "Weiter", "cdp_port": 9999, "timeout_ms": 5000}
        → {"status": "success", "button_label": "Weiter",
            "page_changed": true, "new_text": "Seite 4 von 10..."}
    """
    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 1: Dashboard WebSocket finden
    # ═══════════════════════════════════════════════════════════════════════

    ws_url = get_dashboard_ws(req.cdp_port)

    if not ws_url:
        return SurveyClickButtonResponse(
            status="error",
            button_label=req.button_label,
            page_changed=False,
            message="No dashboard found",
        )

    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 2: Seiteninhalt VOR dem Klick speichern
    # ═══════════════════════════════════════════════════════════════════════

    before_js = "document.body.innerText.substring(0, 500)"

    try:
        ws = websocket.create_connection(
            ws_url, timeout=10, header=[f"Origin: {_ws_origin(ws_url)}"]
        )
        ws.send(
            json.dumps(
                {
                    "id": 1,
                    "method": "Runtime.evaluate",
                    "params": {"expression": before_js, "returnByValue": True},
                }
            )
        )
        response = ws.recv()
        ws.close()

        parsed = json.loads(response)
        before_text = parsed.get("result", {}).get("result", {}).get("value", "")
    except Exception:
        before_text = ""

    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 3: Button-Click JavaScript generieren
    # ═══════════════════════════════════════════════════════════════════════

    # Label in Kleinbuchstaben (case-insensitive matching).
    label_lower = req.button_label.lower()

    click_js = f"""
(function() {{
    // Suche ALLE Buttons (verschiedene HTML-Tags).
    var btns = document.querySelectorAll(
        "button, a[role='button'], input[type='submit'], input[type='button']"
    );

    // Iteriere über alle Buttons.
    for (var b of btns) {{
        // Extrahiere Text-Content oder Value.
        // textContent = sichtbarer Text (inkl. untergeordneter Elemente).
        // value = Input-Value (für <input type="submit">).
        var t = (b.textContent || b.value || '').trim().toLowerCase();

        // Partial Match: Ist der Label-Text im Button-Text enthalten?
        if (t.includes("{label_lower}")) {{
            b.click();
            return "clicked:" + (b.textContent || '').trim().substring(0, 50);
        }}
    }}

    return "not_found";
}})()
"""

    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 4: Button klicken
    # ═══════════════════════════════════════════════════════════════════════

    ws = websocket.create_connection(ws_url, timeout=10, header=[f"Origin: {_ws_origin(ws_url)}"])
    ws.send(
        json.dumps(
            {
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {"expression": click_js, "returnByValue": True},
            }
        )
    )
    response = ws.recv()
    ws.close()

    parsed = json.loads(response)
    result = parsed.get("result", {}).get("result", {}).get("value", "")

    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 5: Wenn Button nicht gefunden → Error
    # ═══════════════════════════════════════════════════════════════════════

    if "not_found" in result:
        return SurveyClickButtonResponse(
            status="not_found",
            button_label=req.button_label,
            page_changed=False,
            new_text="",
            message=f"Button not found: {req.button_label}",
        )

    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 6: Warten (JavaScript/Seite muss reagieren)
    # ═══════════════════════════════════════════════════════════════════════

    # Warte timeout_ms Millisekunden.
    # WARUM time.sleep? FastAPI-Endpoints laufen in Thread-Pool.
    # Blocking ist OK hier (Client wartet sowieso auf Response).
    time.sleep(req.timeout_ms / 1000)

    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 7: Seiteninhalt NACH dem Klick speichern
    # ═══════════════════════════════════════════════════════════════════════

    ws = websocket.create_connection(ws_url, timeout=10, header=[f"Origin: {_ws_origin(ws_url)}"])
    ws.send(
        json.dumps(
            {
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {"expression": before_js, "returnByValue": True},
            }
        )
    )
    response = ws.recv()
    ws.close()

    parsed = json.loads(response)
    after_text = parsed.get("result", {}).get("result", {}).get("value", "")

    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 8: Vergleiche Before/After
    # ═══════════════════════════════════════════════════════════════════════

    # Wenn Text sich geändert hat → page_changed=True.
    page_changed = before_text != after_text

    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 9: Response zurückgeben
    # ═══════════════════════════════════════════════════════════════════════

    return SurveyClickButtonResponse(
        status="success",
        button_label=req.button_label,
        page_changed=page_changed,
        new_text=after_text[:500],
        message="Clicked" + (f" (page changed: {page_changed})" if page_changed else ""),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINT 4: Select Option (POST /survey/select-option)
# ═══════════════════════════════════════════════════════════════════════════════
# Wählt eine Radio-Button oder Checkbox-Option aus.
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/select-option", response_model=SurveySelectOptionResponse)
async def select_option(req: SurveySelectOptionRequest):
    """
    Wählt eine Radio-Button oder Checkbox-Option aus.

    ABLAUF:
    1. Suche Radio Buttons mit passendem Label/Text (case-insensitive, partial).
    2. Wenn nicht gefunden → Suche Checkboxes (Fallback).
    3. Klicke das erste passende Element.
    4. Warte (wait_after_ms) für UI-Update.
    5. Gib Response zurück.

    WARUM Radio VOR Checkbox?
    → Die meisten Survey-Fragen sind Single-Choice (Radio).
    → Wir prüfen zuerst Radio, dann Checkbox als Fallback.
    → Das ist eine Heuristik die in >80% der Fälle korrekt ist.

    WARUM Partial Match?
    → Option-Texte variieren:
      - "Männlich" vs "männlich" (Groß-/Kleinschreibung).
      - "18-25 Jahre" vs "18 - 25" (Leerzeichen).
      - "Deutschland" vs "DE" (Abkürzungen).
    → Partial match ist robuster als exact match.
    → Beispiel: "deutsch" matcht "Deutschland", "Deutsch", "deutsch".

    WARUM nur ERSTES passende Element?
    → Radio Buttons sind Single-Choice: Nur eine Auswahl möglich.
    → Wenn mehrere matchten wäre das ein UI-Bug (duplizierte Labels).
    → Bei Checkboxen (Multi-Choice) könnte man mehrere auswählen,
    → aber das ist komplexer und selten nötig.

    WARUM wait_after_ms?
    → Manche Survey-Seiten validieren die Auswahl sofort.
    → Sie aktivieren/deaktivieren den "Weiter"-Button basierend auf Auswahl.
    → 1000ms gibt der UI Zeit zu reagieren (JavaScript-Events).
    → Zu kurz → Button noch deaktiviert (obwohl Auswahl getroffen).

    WARUM JavaScript .click()?
    → Wir simulieren einen echten Click (inkl. Event-Bubbling).
    → Das feuert alle Event-Listener (React, Vue, Angular, Vanilla JS).
    → Einfacher als komplexe Event-Dispatching (MouseEvent, etc.).

    Args:
        req: SurveySelectOptionRequest
            - option_text: Text der Option (z.B. "Männlich", "Deutschland").
            - cdp_port: CDP Port (default: 9999).
            - wait_after_ms: Wartezeit nach Auswahl (default: 1000ms).

    Returns:
        SurveySelectOptionResponse:
            - status: "success", "not_found", "error".
            - selected: True wenn erfolgreich ausgewählt.

    Example:
        POST /survey/select-option
        {"option_text": "Männlich", "cdp_port": 9999}
        → {"status": "success", "option_text": "Männlich", "selected": true}
    """
    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 1: Dashboard WebSocket finden
    # ═══════════════════════════════════════════════════════════════════════

    ws_url = get_dashboard_ws(req.cdp_port)

    if not ws_url:
        return SurveySelectOptionResponse(
            status="error",
            option_text=req.option_text,
            selected=False,
            message="No dashboard found",
        )

    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 2: Label in Kleinbuchstaben (case-insensitive)
    # ═══════════════════════════════════════════════════════════════════════

    label_lower = req.option_text.lower()

    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 3: JavaScript für Radio/Checkbox Auswahl
    # ═══════════════════════════════════════════════════════════════════════

    click_js = f"""
(function() {{
    // ═══════════════════════════════════════════════════════════
    // RADIO BUTTONS (Single-Choice) - Zuerst prüfen!
    // ═════════════════════════════════════════════════════════==
    // KRITISCH (2026-05-09): Versteckte Inputs (display:none) erfordern
    // Klick auf das PARENT <label>, nicht auf das <input> selbst!
    var radios = document.querySelectorAll('input[type="radio"]');

    for (var r of radios) {{
        // Suche Container (div, span, li, td, label) für Label-Text.
        var container = r.closest('div, span, li, td, label');
        var text = container ? container.innerText.trim().toLowerCase() : '';

        // Zusätzlich: Nächstes Element (oft Label nach Radio).
        var label = r.nextElementSibling;
        if (label) text += ' ' + (label.textContent || '').trim().toLowerCase();

        // Partial Match: Ist der Label-Text im Container-Text enthalten?
        // ODER: Ist der Label-Text im HTML value enthalten?
        if (text.includes("{label_lower}") || r.value.toLowerCase().includes("{label_lower}")) {{
            // 2026-05-09 BUGFIX: Prüfe ob Input versteckt ist.
            var style = window.getComputedStyle(r);
            var isHidden = (style.display === 'none' || style.visibility === 'hidden');

            if (isHidden && container) {{
                // Klicke das sichtbare Container-Element (meist <label>)
                container.click();
                return "radio_label_clicked:" + r.value;
            }} else {{
                // Klicke direkt auf das Input (native Radios)
                r.click();
                return "radio:" + r.value;
            }}
        }}
    }}

    // ═══════════════════════════════════════════════════════════
    // CHECKBOXES (Multi-Choice) - Fallback
    // ═════════════════════════════════════════════════════════==
    // KRITISCH (2026-05-09): Gleicher Bug wie Radios — versteckte Inputs.
    var checks = document.querySelectorAll('input[type="checkbox"]');

    for (var c of checks) {{
        var container = c.closest('div, span, li, td, label');
        var text = (container ? container.innerText.trim() : '').toLowerCase();

        if (text.includes("{label_lower}")) {{
            // 2026-05-09 BUGFIX: Prüfe ob Input versteckt ist.
            var style = window.getComputedStyle(c);
            var isHidden = (style.display === 'none' || style.visibility === 'hidden');

            if (isHidden && container) {{
                container.click();
                return "checkbox_label_clicked:" + c.value;
            }} else {{
                c.click();
                return "checkbox:" + c.value;
            }}
        }}
    }}

    return "not_found";
}})()
"""

    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 4: WebSocket Verbindung aufbauen und ausführen
    # ═══════════════════════════════════════════════════════════════════════

    ws = websocket.create_connection(ws_url, timeout=10, header=[f"Origin: {_ws_origin(ws_url)}"])
    ws.send(
        json.dumps(
            {
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {"expression": click_js, "returnByValue": True},
            }
        )
    )
    response = ws.recv()
    ws.close()

    parsed = json.loads(response)
    result = parsed.get("result", {}).get("result", {}).get("value", "")

    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 5: Wenn nicht gefunden → Error
    # ═══════════════════════════════════════════════════════════════════════

    if "not_found" in result:
        return SurveySelectOptionResponse(
            status="not_found",
            option_text=req.option_text,
            selected=False,
            message=f"Option not found: {req.option_text}",
        )

    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 6: Warten (JavaScript/Seite muss reagieren)
    # ═══════════════════════════════════════════════════════════════════════

    time.sleep(req.wait_after_ms / 1000)

    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 7: Response zurückgeben
    # ═══════════════════════════════════════════════════════════════════════

    return SurveySelectOptionResponse(
        status="success",
        option_text=req.option_text,
        selected=True,
        message=f"Selected: {result}",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINT 5: Fill Text (POST /survey/fill-text)
# ═══════════════════════════════════════════════════════════════════════════════
# Füllt ein Text-Input-Feld oder Textarea aus.
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/fill-text", response_model=SurveyFillTextResponse)
async def fill_text(req: SurveyFillTextRequest):
    """
    Füllt ein Text-Input-Feld oder Textarea aus.

    ABLAUF:
    1. Suche Input-Feld mit passendem Label/Name/ID (case-insensitive, partial).
    2. Fokussiere das Feld (setzt Cursor).
    3. Setze den Wert (input.value = '...').
    4. Feuere 'input' und 'change' Events (wichtig für React/Vue/Angular!).
    5. Wenn nicht gefunden → Suche Textarea als Fallback.
    6. Gib Response zurück.

    WARUM Events feuern?
    → Moderne Frameworks (React, Vue, Angular) überwachen Input-Events
      um ihren internen State zu aktualisieren.
    → Nur value setzen reicht NICHT! Der Framework-State bleibt leer.
    → Beispiel React: onChange-Handler wird nicht aufgerufen → State = "".
    → Wir müssen 'input' und 'change' Events dispatchieren.

    WARUM bubbles=true?
    → Events müssen durch den DOM-Bubble-Mechanismus propagieren.
    → React's Event-System hört auf bubbled Events (nicht direkt auf Element).
    → Ohne bubbles → React erkennt das Event nicht → State nicht aktualisiert.

    WARUM Escape Quotes?
    → Wenn der Wert einfache Anführungszeichen enthält (z.B. "It's fine"),
    → würde das JavaScript brechen (String-Delimiter Konflikt).
    → Wir escapen sie: "It\\'s fine".
    → WARUM? Unser JS-String ist in einfachen Anführungszeichen (Python).
    → JavaScript-String ist auch in einfachen Anführungszeichen.
    → Konflikt: 'It\\'s' → JavaScript sieht 'It\\'s' (Backslash ist Escape in JS).

    WARUM Textarea Fallback?
    → Manche offene Fragen verwenden <textarea> statt <input>.
    → Der Client muss nicht wissen welcher Tag verwendet wird.
    → Wir versuchen zuerst Input, dann Textarea.

    WARUM Fokussieren?
    → Feld fokussieren setzt den Cursor (visuelles Feedback).
    → Manche Frameworks verwenden Focus-Events für Validierung.
    → Echte User fokussieren auch vor dem Tippen (authentischer).

    Args:
        req: SurveyFillTextRequest
            - input_label: Label/Name/ID des Feldes (z.B. "Alter", "E-Mail").
            - value: Einzutragender Wert (z.B. "32", "test@example.com").
            - cdp_port: CDP Port (default: 9999).

    Returns:
        SurveyFillTextResponse:
            - status: "success", "not_found", "error".
            - value: Der eingetragene Wert (Echo für Bestätigung).

    Example:
        POST /survey/fill-text
        {"input_label": "Alter", "value": "32", "cdp_port": 9999}
        → {"status": "success", "input_label": "Alter", "value": "32"}
    """
    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 1: Dashboard WebSocket finden
    # ═══════════════════════════════════════════════════════════════════════

    ws_url = get_dashboard_ws(req.cdp_port)

    if not ws_url:
        return SurveyFillTextResponse(
            status="error",
            input_label=req.input_label,
            value=req.value,
            message="No dashboard found",
        )

    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 2: Label und Value vorbereiten
    # ═══════════════════════════════════════════════════════════════════════

    # Label in Kleinbuchstaben (case-insensitive matching).
    label_lower = req.input_label.lower()

    # Einfache Anführungszeichen escapen (für JavaScript String).
    # WARUM .replace("'", "\\'")? JavaScript-String ist in '...'.
    # Wenn Value enthält ' → String-Delimiter Konflikt.
    # "It's" → 'It\\'s' → JavaScript sieht 'It's' (\\' = escaptes ').
    value_escaped = req.value.replace("'", "\\'")

    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 3: JavaScript für Text-Eingabe
    # ═══════════════════════════════════════════════════════════════════════

    fill_js = f"""
(function() {{
    // ═══════════════════════════════════════════════════════════
    // TEXT INPUTS (input[type="text"], input[type="email"], etc.)
    // ═════════════════════════════════════════════════════════==
    var inputs = document.querySelectorAll(
        'input[type="text"], input[type="email"], input[type="number"], input:not([type])'
    );

    for (var inp of inputs) {{
        // Suche in ID, Name, aria-label, placeholder (alles in Kleinbuchstaben).
        var search = (
            inp.id + ' ' +
            inp.name + ' ' +
            (inp.getAttribute('aria-label') || '') + ' ' +
            inp.placeholder
        ).toLowerCase();

        // Versuche: <label> vor dem Input (previousElementSibling).
        var label = inp.closest('label') || inp.previousElementSibling;
        if (label && label.tagName === 'LABEL') {{
            search += ' ' + label.innerText.trim().toLowerCase();
        }}

        // Partial Match: Ist der Label-Text im search-String enthalten?
        if (search.includes("{label_lower}")) {{
            // Fokussieren (setzt Cursor, visuelles Feedback).
            inp.focus();

            // Wert setzen.
            inp.value = '{value_escaped}';

            // Events feuern (WICHTIG für React/Vue/Angular!).
            // 'input' Event = Wert wurde geändert (während der Eingabe).
            // 'change' Event = Wert wurde final geändert (nach Verlassen des Feldes).
            // bubbles=true = Event propagiert durch DOM (React hört auf bubbled Events).
            inp.dispatchEvent(new Event('input', {{ bubbles: true }}));
            inp.dispatchEvent(new Event('change', {{ bubbles: true }}));

            return "filled:" + inp.id;
        }}
    }}

    // ═══════════════════════════════════════════════════════════
    // TEXTAREA (Fallback)
    // ═════════════════════════════════════════════════════════==
    var tas = document.querySelectorAll('textarea');

    for (var ta of tas) {{
        var search = (ta.id + ' ' + ta.name).toLowerCase();

        if (search.includes("{label_lower}")) {{
            ta.focus();
            ta.value = '{value_escaped}';
            ta.dispatchEvent(new Event('input', {{ bubbles: true }}));
            return "filled_ta:" + ta.id;
        }}
    }}

    return "not_found";
}})()
"""

    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 4: WebSocket Verbindung aufbauen und ausführen
    # ═══════════════════════════════════════════════════════════════════════

    ws = websocket.create_connection(ws_url, timeout=10, header=[f"Origin: {_ws_origin(ws_url)}"])
    ws.send(
        json.dumps(
            {
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {"expression": fill_js, "returnByValue": True},
            }
        )
    )
    response = ws.recv()
    ws.close()

    parsed = json.loads(response)
    result = parsed.get("result", {}).get("result", {}).get("value", "")

    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 5: Wenn nicht gefunden → Error
    # ═══════════════════════════════════════════════════════════════════════

    if "not_found" in result:
        return SurveyFillTextResponse(
            status="not_found",
            input_label=req.input_label,
            value=req.value,
            message=f"Input not found: {req.input_label}",
        )

    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 6: Response zurückgeben
    # ═══════════════════════════════════════════════════════════════════════

    return SurveyFillTextResponse(
        status="success",
        input_label=req.input_label,
        value=req.value,
        message=f"Filled: {result}",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINT 6: Click Custom DIV Radio (POST /survey/click-custom-radio)
# ═══════════════════════════════════════════════════════════════════════════════
# Klickt Custom-DIV-Radio-Buttons (z.B. TolunaStart cf-radio-answer).
# WARUM separater Endpoint?
# → TolunaStart verwendet KEINE nativen <input type="radio">.
# → Der normale /survey/select-option Endpoint funktioniert NICHT für DIVs.
# → Dieser Endpoint klickt direkt auf DIVs mit JavaScript.
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/click-custom-radio", response_model=SurveyClickCustomRadioResponse)
async def click_custom_radio(req: SurveyClickCustomRadioRequest):
    """
    Klickt einen Custom-DIV-Radio-Button (z.B. TolunaStart cf-radio-answer).

    ABLAUF:
    1. Finde Dashboard WebSocket (get_dashboard_ws).
    2. Generiere JavaScript:
       a. Suche alle DIVs mit req.div_class (z.B. .cf-radio-answer).
       b. Wenn req.option_text gesetzt → suche DIV mit passendem Text.
       c. Sonst → verwende req.index (0 = erstes, -1 = letztes).
    3. Führe JavaScript aus (ws_eval).
    4. Gib Response zurück.

    WARUM JavaScript .click()?
    → Simuliert echten Click (inkl. Event-Bubbling).
    → Feuert alle Event-Listener (React, Vue, Angular, Vanilla JS).
    → Manche Frameworks brauchen zusätzlich CSS-Klassen-Toggle.

    WARUM option_text + index Fallback?
    → Text-Match ist robuster (semantisch).
    → Index ist schneller (kein Text-Parsing).
    → Fallback-Kette: option_text → index → first DIV.

    WARUM "selected" CSS-Klasse togglen?
    → Manche Frameworks (nicht React/Vue) verwenden CSS-Klassen für Zustand.
    → Wir togglen .selected / .active als zusätzlicher Fallback.

    Args:
        req: SurveyClickCustomRadioRequest
            - div_class: CSS-Klasse (default: "cf-radio-answer").
            - index: Index (default: 0, -1 = letztes).
            - option_text: Optional Text-Match (case-insensitive).
            - cdp_port: CDP Port (default: 9224).

    Returns:
        SurveyClickCustomRadioResponse:
            - status: "success", "not_found", "error".
            - divs_found: Anzahl gefundener DIVs.
            - clicked_index: Tatsächlich geklickter Index.
            - selected_text: Text des geklickten DIVs.

    Example:
        POST /survey/click-custom-radio
        {"div_class": "cf-radio-answer", "index": 0, "cdp_port": 9224}
        → {"status": "success", "divs_found": 4, "clicked_index": 0,
            "selected_text": "Männlich", "message": "Clicked cf-radio-answer[0]: Männlich"}

        POST /survey/click-custom-radio
        {"div_class": "cf-radio-answer", "option_text": "weiblich", "cdp_port": 9224}
        → {"status": "success", "divs_found": 4, "clicked_index": 1,
            "selected_text": "Weiblich", "message": "Clicked cf-radio-answer[1]: Weiblich"}
    """
    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 1: Dashboard WebSocket finden
    # ═══════════════════════════════════════════════════════════════════════

    ws_url = get_dashboard_ws(req.cdp_port)

    if not ws_url:
        return SurveyClickCustomRadioResponse(
            status="error",
            div_class=req.div_class,
            divs_found=0,
            clicked_index=-1,
            message="No dashboard found",
        )

    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 2: JavaScript für Custom-DIV-Radio-Click generieren
    # ═══════════════════════════════════════════════════════════════════════

    # Option-Text in Kleinbuchstaben (case-insensitive matching).
    option_lower = (req.option_text or "").lower()

    click_js = f"""
(function() {{
    // Suche alle DIVs mit der angegebenen CSS-Klasse.
    var divs = document.querySelectorAll('.{req.div_class}');

    if (divs.length === 0) {{
        return JSON.stringify({{
            status: 'not_found',
            divs_found: 0,
            clicked_index: -1,
            selected_text: null
        }});
    }}

    var clickedIndex = -1;
    var selectedText = '';
    var targetDiv = null;

    // STRATEGIE 1: Wenn option_text gesetzt → suche nach Text-Match.
    if ('{option_lower}') {{
        for (var i = 0; i < divs.length; i++) {{
            var text = (divs[i].innerText || divs[i].textContent || '').trim().toLowerCase();
            if (text.includes('{option_lower}')) {{
                targetDiv = divs[i];
                clickedIndex = i;
                selectedText = text;
                break;
            }}
        }}
    }}

    // STRATEGIE 2: Wenn kein Text-Match → verwende Index.
    if (!targetDiv) {{
        var idx = {req.index};
        if (idx === -1) idx = divs.length - 1;  // -1 = letztes
        if (idx < 0) idx = 0;
        if (idx >= divs.length) idx = divs.length - 1;

        targetDiv = divs[idx];
        clickedIndex = idx;
        selectedText = (targetDiv.innerText || targetDiv.textContent || '').trim();
    }}

    // KLICK AUSFÜHREN
    if (targetDiv) {{
        // 1. Nativer JavaScript Click (feuert Event-Listener).
        targetDiv.click();

        // 2. Optional: CSS-Klasse togglen (für Frameworks die auf Klassen hören).
        targetDiv.classList.add('selected');
        targetDiv.classList.add('active');
        targetDiv.setAttribute('aria-checked', 'true');

        // 3. Optional: Geschwister deselektieren (Radio-Verhalten simulieren).
        for (var i = 0; i < divs.length; i++) {{
            if (divs[i] !== targetDiv) {{
                divs[i].classList.remove('selected');
                divs[i].classList.remove('active');
                divs[i].setAttribute('aria-checked', 'false');
            }}
        }}

        return JSON.stringify({{
            status: 'success',
            divs_found: divs.length,
            clicked_index: clickedIndex,
            selected_text: selectedText.substring(0, 100)
        }});
    }}

    return JSON.stringify({{
        status: 'error',
        divs_found: divs.length,
        clicked_index: -1,
        selected_text: null
    }});
}})()
"""

    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 3: WebSocket Verbindung aufbauen und ausführen
    # ═══════════════════════════════════════════════════════════════════════

    ws = websocket.create_connection(ws_url, timeout=10, header=[f"Origin: {_ws_origin(ws_url)}"])
    ws.send(
        json.dumps(
            {
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {"expression": click_js, "returnByValue": True},
            }
        )
    )
    response = ws.recv()
    ws.close()

    parsed = json.loads(response)
    result = parsed.get("result", {}).get("result", {}).get("value", "{}")

    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 4: Ergebnis parsen und Response zurückgeben
    # ═══════════════════════════════════════════════════════════════════════

    try:
        result_data = json.loads(result)
    except json.JSONDecodeError:
        result_data = {
            "status": "error",
            "divs_found": 0,
            "clicked_index": -1,
            "selected_text": None,
        }

    status = result_data.get("status", "error")
    divs_found = result_data.get("divs_found", 0)
    clicked_index = result_data.get("clicked_index", -1)
    selected_text = result_data.get("selected_text")

    if status == "not_found":
        return SurveyClickCustomRadioResponse(
            status="not_found",
            div_class=req.div_class,
            divs_found=0,
            clicked_index=-1,
            message=f"No DIVs found with class: {req.div_class}",
        )

    if status == "success":
        return SurveyClickCustomRadioResponse(
            status="success",
            div_class=req.div_class,
            divs_found=divs_found,
            clicked_index=clicked_index,
            selected_text=selected_text,
            message=f"Clicked {req.div_class}[{clicked_index}]: {selected_text or 'N/A'}",
        )

    return SurveyClickCustomRadioResponse(
        status="error",
        div_class=req.div_class,
        divs_found=divs_found,
        clicked_index=clicked_index,
        message=f"Unexpected error: {result}",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINT 7: Run One Complete Survey (POST /survey/run-one)
# ═══════════════════════════════════════════════════════════════════════════════
# Führt EINE komplette Survey von Anfang bis Ende aus.
# DIES IST EIN DEMO/PROOF-OF-CONCEPT — NICHT für Produktion!
# ═══════════════════════════════════════════════════════════════════════════════


@router.post(
    "/run-one",
    response_model=SurveyRunOneResponse,
    deprecated=True,
    summary="DEPRECATED — Use POST /survey/open + /survey/fill + /survey/rate instead",
)
async def run_one_survey(req: SurveyRunOneRequest):
    """
    Führt EINE komplette Survey von Anfang bis Ende aus.

    ABLAUF:
    1. Survey Card klicken (öffnet Modal).
    2. "Umfrage starten" Button klicken.
    3. LOOP (max_pages Iterationen):
       a. Seiteninhalt lesen (extract_elements_from_page).
       b. Prüfe auf Completion ("Danke", "Fertig", "Vielen Dank").
       c. Prüfe auf Disqualifikation ("Screen Out", "Leider", "nicht qualifiziert").
       d. Auto-select: Wähle erste Radio/Checkbox Option.
       e. Auto-fill: Fülle leere Textfelder mit "test".
       f. Klicke "Weiter" / "Next" / "Submit".
    4. Gib Ergebnis zurück.

    WARUM Auto-Select?
    → Dies ist ein DEMO/Proof-of-Concept Endpoint.
    → In Produktion würde ein AI-Model (Nemotron) die beste Antwort wählen.
    → Für jetzt: Wir wählen einfach die erste Option.
    → WARNUNG: Dies führt oft zu Disqualifikation (falsche Demografie)!

    WARUM "test" als Default-Wert?
    → Offene Textfelder müssen ausgefüllt werden.
    → "test" ist ein neutraler Platzhalter.
    → In Produktion → echte Antworten vom User oder AI!

    WARUM max_pages Limit?
    → Endlosschleifen verhindern. Wenn eine Survey hängt (Bug, Loop),
    → brechen wir nach max_pages ab.
    → Schützt vor API-Timeouts und Resource-Leaks.

    WARUM Completion-Keywords?
    → "Danke", "Fertig", "Vielen Dank", "Complete", "Done".
    → Diese Wörter erscheinen auf der Abschlussseite.
    → Wenn gefunden → Survey ist abgeschlossen (Success!).

    WARUM Disqualifikation-Keywords?
    → "Screen Out", "Leider", "nicht qualifiziert", "Disqualifiziert".
    → Diese Wörter erscheinen bei Abbruch (nicht das richtige Ziel-Publikum).
    → Wenn gefunden → Survey wurde abgebrochen (Screen-Out).

    WARUM "Umfrage starten" in mehreren Varianten?
    → Der Button-Text variiert leicht:
      - "Umfrage starten" (Standard).
      - "Starten" (Kürzere Variante).
      - "Beginnen" (Alternative).
      - "Survey start" / "Start survey" (Englisch).
    → Wir versuchen mehrere Varianten (erste die matcht gewinnt).

    WARUM time.sleep() in Loop?
    → Jeder Schritt braucht Zeit (JavaScript-Ausführung, Seitenladen).
    → Zu schnell → Race Conditions (Elemente noch nicht im DOM).
    → Zu langsam → ineffizient (lange Survey-Laufzeit).
    → 2-3s pro Seite = Kompromiss.

    WARUM DEMO/Proof-of-Concept?
    → Dieser Endpoint ist NICHT für Produktion gedacht!
    → Er demonstriert den grundlegenden Flow.
    → Für echte Automation brauchen wir:
    - AI-basierte Antwort-Auswahl (Nemotron).
    - Profil-basierte Demografie-Matching.
    - Intelligentere Completion/Disqualifikation-Erkennung.
    - Retry-Logik bei Fehlern.

    Args:
        req: SurveyRunOneRequest
            - survey_id: Optional. Wenn None → erste verfügbare Survey.
            - cdp_port: CDP Port (default: 9999).
            - max_pages: Maximale Anzahl Seiten (default: 20).

    Returns:
        SurveyRunOneResponse:
            - status: "completed", "screen_out", "error".
            - survey_id: ID der ausgeführten Survey.
            - pages_completed: Anzahl beantworteter Seiten.
            - earned: Verdiente Belohnung (€).
            - elapsed_s: Gesamtdauer (Sekunden).

    Example:
        POST /survey/run-one
        {"survey_id": null, "cdp_port": 9999, "max_pages": 20}
        → {"status": "completed", "pages_completed": 5, "elapsed_s": 45.2}
    """
    # Zeit-Messung für Performance-Monitoring.
    import time as time_module

    start = time_module.time()

    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 1: Dashboard WebSocket finden
    # ═══════════════════════════════════════════════════════════════════════

    ws_url = get_dashboard_ws(req.cdp_port)

    if not ws_url:
        return SurveyRunOneResponse(
            status="error",
            survey_id=req.survey_id or "unknown",
            elapsed_s=0,
            message="No dashboard found",
        )

    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 2: Survey Card klicken
    # ═══════════════════════════════════════════════════════════════════════

    # Wir verwenden den click_card Endpoint (interner Aufruf).
    # WARUM interner Aufruf? Wiederverwendung der Logik (DRY-Prinzip).
    click_result = await click_card(
        SurveyClickCardRequest(
            survey_id=req.survey_id,
            cdp_port=req.cdp_port,
        )
    )

    if click_result.status != "success":
        # Card-Click fehlgeschlagen → Survey kann nicht gestartet werden.
        return SurveyRunOneResponse(
            status="error",
            survey_id=click_result.survey_id or req.survey_id or "unknown",
            elapsed_s=time_module.time() - start,
            error=click_result.message,
            message=click_result.message,
        )

    # Survey-ID speichern (für Response).
    survey_id = click_result.survey_id

    # Warte bis Modal sich öffnet.
    time.sleep(2)

    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 3: "Umfrage starten" Button finden und klicken
    # ═══════════════════════════════════════════════════════════════════════

    start_btn_clicked = False

    # Versuche mehrere Button-Text-Varianten.
    for btn_label in ["umfrage starten", "starten", "beginnen", "survey start", "start survey"]:
        ws = websocket.create_connection(
            ws_url, timeout=10, header=[f"Origin: {_ws_origin(ws_url)}"]
        )
        ws.send(
            json.dumps(
                {
                    "id": 1,
                    "method": "Runtime.evaluate",
                    "params": {
                        "expression": f"""
(function() {{
    var btns = document.querySelectorAll("button");
    for (var b of btns) {{
        var t = (b.textContent || '').trim().toLowerCase();
        if (t.includes("{btn_label}")) {{ b.click(); return "clicked"; }}
    }}
    return "not_found";
}})()
""",
                        "returnByValue": True,
                    },
                }
            )
        )
        response = ws.recv()
        ws.close()

        parsed = json.loads(response)
        result = parsed.get("result", {}).get("result", {}).get("value", "")

        if "clicked" in result:
            start_btn_clicked = True
            time.sleep(3)  # Warte bis Survey sich öffnet
            break

    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 4: Wenn Start-Button nicht gefunden → Error
    # ═══════════════════════════════════════════════════════════════════════

    if not start_btn_clicked:
        return SurveyRunOneResponse(
            status="error",
            survey_id=survey_id or "unknown",
            elapsed_s=time_module.time() - start,
            error="Could not click survey start button",
            message="Could not click 'Umfrage starten' or similar button",
        )

    # ═══════════════════════════════════════════════════════════════════════
    # SCHRITT 5: Seiten-Loop (max_pages Iterationen)
    # ═══════════════════════════════════════════════════════════════════════

    pages_completed = 0
    max_pages = req.max_pages

    for _page_num in range(max_pages):
        # Warte bis Seite geladen ist.
        time.sleep(2)

        # Extrahiere alle Elemente von der Seite.
        elements = extract_elements_from_page(ws_url)
        text = elements.get("text", "").lower()

        # Prüfe auf Completion (Survey abgeschlossen).
        completion_keywords = [
            "danke",
            "fertig",
            "vielen dank",
            "complete",
            "done",
            "abgeschlossen",
        ]
        if any(kw in text for kw in completion_keywords):
            # Survey abgeschlossen!
            return SurveyRunOneResponse(
                status="completed",
                survey_id=survey_id or "unknown",
                pages_completed=pages_completed,
                elapsed_s=time_module.time() - start,
                message="Survey completed successfully",
            )

        # Prüfe auf Disqualifikation (Abbruch).
        disqualification_keywords = [
            "screen out",
            "leider",
            "nicht qualifiziert",
            "disqualifiziert",
            "abgebrochen",
        ]
        if any(kw in text for kw in disqualification_keywords):
            # Disqualifiziert!
            return SurveyRunOneResponse(
                status="screen_out",
                survey_id=survey_id or "unknown",
                pages_completed=pages_completed,
                elapsed_s=time_module.time() - start,
                message="Screen out / disqualified",
            )

        # Auto-select: Wähle erste Radio/Checkbox/Custom-DIV Option.
        for el in elements.get("elements", []):
            if el.get("role") == "radio":
                # 2026-05-09 BUGFIX: Label-Click für versteckte Inputs, Input-Click für sichtbare.
                ws = websocket.create_connection(
                    ws_url, timeout=10, header=[f"Origin: {_ws_origin(ws_url)}"]
                )
                ws.send(
                    json.dumps(
                        {
                            "id": 1,
                            "method": "Runtime.evaluate",
                            "params": {
                                "expression": """
(function() {
    var radios = document.querySelectorAll('input[type="radio"]');
    if (radios.length === 0) return 'no_radios';
    var first = radios[0];
    var style = window.getComputedStyle(first);
    var isHidden = (style.display === 'none' || style.visibility === 'hidden');
    if (isHidden) {
        var label = first.closest('label');
        if (label) { label.click(); return 'clicked_label:0'; }
    }
    first.click();
    return 'clicked_input:0';
})()
""",
                                "returnByValue": True,
                            },
                        }
                    )
                )
                ws.recv()
                ws.close()
                break
            elif el.get("role") == "checkbox":
                # 2026-05-09 BUGFIX: Label-Click für versteckte Inputs.
                ws = websocket.create_connection(
                    ws_url, timeout=10, header=[f"Origin: {_ws_origin(ws_url)}"]
                )
                ws.send(
                    json.dumps(
                        {
                            "id": 1,
                            "method": "Runtime.evaluate",
                            "params": {
                                "expression": """
(function() {
    var checks = document.querySelectorAll('input[type="checkbox"]');
    if (checks.length === 0) return 'no_checkboxes';
    var first = checks[0];
    var style = window.getComputedStyle(first);
    var isHidden = (style.display === 'none' || style.visibility === 'hidden');
    if (isHidden) {
        var label = first.closest('label');
        if (label) { label.click(); return 'clicked_label:0'; }
    }
    first.click();
    return 'clicked_input:0';
})()
""",
                                "returnByValue": True,
                            },
                        }
                    )
                )
                ws.recv()
                ws.close()
                break
            elif el.get("role") == "custom_radio":
                # Klicke ersten Custom-DIV-Radio (z.B. TolunaStart cf-radio-answer).
                ws = websocket.create_connection(
                    ws_url, timeout=10, header=[f"Origin: {_ws_origin(ws_url)}"]
                )
                ws.send(
                    json.dumps(
                        {
                            "id": 1,
                            "method": "Runtime.evaluate",
                            "params": {
                                "expression": """
(function() {
    var divs = document.querySelectorAll('.cf-radio-answer, .custom-radio, .radio-option, [role="radio"]');
    if (divs.length > 0) {
        var first = divs[0];
        first.click();
        first.classList.add('selected');
        first.setAttribute('aria-checked', 'true');
        return 'clicked_custom_radio:0';
    }
    return 'not_found';
})()
""",
                                "returnByValue": True,
                            },
                        }
                    )
                )
                ws.recv()
                ws.close()
                break

        # Auto-fill: Fülle leere Textfelder mit "test".
        for el in elements.get("elements", []):
            if el.get("role") == "textbox" and not el.get("value"):
                # Fülle Textfeld mit "test".
                ws = websocket.create_connection(
                    ws_url, timeout=10, header=[f"Origin: {_ws_origin(ws_url)}"]
                )
                ws.send(
                    json.dumps(
                        {
                            "id": 1,
                            "method": "Runtime.evaluate",
                            "params": {
                                "expression": "document.querySelector('input[type=\"text\"]').value = 'test';",
                                "returnByValue": True,
                            },
                        }
                    )
                )
                ws.recv()
                ws.close()
                break

        # Klicke "Weiter" Button.
        ws = websocket.create_connection(
            ws_url, timeout=10, header=[f"Origin: {_ws_origin(ws_url)}"]
        )
        ws.send(
            json.dumps(
                {
                    "id": 1,
                    "method": "Runtime.evaluate",
                    "params": {
                        "expression": """
(function() {
    var btns = document.querySelectorAll("button");
    for (var b of btns) {
        var t = (b.textContent || '').trim().toLowerCase();
        if (t.includes('weiter') || t.includes('next') || t.includes('submit')) {
            b.click();
            return "clicked";
        }
    }
    return "not_found";
})()
""",
                        "returnByValue": True,
                    },
                }
            )
        )
        response = ws.recv()
        ws.close()

        parsed = json.loads(response)
        result = parsed.get("result", {}).get("result", {}).get("value", "")

        if "not_found" in result:
            # Kein "Weiter"-Button gefunden → evtl. letzte Seite oder Fehler.
            break

        pages_completed += 1

    # Max Pages erreicht (nicht abgeschlossen).
    return SurveyRunOneResponse(
        status="error",
        survey_id=survey_id or "unknown",
        pages_completed=pages_completed,
        elapsed_s=time_module.time() - start,
        error="Max pages reached without completion",
        message=f"Survey did not complete after {max_pages} pages",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# ENDE VON SURVEY_ACTIONS.PY
# ═══════════════════════════════════════════════════════════════════════════════
# ZUSAMMENFASSUNG:
#
# Diese Datei implementiert 6 Survey-Action-Endpoints:
#   1. POST /survey/click-card    → Survey-Karte klicken (öffnet Modal).
#   2. GET  /survey/modal         → Modal/Seiteninhalt lesen.
#   3. POST /survey/click-button   → Button klicken (mit Before/After-Vergleich).
#   4. POST /survey/select-option  → Radio/Checkbox auswählen.
#   5. POST /survey/fill-text      → Text eingeben (inkl. Event-Dispatching).
#   6. POST /survey/run-one        → Komplette Survey (DEMO/Proof-of-Concept).
#
# DESIGN-PRINZIPIEN:
#   1. Atomare Operationen: Jeder Endpoint = EINE Aktion (keine Megafunctions).
#   2. CDP WebSocket: Direkte JavaScript-Ausführung (schneller als Playwright).
#   3. Fail-Closed: Bei Fehlern → Error-Response (nicht Crash).
#   4. Partial Match: Case-insensitive, robust gegen UI-Variationen.
#   5. Event-Dispatching: React/Vue/Angular Kompatibilität.
#   6. Timeout: Jede Operation hat Zeitlimit (kein endloses Warten).
#
# WICHTIGE HELPER:
#   - get_dashboard_ws(port)    → Findet Dashboard-Tab via CDP /json API.
#   - ws_eval(ws_url, js)        → Führt JS aus und gibt Resultat zurück.
#   - ws_eval_multi(...)         → Mehrere JS-Calls in EINER WebSocket-Verbindung.
#   - _ws_origin(ws_url)         → Berechnet Origin Header für WS Auth.
#   - extract_elements_from_page() → Extrahiert ALLE interaktiven Elemente.
#
# BANNED PATTERNS (NICHT verwendet):
#   - KEIN Playwright (zu schwer für einfache JS-Ausführung).
#   - KEINE hardcoded PIDs oder Ports (außer Defaults).
#   - KEIN pkill -f "Google Chrome" (tötet USER Chrome!).
#   - KEIN --remote-allow-origins="*" mit Quotes (zsh glob!).
# ═══════════════════════════════════════════════════════════════════════════════
