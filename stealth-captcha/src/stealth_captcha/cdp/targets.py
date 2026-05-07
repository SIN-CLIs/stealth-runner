"""Target discovery via CDP HTTP endpoints.

WARUM: Um eine CDP WebSocket-Verbindung aufzubauen, muss die WS-URL
bekannt sein. Chrome exposed /json und /json/version auf dem Remote-Debugging-Port.
Diese liefern die WS-URLs für jeden Tab. Ohne Target-Discovery kein CDP-Connect.

ARCHITEKTUR: Sync HTTP-Calls (httpx) gegen Chrome's JSON-API.
TargetInfo dataclass kapselt ws_url, id, title, url, type.
list_targets() returned alle Targets; find_page() filtert nach Page-Typ.
Kein State, keine Caching — bei jedem Call frisch aus Chrome gelesen.

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

from dataclasses import dataclass

import httpx

from stealth_captcha.exceptions import CDPConnectionError


@dataclass(slots=True, frozen=True)
class TargetInfo:
    """A CDP target (page, iframe, worker, etc.)."""

    target_id: str
    type: str
    url: str
    title: str
    websocket_debugger_url: str


async def list_targets(
    host: str = "127.0.0.1",
    port: int = 9222,
) -> list[TargetInfo]:
    """List all debuggable targets from /json.

    Returns:
        A list of TargetInfo for every open page, iframe, worker, etc.
    """
    url = f"http://{host}:{port}/json"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, ValueError) as e:
        raise CDPConnectionError(f"Cannot list targets at {url}: {e}") from e

    return [
        TargetInfo(
            target_id=t["id"],
            type=t.get("type", "unknown"),
            url=t.get("url", ""),
            title=t.get("title", ""),
            websocket_debugger_url=t.get("webSocketDebuggerUrl", ""),
        )
        for t in data
    ]


async def find_page(
    url_substring: str,
    *,
    host: str = "127.0.0.1",
    port: int = 9222,
) -> TargetInfo | None:
    """Find the first page target whose URL contains the given substring.

    Useful when navigating to a known captcha page.
    """
    targets = await list_targets(host=host, port=port)
    for t in targets:
        if t.type == "page" and url_substring in t.url:
            return t
    return None


async def get_browser_ws(
    host: str = "127.0.0.1",
    port: int = 9222,
) -> str:
    """Get the browser-level WebSocket debugger URL from /json/version.

    This is the root endpoint that enables attaching to any target.
    """
    url = f"http://{host}:{port}/json/version"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()["webSocketDebuggerUrl"]
    except (httpx.HTTPError, KeyError, ValueError) as e:
        raise CDPConnectionError(f"Cannot get browser WebSocket URL at {url}: {e}") from e


async def create_tab(
    url: str = "about:blank",
    *,
    host: str = "127.0.0.1",
    port: int = 9222,
) -> TargetInfo:
    """Create a new tab via /json/new and return its target info."""
    target_url = f"http://{host}:{port}/json/new?{url}"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.put(target_url)
            resp.raise_for_status()
            t = resp.json()
    except (httpx.HTTPError, ValueError) as e:
        raise CDPConnectionError(f"Cannot create tab: {e}") from e

    return TargetInfo(
        target_id=t["id"],
        type=t.get("type", "page"),
        url=t.get("url", url),
        title=t.get("title", ""),
        websocket_debugger_url=t.get("webSocketDebuggerUrl", ""),
    )
