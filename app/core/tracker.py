import json, os
from app.config import THRESHOLD, STATE_DIR
TRACK_FILE = STATE_DIR + "/success.json"

def record(flow_name):
    data = _load()
    data[flow_name] = data.get(flow_name, 0) + 1
    _save(data)
    count = data[flow_name]
    print(f"[TRACKER] {flow_name} #{count}/{THRESHOLD}")
    return count >= THRESHOLD

def get(flow_name):
    return _load().get(flow_name, 0)

def _load():
    if not os.path.exists(TRACK_FILE):
        return {}
    return json.loads(open(TRACK_FILE).read())

def _save(data):
    os.makedirs(STATE_DIR, exist_ok=True)
    open(TRACK_FILE, "w").write(json.dumps(data, indent=2))
