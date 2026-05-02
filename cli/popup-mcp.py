#!/usr/bin/env python3
"""popup-mcp — MCP Server für sichere Popup-Interaktion via cua-driver.

Tools:
  popup_list_windows(pid)            → Alle sichtbaren Popup-Fenster
  popup_get_elements(pid, window_id) → AX-Elemente im Popup
  popup_click(pid, window_id, index) → Klick via AXPress (keine Maus!)
  popup_type(pid, window_id, index, text) → Text in Popup eingeben
  popup_is_closed(pid, window_id)    → Prüft ob Popup geschlossen
  popup_find_button(pid, window_id, label) → Button per Label suchen
  popup_daemon_start()              → cua-driver Daemon starten

REGLN (banned.md):
  skylight-cli OHNE --window-id bei Popups = BANNED → klickt falsches Fenster!
  cua-driver ist der EINZIG ERLAUBTE Weg für Popup-Interaktion.
"""
import json, re, subprocess, time
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("popup-mcp", version="1.0.0")

CUA = "cua-driver"


def _cua(method: str, args: dict | None = None) -> dict:
    """Führe cua-driver call aus und parsen die JSON-Antwort."""
    payload = json.dumps(args or {})
    r = subprocess.run([CUA, "call", method, payload], capture_output=True, text=True, timeout=15)
    out = r.stdout.strip() or r.stderr.strip()
    if out.startswith("{"):
        try:
            return json.loads(out)
        except json.JSONDecodeError:
            pass
    return {"error": out[:500]}


def _parse_tree(tree: str) -> list[dict]:
    """Extrahiere Elemente aus cua-driver tree_markdown."""
    elems = []
    for m in re.finditer(r'\[(\d+)\]\s+(AX\w+)\s+"([^"]+)"', tree):
        elems.append({"index": int(m.group(1)), "role": m.group(2), "label": m.group(3)})
    return elems


@mcp.tool()
def popup_daemon_start() -> dict:
    """Startet den cua-driver Daemon (nötig vor allen Popup-Operationen)."""
    r = subprocess.run([CUA, "serve"], capture_output=True, text=True, timeout=5)
    time.sleep(2)
    # Prüfe ob daemon läuft
    sock = Path("/Users/jeremy/Library/Caches/cua-driver/cua-driver.sock")
    if sock.exists():
        return {"status": "ok", "daemon": "running", "socket": str(sock)}
    return {"status": "ok", "note": "daemon_started"}


@mcp.tool()
def popup_list_windows(pid: int) -> list[dict]:
    """Liste ALLE sichtbaren Popup-Fenster für eine PID.

    Returns Fenster mit: window_id, title, bounds, is_on_screen.
    Popups sind typischerweise 300-600px breit, Hauptfenster >800px.
    """
    data = _cua("list_windows")
    result = []
    for w in data.get("windows", []):
        if w.get("pid") == pid and w.get("is_on_screen") and w["bounds"].get("width", 0) > 200:
            result.append({
                "window_id": w["window_id"],
                "title": w.get("title", ""),
                "width": w["bounds"]["width"],
                "height": w["bounds"]["height"],
                "x": w["bounds"]["x"],
                "y": w["bounds"]["y"],
            })
    return result


@mcp.tool()
def popup_get_elements(pid: int, window_id: int) -> list[dict]:
    """Hole ALLE AX-Elemente eines bestimmten Popup-Fensters.

    Cached den AX-Tree damit anschließende Klicks per element_index funktionieren.
    Returns Liste mit: index, role, label für jedes Element.
    """
    data = _cua("get_window_state", {"pid": pid, "window_id": window_id})
    tree = data.get("tree_markdown", "")
    return _parse_tree(tree)


@mcp.tool()
def popup_find_button(pid: int, window_id: int, label: str) -> dict:
    """Finde einen Button im Popup anhand seines Labels (z.B. 'Weiter', 'Fortfahren')."""
    elements = popup_get_elements(pid, window_id)
    label_lower = label.lower()
    for e in elements:
        if e["role"] == "AXButton" and label_lower in e["label"].lower():
            return {"found": True, "element_index": e["index"], "label": e["label"]}
    return {"found": False, "label": label}


@mcp.tool()
def popup_click(pid: int, window_id: int, element_index: int) -> dict:
    """Klicke ein Element im Popup via AXPress (KEINE Mausbewegung!)."""
    data = _cua("click", {"pid": pid, "window_id": window_id, "element_index": element_index, "action": "press"})
    if data.get("error") and "No cached AX state" in str(data.get("error", "")):
        return {"status": "error", "reason": "no_cache", "fix": "cua-driver daemon nicht gestartet? rufe popup_daemon_start()"}
    return {"status": "ok", "clicked": element_index, "detail": str(data)[:200]}


@mcp.tool()
def popup_type(pid: int, window_id: int, element_index: int, text: str) -> dict:
    """Tippe Text in ein Popup-Feld (z.B. Email, Passwort)."""
    data = _cua("set_value", {"pid": pid, "window_id": window_id, "element_index": element_index, "value": text})
    return {"status": "ok", "typed": text[:50], "detail": str(data)[:200]}


@mcp.tool()
def popup_is_closed(pid: int, window_id: int) -> dict:
    """Prüfe ob ein Popup-Fenster geschlossen ist."""
    data = _cua("list_windows")
    for w in data.get("windows", []):
        if w.get("pid") == pid and w.get("window_id") == window_id and w.get("is_on_screen"):
            return {"closed": False, "still_visible": True, "title": w.get("title", "")}
    return {"closed": True}


if __name__ == "__main__":
    mcp.run()
