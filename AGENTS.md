# AGENTS.md — Stealth Runner v2.0

## Erlaubte Tools (ONLY these 3)
- **playstealth-cli**: Browser starten und tarnen
- **skylight-cli**: Screenshots, Klicks, Texteingabe, Scrollen, Drag & Drop
- **unmask-cli**: Stealth-Verifikation nach jeder Aktion

## Pipeline (immer genau so)
1. playstealth-cli launch → PID
2. skylight-cli screenshot --mode som → Bild
3. Llama 4 Scout → element_id
4. skylight-cli click --element-index <ID>
5. unmask-cli verify-stealth

## Verboten (NIE verwenden)
- cua-driver (ALT)
- open -na "Google Chrome"
- AXStaticText klicken
- Chrome DevTools Protocol (CDP)
- DOM-Manipulation

## Code-Regeln
- Python 3.12+, Type-Hints
- Kein f-string SQL
- audit.log() für alle Events
- Panel-Logik in sin_survey_core
