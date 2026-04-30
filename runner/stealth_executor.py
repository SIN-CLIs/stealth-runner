import subprocess, json, time, shutil, os

class StealthExecutor:
    def __init__(self, pid, wid):
        self.pid = pid
        self.wid = wid

    @property
    def backend(self):
        return "skylight-cli"

    @property
    def has_unmask(self):
        return shutil.which("unmask") is not None or shutil.which("unmask-cli") is not None

    def screenshot(self, out_path=None, mode="som"):
        path = out_path or os.path.join("/tmp", f"stealth_{int(time.time())}.png")
        path = os.path.realpath(path)
        subprocess.run(["skylight-cli", "screenshot", "--pid", str(self.pid),
                       "--mode", mode, "--out", path], capture_output=True, timeout=15)
        return {"status": "ok", "file": path, "mode": mode}

    def click(self, element_index=None, x=None, y=None):
        if element_index is not None:
            cmd = ["skylight-cli", "click", "--pid", str(self.pid),
                   "--element-index", str(element_index)]
        elif x is not None and y is not None:
            cmd = ["skylight-cli", "click", "--pid", str(self.pid),
                   "--x", str(x), "--y", str(y)]
        else:
            return {"status": "error", "reason": "no element_index or coordinates"}
        resp = self._run(cmd)
        return {"status": "ok", "raw": resp}

    def type_text(self, text):
        resp = self._run(["skylight-cli", "type", "--pid", str(self.pid), "--text", text])
        return {"status": "ok", "raw": resp}

    def get_window_state(self):
        resp = self._run(["skylight-cli", "screenshot", "--pid", str(self.pid),
                         "--mode", "som", "--include-tree"])
        return {"status": "ok", "tree_markdown": json.dumps(resp.get("elements", [])),
                "url": "", "title": ""}

    def scroll(self, direction="down"):
        resp = self._run(["skylight-cli", "scroll", "--pid", str(self.pid),
                         "--direction", direction])
        return {"status": "ok", "raw": resp}

    def list_elements(self):
        out = subprocess.run(["skylight-cli", "click", "--pid", str(self.pid),
                             "--element-index", "0", "--dry-run"],
                            capture_output=True, text=True, timeout=10)
        return {"status": "ok", "raw": out.stderr[:200]}

    def verify_stealth(self):
        if not self.has_unmask:
            return {"status": "ok", "detected": False, "backend": "none"}
        unmask_cmd = "unmask" if shutil.which("unmask") else "unmask-cli"
        resp = self._run([unmask_cmd, "verify-stealth", "--pid", str(self.pid)])
        return {"status": "ok", "detected": resp.get("detected", False), "backend": "unmask-cli"}

    def _run(self, cmd):
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {"raw_stdout": result.stdout[:200], "raw_stderr": result.stderr[:200]}
