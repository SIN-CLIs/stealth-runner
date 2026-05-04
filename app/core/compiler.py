import json, os, re, yaml, shutil, time
from pathlib import Path
from typing import Dict, Any, Optional

from app.config import FLOW_DIR, COMPILED_DIR, STATE_DIR
from app.core import registry, tool_builder

LEARN_PATH = Path.home() / ".stealth" / "learn.md"
FLOWS_DIR = Path(__file__).parent.parent.parent / "app" / "flows"
REQUIRED_SUCCESSES = 10


class FlowStatus:
    def __init__(self, flow_name: str, yaml_path: Optional[Path] = None):
        self.flow_name = flow_name
        self.yaml_path = yaml_path
        self.run_count = 0
        self.success_direct_count = 0
        self.last_run_time = None
        self.tier = "learning"
        self.last_verdict = None
        self._load_status()

    def _status_file(self) -> Path:
        return Path(STATE_DIR) / f"flow_{self.flow_name}.json"

    def _load_status(self):
        f = self._status_file()
        if f.exists():
            d = json.loads(f.read_text())
            self.run_count = d.get("run_count", 0)
            self.success_direct_count = d.get("success_direct_count", 0)
            self.last_run_time = d.get("last_run_time")
            self.tier = d.get("tier", "learning")

    def _save_status(self):
        self._status_file().parent.mkdir(parents=True, exist_ok=True)
        self._status_file().write_text(json.dumps({
            "flow_name": self.flow_name,
            "run_count": self.run_count,
            "success_direct_count": self.success_direct_count,
            "last_run_time": self.last_run_time,
            "tier": self.tier,
            "yaml_path": str(self.yaml_path) if self.yaml_path else None,
        }, indent=2))

    def record_success(self, verdict: str):
        self.run_count += 1
        self.last_run_time = time.time()
        self.last_verdict = verdict
        if verdict == "success_direct":
            self.success_direct_count += 1
        if self.success_direct_count >= REQUIRED_SUCCESSES:
            self.tier = "production"
        self._save_status()

    def record_failure(self):
        self.run_count += 1
        self.last_run_time = time.time()
        self.last_verdict = "failed"
        self._save_status()

    def can_promote(self) -> bool:
        return self.success_direct_count >= REQUIRED_SUCCESSES and self.tier != "production"

    def is_production(self) -> bool:
        return self.tier == "production"

    def summary(self) -> Dict[str, Any]:
        return {
            "flow_name": self.flow_name,
            "run_count": self.run_count,
            "success_direct_count": self.success_direct_count,
            "remaining": max(0, REQUIRED_SUCCESSES - self.success_direct_count),
            "tier": self.tier,
            "last_verdict": self.last_verdict,
            "can_promote": self.can_promote(),
        }


class FlowCompiler:
    def __init__(self, flows_dir: Path = FLOWS_DIR):
        self.flows_dir = flows_dir

    def find_yaml_flow(self, flow_name: str) -> Optional[Path]:
        candidates = [
            self.flows_dir / flow_name / f"{flow_name}.yaml",
            self.flows_dir / flow_name / "flow.yaml",
            self.flows_dir / f"{flow_name}.yaml",
            self.flows_dir / "sin_daemon" / f"{flow_name}.yaml",
            self.flows_dir / "sin_daemon" / "flow.yaml",
        ]
        for p in candidates:
            if p.exists():
                return p
        return None

    def read_yaml_flow(self, path: Path) -> Dict[str, Any]:
        with open(path) as f:
            return yaml.safe_load(f)

    def parse_steps(self, flow: Dict[str, Any]) -> list:
        steps = flow.get("steps", [])
        if isinstance(steps, dict):
            return list(steps.values())
        return steps

    def compile_to_tool_entry(self, flow_name: str, yaml_path: Path) -> Dict[str, Any]:
        flow = self.read_yaml_flow(yaml_path)
        steps = self.parse_steps(flow)

        command_list = []
        for step in steps:
            sid = step.get("id", "unknown")
            desc = step.get("description", sid)
            tool = step.get("tool", "")
            params = step.get("params", {})

            if tool:
                cmd_entry = {
                    "id": sid,
                    "tool": tool,
                    "description": desc,
                }
                if params:
                    cmd_entry["params"] = params
                command_list.append(cmd_entry)

        version = int(time.time())
        tool_name = f"{flow_name}_v{version}"

        return {
            "name": tool_name,
            "description": flow.get("description", f"Compiled flow: {flow_name}"),
            "strict": True,
            "frozen_at": version,
            "source": "FCTES-compiler",
            "promotion_tier": "production",
            "run_count": REQUIRED_SUCCESSES,
            "steps": command_list,
            "yaml_source": str(yaml_path),
        }

    def compile(self, flow_name: str) -> Optional[str]:
        yaml_path = self.find_yaml_flow(flow_name)
        if not yaml_path:
            return None

        status = FlowStatus(flow_name, yaml_path)
        if status.is_production() or status.can_promote():
            pass  # allowed to compile
        else:
            remaining = REQUIRED_SUCCESSES - status.success_direct_count
            print(f"[COMPILE] {flow_name}: noch {remaining} error-freie Runs nötig")
            print(f"           status: {status.success_direct_count}/{REQUIRED_SUCCESSES}")
            return None

        tool_entry = self.compile_to_tool_entry(flow_name, yaml_path)
        version = tool_entry["frozen_at"]

        registry.save(flow_name, version, str(yaml_path))
        tool_builder.register(flow_name, version)

        print(f"[COMPILED] {flow_name} → v{version} (PRODUCTION)")
        print(f"           {len(tool_entry['steps'])} Steps, tool: {tool_entry['name']}")
        return tool_entry["name"]

    def record_run(self, flow_name: str, verdict: str):
        status = FlowStatus(flow_name)
        if verdict.startswith("success"):
            status.record_success(verdict)
        else:
            status.record_failure()
        sm = status.summary()
        print(f"[FLOW] {flow_name}: {sm['success_direct_count']}/{REQUIRED_SUCCESSES} "
              f"({sm['tier']}) — {sm['remaining']} bis production")

    def get_status(self, flow_name: str) -> Dict[str, Any]:
        return FlowStatus(flow_name).summary()

    def list_flows(self) -> Dict[str, Dict[str, Any]]:
        results = {}
        if not self.flows_dir.exists():
            return results
        for d in self.flows_dir.iterdir():
            if d.is_dir():
                name = d.name
                results[name] = self.get_status(name)
        return results


def compile(flow_name: str) -> Optional[str]:
    return FlowCompiler().compile(flow_name)


def record_run(flow_name: str, verdict: str):
    FlowCompiler().record_run(flow_name, verdict)


def get_status(flow_name: str) -> Dict[str, Any]:
    return FlowCompiler().get_status(flow_name)