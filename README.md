# stealth-runner (Public Core Engine)

Generische Automatisierungs-Engine der Stealth-Quad.
Orchestriert **Sense-Hide-Act-Verify-Learn** über atomare CLI-Tools —
**völlig plattformneutral**. Kein Zielportal ist fest eingebaut.

## Architektur
```
[stealth-runner]  ←  lädt  →  [stealth-skills (privat)]
       │                              │
       ├─ state_machine.py            ├─ platforms/heypiggy/
       ├─ executor.py                 ├─ platforms/swagbucks/
       ├─ strategy_selector.py        └─ _registry.json
       └─ learn.py
```

## Schnellstart
```bash
git clone https://github.com/OpenSIN-AI/stealth-runner.git
cd stealth-runner
pip install -e '.[dev]'
stealth-runner --skills-path ../stealth-skills --brain-path ../Infra-SIN-Global-Brain
```

## Skill-System
Eigene Plattform-Skills werden als Shell-Skripte + Markdown in einem separaten
Repository abgelegt. Die Engine lädt sie über `--skills-path` und `_registry.json`.

## Lizenz
MIT — frei für jede Nutzung, Modifikation und Integration.
