import importlib.util, sys
from pathlib import Path

def run(path: str, payload: dict) -> dict:
    p = Path(path)
    spec = importlib.util.spec_from_file_location("flow_module", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["flow_module"] = mod
    spec.loader.exec_module(mod)
    result = mod.execute(payload)
    return result