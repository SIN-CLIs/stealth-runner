# SR-13: Python AX Integration — atomacos + pyobjc

- **Status:** ✅ COMPLETED (2026-05-04)
- **Priority:** 🟡 High
- **Plan:** [`plans/plan-atomacos-python-ax.md`](../plans/plan-atomacos-python-ax.md)
- **Source:** Plane Wiki `chat verlauf mit agent 2` §3

## Description

Created Python-based AX access for the orchestrator using `atomacos` (v3.3.0, already installed). Enables direct AX tree traversal without Swift subprocess calls.

## Deliverables

- [x] `cli/modules/ax_python.py` created (134 lines)
- [x] `get_ax_tree(pid)` — recursive AX tree walk as dict
- [x] `find_by_label(pid, label)` — word-boundary label search
- [x] `get_window_list()` — enumerate all app windows
- [x] Reads `AXDOMIdentifier` from Chrome elements via atomacos

## Acceptance Criteria

- [x] `import atomacos` succeeds (v3.3.0 installed)
- [x] `get_ax_tree(pid=CHROME_PID)` returns structured tree
- [x] `find_by_label(pid, "Weiter")` finds correct element index
- [ ] Integration with `survey_runner.py` for faster AX scans (future)

## Files

- `cli/modules/ax_python.py` (134 lines)
- Dependencies: `atomacos` v3.3.0
