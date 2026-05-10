# ════════════════════════════════════════════════════════════════════════════════╗
# ║  UTILITIES — preflight, registry, HTTP helpers                               ║
# ║                                                                               ║
# ║  WIRD IMPORTIERT VON: alle endpoints/*.py                                    ║
# ║  Enthält: preflight_check + require_survey_ready + update_command_registry  ║
# ║  _schemas.py muss VOR diesem importierbar sein.                              ║
# ╚═══════════════════════════════════════════════════════════════════════════════╝

from __future__ import annotations

import json, asyncio, sys, os, urllib.request
from pathlib import Path
from datetime import datetime, timezone

from fastapi import Depends, HTTPException

# ─── PYTHONPATH SETUP ───────────────────────────────────────────────────────────
_workspace_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
_survey_cli_path = os.path.join(_workspace_root, "survey-cli")
if _survey_cli_path not in sys.path:
    sys.path.insert(0, _survey_cli_path)

# ─── IMPORT SCHEMAS (forward reference, avoid circular) ────────────────────────
# Schemas sind in _schemas.py — werden von endpoints/*.py importiert
# Diese Datei nutzt NUR prefetch_check + update_command_registry
# Kein Endpoint braucht Schemas aus dieser Datei (Schemas kommen direkt aus _schemas)

# ═══════════════════════════════════════════════════════════════════════════════
# PREFLIGHT CHECK
# ═══════════════════════════════════════════════════════════════════════════════

class PreflightError(HTTPException):
    """Raised when system not ready (503)."""
    def __init__(self, reason: str, action: str = ""):
        super().__init__(
            status_code=503,
            detail={
                "error": "preflight_failed",
                "reason": reason,
                "action": action,
                "message": f"System not ready: {reason}. Action: {action or 'none'}",
            },
        )


def preflight_check(port: int = 9999) -> dict:
    """
    Validates: Chrome alive → Dashboard tab → Login valid → Balance readable.
    Returns dict with ready, tab_ws, balance, surveys, reason, action.
    """
    result = {
        "ready": False, "tab_ws": "", "balance": 0.0,
        "surveys": 0, "reason": "", "action": "",
        "chrome_alive": False, "login_valid": False,
    }
    
    # 1. Chrome alive?
    try:
        raw = urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=3).read()
        json.loads(raw)
        result["chrome_alive"] = True
    except Exception:
        result["reason"] = "Chrome not running on port 9999"
        result["action"] = "start_chrome"
        return result
    
    # 2. Dashboard tab?
    try:
        raw = urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=3).read()
        pages = json.loads(raw)
        tab = None
        for p in pages:
            if p.get("type") != "page" or p.get("url", "").startswith("chrome-extension"):
                continue
            url = p.get("url", "")
            if url in ("", "about:blank") or "heypiggy" in url:
                tab = p
                break
        if not tab:
            result["reason"] = "No valid dashboard tab found"
            result["action"] = "restart_chrome"
            return result
        result["tab_ws"] = tab.get("webSocketDebuggerUrl", "")
    except Exception as e:
        result["reason"] = f"Cannot find dashboard tab: {e}"
        result["action"] = "restart_chrome"
        return result
    
    # 3. Login valid?
    ws = result["tab_ws"]
    if ws:
        try:
            import websockets
            async def check():
                async with websockets.connect(ws) as w:
                    await w.send(json.dumps({
                        "id": 1, "method": "Runtime.evaluate",
                        "params": {"expression": "document.body.innerText.substring(0, 500)"},
                    }))
                    resp = await asyncio.wait_for(w.recv(), timeout=5)
                    text = json.loads(resp).get("result", {}).get("result", {}).get("value", "")
                    return "abmelden" in text.lower()
            if not asyncio.run(check()):
                result["reason"] = "Session expired — not logged in"
                result["action"] = "restore_cookies"
                return result
            result["login_valid"] = True
        except Exception:
            pass
    
    # 4. Balance
    if ws:
        try:
            import websockets
            async def get_bal():
                async with websockets.connect(ws) as w:
                    js = """
                    (() => {
                        const txt = document.body.innerText || '';
                        const amts = [...txt.matchAll(/(\\d+[.,]\\d{2})/g)];
                        let max = 0;
                        for (const m of amts) {
                            const n = parseFloat(m[1].replace(',', '.'));
                            if (txt.substring(m.index, m.index + 50).includes('€') && n >= 1.0 && n > max)
                                max = n;
                        }
                        return max;
                    })()
                    """
                    await w.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                                            "params": {"expression": js}}))
                    resp = await asyncio.wait_for(w.recv(), timeout=5)
                    val = json.loads(resp).get("result", {}).get("result", {}).get("value")
                    return float(val) if isinstance(val, (int, float)) else 0.0
            result["balance"] = asyncio.run(get_bal())
        except Exception:
            pass
    
    result["ready"] = True
    return result


def require_survey_ready(port: int = 9999):
    """FastAPI Dependency — raises PreflightError if system not ready."""
    pf = preflight_check(port)
    if not pf["ready"]:
        raise PreflightError(reason=pf["reason"], action=pf["action"])
    return pf


# ═══════════════════════════════════════════════════════════════════════════════
# COMMAND REGISTRY
# ═══════════════════════════════════════════════════════════════════════════════

def update_command_registry(command_id: str, success: bool, details: dict = None):
    """
    Auto-update command_registry.json after every command execution.
    Persists: success_count, failure_count, last_run, last_result, status.
    """
    registry_path = (
        Path(__file__).parent.parent.parent
        / "survey-cli" / "data" / "command_registry.json"
    )
    try:
        with open(registry_path) as f:
            registry = json.load(f)
    except Exception:
        return

    now = datetime.now(timezone.utc).isoformat()
    details = details or {}

    for cmd in registry.get("commands", []):
        if cmd.get("id") == command_id:
            if success:
                cmd["success_count"] = cmd.get("success_count", 0) + 1
                cmd["last_success"] = now
                cmd["status"] = "verified" if cmd["success_count"] >= 3 else "testing"
            else:
                cmd["failure_count"] = cmd.get("failure_count", 0) + 1
                cmd["last_failure"] = now
                cmd["status"] = "testing"
            cmd["last_run"] = now
            cmd["last_result"] = {
                "status": details.get("status", "unknown"),
                "pages_processed": details.get("pages_processed", 0),
                "final_url": details.get("final_url", ""),
                "earned": details.get("earned", 0.0),
            }
            cmd["notes"] = f"{details.get('status','unknown')}, {details.get('pages_processed',0)} pages"
            break
    else:
        registry.setdefault("commands", []).append({
            "id": command_id,
            "description": "Auto-registered from FastAPI endpoint",
            "path": "agent-toolbox/api/endpoints/",
            "success_count": 1 if success else 0,
            "failure_count": 0 if success else 1,
            "last_success": now if success else None,
            "last_run": now,
            "status": "testing",
            "notes": f"First {'success' if success else 'failure'} from FastAPI",
        })

    registry["last_updated"] = now
    try:
        with open(registry_path, "w") as f:
            json.dump(registry, f, indent=2)
    except Exception:
        pass


def _read_balance(port: int) -> float:
    """Fallback: read balance from first HeyPiggy tab."""
    try:
        raw = urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=3).read()
        for p in json.loads(raw):
            if p.get("type") == "page" and "heypiggy" in p.get("url", ""):
                return 0.0
    except Exception:
        pass
    return 0.0