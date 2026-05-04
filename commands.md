# commands.md – Alle wichtigen Befehle

> **← [sinrules.md](sinrules.md) ist das zentrale Regelwerk.**
> **← [AGENTS.md](AGENTS.md) listet alle Tool-Befehle.**

---

## CDP+AX Trinity (NEU, PRIMARY)

```bash
# Chrome starten (liefert cdp_port!)
playstealth launch --url 'https://accounts.google.com/ServiceLogin'
# → {"pid": 48403, "cdp_port": 61934, "cdp_ws": "ws://127.0.0.1:61934"}

# Email-Feld finden + tippen (cdp_click)
python3 -c "
from cli.modules.cdp_click import click_by_label, type_by_label
import asyncio
asyncio.run(type_by_label(pid=48403, cdp_port=61934,
    label='E-Mail oder Telefonnummer', text='zukunftsorientierte.energie@gmail.com'))
"

# Weiter klicken (cdp_click)
python3 -c "
from cli.modules.cdp_click import click_by_label
import asyncio
asyncio.run(click_by_label(pid=48403, cdp_port=61934,
    label='Weiter', role='button'))
"
```

---

## Google Login FLOWS

### FLOW A — Frischer Browser (keine Cookies)
```bash
# 1. Email (cdp_click)
asyncio.run(type_by_label(pid, port, 'E-Mail oder Telefonnummer', EMAIL))

# 2. Weiter (cdp_click)
asyncio.run(click_by_label(pid, port, 'Weiter', 'button'))

# 3-6. ... Passkey + Consent via cua
```

### FLOW B — Cookies cached
```bash
# 1. Konto klicken (cdp_click)
asyncio.run(click_by_label(pid, port, 'zukunftsorientierte.energie@gmail.com', 'link'))

# 2. Weiter (cdp_click)
asyncio.run(click_by_label(pid, port, 'Weiter', 'button'))
```

### FLOW C — Google-Login-in-Google
```bash
# 1. Email → Weiter
asyncio.run(type_by_label(pid, port, 'E-Mail oder Telefonnummer', EMAIL))
asyncio.run(click_by_label(pid, port, 'Weiter', 'button'))

# 2. Andere Option wählen
asyncio.run(click_by_label(pid, port, 'Andere Option wählen', 'button'))

# 3. Passwort eingeben (Link)
asyncio.run(click_by_label(pid, port, 'Passwort eingeben', 'link'))

# 4. Passwort tippen + Weiter
asyncio.run(type_by_label(pid, port, 'Passwort eingeben', PASSWORD))
asyncio.run(click_by_label(pid, port, 'Weiter', 'button'))
```

---

## cua-driver (Popups, Sheets, Dialogs)

```bash
# Daemon starten (einmalig)
cua-driver serve &

# Popup finden
cua-driver call list_windows '{}'

# Popul-Elemente laden
cua-driver call get_window_state '{"pid":PID,"window_id":WID}'

# Im Popup klicken
cua-driver call click '{"pid":PID,"window_id":WID,"element_index":N,"action":"press"}'

# Wert setzen
cua-driver call set_value '{"pid":PID,"window_id":WID,"element_index":N,"value":"text"}'
```

---

## skylight-cli (Fallback, Hauptfenster)

```bash
# Elemente listen (NUR zum Finden, NICHT zum Index-Klicken!)
skylight-cli list-elements --pid PID

# Screenshot
skylight-cli screenshot --pid PID --mode som --output /tmp/step.png

# Klick (FALLBACK — wenn CDP nicht verfügbar)
skylight-cli click --pid PID --element-index N
```

---

## macos-ax-cli (System-Scan, NUR Finden)

```bash
# Alle Fenster systemweit
macos-ax-cli windows list

# Text systemweit suchen
macos-ax-cli find "Fortfahren"

# Elemente einer App
macos-ax-cli elements --pid PID
```

---

## Automatisierter Survey

```bash
# Live Omni Monitor
python3 -c "from runner.live_omni_monitor import LiveOmniMonitor; m=LiveOmniMonitor(debug=True); m.start(); m.run_continuous(max_steps=50)"

# Autonomous Daemon
python -m stealth_runner.autonomous_daemon start
python -m stealth_runner.autonomous_daemon status
```

---

## Dokumentation

```bash
# Knowledge Graph
graphify update .
graphify query "Wie funktioniert CDP+AX Trinity?"

# Architecture Guard
semgrep --config=.semgrep_rules.yaml .

# Doctor Audit
python3 runner/doctor_cli.py
```

---

## Captcha Solving (Normal Captcha / Simple Text Captcha)

```bash
# 1. tmux Session starten (Browser bleibt offen!)
tmux new-session -d -s captcha
tmux send-keys -t captcha "python3 /tmp/captcha_simple.py" C-m
sleep 8

# 2. Full Page Scan
tmux send-keys -t captcha "scan" C-m
sleep 2
tmux capture-pane -p -t captcha -S -50

# 3. Screenshot + NVIDIA Vision
tmux send-keys -t captcha "ss" C-m
sleep 2
tmux send-keys -t captcha "nvidia" C-m
sleep 12
tmux capture-pane -p -t captcha -S -5
# → Captcha-Text aus reasoning (Regex: "([A-Z0-9]+)")

# 4. Antwort + Submit
tmux send-keys -t captcha "answer CAPTCHA_TEXT" C-m
sleep 1
tmux send-keys -t captcha "submit" C-m
sleep 3
tmux capture-pane -p -t captcha -S -5
```

**Wichtig:** Browser in tmux OFFEN lassen! Nie schließen zwischen Steps!  
**NVIDIA reasoning Feld parsen** — content ist immer None!  
**Full Page Scan** vor jeder Aktion!

### Survey In-Page Flow

```python
# clickSurvey öffnet IN-PAGE (kein neuer Tab!)
from cli.modules.heypiggy_login_box import heypiggy_login
from cli.modules.survey_runner import scan_surveys, start_survey

# 1. Login
heypiggy_login(pid=2674, cdp_port=55983)

# 2. Survey scannen + starten
surveys = scan_surveys(pid)  # Findet Tab mit .survey-item
start_survey(pid, surveys[0]["id"])

# 3. WARTEN (8s) und AX-Tree rescanen nach In-Page Modal
# Suche: "Umfrage starten", "Starten", ">>", "Willkommensbonus"
```

### Audio Capture Pipeline

```bash
# Voraussetzung: BlackHole installiert (SIP deaktiviert)
python3 -m cli.modules.audio_capture --check
python3 -m cli.modules.audio_capture --capture --duration 6 --analyze

## 🔄 CUA-ONLY SURVEY LOOP (2026-05-04)

### Vor jeder Aktion
```bash
# Fenster frisch finden (NIE hartcodiert!)
cua-driver call list_windows | grep "PID\|title"

# AX-Tree laden mit depth>5 Filter
cua-driver call get_window_state '{"pid":PID,"window_id":WID}'
```

### Klicken (NUR depth>5 Elemente!)
```bash
# Button finden: AXButton mit Label im Tree suchen, depth prüfen
cua-driver call click '{"pid":PID,"window_id":WID,"element_index":IDX,"action":"press"}'
```

### Text eingeben
```bash
# Erst klicken (fokussieren), dann set_value
cua-driver call click '{"pid":PID,"window_id":WID,"element_index":IDX,"action":"press"}'
cua-driver call set_value '{"pid":PID,"window_id":WID,"element_index":IDX,"value":"TEXT"}'
```

### Nach jeder Aktion: Status-Check
```bash
# Hat sich der Seiteninhalt geändert?
cua-driver call get_window_state '{"pid":PID,"window_id":WID}'

# Sind neue Fenster/Tabs offen?
cua-driver call list_windows

# Button DISABLED? → warten, andere Felder prüfen
# Button ENABLED?  → klicken
```

### Wann welcher Befehl?
| Befehl | Wann | Warum |
|--------|------|-------|
| list_windows | Vor JEDEM Schritt | WID kann sich ändern |
| get_window_state | Vor JEDEM Klick | Indices sind instabil |
| depth > 5 FILTER | IMMER | Filtert Browser-Chrome |
| click | Nur wenn ENABLED | DISABLED = andere Felder fehlen |
| set_value | Nach click auf Feld | Erst fokussieren, dann schreiben |

## 🔒 Captcha lösen (NVIDIA Vision)

```bash
# Captcha-Bild auslesen + NVIDIA Omni lösen
cd /Users/jeremy/dev/stealth-runner && source .env

# Captcha-Refresh + Solve + Type + Next in einem
python3 -c "
import ..., httpx, subprocess
# Captcha-Bild aus Seite holen → base64
# NVIDIA API: nemotron-3-nano-omni
# max_tokens=20, temperature=0
# Antwort aus reasoning oder content extrahieren
# cua-driver set_value + click Go to next question
"
```

## ⚡ stealth-exec (schnelle Befehle über Daemon)

```bash
# Daemon starten
stealth-session start

# Befehle (<50ms Antwortzeit)
stealth-exec cua-touch --action click --label "Männlich"
stealth-exec context --action get_all
stealth-exec context --action get_oauth
stealth-exec cua-touch --action get_state
stealth-exec cdp-js --expression "document.title"
```

## 🔒 Verify-Box (Aktion verifizieren)

```bash
# Nach jeder Aktion mit verify: true prüfen
stealth-exec cua-touch --action click --label "Männlich" -j '{"verify": true}'
# → {"success": true/false, "verify": {"success": bool, "details": "selected/not selected"}}

# Was die Verify-Box prüft:
# - click RadioButton → AXSelected = true?
# - click CheckBox → checked state?
# - set_value Text → Text im Feld?
# - cdp-js → Rückgabewert existiert?
```
