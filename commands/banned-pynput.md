# BANNED: PYNPUT ❌

## Status
**BANNED** — 2026-05-03, AGENTS.md

## Warum BANNED?
- Simuliert Keyboard direkt (kein Element-Fokus)
- Keine Garantie das richtige Eingabefeld
- **Alternativlos zu CUA-DRIVER's set_value**

## Verbote
```python
# ❌ FALSCH - BANNED:
from pynput.keyboard import Key, Controller
from pynput.mouse import Controller as MouseController
keyboard.press('a')
keyboard.type("text")
mouse.click(x, y)
```

## RICHTIG: CUA-DRIVER
```bash
# ✅ RICHTIG:
echo '{"pid": PID, "window_id": WID, "element_index": IDX, "value": "TEXT"}' | cua-driver call set_value
```

## Alternative
- CUA-DRIVER set_value für Text-Eingabe
- CUA-DRIVER press_key für Tastendrücke
- Keychain Auto-Fill für Passwörter