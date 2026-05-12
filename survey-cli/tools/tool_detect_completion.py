#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""================================================================================
TOOL: detect_completion — Survey Status Detection (Complete vs Screen-Out)
================================================================================

WAS IST DAS?
  Erkennt ob eine Survey abgeschlossen wurde, disqualifiziert wurde,
  oder noch läuft. Analysiert URL, Seiten-Titel UND Body-Text.

  WICHTIG: Prüft auch auf interaktive Elemente ("Weiter", "Next")
  um False-Positives zu verhindern (Survey kann in einem Modal laufen!).

WARUM EXISTIERT DAS?
  Agenten können nicht unterscheiden zwischen:
  - "Vielen Dank für Ihre Teilnahme" (Erfolg)
  - "Sie qualifizieren sich leider nicht" (Disqual)
  - "Weiter" Button sichtbar (läuft noch)

  Dieses Tool analysiert ALLE Signale und gibt eindeutigen Status.

ARCHITEKTUR:
  ┌──────────────────┐
  │    detect()      │
  └──────────────────┘
         │
         ▼
  ┌──────────────────┐
  │ URL + Title +   │
  │ Body Text       │
  └──────────────────┘
         │
    ┌────┴─────────────────────────────┐
    ▼                                  ▼
  Dashboard-Marker                  Content-Analyse
  (zurück zum Panel)                (Completion/Screen-Out)
         │                                  │
    ┌────┴─────────────┐              ┌────┴─────────────┐
    ▼                  ▼              ▼                  ▼
  "completed"      "completed"    "screen_out"      "running"

STATUS:
  "completed"  → Survey erfolgreich beendet (Danke-Seite)
  "screen_out" → Disqualifiziert (nicht qualifiziert, quota full)
  "running"    → Survey läuft noch (interaktive Elemente sichtbar)

BEREITS FUNKTIONIERT:
  ✓ Qualtrics (Danke-Seite, Disqualifikation)
  ✓ HeyPiggy (zurück zum Dashboard)
  ✓ PureSpectrum (Completion/Screen-Out)

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

import json  # CDP Nachrichten (de)serialisierung
import websocket  # CDP WebSocket Verbindung

__version__ = "1.0.0"
__frozen__ = True  # 🔒 NICHT AENDERN! Getestet mit Qualtrics + HeyPiggy.


# ═════════════════════════════════════════════════════════════════════════════
# KONSTANTEN: Text-Marker fuer Status-Erkennung
# ═════════════════════════════════════════════════════════════════════════════

# COMPLETION_MARKERS: Woerter/Phrasen die auf erfolgreichen Abschluss hindeuten
#   → WARUM so viele? Weil verschiedene Provider unterschiedliche Phrasen nutzen.
#   → WARUM lowercase? Case-insensitive Vergleich (alle zu lowercase).
#   → WARUM Deutsch + Englisch? Surveys sind multilingual.
COMPLETION_MARKERS = [
    # Deutsch
    "vielen dank",  # Standard-Danke
    "danke fuer",  # Variante mit Umlaut-Ersatz
    "gutgeschrieben",  # HeyPiggy: "Guthaben gutgeschrieben"
    "abgeschlossen",  # "Umfrage abgeschlossen"
    "zurueck zur website",  # Zurück zum Panel
    "zurueck zum panel",  # Variante
    "end of survey",  # Englisch-Variante
    "survey is now complete",
    "completed successfully",
    "fertig",  # Kurzform
    "ihre antwort wurde gespeichert",
    # Englisch
    "thank you for completing",
    "survey complete",
    "you have completed",
    "your response has been recorded",
    "successfully submitted",
    "response recorded",
]

# SCREEN_OUT_MARKERS: Woerter/Phrasen die auf Disqualifikation hindeuten
#   → WARUM so viele? Disqual-Meldungen variieren stark.
#   → WARUM "leider"? Deutsche Disqual-Meldungen nutzen "leider" oft.
SCREEN_OUT_MARKERS = [
    # Deutsch
    "nicht qualifiziert",  # Standard-Disqual
    "quota full",  # Quota voll
    "quote erreicht",  # Variante
    "screened out",
    "sorry, you",  # Englisch in deutscher Umfrage
    "unfortunately",
    "leider",  # Deutsche Höflichkeitsform
    "disqualified",
    "do not qualify",
    "qualifizieren sich nicht",
    "survey is closed",  # Umfrage geschlossen
    "umfrage geschlossen",
    "nicht teilnehmen",  # "Sie können nicht teilnehmen"
]

# DASHBOARD_MARKERS: URLs die auf Zurück-zu-Panel hindeuten
#   → WARUM URLs? Weil Dashboard-Redirects eindeutig sind (nicht text-basiert).
DASHBOARD_MARKERS = [
    "prolific.co/submissions",  # Prolific zurück
    "mturk.com/mturk/preview",  # MTurk zurück
]

# INTERACTIVITY_MARKERS: Woerter die zeigen dass Survey noch läuft
#   → WARUM? Danke-Seiten KÖNNEN "Weiter" enthalten (z.B. "Weiter zum Panel").
#     Aber WENN mehrere Interaktions-Marker vorhanden = Survey läuft noch.
#   → Threshold: 2+ Marker = "running" (verhindert False-Positives).
INTERACTIVITY_MARKERS = [
    "weiter",  # Deutsch: Nächste Seite
    "nächste",  # Variante
    "submit",  # Englisch
    "next",  # Englisch
    "fortfahren",  # Fortsetzen
    "umfrage starten",  # Survey-Start-Button
    "antwort",  # "Antwort eingeben"
]


def detect(ws_url: str, timeout: int = 10) -> str:
    """Erkennt Survey-Status (completed | screen_out | running).

    ARGS:
        ws_url (str): CDP WebSocket URL
        timeout (int): WebSocket Timeout in Sekunden

    RETURNS:
        str: "completed" | "screen_out" | "running"

    ALGORITHMUS:
      1. JavaScript ausführen: URL, Title, Body-Text extrahieren
      2. Dashboard-Check: URL enthält DASHBOARD_MARKERS?
         → JA: return "completed" (zurück zum Panel = fertig)
      3. SCREEN-OUT + COMPLETION VOR Interactivity:
         Completion oder Screen-Out Marker → SOFORT return (Priority!)
      4. Interaktivitäts-Check: 2+ INTERACTIVITY_MARKERS im Text?
         → JA: return "running" (keine Completion/Screen-Out = läuft noch)
      5. Default: return "running"

    WARUM Completion VOR Interactivity?
      Completion-Seiten enthalten oft "Weiter" + "Antwort" (z.B.
      "Ihre Antwort wurde gespeichert. Weiter zur Website.").
      Diese Kombination matched 2+ interactivity = False-Positive "running".
      Fix: Completion/Screen-Out prüfen VOR Interactivity-Check.
    """
    # JavaScript: URL, Title, Body-Text extrahieren
    js = """
    (function() {
        return {
            url: window.location.href.toLowerCase(),
            title: document.title.toLowerCase(),
            text: (document.body.innerText || '').toLowerCase().substring(0, 2000)
            // → substring(0, 2000): Nur erste 2000 Zeichen (Performance)
        };
    })();
    """

    try:
        ws = websocket.create_connection(ws_url, timeout=timeout)
        ws.send(
            json.dumps(
                {
                    "id": 1,
                    "method": "Runtime.evaluate",
                    "params": {"expression": js, "returnByValue": True},
                }
            )
        )
        resp = json.loads(ws.recv())
        ws.close()

        # Daten extrahieren
        data = resp.get("result", {}).get("result", {}).get("value", {})
        url = data.get("url", "")
        title = data.get("title", "")
        text = data.get("text", "")
        combined = url + " " + title + " " + text

        # SCHWELLE 1: Dashboard-Redirect (zurück zum Panel)
        for marker in DASHBOARD_MARKERS:
            if marker in url:
                return "completed"

        # SCHWELLE 2: URL-Completion-Marker
        if any(m in url for m in ["complete", "success", "finished", "done", "thankyou"]):
            return "completed"

        # SCHWELLE 3: Completion ODER Screen-Out – SOFORT return (PRIORITY!)
        # Completion-Seiten enthalten oft "Weiter" + "Antwort" (z.B.
        # "Ihre Antwort wurde gespeichert. Weiter zur Website.").
        # Das matched 2+ INTERACTIVITY_MARKERS → False-Positive "running".
        # Fix: Completion/Screen-Out PRÜFEN VOR dem Interactivity-Check.
        for marker in SCREEN_OUT_MARKERS:
            if marker in combined:
                return "screen_out"

        for marker in COMPLETION_MARKERS:
            if marker in combined:
                return "completed"

        # SCHWELLE 4: Interaktivitäts-Check (nur wenn KEINE Completion/Screen-Out)
        interactive_count = sum(1 for m in INTERACTIVITY_MARKERS if m in text)
        if interactive_count >= 2:
            return "running"

        # DEFAULT: Unsicher = läuft noch
        return "running"

    except Exception:
        # Exception: WebSocket-Fehler, CDP nicht erreichbar
        # Conservative: lieber "running" (weiterlaufen) als falsch "completed"
        return "running"


# ═════════════════════════════════════════════════════════════════════════════
# CLI INTERFACE
# ═════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python tool_detect_completion.py <ws_url>")
        sys.exit(1)

    r = detect(sys.argv[1])
    print("Status: " + r)
