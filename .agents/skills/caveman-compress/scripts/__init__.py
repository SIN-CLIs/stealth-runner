"""Caveman compress scripts.

WARUM: Dieses Paket bündelt alle Tools für die Caveman-Kompression.
Agenten importieren ausschließlich aus diesem Package, nie direkt
aus Einzeldateien. Zentrale Versionskontrolle und API-Stabilität.

ARCHITEKTUR: Package-Root mit __all__ = [cli, compress, detect, validate].
Keine Logik in __init__.py — nur Export-Regelung und Versions-String.

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

__all__ = ["cli", "compress", "detect", "validate"]

__version__ = "1.0.0"
