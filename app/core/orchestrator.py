from app.core import tracker, registry, compiler

THRESHOLD = 10

def run(flow_name: str, learning_fn, payload: dict) -> dict:
    if registry.is_frozen(flow_name):
        from app.core.dispatcher import dispatch
        tool = f"{flow_name}_v{registry.get(flow_name)['version']}"
        return dispatch(tool, payload)
    result = learning_fn(payload)
    if result.get("status") == "ok":
        if tracker.record(flow_name):
            compiler.compile(flow_name)
    return result