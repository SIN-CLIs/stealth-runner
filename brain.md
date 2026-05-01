# brain.md – Zentrale Architekturentscheidung

## JEDER Schritt durch Vision-LLM
Der DOM-Prescan-Fast-Path wurde ENTFERNT. Er klickte immer Element 1,
unabhängig vom Seiteninhalt. Jeder einzelne Schritt geht jetzt durch:
CAPTURE (SoM) -> VISION (Llama 4 Scout) -> EXECUTE -> VERIFY -> loop

## Stealth-Triade
- `playstealth-cli` (HIDE) – Browser starten, tarnen
- `skylight-cli` (ACT) – Screenshots, unsichtbare Klicks
- `unmask-cli` (SENSE) – Stealth-Verifikation

## Klick-Mechanismus
AXPress (`AXUIElementPerformAction`) – einziger funktionierender Klick auf Chrome 148.

## NIEMALS
- Ohne Vision klicken
- DOM-Prescan als Entscheidungsersatz
- Koordinaten raten
- `open -na Chrome`
- `cua-driver`

## LOGIN-Pipeline (NEU)
Vor dem Survey-Loop läuft jetzt der LOGIN-State:
LAUNCH -> LOGIN (cli/heypiggy-login) -> WAIT_READY -> CAPTURE -> VISION -> EXECUTE -> VERIFY -> repeat
Profile: `profiles/jeremy.yaml` (nicht im Git, liefert Google-Email)
