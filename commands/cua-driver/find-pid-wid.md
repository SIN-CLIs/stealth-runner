# CUA-DRIVER FIND PID & WID — VERIFIED ✅

## Status
**VERIFIED** — 2026-05-05

## Was es tut
BOT Chrome PID (Process ID) und WID (Window ID) dynamisch finden.

## PID finden

### Methode 1: playstealth launch (NEU)
```bash
playstealth launch --url 'https://heypiggy.com/?page=dashboard'
# → {"pid": 78708, "profile": "/tmp/heypiggy-bot-1777985655"}
```

### Methode 2: ps + grep (bestehend)
```bash
ps aux | grep "heypiggy-bot-" | grep -v grep | grep "Google Chrome" | grep -v "Helper\|Renderer\|GPU"
# → simoneschulze  78708  ... /Applications/Google Chrome.app/Contents/MacOS/Google Chrome --user-data-dir=/tmp/heypiggy-bot-1777985655
```

### Methode 3: SessionManager (SOTA)
```python
from cli.modules.session_manager import SessionManager
sm = SessionManager()
result = sm.find("heypiggy")
# → {"status": "ok", "pid": 78708, "profile": "/tmp/heypiggy-bot-1777985655"}
```

## WID finden

### Dashboard WID
```bash
cua-driver call list_windows | python3 -c "
import json, sys
d = json.load(sys.stdin)
for w in d.get('windows', []):
    t = (w.get('title') or '').lower()
    h = w.get('bounds',{}).get('height',0)
    if h > 100 and 'heypiggy' in t:
        print(f'PID={w[\"pid\"]} WID={w[\"window_id\"]} title={t[:60]}')
"
# → PID=78708 WID=57128 title=heypiggy – verdienen sie echtes geld...
```

### OAuth WID (nach Google Login Click)
```bash
cua-driver call list_windows | python3 -c "
import json, sys
d = json.load(sys.stdin)
for w in d.get('windows', []):
    t = (w.get('title') or '').lower()
    h = w.get('bounds',{}).get('height',0)
    if h > 100 and 'anmelden' in t:
        print(f'PID={w[\"pid\"]} WID={w[\"window_id\"]}')
"
# → PID=78708 WID=57141
```

### Alle BOT Chrome Windows
```bash
cua-driver call list_windows | python3 -c "
import json, sys
d = json.load(sys.stdin)
for w in d.get('windows', []):
    t = (w.get('title') or '')[:100]
    h = w.get('bounds',{}).get('height',0)
    if h > 100 and w.get('pid') == 78708:
        print(f'WID={w[\"window_id\"]} H={h} {t}')
"
```

## PID/WID in /commands speichern (Session-Marker)
```bash
# PID + WID als JSON für spätere Referenz
echo '{"pid": 78708, "wid": 57128, "ts": "'$(date -Iseconds)'"}' > /tmp/bot_session.json
cat /tmp/bot_session.json
```

## KRITISCHE FILTER
```python
# Filter für BOT Chrome:
bounds.height > 100     # Keine Mini-Fenster (Menüleiste, etc.)
app_name == "chrome"    # Nur Chrome
title enthält Keyword   # heypiggy, google, anmelden, etc.
```

## REGELN
- PID ist IMMER dynamisch → bei jedem Launch neu
- WID ändert sich bei OAuth Popup → nach click NEU scannen!
- `list_windows` gibt DICT `{"windows": [...]}` zurück, NICHT Array
- `bounds` (nicht `frame`) für Höhe verwenden
- USER Chrome (OHNE heypiggy-bot- im path) → NIEMALS touchen!

## Test Log
- 2026-05-05: Dashboard WID=57128, OAuth WID=57141 — beide via list_windows gefunden ✅