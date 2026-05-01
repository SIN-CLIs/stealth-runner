# commands.md - Korrekte Befehle

## TRIO LAYER (Live Auge-Hirn-Hand)

### 1. Chrome starten
```bash
playstealth launch --url 'https://heypiggy.com/?page=dashboard'
# → {"pid": 42296, "status": "ok"}
```

### 2. EYES: Alle Fenster erkennen
```bash
cua-driver call list_windows | python3 -c "
import json,sys
for w in json.load(sys.stdin).get('windows',[]):
    if w.get('pid') == 42296:
        print(f'  WindowID={w[\"window_id\"]} \"{w.get(\"title\",\"\")[:60]}\" OnScreen={w.get(\"is_on_screen\")}')
"
```

### 3. BRAIN: Nur Popup-Elemente sehen
```bash
cua-driver call get_window_state '{"pid":42296,"window_id":30380}' | python3 -c "
import json,sys
tree = json.load(sys.stdin).get('tree_markdown','')
for line in tree.split(chr(10)):
    if 'Weiter' in line or 'E-Mail' in line or 'Passwort' in line or 'Button' in line:
        print(line.strip()[:100])
"
```

### 4. HANDS: Im Popup klicken (GARANTIERT richtiges Fenster!)
```bash
cua-driver call click '{"pid":42296,"window_id":30380,"element_index":35}'
```

### 5. Text im Popup eingeben
```bash
cua-driver call set_value '{"pid":42296,"window_id":30380,"element_index":25,"value":"test@email.com"}'
```

### 6. Live Trio Loop
```bash
python3 runner/trio_live.py <PID>
```

## GOOGLE LOGIN
```bash
# Komplett automatisiert
bash cli/heypiggy-login <PID>
```

## DOCTOR CLI
```bash
# Alle 6 Repos scannen + fixen
python3 runner/doctor_cli.py
```

## GRAPHIFY
```bash
graphify query "Wie hängt X mit Y zusammen?"
graphify path "ModulA" "ModulB"
graphify update .
```

## SEMGREP
```bash
semgrep --config=.semgrep_rules.yaml .
```
