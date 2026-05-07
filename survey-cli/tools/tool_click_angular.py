#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""================================================================================
TOOL: click_angular — CDP Mouse Events fuer Angular/React Frameworks
================================================================================

WAS IST DAS?
  Spezialisierter Klick-Tool fuer Frameworks (Angular, React, Vue), die
  native .click() ignorieren. Nutzt CDP dispatchMouseEvent mit echten
  Mouse-Events (move → press → release).

WARUM EXISTIERT DAS?
  Standard-CDP Runtime.evaluate("element.click()") funktioniert NICHT bei:
  - Angular: Event-Binding ueber Zone.js → click() feuert nicht Angular-ChangeDetection
  - React: Synthetic Events → click() bypassed React Event System
  - Qualtrics: Custom Event-Handler → click() wird ignoriert
  
  Loesung: Echte Mouse-Events via CDP Input.dispatchMouseEvent:
  - mouseMoved: Hover-Effekt triggern
  - mousePressed: Mousedown + event listeners feuern
  - mouseReleased: Mouseup + Click-Event generieren
  → Frameworks erkennen echte User-Interaktion.

ARCHITEKTUR:
  ┌─────────────────┐
  │  click_angular  │
  └─────────────────┘
         │
    ┌────┴────┬────────────┬────────────┐
    ▼         ▼            ▼            ▼
  by_index  by_selector  by_text    (CLI)
    │         │            │
    ▼         ▼            ▼
  queryAll  querySelector  Text-Match
    │         │            │
    ▼         ▼            ▼
  getBoundingClientRect() → Koordinaten
    │
    ▼
  CDP: dispatchMouseEvent(mouseMoved)
    │
    ▼
  CDP: dispatchMouseEvent(mousePressed)
    │
    ▼
  CDP: dispatchMouseEvent(mouseReleased)
    │
    ▼
  {"success": True, "coords": [x, y]}

BEREITS FUNKTIONIERT:
  ✓ PureSpectrum (Angular-basiert)
  ✓ CloudResearch (React-basiert)
  ✓ Qualtrics (Custom Event-Handler)
  ✓ TolunaStart (Vue.js)

BANNED METHODS — NIEMALS VERWENDEN (siehe /banned.md):
  ❌ playstealth launch
  ❌ webauto-nodriver
  ❌ cua-driver click (raw index)
  ❌ --remote-allow-origins=* (ohne Quotes)
  ❌ /tmp/heypiggy-bot (fixed profile)
  ❌ Hardcoded PIDs
  ❌ pkill -f "Google Chrome"
  ❌ killall Google Chrome
  ❌ skylight-cli click --element-index
================================================================================"""

import json       # CDP WebSocket Nachrichten (de)serialisierung
import time       # Sleep zwischen Mouse-Events (0.05s, 0.02s)
import websocket  # CDP WebSocket Verbindung
from typing import Optional, Dict, Any, Union

# ═════════════════════════════════════════════════════════════════════════════
# METADATEN
# ═════════════════════════════════════════════════════════════════════════════

__version__ = "1.0.0"   # Semantische Versionierung (Major.Minor.Patch)
__frozen__ = True       # 🔒 NICHT AENDERN! Getestet und verifiziert.
# → __frozen__ = True: Dieser Flow ist PRODUCTION-ready.
#   Aenderungen erfordern Neu-Testen mit allen Providern!


# ═════════════════════════════════════════════════════════════════════════════
# HAUPTFUNKTION: click()
# ═════════════════════════════════════════════════════════════════════════════
def click(
    ws_url: str,
    idx: Optional[int] = None,
    selector: Optional[str] = None,
    text: Optional[str] = None,
    timeout: int = 10
) -> Dict[str, Any]:
    """Klickt Element via CDP Mouse Events.
    
    ARGS:
        ws_url (str): CDP WebSocket URL (z.B. "ws://127.0.0.1:9999/devtools/page/...")
        idx (int): Index in querySelectorAll() — fuer geordnete Listen
        selector (str): CSS Selector — fuer direktes Element-Targeting
        text (str): Text-Inhalt — fuer Text-basiertes Matching
        timeout (int): WebSocket Timeout in Sekunden (default: 10)
        
    RETURNS:
        dict:
          {"success": True, "method": "cdp_mouse", "coords": [x, y]}
          {"success": False, "error": "Element not found"}
          {"success": False, "error": "idx, selector oder text required"}
          {"success": False, "error": "..."}  # Exception
          
    ALGORITHMUS:
      1. WebSocket-Verbindung aufbauen (ws_url)
      2. JavaScript ausfuehren (Runtime.evaluate):
         - Finde Element (idx/selector/text)
         - scrollIntoView() → Element sichtbar machen
         - getBoundingClientRect() → Koordinaten ermitteln
      3. CDP Mouse-Events senden:
         - mouseMoved: Hover (0.05s Pause)
         - mousePressed: Mousedown (0.02s Pause)
         - mouseReleased: Mouseup + Click
      4. WebSocket schliessen
      5. Ergebnis zurueckgeben
      
    WARUM 3 Mouse-Events?
      Echte User-Interaktion = move → press → release.
      - mouseMoved: Triggert Hover-Effekte (CSS :hover, Tooltips)
      - mousePressed: Triggert Mousedown-Listener (Focus, Active-States)
      - mouseReleased: Triggert Click-Event (Hauptaktion)
      → Alle 3 notwendig fuer Angular/React/Vue Event-Systeme.
      
    WARUM scrollIntoView({behavior: 'instant'})?
      Element muss im Viewport sein fuer Koordinaten.
      - 'instant': Sofort, keine Animation (schneller, zuverlaessiger)
      - 'center': Element in Mitte des Viewports (nicht abgeschnitten)
      
    WARUM getBoundingClientRect() + width/2, height/2?
      Center-Click = zuverlaessiger als Ecke (Ecke kann abgeschnitten sein).
      → Element-Mitte = garantiert innerhalb des Elements.
      
    WARUM 0.05s + 0.02s Pausen?
      Echte User hat Pausen zwischen Mouse-Events.
      - Zu schnell (<10ms): Frameworks erkennen nicht als User-Event
      - Zu langsam (>500ms): Unnoetige Verzoegerung
      - 50ms + 20ms = sweet spot (getestet mit PureSpectrum, Qualtrics)
      
    WARUM returnByValue: True?
      Wir wollen das Ergebnis (Koordinaten) direkt zurueck, nicht
      ueber eine RemoteObject-Referenz. → Einfacher, schneller.
      
    WARUM idx/selector/text XOR?
      Nur EINE Methode zur Zeit. Mehrere = ambiguous.
      → Aufrufer muss sich entscheiden (explizit ist besser).
      
    RACE CONDITION:
      Element kann sich zwischen evaluate und click verschieben
      (z.B. Lazy-Loading, Animation). → Koordinaten veraltet.
      → Loesung: Kurze Pausen + scrollIntoView vorher.
      
    EXCEPTION HANDLING:
      websocket.create_connection kann fehlschlagen (Port nicht erreichbar).
      Runtime.evaluate kann fehlschlagen (Seite nicht geladen).
      dispatchMouseEvent kann fehlschlagen (Koordinaten ausserhalb Viewport).
      → Alles catched, WebSocket wird in finally geschlossen.
    """
    try:
        # Schritt 1: WebSocket-Verbindung aufbauen
        ws = websocket.create_connection(ws_url, timeout=timeout)
        # → timeout=10: Nicht zu lang warten (Agent-Loop blockiert sonst)
        # → ws_url: Muss gueltige CDP WebSocket URL sein
        #   Format: ws://127.0.0.1:<port>/devtools/page/<tab_id>
        
        # Schritt 2: JavaScript ausfuehren — Element finden + Koordinaten
        if idx is not None:
            # METHODE: by_index
            # → querySelectorAll() gibt NodeList, idx selektiert Element
            # → Funktioniert bei: Listen, Radios, Checkboxen, Buttons
            js = """
            (function() {
                var els = document.querySelectorAll(
                    'button, a, input, select, textarea, label, [role=button], ' +
                    '[role=checkbox], [role=radio], [onclick], .LabelWrapper, ' +
                    '.ChoiceStructure, .mat-radio-button, .mat-checkbox'
                );
                // QUERY: Alle interaktiven Elemente
                // → Selektoren decken: HTML5, ARIA, Angular Material, Qualtrics
                var el = els[%d];
                if (!el) return null;
                // scrollIntoView: Element sichtbar machen
                el.scrollIntoView({behavior: 'instant', block: 'center'});
                var r = el.getBoundingClientRect();
                // Center-Koordinaten: zuverlaessiger als Ecke
                return {x: r.left + r.width/2, y: r.top + r.height/2, tag: el.tagName};
            })();
            """ % idx
            
        elif selector:
            # METHODE: by_selector
            # → CSS Selector = direktes, schnelles Targeting
            # → Nutzen wenn Element eindeutig identifizierbar ist
            js = """
            (function() {
                var el = document.querySelector('%s');
                if (!el) return null;
                el.scrollIntoView({behavior: 'instant', block: 'center'});
                var r = el.getBoundingClientRect();
                return {x: r.left + r.width/2, y: r.top + r.height/2, tag: el.tagName};
            })();
            """ % selector
            # → WARNUNG: Kein Escaping des Selectors!
            #   Wenn Selector Sonderzeichen enthält (z.B. [data-id="foo"]),
            #   muss der Aufrufer escapen oder by_text/by_index nutzen.
            
        elif text:
            # METHODE: by_text
            # → Case-insensitive Text-Matching
            # → Nutzen wenn keine eindeutigen IDs/Classes vorhanden
            text_esc = text.replace("'", "\\'")  # Escape Single-Quotes in JS
            js = """
            (function() {
                var els = document.querySelectorAll('button, a, [role=button], label, span, div');
                for (var i = 0; i < els.length; i++) {
                    var t = (els[i].innerText || '').trim().toLowerCase();
                    // MATCH: Exakter Match ODER Contains
                    if (t === '%s'.toLowerCase() || t.includes('%s'.toLowerCase())) {
                        els[i].scrollIntoView({behavior: 'instant', block: 'center'});
                        var r = els[i].getBoundingClientRect();
                        return {x: r.left + r.width/2, y: r.top + r.height/2, tag: els[i].tagName};
                    }
                }
                return null;
            })();
            """ % (text_esc, text_esc)
            # → Doppelter Vergleich: exakt ODER contains
            #   "Weiter" matched sowohl "Weiter" als auch "Weiter >"
            #   → Tolerant fuer leichte UI-Variationen
            
        else:
            # KEINE Methode angegeben → Fehler
            ws.close()
            return {"success": False, "error": "idx, selector oder text required"}
        
        # Schritt 2b: Runtime.evaluate ausfuehren
        ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
            "params": {"expression": js, "returnByValue": True}}))
        resp = json.loads(ws.recv())
        coords = resp.get("result", {}).get("result", {}).get("value")
        # → returnByValue=True: Ergebnis direkt im value-Feld
        # → Struktur: {"result": {"result": {"value": {...}}}}
        #   (CDP verschachtelte Struktur)
        
        if not coords:
            # Element nicht gefunden → WebSocket schliessen, Fehler
            ws.close()
            return {"success": False, "error": "Element not found"}
        
        x, y = coords["x"], coords["y"]
        # → Koordinaten sind float (aus getBoundingClientRect)
        # → dispatchMouseEvent akzeptiert float → kein Runden noetig
        
        # Schritt 3a: Mouse Move (Hover)
        ws.send(json.dumps({"id": 2, "method": "Input.dispatchMouseEvent",
            "params": {"type": "mouseMoved", "x": x, "y": y}}))
        ws.recv()  # Antwort abwarten (wichtig fuer Reihenfolge!)
        time.sleep(0.05)
        # → mouseMoved: Kein Button, nur Position
        # → 0.05s: Kurze Pause fuer Hover-Effekte
        
        # Schritt 3b: Mouse Press (Mousedown)
        ws.send(json.dumps({"id": 3, "method": "Input.dispatchMouseEvent",
            "params": {"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1}}))
        ws.recv()
        time.sleep(0.02)
        # → mousePressed: Button="left", clickCount=1
        # → 0.02s: Kurze Pause zwischen press und release
        
        # Schritt 3c: Mouse Release (Mouseup + Click)
        ws.send(json.dumps({"id": 4, "method": "Input.dispatchMouseEvent",
            "params": {"type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1}}))
        ws.recv()
        # → mouseReleased: Schliesst Click-Event ab
        
        # Schritt 4: WebSocket schliessen
        ws.close()
        
        return {"success": True, "method": "cdp_mouse", "coords": [x, y]}
        # → coords: [x, y] als Array (einfacher fuer JSON/JS-Interop)
        
    except Exception as e:
        # EXCEPTION HANDLING
        # → WebSocket schliessen wenn geoeffnet (vermeidet Leaks)
        # → Fehlermeldung zurueckgeben (kein Crash)
        if 'ws' in dir() and ws:
            ws.close()
        return {"success": False, "error": str(e)}


# ═════════════════════════════════════════════════════════════════════════════
# CLI INTERFACE
# ═════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python tool_click_angular.py <ws_url> <idx|--selector=X|--text=X>")
        sys.exit(1)
        
    ws_url = sys.argv[1]
    arg = sys.argv[2]
    
    if arg.startswith("--selector="):
        # Selector-Modus: --selector=.NextButton
        r = click(ws_url, selector=arg.split("=", 1)[1])
    elif arg.startswith("--text="):
        # Text-Modus: --text=Weiter
        r = click(ws_url, text=arg.split("=", 1)[1])
    else:
        # Index-Modus: 42
        r = click(ws_url, idx=int(arg))
        
    print(json.dumps(r, indent=2))
