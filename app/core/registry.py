import json, os
from app.config import STATE_DIR
REGISTRY_FILE = STATE_DIR + "/registry.json"

def save(flow_name, version, path):
    data = _load()
    data[flow_name] = {"version": version, "path": str(path), "frozen": True}
    _save(data)
    print(f"[REGISTRY] {flow_name} → v{version}")

def get(flow_name):
    return _load().get(flow_name)

def is_frozen(flow_name):
    entry = get(flow_name)
    return entry is not None and entry.get("frozen", False)

def _load():
    if not os.path.exists(REGISTRY_FILE):
        return {}
    return json.loads(open(REGISTRY_FILE).read())

def _save(data):
    os.makedirs(STATE_DIR, exist_ok=True)
    open(REGISTRY_FILE, "w").write(json.dumps(data, indent=2))
