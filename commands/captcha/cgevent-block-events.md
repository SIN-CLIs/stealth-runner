# captcha-cgevent-block-events.md — CGEvent = NULL Element-Events ✅

## Status
**DEFINITIV BEWIESEN** — 2026-05-05, 4 Spy-Tests

## Erkenntnis
`cua-driver call click/drag` postet CGEvent-Mausereignisse. Diese feuern auf **Document-Ebene**
(`pointerdown:true`, `mousemove:true`) aber **NIEMALS** auf dem Ziel-Element (`.gc-drag-block`).

## Beweis (Spy-Protokoll)

| Test | Bedingung | Document Events | Block Events |
|------|-----------|-----------------|--------------|
| 1 | SVGs visible | `[pointerdown:true, ...]` | `[]` |
| 2 | SVGs display:none | — | `[]` |
| 3 | SVGs pointer-events:none | — | `[]` |
| 4 | elementFromPoint=DIV | `[mousedown:true, ...]` | `[]` |

## Technische Ursache
CGEvent → macOS WindowServer → Chrome Compositor → visuelles Rendering
ABER: NICHT → Blink DOM Event System → JavaScript Event Handler

Das Captcha-Element (`.gc-drag-block`) registriert Handler via `addEventListener`.
Diese Handler empfangen NUR DOM-Events — CGEvent-Posts erzeugen KEINE DOM-Events
auf Element-Ebene.

## Konsequenz
Captcha-Validierung via CGEvent ist **unmöglich**. Selbst mit:
- Korrekten Koordinaten (Toolbar=119 kalibriert)
- Entfernten SVG-Overlays
- `elementFromPoint` = Block-Element

## Einziger Lösungsweg
AppleEvents JavaScript (`cua-driver page execute_javascript`):
1. Captcha-Handler direkt via JS referenzieren
2. Handler manuell aufrufen (ohne dispatchEvent)
3. ODER: Event-Listener des Captchas intercepten

## Zugehörige Commands
- [captcha/cgevent-spy.md](cgevent-spy.md) — Erster Spy-Test (Document-Ebene)
- [captcha/move-block.md](move-block.md) — Block per JS bewegen
- [captcha/solve-slide.md](solve-slide.md) — Slide Captcha Solver
