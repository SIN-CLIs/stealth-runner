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

## DATEIEN

| Datei                            | Zweck                                      |
| -------------------------------- | ------------------------------------------ |
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

## VERBOTEN (BANNED – blockiert durch semgrep pre-commit)

- `playstealth launch (isolierte PID)"`
- `BANNED – niemand importiert pyautogui`, `BANNED – niemand importiert pynput`
- `httpx an NVIDIA NIM`, `httpx an NVIDIA NIM`
- `skylight-cli click --x ...` (Koordinaten raten)
- skylight-cli MCP
- Nutzer-Chrome manipulieren
- Ohne Primer klicken
- `recovery_mode: true`, `omni_fallback: llama`

## MODEL NAME HISTORY

- `nvidia/nemotron (doppelter Prefix entfernt)-3-nano-omni-30b-a3b-reasoning` → ❌ 404 (doppelter Prefix)
- `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` → ✅ HTTP 200, SSE funktioniert
