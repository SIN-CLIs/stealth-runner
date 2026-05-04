"""Command validator that detects failure patterns and logs fixes."""
import re, os
from datetime import datetime

LEARN_FILE = os.path.expanduser("~/dev/stealth-runner/learn.md")

FAILURE_PATTERNS = {
    "wrong_pid": r"Kein Chrome Fenster gefunden|PID:\d+ nicht gefunden",
    "cdp_instead_of_cua": r"Runtime\.evaluate.*dispatchEvent|\.querySelector\('input\[type=email\]",
    "fixed_sleep": r"time\.sleep\(\s*(?:[4-9]|\d{2,})\s*\)",
    "overwrite_md": r"cat\s*>\s*\S+\.md|write.*\.md",
    "no_btn_found": r"NOBTN|NO-WEITER|No survey content",
}

FIX_HINTS = {
    "wrong_pid": "Nutze `lsof -ti:PORT` für aktuelle PID",
    "cdp_instead_of_cua": "CUA-ONLY Login Box: heypiggy_login(pid, cdp_port)",
    "fixed_sleep": "1s Polling statt fixed sleep! poll_until()",
    "overwrite_md": "NUR `>>` append! Niemals `>` oder `write`!",
    "no_btn_found": "Prüfe ob andere Elemente (Textfeld) die Seite blockieren",
}

def validate(cmd, output, exit_code):
    matched = [n for n,r in FAILURE_PATTERNS.items() if re.search(r, output)]
    is_error = exit_code != 0 or matched
    fix = " ".join(FIX_HINTS.get(m,"") for m in matched)
    return {"is_error": is_error, "patterns": matched, "fix": fix}

def log_failure(cmd, patterns, fix, details=""):
    with open(LEARN_FILE, "a") as f:
        f.write(f"\n## ❌ FEHLER – {datetime.now().strftime('%H:%M:%S')}\n")
        f.write(f"- Command: `{cmd[:80]}`\n- Muster: {patterns}\n- FIX: {fix}\n- Details: {details[:200]}\n")

def log_success(name, details=""):
    with open(LEARN_FILE, "a") as f:
        f.write(f"\n## ✅ ERFOLG – {datetime.now().strftime('%H:%M:%S')}\n")
        f.write(f"- Befehl: {name}\n- Details: {details[:200]}\n")
