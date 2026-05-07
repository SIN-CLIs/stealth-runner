"""Chrome launcher with hardened flags for stealth automation.

WARUM: Standard-Chrome-Start mit --enable-automation wird sofort als Bot
erkannt (Cloudflare, Kasada, GeeTest). Dieses Modul startet Chrome mit
hardened Flags, die CDP offen halten UND gleichzeitig Automation-Patches
entfernen. Jeder Flag ist bewusst gewählt.

ARCHITEKTUR: Async-Chrome-Launcher (asyncio).
Stealth-Flags sind in _STEALTH_FLAGS zentral definiert.
Profil wird dynamisch unter /tmp/ erzeugt (NIEMALS festes Profil).
CDP WebSocket-URL wird über get_browser_ws ausgelesen.

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

from __future__ import annotations

import asyncio
import os
import shutil
import signal
import sys
from dataclasses import dataclass, field
from pathlib import Path

from stealth_captcha.cdp.targets import get_browser_ws
from stealth_captcha.config import ChromeSettings
from stealth_captcha.exceptions import CDPConnectionError
from stealth_captcha.telemetry import get_logger

log = get_logger(__name__)

# Flags chosen to avoid detection heuristics.
# We deliberately omit --enable-automation and --disable-blink-features=AutomationControlled
# here because they are handled separately by the stealth JS injection.
_STEALTH_FLAGS: tuple[str, ...] = (
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-features=IsolateOrigins,site-per-process,Translate,AcceptCHFrame,MediaRouter,OptimizationHints,ChromeWhatsNewUI",
    "--disable-component-update",
    "--disable-background-networking",
    "--disable-sync",
    "--disable-domain-reliability",
    "--disable-client-side-phishing-detection",
    "--disable-popup-blocking",
    "--disable-prompt-on-repost",
    "--disable-hang-monitor",
    "--disable-breakpad",
    "--disable-renderer-backgrounding",
    "--disable-backgrounding-occluded-windows",
    "--disable-ipc-flooding-protection",
    "--disable-search-engine-choice-screen",
    "--enable-features=NetworkService,NetworkServiceInProcess",
    "--metrics-recording-only",
    "--password-store=basic",
    "--use-mock-keychain",
    "--lang=en-US",
    "--noerrdialogs",
    "--deny-permission-prompts",
)


def _find_chrome() -> str:
    """Locate the Chrome/Chromium binary on the current platform."""
    candidates: list[str] = []

    if sys.platform == "darwin":
        candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary",
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        ]
    elif sys.platform.startswith("linux"):
        candidates = [
            "google-chrome",
            "google-chrome-stable",
            "chromium",
            "chromium-browser",
            "chrome",
        ]
    elif sys.platform == "win32":
        candidates = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files\Chromium\Application\chrome.exe",
        ]

    for c in candidates:
        path = shutil.which(c) if ("/" not in c and "\\" not in c) else c
        if path and Path(path).exists():
            log.info("chrome_binary_found", path=path)
            return path

    raise CDPConnectionError(
        "Chrome/Chromium binary not found. Install Chrome or set STEALTH_CHROME__BINARY."
    )


@dataclass
class StealthBrowser:
    """Manages a Chrome process with stealth flags and isolated profile.

    Usage:
        async with StealthBrowser() as browser:
            ws_url = await get_browser_ws()
            # ... use CDPClient ...

    The browser is automatically terminated when the context manager exits.
    """

    user_data_dir: Path = field(
        default_factory=lambda: Path.home() / ".stealth-suite" / "chrome-profile"
    )
    port: int = 9222
    binary: str | None = None
    headless: bool = False
    extra_flags: tuple[str, ...] = ()
    settings: ChromeSettings | None = None

    # Internal
    proc: asyncio.subprocess.Process | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self.settings:
            if self.settings.binary:
                self.binary = self.settings.binary
            if self.settings.headless:
                self.headless = True
            if self.settings.extra_flags:
                self.extra_flags = self.settings.extra_flags

    async def launch(self) -> None:
        """Launch Chrome with stealth flags.

        Blocks until the CDP endpoint becomes responsive (up to 10s).
        """
        binary = self.binary or _find_chrome()
        self.user_data_dir.mkdir(parents=True, exist_ok=True)

        flags = list(_STEALTH_FLAGS) + [
            f"--remote-debugging-port={self.port}",
            f"--user-data-dir={self.user_data_dir}",
            "--remote-allow-origins=\"*\"",  # 🔥 MIT Quotes! Ohne Quotes expandiert zsh * → "no matches found"
        ]

        if self.headless:
            flags.append("--headless=new")

        # Add any user-specified extra flags
        for flag in self.extra_flags:
            if flag not in flags:
                flags.append(flag)

        log.info(
            "launching_chrome",
            binary=binary,
            port=self.port,
            headless=self.headless,
            profile=str(self.user_data_dir),
        )

        self.proc = await asyncio.create_subprocess_exec(
            binary,
            *flags,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            preexec_fn=os.setsid if sys.platform != "win32" else None,
        )

        # Wait for CDP to come online (poll /json/version)
        for _attempt in range(50):
            try:
                await get_browser_ws("127.0.0.1", self.port)
                log.info("chrome_ready", port=self.port, pid=self.proc.pid)
                return
            except CDPConnectionError:
                await asyncio.sleep(0.2)
                continue

        await self.terminate()
        raise CDPConnectionError(f"Chrome did not become ready on port {self.port} within 10s")

    async def navigate(self, url: str) -> None:
        """Open a URL in the default tab (creates one if none exist).

        Requires that the browser is already running.
        """
        from stealth_captcha.cdp.client import CDPClient
        from stealth_captcha.cdp.targets import create_tab

        ws_url = await get_browser_ws("127.0.0.1", self.port)

        async with await CDPClient.connect(ws_url) as client:
            target = await create_tab(url, host="127.0.0.1", port=self.port)
            session = await client.attach(target.target_id)
            await session.send("Page.enable")
            await session.send("Page.navigate", {"url": url})

            # Wait for load
            async with client.event_stream(session, "Page.loadEventFired") as q:
                try:
                    await asyncio.wait_for(q.get(), timeout=30.0)
                except TimeoutError:
                    log.warning("page_load_timeout", url=url)

    async def terminate(self) -> None:
        """Kill the Chrome process gracefully (SIGTERM → SIGKILL after 5s)."""
        if not self.proc:
            return
        pid = self.proc.pid
        log.info("terminating_chrome", pid=pid)

        try:
            if sys.platform != "win32":
                os.killpg(os.getpgid(pid), signal.SIGTERM)
            else:
                self.proc.terminate()

            try:
                await asyncio.wait_for(self.proc.wait(), timeout=5.0)
            except TimeoutError:
                log.warning("chrome_sigterm_timeout", pid=pid)
                if sys.platform != "win32":
                    os.killpg(os.getpgid(pid), signal.SIGKILL)
                else:
                    self.proc.kill()
        except ProcessLookupError:
            log.info("chrome_already_exited", pid=pid)

        self.proc = None

    async def __aenter__(self) -> StealthBrowser:
        await self.launch()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.terminate()
