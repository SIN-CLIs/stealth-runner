# stealth-skill: heypiggy-survey

> **Autonome Umfrage-Durchführung auf HeyPiggy — Dashboard → Screening → Abschluss**
> Nur skylight-cli + playstealth. KEIN skylight-cli.

---

## 🚀 Start

```bash
playstealth launch --url 'https://heypiggy.com/?page=dashboard'
PID=$(python3 -c "import subprocess,json,sys;r=subprocess.run(['playstealth','launch','--url','https://heypiggy.com/?page=dashboard'],capture_output=True,text=True,timeout=30);print(json.loads(r.stdout.split(chr(10))[-1]).get('pid',''))")
```

## 📋 Dashboard scannen

```bash
skylight-cli list-elements --pid $PID | python3 -c "
import json,sys
for e in json.load(sys.stdin)['elements']:
    l=e.get('label','')
    if 'AXWebArea' in (e.get('path','')) and ('Umfrage' in l or '€' in l):
        print(f'[{e[\"index\"]}] {e[\"role\"]}: {l[:80]}')
"
```

## 🎯 Umfrage starten

```bash
# Beste Umfrage finden und klicken
skylight-cli click --pid $PID --element-index <SURVEY_INDEX>
sleep 3
```

## 📝 Screening-Fragen

- Radio-Buttons: `skylight-cli click --pid $PID --element-index N`
- Multi-Select: mehrere Checkboxen klicken
- Numerisch: `skylight-cli type --pid $PID --element-index N --text "34"`
- Weiter: `skylight-cli click --pid $PID --element-index <WEITER_INDEX>`

## ⚠️ Fangfragen-Regeln

- Nie "Keine" oder "Nichts davon"
- Immer 3-4 Marken auswählen
- "Kaufe mind. 1x/Monat" antworten

## 🛠️ Tools (NUR diese!)

| Tool         | Befehl                                 |
| ------------ | -------------------------------------- |
| skylight-cli | click, type, list-elements, screenshot |
| playstealth  | launch --url                           |

## ❌ NIEMALS

- skylight-cli → BANNED
- osascript → BANNED
- Nutzer-Chrome manipulieren → BANNED
