#!/usr/bin/env python3
# Session Manager — SOTA Multi-Instance Chrome Management
#
# BANNED METHODS — NIEMALS VERWENDEN (siehe /banned.md):
#   ❌ playstealth launch — setzt NICHT --force-renderer-accessibility
#   ❌ webauto-nodriver — ABSOLUT BANNED
#   ❌ cua-driver click (raw index) — instabil, nutze tool_click.py
#   ❌ --remote-allow-origins=* (ohne Quotes) — zsh glob expansion
#   ❌ /tmp/heypiggy-bot (fixed profile) — korruptiert nach Neustart
#   ❌ Hardcoded PIDs — dynamisch, niemals hardcodieren
#   ❌ pkill -f "Google Chrome" — tötet USER Chrome
#   ❌ killall Google Chrome — tötet ALLE Chrome
#   ❌ skylight-cli click --element-index — Index instabil
#
# KORREKT:
#   ✅ --remote-allow-origins="*" (MIT Anführungszeichen)
#   ✅ --user-data-dir="/tmp/heypiggy-new-$(date +%s)"
#   ✅ --force-renderer-accessibility
#   ✅ NUR tool_*.py verwenden (nicht rohes cua-driver)

import os, json, subprocess, time, re, signal

SESSIONS_FILE = os.path.expanduser("~/.stealth/sessions.json")
os.makedirs(os.path.dirname(SESSIONS_FILE), exist_ok=True)


def _run(cmd, input_data=None):
    p = subprocess.run(cmd, input=input_data, capture_output=True, text=True)
    return p


def _main_chrome_pids():
    r = _run(['ps', 'aux'])
    main_pids = set()
    profile_map = {}
    for line in r.stdout.split('\n'):
        if '--user-data-dir=/tmp/heypiggy-new-' not in line:
            continue
        parts = line.split()
        if len(parts) < 11:
            continue
        try:
            pid = int(parts[1])
        except ValueError:
            continue
        m = re.search(r'--user-data-dir=([^\s]+)', line)
        profile_dir = m.group(1) if m else None
        cmdline = ' '.join(parts[10:])
        if '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' in cmdline:
            main_pids.add(pid)
            profile_map[pid] = profile_dir
    return [(pid, profile_map.get(pid)) for pid in main_pids]


def _wid_from_pid(pid):
    r = _run(['cua-driver', 'call', 'list_windows'])
    try:
        data = json.loads(r.stdout)
        for w in data.get("windows", []):
            if w.get("pid") == pid and w.get("bounds", {}).get("height", 0) > 100:
                return w.get("window_id")
    except:
        pass
    return None


class SessionManager:
    def __init__(self):
        self.sessions = self._load()

    def _load(self):
        if os.path.exists(SESSIONS_FILE):
            try:
                with open(SESSIONS_FILE) as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save(self):
        with open(SESSIONS_FILE, 'w') as f:
            json.dump(self.sessions, f, indent=2)

    def register(self, name, pid, profile_dir, wid=None, url=None):
        self.sessions[name] = {
            "pid": pid, "profile_dir": profile_dir, "wid": wid, "url": url,
            "status": "active", "created_at": time.time(), "last_seen": time.time()
        }
        self._save()

    def unregister(self, name):
        if name in self.sessions:
            del self.sessions[name]
            self._save()

    def get(self, name):
        return self.sessions.get(name)

    def touch(self, name):
        if name in self.sessions:
            self.sessions[name]["last_seen"] = time.time()
            self._save()

    def list_all(self):
        return {k: v for k, v in self.sessions.items() if v["status"] == "active"}

    def reconcile(self):
        active = set(pid for pid, _ in _main_chrome_pids())
        stale = []
        for name, s in self.sessions.items():
            if s["status"] == "active" and s["pid"] not in active:
                stale.append(name)
                s["status"] = "stale"
        if stale:
            self._save()
        return stale

    def scan_active(self):
        return [{"pid": pid, "profile_dir": pd} for pid, pd in _main_chrome_pids()]

    def find_session(self, name):
        self.reconcile()
        return self.sessions.get(name)

    def is_alive(self, name):
        s = self.find_session(name)
        if not s:
            return False
        active = set(pid for pid, _ in _main_chrome_pids())
        return s["pid"] in active

    def launch(self, name, url="https://heypiggy.com/?page=dashboard"):
        self.reconcile()
        s = self.sessions.get(name)
        if s and s["status"] == "active":
            pid = s["pid"]
            active = set(p for p, _ in _main_chrome_pids())
            if pid in active:
                wid = _wid_from_pid(pid)
                s["wid"] = wid
                s["last_seen"] = time.time()
                self._save()
                return {"status": "ok", "pid": pid, "wid": wid,
                        "profile_dir": s["profile_dir"], "reused": True}

        for pid, profile_dir in _main_chrome_pids():
            wid = _wid_from_pid(pid)
            self.register(name, pid, profile_dir, wid=wid, url=url)
            return {"status": "ok", "pid": pid, "wid": wid,
                    "profile_dir": profile_dir, "reused": True}

        # ❌ BANNED: playstealth launch — setzt NICHT --force-renderer-accessibility!
        # Stattdessen: Chrome MANUELL starten mit korrekten Flags
        import time
        profile_dir = f"/tmp/heypiggy-new-{int(time.time())}"
        cmd = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            f"--remote-debugging-port=9999",
            "--remote-allow-origins=\"*\"",
            "--force-renderer-accessibility",
            "--no-first-run",
            "--no-default-browser-check",
            f"--user-data-dir={profile_dir}",
            url,
        ]
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(8)

        # PID finden
        pid = None
        ps_out = subprocess.run(["ps", "aux"], capture_output=True, text=True).stdout
        for line in ps_out.split('\n'):
            if profile_dir in line and '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' in line:
                parts = line.split()
                if len(parts) > 1:
                    try:
                        pid = int(parts[1])
                        break
                    except ValueError:
                        pass

        if not pid:
            return {"status": "error", "reason": "chrome_launch_failed"}

        self.register(name, pid, profile_dir, url=url)
        return {"status": "ok", "pid": pid, "wid": None,
                "profile_dir": profile_dir, "reused": False}

    def close(self, name):
        s = self.find_session(name)
        if not s:
            return {"status": "error", "reason": "session_not_found"}
        pid = s["pid"]
        try:
            os.kill(pid, signal.SIGTERM)
            time.sleep(1)
            try:
                os.kill(pid, 0)
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
        except OSError:
            pass
        self.unregister(name)
        return {"status": "ok", "closed_pid": pid}

    def close_all(self):
        closed = []
        for name in list(self.sessions.keys()):
            r = self.close(name)
            if r["status"] == "ok":
                closed.append(name)
        return closed

    def save_auth_state(self, name):
        s = self.find_session(name)
        if not s:
            return {"status": "error", "reason": "session_not_found"}
        auth_file = os.path.expanduser(f"~/.stealth/auth_{name}.json")
        s["auth_state"] = auth_file
        self._save()
        return {"status": "ok", "auth_file": auth_file}

    def load_auth_state(self, name):
        s = self.find_session(name)
        if not s:
            return None
        return s.get("auth_state")


if __name__ == "__main__":
    import sys
    sm = SessionManager()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"

    if cmd == "list":
        print("=== Active Sessions ===")
        sm.reconcile()
        for name, s in sm.list_all().items():
            print(f"  {name}: pid={s['pid']} profile={s['profile_dir']} wid={s.get('wid')}")

    elif cmd == "scan":
        print("=== Running Chrome Processes ===")
        for p in sm.scan_active():
            print(f"  PID={p['pid']} profile={p['profile_dir']}")

    elif cmd == "reconcile":
        stale = sm.reconcile()
        print(f"Removed stale: {stale}" if stale else "No stale sessions")

    elif cmd == "close" and len(sys.argv) > 2:
        print(sm.close(sys.argv[2]))

    elif cmd == "close-all":
        print(f"Closed: {sm.close_all()}")

    elif cmd == "launch" and len(sys.argv) > 2:
        url = sys.argv[3] if len(sys.argv) > 3 else "https://heypiggy.com/?page=dashboard"
        result = sm.launch(sys.argv[2], url)
        print(json.dumps(result, indent=2))