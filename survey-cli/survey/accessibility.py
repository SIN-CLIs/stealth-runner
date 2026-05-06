"""Chrome Accessibility Manager — grant + verify + maintain.

SOTA: NEVER kill Chrome after granting Accessibility. Chrome must stay
running with --force-renderer-accessibility. cua-driver needs this.

Usage:
    from survey.accessibility import ensure_accessibility
    ensure_accessibility()  # Call ONCE at daemon startup
"""

import subprocess
import json
import time
import os


def is_accessibility_enabled():
    """Check if cua-driver can read Chrome's AX-Tree."""
    try:
        result = subprocess.run(
            ["cua-driver", "call", "list_windows"],
            capture_output=True, text=True, timeout=10
        )
        data = json.loads(result.stdout)
        for w in data.get("windows", []):
            pid = w.get("pid", 0)
            wid = w.get("window_id", 0)
            # Try to get AX-Tree for a Chrome window
            owner = w.get("owner", {}).get("name", "")
            title = (w.get("title") or "").lower()
            if "google chrome" in owner.lower() or "chrome" in owner.lower():
                result2 = subprocess.run(
                    ["cua-driver", "call", "get_window_state"],
                    input=json.dumps({"pid": pid, "window_id": wid}),
                    capture_output=True, text=True, timeout=10
                )
                tree = json.loads(result2.stdout)
                children = len(tree.get("children", []))
                if children > 0:
                    return True
        return False
    except Exception:
        return False


def grant_accessibility():
    """Grant Accessibility permission to Google Chrome via tccutil."""
    try:
        subprocess.run(
            ["tccutil", "reset", "Accessibility", "com.google.Chrome"],
            capture_output=True, text=True, timeout=10
        )
        print("[ACCESS] Chrome Accessibility permission reset — restart Chrome to apply")
        return True
    except Exception as e:
        print(f"[ACCESS] Failed to grant: {e}")
        return False


def launch_chrome_with_accessibility(port=9999, url="https://www.heypiggy.com/?page=dashboard"):
    """Launch Chrome with --force-renderer-accessibility on fixed port.
    
    Uses fixed profile /tmp/heypiggy-bot to maintain session + cookies.
    NEVER kills existing Chrome — reuses it if already running.
    """
    # Check if Chrome is already running on the port
    import urllib.request
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=3)
        print(f"[ACCESS] Chrome already running on port {port}")
        return True
    except Exception:
        pass

    # Launch Chrome
    profile_dir = "/tmp/heypiggy-bot"
    cmd = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        f"--remote-debugging-port={port}",
        "--remote-allow-origins=*",
        "--no-first-run",
        "--no-default-browser-check",
        "--force-renderer-accessibility",
        f"--user-data-dir={profile_dir}",
        url,
    ]
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"[ACCESS] Chrome launched on port {port} (profile: {profile_dir})")
        time.sleep(8)
        return True
    except Exception as e:
        print(f"[ACCESS] Chrome launch failed: {e}")
        return False


def ensure_accessibility(port=9999, url="https://www.heypiggy.com/?page=dashboard"):
    """Ensure Chrome is running with Accessibility enabled.

    Call this ONCE at daemon startup. Will restart Chrome if needed
    to apply permission changes.

    Returns:
        True if Accessibility is working, False if user action needed.
    """
    # Check if already working
    if is_accessibility_enabled():
        print("[ACCESS] ✅ Chrome Accessibility is enabled")
        return True

    # Grant permission
    print("[ACCESS] Granting Chrome Accessibility permission...")
    grant_accessibility()

    # Restart Chrome to apply permission (kill + relaunch)
    print("[ACCESS] Restarting Chrome to apply permission...")
    import subprocess as sp
    sp.run(["pkill", "-f", "Google Chrome"], capture_output=True)
    time.sleep(3)

    launch_chrome_with_accessibility(port=port, url=url)

    # Wait and re-check
    time.sleep(8)
    if is_accessibility_enabled():
        print("[ACCESS] ✅ Chrome Accessibility now working")
        return True

    # Still not working — user needs to approve macOS dialog
    print("[ACCESS] ⚠️  macOS Permission dialog may have appeared")
    print("[ACCESS] → Please open System Settings → Privacy → Accessibility")
    print("[ACCESS] → Find 'Google Chrome' and enable the toggle")
    print("[ACCESS] → Then restart the daemon")
    return False


def start_cua_daemon():
    """Start cua-driver daemon if not running."""
    try:
        result = subprocess.run(["pgrep", "-f", "cua-driver serve"], 
                               capture_output=True, text=True, timeout=5)
        if result.stdout.strip():
            return True
    except Exception:
        pass

    try:
        subprocess.Popen(
            ["nohup", "cua-driver", "serve"],
            stdout=open("/tmp/cua-daemon.log", "w"),
            stderr=subprocess.STDOUT
        )
        time.sleep(2)
        print("[ACCESS] cua-driver daemon started")
        return True
    except Exception as e:
        print(f"[ACCESS] cua-driver daemon failed: {e}")
        return False
