# BANNED: COORDINATES-CLICK ❌

## Status
**BANNED** — 2026-05-03, AGENTS.md

## Warum BANNED?
- Koordinaten ändern sich bei Page-Load/Resize
- Keine Garantie das Richtige Element
- Mauszeiger bewegt sich sichtbar (User sieht es!)
- **Alternativlos zu element_index**

## Verbote
```bash
# ❌ FALSCH - BANNED:
click --x 500 --y 300
click_at 500 300
screencap --click X Y
python3 click.py --x=X --y=Y
```

## RICHTIG: Element-Index
```bash
# ✅ RICHTIG:
echo '{"pid": PID, "window_id": WID, "element_index": 54}' | cua-driver call click
# → Element bei beliebiger Position, stabil!
```

## Warum element_index?
1. Position-unabhängig
2. Stable zwischen Page-Loads
3. Accessibility prüft Element-Existenz
4. User sieht keine Mausbewegung

## Alternative
- CUA-DRIVER click mit element_index
- AXPress statt Koordinaten