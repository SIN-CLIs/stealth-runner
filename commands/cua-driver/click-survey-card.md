# cua-driver-click-survey-card — Heypiggy Survey Card klicken ✅

## Status
**VERIFIED** — 2026-05-05, PID=78708 WID=57128

## Command
```bash
echo '{"pid": PID, "window_id": WID, "element_index": IDX}' | cua-driver call click
```

## Live Example (2026-05-05)
```bash
# Dashboard geladen, 12 Survey Cards sichtbar
WID=57128 PID=78708

# Card 1 (0.06 €, 1 Min) klicken
echo '{"pid": 78708, "window_id": 57128, "element_index": 69}' | cua-driver call click
# → ✅ Performed AXPress on [69] AXGroup "".
# → "Umfrage starten" Modal erscheint!

# Elemente nach Modal:
# [241] AXHeading "Umfrage starten"
# [246] AXButton "Umfrage starten"
```

## Warum funktioniert das?
Heypiggy Survey Cards sind `<div>` mit `onclick="clickSurvey('ID')"` Handler.
Im AX-Tree sind es **AXGroup** Elemente (KEINE AXLink/AXButton!).
cua-driver kann `AXPress` auf AXGroup ausführen obwohl die Accessibility-Rolle
keine explizite "Press"-Aktion hat — der Maus-Klick triggert den JS-Handler.

## Survey Cards erkennen
Jede Card ist ein `AXGroup` mit:
- `AXStaticText` = Preis (z.B. "0.06 €")
- `AXStaticText` = Dauer (z.B. "1 Min")
- `AXStaticText` = Bewertungen (z.B. "🔥57")
- 5 `AXImage` = Sterne (1-5)

### Alle 12 Cards (2026-05-05 Dashboard)
| Index | Preis | Dauer | Bewertungen |
|-------|-------|-------|-------------|
| [69] | 0.06 € | 1 Min | 🔥57 |
| [83] | 0.41 € | 4 Min | 🔥9 |
| [97] | 0.15 € | 4 Min | 🔥21 |
| [111] | 0.25 € | 4 Min | 🔥48 |
| [125] | 0.11 € | 5 Min | 🔥11 |
| [139] | 0.21 € | 5 Min | 🔥18 |
| [153] | 0.25 € | 6 Min | 🔥24 |
| [167] | 0.30 € | 6 Min | 🔥30 |
| [181] | 0.30 € | 6 Min | 🔥30 |
| [195] | 0.35 € | 6 Min | 🔥27 |
| [209] | 0.15 € | 6 Min | 🔥42 |
| [223] | 0.11 € | 7 Min | 🔥50 |

## Post-Click: Modal-Elemente
Nach Klick auf Card → "Umfrage starten" Modal:
```
[241] AXHeading "Umfrage starten"
[246] AXButton "Umfrage starten"
```

Dann übernimmt der Standard Survey Flow.

## History
- 2026-05-05: Entdeckt — cua-driver click auf AXGroup funktioniert für Survey Cards
