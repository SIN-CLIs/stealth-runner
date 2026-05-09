# Plan SR-35: Chrome Lease Manager + Safety Layer

## Overview
Make Chrome management safe: never kill user Chrome, lease profiles, auto-recover from crashes.

## KillGuard

```python
# cli/modules/session_manager.py (upgrade)

import os, signal, subprocess

BANNED_COMMANDS = [
    'pkill -f "Google Chrome"',
    'pkill -f heypiggy-bot',
    'killall Google Chrome',
    'killall "Google Chrome"',
    'kill -9 $(pgrep Chrome)',
]

class KillGuard:
    """Blocks any command that would kill user Chrome processes."""
    
    @staticmethod
    def is_safe(command: str) -> bool:
        command_clean = command.replace('"', '').replace("'", '')
        for banned in BANNED_COMMANDS:
            banned_clean = banned.replace('"', '').replace("'", '')
            if banned_clean in command_clean:
                return False
        return True
    
    @staticmethod
    def guard_subprocess(cmd_args: list) -> bool:
        """Check before subprocess.run(cmd_args)."""
        cmd_str = ' '.join(str(a) for a in cmd_args)
        if not KillGuard.is_safe(cmd_str):
            print(f"🛡️  KillGuard BLOCKED: {cmd_str}")
            return False
        return True
    
    @staticmethod
    def safe_kill(pid: int) -> bool:
        """Kill a SPECIFIC PID, only if it's a BOT Chrome."""
        if not SessionManager.is_bot_pid(pid):
            print(f"🛡️  KillGuard: PID {pid} is NOT a bot Chrome — refusing to kill")
            return False
        try:
            os.kill(pid, signal.SIGTERM)
            return True
        except:
            return False
```

## Lease System

```python
# ~/.stealth/chrome_lease.json
# WICHTIG: PIDs sind dynamisch — NIEMALS 71104 hardcodieren!
# Port 9224 ist veraltet — HeyPiggy nutzt Port 9999!
# Profile 902 ist obsolet — HeyPiggy nutzt Profile 901!
{
    "profiles": {
        # HeyPiggy: Profil 901 Kopie in /tmp, Port 9999
        # Dynamische PID via: curl http://127.0.0.1:9999/json | jq '.[].processId'
        "DYNAMIC_PROFILE_901": {
            "pid": "DYNAMIC",  # NIEMALS hardcodieren!
            "leased_by": "session-2026-05-09",
            "leased_at": 1746400000,
            "expires_at": 1746400300,
            "token": "abc123def456",
            "port": 9999,
            "profile": "Profile 901 (Jeremy)"
        }
    }
}
```

```python
class ProfileLease:
    def __init__(self, lease_file=Path.home() / ".stealth" / "chrome_lease.json"):
        self.file = lease_file
    
    def acquire(self, profile_dir: str) -> Optional[str]:
        """Try to lease a profile. Returns token or None."""
        data = self._read()
        
        # Check if profile already leased
        if profile_dir in data.get('profiles', {}):
            existing = data['profiles'][profile_dir]
            if existing['expires_at'] > time.time():
                print(f"🔒 Profile {profile_dir} already leased by {existing['leased_by']}")
                return None
        
        token = secrets.token_hex(16)
        data.setdefault('profiles', {})[profile_dir] = {
            'leased_by': os.environ.get('SESSION_ID', 'unknown'),
            'leased_at': time.time(),
            'expires_at': time.time() + 300,  # 5 min
            'token': token,
        }
        self._write(data)
        return token
    
    def release(self, profile_dir: str, token: str) -> bool:
        data = self._read()
        profile = data.get('profiles', {}).get(profile_dir, {})
        if profile.get('token') == token:
            del data['profiles'][profile_dir]
            self._write(data)
            return True
        return False
```

## Integration with SessionManager

```python
class SessionManager:
    @classmethod
    def close_all(cls):
        """Kill ALL bot Chrome instances, NEVER user Chrome."""
        pids = cls._find_bot_pids()
        for pid, profile in pids:
            print(f"  Closing bot Chrome PID={pid} (profile={profile})")
            KillGuard.safe_kill(pid)
            ProfileLease().release(profile, '*')
        cls._clear_registry()
        print(f"✅ Closed {len(pids)} bot Chrome instances")
    
    @classmethod
    def _find_bot_pids(cls):
        """Find ONLY bot Chrome PIDs (with ~/tmp/chrome-instance-B profile)."""
        r = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        pids = []
        for line in r.stdout.split('\n'):
            if '--user-data-dir=~/tmp/chrome-instance-B' in line:
                parts = line.split()
                if len(parts) >= 2:
                    pid = int(parts[1])
                    m = re.search(r'--user-data-dir=([^\s]+)', line)
                    profile = m.group(1) if m else None
                    pids.append((pid, profile))
        return pids
```

## Implementation: ~2h
