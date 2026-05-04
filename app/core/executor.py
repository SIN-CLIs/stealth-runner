import importlib.util, sys
from pathlib import Path

def run(path, payload):
    p = Path(path)
    spec = importlib.util.spec_from_file_location("flow_mod", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["flow_mod"] = mod
    spec.loader.exec_module(mod)
    return mod.execute(payload)
