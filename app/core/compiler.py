import shutil, time, os
from app.config import FLOW_DIR, COMPILED_DIR
from app.core import registry, tool_builder

def compile(flow_name):
    src = FLOW_DIR + f"/{flow_name}.py"
    if not os.path.exists(src):
        raise FileNotFoundError(f"Learning flow not found: {src}")
    version = int(time.time())
    dst = f"{COMPILED_DIR}/{flow_name}_v{version}.py"
    os.makedirs(COMPILED_DIR, exist_ok=True)
    shutil.copy(src, dst)
    registry.save(flow_name, version, dst)
    tool_builder.register(flow_name, version)
    print(f"[COMPILED] {flow_name} → v{version}")
    return dst
