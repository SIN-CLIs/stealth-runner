# stealth-runner

Autonome Survey-Automation mit KI-Vision — Google Login → Umfragen → EUR-Verdienst.

**Teil der SIN-CLIs Stealth Suite.**

## Quick Start

```bash
playstealth launch --url 'https://www.heypiggy.com/?page=dashboard'
python3 -c "from cli.modules.heypiggy_login_box import heypiggy_login; heypiggy_login(PID)"
python3 -m cli.modules.survey_runner --pid PID --cdp-port PORT
```

## Stealth Suite — Kern-Repos

| Layer | Repo | Rolle |
|-------|------|-------|
| 🧠 Orchestrator | stealth-runner | Python: Vision-LLM, Survey-Automation |
| 🖱️ ACT (CUA-ONLY) | cua-touch | Python + Swift: AX-Interaktionen |
| 🎭 HIDE | playstealth-cli | Python: Chrome-Launcher |
| 👁️ SENSE | unmask-cli | TypeScript: DOM/Network X-Ray |
| 📹 VERIFY | screen-follow | Swift: Screen-Recording |
| 🔍 SCAN | macos-ax-cli | Swift: System AX Scan |
| 🐙 AX-INDEXER | ax-graph | Swift: Unified AX Graph |
| 🧱 CORE | stealth-core | Python: Retry, Breaker, Guardian |
| 🧠 MIND | stealth-mind | Python: CommandValidator, Predictor |
| 🛡️ GUARDIAN | stealth-guardian | Python: SuiteMonitor, AutoHealer |
| 🔄 SYNC | stealth-sync | Python: Session-Doku, ConflictResolver |
| 🔒 CAPTCHA | stealth-captcha | Python: 21 Captcha-Typen |
| 💀 LEGACY | skylight-cli | Swift: Ersetzt durch cua-touch |

## Lizenz

MIT
