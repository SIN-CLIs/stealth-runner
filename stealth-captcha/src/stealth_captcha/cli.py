"""Click-based CLI for the stealth-captcha solver.

WARUM: Captcha-Solving muss manuell debug- und testbar sein.
Dieses CLI stellt Commands bereit für: Chrome-Start, Target-Discovery,
Slide/Drag/Text-Captcha-Lösung, Memory-Stats. Kein Survey-Automation —
rein für Entwicklung und Troubleshooting.

ARCHITEKTUR: Asyncio-basierte CLI (argparse). Delegiert an Solver-Klassen
und Experience-Memory. Support für --use-existing-chrome (verbindet zu
laufender Instanz statt neu zu starten). Exit-Codes: 0 = Success, 1 = Failure.

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
import sys

import click

from stealth_captcha.cdp.browser import StealthBrowser
from stealth_captcha.cdp.client import CDPClient
from stealth_captcha.cdp.targets import (
    create_tab,
    get_browser_ws,
    list_targets,
)
from stealth_captcha.config import get_settings
from stealth_captcha.memory import ExperienceMemory
from stealth_captcha.solver.slide import SlideCaptchaSolver
from stealth_captcha.stealth import StealthInjector
from stealth_captcha.telemetry import get_logger, init_telemetry

log = get_logger(__name__)


@click.group()
@click.option("--log-level", default="INFO", help="Log level (DEBUG, INFO, WARNING)")
def main(log_level: str) -> None:
    """Stealth Captcha CLI — CDP-based captcha solver for Stealth Suite."""
    init_telemetry(level=log_level)


@main.command("solve-slide")
@click.option("--url", required=True, help="Page URL containing the slide captcha")
@click.option("--block-selector", default=".gc-drag-block", help="CSS selector for drag block")
@click.option("--target-selector", default=".gc-drag-target", help="CSS selector for target zone")
@click.option(
    "--use-existing-chrome",
    is_flag=True,
    default=False,
    help="Connect to already-running Chrome on STEALTH_CDP_PORT (default 9222)",
)
def solve_slide(
    url: str,
    block_selector: str,
    target_selector: str,
    use_existing_chrome: bool,
) -> None:
    """Solve a GoCaptcha / NetEase / GeeTest slide captcha."""
    asyncio.run(_solve_slide_async(url, block_selector, target_selector, use_existing_chrome))


async def _solve_slide_async(
    url: str,
    block_selector: str,
    target_selector: str,
    use_existing_chrome: bool,
) -> None:
    settings = get_settings()

    if use_existing_chrome:
        log.info("connecting_to_existing_chrome", port=settings.cdp.port)
        browser_ws = await get_browser_ws(settings.cdp.host, settings.cdp.port)
        await _run_solver(browser_ws, url, block_selector, target_selector)
        return

    async with StealthBrowser(
        user_data_dir=settings.cdp.user_data_dir,
        port=settings.cdp.port,
    ) as browser:
        log.info("chrome_launched", pid=browser.proc.pid if browser.proc else None)
        browser_ws = await get_browser_ws(settings.cdp.host, settings.cdp.port)
        await _run_solver(browser_ws, url, block_selector, target_selector)


async def _run_solver(
    browser_ws: str,
    url: str,
    block_selector: str,
    target_selector: str,
) -> None:
    settings = get_settings()

    async with await CDPClient.connect(
        browser_ws,
        timeout_s=settings.cdp.connect_timeout_s,
    ) as client:
        # Create a new tab
        target = await create_tab("about:blank", host=settings.cdp.host, port=settings.cdp.port)
        session = await client.attach(target.target_id)

        # Stealth inject
        injector = StealthInjector(settings.stealth)
        await injector.install(session)

        # Navigate to target URL
        await session.send("Page.enable")
        await session.send("Page.navigate", {"url": url})

        # Wait for page load
        async with client.event_stream(session, "Page.loadEventFired") as q:
            try:
                await asyncio.wait_for(q.get(), timeout=30.0)
            except TimeoutError:
                log.warning("page_load_timeout", url=url)

        # Small extra wait for JS captcha to initialize
        await asyncio.sleep(1.5)

        # Solve
        solver = SlideCaptchaSolver(
            settings=settings,
            block_selector=block_selector,
            target_selector=target_selector,
        )
        result = await solver.solve(session)

        click.echo(
            f"Result: {result.outcome.value} "
            f"(attempts={result.attempts}, "
            f"duration={result.duration_s:.1f}s)"
        )
        if result.detail:
            click.echo(f"Detail: {result.detail}")

        if result.outcome.value != "success":
            sys.exit(2)


@main.command("targets")
def targets() -> None:
    """List all debuggable CDP targets/pages."""
    settings = get_settings()
    rows = asyncio.run(list_targets(settings.cdp.host, settings.cdp.port))
    if not rows:
        click.echo("No targets found. Is Chrome running with --remote-debugging-port?")
        sys.exit(1)
    for t in rows:
        click.echo(f"{t.type:<10} {t.target_id:<36} {t.url[:80]}")


@main.command("memory-stats")
def memory_stats() -> None:
    """Show experience memory statistics."""
    settings = get_settings()

    async def _stats() -> None:
        async with ExperienceMemory(settings.memory) as mem:
            stats = await mem.stats()
            click.echo(f"Status: {stats.get('status')}")
            click.echo(f"Total entries: {stats.get('total_entries', 0)}")
            for domain in stats.get("per_domain", []):
                click.echo(
                    f"  {domain['host']:<30} "
                    f"{domain['captcha_type']:<12} "
                    f"{domain['count']:>4} solves  "
                    f"avg dx={domain['avg_dx']:.0f}px"
                )

    asyncio.run(_stats())


@main.command("memory-clear")
def memory_clear() -> None:
    """Clear all experience memory."""
    settings = get_settings()

    async def _clear() -> None:
        async with ExperienceMemory(settings.memory) as mem:
            db = mem._db
            if db:
                await db.execute("DELETE FROM trajectories")
                await db.commit()
                click.echo("Experience memory cleared.")

    asyncio.run(_clear())


if __name__ == "__main__":
    main()
