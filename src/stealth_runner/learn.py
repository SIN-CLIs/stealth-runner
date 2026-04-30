"""Skill Capture Loop mit Global‑Brain‑Integration.
Extrahiert aus screen‑follow‑Audit‑Sessions atomare CLI‑Skills
und schreibt Erkenntnisse als Facts & Rules in den Global Brain."""

import json, subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional

SKILLS_DIR = Path("stealth-skills")
TEMPLATE_DIR = SKILLS_DIR / "_templates"
REGISTRY_PATH = SKILLS_DIR / "_registry.json"
BRAIN_PATH = Path("../Infra-SIN-Global-Brain/brain/projects/heypiggy-survey")

def learn_from_session(session_id: Optional[str] = None) -> Dict:
    print("🧠 Skill Capture Loop + Global Brain...")
    
    result = subprocess.run(["screen-follow", "trace", "--last", "500"],
                          capture_output=True, text=True, timeout=10)
    if result.returncode != 0:
        return {"status": "error", "reason": "audit_unavailable"}
    
    commands = []
    for line in result.stdout.strip().splitlines():
        try:
            event = json.loads(line)
            if event.get("type") == "mouse_down" and event.get("elementLabel"):
                label = event["elementLabel"]; y = event.get("y", 0)
                if y > 30:
                    commands.append(f"# Klick: '{label}'")
                    commands.append(f"skylight-cli click --pid $PID --label '{label}'")
        except: pass
    
    if not commands: return {"status": "no_commands"}
    
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    skill_name = f"captured-{timestamp}"
    
    cli_tpl = (TEMPLATE_DIR / "cli-template.sh").read_text()
    filled = cli_tpl.replace("{{SKILL_NAME}}", skill_name)\
        .replace("{{SHORT_DESCRIPTION}}", f"Erfasst {timestamp}")\
        .replace("{{DATE}}", timestamp).replace("{{SESSION_ID}}", session_id or "latest")\
        .replace("{{CAPTURED_COMMANDS}}", "\n".join(commands[-10:]))
    
    cli_path = SKILLS_DIR / "captured" / skill_name
    cli_path.mkdir(parents=True, exist_ok=True)
    (cli_path / skill_name).write_text(filled); (cli_path / skill_name).chmod(0o755)
    
    for tpl_name in ("SKILL-template.md", "states-template.md", "recovery-template.md"):
        tpl_text = (TEMPLATE_DIR / tpl_name).read_text()
        target = tpl_name.replace("-template.md", ".md")
        (cli_path / target).write_text(tpl_text.replace("{{SKILL_NAME}}", skill_name))
    
    update_registry(skill_name, f"captured/{skill_name}/{skill_name}")
    brain_result = push_to_global_brain(skill_name, commands)
    
    print(f"✅ Skill: {skill_name} | Brain: {brain_result}")
    return {"status": "created", "skill": skill_name, "commands": len(commands), "global_brain": brain_result}

def update_registry(skill_name: str, cli_rel_path: str):
    try: reg = json.loads(REGISTRY_PATH.read_text())
    except: reg = {"skills": {}, "captured": []}
    reg["captured"].append({"name": skill_name, "cli": cli_rel_path, "status": "new",
                            "captured_at": datetime.now(timezone.utc).isoformat()})
    REGISTRY_PATH.write_text(json.dumps(reg, indent=2, ensure_ascii=False))

def push_to_global_brain(skill_name: str, commands: List[str]) -> Dict:
    facts_file = BRAIN_PATH / "memory" / "facts.json"
    rules_file = BRAIN_PATH / "memory" / "rules.json"
    
    trigger = "unknown"; strategy = "generic"
    for cmd in commands:
        if "matrix" in cmd: trigger = "matrix_question"; strategy = "question-answering"
        elif "stern" in cmd or "star" in cmd: trigger = "star_rating"; strategy = "question-answering"
        elif "click" in cmd: strategy = "gui-navigation"
    
    fact = {"id": f"fact-{skill_name}", "type": "discovery",
            "content": f"Strategie '{skill_name}' für '{trigger}'", "quality_score": 0.9}
    rule = {"id": f"rule-{skill_name}", "type": "strategy",
            "trigger": trigger, "action": f"Execute: {skill_name}", "success_rate": 1.0}
    
    for fp, entry in [(facts_file, fact), (rules_file, rule)]:
        fp.parent.mkdir(parents=True, exist_ok=True)
        try: data = json.loads(fp.read_text())
        except: data = []
        data.append(entry)
        fp.write_text(json.dumps(data, indent=2))
    
    return {"facts_added": 1, "rules_added": 1, "trigger": trigger, "strategy": strategy}

if __name__ == "__main__":
    import sys
    print(json.dumps(learn_from_session(sys.argv[1] if len(sys.argv) > 1 else None), indent=2))
