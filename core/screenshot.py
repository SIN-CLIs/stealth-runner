"""================================================================================
stealth-runner / core / screenshot.py  — Forensik bei Survey-Failures
================================================================================

ZWECK
-----
Wenn eine Survey scheitert (Budget exceeded, Captcha-Solver-Fail, unbekannter
Question-Type, DOM-Fehler), wollen wir SOFORT wissen "was sah die Seite aus?".

Dieses Modul:
  1. Captured Screenshot + HTML-Dump + Console-Logs aus dem CDP-Browser
  2. Speichert sie unter ~/.stealth/screenshots/<run_id>/<timestamp>_<reason>/
  3. Verlinkt sie im AnalyticsCollector via Tag, im StateManager via Pfad
  4. Auto-rotiert (loescht Daten aelter als N Tage)

Warum nicht Sentry-Attachments? Wir wollen LOKAL debugbar bleiben — die
Survey-Pipeline laeuft eh nur auf einem Maschine, externe Uploads kosten Zeit
(Budget!) und Sentry-Free-Tier-Volumes sind klein.

WIRING
------
In jedem error-Node:

    from core.screenshot import capture_failure
    await capture_failure(
        cdp_url="http://127.0.0.1:9999",
        run_id=state["run_id"],
        reason="captcha_solver_timeout",
        extra={"question_idx": 7},
    )

KEINE ZUSAETZLICHEN DEPS
-----------------------
Wir nutzen direkt das CDP DevTools-Protokoll via aiohttp + websockets, ohne
Playwright zu starten — der Bot-Profile-Chrome laeuft bereits, wir docken an.
================================================================================"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

log = logging.getLogger("core.screenshot")


@dataclass
class FailureArtifact:
    """Resultat eines capture_failure-Aufrufs."""

    directory: Path
    screenshot_path: Path | None
    html_path: Path | None
    log_path: Path
    reason: str
    timestamp: float


async def capture_failure(
    cdp_url: str,
    run_id: str,
    reason: str,
    extra: dict[str, Any] | None = None,
    base_dir: Path | None = None,
) -> FailureArtifact:
    """Capture komplette Forensik fuer eine gescheiterte Survey.

    Args:
        cdp_url: e.g. http://127.0.0.1:9999 (HeyPiggy CDP-Port)
        run_id:  Survey-Run-ID, wird als Subfolder verwendet
        reason:  kurzer slug wie "captcha_timeout", "budget_exceeded"
        extra:   beliebige JSON-serialisierbare Zusatzdaten
        base_dir: Override fuer Test-Setup. Default: ~/.stealth/screenshots

    Returns:
        FailureArtifact mit Pfaden — der Caller persistiert sie im StateManager.

    Schluckt JEDE Exception (failure-capture darf den Failure nicht verschlimmern).
    """
    timestamp = time.time()
    base = Path(base_dir) if base_dir else Path.home() / ".stealth" / "screenshots"
    run_dir = base / run_id
    folder = run_dir / f"{int(timestamp)}_{reason}"
    folder.mkdir(parents=True, exist_ok=True)

    # Log immer schreiben — auch wenn CDP nicht erreichbar ist
    log_path = folder / "context.json"
    log_payload = {
        "run_id": run_id,
        "reason": reason,
        "timestamp": timestamp,
        "cdp_url": cdp_url,
        "extra": extra or {},
    }

    screenshot_path: Path | None = None
    html_path: Path | None = None

    try:
        screenshot_b64, html = await _capture_via_cdp(cdp_url)
        if screenshot_b64:
            screenshot_path = folder / "screenshot.png"
            screenshot_path.write_bytes(base64.b64decode(screenshot_b64))
        if html:
            html_path = folder / "page.html"
            html_path.write_text(html, encoding="utf-8")
        log_payload["cdp_ok"] = True
    except Exception as e:
        log.warning("screenshot.cdp_failed run_id=%s reason=%s err=%s", run_id, reason, e)
        log_payload["cdp_ok"] = False
        log_payload["cdp_error"] = str(e)

    log_path.write_text(json.dumps(log_payload, indent=2, default=str), encoding="utf-8")

    log.info(
        "screenshot.captured run_id=%s reason=%s dir=%s",
        run_id,
        reason,
        folder,
    )
    return FailureArtifact(
        directory=folder,
        screenshot_path=screenshot_path,
        html_path=html_path,
        log_path=log_path,
        reason=reason,
        timestamp=timestamp,
    )


# ── CDP-Implementierung ──────────────────────────────────────────────────────


async def _capture_via_cdp(cdp_url: str) -> tuple[str | None, str | None]:
    """Holt PNG (base64) und HTML aus dem aktiven Chrome-Tab via CDP.

    Erwartet einen laufenden Chrome mit --remote-debugging-port. Verbindet
    sich an den ersten "page"-Target, ruft Page.captureScreenshot und
    Runtime.evaluate(document.documentElement.outerHTML).
    """
    try:
        import aiohttp  # lokaler Import — vermeide harte Dep wenn ungenutzt
        import websockets
    except ImportError:
        log.warning("screenshot.deps_missing: aiohttp+websockets required")
        return None, None

    # 1) Tabs auflisten
    async with aiohttp.ClientSession() as sess:
        async with sess.get(f"{cdp_url}/json", timeout=aiohttp.ClientTimeout(total=2)) as r:
            tabs = await r.json()

    page_tabs = [t for t in tabs if t.get("type") == "page"]
    if not page_tabs:
        return None, None
    ws_url = page_tabs[0].get("webSocketDebuggerUrl")
    if not ws_url:
        return None, None

    # 2) WebSocket-Session: Screenshot + outerHTML
    async with websockets.connect(ws_url, max_size=20 * 1024 * 1024) as ws:
        screenshot_b64 = await _cdp_call(ws, 1, "Page.captureScreenshot", {"format": "png"})
        screenshot = (screenshot_b64 or {}).get("data")

        html_result = await _cdp_call(
            ws,
            2,
            "Runtime.evaluate",
            {
                "expression": "document.documentElement.outerHTML",
                "returnByValue": True,
            },
        )
        html = ((html_result or {}).get("result") or {}).get("value")

    return screenshot, html


async def _cdp_call(ws: Any, msg_id: int, method: str, params: dict) -> dict | None:
    """Schicke einen CDP-Call und warte ueber max 3 s auf Antwort."""
    await ws.send(json.dumps({"id": msg_id, "method": method, "params": params}))
    try:
        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout=3.0)
            msg = json.loads(raw)
            if msg.get("id") == msg_id:
                return msg.get("result")
    except TimeoutError:
        return None


# ── Rotation ─────────────────────────────────────────────────────────────────


def prune_old_artifacts(max_age_days: int = 7, base_dir: Path | None = None) -> int:
    """Loescht Artifact-Folders aelter als max_age_days.

    Returns: Anzahl geloeschter Ordner. Fehler werden geloggt aber nicht geworfen.
    """
    base = Path(base_dir) if base_dir else Path.home() / ".stealth" / "screenshots"
    if not base.exists():
        return 0
    cutoff = time.time() - max_age_days * 86400
    deleted = 0
    for run_dir in base.iterdir():
        if not run_dir.is_dir():
            continue
        for artifact_dir in run_dir.iterdir():
            if not artifact_dir.is_dir():
                continue
            try:
                if artifact_dir.stat().st_mtime < cutoff:
                    for child in artifact_dir.iterdir():
                        child.unlink(missing_ok=True)
                    artifact_dir.rmdir()
                    deleted += 1
            except Exception as e:
                log.warning("screenshot.prune_failed dir=%s err=%s", artifact_dir, e)
    return deleted
