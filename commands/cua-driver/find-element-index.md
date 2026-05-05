# CUA-DRIVER FIND ELEMENT INDEX — VERIFIED ✅

## Status
**VERIFIED** — 2026-05-05

## Was es tut
Aus dem AX-Tree (get_window_state) die element_index Nummer eines Elements finden.

## Methode 1: grep (schnell)
```bash
echo '{"pid": PID, "window_id": WID}' | cua-driver call get_window_state | python3 -c "
import json, sys
d = json.load(sys.stdin)
tree = d.get('tree_markdown', '')
for line in tree.split('\n'):
    if 'KEYWORD' in line.lower():
        print(line.strip())
"
```

## Methode 2: regex extrahieren
```bash
echo '{"pid": PID, "window_id": WID}' | cua-driver call get_window_state | python3 -c "
import json, sys, re
d = json.load(sys.stdin)
tree = d.get('tree_markdown', '')
for line in tree.split('\n'):
    low = line.lower()
    if 'KEYWORD' in low and ('button' in low or 'textfield' in low or 'link' in low):
        m = re.search(r'- \[(\d+)\]', line)
        if m:
            print(f'Index={m.group(1)} Line={line.strip()[:150]}')
"
```

## Live Beispiel (Email-Feld, OAuth Screen)
```bash
echo '{"pid": 78708, "window_id": 57141}' | cua-driver call get_window_state | python3 -c "
import json, sys, re
d = json.load(sys.stdin)
for line in d.get('tree_markdown','').split('\n'):
    if 'e-mail' in line.lower() and 'textfield' in line.lower():
        m = re.search(r'- \[(\d+)\]', line)
        print(f'Email Field Index={m.group(1)}')
"
# → - [25] AXTextField (E-Mail oder Telefonnummer) @(735,549,450,54)
# → Index=25
```

## AXRole Mapping
| AXRole | Suchwort | Verwendung |
|--------|---------|-----------|
| AXButton | "button" | Klickbare Buttons |
| AXLink | "link" | Google Login-Symbol (AXLink!) |
| AXTextField | "textfield" | Eingabefelder |
| AXSecureTextField | "securetextfield" | Passwort-Felder |
| AXCheckBox | "checkbox" | Checkboxen |
| AXRadioButton | "radiobutton" | Radio-Buttons |
| AXHeading | "heading" | Überschriften |
| AXStaticText | "statictext" | Text-Labels |

## Typische Such-Patterns
```bash
# Button mit Label finden
grep -i "weiter.*button" 

# TextField finden
grep -i "email.*textfield"

# Google Login (AXLink, nicht AXButton!)
grep -i "google.*link"
```

## WARNUNG
- Element-Indizes sind DYNAMISCH → nie hardcoden!
- Google Login ist AXLink [54], NICHT AXButton!
- AXRole mit Label kombinieren → präziser Match
- IMMER nach jeder Aktion neu scannen (Indizes können sich ändern!)

## Test Log
- 2026-05-05: Email [25], Weiter [35], Google Login [54] alle via grep gefunden ✅