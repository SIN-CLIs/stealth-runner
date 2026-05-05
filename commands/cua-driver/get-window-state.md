# CUA-DRIVER GET WINDOW STATE — VERIFIED ✅

## Status
**VERIFIED** — 2026-05-05

## Was es tut
Liest den kompletten AX-Tree eines Chrome-Fensters. Elemente haben Index-Nummern für `click`, `set_value`, etc.

## Command
```bash
echo '{"pid": 75167, "window_id": 56869}' | cua-driver call get_window_state
```

## Output Format
```json
{"element_count": 672, "tree_markdown": "- [0] AXWindow ...\n- [1] AXGroup ...\n- [48] AXHeading \"Anmelden...\" @(x,y,w,h) ...", ...}
```

## Parse Element Index
```python
import re, json, subprocess

r = subprocess.run(["cua-driver", "call", "get_window_state"],
                   input='{"pid": 75167, "window_id": 56869}'.encode(),
                   capture_output=True)
d = json.loads(r.stdout)

lines = d.get("tree_markdown", "").split("\n")
for line in lines:
    # Find element index
    m = re.search(r'- \[(\d+)\]', line)
    idx = m.group(1) if m else None
    print(f"[{idx}] {line[:120]}")
```

## Find Specific Element (z.B. Google Login)
```python
for line in lines:
    if "google login-symbol" in line.lower():
        m = re.search(r'- \[(\d+)\]', line)
        print(f"Found: index={m.group(1)} line={line}")
```

## Element Format
```
- [48] AXHeading "Anmelden oder Registrieren" @(721,412,423,30)
  │    ││   │                              ││ ││ ││   │
  │    ││   │                              ││ ││ ││   └─ bounds: x,y,w,h
  │    ││   │                              ││ ││ │└──── height
  │    ││   │                              ││ │└────── width
  │    ││   │                              │└───────── y
  │    ││   │                              └────────── x
  │    ││   └─ element label/title
  │    │└───────────── AXRole (AXHeading, AXLink, AXButton, etc.)
  │    └──────────────── element_index (für click/set_value)
  └──────────────────── line prefix
```

## AXRoles im HeyPiggy Dashboard
| AXRole | Typ | Aktion |
|--------|-----|--------|
| AXLink | Link/Button | click |
| AXButton | Button | click |
| AXTextField | Input | set_value |
| AXHeading | Label/Überschrift | read only |
| AXStaticText | Text | read only |
| AXImage | Icon | read only |

## Google Login Button
```
- [54] AXLink (Google Login-Symbol) @(731,651,132,41)
```
→ Klickbar mit Index 54

## Test Log
- 2026-05-05: Dashboard 672 elements, Google Login [54] ✅