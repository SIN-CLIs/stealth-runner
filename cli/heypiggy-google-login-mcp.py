#!/usr/bin/env python3
"""heypiggy-google-login-mcp — MCP Server für Google OAuth Login auf heypiggy.com.

Tool-Registry:
  heypiggy_login(pid) → Vollständiger Google OAuth Login (Hauptseite + Popup)

Architektur (SOTA 2026-05-02):
  PHASE 1 — Hauptseite: skylight-cli klickt Google Button (NUR Hauptfenster)
  PHASE 2 — Popup:      cua-driver für ALLES im Google OAuth Popup
  PHASE 3 — Verifikation: cua-driver prüft ob Popup weg → Login bestätigt

REGLN (banned.md):
  - skylight-cli OHNE --window-id bei Popups = BANNED (klickt falsches Fenster!)
  - skylight-cli click im Popup → klickt "Geld sparen" statt "Weiter"!
  - NUR cua-driver mit window_id für Popup-Interaktion!

Benötigt:
  - cua-driver Daemon (automatisch gestartet)
  - profiles/jeremy.yaml (google_email)
  - skylight-cli im PATH

Usage:
  python cli/heypiggy-google-login-mcp.py
  (Startet den MCP-Server, dann via MCP-Client Tool aufrufen)
"""
import json, os, subprocess, time
from pathlib import Path
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("heypiggy-google-login-mcp", version="1.0.0")

CUA  = "cua-driver"
SKYL = "/Users/jeremy/.local/bin/skylight-cli"
HERE = Path(__file__).parent.parent
PROFILE_FILE = HERE / "profiles" / "jeremy.yaml"


def _get_email() -> str:
    with open(PROFILE_FILE) as f:
        import yaml
        return yaml.safe_load(f.read()).get("google_email", "")


def _skylight_cmd(args: list[str]) -> dict:
    r = subprocess.run([SKYL] + args, capture_output=True, text=True, timeout=15)
    try:
        return json.loads(r.stdout.strip() or r.stderr.strip())
    except json.JSONDecodeError:
        return {"error": (r.stdout + r.stderr)[:200]}


def _cua(method: str, args: dict | None = None) -> dict:
    payload = json.dumps(args or {})
    r = subprocess.run([CUA, "call", method, payload], capture_output=True, text=True, timeout=15)
    out = r.stdout.strip() or r.stderr.strip()
    try:
        return json.loads(out) if out.startswith("{") else {"error": out[:500]}
    except json.JSONDecodeError:
        return {"error": out[:500]}


def _find_popup(pid: int) -> int | None:
    data = _cua("list_windows")
    for w in data.get("windows", []):
        if w.get("pid") == pid and w.get("is_on_screen") and "anmelden" in w.get("title", "").lower() and w["bounds"].get("width", 0) > 300:
            return w["window_id"]
    return None


def _popup_button_index(pid: int, wid: int, label: str) -> int | None:
    import re
    data = _cua("get_window_state", {"pid": pid, "window_id": wid})
    tree = data.get("tree_markdown", "")
    for m in re.finditer(r'\[(\d+)\]\s+AXButton\s+"([^"]+)"', tree):
        if label.lower() in m.group(2).lower():
            return int(m.group(1))
    return None


def _popup_textfield_index(pid: int, wid: int, label_hint: str) -> int | None:
    import re
    data = _cua("get_window_state", {"pid": pid, "window_id": wid})
    tree = data.get("tree_markdown", "")
    for m in re.finditer(r'\[(\d+)\]\s+AXTextField\s+"([^"]+)"', tree):
        if label_hint.lower() in m.group(2).lower():
            return int(m.group(1))
    return None


def _popup_click(pid: int, wid: int, idx: int) -> dict:
    return _cua("click", {"pid": pid, "window_id": wid, "element_index": idx, "action": "press"})


def _popup_type(pid: int, wid: int, idx: int, text: str) -> dict:
    return _cua("set_value", {"pid": pid, "window_id": wid, "element_index": idx, "value": text})


@mcp.tool()
def heypiggy_login(pid: int) -> dict:
    """Führt den kompletten Google OAuth Login auf heypiggy.com durch.

    Ablauf:
      1. skylight-cli klickt Google Button auf Hauptseite
      2. cua-driver Daemon starten
      3. cua-driver findet Google OAuth Popup (window_id)
      4. cua-driver tippt Email in Popup
      5. cua-driver klickt "Weiter", "Fortfahren", finaler "Weiter" im Popup
      6. Verifikation: Popup muss weg sein

    Returns dict mit status, email, steps.
    """
    email = _get_email()
    if not email:
        return {"status": "error", "reason": "no_email_in_profile"}

    steps = []
    ok = lambda s, **kw: steps.append({"step": s, **kw})

    # Phase 1: Google Button auf Hauptseite
    ok("find_google_button")
    r = _skylight_cmd(["list-elements", "--pid", str(pid)])
    google_idx = None
    for e in r.get("elements", []):
        if "google login" in (e.get("label", "") or "").lower() and e.get("role") == "AXLink":
            google_idx = e["index"]
            break
    if google_idx is None:
        return {"status": "error", "reason": "no_google_button", "steps": steps}
    _skylight_cmd(["click", "--pid", str(pid), "--element-index", str(google_idx)])
    ok("clicked_google_button", element_index=google_idx)
    time.sleep(5)

    # Phase 2: Daemon + Popup finden
    ok("start_daemon")
    subprocess.run([CUA, "serve"], capture_output=True, timeout=5)
    time.sleep(3)

    wid = _find_popup(pid)
    if wid is None:
        return {"status": "error", "reason": "no_popup_after_click", "steps": steps}
    ok("found_popup", window_id=wid)

    # Phase 3: Email (falls Feld sichtbar)
    ok("check_email_field")
    email_idx = _popup_textfield_index(pid, wid, "E-Mail")
    if email_idx:
        _popup_type(pid, wid, email_idx, email)
        ok("typed_email", element_index=email_idx, email=email)
        time.sleep(2)

    # Phase 4: "Weiter" klicken
    ok("click_weiter")
    weiter_idx = _popup_button_index(pid, wid, "Weiter")
    if not weiter_idx:
        return {"status": "error", "reason": "no_weiter_button", "steps": steps}
    _popup_click(pid, wid, weiter_idx)
    ok("clicked_weiter", element_index=weiter_idx)
    time.sleep(5)

    # Phase 5: "Fortfahren" (Consent)
    ok("check_fortfahren")
    fort_idx = _popup_button_index(pid, wid, "Fortfahren")
    if fort_idx:
        _popup_click(pid, wid, fort_idx)
        ok("clicked_fortfahren", element_index=fort_idx)
        time.sleep(5)

    # Phase 6: Finaler "Weiter"
        ok("click_final_weiter")
        final_weiter = _popup_button_index(pid, wid, "Weiter")
        if final_weiter:
            _popup_click(pid, wid, final_weiter)
            ok("clicked_final_weiter", element_index=final_weiter)
            time.sleep(5)

    # Phase 7: Verifikation
    ok("verify_popup_closed")
    for i in range(3):
        time.sleep(3)
        if _find_popup(pid) is None:
            ok("popup_gone", attempt=i + 1)
            return {
                "status": "ok",
                "email": email,
                "pid": pid,
                "steps": len(steps),
                "verified": True,
                "method": "cua-driver (popup-safe)",
            }
        ok("popup_still_open", attempt=i + 1)

    return {"status": "error", "reason": "popup_not_closed_after_retries", "steps": steps}


if __name__ == "__main__":
    mcp.run()
