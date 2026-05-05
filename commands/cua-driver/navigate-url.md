# CUA-DRIVER NAVIGATE TO URL — VERIFIED ✅

## Status
**VERIFIED** — 2026-05-05

## Was es tut
Navigiert Chrome zu einer URL via Address Bar (Bot-spezifisch, toucht NICHT User Chrome!).

## Command Sequence
```bash
# 1. Fokussiere Address Bar (element_index varies per window!)
echo '{"pid": 75167, "window_id": 56869, "element_index": 7}' | cua-driver call click

# 2. URL eintragen
echo '{"pid": 75167, "window_id": 56869, "element_index": 7, "value": "https://..."}' | cua-driver call set_value

# 3. Navigieren
echo '{"pid": 75167, "window_id": 56869}' | cua-driver call press_key '{"pid": 75167, "window_id": 56869, "key": "return"}'
```

## Address Bar Element Index finden
```python
import subprocess, json, re

r = subprocess.run(["cua-driver", "call", "get_window_state"],
                   input=json.dumps({"pid": pid, "window_id": wid}).encode(),
                   capture_output=True, text=True)
d = json.loads(r.stdout)
lines = d.get("tree_markdown", "").split("\n")
for line in lines:
    if "adress" in line.lower() or "suchleiste" in line.lower():
        m = re.search(r'- \[(\d+)\]', line)
        idx = m.group(1) if m else None
        print(f"Address Bar: index={idx} line={line[:120]}")
```

## Chrome Internal URLs (chrome://)
| URL | Nutzen |
|-----|--------|
| `chrome://settings/passwords` | Saved passwords |
| `chrome://settings` | Settings page |
| `chrome://downloads` | Downloads |

## Warum CUA-Driver OK ist
- Nutzt `pid` + `window_id` → NUR das spezifische Window
- Address Bar element_index ist window-spezifisch
- Toucht KEIN User Chrome

## BANNED Alternative
- ❌ `osascript -e 'tell application "Google Chrome" to open location "..."'` → toucht ALLE Chrome!

## Test Log
- 2026-05-05: Address Bar [7] in Dashboard WID=56869 → navigate to chrome://settings/passwords ✅