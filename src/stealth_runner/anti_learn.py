"""Anti-Learning Module — Error-to-Recovery Generator."""
import json, subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

BRAIN_PATH = Path("../Infra-SIN-Global-Brain/brain/projects/heypiggy-survey")
ERROR_FILE = BRAIN_PATH / "memory" / "error_taxonomy.json"

ERROR_PATTERNS = {
    "timeout": {"patterns": ["timeout","timed out","abort"], "recovery": "retry", "retries": 3},
    "stale_element": {"patterns": ["stale","not attached"], "recovery": "refresh", "retries": 2},
    "element_not_found": {"patterns": ["element not found","NoSuch","AXError","not found"], "recovery": "wait_retry", "retries": 2},
    "disqualified": {"patterns": ["disqualified","passt nicht","screen.out","over quota"], "recovery": "skip", "retries": 0},
    "captcha": {"patterns": ["captcha","recaptcha","verify human"], "recovery": "captcha_fallback", "retries": 1},
    "voiceover_expired": {"patterns": ["no on-screen window","JSONDecodeError","Expecting value"], "recovery": "restart_voiceover", "retries": 3},
    "popup_blocking": {"patterns": ["Anmelden","Registrieren"], "recovery": "close_popup", "retries": 1},
}

def learn_from_error(error_msg: str, command: str = "", session_id: str = None) -> Dict:
    etype = classify_error(error_msg)
    strategy = ERROR_PATTERNS.get(etype, {"recovery": "log_skip", "retries": 0})
    
    fact = {"id": f"err-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}",
            "type": "error", "error_type": etype, "command": command[:200],
            "output": error_msg[:300], "recovery": strategy["recovery"],
            "timestamp": datetime.now(timezone.utc).isoformat()}
    
    rule = {"id": f"rec-{etype}", "type": "recovery", "trigger": etype,
            "action": strategy["recovery"], "max_retries": strategy["retries"],
            "success_rate": 0.0}
    
    store(fact, rule)
    
    # Generate recovery skill
    skill_dir = Path(f"stealth-skills/captured/recovery-{etype}")
    if not skill_dir.exists():
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(f"# recovery-{etype}\nAuto-recovery: {strategy['recovery']}\nRetries: {strategy['retries']}")
        cli = (skill_dir / f"recovery-{etype}")
        cli.write_text("#!/bin/bash\n# Auto-recovery for: " + etype + "\nset -euo pipefail\nPID=\"${1:?PID}\"\n\n")
        cli.chmod(0o755)
    
    return {"status": "learned", "error_type": etype, "recovery": strategy["recovery"]}

def classify_error(output: str) -> str:
    ol = output.lower()
    for etype, cfg in ERROR_PATTERNS.items():
        for p in cfg["patterns"]:
            if p.lower() in ol: return etype
    return "unknown"

def store(fact: Dict, rule: Dict):
    ERROR_FILE.parent.mkdir(parents=True, exist_ok=True)
    try: data = json.loads(ERROR_FILE.read_text())
    except: data = {"errors":[], "rules":[]}
    data["errors"].append(fact); data["rules"].append(rule)
    ERROR_FILE.write_text(json.dumps(data, indent=2))

if __name__ == "__main__":
    import sys
    msg = sys.argv[1] if len(sys.argv) > 1 else "test error"
    print(json.dumps(learn_from_error(msg), indent=2))
