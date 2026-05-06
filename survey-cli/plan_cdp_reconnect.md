# ✅ FIXED — 15 tests, LIVE-verified (0 "No such target" errors in production)

**What was implemented**: CDPConnection class (sync, 229 lines) — not async CDPClient from stealth-captcha as originally planned, but a custom sync class that achieves the same goal. Features: exponential backoff (0.3s → 0.6s → 1.2s → 2s), ID-based response routing via `_pending` dict (each send gets its own Future), auto-reconnect on "No such target" errors and connection resets, 5 retry attempts before raising error. No async refactor needed — `execute.py` stays sync. 15 regression tests pass, LIVE-verified: 0 "No such target" errors in the production survey run.

---

# Plan: P2 Fix — Stale CDP WS → CDPClient with Auto-Reconnect

## Problem
`execute.py` creates WebSocket to dashboard tab, caches WS URL, then creates new tab for survey:
- Dashboard WS becomes stale (tab navigated/closed)
- New tab WS not cached
- `execute()` uses cached dashboard WS → "No such target id" (500)

Also: `_refresh_tab_ws()` exists but doesn't work because it doesn't route responses to the right Future.

## Root Cause
1. `websocket.create_connection()` is synchronous, no reconnect logic
2. `_refresh_tab_ws()` calls `ws.recv()` expecting the SAME response type as original call — but the response has already been consumed by the reader loop
3. No event routing — all responses go to the same queue, not per-call Futures

## Fix Strategy: Import CDPClient from stealth-captcha

From `stealth-captcha/cdp/client.py` — production-ready, tested:
- `CDPClient.__init__(ws_url, max_retries=5, backoff=0.3)`
- `CDPClient.send(method, params)` → returns dict response (awaitable)
- `CDPClient.on(event, handler)` → registers event handler
- `CDPClient.close()` → cleanup
- Background `_reader_loop()` single task, routes ALL responses to Futures
- Exponential backoff: 0.3s → 0.6s → 1.2s → 2s (max)
- 5 attempts before raising `CDPConnectionError`

### Import into survey-cli

```python
# survey/execute.py
from pathlib import Path
import sys

# Add stealth-captcha to path
STEALTH_CAPTCHA = Path(__file__).parent.parent.parent / "stealth-captcha"
if STEALTH_CAPTCHA.exists():
    sys.path.insert(0, str(STEALTH_CAPTCHA))

from stealth_captcha.cdp.client import CDPClient
```

### Replace `websocket.create_connection()`

**Current** (`execute.py`):
```python
ws = websocket.create_connection(ws_url, timeout=15)
ws.settimeout(15)
```

**Fixed**:
```python
ws = CDPClient(ws_url, max_retries=5, backoff=0.3)
ws.connect()
```

### Replace all `ws.send()` + `ws.recv()` pairs

```python
# Current:
ws.send(json.dumps({"id": self._id, "method": method, "params": params}))
resp = ws.recv()
result = json.loads(resp)

# Fixed:
result = await ws.send(method, params)  # async/await or sync wrapper
```

### Sync wrapper for CDPClient (since execute.py is sync)

```python
def _sync_send(client, method, params):
    """Sync wrapper for async CDPClient.send()."""
    future = client._pending.get()
    client.ws.send(json.dumps({"id": next(client._id_ctr), "method": method, "params": params}))
    return json.loads(client.ws.recv())  # simplified — real impl uses Future
```

**Better approach**: Convert `execute()` to async using `run_sync()`:

```python
# survey/execute.py — top of file
import asyncio

async def execute_async(config, driver_info, survey, profile, dry_run=False):
    """Async version of execute() using CDPClient."""
    ws_url = driver_info.get("ws_url")
    ws = CDPClient(ws_url, max_retries=5, backoff=0.3)
    await ws.connect()

    result = await ws.send("Runtime.evaluate", {
        "expression": "document.body.innerText"
    })
    # ... rest of execute logic ...

    await ws.close()

def execute(config, driver_info, survey, profile, dry_run=False):
    """Sync wrapper — run_async_execution in event loop."""
    return asyncio.run(execute_async(config, driver_info, survey, profile, dry_run))
```

## Event Routing (Fixes `_refresh_tab_ws()`)

CDPClient routes responses to Futures by ID:
```python
# CDPClient._reader_loop():
future = self._pending.get(id)  # get specific Future by ID
future.set_result(response)
```

→ `_refresh_tab_ws()` can wait for specific response by ID.

## Auto-Reconnect Pattern

```python
async def _with_reconnect(self, method, params, max_attempts=5):
    for attempt in range(max_attempts):
        try:
            return await self.ws.send(method, params)
        except Exception as e:
            if "No such target" in str(e) and attempt < max_attempts - 1:
                # Tab closed — recreate
                self.ws = CDPClient(self._new_tab_url).connect()
                continue
            raise
```

## Files to Change

| File | Change | Risk |
|------|--------|------|
| `survey/execute.py` | Import CDPClient from stealth-captcha | Low |
| `survey/execute.py` | Add `asyncio.run(execute_async())` wrapper | Low |
| `survey/execute.py` | Replace ws.send/recv with CDPClient.send() | Medium — async refactor |
| `survey/execute.py` | Add `_with_reconnect()` wrapper for all CDP calls | Low |
| `survey/runner.py` | Update `_refresh_tab_ws()` to use CDPClient | Medium — event routing |
| `survey/runner.py` | Fix `_refresh_tab_ws()` response matching | Low |

## Tests to Add

```python
# tests/test_cdp_client.py (NEW)
class TestCDPClientReconnect:
    def test_auto_reconnects_on_no_such_target()
    def test_exponential_backoff_on_connection_failure()
    def test_max_retries_exceeded_raises_cdp_error()
    def test_event_routing_to_correct_future()
    def test_multiple_pending_calls_resolve_correctly()
    def test_close_cleans_up_reader_loop()

class TestExecuteReconnect:
    def test_execute_retries_on_stale_ws()
    def test_execute_creates_new_tab_on_ws_failure()
    def test_stealth_injected_on_new_tab()
```

## Verification

```bash
# Before: "No such target id" every survey
# After: CDPClient auto-reconnects, retries, succeeds
python3 -m survey run --mode loop --max 3 --debug
# Look for: "Retrying CDP call (attempt 2/5)"
```

## Estimate

- **Effort**: 4-5h (async refactor)
- **Impact**: Eliminates "No such target id" errors
- **Risk**: Medium — async refactor touches all of execute.py
