import shutil, time, os
from app.config import FLOW_DIR, COMPILED_DIR, OPENCODE_JSON
from app.core import registry, tool_builder

def compile(flow_name: str) -> str:
    src = FLOW_DIR / f"{flow_name}.py"
    if not src.exists():
        raise FileNotFoundError(f"Learning flow not found: {src}")
    version = int(time.time())
    dst = COMPILED_DIR / f"{flow_name}_v{version}.py"
    os.makedirs(COMPILED_DIR, exist_ok=True)
    shutil.copy(str(src), str(dst))
    registry.save(flow_name, version, dst)
    tool_builder.register(flow_name, version)
    print(f"[COMPILED] {flow_name} → v{version} (frozen, tool registered)")
    return str(dst)