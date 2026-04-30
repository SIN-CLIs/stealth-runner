import subprocess, json, time, shutil

class StealthExecutor:
    def __init__(self, pid, wid):
        self.pid = pid
        self.wid = wid
        self.backend = "skylight-cli" if shutil.which("skylight-cli") else \
                       "cua-driver" if shutil.which("cua-driver") else "none"

    def screenshot(self, out_path=None):
        path = out_path or f"/tmp/stealth_{int(time.time())}.png"
        if self.backend == "skylight-cli":
            subprocess.run(["skylight-cli", "screenshot", "--pid", str(self.pid),
                           "--mode", "som", "--out", path], capture_output=True, timeout=15)
        else:
            subprocess.run(["cua-driver", "call", "screenshot", "--image-out", path],
                          capture_output=True, timeout=15)
        return {"status": "ok", "file": path, "backend": self.backend}

    def click(self, x=None, y=None, element_id=None):
        if self.backend == "skylight-cli":
            if element_id is not None:
                resp = self._run(["skylight-cli", "click", "--pid", str(self.pid),
                                  "--element-index", str(element_id)])
            elif x is not None and y is not None:
                resp = self._run(["skylight-cli", "click", "--pid", str(self.pid),
                                  "--point", f"{x},{y}"])
            else:
                return {"status": "error", "reason": "no target"}
        else:
            if element_id is not None:
                resp = self._cua_call("click_element", {"pid": self.pid, "element_id": element_id})
            elif x is not None and y is not None:
                resp = self._cua_call("click", {"pid": self.pid, "window_id": self.wid, "x": x, "y": y})
            else:
                return {"status": "error", "reason": "no target"}
        return {"status": "ok", "raw": resp, "backend": self.backend}

    def type_text(self, text):
        if self.backend == "skylight-cli":
            resp = self._run(["skylight-cli", "type", "--pid", str(self.pid), "--text", text])
        else:
            resp = self._cua_call("type_text", {"pid": self.pid, "window_id": self.wid, "text": text})
        return {"status": "ok", "raw": resp, "backend": self.backend}

    def get_window_state(self):
        if self.backend == "skylight-cli":
            resp = self._run(["skylight-cli", "get-window-state", "--pid", str(self.pid)])
            return {"status": "ok", "url": resp.get("url", ""), "title": resp.get("title", ""),
                    "tree_markdown": resp.get("tree_markdown", "")}
        else:
            resp = self._cua_call("get_window_state", {"pid": self.pid, "window_id": self.wid})
            sc = resp.get("structuredContent", resp)
            return {"status": "ok", "url": sc.get("url", ""), "title": sc.get("title", ""),
                    "tree_markdown": sc.get("tree_markdown", "")}

    def scroll(self, direction="down"):
        if self.backend == "skylight-cli":
            resp = self._run(["skylight-cli", "scroll", "--pid", str(self.pid),
                              "--direction", direction])
        else:
            resp = self._cua_call("scroll", {"pid": self.pid, "window_id": self.wid,
                                             "direction": direction})
        return {"status": "ok", "raw": resp, "backend": self.backend}

    def list_elements(self):
        if self.backend == "skylight-cli":
            resp = self._run(["skylight-cli", "list-elements", "--pid", str(self.pid)])
        else:
            ws = self.get_window_state()
            resp = {"elements": self._parse_ax_elements(ws.get("tree_markdown", ""))}
        return {"status": "ok", "raw": resp, "backend": self.backend}

    def _parse_ax_elements(self, tree_markdown):
        import re
        elements = []
        for line in tree_markdown.split("\n"):
            m = re.match(r'^\s*-\s*\[(\d+)\]\s*AX(\w+)\s*(?:"([^"]*)")?', line)
            if m:
                elements.append({"id": int(m.group(1)), "role": m.group(2),
                                "label": (m.group(3) or "").strip()[:60]})
        return elements

    def _run(self, cmd):
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {"raw_stdout": result.stdout[:200], "raw_stderr": result.stderr[:200]}

    def _cua_call(self, tool, args):
        cmd = ["cua-driver", "call", tool]
        if args:
            cmd.append(json.dumps(args))
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {"raw_stdout": result.stdout[:200]}
