# tool-registry.md — Tool Registry (Stealth Suite)

> **← [commands.md](commands.md) für Command-Index | → [registry.md](registry.md) für Master-Registry**

---

## Captcha Tools (NEU 2026-05-05)

| Tool | Zweck | File |
|------|-------|------|
| `CaptchaSolver(pid, wid)` | Slide + Drag-Drop Captchas lösen | [cli/modules/captcha_solver.py](cli/modules/captcha_solver.py) |
| `solve_slide()` | Slide-Captcha via cua-driver drag | [commands/captcha/solve-slide.md](commands/captcha/solve-slide.md) |
| `solve_dragdrop()` | Generic Drag-Drop | [commands/captcha/solve-drag.md](commands/captcha/solve-drag.md) |
| pixtral-large Vision | Text-Captcha OCR | [commands/captcha/solve-text.md](commands/captcha/solve-text.md) |

## CUA-Driver Tools

| Tool | Zweck | File |
|------|-------|------|
| `cua-driver call list_windows` | Alle Fenster auflisten | [cua-driver/list-windows.md](commands/cua-driver/list-windows.md) |
| `cua-driver call get_window_state` | AX-Tree laden | [cua-driver/get-window-state.md](commands/cua-driver/get-window-state.md) |
| `cua-driver call click` | Element klicken | [cua-driver/click.md](commands/cua-driver/click.md) |
| `cua-driver call set_value` | Text eingeben | [cua-driver/set-value.md](commands/cua-driver/set-value.md) |
| `cua-driver call press_key` | Tastendruck | [cua-driver/navigate-url.md](commands/cua-driver/navigate-url.md) |

## Playstealth Tools

| Tool | Zweck | File |
|------|-------|------|
| `playstealth launch` | Chrome starten | [playstealth/launch.md](commands/playstealth/launch.md) |
| `playstealth run-survey` | Survey ausführen | [playstealth/launch.md](commands/playstealth/launch.md) |

## Management Tools

| Tool | Zweck | File |
|------|-------|------|
| `SessionManager.close_all()` | BOT Chrome killen + Registry leeren | [session-manager/launch.md](commands/session-manager/launch.md) |
| `scripts/check_doc_health.py` | Doc-Health prüfen | [scripts/check_doc_health.py](scripts/check_doc_health.py) |
| `scripts/generate_missing_docs.py` | Fehlende Docs generieren | [scripts/generate_missing_docs.py](scripts/generate_missing_docs.py) |

## BANNED Tools

| Tool | Grund | File |
|------|-------|------|
| webauto-nodriver | ABSOLUT BANNED | [banned-webauto-nodriver.md](commands/banned-webauto-nodriver.md) |
| skylight-cli | RE-ACTIVATED (snapshot-compact + batch) | [banned-skylight-cli.md](commands/banned-skylight-cli.md) |
| CDP Navigation | BANNED | [banned-cdp-commands.md](commands/banned-cdp-commands.md) |
| pyautogui | BANNED | [banned-pyautogui.md](commands/banned-pyautogui.md) |
| pynput | BANNED | [banned-pynput.md](commands/banned-pynput.md) |

**Tool-Gesamt**: 11 verified + 5 banned = 16 registrierte Tools
**Letztes Update**: 2026-05-05
