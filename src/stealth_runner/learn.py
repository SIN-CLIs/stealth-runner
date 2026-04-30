"""Skill Capture Loop — parst screen-follow Audit-Log (type: mouse_down, etc.)."""
import json, subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional

SKILLS_DIR = Path("stealth-skills")
TEMPLATE_DIR = SKILLS_DIR / "_templates"
REGISTRY_PATH = SKILLS_DIR / "_registry.json"
BRAIN_PATH = Path("../Infra-SIN-Global-Brain/brain/projects/heypiggy-survey")

def learn_from_session(session_id: Optional[str] = None) -> Dict:
    print("🧠 Skill Capture Loop...")
    
    result = subprocess.run(["screen-follow", "trace", "--last", "500"],
                          capture_output=True, text=True, timeout=10)
    if result.returncode != 0:
        return {"status": "error", "reason": "audit_unavailable"}
    
    commands = []
    seen_labels = set()
    
    for line in result.stdout.strip().splitlines():
        try:
            event = json.loads(line)
        except:
            continue
        
        etype = event.get("type", "")
        label = event.get("elementLabel", "") or ""
        role = event.get("elementRole", "") or ""
        chars = event.get("characters", "") or ""
        
        # CLICK: Element-Label als Kommando speichern
        if etype == "mouse_down" and label and label not in seen_labels:
            seen_labels.add(label)
            commands.append(f"# Klick auf {role}: \"{label}\"")
            commands.append(f"skylight-cli click --pid $PID --label '{label}'")
        
        # TYPE: Tastatureingaben sammeln
        if etype == "key_down" and chars.strip():
            commands.append(f"# Tasten: \"{chars}\"")
    
    if not commands:
        return {"status": "no_commands"}
    
    # Dedupliziere und begrenze
    unique = list(dict.fromkeys(commands))  # preserve order, remove dups
    unique = unique[-30:]  # max 30 commands
    
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    skill_name = f"captured-{timestamp}"
    
    # CLI bauen
    cli_tpl = (TEMPLATE_DIR / "cli-template.sh").read_text()
    filled = cli_tpl.replace("{{SKILL_NAME}}", skill_name)\
        .replace("{{SHORT_DESCRIPTION}}", f"Erfasst {timestamp}")\
        .replace("{{DATE}}", timestamp).replace("{{SESSION_ID}}", session_id or "latest")\
        .replace("{{CAPTURED_COMMANDS}}", "\n".join(unique))
    
    cli_path = SKILLS_DIR / "captured" / skill_name
    cli_path.mkdir(parents=True, exist_ok=True)
    (cli_path / skill_name).write_text(filled); (cli_path / skill_name).chmod(0o755)
    
    # SKILL.md
    for tpl_name in ("SKILL-template.md", "states-template.md", "recovery-template.md"):
        tpl_text = (TEMPLATE_DIR / tpl_name).read_text()
        target = tpl_name.replace("-template.md", ".md")
        (cli_path / target).write_text(tpl_text.replace("{{SKILL_NAME}}", skill_name)
            .replace("{{SHORT_DESCRIPTION}}", "Erfasster Flow")
            .replace("{{DATE}}", timestamp).replace("{{SESSION_ID}}", session_id or "latest")
            .replace("{{TRIGGER}}", "auto").replace("{{FLOW_DESCRIPTION}}", "Aus Audit-Log")
            .replace("{{PID}}", "$PID").replace("{{CAPTURED_COMMANDS}}", "\n".join(unique)))
    
    update_registry(skill_name, f"captured/{skill_name}/{skill_name}")
    brain_result = push_to_global_brain(skill_name, unique)
    
    print(f"✅ Skill: {skill_name} ({len(unique)} cmds, {len(seen_labels)} labels)")
    return {"status": "created", "skill": skill_name, "commands": len(unique), "labels": len(seen_labels), "global_brain": brain_result}

def update_registry(skill_name: str, cli_rel_path: str):
    try: reg = json.loads(REGISTRY_PATH.read_text())
    except: reg = {"skills": {}, "captured": []}
    reg["captured"].append({"name": skill_name, "cli": cli_rel_path, "status": "new",
                            "captured_at": datetime.now(timezone.utc).isoformat()})
    REGISTRY_PATH.write_text(json.dumps(reg, indent=2, ensure_ascii=False))

def push_to_global_brain(skill_name: str, commands: List[str]) -> Dict:
    facts_file = BRAIN_PATH / "memory" / "facts.json"
    rules_file = BRAIN_PATH / "memory" / "rules.json"
    trigger = "captured-session"
    for cmd in commands:
        if "click" in cmd and "'" in cmd:
            trigger = cmd.split("'")[1][:50]; break
    
    fact = {"id": f"fact-{skill_name}", "type": "discovery",
            "content": f"Session-Strategie: {trigger}", "quality_score": 0.9}
    rule = {"id": f"rule-{skill_name}", "type": "strategy",
            "trigger": trigger, "action": f"Execute: {skill_name}", "success_rate": 1.0}
    
    for fp, entry in [(facts_file, fact), (rules_file, rule)]:
        fp.parent.mkdir(parents=True, exist_ok=True)
        try: data = json.loads(fp.read_text())
        except: data = []
        data.append(entry)
        fp.write_text(json.dumps(data, indent=2))
    
    return {"facts_added": 1, "rules_added": 1, "trigger": trigger}

if __name__ == "__main__":
    import sys
    print(json.dumps(learn_from_session(sys.argv[1] if len(sys.argv) > 1 else None), indent=2))
