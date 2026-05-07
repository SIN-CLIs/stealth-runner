---
description: System-Check — Chrome, Login, Balance, Accessibility
agent: Stealth-Orchestrator
model: vercel/deepseek-v4-flash
---
Führe vollständigen System-Check aus:

1. Chrome-Status: `python3 survey-cli/survey.py doctor`
2. Login prüfen: `/balance`
3. cua-driver AX-Tree: `cua-driver call list_windows` (Prüfe ob AX-Tree lebendig ist)
4. CDP-Status: `curl -s http://127.0.0.1:9999/json | python3 -c "import sys,json; tabs=json.load(sys.stdin); print(f'{len(tabs)} Tabs offen')"`

Probleme und Fixes:
- Chrome tot → Manuell starten mit `--force-renderer-accessibility --remote-allow-origins="*"`
- AX-Tree leer → Accessibility prüfen (System Settings → Accessibility)
- Login expired → `/login`
- CDP 403 → Chrome mit Quotes neustarten
