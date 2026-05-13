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

  ---

  ##  SR-173 (#178) -- Visual Debug Report -- BRAIN-FILE-SECTION

  > **Was**\: HTML+SVG-Overlay-Report PRO Step (sampled). Macht die 4
  > Koordinaten-Bugs in 5 Sekunden statt 15 Minuten sichtbar.
  > **Status**\: implemented on branch `feat/sr-173-visual-debug` (PR-Phase).
  > **Tests**\: 12/12 green on Python 3.13 (`tests/test_visual_debug.py`).

  ### Warum dieses Feature existiert
  Vor SR-173 mussten wir aus JSONL-Events rekonstruieren, WO der Agent ein
  Element vermutete vs. WO es real auf dem Screen war. Dauer\: 15 min pro
  Vorfall. Mit dem Visual-Debug-Report sieht ein Mensch in 5 s welcher der
  vier Bug-Klassen vorliegt\:

  1. **iFrame-Offset-Bug**\: AX-Tree liefert iframe-LOKALE Koords; Click braucht
     PAGE-Koords. Fehlt der `frame_offset`-Add, klicken wir um (frame_x,frame_y)
     Pixel daneben. Pollfish/Cint/Lucid sind alle iframe-embedded. #1 Bug.
  2. **DPR-Mismatch (HiDPI/Zoom)**\: Screenshot ist physical px, AX-Tree ist CSS
     px. Ohne DPR-Skalierung zeichnet das Rect auf halber Größe an der
     falschen Stelle.
  3. **Scroll-Offset stale**\: Snapshot bei scrollY=300, Click 200 ms später
     bei scrollY=400. Click landet 100 px unter dem visuellen Element.
  4. **Overlay z-index**\: AX-Tree sagt `visible`, aber ein Modal mit
     z-index 9999 sitzt drüber. AX-Tree allein kann das nicht erkennen --
     visuell sieht man es sofort.

  ### Dateilandkarte (Single-Source-of-Truth für SR-173)
  ```
  survey-cli/
    survey/
      runner_policy.py                 # NEW: zentrale, immutable Runtime-Policy
                                       #      (env-driven; STEALTH_ENV, VISUAL_DEBUG_*)
      safe_executor.py                 # PATCHED: optionaler Hook nach jeder Aktion
                                       #          (visual_debug_dispatcher +
                                       #          visual_debug_frame_builder)
      observability/
        __init__.py                    # PATCHED: re-exports VisualDebug* API
        visual_debug.py                # NEW: Kernmodul -- Renderer + Dispatcher
                                       #      + Geometry-Primitives (Point/Box/ElementRef)
                                       #      + Protocol-Shims für SR-167/168
    tests/
      test_visual_debug.py             # NEW: 12 Tests; 1 pro Bug-Klasse +
                                       #      Determinismus, Atomicity, Backpressure,
                                       #      End-to-End-Dispatcher
  scripts/
    build_daily_visual_report.py       # NEW: Daily-Aggregator: erzeugt index.html
                                       #      pro Tag; optional Vercel-Blob-Upload
  ```

  ### State-of-the-Art Entscheidungen (mit Begründung)
  - **`ThreadPoolExecutor`, NICHT `asyncio.create_task`**\:
    `safe_executor.SurveyFlowExecutor` ist SYNC (siehe Modul-Docstring\:
    "synchronous websocket ... matches LangGraph node execution"). Es gibt
    keinen laufenden Event-Loop. ThreadPool mit bounded Semaphore ist die
    korrekte Primitive\: non-blocking submit, drop-on-overflow, atexit-clean.
  - **Bounded Queue + DROP-OLDEST**\:
    `threading.BoundedSemaphore(max_queue)`. Wenn voll\: Frame wird
    DROPPED + Warning geloggt. Hot-Path-Latenz ist NIE an Render-Throughput
    gekoppelt -- die zentrale SR-173 Invariante.
  - **Deterministische Sampling**\:
    `blake2b(step_id)[:4] % 10_000 < rate*10_000`. Gleiche step_id → gleiche
    Entscheidung über Retries. Verhindert Double-Counting in Dashboards.
  - **Failure-Override**\:
    `visual_debug_on_failure=True` (Default) zwingt Render bei verifier-fail
    UNABHÄNGIG vom Sample-Rate. SLO\: "kein gescheiterter Step ohne
    Postmortem-Evidenz".
  - **Atomic-Write**\:
    `<final>.<uuid>.tmp` + `os.replace()`. POSIX-atomic; Windows seit Py 3.3.
    Kein Reader sieht halb-geschriebenes HTML.
  - **Selbstenthaltenes HTML**\:
    Bild als `data:image/jpeg;base64,`-URL. Kein Jinja, kein externes CSS,
    kein remote `<img src>`. Test `test_html_is_self_contained_and_under_budget`
    enforce-t das.
  - **JPEG@70 mit Auto-Shrink**\:
    Render-Loop\: q=70 → 60 → ... → 10 bis <= max_kb. ~30 KB pro 1280x720
    in der Praxis. Budget\: 500 KB pro File hart, Warnung bei Überschreitung.
  - **Frozen Dataclasses**\:
    `VisualDebugFrame`, `Point`, `Box`, `ElementRef`, `RunnerPolicy` sind alle
    `frozen=True, slots=True`. Thread-safe by construction; kein Locking.
  - **Protocol-Shims statt harte Imports**\:
    SR-167 (`VerificationResult`) und SR-168 (`AttestationResult`) sind noch
    nicht in main. Wir definieren `runtime_checkable` Protocols mit identischer
    Field-Shape. Sobald die PRs landen\: 1-Zeilen-Swap der Imports, kein
    Runtime-Change.
  - **`from_env()` mit Clamping**\:
    Alle Env-Var-Parser haben `lo`/`hi` Clamps. Kaputte Env-Werte → Default.
    Kein silent-NaN-injection.

  ### Konfiguration (Env-Variablen)
  ```
  STEALTH_ENV               = prod | staging | dev           (default\: dev)
  VISUAL_DEBUG_SAMPLE_RATE  = 0.0 .. 1.0                     (prod\: 0.10)
  VISUAL_DEBUG_ON_FAILURE   = true | false                   (default\: true)
  VISUAL_DEBUG_OUTPUT_DIR   = absolute path                  (default\: ./debug-reports)
  VISUAL_DEBUG_MAX_QUEUE    = int >= 1                       (default\: 128)
  VISUAL_DEBUG_WORKERS      = int >= 1                       (default\: 2)
  VISUAL_DEBUG_JPEG_QUALITY = 1 .. 95                        (default\: 70)
  VISUAL_DEBUG_MAX_KB       = >= 50                          (default\: 500)
  BLOB_READ_WRITE_TOKEN     = Vercel Blob token              (optional, nur für --upload)
  ```

  ### Public-API (was Caller importieren)
  ```python
  from survey.runner_policy import RunnerPolicy
  from survey.observability import (
      VisualDebugDispatcher, VisualDebugFrame,
      ElementRef, Box, Point,
      dispatcher_scope, element_bbox_in_page_coords, render_html_report,
  )

  policy = RunnerPolicy.from_env()
  with dispatcher_scope(policy) as visdbg:
      executor = SurveyFlowExecutor(
          tab_id=tab,
          visual_debug_dispatcher=visdbg,
          visual_debug_frame_builder=build_frame,  # caller-defined
      )
      executor.execute_actions(actions)
  ```

  ### Wann erweitern (Roadmap-Hooks)
  - **SR-167 (#173) merged**\: in `visual_debug.py` ersetze
    `class VerificationResultLike(Protocol)` durch
    `from survey.reliability.verifier import VerificationResult`. Type-Alias
    behalten\: `VerificationResultLike = VerificationResult` falls Downstream-
    Code den Shim referenziert.
  - **SR-168 (#174) merged**\: analog für `AttestationResultLike`. Plus\:
    `network_pending_at_click` field in die Daten-Quelle einhängen
    (gelangt heute schon durch -- braucht nur den Producer).
  - **SR-172 (#172) meta-tracker**\: nach Merge dieses PRs Checkbox abhaken.

  ### NIEMALS in SR-173-Code
  - Synchron blockierende Render-Aufrufe im Hot Path
  - Schreiben auf den finalen Pfad ohne `.tmp + os.replace`
  - Hardcoded Sample-Rate / Output-Dir (alle via `RunnerPolicy`)
  - Externes Asset im HTML (`<link rel="stylesheet">` / remote `<img src>`)
  - Verwendung von `random.random()` für Sampling (Determinismus-Verletzung)
  - Promote `Point`/`Box`/`ElementRef` in `snapshot.py` BEVOR ein zweiter
    Caller sie braucht (YAGNI -- aktueller Single-Caller ist visual_debug)

  ### Test-Matrix (executable specification)
  - `test_iframe_offset_bbox_lands_in_page_coords`  -- Bug-Klasse 1
  - `test_dpr_mismatch_overlay_scales_to_screenshot` (DPR 1.0/1.5/2.0) -- Klasse 2
  - `test_scroll_offset_is_reported_in_side_panel` -- Klasse 3
  - `test_zindex_overlay_warning_is_rendered`      -- Klasse 4
  - `test_sampling_is_deterministic_per_step_id`   -- 1000-id distribution check
  - `test_on_failure_always_renders_when_policy_enabled`
  - `test_render_is_atomic_via_temp_then_replace`
  - `test_html_is_self_contained_and_under_budget` (500 KB hard cap)
  - `test_dispatcher_drops_when_queue_full`        -- Backpressure
  - `test_dispatcher_writes_file_end_to_end`       -- E2E mit Verifier-FAIL

  ### Operations
  - **Daily**\: `python scripts/build_daily_visual_report.py --date YYYY-MM-DD`
    erzeugt `<output_dir>/<date>/index.html` mit Filter-Buttons OK/FAIL.
  - **Mit Upload**\: `BLOB_READ_WRITE_TOKEN=... build_daily_visual_report.py --upload`
    lädt alle Step-Files + Index zu Vercel Blob, gibt index-URL auf stdout.
  - **Cleanup**\: Retention liegt beim Vercel-Blob-Bucket-Policy (empfohlen\: 30 d).

  ### Kosten-Budget (PR-Review-Defense)
  - Frame-Größe\: ~30 KB JPEG@70 + ~5 KB SVG/HTML/JSON = ~35 KB
  - Prod-Sampling\: 10 % aller Steps + 100 % aller Failures
  - Erwartete Steps/Tag\: 10 000 → ~1 500 Renders/Tag → ~50 MB/Tag
  - Vercel Blob $0.30/GB/Monat → ~$0.45/Monat. Trivial.

  ---

