---
content: |
  # AGENTS.md - Stealth-Runner NEXT-GEN (2026-05-06)

  ## 🟢 KANONISCHE ARCHITEKTUR (2026-05-11) — UNIVERSAL CDP SCANNER + ACTUATOR

  > Diese Sektion ist die EINZIGE gültige Beschreibung der Element-Such-,
  > Klick-, Fill- und Captcha-Pipeline. Alle vorherigen Beschreibungen
  > (CDP+AX Trinity, CUA-ONLY Trinity, NEMO Compact Snapshot, skylight-cli
  > snapshot-compact, ELEMENT_EXTRACTOR_JS) sind LEGACY und dürfen nicht
  > mehr in neuen Code-Pfaden referenziert werden.

  ### Worum es geht
  Ein Agent darf KEIN Element der Webseite übersehen — egal ob in iframes,
  Shadow-DOM, Custom-Elements, Web-Components, Angular-CDK-Overlays oder
  Cross-Origin-Frames. Und er darf KEINEN Klick als Erfolg melden, der im
  DOM nichts geändert hat. Beides war strukturell unmöglich mit der alten
  Scan-/Klick-Infrastruktur und ist Ursache aller wiederkehrenden Fehler
  (Issue #24 Anti-stuck-Loop, Issue #25 zero results, Issue #26 stuck on
  language page, Issue #27 completion not detected).

  ### Die 4 kanonischen Module
  ```
  survey-cli/survey/cdp_universal.py   → Universal Scanner (AX-Tree + DOM pierce + Frames)
  survey-cli/survey/cdp_actuator.py    → Echter Maus-Klick + Pflicht-Verify
  survey-cli/survey/captcha_router.py  → Captcha-Detection + Solver-Routing
  agent-toolbox/api/endpoints/universal.py → FastAPI v2-Endpoints (kanonischer Pfad)
  ```
  Jedes Modul hat eine FETTE Inline-Doku am Anfang. Wer diese Docstrings
  nicht gelesen hat, darf den Code nicht anfassen.

  ### Pipeline-Diagramm (pro Tab pro Tick)
  ```
  CDPConnection(ws_url)
        │
        ▼
  cdp_universal.scan(cdp) ──► ScanResult{elements[], captcha_frames[]}
        │                              │
        │                              └──► captcha_router.detect(scan)
        │                                          │
        │                                          ▼
        │                                  CaptchaDetection|None
        │                                          │
        │                                          ▼
        │                                  captcha_router.solve(det) ──► CaptchaResult
        ▼
  LangGraph think_node  (entscheidet welches stable_id geklickt wird)
        │
        ▼
  Actuator(cdp).click(stable_id)
        │
        ▼
  ActionResult{success, before_hash, after_hash, new_url}
        │
        ▼  (wenn success=False → think_node mit Hint "no_dom_change" erneut aufrufen)
  ```

  ### Was sich GEÄNDERT hat (Diff zur alten Welt)
  | Vorher (LEGACY)                                 | Jetzt (KANONISCH)                                   |
  |-------------------------------------------------|-----------------------------------------------------|
  | snapshot.py::ELEMENT_EXTRACTOR_JS (handgerollt) | cdp_universal.scan() via Accessibility.getFullAXTree |
  | walkShadows(depth>5) → Shadow-DOM ab Level 6 verloren | DOM.getFlattenedDocument(pierce=True) → ALLE Levels |
  | iframes nur GEZÄHLT, nie betreten               | Page.getFrameTree + AX-Tree pierced cross-frame     |
  | Modal-Detection per Viewport-Center             | Modale sind einfach AX-Knoten — kein Sonderfall     |
  | @e0 / @e1 Refs (Y-Sortierung instabil)          | stable_id = sha1(frame_id + backend_node_id) STABIL  |
  | el.click() / .checked = true → von React ignoriert | Input.dispatchMouseEvent → echter Maus-Klick         |
  | Klick ohne Verify → "Performed" = Halluzination | Pflicht-Verify via DOM-Hash-Diff vor/nach Aktion    |
  | Captcha-Sniffing im allgemeinen Scanner          | Eigener captcha_router mit iframe-URL-Detection     |
  | 5 parallele Klick-Layer (cua-driver, skylight,  | EIN Pfad: Actuator → CDP Input.dispatchMouseEvent   |
  |  macos-ax, BatchExecutor, raw JS)               |                                                     |

  ### FastAPI Tool-Registry — kanonische Endpoints (v2)
  Diese Endpoints sind die EINZIGEN, die LangGraph-Tools ab sofort aufrufen
  dürfen. Alte /survey/click, /survey/click-angular, /survey/fill-input,
  /survey/snapshot bleiben backward-compat, aber neue Tools MÜSSEN gegen
  /v2/* programmieren.
  ```
  POST /v2/scan
    → ScanResult{url, title, frame_count, element_count,
                 elements:[{stable_id, role, name, value, tag, state, bbox,
                            attrs, frame_url}],
                 captcha_frames:[{frame_id, url}]}

  POST /v2/click           body: {stable_id, cdp_port=9999, url_contains=""}
    → ClickResult{success, reason, before_hash, after_hash, new_url, elapsed_ms}
    reason ∈ {ok, navigated, no_dom_change, element_not_visible,
              unknown_stable_id, scroll_failed, dispatch_failed}

  POST /v2/fill            body: {stable_id, value, clear=True, ...}
    → FillResult{success, reason, elapsed_ms, typed}

  POST /v2/press_key       body: {key, modifiers=0, ...}
  POST /v2/captcha/detect  body: {cdp_port, url_contains}
    → {found, captcha_type, frame_id, frame_url, dom_hint}
  POST /v2/captcha/solve   body: {cdp_port, url_contains}
    → {solved, captcha_type, token, reason, elapsed_ms}
  ```

  ### LangGraph-Knoten-Verhalten (Pflicht)
  1. `scan_node`        ruft `/v2/scan`  → speichert `elements`, `captcha_frames` im State.
  2. `captcha_node`     wenn `captcha_frames` nicht leer ODER vorheriger Klick `no_dom_change`
                        → ruft `/v2/captcha/solve`. Bei `solved=False, reason='no_solver_for_type'`
                        → Eskalation (2captcha-Fallback oder Manual-Mode).
  3. `think_node`       LLM bekommt `elements[]` flat. Entscheidet ein einzelnes `stable_id`
                        plus Aktionstyp. NIEMALS Index, NIEMALS CSS-Selektor.
  4. `act_node`         ruft `/v2/click` oder `/v2/fill`.
                        Wenn `success=False` mit `reason='no_dom_change'`
                        → `scan_node` neu, `think_node` mit Hint "letzter Klick hat
                           DOM nicht verändert, anderes Element wählen".
                        Wenn `success=False` mit `reason='unknown_stable_id'`
                        → `scan_node` neu (stable_id war veraltet), dann erneut.
                        NIEMALS bei `success=False` so tun, als wäre es success.
  5. `verify_node`      Nach Surveyabschluss: balance-Diff > 0 ODER Completion-Marker
                        in body.innerText. Sonst gilt die Survey als NICHT abgeschlossen,
                        unabhängig davon was der Page-Text behauptet.

  ### Was VERBOTEN ist (additiv zu REGEL 1)
  - KEIN `Runtime.evaluate` mit `el.click()` in neuen Tools.
  - KEIN `document.querySelectorAll(...)[idx].click()`.
  - KEIN `el.value = "..."` Setter.
  - KEIN provider-spezifischer Klick-Pfad in neuen Tools.
  - KEINE Action ohne Pflicht-Verify (no_dom_change MUSS als Fehler behandelt werden).
  - KEINE Y-Sort-Reihenfolge oder Index-basierte Element-Refs in neuen Tools.
  - KEIN Captcha-Sniffing im allgemeinen Scanner (gehört in `captcha_router`).

  ### Chrome-Flag-Pflicht
  Der Chrome-Startbefehl MUSS `--force-renderer-accessibility` enthalten.
  Ohne dieses Flag liefert `Accessibility.getFullAXTree` nur den Top-Frame
  und der Scanner verfehlt iframe-Content. Das Flag steht bereits im
  Recipe in REGEL 4 weiter unten — nicht entfernen!

  ### Wie Captcha-Solver erweitert werden (additiv)
  1. `stealth-captcha/solver/<typ>.py` anlegen mit Signatur
     `def solve(cdp, detection) -> CaptchaResult`.
  2. In `survey-cli/survey/captcha_router.py::_solver_for()` einen
     lazy-import-Branch hinzufügen.
  3. Bei iframe-Detection: Eintrag in `IFRAME_URL_TO_TYPE`.
     Bei DOM-Detection: neue `_check_<typ>` Funktion + Aufruf in
     `CaptchaRouter.detect()`.
  KEINE Änderungen am `cdp_universal.py` für neue Captchas.

  ### Wo der Klick wirklich entsteht (für Debugging)
  Wenn ein Klick "nicht ankommt", war es bisher meistens
  `el.click()` via Runtime.evaluate, das React/Angular ignorieren.
  Mit dem neuen Pfad geht jeder Klick als echtes OS-Maus-Event durch:
  ```
  Actuator.click(stable_id)
   ├─ DOM.scrollIntoViewIfNeeded(backendNodeId)
   ├─ DOM.getBoxModel(backendNodeId)          → frische Koordinaten
   ├─ _capture_dom_hash()                     → before_hash
   ├─ Input.dispatchMouseEvent(mouseMoved)
   ├─ Input.dispatchMouseEvent(mousePressed,  clickCount=1, button=left)
   ├─ time.sleep(0.05)                        → humanlike hold
   ├─ Input.dispatchMouseEvent(mouseReleased, clickCount=1, button=left)
   ├─ time.sleep(0.30)                        → SPA-Reaktion (zone.js etc.)
   ├─ _capture_dom_hash()                     → after_hash
   └─ if before_hash == after_hash and not navigated → success=False
  ```

  ### Migrationsregel
  - Neue Tools ab 2026-05-11 → AUSSCHLIESSLICH `/v2/*` benutzen.
  - Bestehende Tools (`tool_click.py`, `tool_click_angular.py`,
    `tool_fill_input.py`, `tool_snapshot.py`, `tool_solve_captcha.py`)
    behalten ihre Endpoints für Backward-Compat, werden aber
    schrittweise durch dünne Wrapper auf `/v2/*` ersetzt.
  - Wenn du als Agent zwischen v1 und v2 wählen kannst → IMMER v2.
  - Wenn ein v1-Endpoint dasselbe besser kann als v2 → das ist ein Bug
    in v2, melde ihn als Issue. Keine Workarounds in Tool-Code.

  ### NIM/LLM-Vertrag (ab 2026-05-11, stable_id-Schema)

  `survey/nim.py::NIMClient.decide(snapshot, profile)` erwartet jetzt:

  ```python
  snapshot = {
    "elements": [
        {"stable_id": "<id>", "role": "button|radio|textbox|...",
         "name": "<accessible name>", "value": "<current value>",
         "checked": bool},
        ...
    ],
    "avoid_stable_id": "<id of element that just produced no_dom_change>",
    "no_dom_change_count": int,
    "iteration": int,
    "provider": "qualtrics|purespectrum|...",
  }
  ```

  Antwort-Schema das das Modell produzieren muss:

  ```json
  {"actions": [
      {"stable_id": "<id from list>", "action": "click"},
      {"stable_id": "<id from list>", "action": "fill", "value": "<text>"},
      {"action": "wait"},
      {"action": "complete"}
  ]}
  ```

  - GENAU EINE Action pro Decide. Verify im execute_node prueft danach.
  - `action="submit"` ist abgeschafft — Continue-Buttons sind normale
    `click` mit stable_id.
  - `action="select"` ist abgeschafft — Radios/Checkboxen werden mit
    `click` auf den stable_id selektiert.
  - Wenn `avoid_stable_id` gesetzt ist: das Modell MUSS einen ANDEREN
    stable_id waehlen (Anti-Stuck-Loop, Issue #24).

  Backward-Compat: Wenn der Aufrufer noch `snapshot["refs"]` (alt) und
  KEINE `snapshot["elements"]` schickt, schaltet `build_survey_prompt()`
  automatisch in den LEGACY-Prompt mit `@eN`-Indizes zurueck. Wird
  entfernt sobald alle Tools migriert sind.

  ### Captcha-Adapter (survey/captcha_adapters.py)

  Sync/Async-Bruecke zwischen `captcha_router._solver_for()` und den
  Solvern in `stealth-captcha/`. Lookup-Reihenfolge:
    1. `survey.captcha_adapters.get_adapter(type)` (Vorrang, lokales Repo)
    2. `stealth_captcha.solver.<type>.solve` (Fallback fuer drop-in solver)

  Heute gebridged:
    - `angular_drag_drop` → sync, wrapped `solve_drag_puzzle_new(ws_url)`
    - `visual_text`       → async, asyncio.run + _SessionStub-Adapter
                            ueber sync CDPConnection
  Heute STUB (klare reason="solver_not_yet_bridged"):
    - `hcaptcha`, `recaptcha`, `turnstile`

  Neuer Captcha-Typ:
    1. Adapter-Funktion `<type>_solve(cdp, detection)` in captcha_adapters.py
    2. Eintrag in `ADAPTERS`-Dict
    3. Detector im captcha_router (IFRAME_URL_TO_TYPE oder DOM-Check)

  ### Graph-Verdrahtung (LangGraph-Knoten ab 2026-05-11)

  Der Survey-Graph hat jetzt FUENF Hauptknoten pro Iteration:

  ```
  ensure_chrome ──► open_survey ──► inject_cookies ──► read_balance_before
                                                                 │
                                                                 ▼
                            ┌──── snapshot ◄────────────┐
                            │       │                   │
                            │       ▼                   │
                            │   captcha  (NEU)          │
                            │       │                   │
                            │       ▼                   │
                            │    decide                 │
                            │       │                   │
                            │       ▼                   │
                            │   execute ───► detect_completion ──► (loop or end)
                            │                       │
                            └───────────────────────┘
                                          │
                                          ▼
                                  read_balance_after ──► done
  ```

  Knoten-Pflichten:

  - `snapshot_node`     ruft `cdp_universal.scan()`. Setzt
                        `state.universal_elements` und `state.captcha_frames`.
  - `captcha_node`      NEU. Setzt `captcha_solved_this_iteration`.
                        NO-OP wenn `captcha_frames` leer UND
                        `no_dom_change_count < 2`. Sonst:
                        `captcha_router.detect_and_solve()`.
  - `decide_node`       Setzt `state.decision = {action, stable_id, value?, …}`.
                        LLM-first, Heuristik-Fallback. Beachtet `avoid_id`
                        wenn letzter Klick `no_dom_change`.
  - `execute_node`      Fuehrt `state.decision` via `cdp_actuator.Actuator` aus.
                        Setzt `state.last_action_result`.
                        Inkrementiert `no_dom_change_count` bei
                        `reason='no_dom_change'`.
  - `detect_completion` Liest URL + body.innerText + balance-Diff.
                        Backward-Compat: nutzt `state.batch_result`
                        (parallel zu `last_action_result` gefuellt).

  Backward-Compat-Felder im State (NICHT in neuem Code verwenden):
  `state.snapshot_refs`, `state.nim_actions`, `state.batch_result`.
  Sie werden weiterhin gespiegelt, damit alte Tools nicht brechen.

  Banned-Patterns in Knoten:
  - KEIN direktes `Runtime.evaluate("el.click()")` mehr.
  - KEIN `document.querySelectorAll(...)[idx].click()`.
  - KEIN Captcha-Check in `decide_node` oder `execute_node`
    (gehoert in `captcha_node`).
  - KEIN Klick-Erfolg ohne `actuator.click()` Verify-Pfad.

  ### Inline-Dokumentations-Pflicht
  Alle vier kanonischen Module enthalten eine umfassende Inline-Doku als
  Modul-Docstring am Anfang der Datei (siehe `cdp_universal.py`,
  `cdp_actuator.py`, `captcha_router.py`, `universal.py`). Diese Docstrings
  sind die Wahrheit. AGENTS.md fasst sie nur zusammen. Bei Widerspruch
  zwischen Docstring und AGENTS.md → Docstring gewinnt, AGENTS.md ist falsch
  und muss korrigiert werden.

  ---


  ## 🔴🔴🔴 KRITISCHE NEUE REGELN (2026-05-09) — GANZ OBEN — UNVERBRÜCHLICH 🔴🔴🔴

  ### REGEL 1: UNIVERSALITÄT — Egal was für eine Webseite/Modal/Pre-Qualifier/Survey
  **ABSOLUTER VERBOT:** Provider-spezifischer Hardcode (`if provider == "purespectrum"`, `if provider == "cint"`, etc.)
  **WARUM?** Jeder neue Survey-Typ bricht den Agenten. Pre-Qualifier, neue Modal-Typen, unbekannte Provider — alles crasht.
  **RICHTIG:** Der Agent SIEHT die Seite (DOM/Screenshot) und DENKT was zu tun ist — wie ein Mensch.
  ```
  capture_node: CDP → DOM Snapshot + Screenshot
  think_node:   LLM (Vision/Nemotron) → "Was ist hier? Was muss ich tun?"
  act_node:     Universal Actions → click, fill, select, scroll (egal welche Seite!)
  verify_node:  "Hat es geklappt? Ist Geld da?"
  ```
  → Jede Webseite der Welt. Jeder Modal-Typ. Jeder Pre-Qualifier. Universal.

  ### REGEL 1b: INTELLIGENZ — Generisch, nicht hardcoded
  **ABSOLUTER VERBOT:** `if "Zahl 52" in text: drag_drop_solver_52()` — DAS IST DUMM.
  **WARUM?** Wenn es "Zahl 20" heißt, crasht alles. Wenn es ein Bild statt Text ist, crasht alles.
  **RICHTIG:** "Ich sehe ein Bild mit '52'. Ich sehe eine leere Drop-Zone. Ich ziehe das Bild in die Zone."
  → Das funktioniert für 52, 20, Dreieck, Quadrat, Text-Bausteine — ALLES.

  ### REGEL 1c: KEINE MONOLITHE — Max 300 Zeilen pro Datei
  **ABSOLUTER VERBOT:** Riesige Dateien mit tausenden Zeilen. Das ist bad practices, NICHT best practices!
  **WARUM?** Monolithe sind undebuggbar, unwartbar, nicht testbar. Nächster Agent zerstört alles.
  **RICHTIG:** Modular, atomar. Jedes Tool eine eigene Datei. Jede Datei unter 300 Zeilen.
  ```
  survey-cli/tools/tool_solve_captcha.py   → 174 Zeilen ✅
  survey-cli/tools/tool_solve_drag_puzzle.py → 147 Zeilen ✅
  survey-cli/tools/tool_scan_dashboard.py  → 176 Zeilen ✅
  survey-cli/tools/tool_universal_answer.py → 216 Zeilen ✅
  ```
  → FastAPI Endpoints sind dünne Orchestratoren, nicht Monolithe!
  → **Wenn eine Datei über 300 Zeilen wächst → SOFORT aufteilen!**

  ### REGEL 1d: KEIN AUTO-RUN — Bis 100 Surveys MANUELL erfolgreich!
  **ABSOLUTER VERBOT:** Monolithischen Auto-Run-Loop bauen der alles automatisiert.
  **WARUM?** Wir können MANUELL keine einzige Umfrage erfolgreich lösen — wie soll ein Auto-Run funktionieren?
  **RICHTIG:** Erst alle FastAPI Endpoints + Tools einzeln bauen und TESTEN.
  Erst wenn 100 Surveys UND folge zuverlässig und fehlerfrei erledigt wurden → Auto-Run.
  ```
  ❌ FALSCH: build_monolithic_auto_run_loop() → запускаем всё auf einmal
  ✅ RICHTIG: Build tool → Test tool → Repeat → 100x verified → THEN automation
  ```

  ### REGEL 2: NIEMALS frisches Profil starten!
  IMMER Profil 901 (Jeremy) mit existierenden Cookies nutzen:
  1. `cp -R "$HOME/Library/Application Support/Google Chrome/Profile 901 (Jeremy)" /tmp/chrome-jeremy-heypiggy-9999`
  2. Chrome auf 9999 starten mit dieser Kopie
  3. 7 HeyPiggy-Cookies aus Backup injizieren (siehe Regel 4)
  → NIEMALS neues leeres Profil starten — das ist Zeitverschwendung und Login nötig!

  ### REGEL 3: Profile-Kopie ist verschlüsselt — reicht nicht allein!
  Chrome speichert Cookies AES-128-GCM mit MAC-Challenge. Kopie allein reicht NICHT.
  → IMMER zusätzlich Cookies per CDP injizieren nach dem Start.

  ### REGEL 4: 7 HeyPiggy-Cookies IMMER injizieren nach Chrome-Start!
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

  ## 📋 STATUS.md — NACH JEDER SESSION UPdaten

  **REGEL: Nach JEDER Survey-Session (erfolgreich oder fehlgeschlagen) → STATUS.md updaten.**

  ```
  Stealth-Runner STATUS.md Pflicht-Updates:
  1. Balance vorher/nachher eintragen (nur WENN echte Änderung!)
  2. Neue Blocker/Probleme dokumentieren (mit Root Cause)
  3. Provider-Status updaten falls getestet
  4. Session-Log erweitern (Datum, Aktion, Ergebnis)
  ```

  **WAS NIEMALS in STATUS.md:**
  - ❌ "Surveys completed: X" — wenn nicht verifiziert
  - ❌ "Surveys failed: Y" — wenn nicht verifiziert
  - ❌ Hardcoded Survey-IDs — die ändern sich pro Session!
  - ❌ Erfundene Zahlen oder Statistiken

  **Location:** `stealth-runner/STATUS.md`

   ## VISION-MODELL: Nemotron 3 Nano Omni (PRIMARY)
  
  - **30B-A3B Mixture-of-Experts** - Video + Audio + Bild + Text in EINEM Modell
  - **256K Kontext** - ganze Survey-Sessions in einem Call
  - **SSE Streaming** - `stream: true` -> tokenweise Antwort
  - **API**\: `POST https://integrate.api.nvidia.com/v1/chat/completions`
  - **Model Name**\: `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`
  - **API Key**\: `$NVIDIA_API_KEY` (Prefix: `nvapi-...`)
  
  ---
  
  ##  NEMO-ARCHITEKTUR: Compact-Loop mit Batch (2026-05-06, PRIMARY)
  
  **AKTUELL (2026-05-10): CDP WebSocket ist PRIMARY. skylight-cli ist NICHT IN BENUTZUNG.**
  survey-cli nutzt CDP WebSocket Runtime.evaluate direkt — kein skylight-cli anywhere.
  
  ```
  +──────────────────────────────────────────────────────────────────────────+
  |                 NEMO LOOP - 1 LLM Call pro Frage-Batch                   |
  +──────────────────────────────────────────────────────────────────────────+
  |                                                                           |
  |  while not complete:                                                      |
  |                                                                           |
  |  +──────────────────────────────────────────────────────────────────+     |
  |  | SCHRITT 1: COMPACT SNAPSHOT (CDP WebSocket)                     |     |
  |  |                                                                  |     |
  |  | Runtime.evaluate(compact_snapshot_js)                           |     |
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
  - **CDP WebSocket Runtime.evaluate** — PRIMARY (NO skylight-cli!)
  - survey-cli/survey/graph/nodes.py:decide_node() — NIM Nemotron Decision
  - survey-cli/survey/*.py Module
  
  ### WAS WIRKLICH FUNKTIONIERT (2026-05-10)
  
  | Tool | Status | Verwendung |
  |------|--------|-------------|
  | **CDP WebSocket** (Runtime.evaluate) | ✅ PRIMARY | survey-cli nutzt CDP DIREKT, kein skylight-cli! |
  | **CDP WebSocket** (Input.dispatchMouseEvent) | ✅ PRIMARY | Angular CDK drag-drop (Approach B verified) |
  | **CDP HTTP** (PUT /json/new?) | ✅ PRIMARY | Tab-Erstellung |
  | **survey-cli tools/** | ✅ PRIMARY | tool_open_survey, tool_fill_survey, tool_snapshot, etc. |
  | **cua-driver** | ⚠️ DEPRECATED | NUR für Popups/Sheets, KEIN Web-Content |
  | **skylight-cli** | ❌ NICHT BENUTZT | survey-cli nutzt CDP direkt! |
  | webauto-nodriver | ❌ BANNED | Absolut |
  
  ### Verboten vs. Erlaubt (NEMO-Update)
  
  | Tool | Status | Begründung |
  |------|--------|------------|
  | **CDP WebSocket** Runtime.evaluate | ✅ PRIMARY | snapshot-compact + batch + fill |
  | **CDP WebSocket** Input.dispatchMouseEvent | ✅ PRIMARY | Angular CDK drag-drop |
  | **survey-cli tools/** | ✅ PRIMARY | tool_open_survey, tool_fill_survey, etc. |
  | **src/stealth_survey/** | ❌ DELETED | INTENTIONALLY DELETED 2026-05-08 |
  | **cua-driver** | ⚠️ DEPRECATED | Nur Popups/Sheets |
  | skylight-cli click (index) | ❌ BANNED | Nicht benutzt, nutze CDP |
  | webauto-nodriver | ❌ BANNED | Absolut |
  
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
  
  ## TOOLS (CDP WebSocket ist das EINZIGE aktive Tool für Web-Content)

  ### WAS WIRKLICH FUNKTIONIERT (2026-05-10)
  
  | Tool | Status | Verwendung |
  |------|--------|-------------|
  | **CDP WebSocket** (Runtime.evaluate) | ✅ PRIMARY — 100% aller survey-cli tools nutzen es | Alle Browser-Interaktionen |
  | **CDP WebSocket** (dispatchMouseEvent) | ✅ PRIMARY | Angular/Komplexe Elemente |
  | **CDP HTTP** (PUT /json/new?) | ✅ PRIMARY | Tab-Erstellung (Popup-frei) |
  | **cua-driver** | ⚠️ DEPRECATED — NUR noch für Google Login + Fallback | KEIN Web-Content |
  | **skylight-cli** | ❌ NICHT BENUTZT — trotz "PRIMARY" in alter AGENTS.md | survey-cli nutzt CDP direkt |
  | **macos-ax-cli** | ❌ NICHT BENUTZT | Nur für System-Scan |
  
  **WARNUNG (2026-05-10): AGENTS.md hatte skylight-cli als PRIMARY markiert, ABER kein survey-cli Code nutzt es!**
  Alle aktiven Tools nutzen CDP WebSocket direkt. skylight-cli ist LEGACY/DEPRECATED.
  
  ### CDP WebSocket Commands (AKTUELL)
  
  ```python
  # Snapshot → Runtime.evaluate JS
  await ws.send(json.dumps({'id':1,'method':'Runtime.evaluate','params':{'expression': 'document.querySelectorAll("input,button,select,textarea")...'}}))
  
  # Click → dispatchMouseEvent oder JS click()
  await ws.send(json.dumps({'id':2,'method':'Input.dispatchMouseEvent', 'params':{'type':'mousePressed','x':cx,'y':cy,...}}))
  # ODER:
  await ws.send(json.dumps({'id':3,'method':'Runtime.evaluate','params':{'expression':'document.querySelector("button").click()'}}))
  
  # Tab erstellen → CDP HTTP PUT /json/new?
  subprocess.run(['curl', '-s', '-X', 'PUT', f'http://127.0.0.1:9999/json/new?{url}'])
  
  # Cookies → Network.setCookies
  await ws.send(json.dumps({'id':4,'method':'Network.setCookies','params':{'cookies':[...]}}))
  ```
  
## VERBOTEN (BANNED)

  - CDP `Accessibility.queryAXTree` / `getContentQuads` (für Navigation)
  - `skylight-cli click --element-index` (skylight-cli ist NICHT IN BENUTZUNG, trotzdem banned)
  - `webauto-nodriver` MCP (ABSOLUT VERBOTEN)
  - `pkill -f "Google Chrome"` (tötet private Sessions!)
  - `POST /json/protocol/targets/create` (falscher endpoint, nutze PUT /json/new?)
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

  ## DRAG-DROP CAPTCHA PUZZLE — ANGULAR CDK LÖSUNG (2026-05-09, BLOCKIERT)

  ### Das Problem
  Purespectrum-Surveys zeigen ein "Zahl X" Drag-Drop Puzzle bei ~66%:
  - 3 draggbare Bilder: `06.png`, `10.png`, `52.png` (100×100px)
  - 1 leere Drop-Zone: `.drop-zone`
  - Text: *"Bitte legen Sie die Zahl 52 in das leere Kästchen"*
  - Button "Nächste" → disabled bis Puzzle gelöst

  ### Warum `solve_drag_puzzle()` in purespectrum.py FAILT
  Alter Code sucht `_dropListRef` / `_dragRef` über `__ngContext__` traversal → ZWEI fatale Fehler:

  1. **`__ngContext__` ist Zahl, nicht Objekt**: Angular Ivy Production Build speichert Component Reference als Index (z.B. `4`), nicht als Object-Dict. `findInstance(4, '_dropListRef')` findet nichts.

  2. **`window.ng` nicht verfügbar**: Angular Debug-API (`ng.getComponent`) existiert nur im Dev-Mode, nicht im Production Build.

  3. **`DragDropCaptchaSolver` in stealth-captcha ist BROKEN**: Nutzt `Input.dispatchMouseEvent` (Mouse-Events) → Angular CDK reagiert NICHT darauf.

  ### Die Lösung: PointerEvents (keine CDK-Interna!)

  **Regel: NIEMALS versuchen Angular CDK Internals zu erreichen. Immer echte User-Interaktion simulieren.**

  ```javascript
  // Schritt 1: Zielbild finden (alt="52")
  const target = document.querySelector('img[alt="52"]');
  const dropZone = document.querySelector('.drop-zone');

  // Schritt 2: Positionen ermitteln
  const rectTarget = target.getBoundingClientRect();
  const rectZone = dropZone.getBoundingClientRect();
  const scrollX = window.scrollX || window.pageXOffset;
  const scrollY = window.scrollY || window.pageYOffset;

  // Schritt 3: PointerEvents dispatchen (Angular CDK nutzt PointerEvents!)
  const sx = rectTarget.left + rectTarget.width/2 + scrollX;
  const sy = rectTarget.top + rectTarget.height/2 + scrollY;
  const ex = rectZone.left + rectZone.width/2 + scrollX;
  const ey = rectZone.top + rectZone.height/2 + scrollY;

  // pointerdown
  target.dispatchEvent(new PointerEvent('pointerdown', {
    bubbles: true, cancelable: true, pointerId: 1, isPrimary: true,
    clientX: sx, clientY: sy, button: 0
  }));

  // pointermove (mittlere Position)
  document.dispatchEvent(new PointerEvent('pointermove', {
    bubbles: true, cancelable: true, pointerId: 1, isPrimary: true, buttons: 1,
    clientX: (sx+ex)/2, clientY: (sy+ey)/2
  }));

  // pointerup über drop zone
  dropZone.dispatchEvent(new PointerEvent('pointerup', {
    bubbles: true, cancelable: true, pointerId: 1, isPrimary: true,
    clientX: ex, clientY: ey, button: 0
  }));
  ```

  ### Warum PointerEvents und nicht MouseEvents?

  Angular CDK (ab v7) verwendet **nur PointerEvents**:
  ```typescript
  @HostListener('pointerdown', ['$event'])
  @HostListener('pointermove', ['$event'])
  @HostListener('pointerup', ['$event'])
  ```
  `MouseEvent` oder CDP `Input.dispatchMouseEvent` löst die CDK Drag-Logik NICHT aus.

  ### Purespectrum Drag-Drop Varianten

  | Variante | Erkennung | Ziel-Identifikation |
  |----------|-----------|---------------------|
  | Zahl-Bilder (`06.png`, `52.png`) | Text: "Zahl X in Kästchen" | `img[alt="X"]` |
  | Formen (Dreieck, Quadrat) | Text: "das Dreieck" | `img[alt="..."]` |
  | Text-Bausteine | textContent statt alt | `div[data-drag-text="..."]` |

  ### `stealth-captcha` Module Status (2026-05-10, UPDATED)

  | Solver | Nutzt | Funktioniert für Angular CDK? |
  |--------|-------|-------------------------------|
  | `SlideCaptchaSolver` | MouseEvents | ❌ NEIN |
  | `DragDropCaptchaSolver` | `Input.dispatchMouseEvent` | ❌ NEIN (falsche Events!) |
  | `TextCaptchaSolver` | NVIDIA Vision | ✅ JA (kein Drag) |
  | `ImageSelectCaptchaSolver` | ? | ⚠️ UNGETESTET |
  | **`AngularDragDropSolver`** | **Multi-Approach** (Playwright mouse → CDP dispatchMouseEvent → Synthetic PointerEvents → HTML5 Drag/DOM) | **🔄 TESTING — 4 Approaches** |

  **NEW SOLVER: `AngularDragDropSolver` (drag_drop_angular.py)**
  - 4 sequential approaches (A→B→C→D), stops at first success
  - Approach A: Playwright `page.mouse.move/down/up()` — REAL browser-level pointer events
  - Approach B: CDP `Input.dispatchMouseEvent` — native browser engine events
  - Approach C: Synthetic `PointerEvent` with 10 intermediate steps + delays + realistic properties
  - Approach D: HTML5 `DragEvent` + direct DOM manipulation + button enable
  - **CRITICAL FIX**: Selectors corrected (`.cdk-drop-list` class, NOT `id="dropZoneList"`)
  - **CRITICAL FIX**: 10 intermediate drag points with arc offset (realistic movement)
  - Debug logging enabled (`DEBUG = True`) for E2E troubleshooting

  ### E2E Test Results (2026-05-10)
  - **Survey 66910983** (PureSpectrum): 0% → 33% → 66% ✅ (consent, ROBOT, visual captcha solved)
  - **Blocked at 66%**: "Zahl 20" drag-drop puzzle
  - **Previous failure**: Synthetic JS `dispatchEvent` blocked by Angular CDK
  - **New solver deployed**: Multi-approach with Playwright raw mouse API as primary
  - **Status**: 🔄 AWAITING LIVE E2E VERIFICATION

  ### Implementierungs-Plan (TODO — 2026-05-10 UPDATE)

  1. [ ] **E2E TEST**: Run `python3 test_drag_drop_angular.py --live --auto-discover` against live survey
  2. [ ] **FIX**: If Approach A (Playwright) fails → investigate CDP tab discovery / selector issues
  3. [ ] **FIX**: If Approach B (CDP) fails → verify `Input.dispatchMouseEvent` generates PointerEvents
  4. [ ] **DOC**: `/commands/surveys/purespectrum-drag-puzzle.md` → ✅ VERIFIED after E2E success
  5. [ ] **INTEGRATE**: Wire `solve_drag_puzzle_new(ws_url)` into `purespectrum.py` preflight flow

  ## SURVEY FLOW (2026-05-10, VERIFIZIERT)
  
  ### Kompletter Ablauf
  ```
  1. SCAN: CDP JS -> finde Tab MIT .survey-item (document.querySelectorAll)
  2. START: CDP JS -> clickSurvey('ID') → Dashboard öffnet Modal
  3. MODAL: CDP JS -> window.open interception + Target.createTarget → Survey-Tab ��ffnet sich
     ⚠️ CUA b.click() + CDP Input.dispatchMouseEvent = FAIL (Chrome Popup Blocker!)
     ✅ window.open interception (siehe §KRITISCH: "Umfrage starten" Problem)
     ⚠️ COOKIE TIMING: Target.createTarget öffnet neuen Tab OHNE Session-Cookies!
  4. CONSENT: CDP JS -> Cookie "Alle akzeptieren" button.click()
  5. CAPTCHA: Fälle "ROBOT", Math, Dropdown → per CDP JS + NVIDIA Vision
  6. START: Survey öffnet sich in Tab → Provider identifizieren
  7. AUDIO-FRAGE: Audio Module -> BlackHole + ffmpeg + NVIDIA Omni
  8. ANTWORT: CDP JS -> Radio/Checkbox/Text per Provider-Methode + "Nächste"
  9. KOMPLETT: Survey schließt -> zurück zu heypiggy Dashboard → Balance erhöht
  ```

  ### 🚨 KRITISCH: Cookie Timing — Survey öffnet sich OHNE Session-Cookies (2026-05-10)

  **E2E Test Result (2026-05-10):**
  - Survey 67078106 (Cint) completed ✅ — "Vielen Dank" displayed
  - Balance before: €2.70 → Balance after: €2.70
  - **Delta: €0.00 — NO PAYMENT!** ❌

  **Root Cause:** `Target.createTarget()` creates new tab → navigates to CPX URL immediately → 7 HeyPiggy cookies are NOT injected into this new tab. The entire redirect chain `CPX → Samplicio → Cint → Potloc` runs WITHOUT session cookies. Heypiggy completion tracking cannot associate the survey completion with the correct user session → balance stays at €0.

  **Affected Code:** `survey-cli/survey/opener.py` → `_open_in_page_modal()` calls `_find_new_tab_after_click()` which uses `Target.createTarget()`. Cookies are injected into the DASHBOARD tab first, but the new survey tab has NO cookies.

  **Fix Attempted:** Page.navigate in dashboard tab (should have cookies) — FAILED
  **Fix Status:** 🔴 UNRESOLVED — further investigation needed

  **Options to try:**
  1. **Inject cookies into survey tab BEFORE navigation** (CDP Network.setCookies on survey tab WS)
  2. **Keep survey in same dashboard tab** (Page.navigate instead of new tab)
  3. **Debug completion tracking** — trace what Heypiggy expects during redirect chain

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
  | Samplicio.us | `rx.samplicio.us/consent/` | Consent -> My-Take -> **Cloudflare CAPTCHA blocks** | ❌ BLOCKED: geo.captcha-delivery.com iframe |
  | Cint | `sw.cint.com/Session/` | Session → Fragen | ❌ BLOCKED: CPX redirects hit Cloudflare CAPTCHA |
  | Nfield/Kantar | `nfieldeu-interviewing.nfieldmr.com` | Welcome -> Audio/Video-Fragen | 🔄 UNGETESTET |
  | Purespectrum | `purespectrum.com` | Cookie → ROBOT captcha ✅ → Textarea ✅ → Visual captcha ✅ → **Drag-Drop "Zahl X"** ✅ → surveyrouter.com screen-out | 🔄 APPROACH B VERIFIED: Drag-drop solved with CDP Input.dispatchMouseEvent. Screen-out at surveyrouter.com is NEW blocker. |

  ### Wichtige Erkenntnisse
  1. **Multi-Tab Problem**\: heypiggy öffnet mehrere Dashboard-Tabs. Nur EINER hat Surveys. Scanne ALLE Tabs!
  2. **Survey In-Page**\: clickSurvey() öffnet den Survey im Dashboard (kein neuer Tab!). AX-Tree rescanen nach neuen Elementen!
  3. **Survey Modal**\: "Umfrage starten" Button nutzt window.open() → Popup Blocker → window.open interception nötig!
  4. **Blob-Audio**\: `<video>` mit blob: URL kann NICHT via JS extrahiert werden. BlackHole nötig.
  5. **Cloudflare CAPTCHA**\: Systemischer Blocker auf allen CPX-Redirects (Cint, Samplicio). Body wird leer, 0 interaktive Elemente.
  6. **surveyrouter.com screen-out**\: Nach PureSpectrum checkbox-Frage → "keine passende Umfragen" → kein Guthaben verdient. |
  
  ### Wichtige Erkenntnisse
  1. **Multi-Tab Problem**\: heypiggy öffnet mehrere Dashboard-Tabs. Nur EINER hat Surveys. Scanne ALLE Tabs!
  2. **Survey In-Page**\: clickSurvey() öffnet den Survey im Dashboard (kein neuer Tab!). AX-Tree rescanen nach neuen Elementen!
  3. **Survey Modal**\: "Umfrage starten" Button nutzt window.open() → Popup Blocker → window.open interception nötig!
  4. **Blob-Audio**\: `<video>` mit blob: URL kann NICHT via JS extrahiert werden. BlackHole nötig.
  5. **Disqualifikation**\: 0.02€ Compensation bei Abbruch. Level-Up bei erfolgreicher Teilnahme.
  6. **Purespectrum Drag-Drop**\: "Zahl X in Kästchen" Puzzle → NICHT `__ngContext__` traversal, NICHT MouseEvents → NUR PointerEvents auf DOM-Ebene. `DragDropCaptchaSolver` in stealth-captcha ist BROKEN (nutzt MouseEvents). `solve_drag_puzzle()` in purespectrum.py ist BROKEN (`__ngContext__` ist Zahl, nicht Objekt).
  
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
  ╔══════════════════════════════════════════════════════════��═══════╗
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
-  CDP WebSocket Runtime.evaluate — PRIMARY für kompakte Snapshots (NO skylight-cli!)
   -  survey-cli/survey/graph/nodes.py:decide_node() — NIM Nemotron Decision
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
└────────────────���────────────────────────────────────────┘
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
| Consent | Samplicio, Ipsos | "Zustimmen und fortfahren" | CDP JS click | ✅ VERIFIED |
| Single Choice Radio | Alle | `input[type=radio]` | CDP click | ✅ VERIFIED |
| Custom Radio DIV | TolunaStart | `class="cf-radio-answer"` | CDP JS click | ✅ VERIFIED |
| Matrix | Kantar | Grid mit Radio-Buttons | CDP loop | 🔄 LEARNING |
| Text Input | Alle | `input[type=text]` | CDP NativeInputValueSetter | ✅ VERIFIED |
| Textarea | Alle | `<textarea>` | CDP NativeInputValueSetter | ✅ VERIFIED |
| NPS Rating | SurveyRouter | Skala 0-10 | CDP click | 🔄 LEARNING |
| Binary Matrix | Kantar | Ja/Nein Grid | CDP loop | 🔄 LEARNING |
| Multi-Select Checkbox | Alle | `input[type=checkbox]` | CDP click (up to 4) | ✅ VERIFIED |
| Dropdown | Qualtrics | `<select>` | CDP click | 🔄 LEARNING |
| Blob Audio | Nfield | `<video src="blob:">` | BlackHole + ffmpeg | 🔄 LEARNING |
| ROBOT Captcha | PureSpectrum | "ROBOT" im Text | type "ROBOT" + click | ✅ VERIFIED |
| Visual Captcha | PureSpectrum | base64 PNG img | Llama 90B Vision + type | ✅ VERIFIED |
| Angular CDK Drag-Drop | PureSpectrum | "Bitte legen Sie die Zahl X" | CDP Input.dispatchMouseEvent | ✅ VERIFIED |
| Cloudflare Challenge | CPX mediated | geo.captcha-delivery.com iframe | ❌ SYSTEMIC BLOCKER | ❌ BLOCKED |
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


---

## §11 — COMPLETE PROJECT ARCHIVE (SINGLE SOURCE OF TRUTH 2026-05-09)

**Dieser Abschnitt ist die autoritative Wissensbasis. Jeder Agent MUSS diesen Abschnitt lesen und verstehen. ALLES was nicht hier dokumentiert ist, wird vom Agenten nicht gesehen.**

---

### §11.1 — ALLE REPOSITORIES (Stealth Suite — 30+ Repos)

| # | Repo | Kern-Funktion | Status |
|---|------|---------------|--------|
| 1 | **stealth-runner** | Orchestrator, FastAPI Endpoints, survey-tools | ✅ PRIMARY |
| 2 | **survey-cli** | Standalone Survey Automation CLI, NEMO Loop | ✅ PRIMARY |
| 3 | **stealth-captcha** | Captcha Solver Module (slide/text/drag) | ✅ PRIMARY — Drag APPROACH B verified (Survey 49517969) |
| 4 | **stealth-session** | Warm Daemon, <50ms Command Execution | ✅ PRIMARY |
| 5 | **stealth-mind** | Command Validator, Failure Pattern Recognition | ✅ ACTIVE |
| 6 | **stealth-skills** | Private Skill Library (heypiggy platform) | ✅ ACTIVE |
| 7 | **stealth-suite** | Monorepo (Turborepo, 14 Packages) | 🔄 REFACTOR |
| 8 | **cua-touch** | CUA Actuation (AXPress Click) | ⚠️ DEPRECATED |
| 9 | **skylight-cli** | macOS AX Window Capture + SoM | ⚠️ DEPRECATED |
| 10 | **stealth-core** | Core Pipeline + Runner + Adapters | 🔄 LEARNING |
| 11 | **stealth-guardian** | Compliance-as-Code Policy Engine | 🔄 LEARNING |
| 12 | **stealth-axiom** | Model Selection Router | 🔄 LEARNING |
| 13 | **stealth-dynamic** | Dynamic Survey Engine | 🔄 PLANNED |
| 14 | **stealth-sync** | OpenCode DB Polling + NIM Integration | ✅ ACTIVE |
| 15 | **stealth-sota** | Chaos Monkey + Self-Healing + Observability | 🔄 LEARNING |
| 16 | **stealth-lora** | SOTA LoRA Training Pipeline | 🔄 LEARNING |
| 17 | **stealth-optimizer** | Output Limiter (micro:32 mid:128 heavy:512) | 🔄 LEARNING |
| 18-30 | stealth-cost, stealth-config, stealth-compressor, stealth-cache, stealth-batch, stealth-memory, stealth-swarm, stealth-lora-transfer, playstealth-cli (❌ BANNED), unmask-cli, screen-follow, ax-graph, macos-ax-cli | Various Infrastructure | 🔄/❌ |

---

### §11.2 — STEALTH-RUNNER DATEIARCHITEKTUR

```
stealth-runner/                                   <- PRIMARY ORCHESTRATOR
├── AGENTS.md                                     <- SINGLE SOURCE OF TRUTH
├── brain.md                                      <- NEMO Architektur
├── sinrules.md                                   <- Golden Rules (zentral)
├── banned.md                                     <- Verbotene Praktiken
├── fix.md                                        <- Root Cause Fixes
├── issues.md                                     <- SR-28 bis SR-37
│
├── [agent-toolbox]/                              <- FastAPI + survey-cli Tools
│   ├── api/endpoints/                            <- MODULAR FASTAPI ROUTERS (KEIN MONOLITH!)
│   │   ├── __init__.py                           <- Re-exports all routers + schemas
│   │   ├── _schemas.py     (268L)                <- Alle Pydantic Request/Response Models
│   │   ├── _utils.py      (221L)                <- preflight_check + require_survey_ready + update_registry
│   │   ├── _common.py     (66L)                 <- Re-exports _schemas + _utils (backward compat)
│   │   ├── survey_core.py     (215L)            <- /open, /close, /rate, /purespectrum-preflight, /run-graph
│   │   ├── survey_answer.py  (267L)             <- /snapshot (ELEMENT_EXTRACTOR_JS), /completion, /answer
│   │   ├── survey_actions.py (245L)             <- /click, /find, /verify, /click-angular, /fill-input, /find-tab, /close-modals
│   │   ├── survey_captchas.py(138L)             <- /captcha/solve, /solve-drag (APPROACH B verified)
│   │   └── survey_scan.py     (108L)            <- /survey/scan
│   ├── api/survey_tools.py                       <- Router Kombination (85L) + /fill endpoint + include_router()
│   ├── api/routes/gmx.py, fireworks.py, browser.py, rotation.py
│   └── core/cdp_client.py, gmx_service.py, fireworks_service.py, cookie_manager.py, browser_manager.py
│
├── [survey-cli]/                                 <- EINGEBETTETES SUBMODUL
│   ├── survey.py                                 <- 12 subcommands: login/scan/run/loop/watch/balance/status/doctor/kill/summary/opencode/profile
│   └── survey/providers/
│       ├── purespectrum.py                       <- PureSpectrum Provider
│       │   ├── solve_purespectrum_preflight()    <- cookie + ROBOT + textarea + visual captcha ✅ WORKING
│       │   └── solve_drag_puzzle()               <- ⚠️ DEPRECATED — tool_solve_drag_puzzle.py APPROACH B nutzen
│       └── heypiggy.py, *.py                     <- Andere Provider
│
├── [stealth-captcha]/                            <- EINGEBETTETES SUBMODUL
│   └── src/stealth_captcha/
│       ├── cli.py                                <- CLI: solve-captcha [slide|drag|text], start-chrome, memory-stats, list-targets
│       └── solver/
│           ├── base.py                           <- CaptchaBackend Protocol + Solver base
│           ├── slide.py                          <- SlideCaptchaSolver (GeeTest)
│           ├── text.py                           <- TextCaptchaSolver + PixtralBackend + NVIDIA Vision ✅ WORKING
│           ├── image_select.py                   <- ImageSelectCaptchaSolver
│           ├── drag_drop.py                      <- DragDropCaptchaSolver ⚠️ DEPRECATED — nutze drag_drop_angular.py
│           ├── drag_drop_angular.py              <- ✅ APPROACH B: CDP Input.dispatchMouseEvent chain — VERIFIED (E2E Survey 49517969)
│           ├── lemin.py                          <- Lemin Puzzle Solver
│           └── utils.py                          <- helper.py, screenshot(), get_chrome_ws()
│
├��─ [commands]/                                   <- VERIFIED Commands (chmod 444)
│   ├── cmd-rules.md
│   ├── bot-chrome/kill-bot-chrome.md             <- ✅ VERIFIED
│   ├── bot-chrome/find-bot-pids.md               <- ✅ VERIFIED
│   ├── captcha/WORKING-SOLUTION.md               <- ⭐ Captcha Solving Overview
│   ├── surveys/purespectrum-survey.md            <- ✅ VERIFIED
│   ├── surveys/survey-start-flow.md              <- ✅ VERIFIED (window.open interception)
│   ├── surveys/surveyrouter-pre-qualifier-2026-05-09.md <- ✅ VERIFIED
│   ├── surveys/purespectrum-drag-puzzle.md       <- ✅ VERIFIED (APPROACH B E2E 2026-05-10)
│   ├── cua-driver/click.md, set-value.md, list-windows.md, get-window-state.md, switch-tab.md
│   └── heypiggy/credentials.md, rating-page.md
│
├── [stealth-sync]/                               <- Sync Daemon
├── [stealth-sota]/                               <- SOTA Extensions: chaos_engine, security_hardening, self_healing, observability, determinism
│
├── [.opencode/skills]/                           <- OpenCode Agent Skills (cavecrew, caveman, diagnose, etc.)
├── [.claude/skills]/                             <- Claude Agent Skills (gitnexus, grill-me, etc.)
├── [.qwen/skills]/                               <- Qwen Agent Skills
│
├── [flows]/                                      <- Compiled Flow Engine
│   ├── candidates/                               <- Flows in Lern-Phase
│   ├── production/                               <- 10x bestanden = Production
│   └── history/                                  <- JSONL pro Flow
│
├── [scripts]/
│   ├── check_doc_health.py                       <- Prueft alle Repos auf Pflichtdateien
│   └── generate_missing_docs.py                  <- Erstellt fehlende Pflichtdateien
│
├── plan-sr-28-cdp-survey-module.md
├── plan-sr-29-ps-captcha-ocr.md                  <- ⭐ SR-29 — PureSpectrum Captcha OCR
├── plan-sr-30-dashboard-poller.md
├── plan-sr-31-fctes-promotion.md
├── plan-sr-32-provider-detect.md
├── plan-sr-33-persona-system.md
├── plan-sr-34-test-suite.md
├── plan-sr-35-chrome-safety.md
├── plan-sr-36-docs-cleanup.md
├── plan-sr-37-skylight-compact.md
│
├── run_survey.py                                 <- Haupt-Einstiegspunkt
├── pyproject.toml, Makefile, .env.example
├── opencode.json                                 <- Tool Registry + Manifest
├── registry.md, registry-*.md                    <- Domain Registries
├── learn.md, anti-learn.md, successful.md        <- Lern-Docs
├── bugs.md, changelog.md, goal.md, roadmap.md    <- Projekt-Mgmt
├── state.md, tool-manifest.md                    <- Status Docs
├── architecture.md, design.md, faq.md, history.md <- Architektur Docs
├── contributing.md, security.md, testing.md      <- Operations Docs
├── benchmarks.md, graph.json, graph-report.md, manifest.json
├── .semgrep_rules.yaml, .gitnexus.yml
│
├── [src/stealth_survey/]                         <- ❌ INTENTIONALLY DELETED 2026-05-08
├── [app/]                                        <- ❌ INTENTIONALLY DELETED 2026-05-08
├── launch_parallel.py                            <- ❌ BANNED — SOFORT LOESCHEN
├── README_PARALLEL.md                            <- ❌ BANNED — SOFORT LOESCHEN
└── tmp_*.py                                      <- ❌ TEST-DATEIEN — SOFORT LOESCHEN
```

---

### §11.3 — COMPLETE DRAG-DROP PUZZLE PROBLEM (FULL DISCLOSURE)

**Status: BLOCKED since 2026-05-09. Survey 67064749 (Zahl 52) + 67064991 (Zahl 42) beide bei 66%.**

#### DOM Structure
```
<div class="cdk-drop-list d-flex justify-content-around">
    <div class="cdk-drag"><img src=".../06.png" alt="06"></div>
    <div class="cdk-drag"><img src=".../10.png" alt="10"></div>
    <div class="cdk-drag"><img src=".../52.png" alt="52"></div>  <- TARGET
</div>
<div class="cdk-drop-list d-flex justify-content-center align-items-center drop-zone">
    <!-- leeres Drop-Ziel -->
</div>
```

#### All Failed Approaches (live getestet 2026-05-09)

| # | Approach | Where | Why Failed | Result |
|---|----------|-------|------------|--------|
| 1 | `__ngContext__` traversal | purespectrum.py:solve_drag_puzzle() | `__ngContext__` ist **Zahl** (4), nicht Object. `findInstance(4, '_dropListRef')` = null | `NO_DROPLISTDIR` |
| 2 | `window.ng.getComponent()` | purespectrum.py | Angular Debug-API nur im Dev-Mode, nicht Production | `NO_WINDOW_NG` |
| 3 | Deep window scope scan | purespectrum.py | Timeout 30s, kein `_dropListRef` gefunden | TIMEOUT |
| 4 | JS `dispatchEvent(MouseEvent)` | Direct CDP | Angular CDK reagiert auf **PointerEvents**, nicht MouseEvents | `dropzoneImg: EMPTY` |
| 5 | JS `dispatchEvent(PointerEvent)` | Direct CDP | CDK blockiert synthetic events auf niedrigerer Ebene | `dropzoneImg: EMPTY` |
| 6 | isTrusted patch on PointerEvent prototype | Direct CDP | CDK prueft `isTrusted` NICHT primaer | `dropzoneImg: EMPTY` |
| 7 | CDP `Input.dispatchMouseEvent` (browser-level via heypiggy tab) | CDP Input | Sendet MouseEvents, nicht PointerEvents | `dropzoneImg: EMPTY` |
| 8 | `DragDropCaptchaSolver` (stealth-captcha) | drag_drop.py | Nutzt `Input.dispatchMouseEvent` = MouseEvents, CDK braucht PointerEvents | ❌ NIEMALS nutzen fuer Angular CDK |
| 9 | CDK `enter()` + `drop()` via placeholder | purespectrum.py | `dropListRef.enter(dragRef, null)` — null placeholder = error | `DROP_ERROR` |
| 10 | CSS clone + mutation | Direct CDP | Angular change detection nicht getriggert | `dropzoneImg: EMPTY` |

#### Root Cause
- Angular CDK (ab v7): `@HostListener('pointerdown', ['$event'])` — NUR PointerEvents
- Synthetic PointerEvents werden von Angular blockiert (nicht via isTrusted)
- CDP `Input.dispatchMouseEvent` sendet MouseEvents (kein `Input.dispatchPointerEvent` in Standard-CDP)
- `__ngContext__` = Production Build Index (Zahl), nicht Component-Objekt
- `window.ng` nicht verfuegbar in Production

#### Working Parts (survey-cli survey 67064991)
```
0% -> .cky-btn-accept click -> 33% -> NVIDIA Vision OCR (ROBOT) -> 33% -> base64 PNG captcha (Q3333S) -> 66% -> ✅ SOLVED with Approach B (CDP mouse events) -> screen-out (€0)
```

#### SOLUTION VERIFIED (2026-05-10) — Approach B: CDP Input.dispatchMouseEvent

**E2E TEST:** Survey 49517969 (PureSpectrum) — "Zahl 28" puzzle at 66%
- ROBOT captcha: filled "ROBOT" → Nächste clicked → advanced to 33%
- Visual captcha: "tpyTrD" solved via Llama 90B vision → Nächste clicked → advanced to 66%
- Drag-drop: "Zahl 28" image dragged to drop-zone via CDP mouse events → Nächste clicked → 100% → screen-out

**Methode:** `Input.dispatchMouseEvent` (Approach B in drag_drop_angular.py)
- Real browser-level mouse events trigger Angular CDK's pointer event handlers
- `mousePressed` → 10× `mouseMoved` (mit arc offset für realistische Bewegung) → `mouseReleased`
- NOT: Synthetic PointerEvents (Approach C/D) — Angular blockiert diese
- NOT: MouseEvents via dispatchEvent (JS-level) — Angular ignoriert diese

**Code Pattern:**
```python
# mousePressed on source (img[alt="28"])
await ws.send(json.dumps({'id':3,'method':'Input.dispatchMouseEvent','params':{
    'type':'mousePressed','x':sx,'y':sy,'button':'left','clickCount':1}}))

# 10-step mouseMoved with arc offset
for i in range(1, 11):
    t = i/10; ix = sx+(ex-sx)*t; iy = sy+(ey-sy)*t
    arc_off = 20*(1-abs(2*t-1)); iy -= arc_off
    await ws.send(json.dumps({'id':3+i,'method':'Input.dispatchMouseEvent','params':{
        'type':'mouseMoved','x':ix,'y':iy,'button':'left'}}))
    await asyncio.sleep(0.05)

# mouseReleased on destination (drop-zone)
await ws.send(json.dumps({'id':20,'method':'Input.dispatchMouseEvent','params':{
    'type':'mouseReleased','x':ex,'y':ey,'button':'left','clickCount':1}}))
```

**Integration:** answer_survey.py:solve_drag_drop() — VERIFIED ✅

#### Solution Architecture (4 neue Dateien — TODO)

```
1. ✅ stealth-captcha/src/stealth_captcha/solver/drag_drop_angular.py
   -> AngularDragDropSolver, Approach B: CDP Input.dispatchMouseEvent — VERIFIED

2. ✅ answer_survey.py:solve_drag_drop()
   -> integriert in survey answer flow

3. TODO: survey-cli/survey/providers/purespectrum.py:solve_drag_puzzle()
   -> survey-cli/tools/tool_*.py Wrapper für FastAPI

4. TODO: commands/surveys/purespectrum-drag-puzzle.md
   -> Dokumentation nach 10x Erfolg
```

---

### §11.4 — ALLE TOOLS & IHRE STATUS

| Tool | Repo | Port/Context | Status | Verwendung |
|------|------|-------------|--------|------------|
| **CDP WebSocket** | stealth-runner | Port 9999 | ✅ PRIMARY | Alle Browser-Interaktionen |
| **survey-cli tools** | survey-cli | Port 9999 | ✅ PRIMARY | Survey-Automation |
| **stealth-captcha** | stealth-captcha | Port 9999 | ⚠️ PARTIAL | Slide/Text ✅, Drag ❌ |
| **cua-driver** | cua-touch | Port 9999 | ⚠️ DEPRECATED | Nur Popups/Sheets, kein Web-Content |
| **skylight-cli** | skylight-cli | macOS AX | ⚠️ DEPRECATED | Window Capture, LEGACY |
| **macos-ax-cli** | macos-ax-cli | macOS AX | ⚠️ EXPERIMENTAL | AX Scanning |
| **playstealth launch** | playstealth-cli | Port 9224 | ❌ BANNED | falsche Flags, Profile 902 |
| **webauto-nodriver** | - | - | ❌ BANNED | ABSOLUT VERBOTEN |
| **decrypt_cookies.py** | - | - | ❌ BANNED | nur Chrome <147 v10 |
| **NVIDIA Vision API** | external | `integrate.api.nvidia.com` | ✅ PRIMARY | Captcha OCR, Survey Decision |
| **NVIDIA NIM Nemotron** | external | `integrate.api.nvidia.com` | ✅ PRIMARY | NEMO Survey Decision |
| **BlackHole + ffmpeg** | system | macOS Audio | ✅ FOR AUDIO | Blob Audio Capture |
| **SwitchAudioSource** | system | macOS Audio | ✅ FOR AUDIO | Audio Routing |

---

### §11.5 — ALLE BEKANNTEN SURVEY PROVIDER

| Provider | URL Pattern | Flow | Status |
|----------|------------|------|--------|
| **SurveyRouter** | heypiggy internal | window.open interception -> Survey-Tab | ✅ FIXED |
| **Purespectrum** | `screener.purespectrum.com` | Cookie -> ROBOT -> Textarea -> Visual -> **Drag-Drop "Zahl X"** | 🔄 APPROACH B VERIFIED (2026-05-10): Drag-drop solved with CDP mouse events. Still blocked at surveyrouter.com screen-out. |
| **Samplicio.us** | `rx.samplicio.us/consent/` | Consent -> My-Take -> **Cloudflare CAPTCHA blocks** | ❌ BLOCKED: geo.captcha-delivery.com iframe challenge (systemic) |
| **Cint** | `sw.cint.com/Session/` | Session -> Fragen | ❌ BLOCKED: CPX redirects hit Cloudflare CAPTCHA (systemic) |
| **Nfield/Kantar** | `nfieldeu-interviewing.nfieldmr.com` | Welcome -> Blob Audio/Video | 🔄 LEARNING |
| **TolunaStart** | `enter.ipsosinteractive.com` | `cf-radio-answer` class | ✅ VERIFIED |
| **Qualtrics** | various | Matrix/Radio/Dropdown | 🔄 LEARNING |
| **Ipsos** | various | Tab-basiert, nicht modal | 🔄 LEARNING |

**SYSTEMISCHE BLOCKER (2026-05-10):**
- **Cloudflare CAPTCHA** auf ALLEN CPX-Redirects (Cint, Samplicio, etc.) → geo.captcha-delivery.com iframe
- **surveyrouter.com screen-out** nach PureSpectrum checkbox → "keine passende Umfragen"

---

### §11.6 — CHROME & SESSION MANAGEMENT

```
HEYPIGGY WORKFLOW:
1. cp -R "$HOME/Library/Application Support/Google Chrome/Profile 901 (Jeremy)" /tmp/chrome-jeremy-heypiggy-9999
2. nohup "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"      --remote-debugging-port=9999      --remote-allow-origins="*"      --force-renderer-accessibility      --no-first-run      --user-data-dir="/tmp/chrome-jeremy-heypiggy-9999"      "https://www.heypiggy.com/?page=dashboard" &>/dev/null &
3. Cookie-Injection: 7 HeyPiggy-Cookies aus ~/.stealth/heypiggy-backup/heypiggy-cookies.json
   HEYPIGGY-Cookies: PHPSESSID, user_session, user_id, user_a_b_group, lang_pig, g_state, referer
4. Verify: body.innerText contains "abmelden"

SESSION TOT -> WIPE agent-toolbox/data/heypiggy-cookies.json -> Chrome neustarten -> Cookies restaurieren
BOT PID FINDEN: ps aux | grep "Google Chrome" | grep "remote-debugging-port=9999" | grep -v grep | awk '{print $2}'
BOT KILL: pkill -f "remote-debugging-port=9999" -> NUR HeyPiggy Bot
❌ VERBOTEN: pkill -f "Google Chrome" -> killt ALLE Chrome inkl. USER Chrome!
```

---

### §11.7 — IMPLEMENTATION BACKLOG (TODO — 2026-05-10 UPDATE)

```
MASTER PLAN: plans/01-survey-agent-langgraph-fastapi.md
→ Zwei-Layer-System: FastAPI PRIMARY (Intelligence) + CLI SECONDARY (Robustness)
→ LangGraph = Engine, SurveyRunner = deprecated

=== KOMPLETTIERT (2026-05-10) ===
✅ **SR-54: Cookie + Subid + Balance Fix Bundle**
   - Cookie injection in _create_tab() + _open_in_page_modal() — 7 HeyPiggy cookies BEFORE navigation
   - Subid preservation in open_survey() — CPX API URL mit real subid statt intercepted URL
   - Balance reading fix — MAX € value statt first match
   - E2E Verified: Survey 66695822 (Cint→Tivian), Balance €2.70 → €2.75 (+€0.05)
   - Tests: 17/18 + 18/18 + 10/10 passed

✅ **AngularDragDropSolver multi-approach** — 4 sequential approaches (A→B→C→D)
✅ **Session validation** — validate_session() + is_session_valid() in session_validator.py
✅ **Garbage cleanup** — launch_parallel.py, README_PARALLEL.md, tmp_revert_runner.py gelöscht

=== KOMPLETTIERT (2026-05-10 CONTINUED) ===
✅ **SR-55: LangGraph Import Fix + FastAPI Background-Task + Dependencies**
   - LangGraph Import Fix: .venv path injection in graph.py (Zeilen 112-130)
   - Fehlende Dependencies installiert: fastapi, uvicorn, openai, playwright, websocket-client
   - FastAPI Background-Task: `_survey_loop()` in main.py — 24/7 Loop alle 5 Minuten
   - Provider-Trust Scoring: Qualtrics 0.9, Toluna 0.8, Cint 0.7, Samplicio 0.4, PureSpectrum 0.3
   - Graceful Shutdown: `_background_running` Flag + 60s Timeout + cancel()
   - Startup Script: `agent-toolbox/start-api.sh` — venv Python Launcher (NICHT System-Python!)
   - Makefile Targets: `run` (Prod), `dev` (Reload), `start-bg` (Background), `stop-bg`
   - pyproject.toml: fastapi>=0.115, uvicorn>=0.34, langgraph>=0.2, websocket-client>=1.9
   - Refactor: `_scan_dashboard_impl()` in dashboard_routes.py — wiederverwendbar für Endpoint + Background
   - Fix: HTTPException Import in survey_tools.py (Zeile 473)
   - Provider Detection: 8 Provider aus Card-Text (qualtrics, toluna, cint, tivian, nfield, samplicio, purespectrum, ipsos)

=== KOMPLETTIERT (2026-05-11) ===
✅ **FastAPI Endpoints in survey_tools.py — 10 endpoints**
   - POST /survey/open, /close, /fill, /rate, /purespectrum-preflight, /run-graph, /universal
   - POST /survey/snapshot (EXTRACTOR_JS), /completion (keyword detection)
   - POST /survey/fill (2x — SurveyFiller wrapper)
✅ **preflight_check() + require_survey_ready()** — 14-step validation, FastAPI Depends() wrapper
✅ **update_command_registry()** — defined, NOT yet wired (→ SR-50)
✅ **Command Registry** — survey-cli/survey/command_registry.py + command_registry.json
✅ **survey_cli/tools/ 17 tools** — open, fill, snapshot, detect_completion, rate, click, find, verify, etc.
✅ **LangGraph nodes.py refactored** — ensure_chrome, inject_cookies, snapshot_node, decide_node, execute_node, detect_completion
✅ **Cookie injection in opener.py** — _create_tab() + _open_in_page_modal() inject 7 HeyPiggy cookies
✅ **shadow_dom_click()** — purespectrum.py Shadow DOM piercing
✅ **GitHub Issues #44-47** — SR-50/51/52/53 erstellt
✅ **AGENTS.md updated** — OFFEN + Tools-Tabelle + KRITISCHE BLOCKER + Balance

=== KOMPLETTIERT (2026-05-11 continued) ===
✅ **SR-50: update_command_registry() wiring** — alle 9 endpoints rufen registry nach Command auf
✅ **SR-51: require_survey_ready wiring** — alle 9 endpoints haben preflight dependency (8 neu, 2 vorh.)
✅ **SR-52: 7 fehlende FastAPI Endpoints** — POST /click, /find, /verify, /click-angular, /fill-input, /find-tab, /close-modals
✅ **SR-53: Provider Detection + Trust Scores** — scanner.py: surveyrouter.com → "internal", PROVIDER_TRUST_SCORES dict, trust_score in scan output

=== OFFEN (NEXT STEPS) ===

**🔴🔴🔴 HARTE REGEL: KEIN AUTO-RUN bis 100 Surveys MANUELL erfolgreich! 🔴🔴🔴**
→ `answer_survey.py` ist NUR für MANUELLE TESTING — niemals Auto-Run daraus!
→ FastAPI + LangGraph als zentrales Hirn — NICHT monolithisches Script!
→ Jedes Command als separater Endpoint + Tool
→ **PERSISTENT COMMAND REGISTRY**: JSON-Datei trackt ALLE Commands (existiert in `survey-cli/data/command_registry.json`)
→ **PRE-FLIGHT CHECK**: Vor jedem Command — `preflight_check()` + `require_survey_ready()` (BEIDE existieren!)
→ **AUTO-UPDATE**: Nach jedem Erfolg/Fehler — `update_command_registry()` (BEIDE existieren!)
→ **SEQUENTIELL**: Surveys NICHT parallel öffnen — einer nach dem anderen
→ **UNIVERSAL AGENT**: FastAPI + LangGraph soll ALLE Survey-Typen erkennen und bearbeiten — Pre-Qualifier, Provider X/Y/Z, egal was kommt — universal, nicht hardcoded!

PHASE 1 — FastAPI + LangGraph Integration (KOMPLETT):
- [x] survey-cli/tools/ existieren bereits — 17 Tools!
- [x] survey-cli/survey/graph/ existiert — state.py, nodes.py, graph.py, __init__.py
- [x] survey-cli/survey/ opener.py, scanner.py, command_registry.py, session_validator.py existieren
- [x] FastAPI Endpoints in survey_tools.py — 17 endpoints total (10 existing + 7 new SR-52) ✅
- [x] FastAPI Endpoints für 7 fehlende tools → **SR-52** ✅ (click/find/verify/click-angular/fill-input/find-tab/close-modals)
- [x] preflight_check() + require_survey_ready() existieren in survey_tools.py
- [x] require_survey_ready dependency in alle 9 endpoints → **SR-51** ✅
- [x] update_command_registry() existiert in survey_tools.py
- [x] update_command_registry() wiring in alle 9 endpoints → **SR-50** ✅ (open/close/fill/rate/purespectrum-preflight/run-graph/snapshot/completion)
- [x] LangGraph E2E test: 22 NIM decisions on live survey 66695822 ✅

PHASE 2 — Captcha + Drag-Drop Solver + EXTRACTOR_JS integrieren:
- [x] answer_survey.py Captcha Solver (Llama 90B via NVIDIA NIM) — TESTED: "tpyTrD" ✅
- [x] answer_survey.py Drag-Drop Solver (CDP Input.dispatchMouseEvent) — TESTED: "Zahl 28" ✅
- [x] purespectrum.py shadow_dom_click() existiert → nutzen!
- [x] EXTRACTOR_JS 100% Element Capture (survey-cli/survey/snapshot.py, 2026-05-11)
  - Shadow DOM traversal (pierce shadow roots, depth≤5)
  - Angular CDK drag-drop detection (.cdk-drag, .drop-zone, img[alt])
  - HeyPiggy modal buttons (.modal-button-positive/negative)
  - Visual captchas (canvas, img with captcha classes)
  - Images (src, alt, isCaptcha flag) for captcha analysis
  - Iframe content extraction (HeyPiggy embeds surveys in iframes)
  - Cookie consent banner detection
  - CompactSnapshot erweitert: images[], dragPuzzle, captchas[], hasShadowDOM
- [x] Captcha Solver als standalone tool → `survey-cli/tools/tool_solve_captcha.py`
  - Auto-detect type: slide / text / drag / visual / none
  - Text/OCR: screenshot → NVIDIA Vision OCR → type → submit (174 lines)
  - Slide: CDP Bezier trajectory → Input.dispatchMouseEvent (174 lines)
  - Drag: delegates to tool_solve_drag_puzzle.py (delegation pattern)
- [x] Drag-Drop Solver als standalone tool → `survey-cli/tools/tool_solve_drag_puzzle.py`
  - APPROACH B (PRIMARY): CDP Input.dispatchMouseEvent chain
  - Verified: Survey 49517969 (Zahl 28) → 100% ✅ (147 lines)
  - NOT synthetic PointerEvents — Angular CDK ignores those!
- [x] Captcha + Drag-Drop als FastAPI Endpoints → survey_tools.py
  - POST /captcha/solve: auto-detect + solve (text/slide/drag)
  - POST /survey/solve-drag: dedicated Angular CDK solver

PHASE 3 — Command Registry + Pre-Flight:
- [x] preflight_check() in survey_tools.py — 14-step validation
- [x] require_survey_ready() FastAPI Depends() wrapper
- [x] Command Registry: survey-cli/survey/command_registry.py + command_registry.json
- [x] update_command_registry() in survey_tools.py definiert + gewired
- [x] Pre-Flight dependency in alle endpoints → **SR-51** ✅
- [ ] Sequential Survey Opening (nicht parallel!)

PHASE 4 — Provider Detection + Universal Flow:
- [x] Provider Detection in scanner.py → surveyrouter.com = "internal" ✅
- [x] PROVIDER_TRUST_SCORES: Qualtrics 0.9, Toluna 0.8, Cint 0.7, Samplicio 0.4, PureSpectrum 0.3, internal 0.2 → **SR-53** ✅
- [x] Provider Detection in dashboard_routes.py — 8 Provider
- [x] scanner.py filter_surveys() adds trust_score zu allen Entries
- [ ] Universal flow: KEIN provider Hardcode! NEMO-Loop erkennt und handelt
- [ ] Pre-Qualifier detection (surveyrouter-pre-qualifier.md)
- [ ] Completion/Screen-Out detection (universal, nicht provider-spezifisch)

PHASE 5 — /commands/ Lösungen in FastAPI/Endpunkte integrieren:
**REGEL: /commands/ sind KEINE separaten Scripts — sie werden FASTAPI ENDPOINTS!**

Every working /commands/ solution → survey-cli/tools/tool_*.py → FastAPI Endpoint:

| /commands/ | Tool | FastAPI Endpoint | Status |
|-----------|------|------------------|--------|
| bot-chrome/kill-bot-chrome.md | chrome.py:kill_bot() | POST /chrome/kill | ✅ existiert |
| bot-chrome/find-bot-pids.md | chrome.py:find_bot_pids() | POST /chrome/pids | ✅ existiert |
| cua-driver/click.md | tool_click.py | POST /survey/click | ✅ existiert |
| cua-driver/set-value.md | tool_fill_input.py | POST /survey/fill-input | ✅ existiert |
| surveys/survey-start-flow.md | tool_open_survey.py | POST /survey/open | ✅ existiert |
| surveys/purespectrum-survey.md | purespectrum.py + preflight | POST /survey/purespectrum-preflight | ✅ existiert |
| captcha/solve-slide.md | stealth-captcha slide.py | POST /captcha/slide | ❌ MISSING |
| captcha/solve-text.md | stealth-captcha text.py | POST /captcha/text | ❌ MISSING |
| captcha/solve-drag.md | drag_drop_angular.py | POST /survey/solve-drag-puzzle | ❌ MISSING |
| heypiggy/rating-page.md | tool_rate_survey.py | POST /survey/rate | ✅ existiert |

**TODO — FastAPI Endpoints die noch fehlen (2026-05-11):**
1. POST /captcha/slide — Slide Captcha Solver (stealth-captcha/solver/slide.py)
2. POST /captcha/text — Text Captcha Solver (stealth-captcha/solver/text.py)
3. POST /survey/solve-drag-puzzle — Angular CDK Drag-Drop Solver
4. POST /survey/dashboard-scan — Dashboard scanner endpoint (nutzt scanner.py)
5. POST /survey/universal-answer — Universal survey answer (NEMO loop per page)

GITHub ISSUES (#44-47) — ALLE GESCLOSSEN ✅:
- [SR-50](https://github.com/SIN-CLIs/stealth-runner/issues/50): update_command_registry() wiring — ✅ CLOSED
- [SR-51](https://github.com/SIN-CLIs/stealth-runner/issues/51): require_survey_ready wiring — ✅ CLOSED
- [SR-52](https://github.com/SIN-CLIs/stealth-runner/issues/52): 7 fehlende FastAPI Endpoints — ✅ CLOSED
- [SR-53](https://github.com/SIN-CLIs/stealth-runner/issues/53): Provider Detection — ✅ CLOSED

KRITISCHE BLOCKER (2026-05-11):
- [x] **Angular CDK drag-drop SOLVED** — Approach B: CDP Input.dispatchMouseEvent
  - Getestet: "Zahl 28" puzzle bei 66% ✅ → Button enabled, Page advanced
  - Methode: mousePressed → 10× mouseMoved (mit arc offset) → mouseReleased
  - Angular CDK reagiert auf REAL browser-level mouse events (nicht synthetic JS!)
- [x] **Captcha Solver WORKS** — Llama 90B vision für PureSpectrum visual captchas
  - Getestet: "tpyTrD" captcha gelöst ✅
  - Model: meta/llama-3.2-90b-vision-instruct via NVIDIA NIM
  - API: https://integrate.api.nvidia.com/v1/chat/completions
- [x] **Nächste Button Fix VERIFIED** — CDP_SUBMIT_JS mit German patterns ✅
- [x] **Multi-Select Checkbox Fix VERIFIED** — klickt bis zu 4 Checkboxes pro Seite ✅
- [x] **Balance Extraction FIXED** (dashboard_routes.py, 2026-05-11)
  - Problem: HeyPiggy body text hat `0.00\n€\n2.75\n€` (newlines zwischen Zahl und €)
  - Regex `\d+[.,]\d+\s*€` FAILT weil \s nicht newlines matcht
  - Fix: Finde alle `\d+[.,]\d{2}` Nummern, prüfe ob € in den nächsten 50 Zeichen vorkommt → max ≥1.0
  - Getestet: `0.00\n€\n2.75\n€` → `2,75 €` korrekt extrahiert ✅
- [x] **Cookie Timing FIXED** (tool_open_survey.py, 2026-05-11)
  - Problem: `Target.createTarget(survey_url)` navigierte neuen Tab SOFORT
  - Cookies wurden NACH Navigation injiziert → Redirect-Chain ohne Session-Cookies
  - HeyPiggy Completion-Tracking konnte Survey nicht zuordnen → €0 verdient
  - Fix: about:blank → Cookies → Page.navigate (CORRECT ORDER)
  - Matched opener.py `_create_tab()` pattern (hatte es bereits richtig)
- [❌] **Cloudflare CAPTCHA BLOCKIERT alle CPX-Redirects** — SYSTEMISCH
  - Samplicio.us → geo.captcha-delivery.com iframe → body empty → 0 elements
  - s.cint.com → geo.captcha-delivery.com iframe → body empty → 0 elements
  - Status: 🔴 UNRESOLVED — alle CPX-mediated surveys betroffen
  - Workaround: Direkte PureSpectrum surveys (ohne CPX-Redirect) versuchen
- [🔄] **surveyrouter.com screen-out** — "keine passende Umfragen" nach PureSpectrum
  - Cookie Timing Fix (tool_open_survey.py) sollte helfen — noch NICHT live getestet
  - Vermutung: Session-Cookies oder Subid-Tracking funktioniert nicht über den Chain
  - Fix: Blank Tab + 7 Cookies + Page.navigate (tool_open_survey.py, committed 2026-05-11)
  - Status: 🔄 UNTESTED — braucht live E2E test
- [❌] **Shadow DOM Element-Erfassung** — FIXED 2026-05-11
  - Problem: EXTRACTOR_JS erfasste NUR Normal-DOM, Shadow DOM (PureSpectrum) war blind
  - Fix: Shadow DOM traversal in EXTRACTOR_JS — walk shadowRoot recursively (depth���5)
  - Auch: Angular CDK drag-drop detection, HeyPiggy modal buttons, Captcha images, Iframes

BALANCE TARGET (€5.00):
- [x] Balance Extraction FIXED (newlines between amount and €) → 2,75 € now read correctly
- [x] Cookie Timing FIXED in tool_open_survey.py → session cookies before navigation
- [ ] Live E2E test needed to verify balance increases after cookie fix
- [ ] Mehr Surveys completieren → Balance €2.75 → €5.00

**Balance: €2.75** (2026-05-11, unverändert — kein Live-Test seit Fixes)
- Survey 66695822 (Cint→Tivian) → +€0.05 ✅ (Cookie+Subid Fix verifiziert, 2026-05-10)
- Survey 67078106 (Cint) → completed ✅ but €0 (CPX redirect → Cloudflare?)
- Survey 66910983 (PureSpectrum) → 66% stuck (drag-drop, 2026-05-09)
- Survey 49517969 (PureSpectrum) → screen-out €0
- Survey 67064749 (PureSpectrum) → screen-out €0
- Survey 67064991 (PureSpectrum) → screen-out €0
- **Fixes committed (2026-05-11):** balance extraction (newlines), cookie timing (blank→cookies→navigate)
- **Nächster Test:** Open survey → complete → verify balance increases

EXISTIERENDE TOOLS (survey-cli/tools/) — ALS FASTAPI ENDPOINTS (21 total — ALLE ✅):
**REGEL: Keine Datei darf 300 Zeilen haben! (>300 = bad practices, nicht best practices!)**
Alle neuen Tools unter 300 Zeilen: tool_solve_captcha (174L), tool_solve_drag_puzzle (147L), tool_scan_dashboard (176L), tool_universal_answer (216L).

**Bestehende (10):**
| Tool | Endpoint | SR |
|------|----------|-----|
| tool_open_survey.py | POST /survey/open | ✅ |
| tool_fill_survey.py | POST /survey/fill (2x!) | ✅ |
| tool_snapshot.py | POST /survey/snapshot | ✅ |
| tool_detect_completion.py | POST /survey/completion | ✅ |
| tool_rate_survey.py | POST /survey/rate | ✅ |
| tool_purespectrum_preflight | POST /survey/purespectrum-preflight | ✅ |
| tool_run_graph | POST /survey/run-graph | ✅ |
| tool_universal | POST /survey/universal | ✅ |

**SR-52 (7):**
| Tool | Endpoint |
|------|----------|
| tool_click.py | POST /survey/click |
| tool_find_element.py | POST /survey/find |
| tool_verify_state.py | POST /survey/verify |
| tool_click_angular.py | POST /survey/click-angular |
| tool_fill_input.py | POST /survey/fill-input |
| tool_find_new_tab.py | POST /survey/find-tab |
| tool_close_modals.py | POST /survey/close-modals |

**NEU 2026-05-11 (4):**
| Tool | Lines | Endpoint | Funktion |
|------|-------|----------|----------|
| tool_solve_captcha.py | 174 | POST /captcha/solve | Auto-detect type → text(OCR)/slide(CDP trajectory)/drag(delegation) |
| tool_solve_drag_puzzle.py | 147 | POST /survey/solve-drag | Angular CDK drag-drop via CDP mouse events (APPROACH B, verified) |
| tool_scan_dashboard.py | 176 | POST /survey/scan | Dashboard scanner + provider detection + trust scores |
| tool_universal_answer.py | 216 | POST /survey/answer | DOM-based universal answerer (radio/checkbox/text/select/NPS/matrix) |

**Alle 21 Endpoints haben:** `dependencies=[Depends(require_survey_ready)]` + `update_command_registry()` ✅

GARBAGE LOESCHEN (SOFORT):
- [x] plan.md (root) -> GELOESCHT
- [x] survey-cli/plan.md -> GELOESCHT
- [x] plans/01-canonical-engine.md -> GELOESCHT
- [x] plan-sr-30-dashboard-poller.md -> GELOESCHT
- [x] plan-sr-31-fctes-promotion.md -> GELOESCHT
- [x] plan-sr-28-cdp-survey-module.md -> GELOESCHT
- [x] launch_parallel.py -> GELOESCHT
- [x] README_PARALLEL.md -> GELOESCHT
- [x] tmp_revert_runner.py -> GELOESCHT
```

---

### §11.8 — KEY FILE REFERENCES

```
CHROME START         -> AGENTS.md REGELN 1-4
SURVEY OPEN          -> survey-cli/tools/tool_open_survey.py + AGENTS.md SURVEY FLOW
LANGGRAPH AGENT      -> survey-cli/survey/graph/ (state.py, nodes.py, graph.py, opencode_tool.py, __init__.py)
CAPTCHA SOLVE        -> stealth-captcha/src/stealth_captcha/cli.py + purespectrum.py
DRAG PUZZLE          -> stealth-captcha/solver/drag_drop_angular.py -> 🔄 Multi-approach (A→B→C→D), awaiting E2E
NEMO LOOP            -> survey-cli/survey.py + AGENTS.md NEMO ARCHITEKTUR
FASTAPI              -> agent-toolbox/api/survey_tools.py
COMMANDS             -> /commands/cmd-rules.md + /commands/surveys/*.md
BANNED               -> banned.md + sinrules.md §BANNED
NVIDIA VISION        -> stealth-captcha/src/stealth_captcha/solver/text.py:PixtralCaptchaBackend
SURVEY TYPES         -> AGENTS.md §8 SURVEY TYP KATALOG
TOOL REGISTRY        -> opencode.json (tool Manifest + Tool Registration)
ENV CREDENTIALS      -> NVIDIA_API_KEY, Chrome Binary, Profile 901, CDP 9999, API 8889
```

---

### §12 — LANGGRAPH SURVEY AGENT (2026-05-10, NEW)

**Architektur: survey-cli/survey/graph/ — LangGraph StateGraph für Survey-Orchestration**

```
survey-cli/survey/graph/
├── __init__.py          ← PUBLIC API (SurveyState, create_graph, etc.)
├── state.py             ← SurveyState: zentrales GraphState
├── nodes.py             ← 8 Graph Nodes (jede ≤30 Zeilen)
├── graph.py             ← StateGraph Builder + route() Routing-Funktion
└── opencode_tool.py     ← CLI Delegation bei 3× Failures

5 FILES: state.py (170L) → nodes.py (280L) → graph.py (160L) → opencode_tool.py (150L) → __init__.py (120L) = ~880L total
```

#### §12.1 — File-Übersicht

| File | Zeilen | Zweck |
|------|--------|-------|
| `state.py` | 170 | SurveyState dataclass — alle Session-Daten |
| `nodes.py` | 280 | 8 Graph Nodes — jede ≤30 Zeilen |
| `graph.py` | 160 | StateGraph Builder + route() Routing |
| `opencode_tool.py` | 150 | opencode CLI Delegation |
| `__init__.py` | 120 | Public API + SurveyGraphError |

#### §12.2 — SurveyState (state.py)

**Zentrales State-Objekt — ALLE Session-Daten in EINER dataclass.**

```python
@dataclass
class SurveyState:
    # Input (set at creation)
    survey_id: str = ""           # HeyPiggy Survey-ID
    provider: str = ""            # Provider Name (purespectrum, etc.)
    cdp_port: int = 9999          # HeyPiggy Chrome Port
    dashboard_ws: Optional[str] = None  # Dashboard Tab WebSocket

    # Computed (set during execution)
    tab_ws: Optional[str] = None  # Survey Tab WebSocket
    cookies_injected: bool = False  # KRITISCH: heypiggy-Cookies injiziert?
    iteration: int = 0            # NEMO-Loop Zähler (0-indexed)
    max_iterations: int = 15      # Safety-Net gegen Endlos-Loop
    consecutive_failures: int = 0 # 3× → delegate
    balance_before: float = 0.0   # Guthaben VOR Session
    balance_after: float = 0.0    # Guthaben NACH Session
    status: str = "initialized"   # Workflow-Status
    errors: List[Dict] = []       # Fehler-Historie
    snapshot_refs: Dict = {}      # @eN Element-Referenzen
    nim_actions: List[Dict] = []  # NIM-Entscheidungen
    batch_result: Optional[Dict] = None  # Batch Execution Result
    completion_detected: bool = False  # Survey fertig?
    screen_out: bool = False      # Disqualifiziert?
    delegation_reason: str = ""   # Warum delegiert?
```

**Status-Flow:**
```
initialized → chrome_ready → tab_open → cookies_injected → running
                                                              ↓
                          completed ← ← ← ← ← ← ← ← ← ← ← ← ┘
                          screen_out ← ← ← ← ← ← ← ← ← ← ← ┘
                          error ← ← ← ← ← ← ← ← ← ← ← ← ← ┘
                          delegated ← ← ← ← ← ← ← ← ← ← ← ┘
```

**Key Properties:**
- `is_running`: True wenn nicht in terminal state
- `should_delegate`: True wenn consecutive_failures >= 3
- `balance_earned`: balance_after - balance_before

#### §12.3 — 8 Graph Nodes (nodes.py)

**Jede Node ≤30 Zeilen, wrapped existierende Funktion, NUR delegate + state update.**

| Node | Wrapped | Zweck |
|------|---------|-------|
| `ensure_chrome` | ChromeLauncher.launch_and_verify() | Chrome starten/verifizieren |
| `open_survey` | SurveyOpener.open() | Survey-Tab öffnen |
| `inject_cookies` | CDP Network.setCookies | 7 Heypiggy-Cookies injizieren |
| `snapshot_node` | CDP Runtime.evaluate (inline JS) | Compact DOM-Snapshot |
| `decide_node` | NIM SurveyClient.decide() | NIM Nemotron Decision |
| `execute_node` | BatchExecutor.execute() | Batch-Ausführung via CDP |
| `detect_completion` | CompletionDetector.detect_ws() | Completion/Screen-Out detectieren |
| `human_delegate` | opencode_tool.delegate_task() | An opencode CLI eskalieren |

**Cookie-Injection (inject_cookies Node) — ROOT CAUSE FIX (2026-05-09):**
```
Problem: Survey-Tabs via Target.createTarget haben KEINE Session-Cookies
         → CPX redirectiert zurück zum Dashboard → €0 verdient
Fix:     7 Heypiggy-Cookies nach Tab-Erstellung injizieren:
         ~/.stealth/heypiggy-backup/heypiggy-cookies.json
         → Network.setCookies (Batch in einem Call)
         → cookies_injected=True
7 Heypiggy-Cookies:
  - PHPSESSID      → www.heypiggy.com (KRITISCH!)
  - user_session   → www.heypiggy.com (KRITISCH!)
  - user_id        → www.heypiggy.com
  - user_a_b_group → www.heypiggy.com
  - lang_pig       → www.heypiggy.com
  - g_state        → www.heypiggy.com
  - referer        → www.heypiggy.com
```

#### §12.4 — StateGraph Builder (graph.py)

**Graph-Struktur mit Conditional Edges:**

```
START
  │
  ▼
ensure_chrome ──→ [error] ──────────────────────────── END
  │
  ▼
open_survey ────→ [screen_out] ────────────────────── END
  │              └──→ [error] ─────────────────────── END
  ▼
inject_cookies ──→ [error] ─────────────────────────── END
  │
  ▼
snapshot ───────────────────────────────────────────┐
  │                                                │
  ▼                                                │
decide ─────────────────────────────────────────────┤
  │                                                │
  ▼                                                │
execute ────────────────────────────────────────────┤
  │                                                │
  ▼                                                │
detect_completion ──→ [completed/screen_out] ─────── END
  │
  ▼
ROUTE (conditional):
  ├─ should_delegate (3× failures) ──→ human_delegate ──→ END
  ├─ iteration >= max_iterations ────→ END
  └─ else ────────────────────────────→ snapshot (continue)
```

**Routing-Priority (route() Funktion):**
```
1. is_terminal (completed/error/delegated/screen_out) → END
2. should_delegate (consecutive_failures >= 3) → human_delegate
3. iteration >= max_iterations → END
4. else → "snapshot" (continue NEMO Loop)
```

**WARUM diese Reihenfolge?**
- Terminal zuerst → kein Loop nötig wenn fertig
- Delegate vor Iteration → echte Probleme zuerst eskalieren
- Iteration-Limit als Safety-Net → verhindert Endlos-Loop

#### §12.5 — opencode CLI Delegation (opencode_tool.py)

**Trigger: consecutive_failures >= 3**

```bash
opencode run --format json --dir /Users/jeremy/dev/stealth-runner \
  --prompt "Fix survey 67064749 (provider=purespectrum):
   Root cause: Angular CDK Drag-Drop Puzzle bei 66% Fortschritt.
   Tab: ws://127.0.0.1:9999/devtools/page/...
   Iteration: 4 (4× execute versucht, 0× Erfolg)
   Action: Implementiere PointerEvent-Lösung aus AGENTS.md §11.3
   Goal: Complete survey and verify balance increased."
```

**Timeout: 300 Sekunden (5 Minuten)**
Override via `OPENCODE_TIMEOUT` env var.

**Delegation-Prompt enthält:**
1. Survey-ID + Provider
2. Root Cause + reason
3. Tab-WS URL
4. Iteration + was versucht wurde
5. Anweisung was zu tun ist
6. AGENTS.md Referenzen

#### §12.6 — Öffentliche API

```python
from survey_cli.survey.graph import (
    SurveyState,        # State-Objekt
    create_graph,       # Kompilierter Graph (invoke-able)
    run_survey_loop,    # Standalone Loop (ohne LangGraph)
    delegate_task,      # opencode CLI Delegation
    SurveyGraphError,   # Exception Klasse
)

# Pattern 1: LangGraph Pipeline (Production)
graph = create_graph()
state = SurveyState(survey_id="67064749", provider="purespectrum")
final = graph.invoke(state)
print(f"Status: {final.status}, Earned: €{final.balance_earned}")

# Pattern 2: Standalone Loop (Fallback, keine LangGraph nötig)
state = SurveyState(survey_id="67064749", provider="purespectrum")
final = run_survey_loop(state)
print(f"Status: {final.status}")

# Pattern 3: Einzelne Nodes (für Testing)
from survey_cli.survey.graph.nodes import ensure_chrome
state = ensure_chrome(SurveyState(cdp_port=9999))
print(f"Chrome: {state.dashboard_ws}")
```

**LangGraph Requirement:**
- `create_graph()` und `build_graph()` brauchen LangGraph
- `run_survey_loop()` funktioniert als Fallback OHNE LangGraph
- `pip install langgraph` für Production

#### §12.7 — Integration in FastAPI

```python
from survey_cli.survey.graph import create_graph, SurveyState

@router.post("/survey/run")
async def run_survey(req: SurveyRequest):
    graph = create_graph()
    state = SurveyState(survey_id=req.survey_id, provider=req.provider)
    result = await asyncio.to_thread(graph.invoke, state)
    return {
        "status": result.status,
        "earned": result.balance_earned,
        "errors": result.errors,
        "delegation": result.delegation_reason,
    }
```

#### §12.8 — TESTING

```bash
# Node-Einzeltests
cd /Users/jeremy/dev/stealth-runner/survey-cli
python3 -c "
from survey.graph import SurveyState, run_survey_loop
state = SurveyState(survey_id='67064749', provider='purespectrum', cdp_port=9999)
final = run_survey_loop(state)
print(f'Status: {final.status}, Errors: {len(final.errors)}')
"

# Standalone node test
python3 -c "
from survey.graph.nodes import ensure_chrome, snapshot_node
state = ensure_chrome(SurveyState(cdp_port=9999))
print(f'Dashboard WS: {state.dashboard_ws}')
"
```

#### §12.9 — FCTC-ES PROMOTION (TODO: nach 10× Erfolg)

```
survey-cli/survey/graph/compiled/
├── survey_graph_v1746800000.py  ← nach 10× Erfolg automatisch generiert
├── registry.json                ← Tool Registration Source of Truth
└── __init__.py                  ← frozen=True, chmod 444
```

**Promotion-Criteria:**
1. 10× erfolgreich (balance_after > balance_before)
2. 0× delegated (consecutive_failures < 3 in allen Runs)
3. Keine errors in state.errors

---

---

## §13 — PROFIL-MAPPING & NIM-PARSER-REGRESSION (2026-05-11)

### §13.1 — Was wurde geaendert (WHY)

**Problem:** `decide_node` Heuristik 2b (survey-cli/survey/graph/nodes.py) hat
JEDE leere `textbox / searchbox / spinbutton` mit `profile["city"]` gefuellt
(Fallback "Berlin"). Effekt in Live-Runs:

- E-Mail-Feld bekam `"Berlin"` → instant Validation-Error
- PLZ-Feld bekam `"Berlin"` → instant Screen-Out
- Geburtsjahr-Feld bekam `"Berlin"` → instant Screen-Out
- → LLM-Fallback wurde im naechsten Tick getriggert (teuer, langsam,
  manchmal `complete=true` falsch positiv)

**Fix:** Neuer `ProfileLoader.match_field(role, name, profile, placeholder)`
in `survey-cli/survey/profile_loader.py`. Heuristik 2b ruft jetzt diesen
Matcher; bei `None` SKIPPT die Heuristik das Feld und der LLM-Tick uebernimmt.

### §13.2 — Wo der Code lebt (WHERE)

| Datei | Funktion / Zeile | Zweck |
|---|---|---|
| `survey-cli/survey/profile_loader.py` | `ProfileLoader.match_field` | DE/EN-Keyword-Matcher Label → Profilwert |
| `survey-cli/survey/profile_loader.py` | `_normalize`, `_FIELD_PATTERNS` | Lowercase + Umlaut-Folding; Keyword-Familien |
| `survey-cli/survey/graph/nodes.py` (Heuristik 2b, ~Zeile 449-) | `decide_node` | Ruft `ProfileLoader.match_field` statt `profile["city"]` |
| `survey-cli/tests/test_profile_match_field.py` | Unit-Tests | 70+ Cases pro Keyword-Familie |
| `survey-cli/tests/test_nim_parse_response.py` | Regression-Tests | NIM `parse_response()` gegen echte + kaputte Outputs |

### §13.3 — Keyword-Familien (KANONISCH, NICHT AENDERN OHNE TEST!)

Jeder Treffer ist `substring auf normalisiertem name/placeholder`. Reihenfolge
= Prioritaet (erstes Match gewinnt). Bei Erweiterung IMMER:

1. Pattern in `_FIELD_PATTERNS` ergaenzen
2. Test-Case in `test_profile_match_field.py::TestMatchField` hinzufuegen
3. Hier in §13.3 Tabelle eintragen

| Familie | Profil-Key(s) | DE-Keywords | EN-Keywords | Format |
|---|---|---|---|---|
| `email` | `email` | mail, e-mail, email | email, e-mail | raw string |
| `birth_year` | `birth_year`, `geburtsjahr` | geburtsjahr, jahr der geburt | birth year, year of birth | 4-digit string |
| `age` | `age`, `alter` | alter, lebensjahre | age | int → string |
| `postal_code` | `postal_code`, `plz`, `zip` | plz, postleitzahl | zip, postal code, postcode | string |
| `city` | `city`, `stadt`, `ort`, `wohnort` | stadt, ort, wohnort | city, town | string |
| `street` | `street`, `strasse` | strasse, straße | street, address line | string |
| `house_number` | `house_number`, `hausnummer` | hausnummer, nr | house number, house no | string |
| `phone` | `phone`, `telefon`, `mobile` | telefon, handy, mobil | phone, mobile, cell | string |
| `name_first` | `first_name`, `vorname` | vorname | first name, given name | string |
| `name_last` | `last_name`, `nachname`, `surname` | nachname, familienname | last name, surname, family name | string |
| `name_full` | `name`, `full_name` | name (ohne vor/nach) | name, full name | string |
| `household_size` | `household_size`, `haushaltsgroesse` | haushaltsgr, personen im haushalt | household size, persons in household | int → string |
| `income` | `income`, `einkommen` | einkommen, haushaltseinkommen | income, household income | int → string |
| `country` | `country`, `land` | land, herkunftsland | country | string |
| `gender` | `gender`, `geschlecht` | geschlecht | gender, sex | string |

**Default:** Wenn KEIN Pattern matcht → `match_field` returnt `None`.
Heuristik 2b SKIPPT dann das Feld → LLM-Tick im naechsten Round.
**NIEMALS** `profile["city"]` als Default zurueckgeben — das war der Bug.

### §13.4 — NIM-Parser-Regression (parse_response)

Datei: `survey-cli/tests/test_nim_parse_response.py`

Deckt ab (Black-Box, kein Mock):

- **Valides JSON:** `{"actions":[{"action":"click","stable_id":"x"}]}`
- **Markdown-Fences:** ` ```json\n{...}\n``` `
- **Mehrere Aktionen:** `actions: [...]` mit 2-3 Items
- **Wait/Submit Contract:** parser respektiert `action=wait`, `action=submit`
- **Complete-Flag:** `{"complete": true}` → parser propagiert
- **Kaputte Inputs:**
  - leerer String, None, " "
  - kaputtes JSON (`{...broken`)
  - `actions: []` (leeres Array)
  - LLM-Geschwafel (Plain Text, kein JSON)
  - Halbes JSON (`{"actions":[{"action"`)
- **Idempotenz:** `parse(parse(x))` raised nicht
- **Fallback-Contract:** Wenn parser nichts findet, returnt Fallback-Item mit
  `action`-Key (decide_node interpretiert das dann).

**Regression-Pflicht:** Bei jeder Aenderung an `nim.parse_response`:
1. Test ausfuehren: `python -m unittest tests.test_nim_parse_response`
2. Wenn neue Edge-Cases auftauchen (z.B. neuer LLM gibt andere Whitespace-
   Patterns aus): Case in §13.4 + Test-Datei ergaenzen
3. NIEMALS Test loeschen ohne Issue-Verweis im Commit-Msg.

### §13.5 — Wie testen (RUN)

```bash
cd survey-cli
uv venv && source .venv/bin/activate
uv pip install openai   # nur fuer test_nim.py noetig
python -m unittest tests.test_profile_match_field tests.test_nim_parse_response
# Erwartet: Ran 94 tests in <1s — OK
```

### §13.6 — Beruehrte Dateien (DELTA 2026-05-11)

```
M  survey-cli/survey/graph/nodes.py            (Heuristik 2b: city → match_field)
M  survey-cli/survey/profile_loader.py         (+ ProfileLoader.match_field, _FIELD_PATTERNS, _normalize)
A  survey-cli/tests/test_profile_match_field.py (NEU: 70+ Cases)
A  survey-cli/tests/test_nim_parse_response.py  (NEU: 24+ Cases)
M  AGENTS.md                                   (+ §13)
```

### §13.7 — Nicht-Ziele (NON-GOALS)

- Keine LLM-Integration im Matcher (rein deterministisch — schnell, testbar)
- Kein Fuzzy-Matching (Levenshtein) — Keyword-Substring reicht und ist
  vorhersagbar
- Kein Lernen aus vergangenen Runs (gehoert in §12 FCTC-ES, nicht in den
  Matcher)
- Matcher gibt NIEMALS `"Berlin"` als Default-Fallback aus

### §13.8 — Offene Follow-Ups (Issue-Tracking, kanonisch)

Diese Issues bilden die Roadmap fuer §13 + angrenzende Themen. Bei
Abarbeitung jeweils Issue-Nummer im Commit-Msg referenzieren (`fixes #48`)
und hier den Status updaten (`OPEN`, `IN PROGRESS`, `DONE <commit>`).

| # | Titel | Status | Abhaengt von |
|---|---|---|---|
| [#48](https://github.com/SIN-CLIs/stealth-runner/issues/48) | SR-50: test_nim.py — Asserts an parse_response Contract alignen | OPEN | — |
| [#49](https://github.com/SIN-CLIs/stealth-runner/issues/49) | SR-51: E2E-Smoke fuer ProfileLoader.match_field gegen echte Survey | OPEN | — |
| [#50](https://github.com/SIN-CLIs/stealth-runner/issues/50) | SR-52: Combobox-Doppelbehandlung in decide_node 2b | OPEN | — |
| [#51](https://github.com/SIN-CLIs/stealth-runner/issues/51) | SR-53: Profile-Schema erweitern (household_size, income, gender, country, phone, first/last_name) | OPEN | — |
| [#52](https://github.com/SIN-CLIs/stealth-runner/issues/52) | SR-54: Matcher-Telemetrie — Hit/Miss-Counter pro Keyword-Familie | OPEN | #49 |
| [#53](https://github.com/SIN-CLIs/stealth-runner/issues/53) | SR-55: §12 FCTC-ES Lernschleife — Matcher-Miss → Pattern-Vorschlag | OPEN | #49, #52 |

**Pflicht:** Jedes weitere Follow-Up zu §13 → erst Issue anlegen, dann
diese Tabelle ergaenzen. KEINE Tickets in separaten .md-Dateien oder
externen Tools — die Roadmap lebt im Agenten-Brain.

---

**Letzte Aktualisierung: 2026-05-11 | Lines: ~2060 + §12 + §13 (incl §13.8) | Plan: plans/01-survey-agent-langgraph-fastapi.md**

