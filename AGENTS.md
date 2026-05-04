# AGENTS.md – Stealth-Runner mit CUA-ONLY Trinity (2026-05-03)

> **← [sinrules.md](sinrules.md) ist das zentrale Regelwerk. Alle Golden Rules sind DORT.**
> **← [brain.md](brain.md) dokumentiert die CUA-ONLY Architektur im Detail.**
> **CDP + skylight-cli + webauto-nodriver sind ALLE BANNED.**

## VISION-MODELL: Nemotron 3 Nano Omni (PRIMARY)

- **30B-A3B Mixture-of-Experts** – Video + Audio + Bild + Text in EINEM Modell
- **256K Kontext** – ganze Survey-Sessions in einem Call
- **SSE Streaming** – `stream: true` → tokenweise Antwort
- **API**: `POST https://integrate.api.nvidia.com/v1/chat/completions`
- **Model Name**: `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`
- **API Key**: `$NVIDIA_API_KEY` (Prefix: `nvapi-...`)

---

## ARCHITEKTUR: CUA-ONLY TRINITY (2026-05-03, AKTIV)

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

## LOGIN BOX (CUA-ONLY, 2026-05-04)

### heypiggy Google Login als Box
```python
from cli.modules.heypiggy_login_box import heypiggy_login

# EIN Aufruf für den kompletten Login!
# FLOW A: Frischer Browser → Email → Passkey bypass → Password → Consent
# FLOW B: Gecachte Cookies → Konto klicken → Consent
# Automatische Erkennung + Fallback
heypiggy_login(pid=2674, cdp_port=55983)
# → True wenn eingeloggt
```

### Features der Box
- ✅ CUA-only (KEIN skylight, KEIN CDP für Navigation)
- ✅ Findet Google OAuth Popup automatisch (via Fenster-Titel)
- ✅ Passkey-Bypass ("Andere Option wählen" → Passwort)
- ✅ 2FA-Erkennung + Warteschleife für Smartphone-Bestätigung
- ✅ macOS System-Dialog ("Fortfahren") Erkennung + Klick
- ✅ Consent-Handling ("Fortfahren", "Als Jeremy fortfahren")
- ✅ Dashboard-verify nach Login

## BEFEHLE

```bash
# Chrome starten (liefert cdp_port!)
playstealth launch --url 'https://accounts.google.com/ServiceLogin'
# → {"pid": 48403, "cdp_port": 61934, ...}

# KOMPLETT: heypiggy Login in EINEM Befehl
python3 -c "
from cli.modules.heypiggy_login_box import heypiggy_login
heypiggy_login(pid=2674, cdp_port=55983)
"

# Detailschritte (nur falls Box fehlschlägt):
# - Email: cua click set_value
# - Weiter: cua click
# - Andere Option: cua click
# - Passwort: cua click set_value
# - macOS Dialog: cua click (anderes Fenster)
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

## ERLAUBT

| Kontext | Tool | Befehl |
|---------|------|--------|
| Web-Content | **cdp_click** (NEU) | `cdp_click.label(pid, port, "Weiter", "button")` |
| Hauptfenster | `skylight-cli` | `click --pid X --element-index Y` |
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
