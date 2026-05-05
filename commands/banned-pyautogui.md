# BANNED: PYAUTOGUI ❌

## Status
**BANNED** — 2026-05-03, AGENTS.md

## Warum BANNED?
- Simuliert Maus/Klick auf KOORDINATEN
- Koordinaten ändern sich bei jedem Page-Load
- FALSCHES Element könnte angeklickt werden
- **KEINE Automation, nur Zufalls-Clicking!**

## Verbote
```python
# ❌ FALSCH - BANNED:
import pyautogui
pyautogui.click(x=500, y=300)
pyautogui.moveTo(x, y)
pyautogui.typewrite("text")
```

## RICHTIG: CUA-DRIVER
```bash
# ✅ RICHTIG - Element-basiert:
echo '{"pid": PID, "window_id": WID, "element_index": IDX}' | cua-driver call click
```

## Warum nicht pyautogui?
1. Koordinaten sind dynamisch
2. Keine Garantie das Richtige Element
3. Mauszeiger bewegt sich sichtbar
4. Element-Indizes sind PRÄZISE

## Alternative
- CUA-DRIVER mit element_index
- AXPress statt Koordinaten