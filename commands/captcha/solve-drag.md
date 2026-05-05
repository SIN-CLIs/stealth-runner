# captcha-solve-drag.md — Drag & Drop Captcha/Puzzle ✅

## Status
**VERIFIED** — 2026-05-05, cua-driver `drag` Command

## Command
```bash
# Drag-Element von Position A nach Position B ziehen
echo '{"pid": PID, "from_x": X1, "from_y": Y1, "to_x": X2, "to_y": Y2, "speed": 200, "steps": 40}' | cua-driver call drag

# Alternative: cliclick für präzisere Maus-Steuerung
/opt/homebrew/bin/cliclick m:<screen_x1>,<screen_y1> dd:<screen_x1>,<screen_y1> m:<screen_x2>,<screen_y2> du:<screen_x2>,<screen_y2>
```

## Live Example (PureSpectrum Drag Puzzle, 2026-05-05)
```bash
# "Bitte legen Sie die Zahl 36 in das leere Kästchen"
# 36-Element: [31] AXGroup "Drag item" @(259,305,100,100) → center (309,355) window
# Drop zone:  [38] AXGroup "Drop zone" @(598,453,150,150) → center (673,528) window
# Window at screen (73,70) → screen coords: (382,425) → (746,598)

# cua-driver drag (window coordinates)
echo '{"pid": 78708, "from_x": 309, "from_y": 355, "to_x": 673, "to_y": 528, "speed": 200, "steps": 40}' | cua-driver call drag
# → ✅ Posted drag from window-pixel (309,355) → (673,528), screen (382,425) → (746,598)

# cliclick (screen coordinates)
/opt/homebrew/bin/cliclick m:382,425 dd:382,425 m:746,598 du:746,598
```

## Drag-Elemente im AX-Tree erkennen

```python
# Drag-Elemente haben AXGroup mit Label "Drag item"
# Drop-Zonen haben AXGroup mit Label "Drop zone for dragging item"

# Koordinaten-Berechnung:
# screen_x = window_x + element_center_x
# screen_y = window_y + element_center_y
# element_center = (bounds_x + bounds_width/2, bounds_y + bounds_height/2)
```

## Fallback wenn Drag nicht registriert
- Browser benötigt DOM-Events (mousedown/mousemove/mouseup) → CDP JS dispatchEvent
- Keyboard-Navigation: Tab → Enter auf Element, Tab → Enter auf Drop-Zone
- Survey abbrechen und anderen Survey-Provider wählen

## Zugehörige Commands
- [captcha-solve-text.md](captcha-solve-text.md) — Text Captcha
- [captcha-solve-geetest.md](captcha-solve-geetest.md) — GeeTest Slider
- [cua-driver/click.md](../cua-driver/click.md) — Element klicken
- [cua-driver/get-window-state.md](../cua-driver/get-window-state.md) — AX-Tree lesen
