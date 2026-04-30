# White-Label Architecture — stealth-runner (Engine) + stealth-skills (Platforms)

## Trennung
- **stealth-runner** (öffentlich, MIT) → Generische Automatisierungs-Engine
- **stealth-skills** (privat) → Plattform-spezifisches Wissen

## Engine (öffentlich)
```
src/stealth_runner/
├── state_machine.py     → Core State Machine (keine Plattform-Logik)
├── executor.py          → CLI Atomic Runner
├── strategy_selector.py → Brain Query (generisch)
├── learn.py             → Skill Capture Loop
└── vision_client.py     → LLM Vision Client
```

## Skills (privat)
```
SIN-CLIs/stealth-skills/platforms/
├── heypiggy/            → google-login, survey, modules
├── swagbucks/           → (future)
└── attapoll/            → (future)
```

## Runtime
```bash
stealth-runner --skills-path ../stealth-skills --platform heypiggy
```
