import subprocess, json, time

class StealthExecutor:
    def __init__(self, pid, wid):
        self.pid = pid
        self.wid = wid

    def screenshot(self, out_path=None):
        path = out_path or f"/tmp/stealth_{int(time.time())}.png"
        subprocess.run(['cua-driver', 'call', 'screenshot', '--image-out', path],
                       capture_output=True, timeout=15)
        return {"status": "ok", "file": path}

    def click(self, x=None, y=None, element_id=None):
        if element_id is not None:
            resp = self._cua_call('click_element', {'pid': self.pid, 'element_id': element_id})
        elif x is not None and y is not None:
            resp = self._cua_call('click', {'pid': self.pid, 'window_id': self.wid, 'x': x, 'y': y})
        else:
            return {"status": "error", "reason": "no target specified"}
        return {"status": "ok", "raw": resp}

    def type_text(self, text):
        resp = self._cua_call('type_text', {'pid': self.pid, 'window_id': self.wid, 'text': text})
        return {"status": "ok", "raw": resp}

    def get_window_state(self):
        resp = self._cua_call('get_window_state', {'pid': self.pid, 'window_id': self.wid})
        sc = resp.get('structuredContent', resp)
        return {"status": "ok", "url": sc.get('url', ''), "title": sc.get('title', ''),
                "tree_markdown": sc.get('tree_markdown', '')}

    def scroll(self, direction='down'):
        resp = self._cua_call('scroll', {'pid': self.pid, 'window_id': self.wid, 'direction': direction})
        return {"status": "ok", "raw": resp}

    def _cua_call(self, tool, args):
        cmd = ['cua-driver', 'call', tool]
        if args:
            cmd.append(json.dumps(args))
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {"raw_stdout": result.stdout[:200]}
