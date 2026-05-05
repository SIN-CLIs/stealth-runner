# changelog.md — Changelog Stealth Suite

> **Zweck**: Jede signifikante Änderung wird hier mit Datum und Referenz dokumentiert.
> Format: `YYYY-MM-DD | Typ | Beschreibung | Issue/PR`

---

## 2026-05-05

| Typ | Beschreibung | Referenz |
|-----|-------------|----------|
| **FIX** | Persona Age Bug: hartcodiertes Alter 42 → date_of_birth="1993-11-13", Alter dynamisch berechnet (32) | [fix.md](fix.md#hartcodiertes-alter) |
| **FIX** | persona_manager.py: DEFAULT_PERSONA age entfernt, date_of_birth hinzugefügt, education→Meister | [persona_manager.py](../playstealth-cli/playstealth_actions/persona_manager.py) |
| **FIX** | jeremy_schulze.json: 6 Felder befüllt (date_of_birth, city, postal_code, employment, education, household) | [jeremy_schulze.json](../A2A-SIN-Worker-heypiggy/profiles/jeremy_schulze.json) |
| **FIX** | sinrules.md: webauto/skylight/CDP klare Abgrenzung dokumentiert | [sinrules.md](sinrules.md#6) |
| **NEW** | /commands Reorganisation: 7 Provider-Subdirectories, cmd-rules.md mit 14 Regeln | [cmd-rules.md](commands/cmd-rules.md) |
| **NEW** | cua-driver/click-survey-card.md: Survey Cards via CUA klickbar (AXGroup → AXPress) | [click-survey-card.md](commands/cua-driver/click-survey-card.md) |
| **NEW** | End-to-End Survey Test: Login→Card→Consent→Frage→Disqualifikation (1 Zyklus) | [history.md](history.md) |
| **NEW** | registry.md: Master Command Registry mit Category-Registries | [registry.md](registry.md) |
| **NEW** | history.md: Session History Log initialisiert | [history.md](history.md) |
| **NEW** | roadmap.md: Stealth Suite Meilensteine definiert | [roadmap.md](roadmap.md) |
| **NEW** | registry-perception.md + registry-actuation.md angelegt | [registry-perception.md](registry-perception.md) |
| **NEW** | 6 Explore Agents: 10 SIN-CLIs Repos gescannt, alle CLI-Commands dokumentiert | [history.md](history.md#2026-05-05) |

| 2026-05-05 | **NEW** | CaptchaSolver Modul: Slide-Captcha via cua-driver drag + AppleEvents JS | [cli/modules/captcha_solver.py](cli/modules/captcha_solver.py) |
| 2026-05-05 | **FIX** | Koordinaten-Bug: Window-Position dynamisch statt hardcoded (73,70) | [commands/captcha/solve-slide.md](commands/captcha/solve-slide.md) |
| 2026-05-05 | **NEW** | Text-Captcha via pixtral-large Vision (Mistral API) | [commands/captcha/solve-text.md](commands/captcha/solve-text.md) |
| 2026-05-05 | **BANNED** | cliclick (Mausbewegung) + CDP dispatchEvent | [banned.md](banned.md) |

## 2026-05-04

| Typ | Beschreibung | Referenz |
|-----|-------------|----------|
| **FIX** | Skylight-cli Widersprüche in AGENTS.md, sinrules.md, brain.md behoben | [AGENTS.md](AGENTS.md) |
| **NEW** | Banned Commands: pyautogui, pynput, coordinates, applescript, skylight, webauto, CDP | [banned.md](banned.md) |
| **NEW** | Google Login PASSKEY Flow: 7-Step Dokumentation | [google/login-flow.md](commands/google/login-flow.md) |
| **NEW** | macOS Recovery Mode als SECRET WAY dokumentiert | [macos-recovery-mode.md](commands/macos-recovery-mode.md) |
| **NEW** | Infisical EU Login + Secrets dokumentiert | [infisical/](commands/infisical/) |

## 2026-05-03

| Typ | Beschreibung | Referenz |
|-----|-------------|----------|
| **NEW** | CUA-ONLY Trinity Architektur aktiviert | [AGENTS.md](AGENTS.md) |
| **NEW** | Heypiggy Credentials dokumentiert | [heypiggy/credentials.md](commands/heypiggy/credentials.md) |
| **NEW** | Session Manager Launch dokumentiert | [session-manager/launch.md](commands/session-manager/launch.md) |
