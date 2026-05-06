# AGENTS.md – Stealth-Runner NEXT-GEN (2026-05-06)

> **← [sinrules.md](sinrules.md) ist das zentrale Regelwerk. Alle Golden Rules sind DORT.**
> **← [brain.md](brain.md) dokumentiert die Architektur im Detail.**
> **← [registry.md](registry.md) ist der Master Command Index.**
>
> **BAN REGELN** (siehe [sinrules.md#6](sinrules.md) für Details):
> - `webauto-nodriver` = ABSOLUT BANNED
> - CDP = NUR für JS execute/evaluate, BANNED für Navigation/Klicks
>
> **NEXT-GEN ARCHITECTUR (2026-05-06) — NEU:**
> - **skylight-cli** = RE-ACTIVATED — Primary Interaction Tool (Compact Snapshot + Batch)
> - **CDP WebSocket** = PRIMARY — Direkter CDP-Zugriff, kein cua-driver Daemon mehr
> - **Nemotron 3 Omni** = BRAIN — NVIDIA NIM für Survey-Entscheidungen
> - **src/stealth_survey/** = NEW MODULE — [SurveyAgent](), [NIMClient](), [BatchExecutor]()
>
> **PFLICHT-REGELN** (vor JEDER Session lesen): sinrules.md, brain.md, fix.md, learn.md, anti-learn.md, banned.md, issues.md
> **DOC-HEALTH**: `python3 scripts/check_doc_health.py` → prüft alle 23 Repos auf Pflichtdateien
> **DOC-GENERATE**: `python3 scripts/generate_missing_docs.py` → erstellt fehlende Pflichtdateien in allen Repos
>
> **SYSTEM PROMPT** (wird via `.opencode/opencode.json` geladen):
> Jede Session beginnt mit Laden aller context_files. Der Agent MUSS vor jeder Aktion
> sinrules, brain, fix, learn, anti-learn, banned prüfen. Bei Fehlern: Universal-Fehlercheck.
>
> **FEHLERCHECK**: Bei Abweichung → 10-Punkte-Analyse (Root-Cause, Befehls-Prüfung, Session-Abgleich,
> Cross-Repo, Registry, W-Fragen, Pipeline, Memory, Doku-Update, Vollständigkeits-Check)

---

## 🚨 EXPLICITE VERBOTE (UNVERBRÜCHLICH)

### NIEMALS user Chrome/Prozesse töten!
**REGEL: ICH DARF NIEMALS — UNTER KEINEN UMSTÄNDEN — USER CHROME, USER OPENCODE SITZUNGEN ODER ANDERE USER-PROZESSE BEENDEN**

- ❌ `pkill -f "Google Chrome"` — VERBOTEN
- ❌ `killall Google Chrome` — VERBOTEN
- ❌ `kill <pid>` auf USER Chrome PIDs — VERBOTEN
- ❌ `ps aux | grep Chrome | kill` — VERBOTEN
- ❌ Chrome-Prozesse über grep/kill beenden — VERBOTEN

**NUR ERLAUBT:**
- ✅ Eigene Launched Chrome-Instanzen beenden (via `playstealth launch` gestartet, eigene PID)
- ✅ Eigenen Code in `/tmp/` starten und dort beenden
- ✅ Chrome mit `--user-data-dir=/tmp/heypiggy-bot-XXXXX` (isoliertes Profil)

**WENN Chrome neu gestartet werden muss:**
- Eigenes isoliertes Profil nutzen: `playstealth launch --url '...'` → NEUE PID
- Niemals existierende User-Chrome-Instanzen touchen
- Bei Konflikt: Frisches Profil in `/tmp/` starten

### /commands Verzeichnis (2026-05-05) — COMMAND DOCUMENTATION

**Governance**: `/commands/cmd-rules.md` — alle Regeln zu /commands.

**Provider-Struktur** (2026-05-05): Sobald >1 Command zu Provider → Subdirectory.

```
/commands/
├── cmd-rules.md                       ← ALLE Regeln zu /commands
│
├── cua-driver/          (8 commands)
│   ├── click.md, click-survey-card.md, set-value.md
│   ├── list-windows.md, get-window-state.md
│   ├── find-element-index.md, find-pid-wid.md, navigate-url.md
│
├── heypiggy/            (1 command)
│   └── credentials.md
│
├── infisical/           (2 commands)
│   ├── login.md, secrets.md
│
├── google/              (1 command)
│   └── login-flow.md
│
├── bot-chrome/          (5 commands: 2 verified + 3 banned)
│   ├── kill-bot-chrome.md, find-bot-pids.md
│   ├── banned-pkill-heypiggy-bot.md, banned-killall-chrome.md
│   └── banned-hardcoded-pids.md
│
├── playstealth/         (1 command)
│   └── launch.md
│
├── session-manager/     (1 command)
│   └── launch.md
│
└── [root]               (9 commands: 1 verified + 8 banned)
    ├── macos-recovery-mode.md
    ├── banned-pyautogui.md, banned-pynput.md
    ├── banned-coordinates-click.md, banned-applescript-chrome.md
    ├── banned-skylight-cli.md, banned-webauto-nodriver.md
    ├── banned-cdp-commands.md, banned-recovery-mode.md (DEPRECATED)
```

### Chrome Kill Regeln (UNVERBRÜCHLICH)
- ❌ PIDs NIEMALS hardcodieren (71104, 70293, etc.) → PIDs ändern sich!
- ❌ `pkill -f "heypiggy-bot"` → killt ALLE Chrome-Instanzen inkl. USER Chrome
- ❌ `killall Google Chrome` → killt ALLE Chrome-Instanzen (USER + BOT!)
- ✅ NUR Main-Prozesse killen: Pattern `/Contents/MacOS/Google Chrome` + `/tmp/heypiggy-bot-`
- ✅ Registry leeren: `rm -f ~/.stealth/sessions.json`
- ✅ SOTA: `SessionManager.close_all()` → killt + leert Registry automatisch

## VISION-MODELL: Nemotron 3 Nano Omni (PRIMARY)

- **30B-A3B Mixture-of-Experts** – Video + Audio + Bild + Text in EINEM Modell
- **256K Kontext** – ganze Survey-Sessions in einem Call
- **SSE Streaming** – `stream: true` → tokenweise Antwort
- **API**: `POST https://integrate.api.nvidia.com/v1/chat/completions`
- **Model Name**: `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`
- **API Key**: `$NVIDIA_API_KEY` (Prefix: `nvapi-...`)

---

## 🆕 NEMO-ARCHITEKTUR: Compact-Loop mit Batch (2026-05-06, PRIMARY)

**skylight-cli un-deprecated!** Jetzt PRIMARY für kompakte Snapshots + Batch-Ausführung.

```
┌──────────────────────────────────────────────────────────────────────────┐
│                 NEMO LOOP — 1 LLM Call pro Frage-Batch                   │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  while not complete:                                                      │
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────┐     │
│  │ SCHRITT 1: COMPACT SNAPSHOT (skylight-cli / CDP)                │     │
│  │                                                                  │     │
│  │ skylight-cli snapshot-compact --pid X --semantic                 │     │
│  │ → {                                                              │     │
│  │     "refs": {"@e0": {role:"radio",text:"Männlich"},...},       │     │
│  │     "semantic": {"questions":[...], "progress":"3/10"},         │     │
│  │     "provider": "qualtrics",                                     │     │
│  │     "stealthScore": 0.92                                         │     │
│  │   }                                                              │     │
│  └──────────────────────────────────────────────────────────────────┘     │
│       │                                                                   │
│       ▼                                                                   │
│  ┌──────────────────────────────────────────────────────────────────┐     │
│  │ SCHRITT 2: NEMOTRON DECISION (NVIDIA NIM)                        │     │
│  │                                                                  │     │
│  │ NIMSurveyClient.decide(snapshot, profile, learnings)             │     │
│  │ → {"actions": [                                                  │     │
│  │     {"ref": "@e0", "action": "select"},                          │     │
│  │     {"ref": "@e12", "action": "fill", "value": "32"},            │     │
│  │     {"action": "submit"}                                         │     │
│  │   ]}                                                             │     │
│  │                                                                  │     │
│  │ Token-Effizient: ~500 tokens in, ~100 tokens raus                │     │
│  └──────────────────────────────────────────────────────────────────┘     │
│       │                                                                   │
│       ▼                                                                   │
│  ┌──────────────────────────────────────────────────────────────────┐     │
│  │ SCHRITT 3: BATCH EXECUTE (CDP WebSocket)                         │     │
│  │                                                                  │     │
│  │ BatchExecutor.execute(ws_url, actions, provider)                 │     │
│  │ → provider-specific CDP JS:                                      │     │
│  │   Qualtrics:    .NextButton.click()                              │     │
│  │   TolunaStart:  .cf-radio[0].click(); button.click()             │     │
│  │   Strat7:       .bsbutton.click()                                │     │
│  │                                                                  │     │
│  │ Alle Actions in EINEM WebSocket-Call (kein Round-Trip!):        │     │
│  │ Runtime.evaluate("(function(){...alle actions...})()")           │     │
│  └──────────────────────────────────────────────────────────────────┘     │
│       │                                                                   │
│       ▼                                                                   │
│  ┌──────────────────────────────────────────────────────────────────┐     │
│  │ SCHRITT 4: MEMORY + GUARDIAN (auto)                              │     │
│  │                                                                  │     │
│  │ stealth_memory.log_step(snapshot, decision, result)              │     │
│  │ stealth_guardian.monitor_and_heal(session, result)               │     │
│  │ → incidents/{session}/, learn.md, anti-learn.md                  │     │
│  └──────────────────────────────────────────────────────────────────┘     │
│                                                                           │
│  Vorteil: 1 LLM-Call PRO SEITE (nicht pro Element!)                      │
│           90% Token-Ersparnis durch Compact Snapshot                      │
│           5× schneller als cua-driver Loop                               │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
```

### NEMO Modul-Struktur (NEW)

```
src/stealth_survey/           ← NEU: Compact Batch Survey Engine
├── __init__.py                → Public API
├── survey_agent.py            → SurveyAgent: run_survey(), run_loop()
├── nim_client.py              → NIMSurveyClient: decide(), decide_with_tools()
├── compact_snapshot.py        → CompactSnapshotGenerator: CDP → @eN snapshot
└── batch_executor.py          → BatchExecutor: actions → CDP JS execution
```

### skylight-cli Commands (NEU, SR-37)

| Command | Zweck | Beispiel |
|---------|-------|----------|
| `snapshot-compact` | Kompaktes @eN Snapshot | `skylight-cli snapshot-compact --pid X --semantic` |
| `find` | Element per role/text/label finden | `skylight-cli find --role button --text "Weiter"` |
| `batch` | Batch-Aktionen ausführen | `skylight-cli batch '[{"ref":"@e0","action":"click"}]'` |

### Verboten vs. Erlaubt (NEMO-Update)

| Tool | Status | Begründung |
|------|--------|------------|
| **skylight-cli** snapshot-compact | ✅ ERLAUBT | PRIMARY — Compact Snapshot |
| **skylight-cli** batch | ✅ ERLAUBT | Batch-Ausführung |
| **CDP WebSocket** Runtime.evaluate | ✅ ERLAUBT | Fallback wenn skylight nicht verfügbar |
| **src/stealth_survey/** | ✅ ERLAUBT | NEMO Survey Engine |
| **cua-driver** | ⚠️ DEPRECATED | Nur Fallback, NEMO ist PRIMARY |
| skylight-cli click (index) | ❌ BANNED | Nutze batch stattdessen |
| webauto-nodriver | ❌ BANNED | Absolut |

---

## ARCHITEKTUR: CUA-ONLY TRINITY (2026-05-03, LEGACY/DEPRECATED)

**Das Problem:** CDP WebSocket wird von Chrome blockiert (origin check). skylight-cli mischt Browser-Chrome + Web-Content.

**Die Lösung:** NUR cua-driver für ALLE Interaktionen.

```
┌──────────────────────────────────────────────────────────────────────────┐
│                     CUA-ONLY TRINITY — Klick-Ablauf                       │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  playstealth launch                                                       │
│  → {"pid": 48403, "cdp_port": 61934}                                     │
│       │                                                                   │
│       ▼                                                                   │
│  ┌──────────────────────────────────────────────────────────────────┐     │
│  │ SCHRITT 0: DAEMON (nohup)                                        │     │
│  │                                                                  │     │
│  │ nohup cua-driver serve > /tmp/cua-daemon.log 2>&1 &              │     │
│  │ → Daemon starten (überlebt bash-Sessions!)                       │     │
│  │ Ohne Daemon: keine Session-Cache → keine Clicks!                 │     │
│  └──────────────────────────────────────────────────────────────────┘     │
│       │                                                                   │
│       ▼                                                                   │
│  ┌──────────────────────────────────────────────────────────────────┐     │
│  │ SCHRITT 1: WINDOW FINDEN (cua-driver)                           │     │
│  │                                                                  │     │
│  │ cua-driver call list_windows                                     │     │
│  │ → Alle Fenster der App (Content-Window hat height > 100)        │     │
│  │ → Apple-Menüleiste (depth 1-4) IMMER ignorieren!                │     │
│  └──────────────────────────────────────────────────────────────────┘     │
│       │                                                                   │
│       ▼                                                                   │
│  ┌──────────────────────────────────────────────────────────────────┐     │
│  │ SCHRITT 2: STATE CACHEN (cua-driver)                            │     │
│  │                                                                  │     │
│  │ cua-driver call get_window_state(pid, window_id)                 │     │
│  │ → Kompletten AX-Tree cachen (alle Elemente mit Indices)         │     │
│  │ → Elemente mit @(x,y,w,h) Position für Koordinaten-Fallback     │     │
│  │ → depth > 5 Filter für Browser-Content                          │     │
│  └──────────────────────────────────────────────────────────────────┘     │
│       │                                                                   │
│       ▼                                                                   │
│  ┌──────────────────────────────────────────────────────────────────┐     │
│  │ SCHRITT 3: INTERAKTION (cua-driver, NUR CUA!)                   │     │
│  │                                                                  │     │
│  │ BUTTON KLICKEN:  call click(pid, wid, index)                     │     │
│  │                  Timeout 30s + 3x Retry bei kAXErrorCannotComplete│     │
│  │                                                                  │     │
│  │ TEXT EINGEBEN:  call set_value(pid, wid, index, "text")          │     │
│  │                                                                  │     │
│  │ TASTENDRUCK:    call press_key(pid, "return")                   │     │
│  │                                                                  │     │
│  │ NAVIGIEREN:     call click → addr_bar                            │     │
│  │                 call set_value → URL                              │     │
│  │                 call press_key → "return"                         │     │
│  └──────────────────────────────────────────────────────────────────┘     │
│       │                                                                   │
│       ▼                                                                   │
│  FALLBACK-KETTE:                                                          │
│  1. AXPress auf element_index → Timeout 30s + 3x Retry (PRIMARY)         │
│  2. Bei Failure: Koordinaten-Click click(pid, x, y) aus @(x,y,w,h)       │
│  3. Bei Links: CDP Navigation (NUR wenn CUA Nav fehlschlägt)            │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
```

## TOOLS (CUA-ONLY, fusioniert)

| Tool | Rolle | Befehl |
|------|-------|--------|
| **cua-driver** (PRIMARY) | ALLE Interaktionen | `cua-driver call {method} {params}` |
| **playstealth** | Chrome Launch | `playstealth launch --url '...'` |
| **macos-ax-cli** | System-Scan (NUR Finden!) | `elements --pid X` |

## VERBOTEN (BANNED)

- CDP `Accessibility.queryAXTree` / `getContentQuads` (für Navigation)
- `cdp_click.py` Modul (CDP+AX Trinity ist obsolet)
- `skylight-cli click --element-index` (Index instabil!)
- `webauto-nodriver` MCP (ABSOLUT VERBOTEN)
- `pkill -f "Google Chrome"` (tötet private Sessions!)
- Apple-Menüleiste klicken (depth < 5)

## ERLAUBT (NUR CUA)

| Kontext | Tool | Befehl |
|---------|------|--------|
| Button klicken | cua-driver | `call click {pid, wid, index}` |
| Text eingeben | cua-driver | `call set_value {pid, wid, index, value}` |
| Navigieren | cua-driver | `call click → call set_value → call press_key` |
| Fenster finden | cua-driver | `call list_windows` |
| AX-Tree lesen | cua-driver | `call get_window_state {pid, wid}` |
| Tastendruck | cua-driver | `call press_key {pid, key}` |
| Chrome starten | playstealth | `playstealth launch --url X` |

## AUDIO CAPTURE MODULE (2026-05-04, NEU)

### Problem
Survey-Seiten nutzen `<video>` mit `blob:` URLs für Audio-Fragen (Tiergeräusche erkennen).
Blob-URLs können NICHT via fetch/XHR/FileReader extrahiert werden (CORS/Security).
Auch MediaRecorder + captureStream scheitern an protected content (EME/MSE).

### Lösung: BlackHole + ffmpeg + NVIDIA Omni Audio Analysis

```
┌─────────────────────────────────────────────────────────────────────┐
│ AUDIO CAPTURE PIPELINE                                               │
│                                                                     │
│  1. SwitchAudioSource -t output -s "BlackHole 2ch"                  │
│     → Chrome-Audio wird auf BlackHole geroutet                      │
│                                                                     │
│  2. ffmpeg -f avfoundation -i ":BlackHole 2ch" -t 6 /tmp/audio.wav │
│     → 6 Sekunden System-Audio aufnehmen                             │
│                                                                     │
│  3. SwitchAudioSource -t output -s "MacBook Pro-Lautsprecher"       │
│     → Audio zurück auf Lautsprecher                                 │
│                                                                     │
│  4. NVIDIA Omni Audio Analysis:                                     │
│     POST /v1/chat/completions                                       │
│     → audio_url + Text-Prompt                                       │
│     → "What animal sound? Options: Elefant, Hahn, Hund, Katze"      │
│     → Answer: "Hahn" (Omni erkennt Tiergeräusche zuverlässig)       │
└─────────────────────────────────────────────────────────────────────┘
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
# → Token erhalten!
```

### Lemin Puzzle Captcha (OpenCV + JS Drag)
```python
from stealth_captcha.solvers.lemin_ultimate import solve_lemin
solve_lemin()
# → Puzzle-Stück per JS dispatchEvent verschieben + Verify
```

### Survey Integration
```python
from stealth_captcha.captcha_handler import handle_captcha_in_survey
handle_captcha_in_survey(pid, page_url)
# → Automatische Captcha-Erkennung + Lösung
```

## SURVEY FLOW (2026-05-04, VERIFIZIERT)

### Kompletter Ablauf
```
1. SCAN: CDP JS → finde Tab MIT .survey-item (document.querySelectorAll)
2. START: CDP JS → document.getElementById('survey-ID').click()
3. MODAL: CUA → "Umfrage starten" Button klicken (index variiert, ~246-270)
4. CONSENT: CUA → "Zustimmen und fortfahren" klicken
5. START: CUA → "Starten" klicken (Survey öffnet in Tab)
6. AUDIO-FRAGE: Audio Module → BlackHole + ffmpeg + NVIDIA Omni
7. ANTWORT: CUA/CDP JS → Option auswählen + "Weiter" klicken
8. KOMPLETT: Survey schließt → zurück zu heypiggy Dashboard
```

### Survey Provider
| Provider | URL Pattern | Flow |
|----------|------------|------|
| Samplicio.us | `rx.samplicio.us/consent/` | Consent → My-Take → Disqual/Complete |
| Cint | `s.cint.com/Survey/Fingerprint/` | Fingerprint → Nfield/Kantar → Fragen |
| Nfield/Kantar | `nfieldeu-interviewing.nfieldmr.com` | Welcome → Audio/Video-Fragen |

### Wichtige Erkenntnisse
1. **Multi-Tab Problem**: heypiggy öffnet mehrere Dashboard-Tabs. Nur EINER hat Surveys. Scanne ALLE Tabs!
2. **Survey In-Page**: clickSurvey() öffnet den Survey im Dashboard (kein neuer Tab!). AX-Tree rescanen nach neuen Elementen!
3. **Survey Modal**: "Umfrage starten" erscheint als Overlay NACH clickSurvey(). Index variiert (~246-270).
4. **Blob-Audio**: `<video>` mit blob: URL kann NICHT via JS extrahiert werden. BlackHole nötig.
5. **Disqualifikation**: 0.02€ Compensation bei Abbruch. Level-Up bei erfolgreicher Teilnahme.

## FLOW-OPTIMIZER

Wenn ein Flow **10x hintereinander** erfolgreich läuft → Promotion zu Production.

```
flows/candidates/   → Flows in Lern-Phase (brauchen noch Vision)
flows/production/   → 10x bestanden → NUR CLI, KEIN Vision!
flows/history/      → JSONL pro Flow (letzte 100 executions)
```

## VERBOTEN (BANNED)

- `skylight-cli click --pid X --element-index Y` für Web-Content (Index instabil!)
- skylight-cli MCP, Nutzer-Chrome manipulieren
- `recovery_mode: true`, `omni_fallback: llama`
- Mausbewegung, Koordinaten raten
- **`pkill -f "heypiggy-bot"`** → killt ALLE Chrome (USER + BOT!)
- **`killall Google Chrome`** → killt ALLE Chrome-Instanzen!
- **Hardcoded PIDs** (71104, 70293, etc.) → PIDs sind dynamisch!
- Commands-Verzeichnis: `/commands/banned-*.md` → alle verbotenen Commands dokumentiert

## ERLAUBT

| Kontext | Tool | Befehl |
|---------|------|--------|
| Chrome Kill | `SessionManager.close_all()` | `sm.close_all()` → killt BOT + leert Registry |
| Chrome Kill | Python Script | `/commands/kill-bot-chrome.md` |
| BOT PIDs finden | Python Script | `/commands/find-bot-pids.md` |
| Chrome Launch | `playstealth` | `playstealth launch --url '...'` |
| Web-Content | **cua-driver** | `call click/set_value/press_key` |
| Popup-Fenster | `cua-driver` | `call click '{"pid":X,"window_id":W,"element_index":Y}'` |
| System-Scan | `macos-ax-cli` | `find "Text"`, `windows list` |
| Audio Capture | `audio_capture.py` | `python3 -m cli.modules.audio_capture --capture --analyze` |

## 🚨 GOLDENE REGEL: NACH JEDER AKTION STATUS PRÜFEN (2026-05-04)
**NIE blind nach einer Aktion weitermachen!** Immer prüfen:
1. `list_windows` → hat sich die WID geändert?
2. `get_window_state` → sind neue Elemente sichtbar?
3. `document.body.innerText` → hat sich der Seiteninhalt geändert?
4. Button DISABLED oder ENABLED?

## 📋 KORREKTER ABLAUF PRO SURVEY-SCHRITT
```
1. list_windows    → WID finden (niemals hartcodieren!)
2. get_window_state → AX-Tree laden
3. depth > 5 FILTER → NUR Web-Content Elemente
4. Element finden   → per Label + Rolle im Tree
5. click/set_value  → Aktion ausführen
6. list_windows    → WID noch gültig?
7. get_window_state → Hat sich was geändert?
8. Weiter mit 2.    → oder fertig
```

## 🛡️ VERIFY-BOX REGEL (2026-05-04)
Jeder Klick/jede Texteingabe SOLLTE `"verify": true` enthalten.
Der Daemon prüft SOFORT ob der Zustand wirklich erreicht wurde.
Ohne Verify: Agent wird belogen (cua-driver sagt "Performed" obwohl nichts passierte).

## 🛡️ VERIFY-BOX: Nie wieder falsches `success: true` (2026-05-04)

### Problem
Der Agent klickt "Männlich". CUA sagt `Performed`. Agent glaubt es. Aber Radio-Button wurde NICHT selektiert — JS-Event-Listener hat nicht gefeuert.

### Lösung: Verify-Box
Der Agent hängt EIN Wort an seinen Befehl: `"verify": true`

```bash
stealth-exec cua-touch --action click --label "Männlich" --json-params '{"verify": true}'
```

### Was passiert dann
1. CUA-Klick auf "Männlich" ausführen
2. AX-Tree NEU scannen (gleiches Fenster)
3. Element suchen und ZUSTAND prüfen:
   - AXRadioButton → `selected=true`?
   - AXCheckBox → `checked=true`?
   - AXTextField → enthält Text?
4. NUR WENN ZUSTAND ERREICHT: `success: true`

### Ohne Verify
```
❌ Agent wird belogen — CUA sagt "Performed", aber nichts passiert
❌ Agent macht 10 Schritte blind weiter
❌ Survey disqualifiziert, 30min verschwendet
```

### Mit Verify
```
✅ Agent kriegt `success: false` + Fehlermeldung
✅ Agent kann SOFORT reagieren (Retry/Fallback)
✅ Kein Blindflug mehr
```

---

## 🏭 COMPILED FLOW ENGINE (2026-05-04)

**Pattern: Agent denkt NICHT mehr. Er macht exakt EINEN Tool-Call.**

### Das Problem
Agenten machen 10-50 individuelle Schritte, vergessen Dinge, kombinieren Tools frei → Fehler, Token-Verschwendung, Instabilität.

### Die Lösung: FCTES — Flow Compilation & Tool Enforcement System

```
LEARNING (unsicher) → 10x Success → COMPILE → TOOL REGISTRY → DISPATCHER (nur noch 1 Call)
```

### Architektur

```
app/
├── flows/learning/         # Unsichere, flexible Flows (Agent baut hier)
│   └── survey_heypiggy.py  # Survey-Loop mit CUA-only Logik
├── flows/compiled/         # NACH 10x Erfolg: frozen, versioniert
│   └── survey_heypiggy_v1746400000.py
├── core/
│   ├── tracker.py          # Success-Counter → Threshold-Check
│   ├── registry.py         # Source of Truth: welcher Flow ist frozen?
│   ├── compiler.py         # Copy learning → compiled + Version + Hash
│   ├── tool_builder.py     # Registriert Tool in opencode.json
│   ├── executor.py         # Führt frozen Flow aus (importlib)
│   ├── dispatcher.py       # Hard Enforcement: NUR versionierte Tools
│   └── orchestrator.py     # Entscheidet: learning oder compiled?
└── run_survey.py           # SINGLE ENTRY POINT ← Agent ruft NUR das auf
```

### Hard Enforcement Regeln

```
╔══════════════════════════════════════════════════════════════════╗
║  REGEL 1: Agent ist NUR ein Trigger                              ║
║  ─────────────────────────────────────────────────────────────── ║
║  ✅ RICHTIG:  python run_survey.py                               ║
║  ❌ FALSCH:   Agent klickt Survey-Cards manuell                  ║
║  ❌ FALSCH:   Agent baut eigene CUA-Befehle                      ║
║  ❌ FALSCH:   Agent zerlegt Flow in Einzelschritte               ║
╚══════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════╗
║  REGEL 2: KEINE Freiheit bei Tool-Wahl                           ║
║  ─────────────────────────────────────────────────────────────── ║
║  ✅ RICHTIG:  dispatch("survey_heypiggy_v1746400000", payload)  ║
║  ❌ FALSCH:   Agent entscheidet "nehme ich skylight oder cua?"   ║
║  ❌ FALSCH:   Agent kombiniert mehrere Tools                     ║
╚══════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════╗
║  REGEL 3: Freeze nach 10 Erfolgen                                ║
║  ─────────────────────────────────────────────────────────────── ║
║  tracker.record("survey_heypiggy")  # nach jedem OK-Run          ║
║  → wenn count >= 10: compiler.compile() → neues Tool             ║
║  → ab jetzt NUR noch das frozen Tool                             ║
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
# ✅ EINZIGER Befehl für Survey-Loop:
python3 run_survey.py

# ✅ Oder intern:
from app.core.orchestrator import run
from app.flows.learning import survey_heypiggy
result = run("survey_heypiggy", survey_heypiggy.execute, {
    "radio_hints": ["Berlin", "männlich", "Angestellter", "Deutsch"],
    "checkbox_hints": ["Keine"],
    "textarea_value": "Ja"
})
```

### Neue Flows hinzufügen (Learning Phase)

1. Flow in `app/flows/learning/` bauen (mit `execute(payload)` Funktion)
2. Testen bis 10× erfolgreich
3. `compiler.compile("flow_name")` →자동으로:
   - Copy nach `app/flows/compiled/flow_v{TIMESTAMP}.py`
   - `registry.save()` → Source of Truth
   - `tool_builder.register()` → opencode.json
   - `dispatcher.dispatch()` → ab jetzt erlaubt

### Dashboard-Survey starten (Persona aus Profil-System)

⚠️ **NIE Alter hartcodieren!** Das Alter wird aus `date_of_birth` im Profil berechnet.
Das Profil-System ist in `A2A-SIN-Worker-heypiggy/persona.py` implementiert.

```python
# ❌ FALSCH: Hartcodiertes Alter führt zu Disqualifikation!
# PAYLOAD = {"age": 42}  # ← DAS WAR DER FEHLER (2026-05-05)
# Persona: Berlin, Kurfürstenstraße 124, 10785, männlich, 42,

# ✅ RICHTIG: Profil laden, Alter aus date_of_birth berechnen
from persona import load_persona, resolve_answer
persona = load_persona("jeremy_schulze")
# → date_of_birth="1993-11-13" → age=32 (berechnet, IMMER aktuell)
answer = resolve_answer(persona, "What is your age?", ["Under 16", "16-25", "26-39", "40+"])
# → matched_option="26-39" (32 fällt in dieses Bracket)
```

**Aktuelles Profil**: Jeremy Schulze, geb. 13.11.1993 (32 Jahre), Berlin, männlich, Angestellter, Meister, 2-Personen-Haushalt

---

## 🔴 KRITISCHES PROBLEM: Chrome CDP WebSocket Block (2026-05-04)

### Das Problem
Chrome blockiert eingehende CDP WebSocket Verbindungen:
```
WebSocketBadStatusException: Handshake status 403 Forbidden
Rejected an incoming WebSocket connection from the http://localhost:XXXXX origin.
Use --remote-allow-origins=* to allow connections from this origin.
```

### Lösung
Chrome MUSS mit `--remote-allow-origins=*` gestartet werden:
```bash
playstealth launch --url '...'  # playstealth setzt das automatisch
```

**ABER**: Selbst mit playstealth kann der Origin-Check noch aktiv sein.
Dann: Chrome neu starten oder `--disable-web-security` testen.

### AX-Tree leer? Checkliste
Wenn `cua-driver call get_window_state` **0 Children** zurückgibt:
1. **Accessibility prüfen**: System Settings → Accessibility → Screen bei Bedarf AN
2. **Chrome Accessibility Flag**: playstealth startet mit `--force-renderer-accessibility`
3. **Window wählen**: Nicht WID 0 (Menüleiste), sondern WID mit `height > 100` und `depth > 5`
4. **Page laden**: Seite muss vollständig geladen sein (5s warten)
5. **CUA-Daemon**: `cua-driver serve` muss als Daemon laufen

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
| `get_window_state` → 0 children | Accessibility nicht aktiv | System Settings → Accessibility einschalten |
| CDP WS 403 Forbidden | Chrome Origin check | Chrome neu starten (playstealth setzt flags) |
| Alle Windows height=0 | Falsches Window | WID mit height>100 suchen |
| AXButton/AXLink nicht gefunden | depth<5 filter | Apple-Menüleiste hat depth 1-4 |


## 🔑 GOOGLE LOGIN — AUTORITATIVER FLOW (CUA-ONLY, 6 STEPS)

**Datei:** `cli/modules/auto_google_login.py`  
**Funktion:** `execute(pid=None, url="https://heypiggy.com/?page=dashboard")`  
**Return:** `{"status": "ok", "pid": X, "wid": Y}` oder `{"status": "error", "reason": "..."}`  
**Methode:** CUA-ONLY via `cua-driver` CLI — KEIN skylight, KEIN CDP, KEIN webauto

### Shell Commands (learning-by-doing, live dokumentiert 2026-05-05)

```bash
# STEP 1: Chrome starten
playstealth launch --url 'https://heypiggy.com/?page=dashboard'
→ BOT PID=71104, profile=/tmp/heypiggy-bot-1777981361

# STEP 2: Windows finden
cua-driver call list_windows | python3 -c "..."
→ WID=56640 PID=71104 Title=HeyPiggy Dashboard

# STEP 3: AX-Tree lesen → Google Login-Symbol finden
echo '{"pid": 71104, "window_id": 56640}' | cua-driver call get_window_state
→ [54] AXLink (Google Login-Symbol) @(731,651,132,41)

# STEP 4: Google Login klicken
echo '{"pid": 71104, "window_id": 56640, "element_index": 54}' | cua-driver call click
→ ✅ Performed AXPress on [54] AXLink
→ wait 5s → NEUE WID 56658 (Google OAuth)

# STEP 5: Email eintragen + Weiter
echo '{"pid": 71104, "window_id": 56658, "element_index": 25, "value": "zukunftsorientierte.energie@gmail.com"}' | cua-driver call set_value
→ [25] AXTextField (E-Mail oder Telefonnummer) @(735,549,450,54)
echo '{"pid": 71104, "window_id": 56658, "element_index": 35}' | cua-driver call click
→ [35] AXButton "Weiter" @(1095,706,91,40)
→ wait 5s → Keychain Auto-Fill → "Jeremy Schulze"

# STEP 6: Fortfahren + Final Weiter
echo '{"pid": 71104, "window_id": 56658, "element_index": 62}' | cua-driver call click
→ [62] AXButton "Fortfahren" @(1090,689,94,30)
→ wait 5s
echo '{"pid": 71104, "window_id": 56658, "element_index": 41}' | cua-driver call click
→ [41] AXButton "Weiter" @(966,786,220,40)
→ wait 5s → Login Complete! Dashboard eingeloggt!
```

### Ablauf (6 Steps, LIVE GETESTET 2026-05-05 PID=71104)

| Step | Element | Index | AXRole | Aktion |
|------|---------|-------|--------|--------|
| 1 | Google Login-Symbol | 54 | AXLink | click |
| 2 | Email-Feld | 25 | AXTextField | set_value |
| 2b | Weiter | 35 | AXButton | click |
| 3 | Fortfahren | 62 | AXButton | click (Keychain Auto-Fill!) |
| 4 | Weiter (Final) | 41 | AXButton | click |

### Rückgabe
- `{"status": "ok", "pid": X, "wid": Y}` wenn "abmelden"/"umfragen" im Dashboard sichtbar
- `{"status": "error", "reason": "..."}` sonst

### Voraussetzung
- `playstealth launch` startet Chrome (oder pid übergeben wenn schon offen)
- cua-driver Daemon muss laufen (`cua-driver serve` als Daemon)

### Beispiel
```python
from cli.modules.auto_google_login import execute as auto_google_login

result = auto_google_login()
if result.get("status") == "ok":
    print(f"✅ Login OK: pid={result['pid']} wid={result['wid']}")
else:
    print(f"❌ Login failed: {result.get('reason')}")
```

### Keychain Auto-Fill Discovery (KRITISCH!)
- Email eintragen → "Weiter" → Keychain füllt automatisch Credentials aus
- "Jeremy Schulze" Konto vorausgewählt → NUR "Fortfahren" klicken
- KEIN Passwort-Feld wenn Keychain aktiv!

### BOT Chrome PIDs (NIEMALS USER Chrome beenden!)
- PID=DYNAMIC = heypiggy-bot-1777981361 (AKTUELL)
- PID=DYNAMIC = heypiggy-bot-1777981087 (geschlossen)
- PID=DYNAMIC = heypiggy-bot-1777979455 (geschlossen)
- USER Chrome: Dynamischer PID (find via ps aux | grep "user-data-dir") (localhost, DeepSeek) → NIEMALS TOUCHEN!

### BANNED (niemals verwenden)
- ❌ skylight-cli (BANNED seit CUA-ONLY Trinity)
- ❌ CDP / webauto-nodriver (BANNED)
- ❌ Hardcoded PIDs (48437, 51212, etc.)
- ❌ devjerro@gmail.com (NUR zukunftsorientierte.energie@gmail.com)
- ❌ Alle anderen Login-Implementierungen (A2A-Worker, stealth-skills, etc. — GELÖSCHT)
