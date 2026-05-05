# CUA-DRIVER LIST WINDOWS — VERIFIED ✅

## Status
**VERIFIED** — 2026-05-05

## Was es tut
Listet alle offenen Fenster auf (alle Apps). Findet Chrome-Windows mit PID, WID, Title, Bounds.

## Command
```bash
cua-driver call list_windows
```

## Output Format
```json
{"current_space_id": 3, "windows": [
  {"app_name": "Google Chrome", "bounds": {"height": 1006, "width": 1200, "x": 39, "y": 120},
   "is_on_screen": true, "layer": 0, "pid": 75167, "title": "HeyPiggy ...", "window_id": 56869, "z_index": 87},
  ...
]}
```

## Parse zu BOT Chrome Windows
```python
import json, subprocess

r = subprocess.run(["cua-driver", "call", "list_windows"], capture_output=True, text=True)
d = json.loads(r.stdout)

for w in d.get("windows", []):
    b = w.get("bounds", {})
    t = (w.get("title") or "").lower()
    n = (w.get("app_name") or "").lower()
    pid = w.get("pid")
    wid = w.get("window_id")
    z = w.get("z_index", 0)

    if b.get("height", 0) > 100 and "chrome" in n.lower():
        print(f"WID={wid} PID={pid} z={z} h={b['height']} title=\"{t[:60]}\"")
```

## Filter Rules
| Filter | Wert | Warum |
|--------|------|-------|
| `bounds.height > 100` | Skip Titlebars (height=30) | Nur echte Fenster |
| `"chrome" in app_name.lower()` | Skip andere Apps | NUR Chrome |
| `is_on_screen=true` | Optional | Nur sichtbare Fenster |

## Find Dashboard WID
```bash
cua-driver call list_windows | python3 -c "
import json, sys
d = json.load(sys.stdin)
for w in d.get('windows', []):
    b = w.get('bounds', {})
    t = (w.get('title') or '').lower()
    n = (w.get('app_name') or '').lower()
    pid = w.get('pid')
    wid = w.get('window_id')
    if b.get('height', 0) > 100 and 'chrome' in n.lower() and 'heypiggy' in t:
        print(f'BOT: PID={pid} WID={wid} title=\"{w.get(\"title\",\"\")[:50]}\"')
"
```

## Test Log
- 2026-05-05: Dashboard WID=56869 PID=75167 ✅