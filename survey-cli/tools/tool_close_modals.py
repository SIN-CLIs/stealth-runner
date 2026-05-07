#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""================================================================================
TOOL: close_modals — Modal/Overlay/Popup Closer
================================================================================

WAS IST DAS?
  Schliesst ALLE sichtbaren Modals, Overlays, Popups und Cookie-Banner.
  MUSS vor Survey-Start aufgerufen werden (Modals blockieren Interaktion!).

WARUM EXISTIERT DAS?
  Survey-Seiten (besonders bei CPX-Redirects) haben oft:
  - Cookie-Consent-Banner ("Akzeptieren" / "Ablehnen")
  - "Umfrage starten" Modals
  - Passwort-/Login-Overlays
  - Advertisement-Popups
  
  Diese blockieren ALLE Interaktionen. Wenn nicht geschlossen:
  → Klicks landen auf Modal statt Survey-Element.
  → Survey-Loop stuck.

ARCHITEKTUR:
  ┌──────────────────┐
  │  close_modals()  │
  └──────────────────┘
         │
    ┌────┴──────────────────────────────────────────┐
    ▼                  ▼                  ▼          ▼
  Close-Buttons    Overlays         Escape      Cookies
  (Text-Match)   (.click())      (KeyEvent)   (Accept/Reject)
    │               │               │            │
    └───────────────┴───────────────┴────────────┘
                    │
                    ▼
              return closed_count

STRATEGIEN (in Reihenfolge):
  1. Close-Buttons (Text-Match): "Schließen", "Close", "x", "X", "Ablehnen", "Dismiss", ...
  2. Overlays/Backdrops: .modal-backdrop, .overlay, [class*="backdrop"], [class*="overlay"]
  3. Escape-Taste: document.dispatchEvent(KeyboardEvent('keydown', {key:'Escape', keyCode:27}))
  4. Cookie-Banner: [class*="cookie"] button mit "accept" / "akzept" / "ablehnen" / "reject"

BEREITS FUNKTIONIERT:
  ✓ HeyPiggy Cookie-Banner
  ✓ Qualtrics "Umfrage starten" Modal
  ✓ PureSpectrum Overlays
  ✓ Generic Cookie-Consent

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

__version__ = "1.0.0"
__frozen__ = True  # 🔒 NICHT AENDERN! Getestet mit HeyPiggy + Qualtrics Modals.


# ═════════════════════════════════════════════════════════════════════════════
# KONSTANTEN: Close-Button-Texte
# ═════════════════════════════════════════════════════════════════════════════

# CLOSE_TEXTS: Bekannte Texte von Schliessen-Buttons
#   → WARUM so viele? Verschiedene Sprachen + Frameworks nutzen unterschiedliche Texte.
#   → WARUM Case-sensitive? "x" != "X" — manche Buttons nutzen kleines x als Icon.
CLOSE_TEXTS = [
    # Deutsch
    'Schließen',      # Standard
    'Close',          # Englisch (oft in DE-Seiten)
    'x',              # Kleines x (Icon)
    'X',              # Grosses X (Icon)
    'Ablehnen',       # Cookie-Banner
    'Dismiss',        # Englisch-Variante
    'Cancel',         # Abbruch
    'Abbrechen',      # Deutsch
    'No thanks',      # Englisch-Phrasen
    'Nein danke',
    'Nein',           # Einfaches Nein
    'No',
    'Spater',         # Später (ohne Umlaut-Ersatz)
    'Later',          # Englisch
    'Skip',           # Überspringen
    'Uberspringen'    # Deutsch
]


def close_modals(ws_url: str, timeout: int = 10) -> int:
    """Schliesst alle sichtbaren Modals/Overlays.
    
    ARGS:
        ws_url (str): CDP WebSocket URL
        timeout (int): WebSocket Timeout in Sekunden
        
    RETURNS:
        int: Anzahl der geschlossenen Elemente (0 = nichts gefunden)
        
    ALGORITHMUS:
      1. JavaScript IIFE ausführen:
         - STRATEGIE 1: Close-Buttons (Text-Match)
           → Alle button, span, div[role=button], a, [class*="close"] durchlaufen
           → Text oder aria-label prüfen gegen CLOSE_TEXTS
           → Match: el.click(), counter++
         - STRATEGIE 2: Overlays/Backdrops
           → .modal-backdrop, .overlay, [class*="backdrop"], [class*="overlay"]
           → Alle .click(), counter++
         - STRATEGIE 3: Escape-Taste
           → document.dispatchEvent(KeyboardEvent('keydown', {key:'Escape', keyCode:27}))
           → Simuliert Escape-Druck (schliesst viele Modals)
         - STRATEGIE 4: Cookie-Banner
           → [class*="cookie"] button
           → Text: "accept", "akzept", "ablehnen", "reject"
           → Match: el.click(), counter++
         - return closed_count
      2. WebSocket schliessen
      3. Counter zurückgeben
      
    WARUM 4 Strategien?
      Modals schliessen sich auf unterschiedliche Weise:
      - Button-Click (STRATEGIE 1)
      - Overlay-Click ausserhalb (STRATEGIE 2)
      - Escape-Taste (STRATEGIE 3)
      - Cookie-Banner spezifisch (STRATEGIE 4)
      → Kombination = maximale Erfolgsrate.
      
    WARUM textContent || innerText?
      textContent: Roher Text (inkl. versteckter Elemente).
      innerText: Nur sichtbarer Text.
      → innerText bevorzugt, textContent als Fallback.
      
    WARUM aria-label?
      Barrierefreie Buttons nutzen aria-label statt sichtbaren Text.
      → z.B. <button aria-label="Close">X</button>
      
    WARUM try/catch um jeden click?
      Ein click kann fehlschlagen (Element nicht mehr im DOM, Event-Handler wirft Exception).
      → try/catch verhindert, dass ein Fehler andere Strategien blockiert.
      
    WARUM keyCode: 27?
      27 = Escape-Taste. Viele Modals lauschen auf Escape.
      → keyCode statt code fuer ältere Browser/Frameworks.
      
    WARUM bubbles: true bei KeyboardEvent?
      Event muss bubblen damit Modal-Listener es fangen.
      
    WARUM return int statt dict?
      Einfachheit. Caller will nur wissen: "wurde etwas geschlossen?"
      → 0 = nichts, >0 = etwas geschlossen.
      
    RACE CONDITION:
      Modals können sich während der Ausführung schliessen
      (z.B. Auto-Close nach 5s). → try/catch, Fehler ignoriert.
      
    EXCEPTION HANDLING:
      WebSocket-Fehler → return 0 (Conservative: nichts geschlossen).
    """
    js = """
    (function() {
        var closed = 0;  // Zähler
        
        // STRATEGIE 1: Close-Buttons (Text-Match)
        var closeTexts = ['Schließen','Close','x','X','Ablehnen','Dismiss',
            'Cancel','Abbrechen','No thanks','Nein danke','Nein','No',
            'Spater','Later','Skip','Uberspringen'];
        document.querySelectorAll(
            'button, span, div[role="button"], a, [class*="close"]'
        ).forEach(function(el) {
            var text = (el.textContent || el.innerText || '').trim();
            var ariaLabel = el.getAttribute('aria-label') || '';
            for (var i = 0; i < closeTexts.length; i++) {
                // Text-Match ODER aria-label Match
                if (text === closeTexts[i] || ariaLabel.includes(closeTexts[i])) {
                    try { el.click(); closed++; } catch(e) {}
                    break;  // Nur einmal pro Element
                }
            }
        });
        
        // STRATEGIE 2: Overlays/Backdrops
        document.querySelectorAll(
            '.modal-backdrop, .overlay, [class*="backdrop"], [class*="overlay"]'
        ).forEach(function(el) {
            try { el.click(); closed++; } catch(e) {}
            // Overlay-Click schliesst oft Modal (Click outside)
        });
        
        // STRATEGIE 3: Escape-Taste (simuliert)
        document.dispatchEvent(new KeyboardEvent('keydown', {
            key: 'Escape',
            keyCode: 27,
            bubbles: true
        }));
        // → Viele Modals lauschen auf Escape
        
        // STRATEGIE 4: Cookie-Banner
        document.querySelectorAll(
            '[class*="cookie"] button, [id*="cookie"] button'
        ).forEach(function(el) {
            var t = (el.innerText || '').toLowerCase();
            // Accept, Akzeptieren, Ablehnen, Reject
            if (t.includes('accept') || t.includes('akzept') || 
                t.includes('ablehnen') || t.includes('reject')) {
                try { el.click(); closed++; } catch(e) {}
            }
        });
        
        return closed;  // Anzahl geschlossener Elemente
    })();
    """
    
    try:
        ws = websocket.create_connection(ws_url, timeout=timeout)
        ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
            "params": {"expression": js, "returnByValue": True}}))
        resp = json.loads(ws.recv())
        ws.close()
        
        result = resp.get("result", {}).get("result", {}).get("value", 0)
        # Sicherstellen dass int zurückgegeben wird (nicht null/undefined)
        return result if isinstance(result, int) else 0
        
    except Exception:
        # Exception: WebSocket-Fehler, CDP nicht erreichbar
        return 0  # Conservative: nichts geschlossen


# ═════════════════════════════════════════════════════════════════════════════
# CLI INTERFACE
# ═════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python tool_close_modals.py <ws_url>")
        sys.exit(1)
        
    r = close_modals(sys.argv[1])
    print("Closed {0} modals".format(r))
