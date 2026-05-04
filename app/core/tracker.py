import json, os, time
from pathlib import Path
from app.config import STATE_DIR

TRACK_FILE = STATE_DIR + "/success.json"


def record(flow_name, verdict="success_direct"):
    from app.core.compiler import FlowCompiler
    compiler = FlowCompiler()
    compiler.record_run(flow_name, verdict)

    data = _load()
    data[flow_name] = data.get(flow_name, 0) + 1
    _save(data)
    count = data[flow_name]

    status = compiler.get_status(flow_name)
    remaining = status["remaining"]
    tier = status["tier"]
    print(f"[TRACKER] {flow_name} #{count} ({tier}) — {remaining} bis production")

    if status["can_promote"]:
        compiled = compiler.compile(flow_name)
        if compiled:
            print(f"[TRACKER] {flow_name} PROMOTED to production! ✅")

    return True


def get(flow_name):
    from app.core.compiler import FlowCompiler
    return FlowCompiler().get_status(flow_name)


def _load():
    if not os.path.exists(TRACK_FILE):
        return {}
    return json.loads(open(TRACK_FILE).read())


def _save(data):
    os.makedirs(STATE_DIR, exist_ok=True)
    open(TRACK_FILE, "w").write(json.dumps(data, indent=2))