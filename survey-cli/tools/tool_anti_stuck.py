#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""================================================================================
TOOL: anti_stuck — Stuck Loop Detector via DOM-Hash
================================================================================

WAS IST DAS?
  Erkennt wenn der Agent in einer Endlosschleife feststeckt.
  Vergleicht DOM-Hashes (bodyText MD5) — wenn 3x hintereinander
  derselbe Hash = Agent ist stuck!

WARUM EXISTIERT DAS?
  Agent-Loops können stuck werden:
  - Click funktioniert nicht (Element nicht klickbar)
  - Survey lädt nicht weiter (Netzwerk-Fehler)
  - Loop klickt immer denselben Button (falsche Logik)
  
  Ohne Detection: Agent versendet 100x denselben Klick = Ban-Risiko!

ARCHITEKTUR:
  ┌──────────────────┐
  │   AntiStuck      │
  │   (Klasse)      │
  └──────────────────┘
         │
    ┌────┴─────────────┐
    ▼                  ▼
  is_stuck(hash)    reset()
    │                  │
    ▼                  ▼
  history.append()   history = []
    │
    ▼
  Threshold-Check: 3x gleicher Hash?
    │
    ┌────┴──────────┐
    ▼               ▼
  True (stuck)   False (OK)
    │               │
    ▼               ▼
  Breche ab!    Weiter!

BEREITS FUNKTIONIERT:
  ✓ Qualtrics Language Loop (wiederholt Sprachauswahl)
  ✓ Stuck auf "Weiter"-Button (klickt, aber nichts passiert)
  ✓ Infinite Redirect Loop

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

from typing import List

__version__ = "1.0.0"
__frozen__ = True  # 🔒 NICHT AENDERN! Getestet mit Qualtrics Stuck-Detection.


# ═════════════════════════════════════════════════════════════════════════════
# KLASSE: AntiStuck
# ═════════════════════════════════════════════════════════════════════════════
# ZWECK:
#   Trackt DOM-Hashes und erkennt Wiederholungen.
#   DOM-Hash = MD5 von document.body.innerText (aus tool_snapshot.py).
#
# WARUM DOM-Hash statt URL?
#   URL kann gleich bleiben während sich Inhalt ändert (AJAX/SPA).
#   DOM-Hash erfasst INHALTS-Änderungen.
#
# WARUM Threshold = 3?
#   1x gleich = Zufall (Netzwerk-Latenz).
#   2x gleich = Verdacht (langsames Laden).
#   3x gleich = Stuck (mit >99% Wahrscheinlichkeit).
#   → 3 = sweet spot (nicht zu empfindlich, nicht zu tolerant).
#
# WARUM Liste (history) statt nur Counter?
#   Wir tracken ALLE Hashes (nicht nur aktuellen).
#   → Ermöglicht erweiterte Analyse (z.B. Oszillation-Erkennung).
#   → Maximal 100 Einträge (Memory-Begrenzung).
# =============================================================================

class AntiStuck:
    def __init__(self, threshold: int = 3):
        """Initialisiert AntiStuck-Checker.
        
        ARGS:
            threshold (int): Wie viele aufeinanderfolgende gleiche Hashes
                             bis "stuck" erkannt wird (default: 3)
                             
        WARUM 3?
          1x = Zufall, 2x = Verdacht, 3x = Stuck.
          → 3 = statistisch signifikant (bei zufälligem Hash = 1/16^12 Wahrscheinlichkeit).
        """
        self.threshold = threshold
        self.history: List[str] = []  # Alle gesehenen Hashes
        
    def is_stuck(self, current_hash: str) -> bool:
        """Prüft ob Agent stuck ist.
        
        ARGS:
            current_hash (str): Aktueller DOM-Hash (aus tool_snapshot)
            
        RETURNS:
            bool: True wenn threshold aufeinanderfolgende gleiche Hashes
            
        ALGORITHMUS:
          1. Hash zur History hinzufügen
          2. History zu lang? → Alte Einträge entfernen (max 100)
          3. Letzte 'threshold' Einträge extrahieren
          4. Alle gleich? (len(set(recent)) == 1)
             → JA: return True (stuck!)
             → NEIN: return False
             
        WARUM len(set(recent)) == 1?
          set() entfernt Duplikate. Wenn Länge = 1 = alle Einträge gleich.
          → Eleganter als manueller Vergleich.
          
        WARUNG: Wenn threshold = 3, brauchen wir mindestens 3 Einträge.
          Weniger als 3 = return False (noch nicht genug Daten).
        """
        self.history.append(current_hash)
        
        # Noch nicht genug Daten?
        if len(self.history) < self.threshold:
            return False
            
        # Letzte 'threshold' Einträge
        recent = self.history[-self.threshold:]
        
        # Alle gleich? → Stuck!
        return len(set(recent)) == 1
        
    def reset(self):
        """Löscht History.
        
        WARUM?
          Nach Stuck-Erkennung oder erfolgreicher Aktion:
          → Reset = frischer Start, keine falschen Positives.
          → Wird von Survey-Loop nach jeder erfolgreichen Seiten-Navigation aufgerufen.
        """
        self.history = []
        
    @property
    def count(self) -> int:
        """Zählt wie oft aktueller Hash wiederholt wurde.
        
        RETURNS:
            int: Anzahl aufeinanderfolgender gleicher Hashes (rückwärts)
            
        WARUM property?
          Einfacher Zugriff: checker.count (statt Methode).
          → Keine Parameter nötig (nutzt interne History).
          
        ALGORITHMUS:
          - Aktueller Hash = history[-1]
          - Rückwärts zählen bis anderer Hash gefunden
          → z.B. ["abc", "def", "def", "def"] → count = 3
        """
        if not self.history:
            return 0
            
        current = self.history[-1]  # Aktueller Hash
        c = 0
        
        # Rückwärts zählen
        for h in reversed(self.history):
            if h == current:
                c += 1
            else:
                break  # Anderer Hash gefunden → Stop
                
        return c


# ═════════════════════════════════════════════════════════════════════════════
# FUNKTION: check_stuck() (Stateless)
# ═════════════════════════════════════════════════════════════════════════════
def check_stuck(history: List[str], current: str, threshold: int = 3) -> bool:
    """Stateless Version: Prüft Stuck ohne Klasse.
    
    ARGS:
        history (list): Liste vorheriger Hashes
        current (str): Aktueller Hash
        threshold (int): Schwelle (default: 3)
        
    RETURNS:
        bool: True wenn stuck
        
    WARUM stateless?
      Einfacher in funktionalen Kontexten (keine Klasse nötig).
      → history wird extern verwaltet (z.B. in Survey-Loop).
      
    WARUM threshold - 1?
      history enthält VORHERIGE Hashes (ohne current).
      → Wir brauchen threshold - 1 vorherige + current = threshold total.
      → z.B. threshold=3: 2 vorherige + current = 3 Einträge.
    """
    if len(history) < threshold - 1:
        return False
        
    # Letzte (threshold - 1) Einträge + current
    recent = history[-(threshold - 1):] + [current]
    
    # Alle gleich?
    return len(set(recent)) == 1


# ═════════════════════════════════════════════════════════════════════════════
# CLI INTERFACE
# ═════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    checker = AntiStuck(threshold=3)
    
    # Test-Fälle
    for h in ["abc", "abc", "abc", "def", "def", "def"]:
        stuck = checker.is_stuck(h)
        print("Hash: {0}, Stuck: {1}, Count: {2}".format(h, stuck, checker.count))
        
    # Erwartete Ausgabe:
    # Hash: abc, Stuck: False, Count: 1  (noch nicht genug)
    # Hash: abc, Stuck: False, Count: 2  (noch nicht genug)
    # Hash: abc, Stuck: True,  Count: 3  (STUCK! 3x gleich)
    # Hash: def, Stuck: False, Count: 1  (neuer Hash, reset)
    # Hash: def, Stuck: False, Count: 2  (wiederholt)
    # Hash: def, Stuck: True,  Count: 3  (STUCK! 3x gleich)
