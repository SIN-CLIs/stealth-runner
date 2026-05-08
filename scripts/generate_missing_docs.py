#!/usr/bin/env python3
"""================================================================================
DOC-HEALTH MASS GENERATOR — Erstellt fehlende Pflichtdateien für alle Repos
================================================================================

WAS IST DAS?
  Automatischer Generator für fehlende Dokumentations-Pflichtdateien
  in allen Stealth-Suite Repos. Erstellt Templates für:
  - README.md
  - AGENTS.md
  - brain.md
  - sinrules.md
  - banned.md
  - Und 15+ weitere generische Dateien

ARCHITEKTUR:
  ┌─────────────────────┐
  │  main()             │
  └─────────────────────┘
         │
    ┌────┴──────────────────────────────┐
    ▼                                     ▼
  scan_repos()                        generate_docs()
  (23 Repos scannen)                   (Templates)
         │                                     │
         ▼                                     ▼
  Fehlende Dateien                    Template auswählen
  identifizieren                      → Generisch oder Repo-spezifisch
                                              │
                                              ▼
                                        Datei schreiben

WARUM Automatisierung?
  23+ Repos manuell pflegen = unmöglich.
  → Automatischer Generator garantiert:
  - Alle Repos haben minimale Doku
  - Einheitliche Struktur
  - Kein Repo ohne AGENTS.md (wichtig für Agent-Anweisungen!)

WARUM Templates?
  Generische Templates = sofort nutzbar.
  Repo-spezifische Anpassungen = später durch Explore Agents.
  → 80/20 Regel: 80% generisch, 20% personalisiert.

WARUM 23 Repos?
  Stealth-Suite ist modular:
  - playstealth-cli (Chrome Launcher)
  - cua-touch (CUA Interaktionen)
  - macos-ax-cli (macOS Accessibility)
  - screen-follow (Screen Following)
  - unmask-cli (Unmasking)
  - stealth-captcha (Captcha Solving)
  - secret-manager-cli (Secrets)
  - stealth-memory (Memory)
  - stealth-skills (Skills)
  - stealth-guardian (Guardian)
  - stealth-axiom (Axiom)
  - stealth-core (Core)
  - stealth-dynamic (Dynamic)
  - stealth-session (Session)
  - stealth-sota (SOTA)
  - stealth-config (Config)
  - stealth-cache (Cache)
  - stealth-compressor (Compressor)
  - stealth-optimizer (Optimizer)
  - stealth-batch (Batch)
  - stealth-cost (Cost)
  - stealth-lora (LoRA)
  - stealth-runner (Hauptrepo — dieses hier!)

DEPENDENZEN:
  - Standardlib: pathlib, datetime, sys
  - Keine externen Dependencies!

BANNED METHODS — NIEMALS VERWENDEN (siehe /banned.md):
  ❌ playstealth launch
  ❌ webauto-nodriver — ABSOLUT BANNED
  ❌ cua-driver click (raw index)
  ❌ --remote-allow-origins=* (ohne Quotes)
  ❌ /tmp/heypiggy-bot (fixed profile)
  ❌ Hardcoded PIDs
  ❌ pkill -f "Google Chrome"
  ❌ killall Google Chrome
  ❌ skylight-cli click --element-index
================================================================================"""
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
    """
    ================================================================================
    Generiert sinrules.md — Repo-spezifisches Regelwerk mit Golden Rules, BANNED
    Methoden und Stealth Suite Compliance Anforderungen.

    WARUM existiert diese Funktion?
      Jedes Repo MUSS ein sinrules.md haben das auf das zentrale Regelwerk verweist.
      Verhindert dass Agents verbotene Tools nutzen oder gegen Architektur-Regeln verstoßen.

    Args:
      repo: Repository Name (z.B. "stealth-core", "playstealth-cli")

    Returns:
      str: Markdown-Inhalt für sinrules.md mit §1-§3 Regeln.

    Side Effects:
      - Keine (pure function, gibt nur String zurück)
    ================================================================================
    """
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
    """
    ================================================================================
    Generiert history.md — Chronologisches Session History Log für ein Repo.

    WARUM existiert diese Funktion?
      Jede Änderung MUSS dokumentiert werden. History dient als Audit-Trail für
      Agent-Aktionen, Doc-Health Bootstrap und Repo-spezifische Events.

    Args:
      repo: Repository Name

    Returns:
      str: Markdown-Inhalt für history.md mit initialisiertem Log-Table.

    Side Effects:
      - Keine (pure function)
    ================================================================================
    """
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
    """
    ================================================================================
    Generiert registry.md — Command Registry Index für ein Repo.

    WARUM existiert diese Funktion?
      Jeder Command MUSS in der Registry auffindbar sein. Verhindert "vergessene"
      Tools die Agents nicht kennen. Verweist auf Master Registry in stealth-runner.

    Args:
      repo: Repository Name

    Returns:
      str: Markdown-Inhalt für registry.md mit Command-Table und BANNED-Liste.

    Side Effects:
      - Keine (pure function)
    ================================================================================
    """
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
    """
    ================================================================================
    Generiert changelog.md — Versions-Changelog für ein Repo.

    WARUM existiert diese Funktion?
      Jede Änderung MUSS im Changelog dokumentiert sein. Dient als History für
      Doc-Health Bootstrap und zukünftige Repo-Änderungen.

    Args:
      repo: Repository Name

    Returns:
      str: Markdown-Inhalt für changelog.md mit initialisiertem Änderungs-Log.

    Side Effects:
      - Keine (pure function)
    ================================================================================
    """
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
    """
    ================================================================================
    Generiert goal.md — Repo-spezifische Ziele und Qualitätsanforderungen.

    WARUM existiert diese Funktion?
      Jedes Repo MUSS definierte Ziele haben. Verhindert zielloses Entwickeln und
      stellt sicher dass Agents wissen was "fertig" bedeutet.

    Args:
      repo: Repository Name

    Returns:
      str: Markdown-Inhalt für goal.md mit Primär-/Qualitätszielen.

    Side Effects:
      - Keine (pure function)
    ================================================================================
    """
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
    """
    ================================================================================
    Generiert roadmap.md — Meilensteine und zukünftige Planung für ein Repo.

    WARUM existiert diese Funktion?
      Agents MUSS wissen welche Features geplant sind. Verhindert dass an falschen
      Stellen entwickelt wird. Verweist auf Haupt-Roadmap in stealth-runner.

    Args:
      repo: Repository Name

    Returns:
      str: Markdown-Inhalt für roadmap.md mit Checkbox-Meilensteinen.

    Side Effects:
      - Keine (pure function)
    ================================================================================
    """
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
    """
    ================================================================================
    Generiert AGENTS.md — Agenten-Anleitung mit Quick Rules für ein Repo.

    WARUM existiert diese Funktion?
      Jedes Repo MUSS eine AGENTS.md haben die Agents vor der Arbeit lesen.
      Enthält BANNED-Tools, Doc-Health-Check Commands und Repo-Info.

    Args:
      repo: Repository Name

    Returns:
      str: Markdown-Inhalt für AGENTS.md mit Quick Rules und Layer-Info.

    Side Effects:
      - Keine (pure function)
    ================================================================================
    """
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
    """
    ================================================================================
    Generiert brain.md — Repo-spezifische Architektur und Integration.

    WARUM existiert diese Funktion?
      Agents MUSS die Architektur verstehen bevor sie Code ändern. Verhindert
      falsche Refactorings die die Stealth Suite Integration brechen.

    Args:
      repo: Repository Name

    Returns:
      str: Markdown-Inhalt für brain.md mit Layer, Dependencies und Integration.

    Side Effects:
      - Keine (pure function)
    ================================================================================
    """
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
    """
    ================================================================================
    Generiert fix.md — Fehlerlog mit Datum, Ursache und Korrektur.

    WARUM existiert diese Funktion?
      Jeder Fehler MUSS dokumentiert werden. Verhindert dass gleiche Bugs immer
      wieder auftreten. Dient als Lern-Resource für zukünftige Agents.

    Args:
      repo: Repository Name

    Returns:
      str: Markdown-Inhalt für fix.md mit initialisiertem Bootstrap-Eintrag.

    Side Effects:
      - Keine (pure function)
    ================================================================================
    """
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
    """
    ================================================================================
    Generiert successful.md — Bewährte, reproduzierbare Abläufe.

    WARUM existiert diese Funktion?
      Erfolgreiche Flows MÜSSEN dokumentiert werden. Agents können dann bewährte
      Patterns nutzen statt jedes Mal neu zu erfinden.

    Args:
      repo: Repository Name

    Returns:
      str: Markdown-Inhalt für successful.md mit Bootstrap-Eintrag.

    Side Effects:
      - Keine (pure function)
    ================================================================================
    """
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
    """
    ================================================================================
    Generiert learn.md — Positive Erkenntnisse und Best Practices.

    WARUM existiert diese Funktion?
      Learnings MÜSSEN geteilt werden. Verhindert dass Agents gleiche Erkenntnisse
      immer wieder neu gewinnen. Dient als Wissensbasis.

    Args:
      repo: Repository Name

    Returns:
      str: Markdown-Inhalt für learn.md mit initialisierten Best Practices.

    Side Effects:
      - Keine (pure function)
    ================================================================================
    """
    return f"""# learn.md — Learnings ({repo})

> **Zweck**: Positive Erkenntnisse und Best Practices.

---

## {TODAY}

### Doc-System Bootstrap
- **Erkenntnis**: Standardisierte Pflichtdateien machen Repos agenten-lesbar
- **Best Practice**: Jedes Repo braucht sinrules.md + brain.md + registry.md als Minimum
"""


def make_anti_learn(repo: str) -> str:
    """
    ================================================================================
    Generiert anti-learn.md — Anti-Patterns die NIE WIEDER auftreten dürfen.

    WARUM existiert diese Funktion?
      Fehlermuster MÜSSEN dokumentiert werden. Verhindert dass Agents gleiche
      Fehler immer wieder machen. Enthält absolute Verbote.

    Args:
      repo: Repository Name

    Returns:
      str: Markdown-Inhalt für anti-learn.md mit BANNED-Liste.

    Side Effects:
      - Keine (pure function)
    ================================================================================
    """
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
    """
    ================================================================================
    Generiert banned.md — Vollständige Liste verbotener Methoden/Tools.

    WARUM existiert diese Funktion?
      BANNED-Tools MÜSSEN explizit dokumentiert sein. Verhindert dass Agents
      veraltete oder gefährliche Tools nutzen. Verweist auf stealth-runner Master.

    Args:
      repo: Repository Name

    Returns:
      str: Markdown-Inhalt für banned.md mit Tabelle (Tool/Grund/Ersatz).

    Side Effects:
      - Keine (pure function)
    ================================================================================
    """
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
    """
    ================================================================================
    Generiert issues.md — Tracking offener Punkte mit Definition of Done.

    WARUM existiert diese Funktion?
      Issues MÜSSEN dokumentiert werden. Verhindert vergessene Bugs/Features.
      Enthält DoD-Checkliste vor dem Schließen.

    Args:
      repo: Repository Name

    Returns:
      str: Markdown-Inhalt für issues.md mit Issue-Table und DoD.

    Side Effects:
      - Keine (pure function)
    ================================================================================
    """
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
    """
    ================================================================================
    Generiert readme.md — Repo-spezifische README mit Doc-Health-Check.

    WARUM existiert diese Funktion?
      GitHub-kompatibles README (Kleinbuchstaben) mit Link zu Haupt-README.
      Zeigt Layer, Beschreibung und Doc-Health Command.

    Args:
      repo: Repository Name

    Returns:
      str: Markdown-Inhalt für readme.md.

    Side Effects:
      - Keine (pure function)
    ================================================================================
    """
    return f"""# readme.md — {repo}

> **← [README.md](README.md) — GitHub-README (Großbuchstaben für GitHub-Kompatibilität)**

{REPO_LAYER.get(repo, '?')} Layer: {REPO_DESC.get(repo, '?')}

**Doc-Health**: `python3 /Users/jeremy/dev/stealth-runner/scripts/check_doc_health.py --repo {repo}`
"""

def make_architecture(repo: str) -> str:
    """
    ================================================================================
    Generiert architecture.md — Repo-spezifische Architekturdokumentation.

    WARUM existiert diese Funktion?
      Separate Architektur-Datei für schnelle Übersicht. Verweist auf brain.md
      für Details. Enthält Layer und Beschreibung.

    Args:
      repo: Repository Name

    Returns:
      str: Markdown-Inhalt für architecture.md.

    Side Effects:
      - Keine (pure function)
    ================================================================================
    """
    return f"""# architecture.md — Architektur ({repo})

> **← [brain.md](brain.md) für detaillierte Architektur**

## Layer
{REPO_LAYER.get(repo, '?')}

## Beschreibung
{REPO_DESC.get(repo, '?')}

**Letztes Update**: {TODAY}
"""

def make_api(repo: str) -> str:
    """
    ================================================================================
    Generiert api.md — API Dokumentation für ein Repo.

    WARUM existiert diese Funktion?
      API-Endpunkte MÜSSEN dokumentiert sein. Verweist auf brain.md für Architektur.

    Args:
      repo: Repository Name

    Returns:
      str: Markdown-Inhalt für api.md (Stub).

    Side Effects:
      - Keine (pure function)
    ================================================================================
    """
    return f"""# api.md — API Dokumentation ({repo})\n\n> **← [brain.md](brain.md) für Architektur\n\nDokumentation folgt.\n\n**Letztes Update**: {TODAY}\n"""
def make_usage(repo: str) -> str:
    """
    ================================================================================
    Generiert usage.md — Anwendungsbeispiele und Nutzungshinweise.

    WARUM existiert diese Funktion?
      Usage-Dokumentation als Pflichtdatei für Agent-Navigation.

    Args:
      repo: Repository Name

    Returns:
      str: Markdown-Inhalt für usage.md (Stub).

    Side Effects:
      - Keine (pure function)
    ================================================================================
    """
    return f"""# usage.md — Nutzung ({repo})\n\nDokumentation folgt.\n\n**Letztes Update**: {TODAY}\n"""
def make_testing(repo: str) -> str:
    """
    ================================================================================
    Generiert testing.md — Teststrategie und Testbefehle.

    WARUM existiert diese Funktion?
      Testing-Dokumentation als Pflichtdatei. Agents müssen Tests vor Commits laufen.

    Args:
      repo: Repository Name

    Returns:
      str: Markdown-Inhalt für testing.md (Stub).

    Side Effects:
      - Keine (pure function)
    ================================================================================
    """
    return f"""# testing.md — Tests ({repo})\n\nDokumentation folgt.\n\n**Letztes Update**: {TODAY}\n"""
def make_benchmarks(repo: str) -> str:
    """
    ================================================================================
    Generiert benchmarks.md — Performance-Metriken für ein Repo.

    WARUM existiert diese Funktion?
      Benchmarks dokumentieren für Performance-Vergleiche.

    Args:
      repo: Repository Name

    Returns:
      str: Markdown-Inhalt für benchmarks.md (Stub).

    Side Effects:
      - Keine (pure function)
    ================================================================================
    """
    return f"""# benchmarks.md — Benchmarks ({repo})\n\nDokumentation folgt.\n\n**Letztes Update**: {TODAY}\n"""
def make_plan(repo: str) -> str:
    """
    ================================================================================
    Generiert plan.md — Umsetzungsplan und Implementierungsstrategie.

    WARUM existiert diese Funktion?
      Plan-Dokumentation für strukturierte Feature-Entwicklung.

    Args:
      repo: Repository Name

    Returns:
      str: Markdown-Inhalt für plan.md (Stub).

    Side Effects:
      - Keine (pure function)
    ================================================================================
    """
    return f"""# plan.md — Umsetzungsplan ({repo})\n\nDokumentation folgt.\n\n**Letztes Update**: {TODAY}\n"""
def make_faq(repo: str) -> str:
    """
    ================================================================================
    Generiert faq.md — Häufig gestellte Fragen für ein Repo.

    WARUM existiert diese Funktion?
      FAQ reduziert repetitive Fragen an Agents.

    Args:
      repo: Repository Name

    Returns:
      str: Markdown-Inhalt für faq.md (Stub).

    Side Effects:
      - Keine (pure function)
    ================================================================================
    """
    return f"""# faq.md — FAQ ({repo})\n\nDokumentation folgt.\n\n**Letztes Update**: {TODAY}\n"""
def make_security(repo: str) -> str:
    """
    ================================================================================
    Generiert security.md — Sicherheitsrichtlinien und verbotene Patterns.

    WARUM existiert diese Funktion?
      Security-Regeln als Pflichtdatei. Verhindert Secrets in Code und gefährliche
      Commands. Verweist auf GitHub SECURITY.md (Großbuchstaben).

    Args:
      repo: Repository Name

    Returns:
      str: Markdown-Inhalt für security.md mit Security-Regeln.

    Side Effects:
      - Keine (pure function)
    ================================================================================
    """
    return f"""# security.md — Sicherheit ({repo})\n\n> **← [SECURITY.md](SECURITY.md) — GitHub-SECURITY (Großbuchstaben)\n\n- NIE Secrets in Code speichern\n- NIE `pkill -f "heypiggy-bot"`\n\n**Letztes Update**: {TODAY}\n"""
def make_contributing(repo: str) -> str:
    """
    ================================================================================
    Generiert contributing.md — Richtlinien für Contributions und PRs.

    WARUM existiert diese Funktion?
      Contributing-Dokumentation für GitHub-Kompatibilität. Verweist auf
      Großbuchstaben-Version für GitHub.

    Args:
      repo: Repository Name

    Returns:
      str: Markdown-Inhalt für contributing.md (Stub).

    Side Effects:
      - Keine (pure function)
    ================================================================================
    """
    return f"""# contributing.md — Beitragen ({repo})\n\n> **← [CONTRIBUTING.md](CONTRIBUTING.md) — GitHub-CONTRIBUTING (Großbuchstaben)\n\n**Letztes Update**: {TODAY}\n"""
def make_troubleshooting(repo: str) -> str:
    """
    ================================================================================
    Generiert troubleshooting.md — Fehlerbehebungsanleitung für ein Repo.

    WARUM existiert diese Funktion?
      Troubleshooting-Doku für schnelle Problembehebung.

    Args:
      repo: Repository Name

    Returns:
      str: Markdown-Inhalt für troubleshooting.md (Stub).

    Side Effects:
      - Keine (pure function)
    ================================================================================
    """
    return f"""# troubleshooting.md — Troubleshooting ({repo})\n\nDokumentation folgt.\n\n**Letztes Update**: {TODAY}\n"""
def make_support(repo: str) -> str:
    """
    ================================================================================
    Generiert support.md — Support-Kontakt und Hilfe-Ressourcen.

    WARUM existiert diese Funktion?
      Support-Doku für Agent-Hilfe bei Problemen.

    Args:
      repo: Repository Name

    Returns:
      str: Markdown-Inhalt für support.md (Stub).

    Side Effects:
      - Keine (pure function)
    ================================================================================
    """
    return f"""# support.md — Support ({repo})\n\n**Letztes Update**: {TODAY}\n"""
def make_design(repo: str) -> str:
    """
    ================================================================================
    Generiert design.md — Design-Entscheidungen und Architektur-Rationale.

    WARUM existiert diese Funktion?
      Design-Doku erklärt WARUM bestimmte Entscheidungen getroffen wurden.

    Args:
      repo: Repository Name

    Returns:
      str: Markdown-Inhalt für design.md (Stub).

    Side Effects:
      - Keine (pure function)
    ================================================================================
    """
    return f"""# design.md — Design ({repo})\n\nDokumentation folgt.\n\n**Letztes Update**: {TODAY}\n"""
def make_commands(repo: str) -> str:
    """
    ================================================================================
    Generiert commands.md — Command Index für ein Repo.

    WARUM existiert diese Funktion?
      Alle Commands MÜSSEN indiziert sein. Verweist auf registry.md für Master-Index.

    Args:
      repo: Repository Name

    Returns:
      str: Markdown-Inhalt für commands.md (Stub).

    Side Effects:
      - Keine (pure function)
    ================================================================================
    """
    return f"""# commands.md — Command Index ({repo})\n\n> **→ [registry.md](registry.md) für Master-Registry\n\nDokumentation folgt.\n\n**Letztes Update**: {TODAY}\n"""
def make_registry_perception(repo: str) -> str:
    """
    ================================================================================
    Generiert registry-perception.md — Perception Layer Registry.

    WARUM existiert diese Funktion?
      Registry für Wahrnehmungs-Tools (Screenshot, AX-Tree, CDP). Verweist auf
      stealth-runner Master-Registry.

    Args:
      repo: Repository Name

    Returns:
      str: Markdown-Inhalt für registry-perception.md (Stub).

    Side Effects:
      - Keine (pure function)
    ================================================================================
    """
    return f"""# registry-perception.md — Perception ({repo})\n\n> **→ [stealth-runner/registry-perception.md](https://github.com/OpenSIN-AI/stealth-runner/blob/main/registry-perception.md)**\n\n**Letztes Update**: {TODAY}\n"""
def make_registry_actuation(repo: str) -> str:
    """
    ================================================================================
    Generiert registry-actuation.md — Actuation Layer Registry.

    WARUM existiert diese Funktion?
      Registry für Aktions-Tools (Click, Type, Navigate). Verweist auf
      stealth-runner Master-Registry.

    Args:
      repo: Repository Name

    Returns:
      str: Markdown-Inhalt für registry-actuation.md (Stub).

    Side Effects:
      - Keine (pure function)
    ================================================================================
    """
    return f"""# registry-actuation.md — Actuation ({repo})\n\n> **→ [stealth-runner/registry-actuation.md](https://github.com/OpenSIN-AI/stealth-runner/blob/main/registry-actuation.md)**\n\n**Letztes Update**: {TODAY}\n"""
def make_registry_graphify(repo: str) -> str:
    """
    ================================================================================
    Generiert registry-graphify.md — Graphify Layer Registry.

    WARUM existiert diese Funktion?
      Registry für Graphifizierungs-Tools. Verweist auf stealth-runner Master.

    Args:
      repo: Repository Name

    Returns:
      str: Markdown-Inhalt für registry-graphify.md (Stub).

    Side Effects:
      - Keine (pure function)
    ================================================================================
    """
    return f"""# registry-graphify.md — Graphify ({repo})\n\n> **→ [stealth-runner/registry-graphify.md](https://github.com/OpenSIN-AI/stealth-runner/blob/main/registry-graphify.md)**\n\n**Letztes Update**: {TODAY}\n"""
def make_registry_skills(repo: str) -> str:
    """
    ================================================================================
    Generiert registry-skills.md — Skills Registry.

    WARUM existiert diese Funktion?
      Registry für Agent-Skills und deren Installation. Verweist auf stealth-runner.

    Args:
      repo: Repository Name

    Returns:
      str: Markdown-Inhalt für registry-skills.md (Stub).

    Side Effects:
      - Keine (pure function)
    ================================================================================
    """
    return f"""# registry-skills.md — Skills ({repo})\n\n> **→ [stealth-runner/registry-skills.md](https://github.com/OpenSIN-AI/stealth-runner/blob/main/registry-skills.md)**\n\n**Letztes Update**: {TODAY}\n"""
def make_registry_credentials(repo: str) -> str:
    """
    ================================================================================
    Generiert registry-credentials.md — Credentials Registry.

    WARUM existiert diese Funktion?
      Registry für sichere Credential-Verwaltung. Verweist auf stealth-runner Master.

    Args:
      repo: Repository Name

    Returns:
      str: Markdown-Inhalt für registry-credentials.md (Stub).

    Side Effects:
      - Keine (pure function)
    ================================================================================
    """
    return f"""# registry-credentials.md — Credentials ({repo})\n\n> **→ [stealth-runner/registry-credentials.md](https://github.com/OpenSIN-AI/stealth-runner/blob/main/registry-credentials.md)**\n\n**Letztes Update**: {TODAY}\n"""
def make_graphify(repo: str) -> str:
    """
    ================================================================================
    Generiert graphify.md — Graphifizierungs-Dokumentation.

    WARUM existiert diese Funktion?
      Graphify-Doku für Code-Graph-Analyse. Verweist auf stealth-runner Master.

    Args:
      repo: Repository Name

    Returns:
      str: Markdown-Inhalt für graphify.md (Stub).

    Side Effects:
      - Keine (pure function)
    ================================================================================
    """
    return f"""# graphify.md — Graphify ({repo})\n\n> **→ [stealth-runner/graphify.md](https://github.com/OpenSIN-AI/stealth-runner/blob/main/graphify.md)**\n\n**Letztes Update**: {TODAY}\n"""
def make_graph_report(repo: str) -> str:
    """
    ================================================================================
    Generiert graph-report.md — Graph Report Dokumentation.

    WARUM existiert diese Funktion?
      Report-Doku für Graph-Analyse-Ergebnisse. Verweist auf stealth-runner Master.

    Args:
      repo: Repository Name

    Returns:
      str: Markdown-Inhalt für graph-report.md (Stub).

    Side Effects:
      - Keine (pure function)
    ================================================================================
    """
    return f"""# graph-report.md — Graph Report ({repo})\n\n> **→ [stealth-runner/graph-report.md](https://github.com/OpenSIN-AI/stealth-runner/blob/main/graph-report.md)**\n\n**Letztes Update**: {TODAY}\n"""
def make_infisical(repo: str) -> str:
    """
    ================================================================================
    Generiert infisical.md — Infisical Secret-Management Dokumentation.

    WARUM existiert diese Funktion?
      Infisical-Doku für sichere Secret-Verwaltung. Verweist auf stealth-runner.

    Args:
      repo: Repository Name

    Returns:
      str: Markdown-Inhalt für infisical.md (Stub).

    Side Effects:
      - Keine (pure function)
    ================================================================================
    """
    return f"""# infisical.md — Infisical ({repo})\n\n> **→ [stealth-runner/infisical.md](https://github.com/OpenSIN-AI/stealth-runner/blob/main/infisical.md)**\n\n**Letztes Update**: {TODAY}\n"""
def make_tool_registry(repo: str) -> str:
    """
    ================================================================================
    Generiert tool-registry.md — Tool Registry Dokumentation.

    WARUM existiert diese Funktion?
      Registry aller Tools im Repo. Verweist auf stealth-runner Master-Registry.

    Args:
      repo: Repository Name

    Returns:
      str: Markdown-Inhalt für tool-registry.md (Stub).

    Side Effects:
      - Keine (pure function)
    ================================================================================
    """
    return f"""# tool-registry.md — Tool Registry ({repo})\n\n> **→ [stealth-runner/tool-registry.md](https://github.com/OpenSIN-AI/stealth-runner/blob/main/tool-registry.md)**\n\n**Letztes Update**: {TODAY}\n"""
def make_tool_manifest(repo: str) -> str:
    """
    ================================================================================
    Generiert tool-manifest.md — Tool Manifest Dokumentation.

    WARUM existiert diese Funktion?
      Manifest aller Tool-Konfigurationen. Verweist auf stealth-runner Master.

    Args:
      repo: Repository Name

    Returns:
      str: Markdown-Inhalt für tool-manifest.md (Stub).

    Side Effects:
      - Keine (pure function)
    ================================================================================
    """
    return f"""# tool-manifest.md — Tool Manifest ({repo})\n\n> **→ [stealth-runner/tool-manifest.md](https://github.com/OpenSIN-AI/stealth-runner/blob/main/tool-manifest.md)**\n\n**Letztes Update**: {TODAY}\n"""
def make_opencode(repo: str) -> str:
    """
    ================================================================================
    Generiert opencode.md — OpenCode CLI Konfigurationsdokumentation.

    WARUM existiert diese Funktion?
      OpenCode-Doku für CLI-Integration. Verweist auf stealth-runner Master.

    Args:
      repo: Repository Name

    Returns:
      str: Markdown-Inhalt für opencode.md (Stub).

    Side Effects:
      - Keine (pure function)
    ================================================================================
    """
    return f"""# opencode.md — OpenCode ({repo})\n\n> **→ [stealth-runner/opencode.md](https://github.com/OpenSIN-AI/stealth-runner/blob/main/opencode.md)**\n\n**Letztes Update**: {TODAY}\n"""
def make_state(repo: str) -> str:
    """
    ================================================================================
    Generiert state.md — Repo-Zustandsdokumentation.

    WARUM existiert diese Funktion?
      State-Doku für aktuellen Entwicklungsstand. Stub für zukünftige Befüllung.

    Args:
      repo: Repository Name

    Returns:
      str: Markdown-Inhalt für state.md (Stub).

    Side Effects:
      - Keine (pure function)
    ================================================================================
    """
    return f"""# state.md — Zustand ({repo})\n\nDokumentation folgt.\n\n**Letztes Update**: {TODAY}\n"""
def make_registry_google(repo: str) -> str:
    """
    ================================================================================
    Generiert registry-google.md — Google Login/OAuth Registry.

    WARUM existiert diese Funktion?
      Registry für Google-Integration (Login, OAuth). Verweist auf stealth-runner.

    Args:
      repo: Repository Name

    Returns:
      str: Markdown-Inhalt für registry-google.md (Stub).

    Side Effects:
      - Keine (pure function)
    ================================================================================
    """
    return f"""# registry-google.md — Google ({repo})\n\n> **→ [stealth-runner/registry-google.md](https://github.com/OpenSIN-AI/stealth-runner/blob/main/registry-google.md)**\n\n**Letztes Update**: {TODAY}\n"""
def make_registry_surveys(repo: str) -> str:
    """
    ================================================================================
    Generiert registry-surveys.md — Survey Automation Registry.

    WARUM existiert diese Funktion?
      Registry für Survey-Integration (Heypiggy, Cint, etc.). Verweist auf Master.

    Args:
      repo: Repository Name

    Returns:
      str: Markdown-Inhalt für registry-surveys.md (Stub).

    Side Effects:
      - Keine (pure function)
    ================================================================================
    """
    return f"""# registry-surveys.md — Surveys ({repo})\n\n> **→ [stealth-runner/registry-surveys.md](https://github.com/OpenSIN-AI/stealth-runner/blob/main/registry-surveys.md)**\n\n**Letztes Update**: {TODAY}\n"""
def make_registry_macos(repo: str) -> str:
    """
    ================================================================================
    Generiert registry-macos.md — macOS System Integration Registry.

    WARUM existiert diese Funktion?
      Registry für macOS-spezifische Tools (Accessibility, AX-Tree). Verweist auf
      stealth-runner Master.

    Args:
      repo: Repository Name

    Returns:
      str: Markdown-Inhalt für registry-macos.md (Stub).

    Side Effects:
      - Keine (pure function)
    ================================================================================
    """
    return f"""# registry-macos.md — macOS ({repo})\n\n> **→ [stealth-runner/registry-macos.md](https://github.com/OpenSIN-AI/stealth-runner/blob/main/registry-macos.md)**\n\n**Letztes Update**: {TODAY}\n"""
def make_graph_json(repo: str) -> str:
    """
    ================================================================================
    Generiert graph.json — Leeres Graph-Datenstruktur-Template.

    WARUM existiert diese Funktion?
      JSON-Stub für Code-Graph-Analyse. Wird von Graphify-Tools befüllt.

    Args:
      repo: Repository Name

    Returns:
      str: Leeres JSON-Objekt '{}'.

    Side Effects:
      - Keine (pure function)
    ================================================================================
    """
    return '{}'
def make_manifest_json(repo: str) -> str:
    """
    ================================================================================
    Generiert manifest.json — Leeres Manifest-Template.

    WARUM existiert diese Funktion?
      JSON-Stub für Tool-Manifest. Wird von Registry-Tools befüllt.

    Args:
      repo: Repository Name

    Returns:
      str: Leeres JSON-Objekt '{}'.

    Side Effects:
      - Keine (pure function)
    ================================================================================
    """
    return '{}'
def make_opencode_json(repo: str) -> str:
    """
    ================================================================================
    Generiert .opencode/opencode.json — Leeres OpenCode Konfigurations-Template.

    WARUM existiert diese Funktion?
      JSON-Stub für OpenCode CLI Konfiguration. Wird mit Tools/Skills befüllt.

    Args:
      repo: Repository Name

    Returns:
      str: JSON-String '{"tools":[],"skills":[]}'.

    Side Effects:
      - Keine (pure function)
    ================================================================================
    """
    return '{"tools":[],"skills":[]}'


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
    """
    ================================================================================
    Generiert alle fehlenden Pflichtdateien für ein einzelnes Repo. Iteriert über
    GENERATORS Mapping, prüft Existenz, erstellt Datei wenn fehlend.

    WARUM existiert diese Funktion?
      Zentrale Generierungslogik die von main() aufgerufen wird. Kapselt
      Repo-Lokation (direkt oder via find) und Datei-Erstellung.
      Unterstützt dry_run Modus für Vorschau ohne Schreiboperation.

    Args:
      repo_name: Repository Name (z.B. "stealth-core")
      dry_run: Wenn True, nur printen was erstellt würde (keine Datei-Writes)

    Returns:
      tuple[int, int]: (created_count, skipped_count) — Anzahl erstellter
        und übersprungener Dateien.

    Side Effects:
      - Erstellt fehlende .md/.json Dateien im Repo-Verzeichnis
      - Erstellt Unterverzeichnisse bei Bedarf (z.B. .opencode/)
      - Printet "NOT FOUND" wenn Repo nicht existiert
    ================================================================================
    """
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
    """
    ================================================================================
    CLI-Einstiegspunkt für Doc-Generierung. Erstellt fehlende Pflichtdateien in
    allen 23 Stealth-Suite Repos oder einem einzelnen Repo via --repo Filter.

    WARUM existiert diese Funktion?
      Agents MUSS vor jeder Aktion alle Pflichtdateien lesen. Diese Funktion
      stellt sicher dass jedes Repo sinrules.md, brain.md, fix.md etc. hat.
      Unterstützt --dry-run für Vorschau ohne Datei-Änderung, --repo für
      Single-Repo-Modus, und generiert alle 46 Dateien aus GENERATORS Mapping.

    Returns:
      None: Printet Ergebnisse nach stdout.

    Side Effects:
      - Erstellt fehlende .md/.json Dateien in Repo-Verzeichnissen
      - Erstellt Unterverzeichnisse bei Bedarf (z.B. .opencode/)
    ================================================================================
    """
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
