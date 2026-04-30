"""Strategy Evolution Module — wählt optimale Skill-Sequenz aus Brain-Daten."""
import json
from pathlib import Path
from typing import Dict, List

BRAIN_PATH = Path("../Infra-SIN-Global-Brain/brain/projects/heypiggy-survey")
REGISTRY_PATH = Path("stealth-skills/_registry.json")

def select_best_strategy(router: str, profile_id: str = "jeremy") -> Dict:
    try: registry = json.loads(REGISTRY_PATH.read_text())
    except: return {"error": "registry_unavailable"}
    
    rules = load_brain_rules(router)
    if not rules:
        return {"router": router, "selected_skills": ["heypiggy-survey"], 
                "expected_success_rate": 0.5, "reason": "no_brain_data_yet"}
    
    scored = []
    for rule in rules:
        score = rule.get("success_rate", 0.5)
        avg_time = rule.get("avg_time_seconds", 30)
        efficiency = score / (avg_time + 1)
        scored.append({"skill_id": rule.get("action", "").replace("Execute: ","").replace("Execute skill: ",""),
                       "success_rate": score, "efficiency": efficiency})
    
    scored.sort(key=lambda x: x["efficiency"], reverse=True)
    selected = scored[:5]
    expected = sum(s["success_rate"] for s in selected) / len(selected) if selected else 0.5
    
    return {"router": router, "selected_skills": [s["skill_id"] for s in selected],
            "expected_success_rate": round(expected, 2), "skill_details": selected,
            "total_rules_analyzed": len(rules)}

def load_brain_rules(router: str) -> List[Dict]:
    rules_file = BRAIN_PATH / "memory" / "rules.json"
    try: rules = json.loads(rules_file.read_text())
    except: return []
    return [r for r in rules if router.lower() in r.get("trigger","").lower() or router.lower() in str(r).lower()]

if __name__ == "__main__":
    import sys
    router = sys.argv[1] if len(sys.argv) > 1 else "toluna"
    print(json.dumps(select_best_strategy(router), indent=2))
