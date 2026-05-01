# AGENTS.md – Stealth-Runner mit NVIDIA Nemotron 3 Nano Omni

## VISION-MODELL: Nemotron 3 Nano Omni (PRIMARY)
- **30B-A3B Mixture-of-Experts** – Video + Audio + Bild + Text in EINEM Modell
- **9× effizienter** als separate Vision+Sprache-Stacks
- **Native 1920×1080** – volle HD-Auflösung ohne Downsampling
- **256K Kontext** – ganze Survey-Sessions in einem Call
- **Conv3D Videokompression** – 2× weniger Tokens für Video
- **API**: NVIDIA NIM (gleicher Endpoint, gleicher `NVIDIA_API_KEY`)
- **Fallback**: Llama 3.2 90B Vision (automatisch bei Fehler)

## NEUE FÄHIGKEITEN DURCH OMNI

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

### Survey-Flow-Prediction
- Nach Schritt 5+ wird automatisch der Flow vorhergesagt
- `Nemotron Omni` analysiert das Muster und sagt nächste Aktion voraus
- Fehlererkennung: Captcha, Timeout, Disqualifikation

## DATEIEN
| Datei | Zweck |
|-------|-------|
| `runner/nemotron_omni.py` | OmniClient – Video/Audio/Bild/Text in einem Call |
| `runner/vision_client/core.py` | Vision-Client Omni-first + Fallback |
| `runner/video_analyzer.py` | CLI-Tool für Screen-Follow-Analyse |
| `runner/step.py` | Ein-Schritt-Orchestrator mit Multi-Frame |
| `runner/state_machine.py` | Vollständige State-Machine Omni-integriert |
| `runner/stealth_executor.py` | Executor mit hold/drag Unterstützung |
| `config/vision_models.yaml` | Modell-Konfiguration |

## BEFEHLE (NUR DIESE NUTZEN)
```bash
# Chrome starten (isoliert)
playstealth launch --url 'https://heypiggy.com/?page=dashboard'

# Screenshot
skylight-cli screenshot --pid <PID> --mode som --output /tmp/step.png

# Element finden
skylight-cli list-elements --pid <PID>

# Klicken
skylight-cli click --pid <PID> --element-index <N>

# Text eingeben
skylight-cli type --pid <PID> --element-index <N> --text "wert"

# Schritt-Orchestrator
python3 runner/step.py "https://heypiggy.com/?page=dashboard"
```

## VERBOTEN (BANNED)
- webauto-nodriver MCP
- Koordinaten raten (`--x`/`--y`)
- Nutzer-Chrome manipulieren
- Chrome-Prozesse killen
- Ohne Primer klicken

## graphify

This project has a graphify knowledge graph at graphify-out/.

Rules:
- Before answering architecture or codebase questions, read graphify-out/GRAPH_REPORT.md for god nodes and community structure
- If graphify-out/wiki/index.md exists, navigate it instead of reading raw files
- For cross-module "how does X relate to Y" questions, prefer `graphify query "<question>"`, `graphify path "<A>" "<B>"`, or `graphify explain "<concept>"` over grep — these traverse the graph's EXTRACTED + INFERRED edges instead of scanning files
- After modifying code files in this session, run `graphify update .` to keep the graph current (AST-only, no API cost)
