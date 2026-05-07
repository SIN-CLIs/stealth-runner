---
description: Heypiggy-Guthaben prüfen
agent: Stealth-Orchestrator
model: vercel/deepseek-v4-flash
---
Prüfe aktuelles Heypiggy-Guthaben und Login-Status:

1. `python3 survey-cli/survey.py balance`
2. Zeige: Guthaben in €, Login-Status
3. Wenn Login expired: `/login`

Ausgabe-Format: "💰 Guthaben: X.XX€ | Login: ✅/❌ | Surveys heute: N"
