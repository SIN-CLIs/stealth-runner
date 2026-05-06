# @stealth/captcha — Stealth Suite Integration Guide

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    STEALTH SUITE PIPELINE                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  @stealth/perception                                        │
│    → OBSERVE: screenshots + AX tree                         │
│    → Detect captcha: .gc-drag-block in DOM?                 │
│         │                                                    │
│         ▼                                                    │
│  @stealth/captcha (THIS PACKAGE)                             │
│    → ACT: CDP Input.dispatchMouseEvent                      │
│    → StealthInjector → Page.addScriptToEvaluateOnNewDocument│
│    → HitTester → elementFromPoint + overlay neutralization  │
│    → GapDetector → DOM getBoundingClientRect                │
│    → TrajectoryGenerator → human-like Bezier + jitter      │
│    → Verifier → DOM polling for .gc-success/.gc-fail       │
│    → ExperienceMemory → sqlite persistence                 │
│         │                                                    │
│         ▼                                                    │
│  @stealth/core                                                │
│    → Continue pipeline                                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Integration Points

### 1. Package Structure (Turborepo)

```
py-packages/captchas/
├── __init__.py              # ← Public API
├── config.py                # ← Pydantic settings (12-factor)
├── exceptions.py            # ← Exception hierarchy
├── cli.py                   # ← Click CLI: solve-slide, targets, memory-stats
├── bridge.py                # ← Backward compat API for old GoCaptchaSolver
├── cdp/
│   ├── client.py            # ← Async CDP WebSocket + session management
│   ├── browser.py           # ← Stealth Chrome launcher
│   └── targets.py           # ← Target discovery (/json, /json/version)
├── stealth/
│   ├── patches.py           # ← JS bundle builder + injector
│   └── scripts/
│       ├── stealth_main.js  # ← navigator.webdriver, plugins, chrome, etc.
│       └── __init__.py
├── primitives/
│   ├── trajectory.py        # ← Bezier + jitter + overshoot
│   ├── hit_test.py          # ← elementFromPoint + overlay neutralization
│   ├── gap_detector.py      # ← DOM getBoundingClientRect gap measurement
│   └── verify.py            # ← DOM polling for success/failure
├── solver/
│   ├── base.py              # ← Abstract base + SolveResult
│   ├── slide.py             # ← GoCaptcha/NetEase/GeeTest slide solver
│   ├── text.py              # ← OCR text captcha solver
│   └── drag_drop.py         # ← Puzzle drag-drop solver
├── memory/
│   └── experience.py        # ← SQLite episodic trajectory cache
├── telemetry/
│   └── tracer.py            # ← structlog logger
├── payloads/
│   ├── gocaptcha_slide.js   # ← Legacy dispatchEvent approach (REFERENCE)
│   └── __init__.py
└── pyproject.toml
```

### 2. @stealth/actuation Integration

In `py-packages/drivers/`, add a new module:

```python
# py-packages/drivers/cdp_client.py
"""CDP client adapter for @stealth/actuation — connects perception to actuation."""

from stealth_captcha.cdp.client import CDPClient
from stealth_captcha.cdp.targets import get_browser_ws, find_page

async def get_cdp_session(url_substring: str = None):
    """Get a CDP session for the first page matching url_substring."""
    ws = await get_browser_ws()
    client = await CDPClient.connect(ws)
    if url_substring:
        target = await find_page(url_substring)
        if not target:
            await client.aclose()
            raise RuntimeError(f"No page found matching: {url_substring}")
    else:
        from stealth_captcha.cdp.targets import create_tab
        target = await create_tab()
    session = await client.attach(target.target_id)
    return client, session
```

### 3. Pipeline Hook (@stealth/core)

In the ACT step of `@stealth/core`:

```python
from stealth_captcha import SlideCaptchaSolver
from stealth_captcha.cdp.client import CDPClient

async def act_captcha(plan, observation):
    """Called when OBSERVE step detects a captcha."""
    if "captcha" not in (observation.get("tags") or []):
        return None  # Not a captcha — skip
    
    ws_url = observation.get("cdp_ws")
    async with await CDPClient.connect(ws_url) as client:
        session = await client.attach(observation["target_id"])
        solver = SlideCaptchaSolver()
        result = await solver.solve(session)
        return result
```

### 4. Environment Variables (12-Factor)

| Variable | Default | Purpose |
|----------|---------|---------|
| `STEALTH_CDP__PORT` | `9222` | Chrome remote debugging port |
| `STEALTH_CDP__HOST` | `127.0.0.1` | Chrome host |
| `STEALTH_TRAJ__DURATION_MIN_MS` | `800` | Min drag duration (ms) |
| `STEALTH_TRAJ__DURATION_MAX_MS` | `1600` | Max drag duration (ms) |
| `STEALTH_SOLVER__MAX_RETRIES` | `3` | Solve retry count |
| `STEALTH_SOLVER__VERIFY_TIMEOUT_S` | `4.0` | Verification timeout |
| `STEALTH_MEM__DB_PATH` | `~/.stealth-suite/captcha-experience.db` | SQLite memory path |
| `STEALTH_CHROME__HEADLESS` | `false` | Run Chrome headless |
| `NVIDIA_API_KEY` | — | For Pixtral OCR backend |

## Migration from Old GoCaptchaSolver

The old `py-packages/captchas/gocaptcha.py` used `dispatchEvent(PointerEvent)`
which produces `isTrusted: false` events — unconditionally blocked by GoCaptcha.
The new `SlideCaptchaSolver` uses CDP `Input.dispatchMouseEvent` — trusted events
at the element level.

**Old code (broken):**
```python
solver = GoCaptchaSolver(pid=71104, wid=56640)
solver.solve()
# → dispatchEvent → isTrusted: false → never works
```

**New code (works):**
```python
# In ACT step:
from stealth_captcha import SlideCaptchaSolver
solver = SlideCaptchaSolver()
result = await solver.solve(cdp_session)
# → CDP Input.dispatchMouseEvent → isTrusted: true → works
```

**Bridge (old API, new engine):**
```python
from stealth_captcha.bridge import GoCaptchaSolver
solver = GoCaptchaSolver(cdp_ws="ws://127.0.0.1:9222/...")
result = solver.solve()
# → same API, but now uses CDP under the hood
```

## Verification

Run the test suite:
```bash
cd py-packages/captchas
pip install -e ".[dev]"
pytest tests/ -v
```

CLI smoke test:
```bash
stealth-captcha solve-slide \
  --url https://example.com/go-captcha \
  --use-existing-chrome
```
