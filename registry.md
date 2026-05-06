# registry.md — Stealth Suite Command Registry (Master Index)

> **Zweck**: Zentraler Index aller Commands, Tools und Skripte im Stealth Suite Monorepo.
> Jeder Befehl MUSS hier oder in einer Category-Registry auffindbar sein.
> **Verwandt**: [commands.md](commands.md) | [banned.md](banned.md) | [sinrules.md](sinrules.md)

---

## Category Registries

| Registry | Zuständig für | Status |
|----------|--------------|--------|
| [registry-perception.md](registry-perception.md) | Screenshot, AX-Tree, Video, Audio Capture | 🔴 TODO |
| [registry-actuation.md](registry-actuation.md) | Click, Type, Navigate, Press Key (CUA + Fallback) | 🔴 TODO |
| [registry-eval.md](registry-eval.md) | Survey Scoring, Ban-Risk, Stealth-Check | 🔴 TODO |
| [registry-guardian.md](registry-guardian.md) | Semgrep Rules, Pipeline Guard, Verify-Box | 🔴 TODO |

---

## Quick Command Index

### Perception (SENSE)
| Command | File | Status |
|---------|------|--------|
| cua-driver list_windows | [commands/cua-driver/list-windows.md](commands/cua-driver/list-windows.md) | ✅ |
| cua-driver get_window_state | [commands/cua-driver/get-window-state.md](commands/cua-driver/get-window-state.md) | ✅ |
| macos-ax-cli find | (TODO) | 🔴 |

### Actuation (ACT)
| Command | File | Status |
|---------|------|--------|
| cua-driver click | [commands/cua-driver/click.md](commands/cua-driver/click.md) | ✅ |
| cua-driver set_value | [commands/cua-driver/set-value.md](commands/cua-driver/set-value.md) | ✅ |
| cua-driver click survey card | [commands/cua-driver/click-survey-card.md](commands/cua-driver/click-survey-card.md) | ✅ |

### Chrome Management (HIDE)
| Command | File | Status |
|---------|------|--------|
| playstealth launch | [commands/playstealth/launch.md](commands/playstealth/launch.md) | ✅ |
| kill bot chrome | [commands/bot-chrome/kill-bot-chrome.md](commands/bot-chrome/kill-bot-chrome.md) | ✅ |

### Survey Automation (survey-cli — NEW)
| Command | Location | Status |
|---------|----------|--------|
| survey login | [survey-cli/survey.py](survey-cli/survey.py) | ✅ NEW |
| survey scan | [survey-cli/survey/scanner.py](survey-cli/survey/scanner.py) | ✅ NEW |
| survey run | [survey-cli/survey/runner.py](survey-cli/survey/runner.py) | ✅ NEW |
| survey loop | [survey-cli/survey/runner.py](survey-cli/survey/runner.py) | ✅ NEW |
| survey watch | [survey-cli/survey.py](survey-cli/survey.py) | ✅ NEW |
| survey balance | [survey-cli/survey/scanner.py](survey-cli/survey/scanner.py) | ✅ NEW |
| survey status/doctor | [survey-cli/survey.py](survey-cli/survey.py) | ✅ NEW |
| survey opencode | [survey-cli/survey/opencode_bridge.py](survey-cli/survey/opencode_bridge.py) | ✅ NEW |
| **GitHub Repo** | [SIN-CLIs/survey-cli](https://github.com/SIN-CLIs/survey-cli) | ✅ |
| find bot pids | [commands/bot-chrome/find-bot-pids.md](commands/bot-chrome/find-bot-pids.md) | ✅ |

### Auth & Credentials
| Command | File | Status |
|---------|------|--------|
| Google Login Flow | [commands/google/login-flow.md](commands/google/login-flow.md) | ✅ |
| Infisical Login | [commands/infisical/login.md](commands/infisical/login.md) | ✅ |
| Infisical Secrets | [commands/infisical/secrets.md](commands/infisical/secrets.md) | ✅ |
| Heypiggy Credentials | [commands/heypiggy/credentials.md](commands/heypiggy/credentials.md) | ✅ |

### Banned (NIE verwenden)
| Command | File | Status |
|---------|------|--------|
| skylight-cli | [commands/banned-skylight-cli.md](commands/banned-skylight-cli.md) | ❌ |
| webauto-nodriver | [commands/banned-webauto-nodriver.md](commands/banned-webauto-nodriver.md) | ❌ |
| CDP commands | [commands/banned-cdp-commands.md](commands/banned-cdp-commands.md) | ❌ |
| pyautogui | [commands/banned-pyautogui.md](commands/banned-pyautogui.md) | ❌ |
| pynput | [commands/banned-pynput.md](commands/banned-pynput.md) | ❌ |
| coordinates-click | [commands/banned-coordinates-click.md](commands/banned-coordinates-click.md) | ❌ |
| pkill heypiggy-bot | [commands/bot-chrome/banned-pkill-heypiggy-bot.md](commands/bot-chrome/banned-pkill-heypiggy-bot.md) | ❌ |
| killall Chrome | [commands/bot-chrome/banned-killall-chrome.md](commands/bot-chrome/banned-killall-chrome.md) | ❌ |
| hardcoded PIDs | [commands/bot-chrome/banned-hardcoded-pids.md](commands/bot-chrome/banned-hardcoded-pids.md) | ❌ |

---

## Command File Rules (siehe [commands/cmd-rules.md](commands/cmd-rules.md))

1. Jeder verifizierte Command → `commands/<name>.md`
2. Jeder gebannte Command → `commands/banned-<name>.md`
3. >1 Command pro Provider → Provider-Subdirectory
4. Jede Command-Datei MUSS Abschnitt **„Zugehörige Commands“** enthalten
5. PIDs NIE hartcodieren — immer dynamisch scannen

---

## Letzte Aktualisierung
2026-05-05 — Initiale Registry erstellt
