"""Skill Capture Loop + Global Brain Bridge."""
import json, subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict

SKILLS_DIR = Path("stealth-skills")
CAPTURED_DIR = SKILLS_DIR / "captured"
TEMPLATES_DIR = SKILLS_DIR / "_templates"
REGISTRY_PATH = SKILLS_DIR / "_registry.json"
BRAIN_PATH = Path("../Infra-SIN-Global-Brain/brain/projects/heypiggy-survey")

def learn_from_session(session_id: str = None) -> dict:
    print("🧠 Skill Capture Loop...")
    
    result = subprocess.run(["screen-follow", "trace", "--last", "200"],
                          capture_output=True, text=True, timeout=10)
    if result.returncode != 0:
        return {"status": "error", "reason": "audit_unavailable"}
    
    commands = []
    for line in result.stdout.strip().splitlines():
        try:
            event = json.loads(line)
            if event.get("type") == "mouse_down" and event.get("elementLabel"):
                label = event["elementLabel"]
                y = event.get("y", 0)
                if y > 30:
                    commands.append(f"# Klick: '{label}'")
                    commands.append(f"skylight-cli click --pid $PID --label '{label}'")
        except: pass
    
    if not commands:
        return {"status": "no_commands"}
    
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    skill_name = f"captured-{timestamp}"
    
    # CLI bauen
    cli_tpl = (TEMPLATES_DIR / "cli-template.sh").read_text()
    filled = cli_tpl.replace("{{SKILL_NAME}}", skill_name)\
        .replace("{{SHORT_DESCRIPTION}}", f"Erfasst {timestamp}")\
        .replace("{{DATE}}", timestamp)\
        .replace("{{SESSION_ID}}", session_id or "latest")\
        .replace("{{CAPTURED_COMMANDS}}", "\n".join(commands[-10:]))
    
    cli_dir = CAPTURED_DIR / skill_name; cli_dir.mkdir(parents=True, exist_ok=True)
    (cli_dir / skill_name).write_text(filled); (cli_dir / skill_name).chmod(0o755)
    
    # SKILL.md
    tpl = (TEMPLATES_DIR / "SKILL-template.md").read_text()
    (cli_dir / "SKILL.md").write_text(tpl.replace("{{SKILL_NAME}}", skill_name)
        .replace("{{SHORT_DESCRIPTION}}", "Erfasster Flow").replace("{{DATE}}", timestamp)
        .replace("{{SESSION_ID}}", session_id or "latest").replace("{{TRIGGER}}", "auto")
        .replace("{{FLOW_DESCRIPTION}}", "Aus Audit-Log").replace("{{PID}}", "$PID"))
    
    for t in ("states-template.md", "recovery-template.md"):
        (cli_dir / t.replace("-template.md", ".md")).write_text((TEMPLATES_DIR / t).read_text())
    
    # Registry
    try: reg = json.loads(REGISTRY_PATH.read_text())
    except: reg = {"skills": {}, "captured": []}
    reg["captured"].append({"name": skill_name, "cli": f"captured/{skill_name}/{skill_name}", "status": "new"})
    REGISTRY_PATH.write_text(json.dumps(reg, indent=2, ensure_ascii=False))
    
    # Global Brain
    brain = push_to_global_brain(skill_name, commands)
    
    return {"status": "created", "skill": skill_name, "commands": len(commands), "global_brain": brain}


def push_to_global_brain(skill_name: str, commands: List[str]) -> Dict:
    """Schreibt Erkenntnisse in den Global Brain."""
    if not BRAIN_PATH.exists():
        return {"status": "brain_unavailable"}
    
    trigger = "auto-detected"
    for cmd in commands:
        if "click" in cmd:
            trigger = cmd.split("'")[1] if "'" in cmd else "click"
            break
    
    facts_file = BRAIN_PATH / "memory" / "facts.json"
    rules_file = BRAIN_PATH / "memory" / "rules.json"
    
    fact = {"id": f"fact-{skill_name}", "type": "discovery",
            "content": f"Strategie '{skill_name}' für '{trigger}'", "quality_score": 0.9}
    rule = {"id": f"rule-{skill_name}", "type": "strategy",
            "trigger": trigger, "action": f"Execute: {skill_name}", "success_rate": 1.0}
    
    for fp, entry in [(facts_file, fact), (rules_file, rule)]:
        try: data = json.loads(fp.read_text())
        except: data = []
        data.append(entry)
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(json.dumps(data, indent=2))
    
    return {"facts_added": 1, "rules_added": 1, "trigger": trigger}


if __name__ == "__main__":
    import sys
    print(json.dumps(learn_from_session(sys.argv[1] if len(sys.argv) > 1 else None), indent=2))
