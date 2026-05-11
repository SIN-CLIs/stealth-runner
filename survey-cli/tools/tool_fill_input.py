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
TOOL: fill_input — Input Field Filler with Validation Retry
================================================================================

WAS IST DAS?
  Füllt ein Input-Feld (Text, Textarea, Select) mit einem Wert und
  prüft auf Validierungsfehler. Wenn Validation fehlschlägt, versucht
  es automatisch mit einem Hinweis aus der Fehlermeldung (z.B. "muss
  zwischen 18 und 65 sein" → retry mit "25").

WARUM EXISTIERT DAS?
  Survey-Seiten haben Validierung (Alter, PLZ, E-Mail-Format).
  Einfaches .value = "X" reicht nicht — Frameworks validieren on-change.
  → Wir feuern Events (input, change, blur, keyup) und prüfen
    validationMessage. Bei Fehler: retry mit korrigiertem Wert.

ARCHITEKTUR:
  ┌──────────────────┐
  │    fill()        │
  └──────────────────┘
         │
         ▼
  ┌──────────────────┐
  │  Element finden  │ (by idx oder selector)
  └──────────────────┘
         │
         ▼
  ┌──────────────────┐
  │  scrollIntoView  │
  │  focus()         │
  │  value = ''      │ (clear)
  │  value = VALUE   │
  └──────────────────┘
         │
         ▼
  ┌──────────────────┐
  │  dispatchEvents  │ (input, change, blur, keyup)
  │  validationMsg   │ ← Prüfen
  └──────────────────┘
         │
    ┌────┴────────────┐
    ▼                 ▼
  success          validation error
    │                    │
    ▼                    ▼
  return            retry mit hint

BEREITS FUNKTIONIERT:
  ✓ Qualtrics (Number, Text, Email Validierung)
  ✓ PureSpectrum (Range-Validierung)

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
import websocket  # CDP WebSocket Verbindung
from typing import Dict, Any, Optional

__version__ = "1.0.0"
__frozen__ = True  # 🔒 NICHT AENDERN! Getestet mit Qualtrics Validierung.


def fill(
    ws_url: str,
    value: str,
    idx: Optional[int] = None,
    selector: Optional[str] = None,
    timeout: int = 10
) -> Dict[str, Any]:
    """Füllt Input-Feld mit Validierung und Auto-Retry.
    
    ARGS:
        ws_url (str): CDP WebSocket URL
        value (str): Wert zum Einfügen (z.B. "25", "Berlin", "email@domain.com")
        idx (int): Index in document.querySelectorAll('input, textarea, select')
                   → Wird genutzt wenn kein eindeutiger Selector vorhanden
        selector (str): CSS Selector zum direkten Finden des Elements
                        → Bevorzugt wenn eindeutig (z.B. "#age", "[name='zip']")
        timeout (int): WebSocket Timeout in Sekunden
        
    RETURNS:
        dict:
          {"success": True, "value": "25"}
            → Erfolgreich gefüllt und validiert
          {"success": True, "value": "25", "method": "hint_retry"}
            → Erst fehlgeschlagen, dann mit Hint retry erfolgreich
          {"success": False, "error": "validation", "validationMessage": "...", "hint": "..."}
            → Validierung fehlgeschlagen, kein retry möglich
          {"success": False, "error": "idx oder selector required"}
            → Weder idx noch selector angegeben
          {"success": False, "error": "Element not found"}
            → Element nicht im DOM
          {"success": False, "error": "No result"}
            → Kein Ergebnis von CDP
            
    ALGORITHMUS:
      1. Prüfen: idx ODER selector angegeben? → NEIN: Fehler
      2. JavaScript IIFE erstellen:
         - Element finden (by idx oder selector)
         - Nicht gefunden? → return {success: false, error: "Element not found"}
         - scrollIntoView({behavior: 'instant', block: 'center'})
           → Element muss sichtbar sein für Event-Feuerung
         - focus() → Focus für Keyboard-Events
         - value = '' → Clear (wichtig! Sonst append statt replace)
         - value = VALUE → Neuen Wert setzen
         - dispatchEvent(input, change, blur, keyup) → Frameworks benachrichtigen
           Angular/React/Vue hören auf diese Events für ChangeDetection
         - validationMessage prüfen → Browser-native Validierung
           z.B. "Bitte geben Sie eine Zahl zwischen 18 und 65 ein"
         - WENN validationMessage UND Regex "muss ... wie (\d+)" matcht:
           → return {success: false, error: "validation", hint: matched_number}
         - SONST: return {success: true, value: el.value}
      3. CDP Runtime.evaluate ausführen
      4. Ergebnis prüfen:
         - success: true → Return Erfolg
         - error == "validation" UND hint vorhanden:
           → Retry mit hint als neuem Wert!
           → Erstelle neues JS mit hint statt value
           → CDP Runtime.evaluate erneut
           → Ergebnis zurückgeben
      5. WebSocket schliessen
      
    WARUM value = '' vor value = VALUE?
      Ohne Clear: value = "25" auf "3" → "325" statt "25".
      → Append statt Replace.
      
    WARUM dispatchEvent(input, change, blur, keyup)?
      Frameworks validieren nicht bei direkter value-Zuweisung.
      - input → onInput (React controlled components)
      - change → onChange (Angular ngModel)
      - blur → onBlur (final validation)
      - keyup → onKeyUp (Debounced validation)
      → Alle 4 Events = maximale Kompatibilität.
      
    WARUM {bubbles: true}?
      Events müssen bubblen damit Framework-Listener sie fangen.
      → Ohne bubbles: Event wird nur auf Element gefeuert, nicht
        auf Parent-Container (wo Frameworks oft lauschen).
        
    WARUM Regex "muss .* wie (\d+)"?
      Deutsche Validierungsmeldungen enthalten oft Zahlen-Vorschlaege:
      "Bitte geben Sie eine Zahl zwischen 18 und 65 ein"
      → Regex matcht "65" als Hint → retry mit "65"
      
    WARUM returnByValue: True?
      Wir wollen das Ergebnis-Dictionary direkt, nicht als RemoteObject.
      
    WARUM json.dumps(value) fuer JS?
      value kann Sonderzeichen enthalten (Quotes, Zeilenumbrueche).
      json.dumps() escapt korrekt: " → \", \n → \n, etc.
      → Keine JS-Injection durch User-Werte.
      
    RACE CONDITION:
      Element kann zwischen evaluate und Event-Dispatch verschwinden
      (z.B. Animation, Lazy-Loading). → Exception catched, Fehler.
      
    EXCEPTION HANDLING:
      WebSocket-Fehler (Verbindung tot, Timeout) → catched, Fehler.
    """
    # Wert fuer JS escapen (JSON-Serialisierung verhindert Injection)
    value_json = json.dumps(value)
    
    # Schritt 1: Element-Selektor bestimmen
    if idx is not None:
        # METHODE: by_index
        # → querySelectorAll('input, textarea, select') gibt NodeList
        # → idx selektiert Element an Position
        # → WICHTIG: Nur interactive Elemente (keine hidden inputs)
        fill_sel = "document.querySelectorAll('input, textarea, select')[" + str(idx) + "]"
    elif selector:
        # METHODE: by_selector
        # → CSS Selector = direktes, schnelles Targeting
        # → Bevorzugt wenn eindeutig
        fill_sel = "document.querySelector('" + selector + "')"
    else:
        # KEINE Methode angegeben
        return {"success": False, "error": "idx oder selector required"}
    
    # JavaScript: Füllen + Validierung + Hint-Extraktion
    js = """
    (function() {
        // Element finden
        var el = %s;
        if (!el) return {success: false, error: 'Element not found'};
        
        // Element sichtbar machen (fuer Event-Feuerung)
        el.scrollIntoView({behavior: 'instant', block: 'center'});
        el.focus();  // Focus fuer Keyboard-Events
        
        // Clear + Set
        el.value = '';  // WICHTIG: Clear vorher!
        el.value = %s;  // Neuer Wert
        
        // Events feuern (Framework-Kompatibilität)
        ['input', 'change', 'blur', 'keyup'].forEach(function(evt) {
            // bubbles: true = Event bubbelt auf Parent
            el.dispatchEvent(new Event(evt, {bubbles: true}));
        });
        
        // Validierungsprüfung
        var vm = el.validationMessage || '';
        if (vm) {
            // Hint aus Validierungsmeldung extrahieren
            // Pattern: "muss ... wie (Zahl)" oder "between (Zahl) and (Zahl)"
            var hint = vm.match(/like\s+(\\d+)/i);
            return {
                success: false,
                error: 'validation',
                validationMessage: vm,
                hint: hint ? hint[1] : null
            };
        }
        
        // Erfolg
        return {success: true, value: el.value};
    })();
    """ % (fill_sel, value_json)
    
    try:
        # Schritt 2: CDP Verbindung aufbauen
        ws = websocket.create_connection(ws_url, timeout=timeout)
        
        # Schritt 3: Runtime.evaluate ausführen
        ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
            "params": {"expression": js, "returnByValue": True}}))
        resp = json.loads(ws.recv())
        
        # Ergebnis extrahieren
        result = resp.get("result", {}).get("result", {}).get("value", {})
        
        # Schritt 4: Retry mit Hint wenn Validation fehlgeschlagen
        if result.get("error") == "validation" and result.get("hint"):
            hint = result["hint"]
            hint_json = json.dumps(hint)  # Escapen fuer JS
            
            # Neues JS: value = hint statt original value
            retry_js = js.replace(value_json, hint_json)
            
            # Retry ausführen
            ws.send(json.dumps({"id": 2, "method": "Runtime.evaluate",
                "params": {"expression": retry_js, "returnByValue": True}}))
            retry_resp = json.loads(ws.recv())
            retry_result = retry_resp.get("result", {}).get("result", {}).get("value", {})
            
            if retry_result.get("success"):
                # Retry erfolgreich!
                ws.close()
                return {"success": True, "value": hint, "method": "hint_retry"}
            # Retry fehlgeschlagen → Original-Fehler zurückgeben
        
        # Schritt 5: WebSocket schliessen, Ergebnis zurückgeben
        ws.close()
        return result if result else {"success": False, "error": "No result"}
        
    except Exception as e:
        # Exception-Handling: WebSocket-Leaks verhindern
        return {"success": False, "error": str(e)}


# ═════════════════════════════════════════════════════════════════════════════
# CLI INTERFACE
# ═════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 4:
        print("Usage: python tool_fill_input.py <ws_url> <idx|--selector=X> <value>")
        sys.exit(1)
        
    ws_url = sys.argv[1]
    value = sys.argv[3]  # Wert ist letztes Argument
    
    if sys.argv[2].startswith("--selector="):
        # Selector-Modus: --selector=#age
        r = fill(ws_url, value, selector=sys.argv[2].split("=", 1)[1])
    else:
        # Index-Modus: 0
        r = fill(ws_url, value, idx=int(sys.argv[2]))
        
    print(json.dumps(r, indent=2))
