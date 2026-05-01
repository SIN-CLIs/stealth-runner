# BANNED.md - Gescheiterte Methoden (Architektur-Regeln)

## ❌ BANNED (NIEMALS NUTZEN)

| Muster | Warum | semgrep-Regel |
|--------|-------|---------------|
| `pgrep Chrome` | Greift Nutzer-Chrome statt isolierte Instanz | `banned-chrome-pgrep` |
| `pkill Chrome` | Killt Nutzer-Prozesse, Datenverlust | `banned-pkill-chrome` |
| `open -na "Google Chrome"` | Manipuliert Nutzer-Browser | `banned-chrome-open` |
| `import pyautogui` | Bewegt Nutzer-Maus | `banned-pyautogui` |
| `import pynput` | Bewegt Nutzer-Maus | `banned-pynput` |
| `from openai import` | Nur httpx direkt an NVIDIA NIM | `banned-openai-client` |
| `skylight-cli click --x` | Koordinaten raten → Apple-Menü (0,0) | `banned-coordinates-click` |
| `webauto-nodriver` | Profil-Konflikt, falscher Chrome | `banned-webauto-nodriver` |
| `cua-driver --x --y` | **ALT:** Koordinaten-basiert, kein Popup-Schutz | ❌ BANNED |
| `recovery_mode: true` | Omni macht ALLE Entscheidungen | `banned-recovery-mode` |

## ✅ ALLOWED (cua-driver ONLY mit window-id + element-index)

### ✅ cua-driver (NEU – mit get_window_state + element_index!)
**AB v0.2.0+ mit `--element-index` und `--window-id` Support**

| Tool | Befehl | Wofür |
|------|--------|-------|
| `cua-driver list_windows` | Alle Fenster sehen (auch Popups!) | Popup-Erkennung |
| `cua-driver get_window_state --pid --window-id` | NUR Elemente im Popup | Gezielte Interaktion |
| `cua-driver click --pid --window-id --element-index` | Klick GARANTIERT im richtigen Fenster | Sichere Ausführung |
| `cua-driver set_value --pid --window-id --element-index --value` | Text im Popup | Texteingabe |

### ✅ skylight-cli (wenn nur 1 Fenster)
| Befehl | Wofür |
|--------|-------|
| `skylight-cli list-elements --pid` | Alle Elemente (alle Fenster) |
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
EYES:  cua-driver list_windows (250ms Polling) → Popup erkannt!
BRAIN: Omni analysiert → "Weiter" Button Index 35 im Google Popup
HANDS: cua-driver click --pid 42296 --window-id 30380 --element-index 35
       → GARANTIERT im Popup, nicht auf Hauptseite!
```
