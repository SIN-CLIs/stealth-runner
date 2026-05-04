import json
from app.config import OPENCODE_JSON

def register(flow_name, version):
    data = _load()
    tool_name = f"{flow_name}_v{version}"
    tool = {
        "name": tool_name,
        "description": f"Frozen deterministic flow: {flow_name}",
        "strict": True,
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": True},
        "frozen_at": version,
        "source": "FCTES-compiler"
    }
    data["tools"] = [t for t in data.get("tools", []) if not t["name"].startswith(flow_name + "_v")]
    data.setdefault("tools", []).append(tool)
    _save(data)
    print(f"[TOOL] Registered: {tool_name}")

def list_tools():
    return _load().get("tools", [])

def _load():
    if not os.path.exists(OPENCODE_JSON):
        return {"tools": [], "flows": []}
    return json.loads(open(OPENCODE_JSON).read())

def _save(data):
    open(OPENCODE_JSON, "w").write(json.dumps(data, indent=2))
