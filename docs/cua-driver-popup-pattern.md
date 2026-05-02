# skylight-cli Popup Interaction Pattern

## Problem

`skylight-cli` operates on the MAIN browser window and cannot see elements
inside popup windows (Google OAuth, consent dialogs). When `skylight-cli list-elements`
returns elements, they are from the MAIN window's perspective – element indices
are NOT valid for popup content.

## Solution: skylight-cli for Popup Windows

### Prerequisites

```bash
# Start daemon (do this ONCE)
skylight-cli serve &
```

### Pattern

```bash
# 1. Find popup window ID
POPUP_WID=$(skylight-cli call list_windows '{}' | python3 -c "
import json,sys
for w in json.load(sys.stdin).get('windows',[]):
    if w.get('pid') == PID and 'anmelden' in (w.get('title','')or'').lower():
        print(w['window_id']); break
")

# 2. IMPORTANT: Load popup elements FIRST (caches them)
skylight-cli call get_window_state "{\"pid\":$PID,\"window_id\":$POPUP_WID}"

# 3. Find the button index INSIDE the popup
BTN_IDX=$(skylight-cli call get_window_state "{\"pid\":$PID,\"window_id\":$POPUP_WID}" | python3 -c "
import json,sys,re
tree = json.load(sys.stdin).get('tree_markdown','')
for line in tree.split(chr(10)):
    if 'Button' in line and 'Weiter' in line:
        m = re.search(r'\[(\d+)\]', line)
        if m: print(m.group(1)); break
")

# 4. Click using skylight-cli (NOT skylight!)
skylight-cli call click "{\"pid\":$PID,\"window_id\":$POPUP_WID,\"element_index\":$BTN_IDX,\"action\":\"press\"}"
```

## Why This Works

- `skylight-cli get_window_state` reads the popup's OWN AX tree
- Element indices from get_window_state are valid for that specific window
- `skylight-cli click` with `window_id` targets the correct window

## Why skylight-cli FAILS

- `skylight-cli list-elements` reads the MAIN window's AX tree
- Popup content is NOT in the main window's tree
- Clicking main window indices while popup is open clicks WRONG elements

## Key Commands Reference

| Action             | Command                                                                                      |
| ------------------ | -------------------------------------------------------------------------------------------- |
| List all windows   | `skylight-cli call list_windows '{}'`                                                        |
| Get popup elements | `skylight-cli call get_window_state '{"pid":PID,"window_id":WID}'`                           |
| Click in popup     | `skylight-cli call click '{"pid":PID,"window_id":WID,"element_index":N,"action":"press"}'`   |
| Type in popup      | `skylight-cli call set_value '{"pid":PID,"window_id":WID,"element_index":N,"value":"text"}'` |
| Start daemon       | `skylight-cli serve &`                                                                       |
| Check daemon       | `skylight-cli status`                                                                        |

## Verified Working (2026-05-02)

- Google OAuth popup: `WID=33508, PID=26897`
- Clicked `[35] AXButton "Weiter"` inside popup → ✅ Success
- Set `[26] AXTextField` email value → ✅ Success
