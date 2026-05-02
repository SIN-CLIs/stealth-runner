# AGENTS.md – Stealth-Runner mit NVIDIA Nemotron 3 Nano Omni

## VISION-MODELL: Nemotron 3 Nano Omni (PRIMARY)

- **30B-A3B Mixture-of-Experts** – Video + Audio + Bild + Text in EINEM Modell
- **9× effizienter** als separate Vision+Sprache-Stacks
- **Native 1920×1080** – volle HD-Auflösung ohne Downsampling
- **256K Kontext** – ganze Survey-Sessions in einem Call
- **Conv3D Videokompression** – 2× weniger Tokens für Video
- **SSE Streaming** – `stream: true` → tokenweise Antwort (niedrigste Latenz)
- **API**: `POST https://integrate.api.nvidia.com/v1/chat/completions`
- **Model Name**: `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`
- **Fallback**: `meta/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` (automatisch bei Fehler)
- **API Key**: `$NVIDIA_API_KEY` (Prefix: `nvapi-...`)

## ARCHITEKTUR

```
┌──────────────────────────────────────────────────────┐
│  playstealth launch --url <URL>                      │
│  → isolierte Chrome-Instanz mit eigener PID          │
└──────────────────┬───────────────────────────────────┘
                   │
┌──────────────────▼───────────────────────────────────┐
│  LiveOmniMonitor (runner/live_omni_monitor.py)       │
│                                                      │
│  ┌─────────────┐   ┌──────────────┐  ┌───────────┐  │
│  │ Screenshot  │   │ Rolling Video│  │ SSE Stream│  │
│  │ (schnell)   │   │ Buffer (temp)│  │ Response  │  │
│  │ 1-2 FPS     │   │ alle 5 steps │  │ tokenweise│  │
│  └──────┬──────┘   └──────┬───────┘  └─────┬─────┘  │
│         │                │                │         │
│         └────────────────┼────────────────┘         │
│                          ▼                          │
│              NVIDIA NIM (https://...)                │
│              → {"action":"click","element_id":N}     │
└──────────────────┬───────────────────────────────────┘
                   │
┌──────────────────▼───────────────────────────────────┐
│  skylight-cli click/type --pid <PID> --element-index  │
│  → KEINE Mausbewegung, KEINE Koordinaten             │
└──────────────────────────────────────────────────────┘
```

## NEUE FÄHIGKEITEN DURCH OMNI

### Rolling Video Buffer (Live-Temporal-Analyse)

```bash
# Automatisch im LiveOmniMonitor:
# 1. screen-follow record --video (Daueraufnahme)
# 2. ffmpeg -sseof -4s → 4-Sekunden-Clip
# 3. base64 → NVIDIA NIM (video_url) → Conv3D Analyse
# 4. Omni erkennt Seitenübergänge, Captchas, Fehlerzustände
```

### Video-Analyse (Screen-Follow-Aufnahmen)

```bash
# Fehler in letzter Aufnahme erkennen
python3 -m runner.video_analyzer --last errors

# Kompletten Survey-Ablauf analysieren
python3 -m runner.video_analyzer --last flow

# CAPTCHA-Lösung aus Video extrahieren
python3 -m runner.video_analyzer --last captcha

# Einzelne Aufnahme analysieren
python3 -m runner.video_analyzer /tmp/screen_recording.mp4 flow
```

### Multi-Frame-Kontext (2-5 Screenshots)

```bash
# Vorher/Nachher-Vergleich (hat der Klick gewirkt?)
python3 -m runner.video_analyzer --compare /tmp/step_3.png /tmp/step_4.png
```

- Wird automatisch in `runner/step.py` und `runner/state_machine.py` genutzt
- Letzte 2 Frames werden für bessere Entscheidungen analysiert
- Erkennt Seitenübergänge und Fehlerzustände

## GRAPHIFY KNOWLEDGE GRAPH (6 Repos → 1 merged Graph)

Graphify ist installiert in ALLEN 6 Repos:

- stealth-runner, playstealth-cli, skylight-cli
- screen-follow, unmask-cli, A2A-SIN-Worker-heypiggy

| Metrik       | Wert                              |
| ------------ | --------------------------------- |
| Nodes        | 4.820                             |
| Edges        | 10.860                            |
| Communities  | 284                               |
| Merged Graph | `graphify-out/merged-graph.json`  |
| Visual       | `graphify-out/graph.html` (D3.js) |

### Graphify Befehle

```bash
graphify query "Wie hängen skylight-cli und stealth-runner zusammen?"
graphify path "StealthExecutor" "LiveOmniMonitor"
graphify explain "SkylightDriver"
graphify update .           # AST-Rebuild nach Code-Änderungen
graphify hook status        # Prüfen ob Git-Hooks aktiv sind
```

### Auto-Rebuild

- `post-commit` Hook: Rebuild nach jedem Commit
- `post-checkout` Hook: Rebuild nach Branch-Wechsel
- Nur AST (tree-sitter), kein LLM → keine Kosten

## DOCTOR CLI (23 Tools)

Der `/doctor` Skill nutzt 23 Open-Source-Tools für Code-Analyse, Doku-Generierung und Qualitätssicherung:

| Kategorie        | Tools                                                          |
| ---------------- | -------------------------------------------------------------- |
| Code-Statistiken | cloc, tokei                                                    |
| Komplexität      | lizard                                                         |
| Abhängigkeiten   | pydeps, pyreverse, code2flow, dependency-cruiser               |
| UML              | plantuml                                                       |
| Doku-Generierung | sphinx, mkdocs, pdoc, typedoc, doxygen, terraform-docs, pandoc |
| Qualität         | vale, standard-readme, prettier, repomix, gitingest            |
| CHANGELOG        | git-cliff, conventional-changelog, auto-changelog              |

Siehe `docs/doctor-tool-library.md` für Details.

```bash
# Alle Tools prüfen
python3 runner/doctor_cli.py
```

## SEMGREP ARCHITECTURE GUARD (11 Regeln)

Semgrep blockiert BANNED Muster VOR dem Commit:

| Regel                                     | Blockiert                               |
| ----------------------------------------- | --------------------------------------- |
| `banned-chrome-pgrep`                     | `playstealth launch (isolierte PID)`    |
| `banned-chrome-open`                      | `playstealth launch`                    |
| `banned-NIEMALS – BANNED (semgrep Regel)` |
| `banned-pyautogui`                        | `BANNED – niemand importiert pyautogui` |
| `banned-pynput`                           | `BANNED – niemand importiert pynput`    |
| `banned-openai-client`                    | `httpx an NVIDIA NIM`                   |
| `banned-coordinates-click`                | `skylight-cli click --x`                |
| `banned-skylight-cli`                     | skylight-cli                            |
| `banned-recovery-mode`                    | `recovery_mode: true`                   |
| `mandatory-playstealth-launch`            | Chrome direkt starten                   |
| `mandatory-nvidia-nim-url`                | Prüft NIM URL                           |

```bash
# Manuell ausführen
semgrep --config=.semgrep_rules.yaml .

# Pre-Commit (automatisch)
# → blockiert Commit wenn BANNED Muster gefunden
```

## LIVE EYE v6 – Memory-Ringbuffer + Omni Video

`runner/live_eye.py` ist das **Live-Video-Auge**.
Es läuft als eigener Prozess und streamt Echtzeit-Video an Nemotron Omni.

### Architektur

```
mss capture (3ms, 5 FPS) → Ringbuffer (20 Frames, 4s)
  → PyAV encode → MP4 (960x540, CRF 28-40)
  → SSE Streaming → Nemotron Omni → JSON-Entscheidung
```

### Optimierungen (v7, 2026-05-01)

1. **PNG→JPEG quality=50** (Zeile 69) → ~80% weniger Payload
2. **SSE Streaming** (statt blocking POST) → erster Token in <1s
3. **JSON-enforced Prompt** → strukturierte Antwort statt Prosa-Parsing
4. **Adaptive FPS via Motion Detection** → CV2 absdiff frame comparison
5. **Frame-Differencing** → statische Frames überspringen (MSE < 2.0)
6. **Conv3D num_frames Optimierung** → weniger Tokens bei low motion (4 vs -1)
7. **CRF Auto-Adjustment** → CRF 28 (motion) / 35 (mid) / 40 (static)

### Motion Detection Details

| Motion Class | MSE Threshold | CRF | Conv3D num_frames | Frame Skip           |
| ------------ | ------------- | --- | ----------------- | -------------------- |
| **high**     | > 15.0        | 28  | -1 (auto)         | Nein                 |
| **mid**      | 2.0 - 15.0    | 35  | 8                 | Nein                 |
| **low**      | < 2.0         | 40  | 4                 | ✅ Ja (übersprungen) |

### LiveEye vs LiveOmniMonitor

| Aspekt      | LiveEye (live_eye.py) | LiveOmniMonitor (live_omni_monitor.py) |
| ----------- | --------------------- | -------------------------------------- |
| Capture     | mss (3ms/FPS)         | skylight-cli screenshot                |
| Video       | PyAV encode → MP4     | screen-follow + ffmpeg                 |
| Streaming   | ✅ SSE                | ✅ SSE                                 |
| Screenshot  | Nein (nur Video)      | Ja (alle Steps)                        |
| Execute     | Nein (nur Analyse)    | Ja (skylight click)                    |
| JSON Prompt | ✅ v6                 | ✅ vorhanden                           |

### WICHTIG – NICHT VERGESSEN

- **AKTIVES MODELL**: `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` (Zeile 14 in live_eye.py)
- **NICHT** `meta/llama-3.2-11b-vision-instruct` (das ist der Legacy-Worker A2A-SIN-Worker-heypiggy)
- **NICHT** `mistralai/mistral-large-3-675b-instruct-2512` (veralteter mcp_survey_runner.py)
- **Aktiver Code**: `stealth-runner/runner/live_eye.py` + `live_omni_monitor.py`
- **Archiviert**: A2A-SIN-Worker-heypiggy (BRAIN.md sagt "ARCHIVIERT")

## DATEIEN

| Datei                            | Zweck                                      |
| -------------------------------- | ------------------------------------------ |
| `runner/live_eye.py`             | Live-Video-Ringbuffer → Omni (v6, SSE)     |
| `runner/live_omni_monitor.py`    | Rolling Video + Screenshot + SSE Streaming |
| `runner/nemotron_omni.py`        | OmniClient – Video/Audio/Bild/Text         |
| `runner/vision_client/core.py`   | Vision-Client Omni-first + Fallback        |
| `runner/video_analyzer.py`       | CLI-Tool für Screen-Follow-Analyse         |
| `runner/omni_survey_runner.py`   | Kompletter Survey-Durchlauf Omni-gesteuert |
| `runner/step.py`                 | Ein-Schritt-Orchestrator mit Multi-Frame   |
| `runner/state_machine.py`        | State-Machine Omni-integriert              |
| `runner/stealth_executor.py`     | Executor mit hold/drag/verify              |
| `config/vision_models.yaml`      | Modell-Konfiguration                       |
| `.semgrep_rules.yaml`            | 11 Architektur-Regeln (CI/CD)              |
| `graphify-out/merged-graph.json` | Knowledge Graph (4820 nodes)               |
| `graphify-out/graph.html`        | Interaktiver D3.js-Graph                   |
| `cli/heypiggy-login`             | Google Login (nur skylight-cli)            |
| `profiles/jeremy.yaml`           | Credentials (NICHT committen)              |

## BEFEHLE (NUR DIESE NUTZEN)

```bash
# Chrome starten (isoliert)
playstealth launch --url 'https://heypiggy.com/?page=dashboard'

# Screenshot
skylight-cli screenshot --pid <PID> --mode som --output /tmp/step.png

# Element finden
skylight-cli list-elements --pid <PID>

# Klicken (NUR per Index, nie per Koordinaten)
skylight-cli click --pid <PID> --element-index <N>

# Text eingeben (NUR per Index)
skylight-cli type --pid <PID> --element-index <N> --text "wert"

# Live Omni Monitor starten
python3 -c "from runner.live_omni_monitor import LiveOmniMonitor; m=LiveOmniMonitor(debug=True); m.start(); m.run_continuous(max_steps=50)"

# Schritt-Orchestrator
python3 runner/step.py "https://heypiggy.com/?page=dashboard"

# Knowledge Graph
graphify query "..."
graphify path "ModulA" "ModulB"
graphify explain "Konzept"

# Architektur-Check
semgrep --config=.semgrep_rules.yaml .
```

## 🔑 POPUP-INTERAKTION (CRITICAL: cua-driver, NIE skylight!)

**skylight-cli kann KEINE Popup-Fenster sehen!** Alle Popup-Elemente (Google OAuth, Consent-Dialoge)
müssen via **cua-driver** mit `window_id` targetiert werden:

```bash
# 1. Daemon starten (einmalig)
cua-driver serve &

# 2. Popup finden
POPUP_WID=$(cua-driver call list_windows '{}' | python3 -c "...")

# 3. Popup-Elemente LADEN (cached für window_id)
cua-driver call get_window_state "{\"pid\":$PID,\"window_id\":$POPUP_WID}"

# 4. Im Popup klicken/tippen
cua-driver call click '{"pid":$PID,"window_id":$POPUP_WID,"element_index":$IDX,"action":"press"}'
cua-driver call set_value '{"pid":$PID,"window_id":$POPUP_WID,"element_index":$IDX,"value":"text"}'
```

**Verifiziert mit PID 31710**: Google OAuth Login komplett via cua-driver – 0 Passwort nötig
dank bestehender Cookies aus früheren Chrome-Profilen.

Siehe `docs/cua-driver-popup-pattern.md` für vollständige Doku.

## VERBOTEN (BANNED – blockiert durch semgrep pre-commit)

- `playstealth launch (isolierte PID)"`
- `BANNED (Mausbewegung verboten)`, `BANNED (Mausbewegung verboten)`
- `httpx an NVIDIA NIM`, `httpx an NVIDIA NIM`
- `skylight-cli click --x ...` (Koordinaten raten)
- `skylight-cli click --x --y` (Koordinatenraten – erlaubt ist NUR mit `--element-index`)
- `skylight-cli click --pid X --element-index Y` **in Popups** → klickt FALSCHES Element!
- skylight-cli MCP
- Nutzer-Chrome manipulieren
- Ohne Primer klicken
- `recovery_mode: true`, `omni_fallback: llama`

## ERLAUBT (cua-driver für Popups, skylight-cli für Hauptfenster)

| Kontext | Tool | Befehl |
|---------|------|--------|
| Hauptfenster | `skylight-cli` | `click --pid X --element-index Y` |
| Hauptfenster | `skylight-cli` | `list-elements --pid X` |
| **Popup-Fenster** | **`cua-driver`** | `call click '{"pid":X,"window_id":W,"element_index":Y}'` |
| **Popup-Fenster** | **`cua-driver`** | `call get_window_state '{"pid":X,"window_id":W}'` |
| **Popup-Fenster** | **`cua-driver`** | `call set_value '{"pid":X,"window_id":W,"element_index":Y,"value":"text"}'` |
| Window-Liste | `cua-driver` | `call list_windows '{}'` |

## MODEL NAME HISTORY

- `nvidia/nemotron (doppelter Prefix entfernt)-3-nano-omni-30b-a3b-reasoning` → ❌ 404 (doppelter Prefix)
- `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` → ✅ HTTP 200, SSE funktioniert
