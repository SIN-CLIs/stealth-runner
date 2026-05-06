# learn.md — HEUTE GELERNT (2026-05-06)

## 🔥 GOOGLE LOGIN — VERIFIED WORKING (PID=95165, PID=86834)

### Der Flow (cua-driver PRIMARY, CDP FALLBACK)
```
1. Invariants prüfen: daemon, Chrome port, Accessibility, AX-Tree elements
2. cua-driver list_windows → Dashboard WID finden (per TITLE, nicht owner!)
3. cua-driver get_window_state → tree_markdown regex parsen
4. Regex: - [N] AXLink (Google Login-Symbol) → element_index
5. cua-driver click → OAuth Popup erscheint (NEUE WID)
6. Regex: - [N] AXTextField (E-Mail…) → set_value email
7. Regex: - [N] AXButton "Weiter" → click
8. Passkey: Regex "weiter" oder "fortfahren" → click → macOS TouchID auto
9. Regex "fortfahren" → click
10. Regex "weiter" → click (Consent)
11. Verify: "Abmelden" + "Umfragen" in tree_markdown
```

### KRITISCH: cua-driver Output-Formate (DAS hat Stunden gekostet)

| Command | Output | Parser |
|---------|--------|--------|
| `list_windows` | JSON | `json.loads()` ✅ |
| `get_window_state` | JSON mit `tree_markdown` String | `json.loads()`, dann Regex |
| `click` | **TEXT** `"✅ Performed AXPress on [N]"` | `"Performed" in stdout` |
| `set_value` | **TEXT** `"✅ Set AXValue on [N]"` | `"Set" in stdout` |

**NIE `json.loads()` auf `click`/`set_value` Output!**
**NIE `el.get("children", [])` auf `get_window_state` — nutze `tree_markdown`!**
**NIE `owner` Feld nutzen (ist LEER) — nutze `title` für Fenster-Identifikation!**

### Markdown-Parser Regex (MUSS beide Formate matchen)
```python
# Format 1: - [35] AXButton (Weiter)         ← mit Klammern
# Format 2: - [35] AXButton "Weiter"         ← mit Anführungszeichen
re.compile(r'-\s*\[(\d+)\]\s+' + role + r'\s+[\(“\"]([^\)\"”]+)[\)\"”]')
```

## 🔥 CHROME — UNVERBRÜCHLICHE REGELN

```bash
# NUR SO starten:
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9999 \
  --remote-allow-origins=* \
  --force-renderer-accessibility \
  --no-first-run \
  --user-data-dir=/tmp/heypiggy-bot \
  'URL'
```

- ❌ `playstealth launch` — setzt NICHT `--force-renderer-accessibility`
- ❌ Ohne `--force-renderer-accessibility` — cua-driver AX-Tree LEER (0 children, 0 tree_markdown)
- ❌ Ohne `--remote-allow-origins=*` — CDP WebSocket 403
- ✅ Profil `/tmp/heypiggy-bot` FEST (nicht timestamped) → Login-Cookies persistent
- ✅ Chrome NIEMALS killen nach Accessibility-Grant (Permission geht verloren)

## 🔥 NIM NEMOTRON 3 OMNI — REASONING MODEL

- `max_tokens=600` (nicht 200!) — Model braucht Tokens zum DENKEN
- KEIN system prompt (verwirrt das Reasoning-Model)
- Chain-of-thought: "Think step by step… Your JSON:"
- Alternativ: `openai/gpt-oss-120b` ist 10× schneller für einfache Fragen

## 🔥 Angular v19: JS .click() IGNORIERT

- Nur CDP `Input.dispatchMouseEvent` funktioniert (isTrusted=true)
- Alle PureSpectrum-Buttons brauchen CDP-Click via `cdp_click_button()`
- JS `.click()` und `dispatchEvent(new MouseEvent(...))` werden ignoriert

## 🔥 PureSpectrum Flow (vollständig)

```
1. Cookie Consent: JS querySelector('button') → click
2. ROBOT Textarea: textarea.value = 'ROBOT ...' → CDP-click Nächste
3. Text Captcha: base64 img src → NVIDIA Vision OCR → fill input → CDP-click Nächste
4. Drag Puzzle: __ngContext__ recursive → findInstance → dropListRef.drop()
```

## 🔥 CPX API: details_url MUSS vom Dashboard kommen

```python
# ❌ Hardcoded URL → "No surveys available"
# ✅ Live URL vom Dashboard via Runtime.evaluate:
details_url = js_eval("details_url")
```
Dashboard hat zusätzliche Parameter: `secure_hash_offerwall`, `m`, `m_1`, etc.

## 🔥 Zombie-Tabs — TOD für tab_ws Tracking

- Vor JEDEM Survey-Run: alle nicht-Dashboard Tabs schließen
- `_find_survey_tab_ws()` muss den NEUESTEN Tab priorisieren
- Nie `chrome.find_survey_tab()` als Fallback (findet Zombie-Tabs)

## 🔥 Gelöschte Dateien (Lügen/Fehler)

- `survey/login.py`: Behauptete "already_logged_in" auf Landing-Page → GELÖSCHT
- Alte `_find_by_role()`: Traversierte `el.get("children", [])` das nicht existiert → ERSETZT

## 🔥 Chrome auf Port 9999 — NIE anders

```python
# login.py startet Chrome IMMER auf 9999:
subprocess.Popen([
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "--remote-debugging-port=9999",
    "--remote-allow-origins=*",
    "--force-renderer-accessibility",
    "--no-first-run",
    "--user-data-dir=/tmp/heypiggy-bot",
    launch_url,
])
```
- Nach Login: Dashboard auf Port 9999 ist eingeloggt
- Daemon nutzt Port 9999 → sieht eingeloggten Zustand
- Profil `/tmp/heypiggy-bot` persistent → Cookies bleiben
- **Nie playstealth (random Port). Nie ohne Accessibility.**

## 🔥 VERIFIED HEUTE (2026-05-06)

| PID | Tool | Ergebnis |
|-----|------|----------|
| 86834 | cua-driver login | ✅ First success after regex fix |
| 95165 | cua-driver login | ✅ Full flow: Google→OAuth→Passkey→Fortfahren→Consent |
| 97688 | cua-driver login | ✅ On port 9999, daemon-ready |
| 9999 | Daemon scan | ✅ 12 surveys, 2.15€ balance |

## 🔥 Invariant-Guard Pattern (für ALLE zukünftigen Tools)

```python
def _verify_invariants():
    errors = []
    if not daemon_running: errors.append("cua-driver daemon NOT running")
    if not chrome_on_9999: errors.append("Chrome NOT on port 9999")
    if not accessibility_enabled: errors.append("AX-Tree < 100 elements")
    if errors: return False
    return True
```
**JEDES Tool MUSS einen Invariant-Guard haben.**

## 🔥 DEBUGGING-TIMELINE (2026-05-06)

| # | Bug | Root Cause | Fix |
|---|-----|-----------|-----|
| 1 | Login crasht `json.loads` | cua-driver `click` returns TEXT "✅ Performed", nicht JSON | `"Performed" in stdout` statt `json.loads()` |
| 2 | "Email or Weiter not found" | Regex matchte nur `(text)`, nicht `"text"` | Regex: `[\(\"]([^\)\"]+)[\)\"]` |
| 3 | 0 AX-Tree children | `get_window_state` hat `tree_markdown`, kein `children[]` | Parse markdown mit Regex |
| 4 | Chrome window not found | `owner` Feld ist LEER in cua-driver | Via `title` suchen statt `owner` |
| 5 | CDP login "success" bei Landing-Page | `cdp_login.py` returned immer OK | Gelöscht, cua-driver ist PRIMARY |
| 6 | 2 Chrome-Instanzen (9999 + playstealth) | `google_login` startete playstealth | Launch direkt auf 9999 |
| 7 | NIM decisions leer | `max_tokens=200` zu wenig für Reasoning-Model | `max_tokens=600`, Chain-of-thought |

## 🔥 subprocess vs Shell Pipe (cua-driver)

```python
# ✅ Shell (funktioniert):
echo '{"pid":84077,"window_id":1704,"element_index":56}' | cua-driver call click

# ✅ Python subprocess (funktioniert auch):
subprocess.run(["cua-driver","call","click"], input=json.dumps(params), 
               capture_output=True, text=True)

# ❌ ABER: json.loads() auf Output → CRASHT bei Text-Antwort!
# cua-driver click/set_value → TEXT, nicht JSON
```

## 🔥 Google OAuth DOM-Struktur

```
Email Page:
  input[type=email] #identifierId @ (25, 217, 450×54)
  button "Weiter" @ (431, 414)

Passkey Page:
  NO "Weiter" button im DOM (nur "Andere Option wählen")
  → cua-driver findet "Weiter" via AX-Tree, nicht CDP
  → Passkey-Lösung ist macOS-Systemdialog → NUR cua-driver!

Fortfahren Page:
  button "Fortfahren" → klicken
  button "Weiter" (Consent) → klicken
```

## 🔥 Provider Detection Patterns

```python
PROVIDER_PATTERNS = {
    "qualtrics":      ["qualtrics.com", "jfe/form"],
    "tolunastart":    ["tolunastart.com"],
    "purespectrum":   ["purespectrum.com"],
    "strat7":         ["strat7audiences.com"],
    "brand_ambassador": ["brand-ambassador.com"],
    "focusvision":    ["focusvision.com"],       # Kantar/Nfield
    "decipher":       ["decipherinc.com"],
    "ipsos":          ["ipsosinteractive.com"],
    "samplicio":      ["samplicio.us"],
    "surveyrouter":   ["surveyrouter.com"],       # BLOCKED
    "gfk":            ["surveys.com"],            # BLOCKED
}
```

## 🔥 GPT-OSS-120B — 10× schneller als Nemotron

```python
# Für 90% der Umfragen reicht dieses Modell:
model = "openai/gpt-oss-120b"  # via NVIDIA NIM
# Schneller, günstiger, gute JSON-Entscheidungen
# Nemotron 3 Omni nur für komplexe Matrix/Video-Fragen
```

## 🔥 reCAPTCHA v2 Checkbox

```python
# 1. iframe-Position finden
iframe = document.querySelector('iframe[title="reCAPTCHA"]')
# 2. CDP-Click bei (iframe.x + 25, iframe.y + iframe.h/2)
# 3. Wait 3s
# 4. "Weiter" Button klicken auf Parent-Page
```

## 🔥 survey-cli Datei-Struktur (final)

```
survey-cli/
├── survey.py                  # CLI Entry (12 commands)
├── survey/
│   ├── google_login.py        # cua-driver login (UNVERÄNDERLICH)
│   ├── cdp_login.py           # CDP fallback login
│   ├── accessibility.py       # Chrome Accessibility Manager
│   ├── chrome.py              # Chrome Lifecycle (launch/create_tab)
│   ├── scanner.py             # Dashboard Scan + Balance
│   ├── runner.py              # NEMO Survey Execution
│   ├── nim.py                 # NVIDIA NIM Client v2
│   ├── snapshot.py            # Compact DOM Snapshot
│   ├── execute.py             # CDP Batch Executor
│   ├── autodoc.py             # Append-only JSONL Logging
│   ├── opencode_bridge.py     # Coding Task Delegation
│   ├── providers/
│   │   ├── purespectrum.py    # OCR + Drag Solver
│   │   ├── qualtrics.py       # .NextButton patterns
│   │   ├── toluna.py          # .cf-radio patterns
│   │   └── strat7.py          # .bsbutton patterns
│   └── profiles/
│       └── jeremy_schulze.json
└── logs/                      # Auto-generated JSONL
```

## 🔥 NIE wieder diese Fehler

1. **NIE `json.loads()` auf cua-driver `click`/`set_value` Output** — es ist TEXT!
2. **NIE `el.get("children")` auf `get_window_state`** — nutze `tree_markdown`!
3. **NIE `owner` Feld für Fenster-Identifikation** — nutze `title`!
4. **NIE `playstealth launch`** — setzt Accessibility-Flag NICHT!
5. **NIE Chrome ohne `--force-renderer-accessibility`** — cua-driver blind!
6. **NIE Chrome ohne `--remote-allow-origins=*`** — CDP 403!
7. **NIE `max_tokens=200` für Nemotron** — Reasoning Model braucht 600+!
8. **NIE system prompt für Nemotron** — Chain-of-thought in user prompt!
9. **NIE JS `.click()` auf Angular-Seiten** — CDP `Input.dispatchMouseEvent`!
10. **NIE Zombie-Tabs offen lassen** — Cleanup vor jedem Survey-Run!
11. **NIE `tccutil reset` ohne Chrome-Neustart** — Permission greift erst nach Restart!
12. **NIE Dashboard-Text mit `?page=dashboard` prüfen** — Landing-Page hat KEINEN Login-Status!
13. **NIE CDP `Page.navigate`** — nutze `Target.createTarget` für neue Tabs!
14. **NIE `pkill -f heypiggy-bot`** — killt USER Chrome mit!
15. **NIE API-URLs hartcodieren** — `details_url` MUSS vom Dashboard kommen!

## 🔥 CDP WebSocket Patterns

```python
# ALLE CDP-Interaktionen gehen über WebSocket:
ws = websocket.create_connection(ws_url, timeout=15)

# JS ausführen (Inhalt lesen):
ws.send(json.dumps({"id":0, "method":"Runtime.evaluate",
    "params":{"expression": "document.body.innerText"}}))

# Maus-Klick (Angular-proof):
ws.send(json.dumps({"id":0, "method":"Input.dispatchMouseEvent",
    "params":{"type":"mousePressed","x":x,"y":y,"button":"left","clickCount":1}}))

# Screenshot:
ws.send(json.dumps({"id":0, "method":"Page.captureScreenshot",
    "params":{"format":"png", "clip":{"x":0,"y":0,"width":200,"height":100,"scale":2}}}))

# Neuer Tab:
ws.send(json.dumps({"id":0, "method":"Target.createTarget",
    "params":{"url": "..."}}))

# Tab schließen:
ws.send(json.dumps({"id":0, "method":"Target.closeTarget",
    "params":{"targetId": tab_id}}))
```

## 🔥 Survey Provider Patterns (getestet)

| Provider | Button | Radio | Text | Matrix | Payout |
|----------|--------|-------|------|--------|--------|
| **Qualtrics** | `.NextButton` | `input[type=radio][idx]` | `textarea.InputText` | `table.ChoiceStructure` | ~0.38€ |
| **TolunaStart** | `button` | `.cf-radio[idx].click()` JS | `input[type=number]` | `.cf-radio` global | ~0.09€ |
| **Strat7** | `.bsbutton:not([disabled])` | `input[type=radio][idx]` | `input[type=text]` | - | ~0.03-0.09€ |
| **BrandAmbassador** | `.submit-btn` | `input[type=radio][idx]` | - | - | ~0.02€ |
| **FocusVision** | `input[type=submit]` | Standard | Standard | - | variabel |
| **PureSpectrum** | `button` (CDP!) | - | `textarea` ROBOT | - | blockiert |

## 🔥 Survey Completion Detection

```python
COMPLETION_MARKERS = [
    "vielen dank", "gutgeschrieben", "zurück zur website",
    "thank you", "survey complete", "umfrage beendet",
]
# Immer BOTH checken: URL title + page innerText
```

## 🔥 Survey Rating (+0.01€ Bonus)

```
Nach Survey-Completion:
1. "Diese Umfrage bewerten" erscheint INLINE auf Completion-Page
2. Klicken → navigiert zu offers.cpx-research.com/rating.php
3. Rating-Button klicken → +0.01€
4. "Zurück zur Website" → zurück zum Dashboard
```

## 🔥 CPX API Endpunkte

```python
# details_url Format (vom Dashboard JS-Context):
"https://live-api.cpx-research.com/api/get-survey-details.php"
"?output_method=jsscriptv1"
"&app_id=11644"
"&ext_user_id=2525530"
"&secure_hash=ae75b0feca27c0f8eb356d7117d978ec"
"&subid_1=&subid_2=website"
"&email=zukunftsorientierte.energie@gmail.com"
"&extra_info_1=offerwall"
"&secure_hash_offerwall=4513de32fa14dec8b40031d79c0149ff"
"&main_info=true"
"&extra_info_2=0.85224"
"&extra_info_3=EUR"
"&extra_info_4=nomobile"
"&m=adsplashxmas&m_1=...&m_2=...&m_3=&m_4="
# Zusätzlich: &survey_id=XXXXX

# Response:
{"status":"success","type":"okay","href":"https://click.cpx-research.com/?k=..."}
# type kann sein: "okay", "question" (pre-qualifier), "not_okay" (screen-out)
```

## 🔥 Chrome Profil-Management

```
/tmp/heypiggy-bot/  ← FESTES Profil (Cookies persistent)
  ├── Default/
  │   ├── Cookies        ← Login-Session
  │   ├── Login Data     ← Passwörter/Passkeys
  │   └── Local Storage  ← heypiggy UI-State
  └── ...
```

- **Nie Profil löschen** — Login-Cookies gehen verloren
- **Nie Profil timestampen** (`/tmp/heypiggy-bot-12345678`) — Daemon findet Profil nicht
- Bei "Chrome wird bereits verwendet"-Fehler: `rm /tmp/heypiggy-bot/SingletonLock`

## 🔥 FCTES Flow Engine (für spätere Tools)

```
Learning (unsicher) → 10× Success → COMPILE → FROZEN → 1-Call Dispatcher

NIE: Agent denkt selbst, kombiniert Tools frei
IMMER: Agent ruft EIN frozen Tool auf → Tool führt Flow aus
```

## 🔥 macOS Accessibility (ONE-TIME SETUP)

```bash
# Schritt 1: Permission reset
tccutil reset Accessibility com.google.Chrome

# Schritt 2: Chrome starten mit --force-renderer-accessibility
# → macOS zeigt Permission-Dialog

# Schritt 3: User klickt "Allow" in System Settings
# → Danach: cua-driver AX-Tree hat 600+ Elemente
# → PERMANENT (bis zum nächsten tccutil reset)
```

## 🔥 Error-Message Lexikon

| Fehler | Bedeutung | Fix |
|--------|-----------|-----|
| `Handshake status 403` | `--remote-allow-origins=*` fehlt | Chrome-Flag setzen |
| `AX-Tree 0 children` | `--force-renderer-accessibility` fehlt | Chrome-Flag + Accessibility-Permission |
| `Expecting value: line 1 column 1` | `json.loads()` auf Text-Output | Output-Typ prüfen (JSON vs TEXT) |
| `No such target id` | Tab wurde bereits geschlossen | `_close_tab` tolerant machen |
| `Survey tab not found` | CPX-Redirect screen-out | Survey als screen_out markieren |
| `Google Login-Symbol not found` | Dashboard ist Landing-Page (nicht logged in) | Login ausführen |
| `No surveys available` | Hardcoded `details_url` ohne Session-Params | Live-URL vom Dashboard holen |

## 🔥 Daemon Watch Loop Architektur

```
while running:
  1. Health Check → Chrome alive? Dashboard WS?
  2. Invariant Check → Login state? Accessibility?
  3. Auto-Login → google_login() if not authenticated
  4. Scan → extract_ids() → filter_surveys() via CPX API
  5. Run Loop → run_survey(id) → NEMO pipeline
  6. AutoDoc → log earnings, errors, decisions
  7. Backoff → exponential if errors, immediate if success
  8. Repeat
```

## 🔥 NEMO Loop (pro Survey-Seite)

```
Compact Snapshot (CDP Runtime.evaluate) → ~200 tokens
    ↓
NIM Decision (Nemotron 3 Omni / GPT-OSS-120B) → ~100 tokens
    ↓
Batch Execute (CDP Runtime.evaluate) → 1 WebSocket call
    ↓
Memory + Guardian (append-only JSONL)
```

## 🔥 Tab Lifecycle (CRITICAL für Multi-Survey)

```
1. CREATE: Target.createTarget(url) → tab_id
2. WAIT: 8s für CPX-Redirect (click.cpx → Qualtrics/PureSpectrum/etc)
3. DETECT: _find_survey_tab_ws(tab_id) → echte Survey-URL
4. HANDLE: PureSpectrum preflight ODER NEMO loop
5. CLOSE: Target.closeTarget(tab_id)
6. CLEAN: Alle Zombie-Tabs vor nächstem Survey schließen
```

## 🔥 Survey ID Extraction (vom Dashboard)

```python
# Dashboard speichert Survey-Liste in JS-Variable:
acctualSurveyList  # 73 Surveys! Nur 12 sichtbar im DOM

# Sichtbare IDs via onclick-Handler:
document.querySelectorAll('[onclick*=clickSurvey]')
# Format: clickSurvey('66846193');

# CPX API check:
details_url + '&survey_id=' + id
# Response: {"type":"okay","href":"..."} oder {"type":"question"}
```

## 🔥 Balance Reader — Regex Stolpersteine

```python
# Dashboard zeigt Balance als: "2.15\n€" (multiline!)
# ❌ Falsch: sucht "2.15€" → findet nichts
# ✅ Richtig: sucht "\d+[.,]\d+\s*\n?\s*€"
BALANCE_REGEX = r'(\d+[.,]\d+)\s*\n?\s*[€$]'

# ABER: Dashboard hat VIELE €-Beträge (Survey-Werte 0.06€, 0.38€...)
# Balance ist der GRÖSSTE Wert → max() filtern
```

## 🔥 WebSocket Connection Management

```python
# IMMER neuen WebSocket pro Operation (nicht wiederverwenden!)
ws = websocket.create_connection(ws_url, timeout=15)
ws.send(json.dumps({...}))
response = json.loads(ws.recv())
ws.close()  # SOFORT schließen!

# Grund: WebSocket-Timeout nach Inaktivität, State-Pollution
# JEDE Operation = neuer WebSocket
```

## 🔥 Timing/Delays — empirisch ermittelt

| Aktion | Delay | Grund |
|--------|-------|-------|
| Chrome Launch | 8s | Profil laden, erste Seite rendern |
| CPX Redirect | 8s | click.cpx → Qualtrics/PureSpectrum chain |
| Nach Button-Klick | 3-5s | Page-Transition, JS-Loading |
| OAuth Popup | 5s | Google Redirect, Passkey-Dialog |
| Captcha lösen | 5s | Page-Reload nach Submit |
| Drag Puzzle | 3s | DOM-Update nach dropListRef.drop() |
| Balance lesen | 2s | Dashboard-Cache-Refresh |

Keine dieser Delays darf unterboten werden — sonst: stale DOM, falsche WS, fehlende Elemente.

## 🔥 File-Saving Patterns (für ALLE Tools)

```python
# Konfiguration: JSON
json.dump(config, open("config.json", "w"), indent=2)

# Logs: JSONL (append-only, nie rewrite!)
with open("logs.jsonl", "a") as f:
    f.write(json.dumps(entry) + "\n")

# Sessions: Markdown (human-readable)
with open(f"sessions/{date}.md", "a") as f:
    f.write(f"## {timestamp}\n{details}\n")

# NIE: LLM schreibt Dokumentation (halluziniert)
# IMMER: Code schreibt strukturierte Logs
```

## 🔥 Tool-Building Checkliste (für jeden neuen Flow)

Bevor ein Flow zum Tool wird:
- [ ] Invariant-Guard (`_verify_invariants()`)
- [ ] cua-driver Output-Type-Check (JSON vs TEXT)
- [ ] Chrome-Flag-Check (Accessibility + CDP)
- [ ] Port-Hardcoding vermeiden (nutze 9999)
- [ ] Zombie-Cleanup vor Start
- [ ] Append-Only Logging
- [ ] Error-Message mit Kontext (Survey-ID, Provider, Iteration)
- [ ] Timing-Delays einhalten
- [ ] WebSocket pro Operation (nicht wiederverwenden)
- [ ] `learn.md` updaten nach Verifikation
- [ ] `commands/` .md Datei anlegen
- [ ] GitHub commit + push
