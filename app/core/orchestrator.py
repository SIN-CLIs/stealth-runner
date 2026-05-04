from app.core import tracker, registry, compiler

def run(flow_name, learning_fn, payload):
    if registry.is_frozen(flow_name):
        from app.core.dispatcher import dispatch
        meta = registry.get(flow_name)
        tool = f"{flow_name}_v{meta['version']}"
        return dispatch(tool, payload)
    result = learning_fn(payload)
    if result.get("status") == "ok":
        if tracker.record(flow_name):
            compiler.compile(flow_name)
    return result
