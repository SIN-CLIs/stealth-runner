# Survey Tools — Frozen Atomic Tools

**REGEL:** Diese Tools sind `__frozen__ = True`. Nicht aendern wenn sie funktionieren!

## Usage

```python
from tools import click, fill, snapshot, detect_completion
from tools import close_modals, find_new_tab, get_tab_ids, select_language
from tools import AntiStuck, find_submit, find_unfilled

# Example survey loop:

tabs_before = get_tab_ids(9222)

click(ws_url, text="Start Survey")
new_ws = find_new_tab(9222, tabs_before)
close_modals(new_ws)

checker = AntiStuck(threshold=3)

while True:
    data = snapshot(new_ws)

    if checker.is_stuck(data["hash"]):
        print("STUCK!")
        break

    status = detect_completion(new_ws)
    if status != "running":
        print(f"Done: {status}")
        break

    if "language" in data["url"].lower():
        select_language(new_ws, "Deutsch")
        continue

    for el in find_unfilled(data["elements"]):
        fill(new_ws, "25", idx=el["idx"])

    submit = find_submit(data["elements"])
    if submit:
        click(new_ws, idx=submit["idx"])
```

## Available Tools

| Tool | Function | Status |
|------|----------|--------|
| `tool_click_angular.py` | `click(ws_url, idx/text/selector)` | ✅ Frozen |
| `tool_select_language.py` | `select_language(ws_url, language)` | ✅ Frozen |
| `tool_fill_input.py` | `fill(ws_url, value, idx/selector)` | ✅ Frozen |
| `tool_find_new_tab.py` | `find_new_tab(port, tabs, ...)` | ✅ Frozen |
| `tool_close_modals.py` | `close_modals(ws_url)` | ✅ Frozen |
| `tool_detect_completion.py` | `detect(ws_url)` | ✅ Frozen |
| `tool_snapshot.py` | `snapshot(ws_url)` | ✅ Frozen |
| `tool_anti_stuck.py` | `AntiStuck(threshold=3)` | ✅ Frozen |

## CLI Mode

Every tool is directly executable:

```bash
python tools/tool_click_angular.py <ws_url> 0
python tools/tool_snapshot.py <ws_url>
python tools/tool_detect_completion.py <ws_url>
python tools/tool_select_language.py <ws_url> English
```
