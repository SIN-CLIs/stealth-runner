---
content: |
  # AGENTS.md - Stealth Survey CLI
  
  **← [../AGENTS.md](../AGENTS.md) ist das MASTER Regelwerk.**
  **← [../sinrules.md](../sinrules.md) ist das zentrale Regelwerk.**
  
  ---
  
  ##  ARCHÄOLOGIE-TSUNAMI - ABSOLUTE PFLICHT VOR JEDER AKTION
  
  **️ VERSTOSS = SOFORTIGER STOP + RISIKO FÜR USER-DATEN/CHROME ️**
  
  **REGEL: Jeder Agent MUSS vor dem ERSTEN Code-Edit einen vollständigen Archäologie-Tsunami starten. KEINE AUSNAHMEN. NICHT VERHANDELBAR.**
  
  ### Warum?
  - **Alter Code = extrem gefährlich** (tötet User Chrome, leaked Credentials, destroyed sessions)
  - **Falscher Code = verwirrt Agents unnötig** (wie DICH! Du denkst du weißt es, aber du LÜGST!)
  - **Lügen-Code = das Schlimmste was in einer Entwicklung geschehen kann** (zerstört Production-Systeme)
  - **Nicht ausreichend kommentierter Code = nächster Agent zerstört alles wieder** (und der nächste, und der nächste...)
  
  ### ️ WARNUNG AN ALLE AGENTS: IHR LÜGT ALLE!
  **Jeder Agent denkt er "kennt den Code". Jeder Agent denkt er "weiß wie es funktioniert". Jeder Agent denkt er "braucht nicht recherchieren".**
  
  **FALSCH. IHR LÜGT ALLE. IMMER.**
  
  - Gestern war alles anders
  - Der Code den du denkst zu kennen wurde gestern Nacht geändert
  - Die PIDs die du auswendig gelernt hast sind DYNAMISCH
  - Die Tools die du nutzen willst sind VIELLEICHT BANNED
  - **RECHERCHIEREN IST NICHT OPTIONAL. ES IST PFLICHT.**
  
  ### Pflicht-Prozedur (IN DIESER REIHENFOLGE - KEIN VERKÜRZEN!):
  1. **Explore Subagent STARTEN**\: Scan ALLER Repos und Code-Dateien (rekursiv!)
  2. **Kategorisieren**\:  DELETE (alt/broken/banned) | ️ LEGACY |  ACTIVE
  3. **BANNED-Patterns prüfen**\: playstealth, webauto-nodriver, pkill -f Google Chrome, hardcoded PIDs, --remote-allow-origins=* ohne Quotes
  4. **Löschen**\: Alle  DELETE Dateien SOFORT entfernen (kein "vielleicht noch nützlich")
  5. **Kommentieren**\: Jede verbleibende Code-Datei mit EXTREMEN Kommentaren ausstatten:
     - **Was macht diese Datei?** (WARUM existiert sie?)
     - **Was ist die Architektur?** (Wie passt sie ins Gesamtbild?)
     - **Was sind die Abhängigkeiten?** (Was bricht wenn diese Datei fehlt?)
     - **BANNED-Methoden als WARNUNG** (in JEDER Datei!)
     - **Jede Funktion dokumentieren** (Args, Returns, Side-Effects, Race-Conditions)
     - **Jede Konstante erklären** (Warum dieser Wert? Warum nicht anders?)
     - **Warum-Fragen beantworten** (Warum 10 Erfolge? Warum 3x Retry? Warum 8s Sleep?)
  6. **Test-Dateien**\: Kein Tool ohne Test-Dateien! KEINE AUSNAHME!
  7. **Commits prüfen**\: `git log --oneline -20` - Was wurde zuletzt geändert?
  8. **Issues prüfen**\: Sind bekannte Bugs dokumentiert?
  
  ### Bei Abweichung (Code entspricht nicht Schema / sieht komisch aus / du verstehst es nicht):
  1. **SOFORT STOP** - Keine weiteren Änderungen!
  2. **Deep-Recherche starten** (alle Repos, Issues, Commits, READMEs)
  3. **ALLE betroffenen Dateien identifizieren**
  4. **Kommentare/Dokumentation in ALLEN betroffenen Dateien nachholen**
  5. **BANNED-Patterns in Code UND Doku markieren**
  6. **Erst DANN weiterarbeiten**
  
  ---
  
  ##  EXPLICITE VERBOTE (UNVERBRÜCHLICH)
  
  ### Chrome Startup
  -  `playstealth launch` - setzt NICHT --force-renderer-accessibility
  -  Chrome OHNE `--force-renderer-accessibility` - cua-driver AX-Tree LEER
  -  Chrome OHNE `--remote-allow-origins="*"` (MIT Quotes!) - CDP WebSocket 403
  -  Chrome MANUELL starten: `/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9999 --remote-allow-origins="*" --force-renderer-accessibility --no-first-run --user-data-dir=/tmp/heypiggy-new-$(date +%s) URL`
  
  ### User Chrome
  -  `pkill -f "Google Chrome"` - VERBOTEN (tötet User Chrome!)
  -  `killall Google Chrome` - VERBOTEN
  -  `kill <pid>` auf USER Chrome PIDs - VERBOTEN
  -  NUR Bot-Chrome beenden (profile=/tmp/heypiggy-new-*)
  
  ### Tools
  -  webauto-nodriver - ABSOLUT BANNED
  -  cua-driver click (raw index) - instabil, nutze tool_click.py
  -  skylight-cli click --element-index - Index instabil
  -  Hardcoded PIDs - dynamisch, niemals hardcodieren
  
  ## NEMO Architecture
  
  ```
  Compact Snapshot (skylight/CDP) → Nemotron Decision (NIM) → Batch Execute (CDP) → Memory/Guardian
  ```
  
  Vorteil: 1 LLM-Call PRO SEITE (nicht pro Element!) = 10× effizienter
