"""Embedded JS payloads for reference — legacy dispatchEvent approach.

WARUM: Historische JS-Snippets für ältere Captcha-Engines.
DIESE PAYLOADS WERDEN NICHT MEHR AKTIV VERWENDET. Die neue CDP-basierte
Engine nutzt Input.dispatchMouseEvent (trusted PointerEvents).
dispatchEvent erzeugt isTrusted=false und wird von modernen Engines
blockiert. Payloads bleiben aus Archivierungsgründen erhalten.

ARCHITEKTUR: load(name) lädt JS-Dateien aus dem Package via importlib.resources.
Nur Referenz — kein Produktiv-Code. Kein State, keine Side-Effects.

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

from importlib import resources


def load(name: str) -> str:
    """Load a JS payload by filename.

    Args:
        name: Filename (e.g., "gocaptcha_slide.js").

    Returns:
        The JavaScript source as a string.
    """
    return resources.files("stealth_captcha.payloads").joinpath(name).read_text(encoding="utf-8")
