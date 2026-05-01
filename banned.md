# BANNED.md - Gescheiterte Methoden (Architektur-Regeln)

## ❌ BANNED (blockiert durch semgrep pre-commit)

| Regel                                     | Muster                                                      | Warum                                |
| ----------------------------------------- | ----------------------------------------------------------- | ------------------------------------ |
| `banned-chrome-pgrep`                     | `playstealth launch (isolierte PID) statt isolierte Instanz |
| `banned-chrome-open`                      | `playstealth launch`                                        | Manipuliert Nutzer-Browser           |
| `banned-NIEMALS – BANNED (semgrep Regel)` | Killt Nutzer-Prozesse, Datenverlust                         |
| `banned-pyautogui`                        | `BANNED – niemand importiert pyautogui`                     | Bewegt Nutzer-Maus                   |
| `banned-pynput`                           | `BANNED – niemand importiert pynput`                        | Bewegt Nutzer-Maus                   |
| `banned-openai-client`                    | `httpx an NVIDIA NIM`                                       | Nur httpx direkt an NVIDIA NIM       |
| `banned-coordinates-click`                | `skylight-cli click --x`                                    | Koordinaten raten → Apple-Menü (0,0) |
| `banned-skylight-cli`                     | skylight-cli                                                | Profil-Konflikt, falscher Chrome     |
| `banned-recovery-mode`                    | `recovery_mode: true`                                       | Omni macht ALLE Entscheidungen       |
| `mandatory-playstealth-launch`            | Chrome direkt starten                                       | Muss via `playstealth launch`        |

## ✅ TRIO LAYER (Live Auge-Hirn-Hand)

```python
# 1. EYES: cua-driver list_windows → Popup erkennen
cua("list_windows") → "Anmelden – Google Konten" (WindowID=30380)

# 2. BRAIN: cua-driver get_window_state → NUR Popup-Elemente
cua("get_window_state", {"pid":42296, "window_id":30380})
# → "Weiter" AXButton Index 35 (NUR im Popup, nicht auf Hauptseite!)

# 3. HANDS: cua-driver click → GARANTIERT im richtigen Fenster
cua("click", {"pid":42296, "window_id":30380, "element_index":35})

# LIVE LOOP: 250ms Polling
runner/trio_live.py start
```
