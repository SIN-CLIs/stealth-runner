# captcha-cgevent-spy.md — CGEvent = NULL DOM Events ✅

## Status
**BEWIESEN** — 2026-05-05, Spy-Test mit 8 Event-Listenern

## Erkenntnis
`cua-driver click/drag` postet CGEvent-Mausereignisse. Der Block bewegt sich **visuell** 
(style.left ändert sich), aber **KEINE JavaScript-DOM-Events** feuern auf dem Element.

## Beweis (Spy-Test)
```javascript
// 8 Event-Listener auf .gc-drag-block registriert:
['mousedown','pointerdown','mouseup','pointerup','mousemove','pointermove','click','dragstart']

// CGEvent click + drag ausgeführt
cua-driver call click  → Block bei 200px

// Spy-Check:
window.__events = {}  // ← KOMPLETT LEER nach CGEvent!
```

## Warum?
- CGEvent → macOS WindowServer → Chrome Rendering Pipeline → AX/Compositor
- Der Compositor bewegt das Element visuell (style.left ändert sich)
- ABER: Kein DOM-Event wird erzeugt
- Captcha-Handler (`mousedown`, `pointerdown`) feuern NIE

## Konsequenz
Captcha-Validierung via CGEvent ist **unmöglich**. Der einzige Weg:
1. AppleEvents JavaScript (`cua-driver page execute_javascript`)
2. Chrome mit `allow-javascript-apple-events = true` starten
3. `PointerEvent` dispatchen → Handler feuern → Captcha validiert

## Zugehörige Commands
- [captcha/move-block.md](captcha/move-block.md) — Block bewegen via JS
- [captcha/solve-slide.md](captcha/solve-slide.md) — Slide-Captcha Solver
- [captcha/solve-text.md](captcha/solve-text.md) — Text-Captcha via Vision
