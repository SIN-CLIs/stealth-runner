# PLAN: Python AX Integration — atomacos + pyobjc für Orchestrator

> **Quelle:** Plane Wiki `chat verlauf mit agent 2` (256966ad) §3  
> **Abhängigkeiten:** Keine (reine Python-Bibliothek, keine neuen Repos nötig)  
> **Priorität:** 🟡 HOCH  
> **Aufwand:** Klein

---

## 🔍 Recherche-Ergebnisse

| Library | Version | Status | Use Case |
|---------|---------|--------|----------|
| **atomacos** | `3.3.0` | ✅ Installiert (`~/Library/Python/3.14/...`) | High-Level AX Tree Dump, `getFrontmostApp()`, `AXChildren` |
| **pyobjc-framework-ApplicationServices** | `12.1` | ✅ Installiert | AXUIElement aus Python via AppKit |
| **Quartz (pyobjc)** | `12.1` | ✅ Installiert | `CGWindowListCopyWindowInfo` aus Python |
| **accessibility (PyPI)** | — | ❌ Nicht gefunden | Existiert nicht auf PyPI |

**Relevant:** `cua-touch` (Python, GitHub: SIN-CLIs/cua-touch) könnte von atomacos profitieren.  
**Aktuell:** cua-touch ruft `cua-driver` (Swift Binary) per Subprocess auf. Mit atomacos könnten viele Aufrufe direkt in Python erfolgen — schneller und ohne Subprocess-Overhead.

---

## 🎯 Ziel

Python-basierten AX-Zugriff für den Orchestrator ermöglichen.  
Damit kann der Orchestrator direkt AX-Trees lesen ohne jedesmal Swift-Tools aufzurufen.

## 🏗️ Implementation

### Neues Modul: `cli/modules/ax_python.py`

```python
import atomacos

def get_ax_tree(pid=None):
    """Gibt kompletten AX-Tree als Dict zurück."""
    if pid:
        app = atomacos.AppRef.from_pid(pid)
    else:
        app = atomacos.getFrontmostApp()
    return _walk_tree(app)

def _walk_tree(element, depth=0):
    """Rekursiver Walk des AX-Trees."""
    if depth > 20:
        return None
    node = {
        "role": element.AXRole,
        "title": getattr(element, "AXTitle", None),
        "dom_id": getattr(element, "AXDOMIdentifier", None),  # Chrome-spezifisch
        "frame": list(getattr(element, "AXFrame", [0,0,0,0])),
        "children": []
    }
    try:
        for child in element.AXChildren:
            child_node = _walk_tree(child, depth+1)
            if child_node:
                node["children"].append(child_node)
    except:
        pass
    return node
```

## ✅ Sub-Tasks

- [ ] `atomacos` import testen: `python3 -c "import atomacos; print('OK')"`
- [ ] `cli/modules/ax_python.py` erstellen
- [ ] `get_ax_tree(pid)` implementieren
- [ ] `find_by_label(pid, label)` implementieren (Label-Suche im Python-Tree)
- [ ] Integration: `survey_runner.py` nutzt `ax_python` für schnelle AX-Scans

## 📂 Verwandte Dateien

| Datei | Rolle |
|-------|-------|
| `cli/modules/skylight_main.py` | Kann ergänzt werden um Python-AX |
| `cli/modules/cdp_click.py` | Kann AXDOMIdentifier aus Python lesen |
| `cli/modules/survey_runner.py` | Kann schneller scannen |

## 🔗 Issue

[ISSUE-SR-13: Python AX Integration](../issues/ISSUE-SR-13.md)
