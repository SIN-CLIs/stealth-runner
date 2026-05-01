# commands.md - Korrekte Befehle (NUR DIESE NUTZEN)

## Chrome starten (isoliert, eigene PID)
```bash
playstealth launch --url 'https://heypiggy.com/?page=dashboard'
# Output: {"pid": 97228, "status": "ok"}
```

## Screenshot (VOR/NACH jedem Schritt)
```bash
skylight-cli screenshot --pid <PID> --mode som --output /tmp/schritt_vor.png
```

## Elemente finden
```bash
skylight-cli list-elements --pid <PID> | python3 -c "
import json,sys
for e in json.load(sys.stdin)['elements']:
    label = e.get('label','').lower()
    if 'google' in label or 'weiter' in label or 'telefon' in label:
        print(f'Index={e[\"index\"]}, Label=\"{e.get(\"label\",\"\")}\"')
"
```

## Element klicken (NUR per Index)
```bash
skylight-cli click --pid <PID> --element-index <N>
```

## Text eingeben (NUR per Index)
```bash
skylight-cli type --pid <PID> --element-index <N> --text "wert"
```

## Google Login (automatisiert)
```bash
bash cli/heypiggy-login <PID>
```

## Live Omni Monitor
```bash
python3 -c "
from runner.live_omni_monitor import LiveOmniMonitor
m = LiveOmniMonitor(fps=1.0, debug=True)
m.start('https://heypiggy.com/?page=dashboard')
m.run_continuous(max_steps=100)
"
```

## Video-Analyse (post-mortem)
```bash
# Letzte Aufnahme auf Fehler prüfen
python3 -m runner.video_analyzer --last errors

# Kompletten Flow analysieren
python3 -m runner.video_analyzer --last flow

# Captcha-Prüfung
python3 -m runner.video_analyzer --last captcha

# Vorher/Nachher Vergleich
python3 -m runner.video_analyzer --compare /tmp/step_3.png /tmp/step_4.png
```

## Graphify Knowledge Graph
```bash
graphify query "Wie hängt X mit Y zusammen?"
graphify path "ModulA" "ModulB"
graphify explain "Konzept"
graphify update .                    # AST-Rebuild nach Code-Änderungen
graphify hook status                 # Prüfen ob Hooks aktiv
```

## Semgrep Architecture Guard
```bash
# Manuell ausführen
semgrep --config=.semgrep_rules.yaml .

# Im Pre-Commit (automatisch)
# → blockiert Commit wenn BANNED Muster gefunden
```

## System-Check
```bash
# API testen (Nemotron Omni)
curl -s -H "Authorization: Bearer $NVIDIA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"nvidia/nemotron-3-nano-omni-30b-a3b-reasoning","messages":[{"role":"user","content":"say ok"}],"max_tokens":5}' \
  "https://integrate.api.nvidia.com/v1/chat/completions"

# SSE Streaming testen
curl -s -H "Authorization: Bearer $NVIDIA_API_KEY" \
  -H "Accept: text/event-stream" \
  -H "Content-Type: application/json" \
  -d '{"model":"nvidia/nemotron-3-nano-omni-30b-a3b-reasoning","messages":[{"role":"user","content":"say hello"}],"stream":true,"max_tokens":20}' \
  "https://integrate.api.nvidia.com/v1/chat/completions"
```

## Schritt-Orchestrator
```bash
python3 runner/step.py "https://heypiggy.com/?page=dashboard"
```
