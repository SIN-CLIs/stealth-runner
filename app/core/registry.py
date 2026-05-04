import json, os
from app.config import STATE_DIR

REGISTRY_FILE = STATE_DIR / "registry.json"

def save(flow_name: str, version: int, path: str) -> None:
    data = _load()
    data[flow_name] = {"version": version, "path": str(path), "frozen": True}
    _save(data)
    print(f"[REGISTRY] {flow_name} → v{version} @ {path}")

def get(flow_name: str) -> dict | None:
    return _load().get(flow_name)

def is_frozen(flow_name: str) -> bool:
    entry = get(flow_name)
    return entry is not None and entry.get("frozen", False)

def _load() -> dict:
    if not REGISTRY_FILE.exists():
        return {}
    return json.loads(REGISTRY_FILE.read_text())

def _save(data: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    REGISTRY_FILE.write_text(json.dumps(data, indent=2))