# BANNED.md - Gescheiterte Methoden (Architektur-Regeln)

## ❌ BANNED (blockiert durch semgrep pre-commit)

| Regel | Muster | Warum |
|-------|--------|-------|
| `banned-chrome-pgrep` | `pgrep Chrome` | Greift Nutzer-Chrome statt isolierte Instanz |
| `banned-chrome-open` | `open -na "Google Chrome"` | Manipuliert Nutzer-Browser |
| `banned-pkill-chrome` | `pkill Chrome` | Killt Nutzer-Prozesse, Datenverlust |
| `banned-pyautogui` | `import pyautogui` | Bewegt Nutzer-Maus |
| `banned-pynput` | `import pynput` | Bewegt Nutzer-Maus |
| `banned-openai-client` | `from openai import` | Nur httpx direkt an NVIDIA NIM |
| `banned-coordinates-click` | `skylight-cli click --x` | Koordinaten raten → Apple-Menü (0,0) |
| `banned-webauto-nodriver` | webauto-nodriver | Profil-Konflikt, falscher Chrome |
| `banned-recovery-mode` | `recovery_mode: true` | Omni macht ALLE Entscheidungen |
| `mandatory-playstealth-launch` | Chrome direkt starten | Muss via `playstealth launch` |

## ✅ EINZIG FUNKTIONIERENDE METHODE

```bash
# 1. Chrome starten
playstealth launch --url 'https://heypiggy.com/?page=dashboard'

# 2. Vision (Nemotron Omni)
#    model: nvidia/nemotron-3-nano-omni-30b-a3b-reasoning
#    endpoint: https://integrate.api.nvidia.com/v1/chat/completions

# 3. Interaktion (nur skylight-cli)
skylight-cli click --pid <PID> --element-index <N>
skylight-cli type --pid <PID> --element-index <N> --text "wert"

# 4. Live Monitor (Rolling Video + SSE)
LiveOmniMonitor → capture → Omni → execute → loop
```
