"""Provider-specific survey patterns.

WARUM: Jeder Survey-Provider (Qualtrics, Toluna, Strat7, PureSpectrum,
Cint, Samplicio, etc.) nutzt unterschiedliche DOM-Strukturen und Events.
Ein generischer Solver schlägt bei jedem Provider fehl. Dieses Paket
kapselt provider-spezifische Selektoren, Commands und Completion-Marker.

ARCHITEKTUR: Jedes Modul exportiert drei Funktionen:
  - detect(page_text): bool — prüft ob dieser Provider aktiv ist
  - get_actions(snapshot, profile, provider): list — NEMO-kompatible Actions
  - is_completed(page_text): bool — prüft Fertigstellungs-Marker
Keine Klassen, kein State — reine Funktionen und Datenstrukturen.
Neue Provider werden als neues Modul hinzugefügt.

BANNED METHODS — NIEMALS VERWENDEN:
❌ playstealth launch
❌ webauto-nodriver — ABSOLUT BANNED
❌ cua-driver click (raw index)
❌ --remote-allow-origins=* (ohne Quotes)
❌ /tmp/heypiggy-bot (fixed profile)
❌ Hardcoded PIDs
❌ pkill -f "Google Chrome"
❌ killall Google Chrome
❌ skylight-cli click --element-index
"""
