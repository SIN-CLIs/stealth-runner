import subprocess
import json
from pathlib import Path
from typing import Optional, Dict


class SkylightDriver:
    def __init__(self, pid: Optional[int] = None):
        self.pid = pid

    def click(
        self,
        element_index: Optional[int] = None,
        axpath: Optional[str] = None,
        expected_label: Optional[str] = None,
        expected_role: Optional[str] = None,
        post_delay: int = 0,
    ) -> Dict:
        if not self.pid:
            return {"status": "error", "reason": "no_pid"}
        if axpath:
            cmd = ["skylight-cli", "click", "--pid", str(self.pid), "--axpath", axpath]
        elif element_index is not None:
            cmd = ["skylight-cli", "click", "--pid", str(self.pid), "--element-index", str(element_index)]
        else:
            raise ValueError("Either axpath or element_index must be provided.")

        if expected_label:
            cmd.extend(["--expected-label", expected_label])
        if expected_role:
            cmd.extend(["--expected-role", expected_role])
        if post_delay:
            cmd.extend(["--post-delay", str(post_delay)])

        result = subprocess.run(cmd, capture_output=True, text=True)
        return json.loads(result.stdout)

    def type_text(
        self,
        element_index: int,
        text: str,
        post_delay: int = 0,
    ) -> Dict:
        if not self.pid:
            return {"status": "error", "reason": "no_pid"}
        cmd = [
            "skylight-cli",
            "type",
            "--pid", str(self.pid),
            "--element-index", str(element_index),
            "--text", text,
        ]
        if post_delay:
            cmd.extend(["--post-delay", str(post_delay)])
        result = subprocess.run(cmd, capture_output=True, text=True)
        return json.loads(result.stdout)

    def _screenshot_with_workaround(self, mode: str, output: str) -> dict:
        """Workaround for skylight-cli v0.2.0 ignoring --output.
        Uses a temporary directory to avoid polluting the current working directory.
        """
        import os, shutil, tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            old_cwd = os.getcwd()
            os.chdir(tmpdir_path)
            try:
                cwd_file = tmpdir_path / "skylight_screenshot.png"
                if cwd_file.exists():
                    cwd_file.unlink()
                cmd = ["skylight-cli", "screenshot", "--pid", str(self.pid), "--mode", mode]
                result = subprocess.run(cmd, capture_output=True, text=True)
            finally:
                os.chdir(old_cwd)
            if cwd_file.exists():
                shutil.copy2(str(cwd_file), output)
        return json.loads(result.stdout)

    def screenshot(self, mode: str = "som", output: str = "/tmp/screenshot.png") -> Dict:
        if not self.pid:
            return {"status": "error", "reason": "no_pid"}
        return self._screenshot_with_workaround(mode, output)

    def inspect(self, element_index: int) -> Dict:
        if not self.pid:
            return {"status": "error", "reason": "no_pid"}
        cmd = ["skylight-cli", "inspect", "--pid", str(self.pid), "--element-index", str(element_index)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return json.loads(result.stdout)

    def list_elements(self) -> Dict:
        if not self.pid:
            return {"status": "error", "reason": "no_pid", "elements": []}
        cmd = ["skylight-cli", "list-elements", "--pid", str(self.pid)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return json.loads(result.stdout)

    def find_element(self, label_contains: str, role: Optional[str] = None) -> Optional[Dict]:
        data = self.list_elements()
        for e in data.get("elements", []):
            el_label = str(e.get("label", "")).lower()
            if label_contains.lower() in el_label:
                if role is None or e.get("role") == role:
                    return e
        return None
