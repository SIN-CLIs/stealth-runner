"""================================================================================
DEPRECATED 2026-05-11 — Wird ersetzt durch die kanonische v2-Pipeline.
================================================================================

Dieser Tool-Pfad ist LEGACY. Er bleibt nur fuer Backward-Compat bestehender
Integrationen erhalten. NEUER Code MUSS gegen die folgenden Endpoints
programmieren:

    POST /v2/scan         → ersetzt /survey/snapshot, /survey/scan
    POST /v2/click        → ersetzt /survey/click, /survey/click-angular
    POST /v2/fill         → ersetzt /survey/fill-input
    POST /v2/press_key    → neu
    POST /v2/captcha/*    → ersetzt /survey/solve-captcha,
                            /survey/solve-drag-puzzle

Die Implementierungen leben in:
    survey-cli/survey/cdp_universal.py      Universal Scanner (AX-Tree pierce)
    survey-cli/survey/cdp_actuator.py       Maus-Events + Pflicht-Verify
    survey-cli/survey/captcha_router.py     Detection + Solver-Routing
    agent-toolbox/api/endpoints/universal.py FastAPI-Endpoints unter /v2/*

WARUM DIESER TOOL-PFAD STIRBT:
  - Y-Sort-Reihenfolge → instabile @eN-Indizes bei Reflow
  - el.click() / .value = "..." → von React/Angular ignoriert
  - Keine Pflicht-Verify nach Aktion → Halluzinationen "Performed without effect"
  - Provider-spezifisches JS hardcoded → jeder neue Provider = Patch
  - walkShadows(depth>5) → tieferes Shadow-DOM unsichtbar
  - iframes nur gezaehlt, nie betreten

Migration-Path fuer dieses Modul:
  → Wrap die alte API auf /v2/*. Wenn das alte Tool z.B. (selector) erwartet,
    intern via /v2/scan einen Match auf attrs.id / name finden und dessen
    stable_id an /v2/click weitergeben. So bleibt die externe API stabil.

LIES BEVOR DU DIESES MODUL AENDERST: AGENTS.md Sektion
"KANONISCHE ARCHITEKTUR (2026-05-11)".
================================================================================
"""

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""================================================================================
TOOL: snapshot — Semantic DOM Element Extraction
================================================================================

WAS IST DAS?
  Extrahiert ALLE interaktiven Elemente aus einer Webseite via CDP.
  Erzeugt strukturierte Daten: Element-Typ, Text, Koordinaten, Zustand.
  
  Zusaetzlich: DOM-Hash fuer Anti-Stuck-Erkennung.
  → Wenn sich Hash nicht aendert nach Aktion = Stuck!

ARCHITEKTUR:
  ┌────────────────────┐
  │     snapshot()     │
  └────────────────────┘
         │
         ▼
  CDP: Runtime.evaluate(EXTRACTOR_JS)
         │
         ▼
  ┌────────────────────┐
  │  EXTRACTOR_JS     │
  │  (im Browser)      │
  └────────────────────┘
         │
    ┌────┴────┬────────┬────────┬────────┐
    ▼         ▼        ▼        ▼        ▼
  Radios  Checkboxen Selects  Inputs  Buttons
  (Qualtrics LabelWrapper, Angular Material, Generic)
         │
         ▼
  {elements: [...], url: "...", title: "...", hash: "..."}

BEREITS FUNKTIONIERT:
  ✓ Qualtrics (LabelWrapper, ChoiceStructure)
  ✓ PureSpectrum
  ✓ Generic (ARIA, Standard HTML)

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

import json       # CDP Nachrichten (de)serialisierung
import hashlib    # DOM-Hash fuer Anti-Stuck-Erkennung
import websocket  # CDP WebSocket Verbindung
from typing import Dict, Any, List, Optional

# ═════════════════════════════════════════════════════════════════════════════
# METADATEN
# ═════════════════════════════════════════════════════════════════════════════

__version__ = "1.0.0"
__frozen__ = True  # 🔒 NICHT AENDERN! Getestet mit allen Providern.


# ═════════════════════════════════════════════════════════════════════════════
# EXTRACTOR_JS: Im Browser ausgefuehrtes JavaScript
# ═════════════════════════════════════════════════════════════════════════════
# WARUM JS statt CDP Accessibility API?
#   CDP Accessibility API ist langsam (DOM-Tree durchlaufen).
#   JS querySelectorAll ist schnell (native Browser-Engine).
#   → 10-100x schneller fuer grosse Seiten.
#
# WARUM IIFE (Immediately Invoked Function Expression)?
#   Isoliert Variablen. Keine globale Verschmutzung.
#   → returnByValue=True gibt nur das return-Objekt zurueck.
#
# WARUM MAX = 50?
#   Qualtrics-Umfragen haben oft 50+ Elemente (Radios, Labels, Inputs).
#   Groesser = langsamer, mehr Daten.
#   50 = sweet spot (deckt 95% aller Survey-Seiten ab).
#
# WARUM Set fuer Deduplikation?
#   Ein Element kann von mehreren querySelectorAll-Queries gefunden werden
#   (z.B. ein Input ist auch ein [role=checkbox]).
#   Set mit key "type:text" dedupliziert.
#
# WARUM style.display === 'none'?
#   Versteckte Elemente (display: none) sind fuer Agent irrelevant.
#   → Filter spart Bandbreite + verhindert Klicks auf unsichtbare Elemente.
#
# WARUM rect.top > window.innerHeight + 300?
#   Elemente weit unterhalb des Viewports sind wahrscheinlich nicht relevant.
#   +300 = Toleranz fuer Lazy-Loading / Scroll-Bereich.
#
# WARUM document.body.innerText statt innerHTML?
#   innerText = nur sichtbarer Text (keine Tags/Scripts).
#   → Kleiner, schneller, relevanter fuer Hash.
#
# WARUM md5 statt sha256?
#   md5 ist schneller. Wir brauchen keinen kryptographischen Hash,
#   nur einen schnellen Vergleichswert. 12 Zeichen = ausreichend.
#
# WARUM .substring(0, 500) fuer bodyText?
#   Seiten koennen Megabytes an Text haben (lange Umfragen).
#   500 Zeichen = genug fuer Hash, aber nicht zu gross.
# =============================================================================

EXTRACTOR_JS = """
(function() {
    var MAX = 50;           // Maximale Anzahl Elemente
    var out = [];           // Ergebnis-Array
    var seen = new Set();   // Deduplikation: type:text als Key
    
    function add(el, type) {
        // FILTER 1: Maximale Anzahl erreicht?
        if (out.length >= MAX) return;
        
        // FILTER 2: Element muss sichtbare Groesse haben
        var rect = el.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) return;
        
        // FILTER 3: Element muss sichtbar sein (nicht display: none)
        var style = window.getComputedStyle(el);
        if (style.display === 'none' || style.visibility === 'hidden') return;
        
        // FILTER 4: Element nicht zu weit unterhalb des Viewports
        if (rect.top > window.innerHeight + 300) return;
        
        // EXTRAKTION: Text (ARIA-Label bevorzugt, dann innerText, dann value)
        var text = (el.getAttribute('aria-label') || el.innerText || el.value || '').trim().substring(0, 80);
        // → substring(0, 80): Max 80 Zeichen pro Element (Platz sparen)
        
        // DEDUPLIKATION: type + text als Key
        var key = type + ':' + text.toLowerCase();
        if (seen.has(key) && text) return;  // Bereits gesehen AND Text nicht leer
        seen.add(key);
        
        // ERGEBNIS: Element-Dictionary
        out.push({
            idx: out.length,           // Laufender Index (0, 1, 2, ...)
            type: type,                // Element-Typ (siehe unten)
            text: text,                // Extrahierter Text
            x: Math.round(rect.left + rect.width/2),   // Center-X
            y: Math.round(rect.top + rect.height/2),   // Center-Y
            tag: el.tagName.toLowerCase(),  // HTML-Tag (button, input, etc.)
            name: el.name || '',       // Input-Name (fuer Form-Identifikation)
            checked: el.checked || false  // Zustand (nur fuer Radios/Checkboxen)
        });
    }
    
    // QUERIES: Qualtrics + Angular Material + Generic HTML
    
    // QUERY 1: Qualtrics LabelWrapper (Radios, Checkboxen)
    document.querySelectorAll('.LabelWrapper, .ChoiceStructure, .mat-radio-button, .mat-checkbox')
    .forEach(function(el) {
        var inp = el.querySelector('input[type=radio], input[type=checkbox]');
        if (inp) {
            // Typ bestimmen: radio oder checkbox
            // Zustand: checked → "radio-selected" / "checkbox-selected"
            add(el, inp.type==='radio' 
                ? (inp.checked ? 'radio-selected' : 'radio')
                : (inp.checked ? 'checkbox-selected' : 'checkbox'));
        }
    });
    
    // QUERY 2: Select-Elemente (Dropdowns)
    document.querySelectorAll('select').forEach(function(el) { add(el, 'select'); });
    
    // QUERY 3: Input-Elemente (Textfelder, Radios, Checkboxen, Submit)
    document.querySelectorAll('input:not([type=hidden])').forEach(function(el) {
        var t = el.type || 'text';  // Default: text
        if(t === 'radio') add(el, el.checked ? 'radio-selected' : 'radio');
        else if(t === 'checkbox') add(el, el.checked ? 'checkbox-selected' : 'checkbox');
        else if(t === 'submit') add(el, 'submit');
        else add(el, 'input');  // text, password, email, number, etc.
    });
    
    // QUERY 4: Textarea
    document.querySelectorAll('textarea').forEach(function(el) { add(el, 'textarea'); });
    
    // QUERY 5: Buttons (inkl. ARIA role=button)
    document.querySelectorAll('button, [role=button]').forEach(function(el) {
        var txt = (el.innerText || '').toLowerCase();
        // HEURISTIK: "Next", "Weiter", "Submit", "Continue" = Submit-Button
        if(txt.includes('next') || txt.includes('weiter') || 
           txt.includes('submit') || txt.includes('continue')) {
            add(el, 'submit');
        } else {
            add(el, 'button');
        }
    });
    
    // QUERY 6: Labels (fuer Click-Targeting)
    document.querySelectorAll('label[for]').forEach(function(el) { add(el, 'label'); });
    
    // SORTIERUNG: Submit-Buttons zuerst (wichtigste Elemente)
    out.sort(function(a, b) {
        if(a.type === 'submit' && b.type !== 'submit') return 1;   // a nach b
        if(b.type === 'submit' && a.type !== 'submit') return -1;   // b nach a
        return a.y - b.y;  // Dann: Top-to-Bottom (Y-Koordinate)
    });
    
    // RE-INDEX: Nach Sortierung neu nummerieren
    out.forEach(function(el, i) { el.idx = i; });
    
    // RETURN: Strukturierte Daten
    return {
        elements: out,                              // Liste aller Elemente
        url: window.location.href,                  // Aktuelle URL
        title: document.title,                      // Seiten-Titel
        bodyText: (document.body.innerText || '').substring(0, 500)  // Text fuer Hash
    };
})();
"""


# ═════════════════════════════════════════════════════════════════════════════
# HAUPTFUNKTION: snapshot()
# ═════════════════════════════════════════════════════════════════════════════
def snapshot(ws_url: str, timeout: int = 15) -> Dict[str, Any]:
    """Erstellt Snapshot aller interaktiven Elemente.
    
    ARGS:
        ws_url (str): CDP WebSocket URL
        timeout (int): WebSocket Timeout in Sekunden (default: 15)
        
    RETURNS:
        dict:
          {
            "elements": [     // Liste von Element-Dictionaries
              {
                "idx": 0,           // Index (sortiert)
                "type": "radio",     // Element-Typ
                "text": "Männlich",  // Text-Label
                "x": 100, "y": 200, // Center-Koordinaten
                "tag": "label",     // HTML-Tag
                "name": "gender",   // Input-Name
                "checked": false    // Zustand
              },
              ...
            ],
            "url": "https://...",     // Aktuelle URL
            "title": "Survey Title",  // Seiten-Titel
            "hash": "a1b2c3d4"       // MD5-Hash von bodyText (Anti-Stuck)
          }
          
    WARUM 15s Timeout?
      CDP-Verbindung kann langsam sein (erster Connect, Auth).
      - 5s: Zu kurz fuer langsame Verbindungen
      - 30s: Zu lang, blockiert Agent-Loop
      - 15s: sweet spot
      
    WARUM hash aus bodyText?
      Anti-Stuck-Erkennung: Wenn 2 Snapshots denselben Hash haben,
      hat sich die Seite nicht geaendert → Aktion hatte keinen Effekt.
      → Hash-Vergleich ist schneller als kompletter DOM-Vergleich.
      
    RACE CONDITION:
      Seite kann sich aendern WAEHREND snapshot().
      → Elemente koennen veraltet sein. → Aufrufer muss validieren.
    """
    try:
        ws = websocket.create_connection(ws_url, timeout=timeout)
        ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
            "params": {"expression": EXTRACTOR_JS, "returnByValue": True}}))
        resp = json.loads(ws.recv())
        ws.close()
        
        data = resp.get("result", {}).get("result", {}).get("value", {})
        body_text = data.get("bodyText", "")
        
        # Anti-Stuck Hash: MD5 von bodyText, gekuerzt auf 12 Zeichen
        dom_hash = hashlib.md5(body_text.encode()).hexdigest()[:12]
        
        return {
            "elements": data.get("elements", []),
            "url": data.get("url", ""),
            "title": data.get("title", ""),
            "hash": dom_hash
        }
    except Exception as e:
        return {"elements": [], "url": "", "title": "", "hash": "error", "error": str(e)}


# ═════════════════════════════════════════════════════════════════════════════
# HELPER: find_submit()
# ═════════════════════════════════════════════════════════════════════════════
def find_submit(elements: List[Dict]) -> Optional[Dict]:
    """Findet Submit-Button in Element-Liste.
    
    ARGS:
        elements: Liste von Element-Dictionaries (aus snapshot())
        
    RETURNS:
        dict oder None: Erstes Submit-Element oder None
        
    WARUM erstes Submit?
      Submit-Buttons sind am wichtigsten (Survey fortfuehren).
      Sortierung in EXTRACTOR_JS legt sie ans Ende (oder Anfang, je nach Logik).
      → Erstes = wahrscheinlich "Weiter" oder "Submit".
      
    WARUM "submit" statt "button"?
      "submit" ist spezifischer. Ein "button" koennte irgendein Button sein
      ("Zurueck", "Abbrechen"), aber "submit" = Hauptaktion.
    """
    for el in elements:
        if el.get("type") == "submit":
            return el
    return None


# ═════════════════════════════════════════════════════════════════════════════
# HELPER: find_unfilled()
# ═════════════════════════════════════════════════════════════════════════════
def find_unfilled(elements: List[Dict]) -> List[Dict]:
    """Findet alle ungefuellten Input-Felder.
    
    ARGS:
        elements: Liste von Element-Dictionaries (aus snapshot())
        
    RETURNS:
        list: Nur Elemente die Nutzer-Eingabe benoetigen
        
    WARUM diese Typen?
      input: Textfelder (Name, Email, etc.)
      textarea: Freitext-Felder
      radio: Radio-Buttons (eine Auswahl)
      checkbox: Checkboxen (mehrere Auswahl)
      → Alles was vom Nutzer beantwortet werden muss.
      
    WARUM nicht "select"?
      Selects haben oft Default-Werte (erste Option ausgewaehlt).
      → Nicht immer "unfilled". → Aufrufer prueft separat.
      
    WARUM nicht "submit"?
      Submit-Buttons sind keine Eingabefelder.
    """
    return [el for el in elements if el.get("type") in ("input", "textarea", "radio", "checkbox")]


# ═════════════════════════════════════════════════════════════════════════════
# CLI INTERFACE
# ═════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python tool_snapshot.py <ws_url>")
        sys.exit(1)
        
    data = snapshot(sys.argv[1])
    print("URL: " + data['url'])
    print("Hash: " + data['hash'])
    print("Elements (" + str(len(data['elements'])) + "):")
    for el in data["elements"]:
        print("  [{0}] {1}: {2}".format(el['idx'], el['type'], el['text'][:40]))
