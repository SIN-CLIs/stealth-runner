# GoCaptcha Slide — Status 2026-05-05 21:55

## ✅ WAS FUNKTIONIERT

### CSS move + CDP mouseup (PARTIALLY working)
- CSS: `block.style.left = targetCssLeft` → Block bewegt sich auf korrekte Position
- CDP: `Input.dispatchMouseEvent(mouseReleased)` → Block STAYT (kein Reset)
- **PROBLEM:** Puzzle-Stück (`.gc-tile`) bewegt sich NICHT mit
- **Demo-Seite:** Block bei 623 = "captcha akzeptiert" (kein Backend für Validation)
- **Real heypiggy:** Backend sieht Puzzle nicht ausgerichtet → Fail

### Koordinaten (frische Seite)
```
DOM (viewport):    Block center (446, 1102) → Target (664, 1102), Gap 218px
CSS target left:   218px (parent-local)
Block nach CSS:    X=623, right=705, diff=0px ✓
```

## ❌ WAS NICHT FUNKTIONIERT

### CDP full mouse sequence (mousedown→mousemove→mouseup)
- Captcha erkennt als Bot → Block resettet auf Start
- Selbst mit 2000ms Dauer, 60 steps, ease-out

### CUA-driver drag
- Commands erreichen Chrome nicht richtig
- Block bewegt sich NICHT
- Tile minimal bewegt (~13px) aber nicht richtig
- Koordinaten-System komplex: viewport ↔ window-local ↔ screen

## 🔧 NÄCHSTER SCHRITT

### Problem: Puzzle muss sich MIT dem Regler bewegen

**Lösungsidee:** Statt drag, CSS-Transform auf BEIDE Elemente anwenden:
1. Puzzle (`.gc-tile`) positionieren via CSS/Transform
2. Block (`.gc-drag-block`) positionieren via CSS
3. Mouseup feuern → Captcha liest beide Positionen

**Oder:** CUA mit element_index click erst testen, dann drag:
```bash
# Erst cache füllen
cua-driver call get_window_state '{"pid": 97078, "window_id": 59404}'

# Dann element_index click (um block zu fokussieren)
echo '{"pid": 97078, "window_id": 59404, "element_index": 230}' | cua-driver call click

# DANN drag command
echo '{"pid": 97078, "from_x": 468, "from_y": 627, "to_x": 686, "to_y": 627, "speed": 3, "steps": 60}' | cua-driver call drag
```

## 📁 RELEVANTE DATEIEN

- `stealth-suite/py-packages/captchas/solver/slide.py` — aktuelle Implementation
- `stealth-runner/cli/modules/captcha_solver.py` — alter Ansatz (captcha_solver.py)
- `/tmp/proof_before.png` — Screenshot vor Drag
- `/tmp/proof_after.png` — Screenshot nach CSS move (Block bei 623, Puzzle unverändert)

## 🎯 ZIEL

Auf heypiggy.com: Puzzle EXAKT an richtige Position → Backend validiert → Captcha schließt → Survey läuft