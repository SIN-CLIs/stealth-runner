"""
Patchright/Playwright compatibility shim for stealth-captcha.

WHY THIS FILE EXISTS
--------------------
Same rationale as the matching shim in survey-cli (`survey/daemon/
_playwright_compat.py`). Patchright is a drop-in replacement for the
`playwright` package that closes CDP-detection leaks at the binary patch
level. Switching is a zero-API-change move; only the import source
changes. We must NOT make Patchright a hard dependency because CI
sandboxes without internet (e.g. INTEGRATIONS_ONLY runners) cannot
install it on demand.

PUBLIC SURFACE
--------------
- `BACKEND_NAME` — "patchright" / "playwright" / "none". Computed lazily
  via `detect_backend()`. Reading the constant alone never imports a
  browser package; you only pay the import cost when you actually want
  to launch a browser.
- `get_async_playwright()` — returns the upstream `async_playwright`
  callable from whichever backend is installed; raises ImportError with
  a clear message when neither is. THIS is where you pay the cost.
- `subprocess_import_block(indent)` — yields a Python source snippet
  that produces an `async_playwright` symbol in a SUBPROCESS' scope.
  Pure-string, no imports — works even when neither backend is installed
  in the parent process (the drag-drop solver spawns its own
  subprocess for isolation).

CONTRACT
--------
- The detection has THREE outcomes, not two: patchright present,
  playwright present, neither present. The "neither" case must be a
  recoverable runtime error, not an import-time crash, so callers that
  need only `subprocess_import_block()` can still import this module on
  hosts without any browser library installed (CI lint, unit tests).

HISTORY
-------
- 2026-05-17 (CEO-WAVE-1): initial impl as part of P0 stealth hardening.
- 2026-05-17 (CEO-WAVE-1, fix): split eager import into lazy
  `get_async_playwright()` so unit tests of `subprocess_import_block`
  pass on hosts without any browser library installed.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)


def _detect() -> tuple[str, Callable[[], Any] | None]:
    """Try patchright, then playwright, return (name, factory) or
    ("none", None) if neither is present."""
    try:
        from patchright.async_api import async_playwright as factory  # type: ignore[import-not-found]

        return "patchright", factory
    except ImportError:
        pass
    try:
        from playwright.async_api import async_playwright as factory  # type: ignore[import-not-found]

        return "playwright", factory
    except ImportError:
        pass
    return "none", None


_NAME, _FACTORY = _detect()
BACKEND_NAME: str = _NAME

if BACKEND_NAME == "patchright":
    logger.info(
        "stealth-captcha playwright-compat: using Patchright (CDP stealth patches active)."
    )
elif BACKEND_NAME == "playwright":
    logger.warning(
        "stealth-captcha playwright-compat: using vanilla playwright "
        "(no CDP stealth patches). Install patchright for production: "
        "`pip install patchright && patchright install chromium`"
    )
else:
    # Don't crash — only complain when someone actually wants a browser.
    logger.debug(
        "stealth-captcha playwright-compat: neither patchright nor playwright installed. "
        "subprocess_import_block() still works; get_async_playwright() will raise."
    )


def get_async_playwright() -> Any:
    """Return the `async_playwright` callable from whichever backend is
    installed. Raises ImportError if neither is available — this is the
    same failure mode the original `from playwright.async_api import
    async_playwright` had, just with a better error message."""
    if _FACTORY is None:
        raise ImportError(
            "Neither patchright nor playwright is installed. Install:\n"
            "  pip install patchright && patchright install chromium  # recommended\n"
            "  pip install playwright && playwright install chromium  # fallback"
        )
    return _FACTORY


def subprocess_import_block(indent: int = 4) -> str:
    """Return a Python source block that imports async_playwright with
    patchright preferred, playwright fallback. For inlining into the
    subprocess script template used by the Angular CDK drag-drop solver.

    The block is intentionally side-effect-free except for binding the
    name `async_playwright` in the subprocess' module scope. It does not
    print, log, or write anything — the caller controls subprocess I/O.

    Args:
        indent: number of leading spaces to prepend on each line so the
            block can be inlined inside an `async def`/function body
            without breaking Python's significant-whitespace rule.
            Default 4 matches the most common nesting (one function deep).
    """
    pad = " " * indent
    return (
        f"{pad}try:\n"
        f"{pad}    from patchright.async_api import async_playwright\n"
        f"{pad}except ImportError:\n"
        f"{pad}    from playwright.async_api import async_playwright\n"
    )


__all__ = ["BACKEND_NAME", "get_async_playwright", "subprocess_import_block"]
