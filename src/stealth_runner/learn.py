"""Skill Capture Loop — extrahiert aus Sessions atomare CLIs."""
import json, os, subprocess
from datetime import datetime, timezone
from pathlib import Path

SKILLS_DIR = Path("stealth-skills")
CAPTURED_DIR = SKILLS_DIR / "captured"
TEMPLATES_DIR = SKILLS_DIR / "_templates"
REGISTRY_PATH = SKILLS_DIR / "_registry.json"

def learn_from_session(session_id: str = None) -> dict:
    print("🧠 Skill Capture Loop gestartet...")
    
    # Audit-Log lesen
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
                x, y = event.get("x", 0), event.get("y", 0)
                if y > 30:  # Kein Apple-Menü
                    commands.append(f"# Klick auf '{label}' bei ({x:.0f}, {y:.0f})")
                    commands.append(f"skylight-cli click --pid $PID --label '{label}'")
        except: pass
    
    if not commands:
        return {"status": "no_commands"}
    
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    skill_name = f"captured-{timestamp}"
    
    # CLI bauen
    cli_template = (TEMPLATES_DIR / "cli-template.sh").read_text()
    filled = cli_template.replace("{{SKILL_NAME}}", skill_name)\
        .replace("{{SHORT_DESCRIPTION}}", f"Erfasst am {timestamp}")\
        .replace("{{DATE}}", timestamp)\
        .replace("{{SESSION_ID}}", session_id or "latest")\
        .replace("{{CAPTURED_COMMANDS}}", "\n".join(commands[-10:]))
    
    cli_dir = CAPTURED_DIR / skill_name
    cli_dir.mkdir(parents=True, exist_ok=True)
    (cli_dir / skill_name).write_text(filled)
    (cli_dir / skill_name).chmod(0o755)
    
    # SKILL.md
    skill_tpl = (TEMPLATES_DIR / "SKILL-template.md").read_text()
    (cli_dir / "SKILL.md").write_text(
        skill_tpl.replace("{{SKILL_NAME}}", skill_name)
        .replace("{{SHORT_DESCRIPTION}}", "Erfasster Flow")
        .replace("{{DATE}}", timestamp)
        .replace("{{SESSION_ID}}", session_id or "latest")
        .replace("{{TRIGGER}}", "automatisch")
        .replace("{{FLOW_DESCRIPTION}}", "Aus Audit-Log extrahiert")
        .replace("{{PID}}", "$PID")
    )
    
    # States + Recovery
    for t in ("states-template.md", "recovery-template.md"):
        tpl_text = (TEMPLATES_DIR / t).read_text()
        (cli_dir / t.replace("-template.md", ".md")).write_text(tpl_text)
    
    # Registry updaten
    try: reg = json.loads(REGISTRY_PATH.read_text())
    except: reg = {"skills": {}, "captured": []}
    reg["captured"].append({"name": skill_name, "cli": f"captured/{skill_name}/{skill_name}", "status": "new"})
    REGISTRY_PATH.write_text(json.dumps(reg, indent=2, ensure_ascii=False))
    
    print(f"✅ Neuer Skill: {skill_name} ({len(commands)} commands)")
    return {"status": "created", "skill": skill_name, "commands": len(commands)}

if __name__ == "__main__":
    import sys
    sid = sys.argv[1] if len(sys.argv) > 1 else None
    print(json.dumps(learn_from_session(sid), indent=2))
