---
description: Dashboard nach verfügbaren Umfragen scannen
agent: Stealth-Orchestrator
model: vercel/deepseek-v4-flash
---
Scanne das Heypiggy Dashboard nach verfügbaren Umfragen:

1. `python3 survey-cli/survey.py scan`
2. Zeige: Survey-ID, Titel, Vergütung, Zeitaufwand pro Umfrage
3. Wenn 0 Surveys: "Keine Umfragen verfügbar" melden
4. Wenn Surveys gefunden: Liste formatieren und nächste Schritte vorschlagen

WENN Scan fehlschlägt:
- Chrome-Check: `python3 survey-cli/survey.py doctor`
- Login prüfen: `/login` wenn nötig
