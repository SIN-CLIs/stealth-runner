"""Caveman Compress — __main__ Entry Point.

WARUM: Ermöglicht `python -m scripts` als Shorthand für CLI.
Keine Logik hier — nur Weiterleitung an cli.main().

ARCHITEKTUR: Ein-Zeilen-Redirect. Kein State, keine Imports außer cli.main.

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

from .cli import main

main()
