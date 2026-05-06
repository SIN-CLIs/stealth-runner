"""Embedded JS payloads for reference — legacy dispatchEvent approach.

These payloads are preserved for reference. The new CDP-based engine
does NOT use dispatchEvent — it uses Input.dispatchMouseEvent on the
CDP protocol instead, which produces trusted element-level PointerEvents.
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
