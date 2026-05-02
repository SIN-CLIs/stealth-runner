# BANNED.md - Gescheiterte Methoden (Architektur-Regeln)

## ❌ BANNED (NIEMALS NUTZEN)

### Popup-Interaktion via skylight-cli
```bash
# ❌ FALSCH – klickt Hauptfenster-Element, NICHT den Popup-Button!
skylight-cli click --pid 26897 --element-index 35
# → Klickte "Geld sparen, Geld verdienen" statt "Weiter" im Google-Popup!
```
**Korrekt**: `cua-driver call click '{"pid":26897,"window_id":33508,"element_index":35}'`

### Hintergrund-Prozesse via bash mit `&`
```bash
# ❌ FALSCH – blockiert trotzdem die Shell!
bash(command="screen-follow record --video --output /tmp/file.mp4 &")
```
**Korrekt**: `interactive_bash(tmux_command="new-session -d -s mysession")`

### playstealth --json Argument-Reihenfolge
```bash
# ❌ FALSCH
playstealth launch --url X --json
# → "unrecognized arguments: --json"
```
**Korrekt**: `playstealth --json launch --url X`

### asyncio.get_event_loop() in Python 3.14+
```python
# ❌ FALSCH – deprecated!
loop = asyncio.get_event_loop()
```
**Korrekt**: `loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)`

| Muster                                     | Warum                                           | semgrep-Regel              |
| ------------------------------------------ | ----------------------------------------------- | -------------------------- |
| `playstealth launch (isolierte PID)-pgrep` |
| `NIEMALS – BANNED`                         |
| `playstealth launch`                       | Manipuliert Nutzer-Browser                      | `banned-chrome-open`       |
| `BANNED (Mausbewegung verboten)`           | Bewegt Nutzer-Maus                              | `banned-pyautogui`         |
| `BANNED (Mausbewegung verboten)`           | Bewegt Nutzer-Maus                              | `banned-pynput`            |
| `httpx an NVIDIA NIM`                      | Nur httpx direkt an NVIDIA NIM                  | `banned-openai-client`     |
| `skylight-cli click --x`                   | Koordinaten raten → Apple-Menü (0,0)            | `banned-coordinates-click` |
| `skylight-cli`                             | Profil-Konflikt, falscher Chrome                | `banned-skylight-cli`      |
| `skylight-cli --x --y`                     | **ALT:** Koordinaten-basiert, kein Popup-Schutz | ❌ BANNED                  |
| `recovery_mode: true`                      | Omni macht ALLE Entscheidungen                  | `banned-recovery-mode`     |

## ✅ ALLOWED (skylight-cli ONLY mit window-id + element-index)

### ✅ skylight-cli (NEU – mit get_window_state + element_index!)

**AB v0.2.0+ mit `--element-index` und `--window-id` Support**

| Tool                                                               | Befehl                                | Wofür                |
| ------------------------------------------------------------------ | ------------------------------------- | -------------------- |
| `skylight-cli list_windows`                                        | Alle Fenster sehen (auch Popups!)     | Popup-Erkennung      |
| `skylight-cli get_window_state --pid --window-id`                  | NUR Elemente im Popup                 | Gezielte Interaktion |
| `skylight-cli click --pid --window-id --element-index`             | Klick GARANTIERT im richtigen Fenster | Sichere Ausführung   |
| `skylight-cli set_value --pid --window-id --element-index --value` | Text im Popup                         | Texteingabe          |

### ✅ skylight-cli (wenn nur 1 Fenster)

| Befehl                                     | Wofür                                                   |
| ------------------------------------------ | ------------------------------------------------------- |
| `skylight-cli list-elements --pid`         | Alle Elemente (alle Fenster)                            |
| `skylight-cli click --pid --element-index` | Klick (RISKANT bei Popups: klickt ins falsche Fenster!) |

### ✅ playstealth launch

```bash
playstealth launch --url 'https://heypiggy.com/?page=dashboard'
```

### ✅ Nemotron Omni Vision

```bash
model: nvidia/nemotron-3-nano-omni-30b-a3b-reasoning
endpoint: https://integrate.api.nvidia.com/v1/chat/completions
```

## 🔥 TRIO LAYER (DIE EINZIG RICHTIGE METHODE)

```
EYES:  skylight-cli list_windows (250ms Polling) → Popup erkannt!
BRAIN: Omni analysiert → "Weiter" Button Index 35 im Google Popup
HANDS: skylight-cli click --pid 42296 --window-id 30380 --element-index 35
       → GARANTIERT im Popup, nicht auf Hauptseite!
```

## 🛠️ POPUP-TOOLS (MCP + CLI, 2026-05-02)

```bash
# Popup-MCP (7 tools via cua-driver)
python cli/popup-mcp.py
# Tools: popup_list_windows, popup_get_elements, popup_click, popup_type,
#        popup_find_button, popup_is_closed, popup_daemon_start

# Google Login MCP
python cli/heypiggy-google-login-mcp.py  # → heypiggy_login(pid)

# CLI-Wrapper
cli/popup list-windows <PID>              # Alle Popup-Fenster
cli/popup click <PID> <WID> <INDEX>       # Klick via cua-driver AXPress
cli/heypiggy-login <PID>                  # Vollständiger Login
```
