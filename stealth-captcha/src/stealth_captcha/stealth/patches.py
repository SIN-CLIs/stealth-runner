"""StealthInjector: ships JS patches to the browser via CDP.

Uses Page.addScriptToEvaluateOnNewDocument so patches run on every
new document (including iframes) BEFORE the page's own scripts.

The bundle is built once by build_stealth_bundle() and reused across
injections to the same session.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib import resources
from typing import Any

from stealth_captcha.cdp.client import CDPSession
from stealth_captcha.config import StealthSettings
from stealth_captcha.exceptions import StealthInjectionError
from stealth_captcha.telemetry import get_logger

log = get_logger(__name__)


def _load_script(name: str) -> str:
    """Load an embedded JS script from the scripts package."""
    pkg = "stealth_captcha.stealth.scripts"
    return resources.files(pkg).joinpath(name).read_text(encoding="utf-8")


def build_stealth_bundle(settings: StealthSettings) -> str:
    """Assemble the full stealth JS bundle from individual patches.

    Injects a config object (window.__STEALTH_CFG__), then runs the
    stealth_main.js payload. All modules are configured via settings.

    Returns:
        A single JavaScript string ready for CDP injection.
    """
    cfg: dict[str, Any] = {
        "navigator": settings.enable_navigator_patches,
        "plugins": settings.enable_plugins_patch,
        "languages": True,
        "languagesValue": ["en-US", "en"],
        "chromeRuntime": settings.enable_chrome_runtime_patch,
        "permissions": settings.enable_permissions_patch,
        "webgl": settings.enable_webgl_patches,
        "canvas": settings.enable_canvas_patches,
        "audio": settings.enable_audio_patches,
        "battery": settings.enable_battery_patch,
        "iframe": settings.enable_iframe_contentwindow_patch,
    }

    cfg_js = "window.__STEALTH_CFG__ = " + json.dumps(cfg) + ";"
    stealth_js = _load_script("stealth_main.js")

    return "\n".join([cfg_js, stealth_js])


@dataclass
class StealthInjector:
    """Injects and manages stealth JS in a CDP session.

    Usage:
        injector = StealthInjector(settings.stealth)
        await injector.install(session)
        # ... solve captcha ...
        await injector.uninstall(session)
    """

    settings: StealthSettings
    _script_id: str | None = field(default=None, init=False, repr=False)

    async def install(self, session: CDPSession) -> None:
        """Inject the stealth bundle into the page.

        Safe to call multiple times — checks for existing scriptId.
        If called again, re-installs (e.g., after navigation).
        """
        bundle = build_stealth_bundle(self.settings)
        try:
            await session.send("Page.enable")
            result = await session.send(
                "Page.addScriptToEvaluateOnNewDocument",
                {"source": bundle, "runImmediately": True},
            )
            self._script_id = result.get("identifier")
            # Also run immediately in the current document
            await session.send(
                "Runtime.evaluate",
                {"expression": bundle, "awaitPromise": False, "returnByValue": False},
            )
            log.info("stealth_injected", script_id=self._script_id, size_bytes=len(bundle))
        except Exception as e:
            raise StealthInjectionError(f"Failed to inject stealth bundle: {e}") from e

    async def uninstall(self, session: CDPSession) -> None:
        """Remove the injected script from new documents (idempotent)."""
        if not self._script_id:
            return
        try:
            await session.send(
                "Page.removeScriptToEvaluateOnNewDocument",
                {"identifier": self._script_id},
            )
        finally:
            self._script_id = None
