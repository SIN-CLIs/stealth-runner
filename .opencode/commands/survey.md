---
description: NEMO Survey Loop — Starte automatische Umfrage-Ausfüllung
agent: Stealth-Orchestrator
model: vercel/deepseek-v4-pro
---
Starte den NEMO Survey Loop für Heypiggy:

1. Prüfe Chrome läuft auf Port 9224 (HeyPiggy) (CDP): `curl -s http://127.0.0.1:9224/json | head -5`
2. Prüfe Login-Status: `python3 survey-cli/survey.py status`
3. Wenn nicht eingeloggt: `/login`
4. Dashboard scannen: `python3 survey-cli/survey.py scan`
5. Survey Loop starten: `python3 survey-cli/survey.py loop --max $1`

WENN Fehler (Chrome tot, Login expired):
- Chrome neu starten via manuellen Befehl (NIE playstealth!)
- `/login` erneut ausführen
- Loop fortsetzen

BANNED: playstealth launch, webauto-nodriver, cua-driver raw click
KORREKT: Nur survey-cli/tools/*.py und src/stealth_survey/ nutzen!
