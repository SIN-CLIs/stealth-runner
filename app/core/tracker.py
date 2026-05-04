"""Success Tracker — zählt Runs + Threshold-Check."""
import json, os
from app.config import THRESHOLD, STATE_DIR

TRACK_FILE = STATE_DIR / "success.json"

def record(flow_name: str) -> bool:
    data = _load()
    data[flow_name] = data.get(flow_name, 0) + 1
    _save(data)
    count = data[flow_name]
    print(f"[TRACKER] {flow_name} run #{count}/{THRESHOLD}")
    return count >= THRESHOLD

def get(flow_name: str) -> int:
    return _load().get(flow_name, 0)

def _load() -> dict:
    if not TRACK_FILE.exists():
        return {}
    return json.loads(TRACK_FILE.read_text())

def _save(data: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    TRACK_FILE.write_text(json.dumps(data, indent=2))