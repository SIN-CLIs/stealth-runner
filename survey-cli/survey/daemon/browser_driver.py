"""
Browser Driver - Playwright-based stealth browser automation.

Integrates with StealthBrowser for anti-detection and human-like behavior.

SR-150 extensions:
    - drag_element(source_sel, target_sel) — CDP-based drag operation
    - play_media(selector, max_seconds) — play video/audio and wait
"""

from __future__ import annotations

import asyncio
import logging
import random
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator

from .stealth import (
    StealthBrowser,
    Fingerprint,
    ProxyConfig,
)

logger = logging.getLogger(__name__)


@dataclass
class ElementInfo:
    """Information about a DOM element."""

    selector: str
    tag: str
    text: str
    attributes: dict[str, str]
    bounding_box: dict[str, float] | None
    is_visible: bool
    is_enabled: bool


class BrowserDriver:
    """
    Stealth browser driver using Playwright.

    Provides high-level API for survey automation with
    built-in anti-detection and human-like behavior.

    SR-150: drag_element(), play_media() primitives added.
    """

    def __init__(
        self,
        headless: bool = True,
        proxy: ProxyConfig | None = None,
        fingerprint: Fingerprint | None = None,
    ):
        self.headless = headless
        self.stealth = StealthBrowser(fingerprint=fingerprint, proxy=proxy)
        self._browser = None
        self._context = None
        self._page = None

    async def start(self) -> None:
        """Start browser with stealth configuration."""
        try:
            from ._playwright_compat import BACKEND_NAME, get_async_playwright
            async_playwright = get_async_playwright()
        except ImportError:
            logger.error(
                "Neither patchright nor playwright is installed. "
                "Run: pip install patchright && patchright install chromium"
            )
            raise

        logger.info(f"Browser backend selected: {BACKEND_NAME}")
        self._playwright = await async_playwright().start()

        launch_args = self.stealth.get_browser_args()

        proxy_config = None
        if self.stealth.proxy:
            proxy_config = {
                "server": self.stealth.proxy.url,
            }
            if self.stealth.proxy.username:
                proxy_config["username"] = self.stealth.proxy.username
                proxy_config["password"] = self.stealth.proxy.password

        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=launch_args,
        )

        # Create context with fingerprint
        fp = self.stealth.fingerprint
        self._context = await self._browser.new_context(
            viewport={"width": fp.screen_width, "height": fp.screen_height},
            user_agent=fp.user_agent,
            locale=fp.language,
            timezone_id=fp.timezone,
            proxy=proxy_config,
        )

        self._page = await self._context.new_page()

        # Inject stealth scripts
        await self._page.add_init_script(self.stealth.get_stealth_scripts())

        logger.info("Browser started with stealth configuration")

    async def stop(self) -> None:
        """Stop browser and cleanup."""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("Browser stopped")

    @asynccontextmanager
    async def session(self) -> AsyncIterator["BrowserDriver"]:
        """Context manager for browser session."""
        await self.start()
        try:
            yield self
        finally:
            await self.stop()

    async def goto(self, url: str, wait_until: str = "networkidle") -> None:
        """Navigate to URL with human-like delay."""
        # Random pre-navigation delay
        await asyncio.sleep(0.5 + 1.5 * asyncio.get_event_loop().time() % 1)

        await self._page.goto(url, wait_until=wait_until)

        # Post-navigation delay (simulating page scanning)
        await asyncio.sleep(1 + 2 * asyncio.get_event_loop().time() % 1)

        logger.info(f"Navigated to: {url}")

    async def get_html(self) -> str:
        """Get current page HTML."""
        return await self._page.content()

    async def get_url(self) -> str:
        """Get current page URL."""
        return self._page.url

    async def find_element(self, selector: str) -> ElementInfo | None:
        """Find element and return info."""
        try:
            element = await self._page.query_selector(selector)
            if not element:
                return None

            tag = await element.evaluate("el => el.tagName.toLowerCase()")
            text = await element.inner_text() if tag not in ["input", "select"] else ""

            attrs = await element.evaluate("""
                el => {
                    const attrs = {};
                    for (const attr of el.attributes) {
                        attrs[attr.name] = attr.value;
                    }
                    return attrs;
                }
            """)

            box = await element.bounding_box()
            is_visible = await element.is_visible()
            is_enabled = await element.is_enabled()

            return ElementInfo(
                selector=selector,
                tag=tag,
                text=text.strip() if text else "",
                attributes=attrs,
                bounding_box=box,
                is_visible=is_visible,
                is_enabled=is_enabled,
            )
        except Exception as e:
            logger.warning(f"Error finding element {selector}: {e}")
            return None

    async def find_elements(self, selector: str) -> list[ElementInfo]:
        """Find all matching elements."""
        elements = await self._page.query_selector_all(selector)
        results = []

        for i, element in enumerate(elements):
            try:
                tag = await element.evaluate("el => el.tagName.toLowerCase()")
                text = await element.inner_text() if tag not in ["input", "select"] else ""
                box = await element.bounding_box()
                is_visible = await element.is_visible()

                results.append(
                    ElementInfo(
                        selector=f"{selector}:nth-child({i + 1})",
                        tag=tag,
                        text=text.strip() if text else "",
                        attributes={},
                        bounding_box=box,
                        is_visible=is_visible,
                        is_enabled=True,
                    )
                )
            except Exception:
                continue

        return results

    async def human_click(self, selector: str) -> bool:
        """Click element with human-like mouse movement."""
        element = await self._page.query_selector(selector)
        if not element:
            logger.warning(f"Element not found: {selector}")
            return False

        box = await element.bounding_box()
        if not box:
            logger.warning(f"Element has no bounding box: {selector}")
            return False

        # Calculate click position (with slight randomness)
        target_x = int(box["x"] + box["width"] * (0.3 + 0.4 * asyncio.get_event_loop().time() % 1))
        target_y = int(box["y"] + box["height"] * (0.3 + 0.4 * asyncio.get_event_loop().time() % 1))

        # Generate mouse path
        current_pos = await self._page.evaluate(
            "() => ({x: window.mouseX || 0, y: window.mouseY || 0})"
        )
        path = self.stealth.mouse.generate_path(
            (current_pos.get("x", 0), current_pos.get("y", 0)),
            (target_x, target_y),
        )

        # Execute mouse movement
        for x, y, delay in path:
            await self._page.mouse.move(x, y)
            await asyncio.sleep(delay / 1000)

        # Click with realistic timing
        await self._page.mouse.down()
        await asyncio.sleep(0.05 + 0.1 * asyncio.get_event_loop().time() % 1)
        await self._page.mouse.up()

        logger.debug(f"Clicked element: {selector}")
        return True

    async def human_type(self, selector: str, text: str) -> bool:
        """Type text with human-like keystroke patterns."""
        element = await self._page.query_selector(selector)
        if not element:
            logger.warning(f"Element not found: {selector}")
            return False

        # Click to focus
        await self.human_click(selector)
        await asyncio.sleep(0.2)

        # Clear existing content
        await element.evaluate("el => el.value = ''")

        # Generate keystrokes
        keystrokes = self.stealth.typing.generate_keystrokes(text)

        for keystroke in keystrokes:
            key = keystroke["key"]
            delay = keystroke["delay"]

            if key == "Backspace":
                await self._page.keyboard.press("Backspace")
            elif len(key) == 1:
                await self._page.keyboard.type(key)
            else:
                await self._page.keyboard.press(key)

            await asyncio.sleep(delay / 1000)

        logger.debug(f"Typed text in: {selector}")
        return True

    async def select_option(self, selector: str, value: str) -> bool:
        """Select dropdown option."""
        try:
            await self.human_click(selector)
            await asyncio.sleep(0.3)
            await self._page.select_option(selector, value)
            return True
        except Exception as e:
            logger.warning(f"Error selecting option: {e}")
            return False

    async def check_checkbox(self, selector: str, checked: bool = True) -> bool:
        """Check or uncheck checkbox."""
        element = await self._page.query_selector(selector)
        if not element:
            return False

        is_checked = await element.is_checked()
        if is_checked != checked:
            await self.human_click(selector)

        return True

    async def scroll_to(self, selector: str) -> None:
        """Scroll element into view with human-like behavior."""
        element = await self._page.query_selector(selector)
        if element:
            # Smooth scroll
            await element.evaluate("""
                el => el.scrollIntoView({behavior: 'smooth', block: 'center'})
            """)
            await asyncio.sleep(0.5 + 0.5 * asyncio.get_event_loop().time() % 1)

    async def scroll_page(self, direction: str = "down", amount: int = 300) -> None:
        """Scroll page with human-like behavior."""
        if direction == "down":
            delta = amount
        else:
            delta = -amount

        # Multiple small scrolls
        steps = 5
        for _ in range(steps):
            await self._page.mouse.wheel(0, delta // steps)
            await asyncio.sleep(0.05 + 0.1 * asyncio.get_event_loop().time() % 1)

    async def wait_for_selector(
        self,
        selector: str,
        timeout: int = 30000,
        state: str = "visible",
    ) -> bool:
        """Wait for element to appear."""
        try:
            await self._page.wait_for_selector(selector, timeout=timeout, state=state)
            return True
        except Exception:
            return False

    async def wait_for_navigation(self, timeout: int = 30000) -> bool:
        """Wait for page navigation."""
        try:
            await self._page.wait_for_load_state("networkidle", timeout=timeout)
            return True
        except Exception:
            return False

    async def screenshot(self, path: str | Path) -> None:
        """Take screenshot."""
        await self._page.screenshot(path=str(path))

    async def evaluate(self, script: str) -> Any:
        """Evaluate JavaScript in page context."""
        return await self._page.evaluate(script)

    async def get_cookies(self) -> list[dict]:
        """Get all cookies."""
        return await self._context.cookies()

    async def set_cookies(self, cookies: list[dict]) -> None:
        """Set cookies."""
        await self._context.add_cookies(cookies)

    async def clear_cookies(self) -> None:
        """Clear all cookies."""
        await self._context.clear_cookies()

    def rotate_identity(self) -> None:
        """Rotate browser fingerprint and session."""
        self.stealth.rotate_session()
        logger.info("Rotated browser identity")

    # -------------------------------------------------------------------------
    # SR-150: Extended Primitives for drag-drop and media playback
    # -------------------------------------------------------------------------

    async def drag_element(
        self,
        source_sel: str,
        target_sel: str,
        jitter: bool = True,
    ) -> bool:
        """SR-150: Drag element from source to target using CDP mouse events.

        Implements realistic drag-and-drop with:
        - Human-like mouse path (10-step Bezier with timing jitter)
        - mouseDown → multiple mouseMoved → mouseUp sequence
        - No Playwright page.mouse.down() calls — pure CDP for stealth

        Args:
            source_sel: CSS selector for drag source element
            target_sel: CSS selector for drop target element
            jitter: Add random timing/position jitter (default True)

        Returns:
            True if drag completed successfully, False otherwise
        """
        try:
            # Get source element bounding box
            source = await self._page.query_selector(source_sel)
            if not source:
                logger.warning(f"Drag source not found: {source_sel}")
                return False

            source_box = await source.bounding_box()
            if not source_box:
                logger.warning(f"Drag source has no bounding box: {source_sel}")
                return False

            # Get target element bounding box
            target = await self._page.query_selector(target_sel)
            if not target:
                logger.warning(f"Drag target not found: {target_sel}")
                return False

            target_box = await target.bounding_box()
            if not target_box:
                logger.warning(f"Drag target has no bounding box: {target_sel}")
                return False

            # Calculate center points with optional jitter
            jitter_px = 5 if jitter else 0
            source_x = (
                source_box["x"] + source_box["width"] / 2 + random.randint(-jitter_px, jitter_px)
            )
            source_y = (
                source_box["y"] + source_box["height"] / 2 + random.randint(-jitter_px, jitter_px)
            )
            target_x = (
                target_box["x"] + target_box["width"] / 2 + random.randint(-jitter_px, jitter_px)
            )
            target_y = (
                target_box["y"] + target_box["height"] / 2 + random.randint(-jitter_px, jitter_px)
            )

            # Get CDP session
            cdp = await self._page.context.new_cdp_session(self._page)

            # Generate 10-step path with Bezier-like curve
            steps = 10
            path_points = []
            for i in range(steps + 1):
                t = i / steps
                # Quadratic bezier with control point offset for natural curve
                ctrl_x = (source_x + target_x) / 2 + (target_y - source_y) * 0.1
                ctrl_y = (source_y + target_y) / 2 - (target_x - source_x) * 0.1
                x = (1 - t) ** 2 * source_x + 2 * (1 - t) * t * ctrl_x + t**2 * target_x
                y = (1 - t) ** 2 * source_y + 2 * (1 - t) * t * ctrl_y + t**2 * target_y
                # Add micro-jitter
                if jitter and 0 < i < steps:
                    x += random.uniform(-2, 2)
                    y += random.uniform(-2, 2)
                path_points.append((x, y))

            # Move to source first
            await cdp.send(
                "Input.dispatchMouseEvent",
                {
                    "type": "mouseMoved",
                    "x": source_x,
                    "y": source_y,
                },
            )
            await asyncio.sleep(random.uniform(0.05, 0.15) if jitter else 0.05)

            # Mouse down
            await cdp.send(
                "Input.dispatchMouseEvent",
                {
                    "type": "mousePressed",
                    "x": source_x,
                    "y": source_y,
                    "button": "left",
                    "clickCount": 1,
                },
            )
            await asyncio.sleep(random.uniform(0.08, 0.15) if jitter else 0.1)

            # Drag along path
            for x, y in path_points[1:]:
                await cdp.send(
                    "Input.dispatchMouseEvent",
                    {
                        "type": "mouseMoved",
                        "x": x,
                        "y": y,
                        "button": "left",
                    },
                )
                delay = random.uniform(0.02, 0.06) if jitter else 0.03
                await asyncio.sleep(delay)

            # Mouse up at target
            await cdp.send(
                "Input.dispatchMouseEvent",
                {
                    "type": "mouseReleased",
                    "x": target_x,
                    "y": target_y,
                    "button": "left",
                    "clickCount": 1,
                },
            )

            await cdp.detach()
            logger.debug(f"Dragged {source_sel} → {target_sel}")
            return True

        except Exception as e:
            logger.warning(f"Drag failed: {e}")
            return False

    async def play_media(
        self,
        selector: str,
        max_seconds: float | None = None,
    ) -> float:
        """SR-150: Play video/audio element and wait for completion.

        Uses CDP Runtime.evaluate to control media playback directly.
        Waits for the 'ended' event or max_seconds timeout.

        Args:
            selector: CSS selector for <video> or <audio> element
            max_seconds: Maximum seconds to wait (None = wait for full duration)

        Returns:
            Actual seconds played (may be less than duration if max_seconds hit)
        """
        try:
            # Get element and verify it's a media element
            element = await self._page.query_selector(selector)
            if not element:
                logger.warning(f"Media element not found: {selector}")
                return 0.0

            tag = await element.evaluate("el => el.tagName.toLowerCase()")
            if tag not in ("video", "audio"):
                logger.warning(f"Element is not a media element: {selector} (tag={tag})")
                return 0.0

            # Get media duration via CDP
            cdp = await self._page.context.new_cdp_session(self._page)

            # Get duration
            duration_result = await cdp.send(
                "Runtime.evaluate",
                {
                    "expression": f"document.querySelector('{selector}').duration || 30",
                    "returnByValue": True,
                },
            )
            duration = duration_result.get("result", {}).get("value", 30.0)

            # Cap at max_seconds if specified
            if max_seconds is not None and duration > max_seconds:
                duration = max_seconds

            # Warn for very long media
            if duration > 120:
                logger.warning(f"Long media detected ({duration}s), proceeding anyway: {selector}")

            # For audio, mute before playing (avoid noise on host)
            if tag == "audio":
                await cdp.send(
                    "Runtime.evaluate",
                    {
                        "expression": f"document.querySelector('{selector}').muted = true",
                    },
                )

            # Start playback
            await cdp.send(
                "Runtime.evaluate",
                {
                    "expression": f"document.querySelector('{selector}').play()",
                },
            )
            logger.debug(f"Started playing {tag}: {selector} (duration={duration}s)")

            # Wait for media to complete (with small jitter buffer)
            jitter = random.uniform(0.3, 0.8)
            await asyncio.sleep(duration + jitter)

            # Pause to ensure clean state
            await cdp.send(
                "Runtime.evaluate",
                {
                    "expression": f"document.querySelector('{selector}').pause()",
                },
            )

            await cdp.detach()
            logger.debug(f"Finished playing {tag}: {selector}")
            return duration

        except Exception as e:
            logger.warning(f"Media playback failed: {e}")
            return 0.0

    async def click_at(self, x: int, y: int) -> bool:
        """Click at specific coordinates (for hotspot questions).

        Args:
            x: X coordinate
            y: Y coordinate

        Returns:
            True if click succeeded
        """
        try:
            cdp = await self._page.context.new_cdp_session(self._page)

            # Move to position
            await cdp.send(
                "Input.dispatchMouseEvent",
                {
                    "type": "mouseMoved",
                    "x": x,
                    "y": y,
                },
            )
            await asyncio.sleep(random.uniform(0.05, 0.1))

            # Click
            await cdp.send(
                "Input.dispatchMouseEvent",
                {
                    "type": "mousePressed",
                    "x": x,
                    "y": y,
                    "button": "left",
                    "clickCount": 1,
                },
            )
            await asyncio.sleep(random.uniform(0.05, 0.1))

            await cdp.send(
                "Input.dispatchMouseEvent",
                {
                    "type": "mouseReleased",
                    "x": x,
                    "y": y,
                    "button": "left",
                    "clickCount": 1,
                },
            )

            await cdp.detach()
            logger.debug(f"Clicked at ({x}, {y})")
            return True

        except Exception as e:
            logger.warning(f"Click at coordinates failed: {e}")
            return False
