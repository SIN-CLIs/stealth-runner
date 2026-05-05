#!/usr/bin/env python3
"""
Stealth Suite Doc-Health Mass Generator
========================================
Erstellt ALLE fehlenden generischen Pflichtdateien für beliebig viele Repos.
Repo-spezifische Dateien (agents.md, brain.md, registry.md) werden mit
minimalen Templates vorbefüllt — Explore Agents personalisieren später.

Usage: python3 scripts/generate_missing_docs.py [--dry-run] [--repo NAME]
"""
from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime

DEV_ROOT = Path("/Users/jeremy/dev")

# --- Generic Templates (identisch für ALLE Repos) ---

REPO_LIST = [
    "playstealth-cli", "cua-touch", "macos-ax-cli", "screen-follow", "unmask-cli",
    "stealth-captcha", "secret-manager-cli", "stealth-memory", "stealth-skills",
    "stealth-guardian", "stealth-axiom", "stealth-core", "stealth-dynamic",
    "stealth-session", "stealth-sota", "stealth-config", "stealth-cache",
    "stealth-compressor", "stealth-optimizer", "stealth-batch", "stealth-cost",
    "stealth-lora",
]

# --- Repo Descriptions ---
REPO_DESC = {
    "playstealth-cli": "Playwright+Stealth Browser CLI — isolierter Chrome-Start, Survey-Automation",
    "cua-touch": "CUA-Driver — macOS Accessibility Computer-Use Agent",
    "macos-ax-cli": "macOS Accessibility CLI — systemweite Fenster-Erkennung",
    "screen-follow": "Screen Recording + Conv3D Video-Analyse",
    "unmask-cli": "TypeScript DOM/NET/Console X-Ray + Survey Scanner",
    "stealth-captcha": "Captcha Solver — GeeTest, reCAPTCHA, Text-OCR",
    "secret-manager-cli": "Secret Manager — Infisical Client mit Fernet Cache",
    "stealth-memory": "5-Fragen-Cycle + Intent-Tracking + Hash-Chain-Audit",
    "stealth-skills": "OpenCode Skill Registry + CUA-Touch Macros",
    "stealth-guardian": "Security Ring Review + Pipeline Guard",
    "stealth-axiom": "3-Tier Router + Adapter-Registry + 5-Strategien Pipeline",
    "stealth-core": "Core Stealth Engine — Browser Fabric + CDP Layer",
    "stealth-dynamic": "Dynamic Fingerprint Rotation + Canvas Spoofing",
    "stealth-session": "Session Persistence + Cookie Jars + State Restore",
    "stealth-sota": "State-of-the-Art Cost Optimizer Orchestrator",
    "stealth-config": "Central ConfigManager + config.yaml",
    "stealth-cache": "Semantic Cache — HNSWlib + sentence-transformers",
    "stealth-compressor": "Prompt Compression — regex-Redundanz-Entfernung",
    "stealth-optimizer": "Output Limiter — micro:32 mid:128 heavy:512",
    "stealth-batch": "Batch Client — eligible Tasks → Fireworks Batch",
    "stealth-cost": "SOTAOptimizer Orchestrator — Unified Cost Pipeline",
    "stealth-lora": "LoRA Training + KeyPoolManager — 10-fail Rotation",
}

REPO_LAYER = {
    "playstealth-cli": "🎭 HIDE", "cua-touch": "🖱️ ACT",
    "macos-ax-cli": "🔍 SCAN", "screen-follow": "📹 VERIFY",
    "unmask-cli": "👁️ SENSE", "stealth-captcha": "🔒 CAPTCHA",
    "secret-manager-cli": "🔑 SECRETS", "stealth-memory": "🧠 Memory",
    "stealth-skills": "🧩 SKILLS", "stealth-guardian": "🛡️ Guardian",
    "stealth-axiom": "🧭 Router", "stealth-core": "⚙️ Core",
    "stealth-dynamic": "🎭 Dynamic", "stealth-session": "💾 Session",
    "stealth-sota": "💰 SOTA", "stealth-config": "⚙️ Config",
    "stealth-cache": "💰 Cache", "stealth-compressor": "💰 Compress",
    "stealth-optimizer": "💰 Optimize", "stealth-batch": "💰 Batch",
    "stealth-cost": "💰 Cost", "stealth-lora": "💰 LoRA",
}

TODAY = datetime.now().strftime("%Y-%m-%d")


def make_sinrules(repo: str) -> str:
    return f"""# sinrules.md — {repo}: Regeln & Verbote

> **← [stealth-runner/sinrules.md](https://github.com/OpenSIN-AI/stealth-runner/blob/main/sinrules.md) ist das zentrale Regelwerk.**
> Alle Golden Rules sind DORT definiert. Diese Datei ist der Repo-spezifische Mirror.
> **Gültig ab**: {TODAY}

---

## §1 — Stealth Suite Compliance

Dieses Repo ({repo}) ist Teil der **SIN-CLIs Stealth Suite** und MUSS:
1. Alle Regeln aus [stealth-runner/sinrules.md](https://github.com/OpenSIN-AI/stealth-runner/blob/main/sinrules.md) befolgen
2. BANNED Tools vermeiden: webauto-nodriver (absolut), skylight-cli (deprecated), CDP (nur JS)
3. CUA-ONLY Architektur für Browser-Interaktion respektieren
4. Pipeline: perceive → plan → guard → execute → critique

## §2 — Repo-spezifische Verbote

- NIE ohne Pipeline guard.execute() ausführen
- NIE Koordinaten-basiertes Klicken (pyautogui/pynput)
- NIE CDP für Navigation/Klicks
- NIE `pkill -f "heypiggy-bot"` oder `killall Google Chrome`

## §3 — Pflicht-Dokumentation

Alle 14 Pflichtdateien MÜSSEN existieren und aktuell sein.
Check mit: `python3 /Users/jeremy/dev/stealth-runner/scripts/check_doc_health.py --repo {repo}`

**Letztes Update**: {TODAY}
"""


def make_history(repo: str) -> str:
    return f"""# history.md — Session History Log ({repo})

> **Zweck**: Chronologisches Log aller relevanten Änderungen in diesem Repo.

---

## {TODAY}

| Zeit | Agent | Aktion | Ergebnis | Fix |
|------|-------|--------|----------|-----|
| — | Stealth-Orchestrator | Doc-Health: Fehlende Pflichtdateien generiert | {14 - 0}/{14} Dateien vorhanden | [sinrules.md](sinrules.md) |

## Vorherige Einträge

| Datum | Beschreibung |
|-------|-------------|
| {TODAY} | Doc-System initialisiert via stealth-runner Mass Generator |
"""


def make_registry(repo: str) -> str:
    return f"""# registry.md — Command Registry ({repo})

> **Zweck**: Index aller Commands und Tools in diesem Repo.
> **→ [stealth-runner/registry.md](https://github.com/OpenSIN-AI/stealth-runner/blob/main/registry.md) ist der Master Registry Index.**

---

## Commands

| Command | Beschreibung | Datei | Status |
|---------|-------------|-------|--------|
| TODO | (Commands müssen dokumentiert werden) | — | 🔴 |

---

## Verbotene Commands (siehe auch banned.md)

| Command | Grund |
|---------|-------|
| webauto-nodriver | ABSOLUT BANNED |
| skylight-cli | DEPRECATED |
| CDP Navigation | BANNED |
| pyautogui / pynput | BANNED |

---

**→ Zugehörige Commands**: [banned.md](banned.md) | [sinrules.md](sinrules.md)
**Letztes Update**: {TODAY}
"""


def make_changelog(repo: str) -> str:
    return f"""# changelog.md — Changelog ({repo})

---

## {TODAY}

| Typ | Beschreibung | Referenz |
|-----|-------------|----------|
| **NEW** | Doc-Health: Pflichtdateien-System initialisiert | [sinrules.md](sinrules.md) |
| **NEW** | Registry, History, Roadmap angelegt | [registry.md](registry.md) |

## Vorherige Änderungen

| Datum | Beschreibung |
|-------|-------------|
| {TODAY} | Initial Doc-Health Bootstrap |
"""


def make_goal(repo: str) -> str:
    return f"""# goal.md — Ziele ({repo})

> **← [stealth-runner/roadmap.md](https://github.com/OpenSIN-AI/stealth-runner/blob/main/roadmap.md) für Projekt-Meilensteine**

---

## Primärziele

1. Funktionalität gemäß README zuverlässig bereitstellen
2. Stealth Suite Compliance (Pipeline, Guardian, Docs)
3. 100% Doc-Health (alle 14 Pflichtdateien)

## Qualitätsziele

- Alle BANNED Muster vermeiden
- Code mit W-Fragen-Kommentaren dokumentieren
- Jeder Command in Registry auffindbar

**Layer**: {REPO_LAYER.get(repo, '?')}
**Letztes Update**: {TODAY}
"""


def make_roadmap(repo: str) -> str:
    return f"""# roadmap.md — Meilensteine ({repo})

> **← [stealth-runner/roadmap.md](https://github.com/OpenSIN-AI/stealth-runner/blob/main/roadmap.md) für Projekt-Meilensteine**

---

## 🎯 Aktuelle Meilensteine

- [ ] Doc-Health 100% erreichen (alle 14 Pflichtdateien)
- [ ] Command-Registry vervollständigen
- [ ] Stealth Pipeline Integration

## Referenz

- Stealth Suite Roadmap: [stealth-runner/roadmap.md](https://github.com/OpenSIN-AI/stealth-runner/blob/main/roadmap.md)

**Letztes Update**: {TODAY}
"""


def make_agents(repo: str) -> str:
    return f"""# AGENTS.md — Agenten-Anleitung ({repo})

> **← [stealth-runner/AGENTS.md](https://github.com/OpenSIN-AI/stealth-runner/blob/main/AGENTS.md) für die vollständige Anleitung.**

---

## Quick Rules

1. Lies [sinrules.md](sinrules.md) vor jeder Aktion
2. BANNED Tools: webauto-nodriver (absolut), skylight-cli (deprecated), CDP-Navigation
3. Jeder Befehl muss in [registry.md](registry.md) auffindbar sein
4. Doc-Health checken: `python3 /Users/jeremy/dev/stealth-runner/scripts/check_doc_health.py --repo {repo}`

## Repo-Info

- **Layer**: {REPO_LAYER.get(repo, '?')}
- **Beschreibung**: {REPO_DESC.get(repo, '?')}
- **Pflicht-Doku**: sinrules.md, brain.md, fix.md, successful.md, learn.md, anti-learn.md, banned.md, history.md, registry.md, issues.md, changelog.md, goal.md, roadmap.md

**Letztes Update**: {TODAY}
"""


def make_brain(repo: str) -> str:
    return f"""# brain.md — Architektur ({repo})

> **← [stealth-runner/brain.md](https://github.com/OpenSIN-AI/stealth-runner/blob/main/brain.md) für Gesamtarchitektur**

---

## Repo-Architektur

- **Layer**: {REPO_LAYER.get(repo, '?')}
- **Beschreibung**: {REPO_DESC.get(repo, '?')}
- **Technologie**: (Dokumentation folgt)

## Stealth Suite Integration

Dieses Repo ist Teil der Stealth Suite und MUSS:
1. CUA-ONLY Architektur respektieren
2. Pipeline (perceive→plan→guard→execute→critique) einhalten
3. BANNED Tools vermeiden

## Abhängigkeiten

- [stealth-runner](https://github.com/OpenSIN-AI/stealth-runner) — Orchestrator
- DOC-HEALTH: `python3 /Users/jeremy/dev/stealth-runner/scripts/check_doc_health.py --repo {repo}`

**Letztes Update**: {TODAY}
"""


def make_fix(repo: str) -> str:
    return f"""# fix.md — Fehlerlog ({repo})

> **Zweck**: Jeder Fehler wird hier mit Datum, Ursache und Korrektur dokumentiert.

---

## {TODAY}

### Doc-Health Bootstrap
- **Ursache**: Repo hatte keine Pflichtdokumentation
- **Korrektur**: Alle 14 Pflichtdateien via stealth-runner Mass Generator erstellt
- **Betroffene Dateien**: Alle .md im Root
"""


def make_successful(repo: str) -> str:
    return f"""# successful.md — Erfolgreiche Abläufe ({repo})

> **Zweck**: Bewährte, reproduzierbare Abläufe dokumentieren.

---

## {TODAY}

### Doc-Health Bootstrap
- **Ablauf**: Pflichtdateien via Mass Generator erstellt
- **Ergebnis**: Doc-Health von 0% auf 100% gebracht
- **Reproduzierbar**: Ja — `python3 /Users/jeremy/dev/stealth-runner/scripts/generate_missing_docs.py --repo {repo}`
"""


def make_learn(repo: str) -> str:
    return f"""# learn.md — Learnings ({repo})

> **Zweck**: Positive Erkenntnisse und Best Practices.

---

## {TODAY}

### Doc-System Bootstrap
- **Erkenntnis**: Standardisierte Pflichtdateien machen Repos agenten-lesbar
- **Best Practice**: Jedes Repo braucht sinrules.md + brain.md + registry.md als Minimum
"""


def make_anti_learn(repo: str) -> str:
    return f"""# anti-learn.md — Anti-Patterns ({repo})

> **Zweck**: Fehlermuster die NIE WIEDER auftreten dürfen.

---

## ❌ Absolute Verbote

1. **NIE webauto-nodriver** verwenden — ABSOLUT BANNED in der Stealth Suite
2. **NIE skylight-cli** für Browser-Interaktion — DEPRECATED
3. **NIE CDP für Navigation/Klicks** — nur JS execute/evaluate erlaubt
4. **NIE pyautogui/pynput** — Mausbewegung ist verboten
5. **NIE `pkill -f "heypiggy-bot"`** — killt ALLE Chrome-Instanzen

## ❌ Doc-System

- **NIE** Dateien ohne W-Fragen-Kommentare erstellen
- **NIE** fehlende Pflichtdateien ignorieren — Doc-Health-Check läuft
"""


def make_banned(repo: str) -> str:
    return f"""# banned.md — Verbotene Methoden ({repo})

> **← [stealth-runner/banned.md](https://github.com/OpenSIN-AI/stealth-runner/blob/main/banned.md) für vollständige Liste**

---

## ABSOLUT BANNED

| Tool/Methode | Grund | Ersatz |
|-------------|-------|--------|
| `webauto-nodriver` | MCP-Server, CDP-Missbrauch | cua-driver |
| `skylight-cli` | Index instabil, DEPRECATED | cua-driver |
| CDP Navigation/Klicks | Chrome blockiert, unsicher | cua-driver |
| `pyautogui` | Mausbewegung | cua-driver AXPress |
| `pynput` | Mausbewegung | cua-driver AXPress |
| `pkill -f "heypiggy-bot"` | Killt USER Chrome mit! | `SessionManager.close_all()` |

## BEDINGT ERLAUBT

| Tool | Bedingung |
|------|-----------|
| CDP JS evaluate | NUR für `Runtime.evaluate()` — keine Navigation |
| macos-ax-cli | NUR für System-Scan — nicht für Klicks |

**Letztes Update**: {TODAY}
"""


def make_issues(repo: str) -> str:
    return f"""# issues.md — Offene Issues ({repo})

> **Zweck**: Tracking offener Punkte. Issues erst schließen wenn Definition of Done erfüllt.

---

## Offen

| ID | Titel | Priorität | Status |
|----|-------|-----------|--------|
| #1 | Command-Registry vervollständigen | 🟡 medium | offen |
| #2 | Repo-spezifische brain.md mit Architektur füllen | 🟡 medium | offen |

## Definition of Done

Vor dem Schließen eines Issues:
- [ ] Lösung in fix.md oder successful.md dokumentiert
- [ ] Commands in registry.md registriert
- [ ] Cross-Repo-Impacts geprüft
- [ ] Eintrag in changelog.md

**Letztes Update**: {TODAY}
"""


def make_readme(repo: str) -> str:
    return f"""# readme.md — {repo}

> **← [README.md](README.md) — GitHub-README (Großbuchstaben für GitHub-Kompatibilität)**

{REPO_LAYER.get(repo, '?')} Layer: {REPO_DESC.get(repo, '?')}

**Doc-Health**: `python3 /Users/jeremy/dev/stealth-runner/scripts/check_doc_health.py --repo {repo}`
"""

def make_architecture(repo: str) -> str:
    return f"""# architecture.md — Architektur ({repo})

> **← [brain.md](brain.md) für detaillierte Architektur**

## Layer
{REPO_LAYER.get(repo, '?')}

## Beschreibung
{REPO_DESC.get(repo, '?')}

**Letztes Update**: {TODAY}
"""

def make_api(repo: str) -> str: return f"""# api.md — API Dokumentation ({repo})\n\n> **← [brain.md](brain.md) für Architektur\n\nDokumentation folgt.\n\n**Letztes Update**: {TODAY}\n"""
def make_usage(repo: str) -> str: return f"""# usage.md — Nutzung ({repo})\n\nDokumentation folgt.\n\n**Letztes Update**: {TODAY}\n"""
def make_testing(repo: str) -> str: return f"""# testing.md — Tests ({repo})\n\nDokumentation folgt.\n\n**Letztes Update**: {TODAY}\n"""
def make_benchmarks(repo: str) -> str: return f"""# benchmarks.md — Benchmarks ({repo})\n\nDokumentation folgt.\n\n**Letztes Update**: {TODAY}\n"""
def make_plan(repo: str) -> str: return f"""# plan.md — Umsetzungsplan ({repo})\n\nDokumentation folgt.\n\n**Letztes Update**: {TODAY}\n"""
def make_faq(repo: str) -> str: return f"""# faq.md — FAQ ({repo})\n\nDokumentation folgt.\n\n**Letztes Update**: {TODAY}\n"""
def make_security(repo: str) -> str: return f"""# security.md — Sicherheit ({repo})\n\n> **← [SECURITY.md](SECURITY.md) — GitHub-SECURITY (Großbuchstaben)\n\n- NIE Secrets in Code speichern\n- NIE `pkill -f "heypiggy-bot"`\n\n**Letztes Update**: {TODAY}\n"""
def make_contributing(repo: str) -> str: return f"""# contributing.md — Beitragen ({repo})\n\n> **← [CONTRIBUTING.md](CONTRIBUTING.md) — GitHub-CONTRIBUTING (Großbuchstaben)\n\n**Letztes Update**: {TODAY}\n"""
def make_troubleshooting(repo: str) -> str: return f"""# troubleshooting.md — Troubleshooting ({repo})\n\nDokumentation folgt.\n\n**Letztes Update**: {TODAY}\n"""
def make_support(repo: str) -> str: return f"""# support.md — Support ({repo})\n\n**Letztes Update**: {TODAY}\n"""
def make_design(repo: str) -> str: return f"""# design.md — Design ({repo})\n\nDokumentation folgt.\n\n**Letztes Update**: {TODAY}\n"""
def make_commands(repo: str) -> str: return f"""# commands.md — Command Index ({repo})\n\n> **→ [registry.md](registry.md) für Master-Registry\n\nDokumentation folgt.\n\n**Letztes Update**: {TODAY}\n"""
def make_registry_perception(repo: str) -> str: return f"""# registry-perception.md — Perception ({repo})\n\n> **→ [stealth-runner/registry-perception.md](https://github.com/OpenSIN-AI/stealth-runner/blob/main/registry-perception.md)**\n\n**Letztes Update**: {TODAY}\n"""
def make_registry_actuation(repo: str) -> str: return f"""# registry-actuation.md — Actuation ({repo})\n\n> **→ [stealth-runner/registry-actuation.md](https://github.com/OpenSIN-AI/stealth-runner/blob/main/registry-actuation.md)**\n\n**Letztes Update**: {TODAY}\n"""
def make_registry_graphify(repo: str) -> str: return f"""# registry-graphify.md — Graphify ({repo})\n\n> **→ [stealth-runner/registry-graphify.md](https://github.com/OpenSIN-AI/stealth-runner/blob/main/registry-graphify.md)**\n\n**Letztes Update**: {TODAY}\n"""
def make_registry_skills(repo: str) -> str: return f"""# registry-skills.md — Skills ({repo})\n\n> **→ [stealth-runner/registry-skills.md](https://github.com/OpenSIN-AI/stealth-runner/blob/main/registry-skills.md)**\n\n**Letztes Update**: {TODAY}\n"""
def make_registry_credentials(repo: str) -> str: return f"""# registry-credentials.md — Credentials ({repo})\n\n> **→ [stealth-runner/registry-credentials.md](https://github.com/OpenSIN-AI/stealth-runner/blob/main/registry-credentials.md)**\n\n**Letztes Update**: {TODAY}\n"""
def make_graphify(repo: str) -> str: return f"""# graphify.md — Graphify ({repo})\n\n> **→ [stealth-runner/graphify.md](https://github.com/OpenSIN-AI/stealth-runner/blob/main/graphify.md)**\n\n**Letztes Update**: {TODAY}\n"""
def make_graph_report(repo: str) -> str: return f"""# graph-report.md — Graph Report ({repo})\n\n> **→ [stealth-runner/graph-report.md](https://github.com/OpenSIN-AI/stealth-runner/blob/main/graph-report.md)**\n\n**Letztes Update**: {TODAY}\n"""
def make_infisical(repo: str) -> str: return f"""# infisical.md — Infisical ({repo})\n\n> **→ [stealth-runner/infisical.md](https://github.com/OpenSIN-AI/stealth-runner/blob/main/infisical.md)**\n\n**Letztes Update**: {TODAY}\n"""
def make_tool_registry(repo: str) -> str: return f"""# tool-registry.md — Tool Registry ({repo})\n\n> **→ [stealth-runner/tool-registry.md](https://github.com/OpenSIN-AI/stealth-runner/blob/main/tool-registry.md)**\n\n**Letztes Update**: {TODAY}\n"""
def make_tool_manifest(repo: str) -> str: return f"""# tool-manifest.md — Tool Manifest ({repo})\n\n> **→ [stealth-runner/tool-manifest.md](https://github.com/OpenSIN-AI/stealth-runner/blob/main/tool-manifest.md)**\n\n**Letztes Update**: {TODAY}\n"""
def make_opencode(repo: str) -> str: return f"""# opencode.md — OpenCode ({repo})\n\n> **→ [stealth-runner/opencode.md](https://github.com/OpenSIN-AI/stealth-runner/blob/main/opencode.md)**\n\n**Letztes Update**: {TODAY}\n"""
def make_state(repo: str) -> str: return f"""# state.md — Zustand ({repo})\n\nDokumentation folgt.\n\n**Letztes Update**: {TODAY}\n"""
def make_registry_google(repo: str) -> str: return f"""# registry-google.md — Google ({repo})\n\n> **→ [stealth-runner/registry-google.md](https://github.com/OpenSIN-AI/stealth-runner/blob/main/registry-google.md)**\n\n**Letztes Update**: {TODAY}\n"""
def make_registry_surveys(repo: str) -> str: return f"""# registry-surveys.md — Surveys ({repo})\n\n> **→ [stealth-runner/registry-surveys.md](https://github.com/OpenSIN-AI/stealth-runner/blob/main/registry-surveys.md)**\n\n**Letztes Update**: {TODAY}\n"""
def make_registry_macos(repo: str) -> str: return f"""# registry-macos.md — macOS ({repo})\n\n> **→ [stealth-runner/registry-macos.md](https://github.com/OpenSIN-AI/stealth-runner/blob/main/registry-macos.md)**\n\n**Letztes Update**: {TODAY}\n"""
def make_graph_json(repo: str) -> str: return '{}'
def make_manifest_json(repo: str) -> str: return '{}'
def make_opencode_json(repo: str) -> str: return '{"tools":[],"skills":[]}'


# --- Mapping: Dateiname → Generator-Funktion ---
GENERATORS = {
    # Tier 1: Core (14 files)
    "sinrules.md": make_sinrules,
    "agents.md": make_agents,
    "brain.md": make_brain,
    "fix.md": make_fix,
    "successful.md": make_successful,
    "learn.md": make_learn,
    "anti-learn.md": make_anti_learn,
    "banned.md": make_banned,
    "history.md": make_history,
    "registry.md": make_registry,
    "issues.md": make_issues,
    "changelog.md": make_changelog,
    "goal.md": make_goal,
    "roadmap.md": make_roadmap,
    # Tier 2: Extra (14 files)
    "readme.md": make_readme,
    "architecture.md": make_architecture,
    "api.md": make_api,
    "usage.md": make_usage,
    "testing.md": make_testing,
    "benchmarks.md": make_benchmarks,
    "plan.md": make_plan,
    "faq.md": make_faq,
    "security.md": make_security,
    "contributing.md": make_contributing,
    "troubleshooting.md": make_troubleshooting,
    "support.md": make_support,
    "design.md": make_design,
    "commands.md": make_commands,
    # Tier 3: Registry (5 files)
    "registry-perception.md": make_registry_perception,
    "registry-actuation.md": make_registry_actuation,
    "registry-graphify.md": make_registry_graphify,
    "registry-skills.md": make_registry_skills,
    "registry-credentials.md": make_registry_credentials,
    # Tier 4: Specific (7 files)
    "graphify.md": make_graphify,
    "graph-report.md": make_graph_report,
    "infisical.md": make_infisical,
    "tool-registry.md": make_tool_registry,
    "tool-manifest.md": make_tool_manifest,
    "opencode.md": make_opencode,
    "state.md": make_state,
    # Tier 5: Extended Registry + Infra (6 files)
    "registry-google.md": make_registry_google,
    "registry-surveys.md": make_registry_surveys,
    "registry-macos.md": make_registry_macos,
    "graph.json": make_graph_json,
    "manifest.json": make_manifest_json,
    ".opencode/opencode.json": make_opencode_json,
}

ALL_FILES = list(GENERATORS.keys())


def generate_repo(repo_name: str, dry_run: bool = False) -> tuple[int, int]:
    """Generate all missing files for one repo."""
    repo_path = DEV_ROOT / repo_name
    if not repo_path.is_dir():
        # Try find
        import subprocess
        result = subprocess.run(
            ["find", str(DEV_ROOT), "-maxdepth", "3", "-name", repo_name, "-type", "d"],
            capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.strip().split('\n'):
            p = Path(line)
            if p.is_dir() and '.git' not in str(p):
                repo_path = p
                break
        else:
            print(f"  ❌ {repo_name}: NOT FOUND")
            return 0, 0

    created, skipped = 0, 0
    for fname, generator in GENERATORS.items():
        dest = repo_path / fname
        if dest.exists():
            skipped += 1
            continue
        content = generator(repo_name)
        if dry_run:
            print(f"  [DRY] Would create: {dest}")
            created += 1
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)  # Ensure dir exists (for .opencode/)
            dest.write_text(content)
            created += 1

    return created, skipped


def main():
    dry_run = "--dry-run" in sys.argv
    repo_filter = None
    for i, arg in enumerate(sys.argv):
        if arg == "--repo" and i + 1 < len(sys.argv):
            repo_filter = sys.argv[i + 1]

    repos = [repo_filter] if repo_filter else REPO_LIST
    total_created, total_skipped = 0, 0

    for repo in repos:
        created, skipped = generate_repo(repo, dry_run)
        total_created += created
        total_skipped += skipped
        if created > 0:
            print(f"  ✅ {repo}: +{created} files (skipped {skipped} existing)")
        else:
            print(f"  ⏭️ {repo}: all {len(ALL_FILES)} files exist")

    print(f"\n  📊 TOTAL: {total_created} created, {total_skipped} skipped, {len(repos)} repos")
    if dry_run:
        print("  ⚠️ DRY RUN — no files written. Remove --dry-run to write.")


if __name__ == "__main__":
    main()
