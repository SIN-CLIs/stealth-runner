"""
Anti-Detection Suite - Browser fingerprint randomization and human-like behavior.

Features:
    - Browser fingerprint randomization (canvas, webgl, audio)
    - Human-like mouse movements (bezier curves, micro-movements)
    - Realistic typing patterns (WPM variance, typos, corrections)
    - Session rotation (cookies, localStorage)
    - Proxy rotation with geo-targeting
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


class BrowserType(str, Enum):
    """Supported browser types for fingerprint generation."""
    CHROME = "chrome"
    FIREFOX = "firefox"
    SAFARI = "safari"
    EDGE = "edge"


@dataclass
class Fingerprint:
    """Browser fingerprint configuration."""
    user_agent: str
    screen_width: int
    screen_height: int
    color_depth: int
    timezone: str
    language: str
    platform: str
    hardware_concurrency: int
    device_memory: int
    webgl_vendor: str
    webgl_renderer: str
    canvas_hash: str
    audio_hash: str
    fonts: list[str] = field(default_factory=list)
    plugins: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "userAgent": self.user_agent,
            "screen": {"width": self.screen_width, "height": self.screen_height},
            "colorDepth": self.color_depth,
            "timezone": self.timezone,
            "language": self.language,
            "platform": self.platform,
            "hardwareConcurrency": self.hardware_concurrency,
            "deviceMemory": self.device_memory,
            "webgl": {"vendor": self.webgl_vendor, "renderer": self.webgl_renderer},
            "canvas": self.canvas_hash,
            "audio": self.audio_hash,
            "fonts": self.fonts,
            "plugins": self.plugins,
        }


@dataclass
class ProxyConfig:
    """Proxy configuration."""
    host: str
    port: int
    username: str | None = None
    password: str | None = None
    protocol: str = "http"
    country: str | None = None

    @property
    def url(self) -> str:
        auth = f"{self.username}:{self.password}@" if self.username else ""
        return f"{self.protocol}://{auth}{self.host}:{self.port}"


class FingerprintGenerator:
    """Generate realistic browser fingerprints."""

    # Common screen resolutions
    SCREEN_RESOLUTIONS = [
        (1920, 1080), (1366, 768), (1536, 864), (1440, 900),
        (1280, 720), (2560, 1440), (1600, 900), (1280, 800),
    ]

    # User agent templates
    USER_AGENTS = {
        BrowserType.CHROME: [
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        ],
        BrowserType.FIREFOX: [
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        ],
        BrowserType.SAFARI: [
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        ],
    }

    # WebGL configurations
    WEBGL_CONFIGS = [
        ("Intel Inc.", "Intel Iris OpenGL Engine"),
        ("Google Inc. (NVIDIA)", "ANGLE (NVIDIA GeForce GTX 1080 Direct3D11)"),
        ("Google Inc. (AMD)", "ANGLE (AMD Radeon Pro 5500M Direct3D11)"),
        ("Google Inc. (Intel)", "ANGLE (Intel UHD Graphics 630 Direct3D11)"),
    ]

    # Common fonts
    COMMON_FONTS = [
        "Arial", "Helvetica", "Times New Roman", "Georgia", "Verdana",
        "Courier New", "Comic Sans MS", "Impact", "Trebuchet MS", "Palatino",
    ]

    # Timezones
    TIMEZONES = [
        "America/New_York", "America/Chicago", "America/Denver",
        "America/Los_Angeles", "Europe/London", "Europe/Paris",
    ]

    def generate(self, browser: BrowserType = BrowserType.CHROME) -> Fingerprint:
        """Generate a realistic browser fingerprint."""
        resolution = random.choice(self.SCREEN_RESOLUTIONS)
        webgl = random.choice(self.WEBGL_CONFIGS)

        # Generate consistent hashes
        seed = random.randint(0, 2**32)
        canvas_hash = hashlib.md5(f"canvas_{seed}".encode()).hexdigest()[:16]
        audio_hash = hashlib.md5(f"audio_{seed}".encode()).hexdigest()[:16]

        # Select random subset of fonts
        fonts = random.sample(self.COMMON_FONTS, k=random.randint(5, 8))

        return Fingerprint(
            user_agent=random.choice(self.USER_AGENTS.get(browser, self.USER_AGENTS[BrowserType.CHROME])),
            screen_width=resolution[0],
            screen_height=resolution[1],
            color_depth=random.choice([24, 32]),
            timezone=random.choice(self.TIMEZONES),
            language=random.choice(["en-US", "en-GB", "en"]),
            platform=self._get_platform(browser),
            hardware_concurrency=random.choice([4, 8, 12, 16]),
            device_memory=random.choice([4, 8, 16]),
            webgl_vendor=webgl[0],
            webgl_renderer=webgl[1],
            canvas_hash=canvas_hash,
            audio_hash=audio_hash,
            fonts=fonts,
            plugins=[],
        )

    def _get_platform(self, browser: BrowserType) -> str:
        platforms = ["MacIntel", "Win32", "Linux x86_64"]
        return random.choice(platforms)


class MouseSimulator:
    """Simulate human-like mouse movements."""

    def __init__(self, speed_factor: float = 1.0):
        self.speed_factor = speed_factor
        self._last_position = (0, 0)

    def generate_path(
        self,
        start: tuple[int, int],
        end: tuple[int, int],
        steps: int | None = None,
    ) -> list[tuple[int, int, float]]:
        """
        Generate human-like mouse path using bezier curves.
        
        Returns list of (x, y, delay_ms) tuples.
        """
        if steps is None:
            distance = math.sqrt((end[0] - start[0])**2 + (end[1] - start[1])**2)
            steps = max(10, int(distance / 10))

        # Generate control points for bezier curve
        control1 = self._random_control_point(start, end)
        control2 = self._random_control_point(start, end)

        path = []
        for i in range(steps + 1):
            t = i / steps
            
            # Cubic bezier
            x = int(
                (1-t)**3 * start[0] +
                3 * (1-t)**2 * t * control1[0] +
                3 * (1-t) * t**2 * control2[0] +
                t**3 * end[0]
            )
            y = int(
                (1-t)**3 * start[1] +
                3 * (1-t)**2 * t * control1[1] +
                3 * (1-t) * t**2 * control2[1] +
                t**3 * end[1]
            )

            # Add micro-jitter
            if i > 0 and i < steps:
                x += random.randint(-2, 2)
                y += random.randint(-2, 2)

            # Variable delay (slower at start/end, faster in middle)
            speed_curve = math.sin(t * math.pi)
            base_delay = 5 + (1 - speed_curve) * 15
            delay = base_delay * self.speed_factor * random.uniform(0.8, 1.2)

            path.append((x, y, delay))

        self._last_position = end
        return path

    def _random_control_point(
        self,
        start: tuple[int, int],
        end: tuple[int, int],
    ) -> tuple[int, int]:
        """Generate random control point for bezier curve."""
        mid_x = (start[0] + end[0]) / 2
        mid_y = (start[1] + end[1]) / 2

        # Add randomness perpendicular to the line
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        distance = math.sqrt(dx**2 + dy**2)

        if distance == 0:
            return (int(mid_x), int(mid_y))

        # Perpendicular offset
        offset = random.uniform(-0.3, 0.3) * distance
        perp_x = -dy / distance * offset
        perp_y = dx / distance * offset

        # Position along the line
        t = random.uniform(0.3, 0.7)
        x = start[0] + dx * t + perp_x
        y = start[1] + dy * t + perp_y

        return (int(x), int(y))

    def generate_click_sequence(
        self,
        position: tuple[int, int],
        click_type: str = "single",
    ) -> list[dict]:
        """Generate realistic click sequence with pre/post movements."""
        sequence = []

        # Small approach movement
        approach_offset = (
            random.randint(-5, 5),
            random.randint(-5, 5),
        )
        approach_pos = (
            position[0] + approach_offset[0],
            position[1] + approach_offset[1],
        )

        # Move to approach position
        if self._last_position != approach_pos:
            path = self.generate_path(self._last_position, approach_pos)
            for x, y, delay in path:
                sequence.append({"type": "move", "x": x, "y": y, "delay": delay})

        # Final approach to click position
        final_path = self.generate_path(approach_pos, position, steps=5)
        for x, y, delay in final_path:
            sequence.append({"type": "move", "x": x, "y": y, "delay": delay})

        # Click with realistic timing
        if click_type == "double":
            sequence.append({"type": "mousedown", "delay": random.uniform(10, 30)})
            sequence.append({"type": "mouseup", "delay": random.uniform(50, 100)})
            sequence.append({"type": "mousedown", "delay": random.uniform(80, 150)})
            sequence.append({"type": "mouseup", "delay": random.uniform(50, 100)})
        else:
            sequence.append({"type": "mousedown", "delay": random.uniform(10, 30)})
            sequence.append({"type": "mouseup", "delay": random.uniform(80, 150)})

        # Small post-click drift
        drift = (
            position[0] + random.randint(-3, 3),
            position[1] + random.randint(-3, 3),
        )
        sequence.append({"type": "move", "x": drift[0], "y": drift[1], "delay": random.uniform(50, 100)})

        self._last_position = drift
        return sequence


class TypingSimulator:
    """Simulate human-like typing patterns."""

    # Average WPM ranges by typing skill
    WPM_RANGES = {
        "slow": (20, 35),
        "average": (35, 50),
        "fast": (50, 70),
        "expert": (70, 100),
    }

    # Common typo patterns
    TYPO_PATTERNS = {
        "a": ["s", "q", "z"],
        "s": ["a", "d", "w"],
        "d": ["s", "f", "e"],
        "e": ["w", "r", "d"],
        "r": ["e", "t", "f"],
        "t": ["r", "y", "g"],
        "i": ["u", "o", "k"],
        "o": ["i", "p", "l"],
        "n": ["b", "m", "h"],
        "m": ["n", ",", "j"],
    }

    def __init__(
        self,
        skill_level: str = "average",
        typo_rate: float = 0.02,
        correction_rate: float = 0.8,
    ):
        self.skill_level = skill_level
        self.typo_rate = typo_rate
        self.correction_rate = correction_rate
        self.wpm_range = self.WPM_RANGES.get(skill_level, self.WPM_RANGES["average"])

    def generate_keystrokes(self, text: str) -> list[dict]:
        """
        Generate realistic keystroke sequence for given text.
        
        Returns list of {"key": str, "delay": float} dicts.
        """
        keystrokes = []
        current_wpm = random.uniform(*self.wpm_range)
        base_delay = 60000 / (current_wpm * 5)  # ms per character

        i = 0
        while i < len(text):
            char = text[i]

            # Occasionally introduce typo
            if random.random() < self.typo_rate and char.lower() in self.TYPO_PATTERNS:
                typo_char = random.choice(self.TYPO_PATTERNS[char.lower()])
                
                # Type the typo
                keystrokes.append({
                    "key": typo_char,
                    "delay": self._get_delay(base_delay),
                })

                # Maybe correct it
                if random.random() < self.correction_rate:
                    # Pause before noticing
                    keystrokes.append({
                        "key": "Backspace",
                        "delay": random.uniform(200, 500),
                    })
                    # Type correct character
                    keystrokes.append({
                        "key": char,
                        "delay": self._get_delay(base_delay),
                    })
                else:
                    i += 1
                    continue

            # Normal keystroke
            keystrokes.append({
                "key": char,
                "delay": self._get_delay(base_delay, char),
            })

            # Occasional pause (thinking)
            if random.random() < 0.05:
                keystrokes[-1]["delay"] += random.uniform(200, 800)

            # Speed variation over time
            if random.random() < 0.1:
                current_wpm = random.uniform(*self.wpm_range)
                base_delay = 60000 / (current_wpm * 5)

            i += 1

        return keystrokes

    def _get_delay(self, base_delay: float, char: str = "") -> float:
        """Calculate delay with realistic variance."""
        # Longer delay for special characters
        modifier = 1.0
        if char in ".,!?;:":
            modifier = 1.3
        elif char == " ":
            modifier = 0.8
        elif char.isupper():
            modifier = 1.2
        elif char.isdigit():
            modifier = 1.4

        # Add randomness
        delay = base_delay * modifier * random.uniform(0.7, 1.4)
        return max(30, delay)  # Minimum 30ms


class SessionManager:
    """Manage browser sessions with rotation."""

    def __init__(
        self,
        session_dir: str | Path = "~/.survey_agent/sessions",
        max_sessions: int = 10,
    ):
        self.session_dir = Path(session_dir).expanduser()
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.max_sessions = max_sessions
        self._current_session: str | None = None

    def create_session(self, fingerprint: Fingerprint) -> str:
        """Create new browser session."""
        session_id = hashlib.md5(
            f"{time.time()}_{random.random()}".encode()
        ).hexdigest()[:12]

        session_path = self.session_dir / session_id
        session_path.mkdir(exist_ok=True)

        # Save fingerprint
        with open(session_path / "fingerprint.json", "w") as f:
            json.dump(fingerprint.to_dict(), f, indent=2)

        # Initialize empty cookies
        with open(session_path / "cookies.json", "w") as f:
            json.dump([], f)

        self._current_session = session_id
        self._cleanup_old_sessions()

        logger.info(f"Created session: {session_id}")
        return session_id

    def load_session(self, session_id: str) -> dict | None:
        """Load existing session data."""
        session_path = self.session_dir / session_id
        if not session_path.exists():
            return None

        data = {}
        
        fp_path = session_path / "fingerprint.json"
        if fp_path.exists():
            with open(fp_path) as f:
                data["fingerprint"] = json.load(f)

        cookies_path = session_path / "cookies.json"
        if cookies_path.exists():
            with open(cookies_path) as f:
                data["cookies"] = json.load(f)

        return data

    def save_cookies(self, session_id: str, cookies: list[dict]) -> None:
        """Save cookies for session."""
        session_path = self.session_dir / session_id
        if session_path.exists():
            with open(session_path / "cookies.json", "w") as f:
                json.dump(cookies, f, indent=2)

    def delete_session(self, session_id: str) -> None:
        """Delete a session."""
        session_path = self.session_dir / session_id
        if session_path.exists():
            import shutil
            shutil.rmtree(session_path)
            logger.info(f"Deleted session: {session_id}")

    def rotate_session(self) -> str:
        """Create new session for rotation."""
        if self._current_session:
            self.delete_session(self._current_session)

        generator = FingerprintGenerator()
        fingerprint = generator.generate()
        return self.create_session(fingerprint)

    def _cleanup_old_sessions(self) -> None:
        """Remove oldest sessions if exceeding max."""
        sessions = sorted(
            self.session_dir.iterdir(),
            key=lambda p: p.stat().st_mtime,
        )

        while len(sessions) > self.max_sessions:
            oldest = sessions.pop(0)
            if oldest.is_dir():
                import shutil
                shutil.rmtree(oldest)
                logger.info(f"Cleaned up old session: {oldest.name}")


class ProxyRotator:
    """Manage proxy rotation."""

    def __init__(
        self,
        proxies: list[ProxyConfig] | None = None,
        rotation_interval: int = 300,
    ):
        self.proxies = proxies or []
        self.rotation_interval = rotation_interval
        self._current_index = 0
        self._last_rotation = time.time()

    def add_proxy(self, proxy: ProxyConfig) -> None:
        """Add proxy to rotation pool."""
        self.proxies.append(proxy)

    def get_proxy(self, country: str | None = None) -> ProxyConfig | None:
        """Get current proxy, optionally filtered by country."""
        if not self.proxies:
            return None

        # Filter by country if specified
        if country:
            filtered = [p for p in self.proxies if p.country == country]
            if filtered:
                return random.choice(filtered)

        # Check if rotation needed
        if time.time() - self._last_rotation > self.rotation_interval:
            self._rotate()

        return self.proxies[self._current_index]

    def _rotate(self) -> None:
        """Rotate to next proxy."""
        if self.proxies:
            self._current_index = (self._current_index + 1) % len(self.proxies)
            self._last_rotation = time.time()
            logger.info(f"Rotated to proxy: {self.proxies[self._current_index].host}")

    def mark_failed(self, proxy: ProxyConfig) -> None:
        """Mark proxy as failed and rotate."""
        logger.warning(f"Proxy failed: {proxy.host}")
        self._rotate()


class StealthBrowser:
    """
    Stealth browser wrapper with anti-detection features.
    
    Combines fingerprint, mouse, typing, session, and proxy management.
    """

    def __init__(
        self,
        fingerprint: Fingerprint | None = None,
        proxy: ProxyConfig | None = None,
        session_id: str | None = None,
    ):
        self.fingerprint_generator = FingerprintGenerator()
        self.fingerprint = fingerprint or self.fingerprint_generator.generate()
        self.proxy = proxy

        self.mouse = MouseSimulator()
        self.typing = TypingSimulator()
        self.session_manager = SessionManager()

        if session_id:
            self._session_id = session_id
        else:
            self._session_id = self.session_manager.create_session(self.fingerprint)

    def get_browser_args(self) -> list[str]:
        """Get browser launch arguments for stealth."""
        return [
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--disable-dev-shm-usage",
            "--disable-browser-side-navigation",
            "--disable-gpu",
            "--no-sandbox",
            f"--window-size={self.fingerprint.screen_width},{self.fingerprint.screen_height}",
            f"--user-agent={self.fingerprint.user_agent}",
        ]

    def get_stealth_scripts(self) -> str:
        """Get JavaScript to inject for stealth."""
        return f"""
        // Override navigator properties
        Object.defineProperty(navigator, 'webdriver', {{get: () => undefined}});
        Object.defineProperty(navigator, 'plugins', {{get: () => [{len(self.fingerprint.plugins)}]}});
        Object.defineProperty(navigator, 'languages', {{get: () => ['{self.fingerprint.language}']}});
        Object.defineProperty(navigator, 'hardwareConcurrency', {{get: () => {self.fingerprint.hardware_concurrency}}});
        Object.defineProperty(navigator, 'deviceMemory', {{get: () => {self.fingerprint.device_memory}}});
        
        // Override WebGL
        const getParameter = WebGLRenderingContext.prototype.getParameter;
        WebGLRenderingContext.prototype.getParameter = function(parameter) {{
            if (parameter === 37445) return '{self.fingerprint.webgl_vendor}';
            if (parameter === 37446) return '{self.fingerprint.webgl_renderer}';
            return getParameter.call(this, parameter);
        }};
        
        // Override screen
        Object.defineProperty(screen, 'width', {{get: () => {self.fingerprint.screen_width}}});
        Object.defineProperty(screen, 'height', {{get: () => {self.fingerprint.screen_height}}});
        Object.defineProperty(screen, 'colorDepth', {{get: () => {self.fingerprint.color_depth}}});
        
        // Remove automation indicators
        delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
        delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
        delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
        """

    async def human_click(self, x: int, y: int) -> list[dict]:
        """Generate human-like click at position."""
        return self.mouse.generate_click_sequence((x, y))

    async def human_type(self, text: str) -> list[dict]:
        """Generate human-like typing sequence."""
        return self.typing.generate_keystrokes(text)

    def rotate_session(self) -> None:
        """Rotate to new session with new fingerprint."""
        self.fingerprint = self.fingerprint_generator.generate()
        self._session_id = self.session_manager.rotate_session()

    @property
    def session_id(self) -> str:
        return self._session_id
