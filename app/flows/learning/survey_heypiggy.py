import subprocess, json, time, os, re
from app.config import PLAYSTEALTH_PID, CHROME_WID, CDP_PORT

def _cua(method, params):
    inp = {**params, "pid": PLAYSTEALTH_PID}
    if method == "list_windows":
        inp = {"pid": PLAYSTEALTH_PID}
    elif "window_id" not in inp:
        inp["window_id"] = CHROME_WID
    r = subprocess.run(["cua-driver", "call", method], input=json.dumps(inp), capture_output=True, text=True)
    try:
        return json.loads(r.stdout)
    except:
        return {}

def _get_state():
    data = _cua("get_window_state", {"window_id": CHROME_WID})
    return data.get("tree_markdown", "").split("\n")

def _find_idx(lines, pattern):
    for line in lines:
        if pattern.lower() in line.lower() and re.search(r'- \[(\d+)\]', line):
            m = re.search(r'- \[(\d+)\]', line)
            return int(m.group(1))
    return None

def _find_modal_button(lines):
    for line in lines:
        for kw in ["umfrage starten", "zustimmen und fortfahren", "zustimmen", "starten", "akzeptieren"]:
            if kw in line.lower() and re.search(r'- \[(\d+)\]', line):
                m = re.search(r'- \[(\d+)\]', line)
                if "AXButton" in line:
                    return int(m.group(1))

def _find_forward(lines):
    for line in lines:
        for kw in ["weiter", "nächste", "next", "submit", "send"]:
            if kw in line.lower() and "DISABLED" not in line and re.search(r'- \[(\d+)\]', line):
                m = re.search(r'- \[(\d+)\]', line)
                if "AXButton" in line:
                    return int(m.group(1))

def _find_radio_answer(lines, hints):
    for hint in hints:
        for line in lines:
            if hint.lower() in line.lower() and "AXRadioButton" in line and re.search(r'- \[(\d+)\]', line):
                return int(re.search(r'- \[(\d+)\]', line).group(1))
    return None

def _click_idx(idx):
    r = _cua("click", {"element_index": idx})
    return " Performed " in r.get("stdout", "")

def _set_value(idx, value):
    r = _cua("set_value", {"element_index": idx, "value": value})
    return " Set " in r.get("stdout", "")

def _click_xy(x, y):
    r = _cua("click", {"x": x, "y": y})
    return " Posted " in r.get("stdout", "")

def _get_balance():
    lines = _get_state()
    for line in lines:
        if "money bag" in line.lower() and "€" in line:
            m = re.search(r'(\d+\.\d+)', line)
            if m:
                return float(m.group(1))
    return 0.0

def _find_textarea(lines):
    for line in lines:
        if "AXTextArea" in line and re.search(r'- \[(\d+)\]', line):
            return int(re.search(r'- \[(\d+)\]', line).group(1))
    return None

def execute(payload):
    start_balance = _get_balance()
    for _ in range(20):
        lines = _get_state()
        is_dash = any("/page=dashboard" in l for l in lines) or any("umfrage" in l.lower() for l in lines[:50])
        if is_dash:
            btn = _find_modal_button(lines)
            if btn:
                _click_idx(btn)
                time.sleep(3)
                continue
        fwd = _find_forward(lines)
        if fwd:
            _click_idx(fwd)
            time.sleep(3)
            continue
        radio = _find_radio_answer(lines, payload.get("radio_hints", []))
        if radio:
            _click_idx(radio)
            time.sleep(1)
            continue
        ta = _find_textarea(lines)
        if ta:
            _set_value(ta, payload.get("textarea_value", "Ja"))
            time.sleep(1)
            continue
        break
    end_balance = _get_balance()
    return {"status": "ok", "earned": round(end_balance - start_balance, 2), "start": start_balance, "end": end_balance}
