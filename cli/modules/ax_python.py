"""ax_python — Python AX tree traversal via atomacos.

Bietet schnellen Python-basierten AX-Zugriff für den Orchestrator,
ohne jedesmal cua-driver/skylight-cli subprocess aufrufen zu müssen.

Usage:
    from cli.modules.ax_python import get_ax_tree, find_by_label
    tree = get_ax_tree(pid=12345)
    idx = find_by_label(pid=12345, label="Weiter")
"""
from __future__ import annotations

try:
    import atomacos
except ImportError:
    atomacos = None


def _import_atomacos():
    if atomacos is None:
        raise ImportError(
            "atomacos nicht installiert. pip install atomacos"
        )
    return atomacos


def get_ax_tree(pid: int | None = None, max_depth: int = 20) -> dict | None:
    """Gibt kompletten AX-Tree einer App als Dict zurück."""
    atc = _import_atomacos()
    try:
        if pid:
            app = atc.AppRef.from_pid(pid)
        else:
            app = atc.getFrontmostApp()
    except Exception:
        # Möglicherweise keine AX Berechtigung
        return None
    return _walk_tree(app, depth=0, max_depth=max_depth)


def _walk_tree(element, depth: int, max_depth: int) -> dict | None:
    """Rekursiver Walk des AX-Trees."""
    if depth > max_depth:
        return None
    try:
        role = getattr(element, "AXRole", "AXUnknown")
        label = getattr(element, "AXTitle", None) or getattr(element, "AXDescription", "")
        dom_id = getattr(element, "AXDOMIdentifier", None)
        frame = getattr(element, "AXFrame", None)
        frame_list = [frame.origin.x, frame.origin.y, frame.size.width, frame.size.height] if frame else None
        enabled = getattr(element, "AXEnabled", None)
        focused = getattr(element, "AXFocused", None)
        value = getattr(element, "AXValue", None)
        actions = getattr(element, "AXActionNames", []) or []
        children_list = getattr(element, "AXChildren", []) or []
        node = {
            "role": role,
            "label": str(label)[:80] if label else "",
            "dom_id": dom_id,
            "frame": frame_list,
            "enabled": enabled,
            "focused": focused,
            "value": str(value)[:80] if value else None,
            "actions": list(actions),
            "children": [],
        }
        for child in children_list:
            child_node = _walk_tree(child, depth + 1, max_depth)
            if child_node:
                node["children"].append(child_node)
        return node
    except Exception:
        return None


def find_by_label(pid: int, label: str, role: str | None = None) -> int | None:
    """Findet ersten Element-Index mit passendem Label (word-boundary).

    Returns:
        element_index oder None wenn nicht gefunden
    """
    import re as _re
    pattern = _re.compile(r'\b' + _re.escape(label) + r'\b', _re.IGNORECASE)
    tree = get_ax_tree(pid=pid)
    if not tree:
        return None
    return _find_in_tree(tree, pattern, role=role, current_idx=[0])


def _find_in_tree(node: dict, pattern, role: str | None = None, current_idx: list) -> int | None:
    """Rekursive Suche mit Index-Zählung."""
    my_idx = current_idx[0]
    current_idx[0] += 1
    node_label = node.get("label", "")
    node_role = node.get("role", "")
    if pattern.search(node_label):
        if role is None or node_role == role:
            return my_idx
    for child in node.get("children", []):
        result = _find_in_tree(child, pattern, role, current_idx)
        if result is not None:
            return result
    return None


def get_window_list() -> list[dict]:
    """Listet alle Fenster aller laufenden Apps."""
    atc = _import_atomacos()
    try:
        apps = [atc.AppRef.from_pid(p) for p in _get_all_pids()]
        windows = []
        for app in apps:
            try:
                w = app.AXWindows
                if w:
                    windows.append(w)
            except Exception:
                pass
        return windows
    except Exception:
        return []


def _get_all_pids() -> list[int]:
    """Hilfsfunktion: Alle laufenden PIDs via NSWorkspace."""
    import subprocess
    try:
        r = subprocess.run(
            ["python3", "-c", "import AppKit; import json; apps = AppKit.NSWorkspace.sharedWorkspace().runningApplications(); print(json.dumps([a.processIdentifier() for a in apps]))"],
            capture_output=True, text=True, timeout=10
        )
        return json.loads(r.stdout)
    except Exception:
        return []
