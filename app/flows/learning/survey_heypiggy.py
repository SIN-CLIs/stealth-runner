"""
HeyPiggy Survey Flow — Compiled CUA-only
=========================================
Hard Enforcement: NUR CUA-Tools, KEIN CDP für Navigation, KEIN Agent-Denken.

Flow:
  1. Dashboard laden → Survey-Cards finden
  2. Modal: "Umfrage starten" → Consent
  3. Fragen beantworten → Forward
  4. Survey complete → Balance prüfen

Persona: Berlin, männlich, 42, Anstellung, 2-Personen-Haushalt
Chrome: PID 48437, CDP 50015
"""
import subprocess, json, time, os
from pathlib import Path

PLAYSTEALTH_PID = 48437
CHROME_WID = 52623
CDP_PORT = 50015

def _cua(method: str, params: dict) -> dict:
    inp = {**params, "pid": PLAYSTEALTH_PID}
    if method == "list_windows":
        inp = {"pid": PLAYSTEALTH_PID}
    elif "window_id" not in inp:
        inp["window_id"] = CHROME_WID
    result = subprocess.run(
        ["cua-driver", "call", method],
        input=json.dumps(inp),
        capture_output=True, text=True
    )
    try:
        return json.loads(result.stdout)
    except:
        return {}

def _list_windows() -> list:
    data = _cua("list_windows", {})
    return [w for w in data.get("windows", []) if w.get("height", 0) > 100]

def _get_state() -> list:
    data = _cua("get_window_state", {"window_id": CHROME_WID})
    return data.get("tree_markdown", "").split("\n")

def _find_idx(lines: list, pattern: str, exact: bool = False) -> int | None:
    import re
    for line in lines:
        if exact:
            if pattern in line and re.search(r'- \[(\d+)\]', line):
                pass
        else:
            if pattern.lower() in line.lower() and re.search(r'- \[(\d+)\]', line):
                m = re.search(r'- \[(\d+)\]', line)
                return int(m.group(1))
    return None

def _click_idx(idx: int) -> bool:
    result = _cua("click", {"element_index": idx})
    return " Performed " in result.get("stdout", "")

def _set_value(idx: int, value: str) -> bool:
    result = _cua("set_value", {"element_index": idx, "value": value})
    return " Set " in result.get("stdout", "")

def _click_xy(x: int, y: int) -> bool:
    result = _cua("click", {"x": x, "y": y})
    return " Posted " in result.get("stdout", "")

def _find_modal_button(lines: list) -> int | None:
    import re
    keywords = ["umfrage starten", "zustimmen und fortfahren", "zustimmen", "starten", "akzeptieren"]
    button_idx = None
    for line in lines:
        for kw in keywords:
            if kw in line.lower() and re.search(r'- \[(\d+)\]', line):
                m = re.search(r'- \[(\d+)\]', line)
                idx = int(m.group(1))
                if "AXButton" in line:
                    return idx
                if button_idx is None:
                    button_idx = idx
    return button_idx

def _find_forward(lines: list) -> int | None:
    import re
    keywords = ["weiter", "nächste", "next", "forward", "submit", "send"]
    button_idx = None
    for line in lines:
        for kw in keywords:
            if kw in line.lower() and re.search(r'- \[(\d+)\]', line):
                m = re.search(r'- \[(\d+)\]', line)
                idx = int(m.group(1))
                if "DISABLED" not in line and "AXButton" in line:
                    return idx
                if button_idx is None and "DISABLED" not in line:
                    button_idx = idx
    return button_idx

def _find_radio_answer(lines: list, persona_hints: list) -> int | None:
    import re
    for hint in persona_hints:
        for line in lines:
            if hint.lower() in line.lower() and "AXRadioButton" in line:
                m = re.search(r'- \[(\d+)\]', line)
                if m:
                    return int(m.group(1))
    return None

def _find_checkbox(lines: list, persona_hints: list) -> int | None:
    import re
    for hint in persona_hints:
        for line in lines:
            if hint.lower() in line.lower() and "AXCheckBox" in line:
                m = re.search(r'- \[(\d+)\]', line)
                if m:
                    return int(m.group(1))
    return None

def _check_tab_changed() -> bool:
    import urllib.request
    try:
        resp = urllib.request.urlopen(f"http://localhost:{CDP_PORT}/json", timeout=5)
        tabs = json.loads(resp.read())
        for t in tabs:
            url = t.get("url", "")
            if "survey" in url.lower() and "dashboard" not in url:
                return True
        return False
    except:
        return False

def _get_balance() -> float:
    lines = _get_state()
    import re
    for line in lines:
        if "money bag" in line.lower() and "€" in line:
            m = re.search(r'(\d+\.\d+)', line)
            if m:
                return float(m.group(1))
    return 0.0

def _click_survey_card() -> bool:
    import re
    lines = _get_state()
    for line in lines:
        if "AXGroup" in line and re.search(r'@\(.*?\)', line):
            m = re.search(r'@\((\d+),(\d+),(\d+),(\d+)\)', line)
            if m:
                x, y, w, h = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
                if 500 <= y <= 900 and w > 200:
                    cx, cy = x + w // 2, y + h // 2
                    result = _click_xy(cx, cy)
                    if result:
                        time.sleep(2)
                        return True
    return False

def execute(payload: dict) -> dict:
    start_balance = _get_balance()
    runs = 0
    max_runs = 15

    while runs < max_runs:
        runs += 1
        lines = _get_state()
        url_lines = [l for l in lines if "heypiggy" in l.lower() and ("dashboard" in l.lower() or "/?" in l)]
        is_dashboard = any("/page=dashboard" in l for l in lines) or any("umfrage" in l.lower() for l in lines[:50])

        if is_dashboard:
            btn = _find_modal_button(lines)
            if btn:
                _click_idx(btn)
                time.sleep(3)
                lines = _get_state()
                continue

        forward = _find_forward(lines)
        if forward:
            if _click_idx(forward):
                time.sleep(3)
                lines = _get_state()
                continue

        radio = _find_radio_answer(lines, payload.get("radio_hints", []))
        if radio:
            _click_idx(radio)
            time.sleep(1)
            lines = _get_state()
            continue

        checkbox = _find_checkbox(lines, payload.get("checkbox_hints", []))
        if checkbox:
            _click_idx(checkbox)
            time.sleep(1)
            lines = _get_state()
            continue

        textarea = None
        for line in lines:
            if "AXTextArea" in line:
                import re
                m = re.search(r'- \[(\d+)\]', line)
                if m:
                    textarea = int(m.group(1))
                    break

        if textarea is not None:
            default_val = payload.get("textarea_value", "Ja")
            _set_value(textarea, default_val)
            time.sleep(1)
            lines = _get_state()
            forward_now = _find_forward(lines)
            if forward_now and "DISABLED" not in str(lines):
                _click_idx(forward_now)
                time.sleep(3)
                lines = _get_state()
                continue

        if not is_dashboard and not forward and not radio and not checkbox and textarea is None:
            break

    end_balance = _get_balance()
    earned = round(end_balance - start_balance, 2)

    return {
        "status": "ok",
        "earned": earned,
        "start_balance": start_balance,
        "end_balance": end_balance,
        "runs": runs
    }