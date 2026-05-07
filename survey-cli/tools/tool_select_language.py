#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""================================================================================
TOOL: select_language — Language Selector for Qualtrics/CPX
================================================================================

WAS IST DAS?
  Wählt eine Sprache auf Qualtrics Language-Selection-Seiten.
  Unterstützt sowohl <select> Dropdowns als auch Radio-Buttons.

WARUM EXISTIERT DAS?
  Viele CPX-Surveys starten mit einer Sprachauswahl:
  "Bitte wählen Sie Ihre Sprache: [Deutsch] [English] [Français]"
  → Dieser Tool findet und selektiert die gewünschte Sprache automatisch.

ARCHITEKTUR:
  ┌──────────────────┐
  │ select_language()│
  └──────────────────┘
         │
    ┌────┴─────────────┐
    ▼                  ▼
  <select>           Radio Buttons
    │                  │
    ▼                  ▼
  Option-Match      LabelWrapper/
  selectedIndex=j   ChoiceStructure
    │                  │
    ▼                  ▼
  dispatchEvent      .click()
  ('change')         input.click()
    │                  │
    └────────┬─────────┘
             ▼
    Fallback: Full DOM Text-Match
             ▼
         return result

BEREITS FUNKTIONIERT:
  ✓ Qualtrics DE/EN Sprachauswahl
  ✓ CPX Language Selector

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
from typing import Dict, Any

__version__ = "1.0.0"
__frozen__ = True  # 🔒 NICHT AENDERN! Getestet mit Qualtrics Language Page.


def select_language(ws_url: str, language: str = "Deutsch", timeout: int = 10) -> Dict[str, Any]:
    """Wählt Sprache auf Language-Selection-Seite.
    
    ARGS:
        ws_url (str): CDP WebSocket URL
        language (str): Gewünschte Sprache (default: "Deutsch")
                        → Case-insensitive: "deutsch", "DEUTSCH", "Deutsch" = gleich
        timeout (int): WebSocket Timeout in Sekunden
        
    RETURNS:
        dict:
          {"success": true, "method": "select", "value": "Deutsch"}
            → Sprache via <select> Dropdown ausgewählt
          {"success": true, "method": "radio", "value": "deutsch"}
            → Sprache via Radio-Button ausgewählt
          {"success": true, "method": "text_match", "value": "deutsch"}
            → Sprache via Text-Matching (Fallback)
          {"success": false, "error": "Language not found: deutsch"}
            → Sprache nicht gefunden
            
    ALGORITHMUS:
      1. JavaScript IIFE erstellen (case-insensitive):
      2. METHODE 1: <select> Dropdown
         - Alle <select> Elemente durchlaufen
         - Jede Option prüfen: text.toLowerCase().includes(lang)
         - Match: selectedIndex = j, dispatchEvent('change')
         → return {success: true, method: 'select', value: option.text}
      3. METHODE 2: Radio Buttons
         - Container: .LabelWrapper, .ChoiceStructure, label, [role=radio],
           .mat-radio-button, .q-radio
         - Text innerhalb Container prüfen: includes(lang)
         - Click auf Container + click auf inneres <input type=radio>
         → return {success: true, method: 'radio', value: text.trim()}
      4. METHODE 3: Full DOM Text-Match (Fallback)
         - Alle Elemente durchlaufen
         - Blatt-Elemente (children.length === 0)
         - Text === lang OR includes(lang)
         - el.click()
         → return {success: true, method: 'text_match', value: t}
      5. KEIN Match → return {success: false, error: "Language not found: " + lang}
      
    WARUM 3 Methoden?
      Qualtrics nutzt verschiedene Sprachseiten-Implementierungen:
      - Alte: <select> Dropdown
      - Neue: Radio-Buttons (.LabelWrapper)
      - Spezial: Custom HTML (Text-Match)
      → Alle 3 abdecken = maximale Kompatibilität.
      
    WARUM toLowerCase()?
      "Deutsch" = "deutsch" = "DEUTSCH". Case-insensitive = tolerant.
      
    WARUM includes() statt ===?
      "Deutsch (German)" matched "deutsch" (includes).
      → Variationen abdecken (z.B. Sprach-Codes: "Deutsch [DE]").
      
    WARUM dispatchEvent('change') bei Select?
      Browser aktualisiert selectedIndex, ABER Frameworks (Angular/React)
      lauschen auf 'change' Event. Ohne dispatch = keine Framework-Update.
      
    WARUM doppelter click bei Radio?
      1. Container.click() → UI-Update (Label aktiviert)
      2. input.click() → Event-Feuerung (Framework-Listener)
      → Einzelner click auf Container reicht oft nicht fuer Frameworks.
      
    WARUM children.length === 0 bei Text-Match?
      Blatt-Elemente = reiner Text (keine verschachtelten Elemente).
      → Verhindert, dass Container-Text (der Kinder-Text enthaelt)
        doppelt matched wird.
      
    WARUM substring(0, 80) fuer Text?
      Max 80 Zeichen pro Element (Platz sparen in Snapshot).
    """
    # Case-insensitive: alles zu lowercase
    lang_lower = language.lower()
    
    # JavaScript: 3 Methoden (Select, Radio, Text-Match)
    js = """
    (function() {
        var lang = '%s';
        
        // METHODE 1: <select> Dropdown
        var selects = document.querySelectorAll('select');
        for (var i = 0; i < selects.length; i++) {
            var sel = selects[i];
            for (var j = 0; j < sel.options.length; j++) {
                if (sel.options[j].text.toLowerCase().includes(lang)) {
                    // Option gefunden → selektieren
                    sel.selectedIndex = j;
                    // Frameworks benachrichtigen (Angular/React)
                    sel.dispatchEvent(new Event('change', {bubbles: true}));
                    return {
                        success: true,
                        method: 'select',
                        value: sel.options[j].text
                    };
                }
            }
        }
        
        // METHODE 2: Radio Buttons (Qualtrics-Style)
        var containers = document.querySelectorAll(
            '.LabelWrapper, .ChoiceStructure, label, [role=radio], ' +
            '.mat-radio-button, .q-radio'
        );
        for (var i = 0; i < containers.length; i++) {
            var text = (containers[i].innerText || '').toLowerCase();
            if (text.includes(lang)) {
                // Container click (UI)
                containers[i].click();
                // Inneres Radio-Input click (Event)
                var inp = containers[i].querySelector('input[type=radio]');
                if (inp) inp.click();
                return {
                    success: true,
                    method: 'radio',
                    value: text.trim()
                };
            }
        }
        
        // METHODE 3: Full DOM Text-Match (Fallback)
        var all = document.querySelectorAll('*');
        for (var i = 0; i < all.length; i++) {
            var el = all[i];
            // Nur Blatt-Elemente (keine Kinder = reiner Text)
            if (el.children.length === 0) {
                var t = (el.innerText || '').toLowerCase().trim();
                if (t === lang || t.includes(lang)) {
                    el.click();
                    return {
                        success: true,
                        method: 'text_match',
                        value: t
                    };
                }
            }
        }
        
        // KEIN Match gefunden
        return {success: false, error: 'Language not found: ' + lang};
    })();
    """ % lang_lower  # lang_lower in JS einfügen
    
    try:
        ws = websocket.create_connection(ws_url, timeout=timeout)
        ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
            "params": {"expression": js, "returnByValue": True}}))
        resp = json.loads(ws.recv())
        ws.close()
        
        result = resp.get("result", {}).get("result", {}).get("value", {})
        return result if result else {"success": False, "error": "No result"}
        
    except Exception as e:
        return {"success": False, "error": str(e)}


# ═════════════════════════════════════════════════════════════════════════════
# CLI INTERFACE
# ═════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python tool_select_language.py <ws_url> [language]")
        sys.exit(1)
        
    ws_url = sys.argv[1]
    # Optional: Sprache als 2. Argument (default: "Deutsch")
    lang = sys.argv[2] if len(sys.argv) > 2 else "Deutsch"
    
    r = select_language(ws_url, lang)
    print(json.dumps(r, indent=2))
