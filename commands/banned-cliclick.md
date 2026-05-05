# BANNED: cliclick ❌

## Status
**BANNED** — 2026-05-05, CUA-ONLY Architektur

## Warum BANNED?
- cliclick ist ein **Mausbewegungs-Tool** — genau wie pyautogui/pynput
- Verstößt gegen CUA-ONLY Architektur: NUR cua-driver AXPress
- CUA-ONLY = KEINE Mausbewegung, KEINE Koordinaten-Klicks

## Verbote
```bash
# ❌ FALSCH - BANNED:
/opt/homebrew/bin/cliclick m:x,y
/opt/homebrew/bin/cliclick dd:x,y
/opt/homebrew/bin/cliclick du:x,y
```

## RICHTIG: CUA-ONLY
```bash
# ✅ RICHTIG — cua-driver AXPress:
echo '{"pid": PID, "window_id": WID, "element_index": IDX}' | cua-driver call click

# ✅ RICHTIG — cua-driver drag (AX-basiert, KEINE rohe Maus!):
echo '{"pid": PID, "from_x": X1, "from_y": Y1, "to_x": X2, "to_y": Y2}' | cua-driver call drag

# ✅ RICHTIG — Wenn CUA nicht funktioniert: Survey ABBRECHEN, anderen wählen
```

## History
- 2026-05-05: BANNED — CUA-ONLY verletzt
- Mausbewegung = pyautogui/pynput-Level Verstoß

## Zugehörige Commands
- [banned-pyautogui.md](../banned-pyautogui.md)
- [banned-pynput.md](../banned-pynput.md)
- [banned-coordinates-click.md](../banned-coordinates-click.md)
