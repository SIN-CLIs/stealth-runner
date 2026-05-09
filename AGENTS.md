---
content: |
  # AGENTS.md - Stealth-Runner NEXT-GEN (2026-05-06)

  ## 🔴🔴🔴 KRITISCHE NEUE REGELN (2026-05-09) — GANZ OBEN — UNVERBRÜCHLICH 🔴🔴🔴

  ### REGEL 1: NIEMALS frisches Profil starten!
  IMMER Profil 901 (Jeremy) mit existierenden Cookies nutzen:
  1. `cp -R "$HOME/Library/Application Support/Google Chrome/Profile 901 (Jeremy)" /tmp/chrome-jeremy-heypiggy-9999`
  2. Chrome auf 9999 starten mit dieser Kopie
  3. 7 HeyPiggy-Cookies aus Backup injizieren (siehe Regel 3)
  → NIEMALS neues leeres Profil starten — das ist Zeitverschwendung und Login nötig!

  ### REGEL 2: Profile-Kopie ist verschlüsselt — reicht nicht allein!
  Chrome speichert Cookies AES-128-GCM mit MAC-Challenge. Kopie allein reicht NICHT.
  → IMMER zusätzlich Cookies per CDP injizieren nach dem Start.

  ### REGEL 3: 7 HeyPiggy-Cookies IMMER injizieren nach Chrome-Start!
  Backup: `~/.stealth/heypiggy-backup/heypiggy-cookies.json`
  Struktur: `{"metadata": {...}, "cookies": [...]}` — 40 Cookies total (aktive Session: 7 HeyPiggy, Rest Google/misc)
  HEYPIGGY-Cookies (7 Stück):
  - `PHPSESSID` — www.heypiggy.com
  - `user_session` — www.heypiggy.com (KRITISCH für Login!)
  - `user_id` — www.heypiggy.com (KRITISCH!)
  - `user_a_b_group` — www.heypiggy.com
  - `lang_pig` — www.heypiggy.com
  - `g_state` — www.heypiggy.com
  - `referer` — www.heypiggy.com
  → NIEMALS nur Google-Cookies ansehen und aufgeben! HeyPiggy-Cookies IMMER finden und injizieren!
  → CDN: `Network.setCookies` mit batch (alle 7 in einem Call)
  → DANN: `Page.navigate` zu `https://www.heypiggy.com/?page=dashboard`
  → ERFOLG wenn body.innerText "Abmelden" enthält

  ### REGEL 4: Recipe für HeyPiggy Chrome-Start (COPY EXACT!)
  ```bash
  # 1. Profil kopieren
  cp -R "$HOME/Library/Application Support/Google Chrome/Profile 901 (Jeremy)" /tmp/chrome-jeremy-heypiggy-9999

  # 2. Chrome starten
  nohup "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
    --remote-debugging-port=9999 \
    --remote-allow-origins="*" \
    --force-renderer-accessibility \
    --no-first-run \
    --user-data-dir="/tmp/chrome-jeremy-heypiggy-9999" \
    "https://www.heypiggy.com/?page=dashboard" &>/dev/null &
  sleep 4

  # 3. 7 HeyPiggy-Cookies aus BACKUP injizieren (decrypt_cookies.py funktioniert NICHT für Chrome 147+ v11!)
  python3 -c "
  import json, asyncio, websockets, urllib.request
  COOKIE_FILE = '~/.stealth/heypiggy-backup/heypiggy-cookies.json'
  with open(COOKIE_FILE.expanduser()) as f:
      data = json.load(f)
  # Filter HeyPiggy only
  heypiggy = [{'name':c['name'],'value':c['value'],'domain':c['domain'],'path':c.get('path','/'),'expires':c.get('expires',-1),'secure':c.get('secure',False),'httpOnly':c.get('httpOnly',False)} for c in data.get('cookies',[]) if 'heypiggy' in c.get('domain','')]
  pages = json.load(urllib.request.urlopen('http://127.0.0.1:9999/json/list'))
  ws = [p['webSocketDebuggerUrl'] for p in pages if p.get('type')=='page' and 'heypiggy' in p.get('url','')][0]
  async def run():
      async with websockets.connect(ws) as ws2:
          await ws2.send(json.dumps({'id':1,'method':'Network.setCookies','params':{'cookies':heypiggy}}))
          await ws2.recv()
          await ws2.send(json.dumps({'id':2,'method':'Page.navigate','params':{'url':'https://www.heypiggy.com/?page=dashboard'}}))
          await asyncio.sleep(4)
          await ws2.send(json.dumps({'id':3,'method':'Runtime.evaluate','params':{'expression':'document.body.innerText.substring(0,500)'}}))
          r = await ws2.recv()
          print('EINGELOGGT!' if 'abmelden' in json.loads(r).get('result',{}).get('result',{}).get('value','').lower() else 'FEHLER')
  asyncio.run(run())
  "
  ```

  **WARUM decrypt_cookies.py NICHT nutzen?**
  - Chrome 147+ nutzt AES-128-GCM v11 (Safe Storage / Keychain)
  - `decrypt_cookies.py` schafft NUR v10 (AES-CBC, Chrome <147)
  - FÜR AKTUELLEN CHROME: Backup-Cookies nutzen aus `~/.stealth/heypiggy-backup/heypiggy-cookies.json`
  - Backup ist via CDP aus laufender Session extrahiert = funktioniert IMMER

  ---

  # AGENTS.md - Stealth-Runner NEXT-GEN (2026-05-06)

  ## ⚠️⚠️⚠️ CHROME START CONFIG — ZEILE 1 — NIEMALS ÄNDERN — NIEMALS VERGESSEN ⚠️⚠️⚠️
  
  ```bash
  # KORREKTUR (2026-05-09): Ehrliche Dokumentation
  # 
  # FAKTEN (keine Lügen):
  # - Profil 901 (Jeremy) = HeyPiggy (mit Cookie-Injection)
  # - Profil 902 = VERALTET, NICHT verwenden (verschlüsselte Cookies!)
  # - Chrome erlaubt nur EINEN Prozess pro user-data-dir (SingletonLock)
  #
  # AKTIV (HEYPIGGY):
  nohup "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
    --remote-debugging-port=9999 \
    --remote-allow-origins="*" \
    --force-renderer-accessibility \
    --no-first-run \
    --user-data-dir="/tmp/chrome-jeremy-heypiggy-9999" \
    "https://www.heypiggy.com/?page=dashboard" &>/dev/null &
  
  # Recipe: Profil 901 kopieren + Chrome starten + 7 HeyPiggy-Cookies injectieren
  # → Siehe REGELN 1-4 GANZ OBEN (diese Datei, Zeile 5-75)
  ```
  
  | Flag | Wert | Warum |
  |------|------|-------|
  | `--remote-debugging-port` | **9999** | HeyPiggy Bot-Chrome Port |
  | `--remote-allow-origins` | `"*"` | MIT Quotes — sonst 403 |
  | `--force-renderer-accessibility` | required | CUA AX-Tree — sonst LEER |
  | `--no-first-run` | required | Blockiert First-Run-Dialog |
  | `--user-data-dir` | `/tmp/chrome-jeremy-heypiggy-9999` | Profil 901 Kopie |
  
  **WICHTIG:**
  - Profil 901 (Jeremy) = HEYPIGGY (nicht SINator!)
  - Profil 902 = VERALTET (verschlüsselte Cookies, Login nötig!)
  - Port 9999 = HeyPiggy (nicht 9222/9224!)
  - Port 9222 = SINator Chrome (NICHT anfassen!)
  - Port 9224 = VERALTET (alter HeyPiggy-Port, nicht verwenden!)
  
  **BANNED:**
  - `pkill -f "Google Chrome"` = tötet ALLE Chrome-Instanzen
  - `launch_parallel.py` + Profil 902 = verschlüsselte Cookies, FALSCH!
  - Port 9224 für HeyPiggy = FALSCH, Port 9999 verwenden!
  - Frische `/tmp/` Profile ohne Cookie-Injection = Login nötig, FALSCH!

---


  
  ---
  
  **-< [sinrules.md](sinrules.md) ist das zentrale Regelwerk. Alle Golden Rules sind DORT.**
  **-< [brain.md](brain.md) dokumentiert die Architektur im Detail.**
  **-< [registry.md](registry.md) ist der Master Command Index.**
  >
  **BAN REGELN** (siehe [sinrules.md#6](sinrules.md) für Details):
  - `webauto-nodriver` = ABSOLUT BANNED
  - CDP = NUR für JS execute/evaluate, BANNED für Navigation/Klicks
  >
  **NEXT-GEN ARCHITECTUR (2026-05-06) - NEU:**
  - **skylight-cli** = RE-ACTIVATED - Primary Interaction Tool (Compact Snapshot + Batch)
  - **CDP WebSocket** = PRIMARY - Direkter CDP-Zugriff, kein cua-driver Daemon mehr
  - **Nemotron 3 Omni** = BRAIN - NVIDIA NIM für Survey-Entscheidungen
  - **src/stealth_survey/** = INTENTIONALLY DELETED (2026-05-08) — NEMO läuft via survey-cli + CDP
  >
  **PFLICHT-REGELN** (vor JEDER Session lesen): sinrules.md, brain.md, fix.md, learn.md, anti-learn.md, banned.md, issues.md
  **DOC-HEALTH**\: `python3 scripts/check_doc_health.py` -> prüft alle 23 Repos auf Pflichtdateien
  **DOC-GENERATE**\: `python3 scripts/generate_missing_docs.py` -> erstellt fehlende Pflichtdateien in allen Repos
  >
  **SYSTEM PROMPT** (wird via `.opencode/opencode.json` geladen):
  Jede Session beginnt mit Laden aller context_files. Der Agent MUSS vor jeder Aktion
  sinrules, brain, fix, learn, anti-learn, banned prüfen. Bei Fehlern: Universal-Fehlercheck.
  >
  **FEHLERCHECK**\: Bei Abweichung -> 10-Punkte-Analyse (Root-Cause, Befehls-Prüfung, Session-Abgleich,
  Cross-Repo, Registry, W-Fragen, Pipeline, Memory, Doku-Update, Vollständigkeits-Check)
  
  ---
  
  ##  ARCHÄOLOGIE-TSUNAMI - ABSOLUTE PFLICHT VOR JEDER AKTION
  
   **VERSTOSS = SOFORTIGER STOP + RISIKO FÜR USER-DATEN/CHROME**
  
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
  2. **Kategorisieren**\: DELETE (alt/broken/banned) | LEGACY | ACTIVE
  3. **BANNED-Patterns prüfen**\: playstealth, webauto-nodriver, pkill -f Google Chrome, hardcoded PIDs, --remote-allow-origins=* ohne Quotes
  4. **Löschen**\: Alle DELETE Dateien SOFORT entfernen (kein "vielleicht noch nützlich")
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
  
  ## 🚨 GOLDENE REGEL: NIEMALS MONOLITHISCHE ENDPOINTS BAUEN — IMMER ALLE survey-cli/tools/ ALS FASTAPI ENDPOINTS EXPONIEREN (2026-05-09)
  
  **ABSOLUTER VERBOT:** Monolithische Endpoints wie `POST /survey/run-one` die ALLES in einer Funktion machen (click + loop + fill + submit + rate).
  
  **WARUM?**
  - Monolithische Endpoints sind **UNDEBUGGABLE** — wenn sie fehlschlagen, weißt du nicht welcher Teil
  - Sie können **NICHT wiederverwendet** werden — du kannst nicht nur den "Rating-Teil" aufrufen
  - Sie **kopieren Code** statt existierende `survey-cli/tools/` zu nutzen
  - `survey-cli/tools/` sind bereits **getestet** (~38 test files in survey-cli/tests/), **profil-aware**, **provider-aware**
  - Monolithen werden **NIE fertig** — man fügt immer mehr if/else hinzu bis sie explodieren
  
  **RICHTIG (Beispiel):**
  ```python
  # survey-cli/tools/tool_open_survey.py — bereits fertig, getestet, frozen=True
  def open_survey(survey_id: str) -> Dict: ...
  
  # → FastAPI Endpoint NUR als Wrapper:
  @router.post("/survey/open")
  async def api_open_survey(req: OpenSurveyRequest):
      return open_survey(req.survey_id)
  ```
  
  **FALSCH (Beispiel):**
  ```python
  # NIEMALS SO ETWAS BAUEN:
  @router.post("/survey/run-one")
  async def run_one_survey(req):
      # 2000 Zeilen die ALLES machen:
      # - click card
      # - click modal
      # - wait for ajax
      # - extract last_link
      # - navigate
      # - loop 25 pages
      # - auto-select first option (wrong!)
      # - auto-fill "test"
      # - check completion keywords
      # - ... NEVER ENDS
      pass
  ```
  
  **UMGESETZTE FASTAPI ENDPOINTS (survey-cli/tools/ → FastAPI):**
  | Survey-CLI Tool | FastAPI Endpoint | Status |
  |----------------|------------------|--------|
  | `tool_open_survey.py` | `POST /survey/open` | ✅ EXISTIERT in agent-toolbox/api/survey_tools.py |
  | `tool_fill_survey.py` | `POST /survey/fill` | ✅ EXISTIERT in agent-toolbox/api/survey_tools.py |
  | `tool_rate_survey.py` | `POST /survey/rate` | ✅ EXISTIERT in agent-toolbox/api/survey_tools.py |
  | `tool_click.py` | `POST /survey/click` | ✅ EXISTIERT in agent-toolbox/api/survey_actions.py |
  
  **PFLICHT:**
  1. Wenn ein `survey-cli/tools/tool_*.py` existiert → **SOFORT** FastAPI-Wrapper bauen
  2. Wenn ein Command in `/commands/` als ✅ VERIFIED markiert ist → **SOFORT** in `survey-cli/tools/tool_*.py` umwandeln → dann FastAPI-Wrapper
  3. NIE mehr als 50 Zeilen in einem Endpoint — alles was komplexer ist gehört in ein Tool
  4. Tools müssen **standalone testbar** sein (`cd survey-cli && python3 -m pytest tests/test_*.py`)
  
  ---
  
  ##  EXPLICITE VERBOTE (UNVERBRÜCHLICH)
  
  ###  CHROME NUR MIT ACCESSIBILITY + CDP STARTEN
  **REGEL: Chrome MUSS IMMER mit `--force-renderer-accessibility` UND `--remote-allow-origins="*"` gestartet werden.**
  -  `playstealth launch` - setzt NICHT beide Flags
  -  Chrome OHNE `--force-renderer-accessibility` - cua-driver AX-Tree LEER
  -  Chrome OHNE `--remote-allow-origins="*"` - CDP WebSocket 403
  -  `/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9999 --remote-allow-origins="*" --force-renderer-accessibility --no-first-run --user-data-dir=/tmp/chrome-jeremy-heypiggy-9999 URL`
  -  cua-driver + CDP BEIDE nutzen - eine Chrome-Instanz, beide Tools
  
  ### NIEMALS user Chrome/Prozesse töten!
  **REGEL: ICH DARF NIEMALS - UNTER KEINEN UMSTÄNDEN - USER CHROME, USER OPENCODE SITZUNGEN ODER ANDERE USER-PROZESSE BEENDEN**
  
  -  `pkill -f "Google Chrome"` - VERBOTEN
  -  `killall Google Chrome` - VERBOTEN
  -  `kill <pid>` auf USER Chrome PIDs - VERBOTEN
  -  `ps aux | grep Chrome | kill` - VERBOTEN
  -  Chrome-Prozesse über grep/kill beenden - VERBOTEN
  
  **NUR ERLAUBT:**
  -  Chrome mit Profil 901 Kopie in `/tmp/chrome-jeremy-heypiggy-9999`
  -  Eigenen Code in `/tmp/` starten und dort beenden
  -  NUR Main-Prozesse killen mit Pattern `/Contents/MacOS/Google Chrome` + `--remote-debugging-port=9999` (HeyPiggy)
  
  **WENN Chrome neu gestartet werden muss:**
  - Recipe REGELN 1-4 ausführen (Profil 901 Kopie + Cookie-Injection)
  - Niemals existierende User-Chrome-Instanzen touchen
  - Bei Konflikt: Frisches Profil in `/tmp/` starten + Cookie-Injection
  
  ### /commands Verzeichnis (2026-05-10) - COMMAND DOCUMENTATION
  
  **Governance**: `/commands/cmd-rules.md` - alle Regeln zu /commands.
  
  **Provider-Struktur**: Sobald >1 Command zu Provider -> Subdirectory.
  
  ```
  /commands/                    (46 .md files, 10 subdirs)
  +── cmd-rules.md
  +── bot-chrome/               (2 verified + 1 banned)
  |   +── kill-bot-chrome.md ✅, find-bot-pids.md ✅
  |   +── (DEPRECATED: Port 9224 + Profil 902 → GEFIXT 2026-05-10)
  +── captcha/                  (10 files: slide/text/drag puzzle solvers)
  |   +── solve-slide.md, solve-text.md, solve-drag.md
  |   +── WORKING-SOLUTION.md, README.md
  +── cdp/                      (CDP commands)
  +── chrome/                   (Chrome start/config)
  +── cua-driver/               (9 commands)
  |   +── click.md, click-survey-card.md, set-value.md
  |   +── list-windows.md, get-window-state.md
  |   +── find-element-index.md, find-pid-wid.md, navigate-url.md
  |   +── switch-tab.md (NEU 2026-05-10)
  +── heypiggy/                 (2 commands)
  |   +── credentials.md, rating-page.md
  +── infisical/                (2 commands)
  +── playstealth/              (1 command — BANNED: kein accessibility flag)
  +── session-manager/          (1 command)
  +── surveys/                  (6 survey provider docs)
  |   +── purespectrum-survey.md ✅ (2026-05-09)
  |   +── surveyrouter-pre-qualifier-2026-05-09.md ✅
  |   +── qualtrics-huk-survey.md, civey-fill.md
  |   +── survey-answer-patterns.md, survey-start-flow.md ✅
  +── [root]                   (provider survey docs)
      +── brand-ambassador-survey.md, insights-today-survey.md
      +── my-take-survey.md, nfield-survey.md, strat7-survey.md
      +── purespectrum-survey.md, proquoai-survey.md
      +── cpx-rating-page.md
  +── banned-cdp-commands.md, macos-recovery-mode.md
  ```
  
  ### Chrome Kill Regeln (UNVERBRÜCHLICH)
  -  PIDs NIEMALS hardcodieren (71104, 70293, etc.) -> PIDs ändern sich!
  -  `pkill -f "heypiggy-bot"` -> killt ALLE Chrome-Instanzen inkl. USER Chrome
  -  `killall Google Chrome` -> killt ALLE Chrome-Instanzen (USER + BOT!)
  -  NUR Main-Prozesse killen: Pattern `/Contents/MacOS/Google Chrome` + `--remote-debugging-port=9999` (HeyPiggy) oder `--remote-debugging-port=9222` (SINator)
  -  Registry leeren: `rm -f ~/.stealth/sessions.json`
  -  SOTA: `SessionManager.close_all()` -> killt + leert Registry automatisch
  
  ## VISION-MODELL: Nemotron 3 Nano Omni (PRIMARY)
  
  - **30B-A3B Mixture-of-Experts** - Video + Audio + Bild + Text in EINEM Modell
  - **256K Kontext** - ganze Survey-Sessions in einem Call
  - **SSE Streaming** - `stream: true` -> tokenweise Antwort
  - **API**\: `POST https://integrate.api.nvidia.com/v1/chat/completions`
  - **Model Name**\: `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`
  - **API Key**\: `$NVIDIA_API_KEY` (Prefix: `nvapi-...`)
  
  ---
  
  ##  NEMO-ARCHITEKTUR: Compact-Loop mit Batch (2026-05-06, PRIMARY)
  
  **skylight-cli un-deprecated!** Jetzt PRIMARY für kompakte Snapshots + Batch-Ausführung.
  
  ```
  +──────────────────────────────────────────────────────────────────────────+
  |                 NEMO LOOP - 1 LLM Call pro Frage-Batch                   |
  +──────────────────────────────────────────────────────────────────────────+
  |                                                                           |
  |  while not complete:                                                      |
  |                                                                           |
  |  +──────────────────────────────────────────────────────────────────+     |
  |  | SCHRITT 1: COMPACT SNAPSHOT (skylight-cli / CDP)                |     |
  |  |                                                                  |     |
  |  | skylight-cli snapshot-compact --pid X --semantic                 |     |
  |  | -> {                                                              |     |
  |  |     "refs": {"@e0": {role:"radio",text:"Männlich"},...},       |     |
  |  |     "semantic": {"questions":[...], "progress":"3/10"},         |     |
  |  |     "provider": "qualtrics",                                     |     |
  |  |     "stealthScore": 0.92                                         |     |
  |  |   }                                                              |     |
  |  +──────────────────────────────────────────────────────────────────+     |
  |       |                                                                   |
  |       ▼                                                                   |
  |  +──────────────────────────────────────────────────────────────────+     |
  |  | SCHRITT 2: NEMOTRON DECISION (NVIDIA NIM)                        |     |
  |  |                                                                  |     |
  |  | NIMSurveyClient.decide(snapshot, profile, learnings)             |     |
  |  | -> {"actions": [                                                  |     |
  |  |     {"ref": "@e0", "action": "select"},                          |     |
  |  |     {"ref": "@e12", "action": "fill", "value": "32"},            |     |
  |  |     {"action": "submit"}                                         |     |
  |  |   ]}                                                             |     |
  |  |                                                                  |     |
  |  | Token-Effizient: ~500 tokens in, ~100 tokens raus                |     |
  |  +──────────────────────────────────────────────────────────────────+     |
  |       |                                                                   |
  |       ▼                                                                   |
  |  +──────────────────────────────────────────────────────────────────+     |
  |  | SCHRITT 3: BATCH EXECUTE (CDP WebSocket)                         |     |
  |  |                                                                  |     |
  |  | BatchExecutor.execute(ws_url, actions, provider)                 |     |
  |  | -> provider-specific CDP JS:                                      |     |
  |  |   Qualtrics:    .NextButton.click()                              |     |
  |  |   TolunaStart:  .cf-radio[0].click(); button.click()             |     |
  |  |   Strat7:       .bsbutton.click()                                |     |
  |  |                                                                  |     |
  |  | Alle Actions in EINEM WebSocket-Call (kein Round-Trip!):        |     |
  |  | Runtime.evaluate("(function(){...alle actions...})()")           |     |
  |  +──────────────────────────────────────────────────────────────────+     |
  |       |                                                                   |
  |       ▼                                                                   |
  |  +──────────────────────────────────────────────────────────────────+     |
  |  | SCHRITT 4: MEMORY + GUARDIAN (auto)                              |     |
  |  |                                                                  |     |
  |  | stealth_memory.log_step(snapshot, decision, result)              |     |
  |  | stealth_guardian.monitor_and_heal(session, result)               |     |
  |  | -> incidents/{session}/, learn.md, anti-learn.md                  |     |
  |  +──────────────────────────────────────────────────────────────────+     |
  |                                                                           |
  |  Vorteil: 1 LLM-Call PRO SEITE (nicht pro Element!)                      |
  |           90% Token-Ersparnis durch Compact Snapshot                      |
  |           5× schneller als cua-driver Loop                               |
  |                                                                           |
  +──────────────────────────────────────────────────────────────────────────+
  ```
  
### NEMO Modul-Struktur (INTENTIONALLY DELETED - DO NOT RESTORE)

  `src/stealth_survey/` wurde am 2026-05-08 absichtlich gelöscht.
  NEMO-Loop läuft stattdessen via:
  - skylight-cli snapshot-compact (Primary)
  - CDP WebSocket Runtime.evaluate (Fallback)
  - survey-cli/survey/*.py Module
  
  ### skylight-cli Commands (NEU, SR-37)
  
  | Command | Zweck | Beispiel |
  |---------|-------|----------|
  | `snapshot-compact` | Kompaktes @eN Snapshot | `skylight-cli snapshot-compact --pid X --semantic` |
  | `find` | Element per role/text/label finden | `skylight-cli find --role button --text "Weiter"` |
  | `batch` | Batch-Aktionen ausführen | `skylight-cli batch '[{"ref":"@e0","action":"click"}]'` |
  
  ### Verboten vs. Erlaubt (NEMO-Update)
  
  | Tool | Status | Begründung |
  |------|--------|------------|
  | **skylight-cli** snapshot-compact |  ERLAUBT | PRIMARY - Compact Snapshot |
  | **skylight-cli** batch |  ERLAUBT | Batch-Ausführung |
  | **CDP WebSocket** Runtime.evaluate |  ERLAUBT | Fallback wenn skylight nicht verfügbar |
  | **src/stealth_survey/** |  ❌ DELETED | INTENTIONALLY DELETED 2026-05-08 — NEMO läuft via survey-cli + CDP |
  | **cua-driver** | ️ DEPRECATED | Nur Fallback, NEMO ist PRIMARY |
  | skylight-cli click (index) |  BANNED | Nutze batch stattdessen |
  | webauto-nodriver |  BANNED | Absolut |
  
  ---
  
  ## ARCHITEKTUR: CUA-ONLY TRINITY (2026-05-03, LEGACY/DEPRECATED)
  
  **Das Problem:** CDP WebSocket wird von Chrome blockiert (origin check). skylight-cli mischt Browser-Chrome + Web-Content.
  
  **Die Lösung:** NUR cua-driver für ALLE Interaktionen.
  
  ```
  +──────────────────────────────────────────────────────────────────────────+
  |                     CUA-ONLY TRINITY - Klick-Ablauf                       |
  +──────────────────────────────────────────────────────────────────────────+
  |                                                                           |
  |  Chrome Recipe (REGELN 1-4)                                               |
  |  -> {"pid": DYNAMIC, "port": 9999}                                        |
  |       |                                                                   |
  |       ▼                                                                   |
  |  +──────────────────────────────────────────────────────────────────+     |
  |  | SCHRITT 0: DAEMON (nohup)                                        |     |
  |  |                                                                  |     |
  |  | nohup cua-driver serve > /tmp/cua-daemon.log 2>&1 &              |     |
  |  | -> Daemon starten (überlebt bash-Sessions!)                       |     |
  |  | Ohne Daemon: keine Session-Cache -> keine Clicks!                 |     |
  |  +──────────────────────────────────────────────────────────────────+     |
  |       |                                                                   |
  |       ▼                                                                   |
  |  +──────────────────────────────────────────────────────────────────+     |
  |  | SCHRITT 1: WINDOW FINDEN (cua-driver)                           |     |
  |  |                                                                  |     |
  |  | cua-driver call list_windows                                     |     |
  |  | -> Alle Fenster der App (Content-Window hat height > 100)        |     |
  |  | -> Apple-Menüleiste (depth 1-4) IMMER ignorieren!                |     |
  |  +──────────────────────────────────────────────────────────────────+     |
  |       |                                                                   |
  |       ▼                                                                   |
  |  +──────────────────────────────────────────────────────────────────+     |
  |  | SCHRITT 2: STATE CACHEN (cua-driver)                            |     |
  |  |                                                                  |     |
  |  | cua-driver call get_window_state(pid, window_id)                 |     |
  |  | -> Kompletten AX-Tree cachen (alle Elemente mit Indices)         |     |
  |  | -> Elemente mit @(x,y,w,h) Position für Koordinaten-Fallback     |     |
  |  | -> depth > 5 Filter für Browser-Content                          |     |
  |  +──────────────────────────────────────────────────────────────────+     |
  |       |                                                                   |
  |       ▼                                                                   |
  |  +──────────────────────────────────────────────────────────────────+     |
  |  | SCHRITT 3: INTERAKTION (cua-driver, NUR CUA!)                   |     |
  |  |                                                                  |     |
  |  | BUTTON KLICKEN:  call click(pid, wid, index)                     |     |
  |  |                  Timeout 30s + 3x Retry bei kAXErrorCannotComplete|     |
  |  |                                                                  |     |
  |  | TEXT EINGEBEN:  call set_value(pid, wid, index, "text")          |     |
  |  |                                                                  |     |
  |  | TASTENDRUCK:    call press_key(pid, "return")                   |     |
  |  |                                                                  |     |
  |  | NAVIGIEREN:     call click -> addr_bar                            |     |
  |  |                 call set_value -> URL                              |     |
  |  |                 call press_key -> "return"                         |     |
  |  +──────────────────────────────────────────────────────────────────+     |
  |       |                                                                   |
  |       ▼                                                                   |
  |  FALLBACK-KETTE:                                                          |
  |  1. AXPress auf element_index -> Timeout 30s + 3x Retry (PRIMARY)         |
  |  2. Bei Failure: Koordinaten-Click click(pid, x, y) aus @(x,y,w,h)       |
  |  3. Bei Links: CDP Navigation (NUR wenn CUA Nav fehlschlägt)            |
  |                                                                           |
  +──────────────────────────────────────────────────────────────────────────+
  ```
  
  ## TOOLS (NEMO-PRIMARY, CUA-ONLY = LEGACY)
  
  | Tool | Rolle | Befehl |
  |------|-------|--------|
  | **skylight-cli** (PRIMARY) | Compact Snapshot + Batch | `skylight-cli snapshot-compact --pid X --semantic` |
  | **CDP WebSocket** (PRIMARY) | Snapshot + Batch Execute | `Runtime.evaluate(...)` via ws://127.0.0.1:9999/... |
  | **Chrome Recipe** | Chrome Launch | Recipe REGELN 1-4 (Profile 901 + Cookie-Injection) |
  | **cua-driver** (LEGACY) | Popups/Sheets ONLY | `cua-driver call {method} {params}` |
  | **macos-ax-cli** | System-Scan (NUR Finden!) | `elements --pid X` |
  
  ## VERBOTEN (BANNED)
  
  - CDP `Accessibility.queryAXTree` / `getContentQuads` (für Navigation)
  - `cdp_click.py` Modul (CDP+AX Trinity ist obsolet)
  - `skylight-cli click --element-index` (Index instabil!)
  - `webauto-nodriver` MCP (ABSOLUT VERBOTEN)
  - `pkill -f "Google Chrome"` (tötet private Sessions!)
  - Apple-Menüleiste klicken (depth < 5)
  
  ## ERLAUBT (CDP PRIMARY für Web-Content, CUA NUR für Popups/Sheets)
  
  ⚠️ **WARNUNG (2026-05-10): Chrome 9999 hat LEERE AX-Tree für Web-Content!**
  CUA funktioniert NUR für native macOS Popups/Sheets, NICHT für Browser-Web-Content.
  Für Survey-Interaktion: CDP JS ist PRIMARY, nicht CUA!
  
  | Kontext | Tool | Befehl |
  |---------|------|--------|
  | Browser-Web-Content | **CDP WebSocket** | `Runtime.evaluate(...)` |
  | Survey-Modal | **CDP window.open interception** | `_click_modal_button_cdp()` |
  | Popup/Sheet | cua-driver | `call click {pid, wid, index}` |
  | Text eingeben (Popup) | cua-driver | `call set_value {pid, wid, index, value}` |
  | Fenster finden | cua-driver | `call list_windows` |
  | Chrome starten | Profil 901 Kopie | Recipe in REGELN 1-4 |
  
  ## AUDIO CAPTURE MODULE (2026-05-04, NEU)
  
  ### Problem
  Survey-Seiten nutzen `<video>` mit `blob:` URLs für Audio-Fragen (Tiergeräusche erkennen).
  Blob-URLs können NICHT via fetch/XHR/FileReader extrahiert werden (CORS/Security).
  Auch MediaRecorder + captureStream scheitern an protected content (EME/MSE).
  
  ### Lösung: BlackHole + ffmpeg + NVIDIA Omni Audio Analysis
  
  ```
  +─────────────────────────────────────────────────────────────────────+
  | AUDIO CAPTURE PIPELINE                                               |
  |                                                                     |
  |  1. SwitchAudioSource -t output -s "BlackHole 2ch"                  |
  |     -> Chrome-Audio wird auf BlackHole geroutet                      |
  |                                                                     |
  |  2. ffmpeg -f avfoundation -i ":BlackHole 2ch" -t 6 /tmp/audio.wav |
  |     -> 6 Sekunden System-Audio aufnehmen                             |
  |                                                                     |
  |  3. SwitchAudioSource -t output -s "MacBook Pro-Lautsprecher"       |
  |     -> Audio zurück auf Lautsprecher                                 |
  |                                                                     |
  |  4. NVIDIA Omni Audio Analysis:                                     |
  |     POST /v1/chat/completions                                       |
  |     -> audio_url + Text-Prompt                                       |
  |     -> "What animal sound? Options: Elefant, Hahn, Hund, Katze"      |
  |     -> Answer: "Hahn" (Omni erkennt Tiergeräusche zuverlässig)       |
  +─────────────────────────────────────────────────────────────────────+
  ```
  
  ### Voraussetzungen
  | Tool | Install | Check |
  |------|---------|-------|
  | **BlackHole** | `brew install blackhole-2ch` | SIP muss deaktiviert! |
  | **ffmpeg** | `brew install ffmpeg` | `which ffmpeg` |
  | **SwitchAudioSource** | `brew install switchaudio-osx` | `which SwitchAudioSource` |
  | **NVIDIA API Key** | `export NVIDIA_API_KEY=nvapi-...` | |
  
  ### Audio Module CLI
  ```bash
  # Pipeline-Check
  python3 -m cli.modules.audio_capture --check
  
  # Audio aufnehmen + analysieren
  python3 -m cli.modules.audio_capture --capture --duration 6 --analyze
  ```
  
  ## CAPTCHA SOLVING (2026-05-03)
  
  ### Simple Text Captcha (NVIDIA reasoning)
  ```
  1. tmux new-session -d -s captcha
  2. tmux send-keys -t captcha "python3 /tmp/captcha_simple.py" C-m
  3. tmux send-keys -t captcha "ss" C-m       # Screenshot
  4. tmux send-keys -t captcha "nvidia" C-m    # NVIDIA Vision
  5. tmux send-keys -t captcha "answer TEXT" C-m  # Antwort
  6. tmux send-keys -t captcha "submit" C-m    # Submit
  ```
  
  ### GeeTest v4 (GeekedTest API)
  ```python
  from stealth_captcha import solve_captcha
  r = solve_captcha("geetest_v4", {"captcha_id":"...", "risk_type":"slide"})
  # -> Token erhalten!
  ```
  
  ### Lemin Puzzle Captcha (OpenCV + JS Drag)
  ```python
  from stealth_captcha.solvers.lemin_ultimate import solve_lemin
  solve_lemin()
  # -> Puzzle-Stück per JS dispatchEvent verschieben + Verify
  ```
  
  ### Survey Integration
  ```python
  from stealth_captcha.captcha_handler import handle_captcha_in_survey
  handle_captcha_in_survey(pid, page_url)
  # -> Automatische Captcha-Erkennung + Lösung
  ```
  
  ## SURVEY FLOW (2026-05-10, VERIFIZIERT)
  
  ### Kompletter Ablauf
  ```
  1. SCAN: CDP JS -> finde Tab MIT .survey-item (document.querySelectorAll)
  2. START: CDP JS -> clickSurvey('ID') → Dashboard öffnet Modal
  3. MODAL: CDP JS -> window.open interception + Target.createTarget → Survey-Tab öffnet sich
     ⚠️ CUA b.click() + CDP Input.dispatchMouseEvent = FAIL (Chrome Popup Blocker!)
     ✅ window.open interception (siehe §KRITISCH: "Umfrage starten" Problem)
  4. CONSENT: CDP JS -> Cookie "Alle akzeptieren" button.click()
  5. CAPTCHA: Fälle "ROBOT", Math, Dropdown → per CDP JS + NVIDIA Vision
  6. START: Survey öffnet sich in Tab → Provider identifizieren
  7. AUDIO-FRAGE: Audio Module -> BlackHole + ffmpeg + NVIDIA Omni
  8. ANTWORT: CDP JS -> Radio/Checkbox/Text per Provider-Methode + "Nächste"
  9. KOMPLETT: Survey schließt -> zurück zu heypiggy Dashboard → Balance erhöht
  ```

  ### KRITISCH: "Umfrage starten" Button — window.open interception (2026-05-09 DISCOVERED!)
  
  **PROBLEM (alle Methoden FAIL):**
  - `b.click()` → window.open() von Chrome Popup Blocker blockiert
  - `b.dispatchEvent(new MouseEvent('click'))` → gleicher Effekt
  - `CDP Input.dispatchMouseEvent(x, y)` → gleicher Effekt
  
  **LÖSUNG (GETESTET 2026-05-09):**
  1. window.open temporär überschreiben → URL capture
  2. openSurvey() aufrufen → window.open(url) wird abgefangen
  3. window.open wiederherstellen
  4. Target.createTarget(captured_url) → NEUER TAB öffnet sich (KEIN Popup Blocker!)
  
  **Code:** `survey-cli/tools/tool_open_survey.py` → `_handle_modal_with_cdp()` + `_click_modal_button_cdp()`

  ### Survey Provider
  | Provider | URL Pattern | Flow | Status |
  |----------|------------|------|--------|
  | Samplicio.us | `rx.samplicio.us/consent/` | Consent -> My-Take -> Disqual/Complete | ✅ |
  | Cint | `sw.cint.com/Session/` | Session → Fragen | ✅ |
  | Nfield/Kantar | `nfieldeu-interviewing.nfieldmr.com` | Welcome -> Audio/Video-Fragen | ✅ |
  | Purespectrum | `purespectrum.com` | Cookie + ROBOT captcha + Textarea | ✅ NEW 2026-05-09 |
  
  ### Wichtige Erkenntnisse
  1. **Multi-Tab Problem**\: heypiggy öffnet mehrere Dashboard-Tabs. Nur EINER hat Surveys. Scanne ALLE Tabs!
  2. **Survey In-Page**\: clickSurvey() öffnet den Survey im Dashboard (kein neuer Tab!). AX-Tree rescanen nach neuen Elementen!
  3. **Survey Modal**\: "Umfrage starten" Button nutzt window.open() → Popup Blocker → window.open interception nötig!
  4. **Blob-Audio**\: `<video>` mit blob: URL kann NICHT via JS extrahiert werden. BlackHole nötig.
  4. **Blob-Audio**\: `<video>` mit blob: URL kann NICHT via JS extrahiert werden. BlackHole nötig.
  5. **Disqualifikation**\: 0.02€ Compensation bei Abbruch. Level-Up bei erfolgreicher Teilnahme.
  
  ## FLOW-OPTIMIZER
  
  Wenn ein Flow **10x hintereinander** erfolgreich läuft -> Promotion zu Production.
  
  ```
  flows/candidates/   -> Flows in Lern-Phase (brauchen noch Vision)
  flows/production/   -> 10x bestanden -> NUR CLI, KEIN Vision!
  flows/history/      -> JSONL pro Flow (letzte 100 executions)
  ```
  
  ## VERBOTEN (BANNED)
  
  - `skylight-cli click --pid X --element-index Y` für Web-Content (Index instabil!)
  - skylight-cli MCP (ABSOLUT BANNED für Navigation/Klicks)
  - `recovery_mode: true`, `omni_fallback: llama`
  - Mausbewegung, Koordinaten raten
  - **`pkill -f "heypiggy-bot"`** -> killt ALLE Chrome (USER + BOT!)
  - **`killall Google Chrome`** -> killt ALLE Chrome-Instanzen!
  - **Hardcoded PIDs** (71104, 70293, etc.) -> PIDs sind dynamisch!
  - Commands-Verzeichnis: `/commands/banned-*.md` -> alle verbotenen Commands dokumentiert
  
  ## ERLAUBT
  
  | Kontext | Tool | Befehl |
  |---------|------|--------|
  | Chrome Kill | `SessionManager.close_all()` | `sm.close_all()` -> killt BOT + leert Registry |
  | Chrome Kill | Python Script | `/commands/kill-bot-chrome.md` |
  | BOT PIDs finden | Python Script | `/commands/find-bot-pids.md` |
  | Chrome Launch | Profil 901 Kopie | Recipe in REGELN 1-4 (ganz oben) |
  | Web-Content | **cua-driver** | `call click/set_value/press_key` |
  | Popup-Fenster | `cua-driver` | `call click '{"pid":X,"window_id":W,"element_index":Y}'` |
  | System-Scan | `macos-ax-cli` | `find "Text"`, `windows list` |
  | Audio Capture | `audio_capture.py` | `python3 -m cli.modules.audio_capture --capture --analyze` |
  
  ##  GOLDENE REGEL: NACH JEDER AKTION STATUS PRÜFEN (2026-05-04)
  **NIE blind nach einer Aktion weitermachen!** Immer prüfen:
  1. `list_windows` -> hat sich die WID geändert?
  2. `get_window_state` -> sind neue Elemente sichtbar?
  3. `document.body.innerText` -> hat sich der Seiteninhalt geändert?
  4. Button DISABLED oder ENABLED?
  
  ##  KORREKTER ABLAUF PRO SURVEY-SCHRITT
  ```
  1. list_windows    -> WID finden (niemals hartcodieren!)
  2. get_window_state -> AX-Tree laden
  3. depth > 5 FILTER -> NUR Web-Content Elemente
  4. Element finden   -> per Label + Rolle im Tree
  5. click/set_value  -> Aktion ausführen
  6. list_windows    -> WID noch gültig?
  7. get_window_state -> Hat sich was geändert?
  8. Weiter mit 2.    -> oder fertig
  ```
  
  ## ️ VERIFY-BOX REGEL (2026-05-04)
  Jeder Klick/jede Texteingabe SOLLTE `"verify": true` enthalten.
  Der Daemon prüft SOFORT ob der Zustand wirklich erreicht wurde.
  Ohne Verify: Agent wird belogen (cua-driver sagt "Performed" obwohl nichts passierte).
  
  ## ️ VERIFY-BOX: Nie wieder falsches `success: true` (2026-05-04)
  
  ### Problem
  Der Agent klickt "Männlich". CUA sagt `Performed`. Agent glaubt es. Aber Radio-Button wurde NICHT selektiert - JS-Event-Listener hat nicht gefeuert.
  
  ### Lösung: Verify-Box
  Der Agent hängt EIN Wort an seinen Befehl: `"verify": true`
  
  ```bash
  stealth-exec cua-touch --action click --label "Männlich" --json-params '{"verify": true}'
  ```
  
  ### Was passiert dann
  1. CUA-Klick auf "Männlich" ausführen
  2. AX-Tree NEU scannen (gleiches Fenster)
  3. Element suchen und ZUSTAND prüfen:
     - AXRadioButton -> `selected=true`?
     - AXCheckBox -> `checked=true`?
     - AXTextField -> enthält Text?
  4. NUR WENN ZUSTAND ERREICHT: `success: true`
  
  ### Ohne Verify
  ```
   Agent wird belogen - CUA sagt "Performed", aber nichts passiert
   Agent macht 10 Schritte blind weiter
   Survey disqualifiziert, 30min verschwendet
  ```
  
  ### Mit Verify
  ```
   Agent kriegt `success: false` + Fehlermeldung
   Agent kann SOFORT reagieren (Retry/Fallback)
   Kein Blindflug mehr
  ```
  
  ---
  
  ##  COMPILED FLOW ENGINE (2026-05-04)
  
  **Pattern: Agent denkt NICHT mehr. Er macht exakt EINEN Tool-Call.**
  
  ### Das Problem
  Agenten machen 10-50 individuelle Schritte, vergessen Dinge, kombinieren Tools frei -> Fehler, Token-Verschwendung, Instabilität.
  
  ### Die Lösung: FCTES - Flow Compilation & Tool Enforcement System
  
  ```
  LEARNING (unsicher) -> 10x Success -> COMPILE -> TOOL REGISTRY -> DISPATCHER (nur noch 1 Call)
  ```
  
  ### Architektur
  
  **HINWEIS: `app/` wurde INTENTIONALLY GELÖSCHT (2026-05-08)**
  NEMO-Loop läuft via survey-cli/survey/*.py Module statt app/.
  
  ### Hard Enforcement Regeln
  
  ```
  ╔══════════════════════════════════════════════════════════════════╗
  ║  REGEL 1: Agent ist NUR ein Trigger                              ║
  ║  ─────────────────────────────────────────────────────────────── ║
  ║   RICHTIG:  python run_survey.py                               ║
  ║   FALSCH:   Agent klickt Survey-Cards manuell                  ║
  ║   FALSCH:   Agent baut eigene CUA-Befehle                      ║
  ║   FALSCH:   Agent zerlegt Flow in Einzelschritte               ║
  ╚══════════════════════════════════════════════════════════════════╝
  
  ╔══════════════════════════════════════════════════════════════════╗
  ║  REGEL 2: KEINE Freiheit bei Tool-Wahl                           ║
  ║  ─────────────────────────────────────────────────────────────── ║
  ║   RICHTIG:  dispatch("survey_heypiggy_v1746400000", payload)  ║
  ║   FALSCH:   Agent entscheidet "nehme ich skylight oder cua?"   ║
  ║   FALSCH:   Agent kombiniert mehrere Tools                     ║
  ╚══════════════════════════════════════════════════════════════════╝
  
  ╔══════════════════════════════════════════════════════════════════╗
  ║  REGEL 3: Freeze nach 10 Erfolgen                                ║
  ║  ─────────────────────────────────────────────────────────────── ║
  ║  tracker.record("survey_heypiggy")  # nach jedem OK-Run          ║
  ║  -> wenn count >= 10: compiler.compile() -> neues Tool             ║
  ║  -> ab jetzt NUR noch das frozen Tool                             ║
  ╚══════════════════════════════════════════════════════════════════╝
  ```
  
  ### Tool Registration (opencode.json)
  
  ```json
  {
    "tools": [
      {
        "name": "survey_heypiggy_v1746400000",
        "description": "Frozen deterministic survey flow: CUA-only, 15 Frage-Runs, Forward-Button-Loop",
        "strict": true,
        "input_schema": {
          "type": "object",
          "properties": {
            "radio_hints": {"type": "array", "items": {"type": "string"}},
            "checkbox_hints": {"type": "array", "items": {"type": "string"}},
            "textarea_value": {"type": "string"}
          },
          "additionalProperties": true
        },
        "frozen_at": 1746400000,
        "source": "FCTES-compiler"
      }
    ]
  }
  ```
  
  ### Single Entry Point (Was der Agent NUR tun darf)
  
  ```bash
  #  EINZIGER Befehl für Survey-Loop:
  python3 run_survey.py
  
#  Oder intern:
  from survey_cli.survey.runner import SurveyRunner, RunnerConfig
  config = RunnerConfig(cdp_port=9999, max_surveys=10)
  runner = SurveyRunner(config)
  result = runner.run_survey(survey_id="66950684")
  ```

  ### Neue Flows hinzufügen (Learning Phase)

  1. Flow in `survey-cli/survey/` als Python-Modul bauen (mit `execute(payload)` Funktion)
  2. Testen bis 10× erfolgreich
  3. `compiler.compile("flow_name")` ->자동isch:
     - Copy nach `survey-cli/survey/compiled/flow_v{TIMESTAMP}.py`
     - `registry.save()` -> Source of Truth
     - `tool_builder.register()` -> opencode.json
     - `dispatcher.dispatch()` -> ab jetzt erlaubt
  
  ### Dashboard-Survey starten (Persona aus Profil-System)
  
  **NIE Alter hartcodieren!** Das Alter wird aus `date_of_birth` im Profil berechnet.
  Das Profil-System: Persona-Daten in `survey-cli/profiles/` oder in session-DB.
  
  ```python
  #  FALSCH: Hartcodiertes Alter führt zu Disqualifikation!
  # PAYLOAD = {"age": 42}  # -< DAS WAR DER FEHLER (2026-05-05)
  # Persona: Berlin, Kurfürstenstraße 124, 10785, männlich, 42,
  
  #  RICHTIG: Profil laden, Alter aus date_of_birth berechnen
  from survey_cli.survey.profile_loader import ProfileLoader
  persona = ProfileLoader.load_profile()
  # -> date_of_birth="1993-11-13" -> age=32 (berechnet, IMMER aktuell)
  answer = resolve_answer(persona, "What is your age?", ["Under 16", "16-25", "26-39", "40+"])
  # -> matched_option="26-39" (32 fällt in dieses Bracket)
  ```
  
  **Aktuelles Profil**\: Jeremy Schulze, geb. 13.11.1993 (32 Jahre), Berlin, männlich, Angestellter, Meister, 2-Personen-Haushalt
  
  ---
  
  ##  KRITISCHES PROBLEM: Chrome CDP WebSocket Block (2026-05-04)
  
  ### Das Problem
  Chrome blockiert eingehende CDP WebSocket Verbindungen:
  ```
  WebSocketBadStatusException: Handshake status 403 Forbidden
  Rejected an incoming WebSocket connection from the http://localhost:XXXXX origin.
  Use --remote-allow-origins="*" to allow connections from this origin.
  ```
  
  ### Lösung
  Chrome MUSS mit `--remote-allow-origins="*"` gestartet werden:
  ```bash
  # Recipe: Profil 901 kopieren + Chrome 9999 starten + 7 HeyPiggy-Cookies injectieren
  # → Siehe REGELN 1-4 GANZ OBEN
  ```
  
  **ABER**\: Selbst mit korrekten Flags kann der Origin-Check noch aktiv sein.
  Dann: Chrome neu starten mit `--disable-web-security` testen.
  
  ### AX-Tree leer? Checkliste
  Wenn `cua-driver call get_window_state` **0 Children** zurückgibt:
  1. **Accessibility prüfen**\: System Settings -> Accessibility -> Screen bei Bedarf AN
  2. **Chrome Accessibility Flag**\: Chrome MUSS mit `--force-renderer-accessibility` gestartet werden. playstealth setzt dies NICHT (DESHALB BANNED!).
  3. **Window wählen**\: Nicht WID 0 (Menüleiste), sondern WID mit `height > 100` und `depth > 5`
  4. **Page laden**\: Seite muss vollständig geladen sein (5s warten)
  5. **CUA-Daemon**\: `cua-driver serve` muss als Daemon laufen
  
  ### Fallback wenn CUA komplett leer ist
  ```bash
  # macOS System-Info checken
  python3 -c "
  import subprocess
  result = subprocess.run(['system_profiler', 'SPAccessibilityDataType', '-json'], 
      capture_output=True, text=True)
  import json
  data = json.loads(result.stdout)
  print('AX Enabled:', data.get('spAccessibilityDataType', {}).get('AXEnhancedAccessibility', '?'))
  "
  ```
  
  ### Dokumentierte Symptome
  | Symptom | Ursache | Fix |
  |---------|---------|-----|
  | `get_window_state` -> 0 children | Accessibility nicht aktiv | System Settings -> Accessibility einschalten |
  | CDP WS 403 Forbidden | Chrome Origin check | Chrome mit `--remote-allow-origins="*"` starten |
  | Alle Windows height=0 | Falsches Window | WID mit height>100 suchen |
  | AXButton/AXLink nicht gefunden | depth<5 filter | Apple-Menüleiste hat depth 1-4 |
  
  
  ##  GOOGLE LOGIN - AUTORITATIVER FLOW (CUA-ONLY, 6 STEPS)
  
  **Datei:** `cli/modules/auto_google_login.py`  
  **Funktion:** `execute(pid=None, url="https://heypiggy.com/?page=dashboard")`  
  **Return:** `{"status": "ok", "pid": X, "wid": Y}` oder `{"status": "error", "reason": "..."}`  
  **Methode:** CUA-ONLY via `cua-driver` CLI - KEIN skylight, KEIN CDP, KEIN webauto
  
  ### Shell Commands (learning-by-doing, live dokumentiert 2026-05-05)
  
  ```bash
  # STEP 1: Chrome starten (Recipe aus REGELN 1-4)
  # Profil 901 kopieren + Chrome 9999 starten + 7 HeyPiggy-Cookies injectieren
  # -> HEYPIGGY Profil 901 Kopie, Port 9999
  
  # STEP 2: Windows finden
  cua-driver call list_windows | python3 -c "..."
  -> WID=DYNAMIC PID=DYNAMIC Title=HeyPiggy Dashboard
  
  # STEP 3: AX-Tree lesen -> Google Login-Symbol finden
  echo '{"pid": DYNAMIC_PID, "window_id": DYNAMIC_WID}' | cua-driver call get_window_state
  # HINWEIS: PIDs sind dynamisch! Aktuell: Profil 901 Kopie, Port 9999
  -> [N] AXLink (Google Login-Symbol) @(x,y,w,h)
  
  # STEP 4: Google Login klicken
  echo '{"pid": DYNAMIC_PID, "window_id": DYNAMIC_WID, "element_index": N}' | cua-driver call click
  ->  Performed AXPress on [N] AXLink
  -> wait 5s -> NEUE WID (Google OAuth)
  
  # STEP 5: Email eintragen + Weiter
  echo '{"pid": DYNAMIC_PID, "window_id": DYNAMIC_WID, "element_index": N, "value": "zukunftsorientierte.energie@gmail.com"}' | cua-driver call set_value
  -> [N] AXTextField (E-Mail oder Telefonnummer) @(x,y,w,h)
  echo '{"pid": DYNAMIC_PID, "window_id": DYNAMIC_WID, "element_index": N}' | cua-driver call click
  -> [N] AXButton "Weiter" @(x,y,w,h)
  -> wait 5s -> Keychain Auto-Fill -> "Jeremy Schulze"
  
  # STEP 6: Fortfahren + Final Weiter
  echo '{"pid": DYNAMIC_PID, "window_id": DYNAMIC_WID, "element_index": N}' | cua-driver call click
  -> [N] AXButton "Fortfahren" @(x,y,w,h)
  -> wait 5s
  echo '{"pid": DYNAMIC_PID, "window_id": DYNAMIC_WID, "element_index": N}' | cua-driver call click
  -> [N] AXButton "Weiter" @(x,y,w,h)
  -> wait 5s -> Login Complete! Dashboard eingeloggt!
  ```
  
  ### Ablauf (6 Steps, LIVE GETESTET 2026-05-05)
  
  **WICHTIG: NIEMALS hardcoded Indices nutzen! UI ändert sich!**
  **CUA hat auf Chrome 9999 leere AX-Tree für Web-Content → CDP JS bevorzugt!**
  
  | Step | Element | Suche (dynamisch) | Aktion |
  |------|---------|--------------------|--------|
  | 1 | Google Login-Symbol | `AXLink` mit text containing "Google" oder "Anmelden" | click |
  | 2 | Email-Feld | `AXTextField` mit placeholder "E-Mail" oder "Email" | set_value |
  | 2b | Weiter | `AXButton` mit text containing "Weiter" | click |
  | 3 | Fortfahren | `AXButton` mit text "Fortfahren" (Keychain Auto-Fill!) | click |
  | 4 | Weiter (Final) | `AXButton` mit text "Weiter" | click |
  
  **Methode:** `cua-driver call find_element_index` mit regex `\bWeiter\b` → dynamischer Index
  **Fallback:** CDP JS `document.querySelector('button')` → Koordinaten → `cua-driver call click at`
  
  ### Rückgabe
  - `{"status": "ok", "pid": X, "wid": Y}` wenn "abmelden"/"umfragen" im Dashboard sichtbar
  - `{"status": "error", "reason": "..."}` sonst
  
  ### Voraussetzung
  - Chrome muss LAUFEN auf Port 9999 (Profil 901 Kopie + Cookie-Injection)
  - cua-driver Daemon muss laufen (`cua-driver serve` als Daemon)
  
  ### Beispiel
  ```python
  from cli.modules.auto_google_login import execute as auto_google_login
  
  result = auto_google_login()
  if result.get("status") == "ok":
      print(f" Login OK: pid={result['pid']} wid={result['wid']}")
  else:
      print(f" Login failed: {result.get('reason')}")
  ```
  
  ### Keychain Auto-Fill Discovery (KRITISCH!)
  - Email eintragen -> "Weiter" -> Keychain füllt automatisch Credentials aus
  - "Jeremy Schulze" Konto vorausgewählt -> NUR "Fortfahren" klicken
  - KEIN Passwort-Feld wenn Keychain aktiv!
  
  ### BOT Chrome PIDs (NIEMALS USER Chrome beenden!)
  - Chrome 9999 Profil: /tmp/chrome-jeremy-heypiggy-9999
  - Chrome 9222 Profil: /Users/jeremy/Library/Application Support/Google Chrome (SIMONE, NICHT TOUCHEN!)
  
  ### BANNED (niemals verwenden)
  -  webauto-nodriver (ABSOLUT BANNED)
  -  pkill -f "heypiggy-bot" (killt ALLE Chrome!)
  -  Hardcoded PIDs
  -  devjerro@gmail.com (NUR zukunftsorientierte.energie@gmail.com)
  -  launch_parallel.py (verschlüsselte Cookies!)
  
  ### ERLAUBT
  -  skylight-cli snapshot-compact — PRIMARY für kompakte Snapshots
  -  skylight-cli batch — Batch-Aktionen ausführen
  -  CDP WebSocket Runtime.evaluate — direkte JS-Execution (PRIMARY für Snapshot + Batch)
  -  cua-driver — LEGACY ONLY, nur für Popups/Sheets
  
  ---
  
  ##  SURVEY-CLI - Standalone Binary (2026-05-06, NEU)
  
  **Separates survey automation from coding completely.**
  
  ### Was ist survey-cli?
  - **Standalone** Python-CLI (kein opencode cli nötig!)
  - **12 subcommands**\: login, scan, run, loop, watch, balance, status, doctor, kill, summary, opencode, profile
  - **NEMO Architecture**\: Compact Snapshot -> NIM Decision -> Batch Execute -> AutoDoc
  - **CDP WebSocket** für ALLE Browser-Interaktionen
  - **NVIDIA NIM Nemotron 3 Omni** für Entscheidungen
  - **Auto-Dokumentation** via append-only JSONL (KEIN LLM schreibt Docs!)
  - **OpenCode Bridge** für Coding-Delegation
  
  ### Architektur
  ```
  survey.py -> survey/*.py -> CDP WebSocket (port 9999) -> HeyPiggy Chrome
                              NVIDIA NIM API -> Nemotron 3 Omni
                              logs/*.jsonl -> Auto-Doc (append-only)
  ```
  
  ### Quick Start
  ```bash
  cd survey-cli/
  pip install -r requirements.txt
  ./survey.py login       # Einmalig Login
  ./survey.py watch       # Dauerschleife
  ```
  
  ### Wann survey-cli vs opencode cli?
  | scenario | tool |
  |----------|------|
  | Umfragen ausfüllen | `survey.py loop --max 10` |
  | Dashboard scannen | `survey.py scan` |
  | Coding-Aufgabe | `survey.py opencode "fix X"` |
  | System-Check | `survey.py doctor` |
  | Entwicklung | `opencode` (open-code cli) |
  
  ### GitHub
  - **Repo**\: https://github.com/SIN-CLIs/survey-cli
  - **Location**\: `survey-cli/` im stealth-runner workspace
  
  ### Skill Integration
  - **OpenCode Skill**\: `/survey-runner` - in `infra-sin-opencode-stack/skills/survey-runner/SKILL.md`
  - **Catalog**\: `infra-sin-opencode-stack/skills/catalog.json`
  - **Install**\: `infra-sin-opencode-stack/install.sh` via `sync_dir_additive skills/`
  - **Stealth Suite**\: 23+ Repos - `stealth-runner/`, `stealth-core/`, `stealth-session/`, `stealth-guardian/`, `stealth-memory/`, `stealth-captcha/`, `stealth-skills/`, `playstealth-cli/`, `skylight-cli/`, `cua-touch/`, `macos-ax-cli/`

---

## DAEMON WAY — State-of-the-Art Architektur-Prinzip (2026-05-09)

**TOKEN-KOSTEN SIND LÄCHERLICH GÜNSTIG.** 1€ Token = 100× billiger als 1h Bug-Suche. Voller Kontext rein, fertiges Ergebnis raus. Keine Sparsamkeit.

---

### §1 — SINGLE SOURCE OF TRUTH: AGENTS.MD

**Regel: ALLES in AGENTS.md. NICHTS verstecken.**

```
Warum AGENTS.md?
├── Modell hat Bauvplan permanent im Attention-Mechanism
├── Kein "Ich dachte die Tabelle sollte so aussehen"
├── Definition steht DIREKT über dem Code den es schreibt
└── Bei jedem Prompt wird Kontext neu gewichtet = keine Context Drift
```

**Struktur:**
1. Projekt-Vision (harte Fakten)
2. Tech Stack & Constraints (keine Alternativen erlauben)
3. Datenmodell (DB-Schema rein!)
4. Business Logic Blueprints ("Wenn X → Y in Tabelle Z")
5. Definition of Done (wann ist Task FERTIG für die KI?)

---

### §2 — DAEMON WAY: LERNENDES SYSTEM (LEARNING-BY-DOING)

**Der Daemon lernt wie ein Mensch: Versuchen → Scheitern → Löschen → Nächstes probieren.**

```
DAEMON LOOP (unbegrenzt):
┌─────────────────────────────────────────────────────────┐
│  1. SCAN    → finde Survey auf Dashboard               │
│  2. PROBIEREN → öffne mit aktuellem Flow               │
│  3. ERFOLG  → ✅ +0.XX€ → Flow VERIFIED speichern     │
│  4. FEHLER  → ❌ Disqualifikation/Error                │
│  5. ANALYSIEREN → WARUM gescheitert?                  │
│  6. FLOW ANPASSEN → nächsten Survey probieren         │
│  7. WIEDERHOLEN                                        │
└─────────────────────────────────────────────────────────┘
```

**Survey-Typen lernen (fortlaufend):**

| Phase | Was | Wie |
|-------|-----|-----|
| DISCOVER | Neuen Survey-Typ finden | Dashboard scannen, Tab öffnen, URL merken |
| CLASSIFY | Provider identifizieren | URL-Pattern, JS-Struktur, DOM-Form |
| MAP | Fragetypen clustern | Consent, Radio, Matrix, Text, NPS, Multi, Dropdown |
| CODIFY | Flow als Code | survey-cli/survey/providers/*.py |
| FREEZE | Flow einfrieren | 10× Erfolg → VERIFIED → Read-Only |
| EXPOSE | Als FastAPI Endpoint | survey_tools.py Wrapper |

**Bekannte Survey-Provider (lernend erfasst):**
- `surveyrouter` — heypiggy intern (modal flow)
- `emea.focusvision.com` — 35 pages, audio Fragen
- `enter.ipsosinteractive.com` — TolunaStart, cf-radio-answer
- `rx.samplicio.us` — Consent → My-Take
- `s.cint.com` — Fingerprint → Nfield/Kantar
- `nfieldeu-interviewing.nfieldmr.com` — Audio/Video Fragen

---

### §3 — DELETE WRONG IMMEDIATELY (PERMANENT)

**Regel: Sobald ein Command/Code FEHLERHAFT ist → SOFORT LÖSCHEN. Keine "vielleicht noch nützlich".**

```
VERBOTENE DATEIEN (SOFORT ENTFERNEN):
├── src/stealth_survey/           → INTENTIONALLY DELETED
├── app/                          → INTENTIONALLY DELETED
├── survey-cli/survey/agents/     → INTENTIONALLY DELETED
├── launch_parallel.py            → verschlüsselte Cookies, FALSCH
├── decrypt_cookies.py            → v10 only, Chrome 147+ = kaputt
├── Alle *.py die pkill -f "Google Chrome" nutzen
└── Alle *.py die hardcoded PIDs haben
```

**BANNED Commands → SOFORT löschen:**
- `playstealth launch` → BANNED, Profil 902, Port 9224, keine Cookie-Injection
- `pkill -f "Google Chrome"` → tötet USER Chrome
- `killall Google Chrome` → tötet ALLE Chrome-Instanzen
- `webauto-nodriver` → ABSOLUT BANNED
- Hardcoded PIDs (71104, 70293, etc.) → PIDs sind dynamisch!

**Nach jedem LÖSCHEN:**
1. AGENTS.md updaten (neue LÜGE = neue Regel)
2. `learn.md` + `anti-learn.md` füttern
3. Issue erstellen wenn Fehler kritisch

---

### §4 — ONCE VERIFIED = READ-ONLY (UNVERBRÜCHLICH)

**Regel: Sobald ein Command/Endpoint/Flow VERIFIED ist → NIEMALS wieder anfassen.**

```
VERIFIED = READ-ONLY (chmod 444 auf .md Dateien):
├── /commands/<provider>/<name>.md      → ✅ VERIFIED = Read-Only
├── survey-cli/tools/tool_*.py          → frozen=True
├── FastAPI Endpoint in survey_tools.py → nicht mehr ändern
└── survey-cli/survey/providers/*.py    → frozen nach 10× Erfolg
```

**Ausnahme:** Wenn ein FIX notwendig ist → NEUE Datei erstellen, alte als `DEPRECATED` markieren.

**Warum?**
- Nächster Agent zerstört alles wieder (ADHS-KI Problem)
- Verified = 10× getestet, funktioniert
- Jede Änderung = Risiko dass es bricht

---

### §5 — FEED AGENTS.MD FOREVER (LEARNING LOOP)

**Regel: Jede neue Erkenntnis → AGENTS.MD. Sofort. Nicht warten.**

```
FEEDBACK LOOP (nach jedem Survey):
┌─────────────────────────────────────────────────────────┐
│  1. Survey beendet                                       │
│  2. ERFOLG oder FEHLER?                                 │
│  3. WENN FEHLER:                                        │
│     ├── Root-Cause analysieren                          │
│     ├── anti-learn.md updaten                           │
│     └── AGENTS.md: "NIEMALS [falscher weg]" hinzufügen  │
│  4. WENN ERFOLG:                                        │
│     ├── learn.md updaten                                │
│     ├── commands/<provider>.md VERIFIED maken           │
│     └── AGENTS.md: Flow dokumentieren                   │
│  5. WENN NEUE PROVIDER/SURVEY-TYP:                      │
│     ├── Survey-Typ clustern                            │
│     ├── commands/surveys/<name>.md erstellen           │
│     └── AGENTS.md: "Provider X flowt mit Methode Y"    │
└─────────────────────────────────────────────────────────┘
```

**Was WIRKLICH rein muss in AGENTS.md (Beispiele):**
- ✅ "TolunaStart nutzt `cf-radio-answer` class, NICHT input[type=radio]"
- ✅ "Nfield/Kantar hat BLOB-Audio-Fragen → BlackHole nötig"
- ✅ "Ipsos öffnet Survey in NEUEM TAB, nicht modal"
- ✅ "SurveyRouter nutzt onclick=\"clickSurvey(ID)\" im DIV"
- ❌ NICHT: "Das ist interessant" / "Vielleicht funktioniert das"

---

### §6 — FASTFAPI ALS DAEMON-HIRN

**FastAPI (Port 8889) ist die ZENTRALE STEUERUNG für alle Survey-Operationen.**

```
FASTAPI ENDPOINTS (Survey-Tools):
├── POST /survey/open      → tool_open_survey.py Wrapper
├── POST /survey/close     → close_survey_tab Wrapper
├── POST /survey/fill      → SurveyFiller.decide_actions() Wrapper
├── POST /survey/rate      → rate_survey() Wrapper
└── POST /survey/click     → tool_click.py Wrapper (survey_actions.py)

FASTAPI ENDPOINTS (Dashboard):
├── POST /dashboard/scan   → scan_dashboard() → 12 surveys
├── POST /dashboard/balance → balance_eur = 2.60€
└── GET  /docs             → Swagger UI

DAEMON nutzt NUR FastAPI, NIEMALS direkte CDP/cua-driver Calls:
→ Daemon fragt FastAPI → FastAPI callt survey-cli/tools → Ergebnis zurück
```

**Warum FastAPI?**
- Agent/Bot/Daemon ruft EINEN Endpoint, nicht 20 einzelne Commands
- Keine Context Drift weil alles in AGENTS.md + FastAPI definiert
- Wiederverwendbar: same Endpoint für Agent + Daemon + CLI

---

### §7 — COMMAND VERZEICHNIS (READ-ONLY NACH VERIFY)

**`/commands/` ist die permanente Wissensbasis. VERIFIED = chmod 444.**

```
/commands/
├── cmd-rules.md              ← Regeln (darf geändert werden)
├── survey-router.md          ← ✅ VERIFIED (chmod 444)
├── tolunastart-survey.md     ← ✅ VERIFIED (chmod 444)
├── ipsos-survey.md           ← ✅ VERIFIED (chmod 444)
├── kill-bot-chrome.md        ← ✅ VERIFIED (chmod 444)
├── playstealth-launch.md     ← ❌ BANNED (NICHT löschen, als Warnung!)
└── banned.md                 ← zentrale Verbotsliste
```

**Datei-Template für VERIFIED Commands:**
```markdown
# <name> — <beschreibung>

## Status
✅ VERIFIED — 2026-05-09, Chrome 9999, PID=<dynamisch> WID=<dynamisch>

## Command (FUNKTIONIERT)
```bash
# Exakter Befehl - NICHT ÄNDERN!
```

## Verification
```bash
# Output zeigt ERFOLG
```

## Wann verwenden?
- Kontext 1
- Kontext 2

## History
- 2026-05-09: Erstellt (10× Erfolg)
```

---

### §8 — SURVEY TYP KATALOG (LEARNING-BY-DOING)

**Alle jemals entdeckten Survey-Typen in AGENTS.md dokumentieren.**

| Survey-Typ | Provider | Erkennung | Flow | Status |
|------------|----------|-----------|------|--------|
| Consent | Samplicio, Ipsos | "Zustimmen und fortfahren" | CUA click index | ✅ VERIFIED |
| Single Choice Radio | Alle | `input[type=radio]` | CDP click | ✅ VERIFIED |
| Custom Radio DIV | TolunaStart | `class="cf-radio-answer"` | CDP JS click | ✅ VERIFIED |
| Matrix | Kantar | Grid mit Radio-Buttons | CUA loop | 🔄 LEARNING |
| Text Input | Alle | `input[type=text]` | CUA set_value | ✅ VERIFIED |
| Textarea | Alle | `<textarea>` | CUA set_value | ✅ VERIFIED |
| NPS Rating | SurveyRouter | Skala 0-10 | CDP click | 🔄 LEARNING |
| Binary Matrix | Kantar | Ja/Nein Grid | CUA loop | 🔄 LEARNING |
| Multi-Select | Cint | Checkboxen | CDP click multiple | 🔄 LEARNING |
| Dropdown | Qualtrics | `<select>` | CUA select | 🔄 LEARNING |
| Blob Audio | Nfield | `<video src="blob:">` | BlackHole + ffmpeg | 🔄 LEARNING |
| Welcome/Submit | Alle | "Vielen Dank" | Tab close | ✅ VERIFIED |

**WENN NEUER TYP entdeckt:**
1. URL + Screenshot speichern
2. Provider identifizieren
3. Flow clustern (Cluster = gleiche Bedienung)
4. `/commands/surveys/<provider>-<typ>.md` erstellen
5. AGENTS.md Section "Survey Typ Katalog" updaten

---

### §9 — DEFINITION OF DONE (KI weiss wann fertig)

**Agent/Daemon hört AUF wenn:**

```
SURVEY:
├── Tab hat sich geschlossen (SurveyRouter return)
├── balance_eur hat sich erhöht
├── oder: Disqualifikation erkannt (0.02€)
└── → Nächster Survey scannen

COMMAND:
├── Shell Output zeigt ERFOLG (kein Error)
├── verify: true bestätigt (Zustand erreicht)
└── → Command als VERIFIED in /commands/ speichern

BUG FIX:
├── Alle betroffenen Files fixed (grep prüfen)
├── AGENTS.md aktualisiert (Lüge = neue Regel)
├── Issue erstellt mit Root-Cause
└── → NIEMALS mehr denselben Fehler machen
```

---

### §10 — ANTI-PATTERN (NIEMALS MACHEN)

```
❌ Monolithische Endpoints (POST /survey/run-all)
   → Stattdessen: einzelne Endpoints, wiederverwendbar

❌ Hardcoded PIDs / Ports
   → Stattdessen: dynamisch scannen, Config aus AGENTS.md

❌ Falsches speichern statt löschen
   → Stattdessen: DELETE IMMEDIATELY bei Fehler

❌ Context sparen wegen Token-Kosten
   → Stattdessen: voller Kontext = 100× billiger

❌ "Ich weiss wie es funktioniert"
   → Stattdessen: RECHERCHIEREN ist PFLICHT

❌ Alte verified Files anfassen
   → Stattdessen: NEUE Datei, alte als DEPRECATED
```
