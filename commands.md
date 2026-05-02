# commands.md – Alle wichtigen Befehle

## Google Login (cua-driver Popup-Methode – 2026-05-02)

```bash
# 1. Chrome starten
playstealth --json launch --url 'https://heypiggy.com/?page=dashboard'

# 2. cua-driver daemon (einmalig)
cua-driver serve &

# 3. Google Login Button klicken (Hauptfenster via skylight)
skylight-cli click --pid <PID> --element-index 33

# 4. Popup Window-ID finden
cua-driver call list_windows '{}' | python3 -c "import sys,json;[print(w['window_id']) for w in json.load(sys.stdin).get('windows',[]) if w.get('pid')==<PID> and 'anmelden' in (w.get('title','')or'').lower()]"

# 5. Email im Popup eintippen
cua-driver call set_value '{"pid":<PID>,"window_id":<WID>,"element_index":25,"value":"zukunftsorientierte.energie@gmail.com"}'

# 6. Weiter im Popup klicken
cua-driver call click '{"pid":<PID>,"window_id":<WID>,"element_index":35,"action":"press"}'

# 7. Consent "Fortfahren" klicken
cua-driver call click '{"pid":<PID>,"window_id":<WID>,"element_index":65,"action":"press"}'

# 8. Finales "Weiter" klicken → LOGGED IN
cua-driver call click '{"pid":<PID>,"window_id":<WID>,"element_index":41,"action":"press"}'
```

## Survey Automation

```bash
# Live Omni Monitor (Screenshot + Video + Voice)
python3 run_survey_with_voice.py

# Schritt-Orchestrator (ein Schritt pro Aufruf)
PYTHONPATH=. python3 runner/step.py "https://heypiggy.com/?page=dashboard"

# Live Eye v7 (Motion Detection)
PYTHONPATH=. python3 runner/live_eye.py
```

## Video & Analysis

```bash
# Screen recording (in tmux)
screen-follow record --video --output /tmp/session.mp4

# Video-Analyse mit Nemotron Omni
python3 -m runner.video_analyzer --last flow

# Screenshot + Omni Vision
skylight-cli screenshot --pid <PID> --mode som
cp skylight_screenshot.png /tmp/page.png
python3 -c "from runner.nemotron_omni import get_omni; print(get_omni().analyze_image('/tmp/page.png'))"
```

## Knowledge Graph

```bash
graphify query "Wie hängen skylight-cli und stealth-runner zusammen?"
graphify path "StealthExecutor" "LiveOmniMonitor"
graphify explain "SkylightDriver"
graphify update .
```

## /doctor

```bash
python3 runner/doctor_cli.py           # Full scan + fix + commit
python3 runner/doctor_cli.py --dry-run # Report only
```

## tmux Background

```bash
# Session erstellen
tmux new-session -d -s mysession -c ~/dev/stealth-runner

# Command in Pane senden (non-blocking)
tmux send-keys -t mysession "command" Enter

# Logs lesen (non-blocking)
tmux capture-pane -t mysession -p -S -50
```
