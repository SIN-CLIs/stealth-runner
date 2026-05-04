import json
from app.config import OPENCODE_JSON

def register(flow_name: str, version: int) -> None:
    data = _load()
    tool_name = f"{flow_name}_v{version}"
    tool = {
        "name": tool_name,
        "description": f"Frozen deterministic flow: {flow_name}",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"survey_url": {"type": "string"}},
            "additionalProperties": True
        },
        "frozen_at": version,
        "source": "FCTES-compiler"
    }
    data["tools"] = [t for t in data.get("tools", []) if not t["name"].startswith(flow_name + "_v")]
    data.setdefault("tools", []).append(tool)
    _save(data)
    print(f"[TOOL] Registered: {tool_name} → opencode.json")

def _load() -> dict:
    if not OPENCODE_JSON.exists():
        return {"tools": [], "flows": []}
    return json.loads(OPENCODE_JSON.read_text())

def _save(data: dict) -> None:
    OPENCODE_JSON.write_text(json.dumps(data, indent=2))

def list_tools() -> list:
    return _load().get("tools", [])

def is_registered(tool_name: str) -> bool:
    return any(t["name"] == tool_name for t in list_tools())