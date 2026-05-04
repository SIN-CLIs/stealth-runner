from app.core import registry, executor

def dispatch(tool_name: str, payload: dict) -> dict:
    if "_v" not in tool_name:
        raise ValueError(f"Tool name must be versioned: {tool_name}")
    flow_name = tool_name.split("_v")[0]
    meta = registry.get(flow_name)
    if not meta:
        raise Exception(f"Flow not registered: {flow_name}")
    if not meta.get("frozen"):
        raise Exception(f"Flow not frozen yet: {flow_name}")
    return executor.run(meta["path"], payload)