# CUA-DRIVER CLICK — VERIFIED ✅

## Status
**VERIFIED** — 2026-05-05

## Was es tut
Klickt auf ein UI-Element via AXPress (Accessibility API). Nutzt element_index aus get_window_state.

## Command
```bash
echo '{"pid": 75167, "window_id": 56885, "element_index": 54}' | cua-driver call click
```

## Response
```
✅ Performed AXPress on [54] AXLink "".
```

## Success Check
```python
import subprocess, json

r = subprocess.run(["cua-driver", "call", "click"],
                   input=json.dumps({"pid": pid, "window_id": wid, "element_index": idx}).encode(),
                   capture_output=True, text=True)
success = "performed" in r.stdout.lower() or "performed" in r.stderr.lower()
```

## Wait After Click
```python
import time
time.sleep(5)  # Warten bis Popup/Page loaded
```

## Retry Logic
```python
for attempt in range(3):
    result = cua_click(pid, wid, idx)
    if "performed" in result.lower():
        break
    time.sleep(2)
```

## Error Types
| Fehler | Ursache | Fix |
|--------|---------|-----|
| kAXErrorCannotComplete | Element nicht interactable | Retry oder Koordinaten-Fallback |
| kAXErrorDisabled | Element ist disabled | Anderen Index suchen |
| kAXErrorNotFound | Element existiert nicht | AX-Tree neu scannen |

## Typische HeyPiggy Elemente
| Element | Index | AXRole |
|---------|-------|--------|
| Google Login-Symbol | 54 | AXLink |
| "Weiter" Button | 35 | AXButton |
| "Fortfahren" Button | 62 | AXButton |

## Test Log
- 2026-05-05: Google Login [54] → ✅ Performed AXPress, Google OAuth Popup (WID=56885) ✅