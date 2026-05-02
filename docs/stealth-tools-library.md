# Stealth Tools Library – Alle Befehle & Patterns

## 1. Browser Launch (playstealth)
```bash
# ✅ KORREKT
playstealth --json launch --url 'https://heypiggy.com/?page=dashboard'

# ❌ FALSCH (--json am Ende)
playstealth launch --url X --json
```

## 2. Hauptfenster-Interaktion (skylight-cli)
```bash
skylight-cli list-elements --pid <PID>        # Elemente auflisten
skylight-cli click --pid <PID> --element-index <N>  # Klicken
skylight-cli type --pid <PID> --element-index <N> --text "..."  # Tippen
skylight-cli screenshot --pid <PID> --mode som  # Screenshot (ignoriert --output!)
```

**Workaround**: `skylight-cli` ignoriert `--output` – schreibt immer nach `./skylight_screenshot.png`. Workaround in `skylight.py` nutzt temporäres Verzeichnis.

## 3. Popup-Interaktion (cua-driver) ⭐ KRITISCH
skylight-cli kann KEINE Popup-Fenster sehen! Popups (Google OAuth, Consent) via cua-driver:

```bash
# Daemon starten (einmalig pro Session)
cua-driver serve &

# Popup finden
cua-driver call list_windows '{}'

# Popup-Elemente laden (cacht per window_id)
cua-driver call get_window_state '{"pid":PID,"window_id":WID}'

# Im Popup klicken (NICHT skylight!)
cua-driver call click '{"pid":PID,"window_id":WID,"element_index":N,"action":"press"}'

# Text im Popup setzen
cua-driver call set_value '{"pid":PID,"window_id":WID,"element_index":N,"value":"text"}'
```

## 4. Vision AI (Nemotron Omni)
```python
import httpx, base64
from PIL import Image; from io import BytesIO

# PNG → JPEG (quality=40) für 90% weniger Payload
img = Image.open(path).convert('RGB')
buf = BytesIO(); img.save(buf, format='JPEG', quality=40)
b64 = base64.b64encode(buf.getvalue()).decode()

r = httpx.post('https://integrate.api.nvidia.com/v1/chat/completions',
    headers={'Authorization': f'Bearer {key}'},
    json={'model': 'nvidia/nemotron-3-nano-omni-30b-a3b-reasoning',
          'messages': [{'role': 'user', 'content': [
              {'type': 'text', 'text': prompt},
              {'type': 'image_url', 'image_url': {'url': f'data:image/jpeg;base64,{b64}'}}
          ]}],
          'max_tokens': 1000},
    timeout=60)

msg = r.json()['choices'][0]['message']
# WICHTIG: JSON-Antwort ist in 'content', Reasoning in 'reasoning'
json_answer = msg.get('content') or ''
reasoning = msg.get('reasoning') or ''
```

**Konfiguration** (`config/vision_models.yaml`):
```yaml
current_model: nvidia/nemotron-3-nano-omni-30b-a3b-reasoning
max_tokens: 1000     # NIEMALS 300! Reasoning braucht Platz
timeout: 60
```

## 5. Survey Automation
```bash
# Ein Schritt (wiederhole für Loop)
PYTHONPATH=. python3 runner/step.py "https://heypiggy.com/?page=dashboard"

# Voiceover + Loop
python3 run_survey_with_voice.py

# Manueller Loop
cd ~/dev/stealth-runner
while true; do
    python3 runner/step.py 2>&1 | tail -1
    sleep 3
done
```

## 6. Video Recording (screen-follow)
```bash
# Start (in tmux, nie direkt!)
screen-follow record --video --output /tmp/session.mp4
```

## 7. tmux Background (NON-BLOCKING)
```bash
# Session erstellen
tmux new-session -d -s survey -c ~/dev/stealth-runner

# Command senden
tmux send-keys -t survey "command" Enter

# Logs lesen
tmux capture-pane -t survey -p -S -20
```

## 8. /doctor Skill
```bash
python3 runner/doctor_cli.py  # Full scan + fix + commit
python3 runner/doctor_cli.py --dry-run  # Report only
```

## 9. Knowledge Graph
```bash
graphify update .
graphify query "Frage?"
graphify path "ModulA" "ModulB"
```

## 10. BANNED – NIEMALS NUTZEN
```bash
# ❌ Popup-Klicks via skylight-cli
skylight-cli click --pid X --element-index Y  # wenn Popup offen!

# ❌ bash mit & für Background
bash("command &")  # blockiert die Shell trotzdem!

# ❌ PNG direkt (kein JPEG)
openai-Client  # NVIDIA Key verbrennen!
```
