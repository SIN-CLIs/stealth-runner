"""
Patchright/Playwright compatibility shim for the survey-cli daemon.

WHY THIS FILE EXISTS
--------------------
Patchright is a drop-in replacement for the `playwright` Python package that
ships the same public API (`playwright.async_api`) but with the CDP-detection
leaks closed at the binary patches level (Runtime.enable side effects,
function.toString tampering, the `cdc_*` ChromeDriver markers, the
`navigator.webdriver` property, console.* trap, etc.). Switching to it is a
zero-API-change move; the only thing that changes is which package backs the
import.

We must NOT make Patchright a hard dependency because:
  - CI containers without Patchright's bundled Chromium build keep working
    against vanilla `playwright`.
  - Anyone running this in a sandbox without internet access (e.g. our own
    INTEGRATIONS_ONLY runners) cannot fetch Patchright on demand.

PUBLIC SURFACE
--------------
- `BACKEND_NAME` — "patchright" / "playwright" / "none". Reading this
  constant never imports a browser package.
- `get_async_playwright()` — returns the upstream `async_playwright`
  callable from whichever backend is installed; raises ImportError with
  a clear message when neither is. THIS is where you pay the import cost.

USAGE
-----
    from survey.daemon._playwright_compat import (
        BACKEND_NAME,
        get_async_playwright,
    )
    logger.info("playwright backend: %s", BACKEND_NAME)
    async with get_async_playwright()() as p:
        ...

CONTRACT
--------
- get_async_playwright() returns the same callable shape as the upstream
  `async_playwright` (returns an awaitable context manager). Calling code
  does not need to know which backend is in use.
- BACKEND_NAME is "patchright" / "playwright" / "none". Importing this
  module is safe even when neither backend is installed; only
  `get_async_playwright()` raises.

HISTORY
-------
- 2026-05-17 (CEO-WAVE-1): initial impl as part of P0 stealth hardening.
- 2026-05-17 (CEO-WAVE-1, fix): split eager import into lazy factory so
  this module loads safely under lint / AST tooling without playwright
  installed.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)


def _detect() -> tuple[str, Callable[[], Any] | None]:
    """Try patchright, then playwright, return (name, factory) or
    ("none", None) if neither is present."""
    try:
        # Patchright keeps the exact same public symbol path as playwright,
        # so importing it as if it were playwright is intentional and
        # supported.
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
        "playwright-compat: using Patchright (CDP stealth patches active). "
        "Switch to vanilla playwright by uninstalling patchright."
    )
elif BACKEND_NAME == "playwright":
    logger.warning(
        "playwright-compat: using vanilla playwright (no CDP stealth patches). "
        "Install patchright for production use: "
        "`pip install patchright && patchright install chromium`"
    )
else:
    logger.debug(
        "playwright-compat: neither patchright nor playwright installed. "
        "get_async_playwright() will raise ImportError when called."
    )


def get_async_playwright() -> Any:
    """Return the `async_playwright` callable from whichever backend is
    installed. Raises ImportError if neither is available — same failure
    mode as the original `from playwright.async_api import async_playwright`,
    just with a better error message."""
    if _FACTORY is None:
        raise ImportError(
            "Neither patchright nor playwright is installed. Install one of:\n"
            "  pip install patchright && patchright install chromium  # recommended (stealth)\n"
            "  pip install playwright && playwright install chromium  # vanilla fallback"
        )
    return _FACTORY


__all__ = ["BACKEND_NAME", "get_async_playwright"]
