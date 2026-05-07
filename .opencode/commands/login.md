---
description: Google Login für Heypiggy (6-Step CUA Flow)
agent: Stealth-Orchestrator
model: vercel/deepseek-v4-pro
---
Führe Google OAuth Login für Heypiggy aus:

1. Chrome-Check: Ist ein Bot-Chrome auf Port 9999? `curl -s http://127.0.0.1:9999/json/version`
2. Wenn nicht: `!kill-bots` dann Chrome neu starten:
   `"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --remote-debugging-port=9999 --remote-allow-origins="*" --force-renderer-accessibility --no-first-run --user-data-dir="/tmp/heypiggy-new-$(date +%s)" "https://www.heypiggy.com/?page=dashboard"`
3. 8s warten, dann Login:
   `python3 -c "from cli.modules.auto_google_login import execute; print(execute())"`
4. Verifiziere: `python3 survey-cli/survey.py status` → "Logged in: True"

BANNED: playstealth launch (setzt NICHT --force-renderer-accessibility!)
KORREKT: Chrome MANUELL starten mit Quotes + Timestamped Profile
