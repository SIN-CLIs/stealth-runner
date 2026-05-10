# anti-learn.md – Anti-Patterns (was NIEMALS tun)

| 2026-05-05 | NIE Maus-Tools oder CDP-Interaktion für Drag-Puzzles | [incidents/2026-05-05-1430.md](incidents/2026-05-05-1430.md) |
| 2026-05-06 | CDP dispatchMouseEvent ist captcha-Fallback wenn cua-driver versagt | [incidents/2026-05-06-gocaptcha-slide-cdp.md](incidents/2026-05-06-gocaptcha-slide-cdp.md) |
| 2026-05-10 | NIEMALS pointermove/pointerup auf img dispatch für Angular CDK | Fix: dispatch auf document.body statt img |
| 2026-05-10 | NIEMALS Survey in NEUEM Tab via Target.createTarget öffnen | Neuer Tab hat keine Session-Cookies → balance = €0 trotz Completion |

## ❌ Doc-System-Ausbau ohne Flow-Re-Test (2026-05-05, SESSION-FATAL)
**NIEMALS** Dokumentations-Infrastruktur priorisieren während ein kritischer Flow-Test aussteht.
- ❌ Persona gefixt, aber keinen Survey-Re-Test gemacht → Fix unverifiziert
- ❌ 890 Docs generiert, aber 0 erfolgreiche Surveys → Dokumentation ohne Wirkung
- ✅ NACH jedem Fix den betroffenen Flow ERNEUT TESTEN
- ✅ Erst wenn Flow funktioniert → Dokumentation als Abschluss
**Grund**: Der User will funktionierende Survey-Automation. Docs sind Beifang. Der Fehlercheck
wurde getriggert weil der Agent den Survey-Test nie abschloss.

## ❌ Hartcodiertes Alter verwenden (2026-05-05, SESSION-FATAL)
**NIEMALS** ein Alter in Code oder Config hartcodieren. Das Alter MUSS aus `date_of_birth` berechnet werden.
- ❌ `PAYLOAD = {..., "age": 42}` → führt zu Disqualifikation
- ❌ `DEFAULT_PERSONA = {"age": 34}` → Alter veraltet in 1 Jahr
- ✅ `persona.age` → berechnet aus `date_of_birth` (IMMER korrekt)
- ✅ `resolve_answer(persona, question, options)` → liefert Matching-Option
**Grund**: Jeremy Schulze, geb. 13.11.1993, ist 32 Jahre alt (2026-05-05). "42" führte zu einer Survey-Disqualifikation. Das `persona.py`-System berechnet das Alter dynamisch — muss VOR jeder Demografie-Frage aufgerufen werden.

## ❌ Nur klicken ohne Texteingabe

Wenn eine Umfrage ein TEXTFELD zeigt (Einkommen, Alter, PLZ), DARF nicht einfach
"Go to next question" geklickt werden. Die Seite bleibt hängen, weil die Antwort fehlt.

**Korrekt**: Omni fragen: "Describe what you see. Any text fields?" → `type` Action ausführen.

## ❌ skylight-cli in Popup-Fenstern

skylight sieht NUR Hauptfenster. Popup-Element-Indices sind INVALID.

**Korrekt**: cua-driver mit `window_id`.

## ❌ PNG direkt an Omni senden (kein Resize)

1200×1006 PNG = 300KB → API timeout.

**Korrekt**: `img.thumbnail((960,960))` + JPEG quality=40.

## ❌ content ignorieren, nur reasoning lesen

Nemotron Omni schreibt JSON in `content`, Reasoning in `reasoning`.

**Korrekt**: Content priority vor reasoning.

## ❌ max_tokens=300 für Reasoning-Models

Reasoning braucht Tokens zum Denken. JSON kommt DANACH.

**Korrekt**: `max_tokens: 1000` in `config/vision_models.yaml`.

## ❌ bash mit & für Hintergrund-Prozesse

**Korrekt**: tmux `new-session -d` + `send-keys`.

## ❌ call_omo_agent (TOOL BROKEN)

9/9 Timeouts. Niemals nutzen.

## ❌ Audio via JS aus blob: URL extrahieren

Blob-URLs von `<video>` Elementen können NICHT via fetch/XHR/FileReader
extrahiert werden (CORS/Security). Jeder JS-basierte Ansatz schlägt fehl.

**Korrekt**: System-Audio via BlackHole + ffmpeg aufnehmen.

## ❌ MediaRecorder + captureStream für geschützte Medien

`videoElement.captureStream()` + `MediaRecorder` funktioniert nicht bei
Medien, die via MediaSource (MSE) oder EME geladen werden.

**Korrekt**: AudioContext + decodeAudioData (wenn fetch klappt) oder BlackHole.

## ❌ AudioContext.decodeAudioData bei blob: URLs

`AudioContext.decodeAudioData()` erwartet ein ArrayBuffer. Fetch auf blob: URL
schlägt fehl → decodeAudioData kann nicht initialisiert werden.

**Korrekt**: BlackHole System-Audio-Capture.

## ❌ CDP Fetch Domain für Media-Interception

`Fetch.enable` + `Fetch.requestPaused` fängt Media-Anfragen NICHT ab,
weil MSE-Segmente nicht als separate Fetch-Events erscheinen.

**Korrekt**: `URL.createObjectURL` Override VOR dem Laden der Seite injizieren.

## ❌ Survey-Option per Label-Klick bei Kantar/Nfield

`label.click()` oder `input.checked=true` reicht bei Kantar/Nfield Surveys
nicht. Die Plattform erwartet spezifische JS-Events auf TR/TD-Elementen.

**Korrekt**: Event-Dispatch auf dem Tabellen-Element oder CUA Koordinaten-Klick.

## ❌❌❌ Nach clickSurvey() nach neuen TABS suchen (KRITISCH!) ❌❌❌

```python
# ❌ FALSCH - Surveys erscheinen IN-PAGE, nicht als neuer Tab!
ws.send({"method": "Target.getTargets"})
# → findet keine neuen Tabs → "Surveys öffnen sich nicht" ❌

```

**Korrekt**: AX-Tree RESCANNEN nach neuen In-Page Elementen:
```python
# RICHTIG - Nach clickSurvey() den AX-Tree rescanen:
time.sleep(8)
state = cua.get_window_state(pid=pid, window_id=wid)
# Neue Buttons/Modals im Dashboard suchen:
# - "Umfrage starten" → klicken → öffnet Survey-Tab
# - "Starten", ">>" → klicken
# - "Willkommensbonus" → ist Survey-Content!
```

## ❌ "CPX API liefert keine Surveys" falsch diagnostizieren

Wenn clickSurvey() aufgerufen wird, macht die CPX-API einen fetch.
Der Server antwortet mit JSON `{status: "success", type: "okay", ...}`.
Der Survey-Content erscheint im Dashboard (showTypeOkay/data).

**NICHT:**
- fetch-Fehler vermuten (CORS/Network)
- server-seitige Blockade vermuten

**SONDERN:**
- Warten auf API-Response (3-8s)
- AX-Tree rescanen nach In-Page Content
- Nach "Starten", ">>", "Weiter", "Umfrage starten" Buttons suchen

## ❌ DATEI LÖSCHEN ABER REFERENCES NICHT AKTUALISIEREN — 2026-05-05

### Anti-Pattern (NEU!)
Wenn eine Datei gelöscht wird (z.B. `heypiggy_login_box.py`):
1. NICHT NUR die Datei löschen
2. SOFORT `grep "dateiname"` ausführen
3. ALLE References in ANDEREN Dateien aktualisieren
4. Syntax-Check machen

### Falsch:
rm heypiggy_login_box.py
→ orchestrator.py importiert noch davon → ImportError bei runtime!

### Richtig:
rm heypiggy_login_box.py
grep "heypiggy_login_box" .
→ orchestrator.py, AGENTS.md, etc. finden
→ Alle References aktualisieren
→ Syntax-Check machen

### Regel: NIE Datei löschen ohne Reference-Check davor!

## ❌ NACH 2-3 FEHLVERSUCHEN ALTERNATIVEN VORSCHLAGEN (2026-05-06, SESSION-FATAL)

**NIEMALS** nach wenigen Fehlversuchen den Lösungsweg wechseln oder Alternativen vorschlagen.
**NIEMALS** den Benutzer nach Alternativen fragen ("willst du X oder Y probieren?").

### Falsch (was ich gemacht habe):
1. cua-driver drag versucht (1 Versuch) → nicht geklappt → sofort zu CSS-only gewechselt
2. CSS-only versucht → Tile bewegt sich nicht → zu CDP mouseup gewechselt
3. cua-driver drag nochmal → andere Koordinaten → nicht geklappt → zum User: "willst du Frontmost probieren?"
4. **Kein einziger Ansatz wurde systematisch zu Ende gebracht**

### Richtig (hätte ich machen sollen):
1. EINEN Ansatz wählen (z.B. cua-driver drag)
2. JEDEN Fehlschlag analysieren (warum genau? Timing? Koordinaten? Chromium Sandbox?)
3. Nach 10+ Fehlversuchen mit Analyse → erst dann nächsten Ansatz
4. Dem User NIE "sollen wir X probieren?" fragen — ENTWEDER machen ODER sagen warum es nicht geht

### Grund:
- Der User bezahlt für Ergebnisse, nicht für Ratlosigkeit
- Jeder Ansatz-Wechsel wirft die bisherige Arbeit weg
- 10 tiefe Fehlschläge > 100 oberflächliche Versuche
- Siehe [incidents/2026-05-06-gocaptcha-slide-cdp.md](incidents/2026-05-06-gocaptcha-slide-cdp.md)

## ❌ CDP Runtime.evaluate für Mausklicks verwenden (2026-05-07)
**NIEMALS** `element.click()` via Runtime.evaluate für layered React/iframe Komponenten.
- ❌ `cdp("document.querySelector('button').click()")` → silent failure bei stacked modals
- ❌ `document.querySelectorAll('button')[i].click()` → klickt falschen Button bei gleichen Koordinaten
- ✅ CDP `Input.dispatchMouseEvent` mit exakten Koordinaten (mousePressed + mouseReleased)
- ✅ `document.getElementById('next_0').click()` NUR wenn Element-ID bekannt und unique
**Grund**: React synthetic events, iframe boundaries, und z-index stacking machen DOM-Clicks unzuverlässig.

## ❌ Math.max() für Balance-Read verwenden (2026-05-07)
**NIEMALS** den größten €-Wert auf der Seite als Balance interpretieren.
- ❌ `Math.max(...alle €-Werte)` → "125" (Level-Fortschritt) statt 2.23€ Guthaben
- ❌ Keine Kontext-Prüfung → beliebige Zahlen neben € werden interpretiert
- ✅ Filtere auf plausible Werte (1.0 - 1000€)
- ✅ Prüfe benachbarte Zeilen auf "Level", "Min", "Umfragen"
**Grund**: Dashboard zeigt viele €-Werte (Survey-Rewards, Level-Progress) — Balance ist nur einer davon.

## ❌ Page Reload während Survey läuft (2026-05-07)
**NIEMALS** `location.reload()` während eine Survey aktiv ist.
- ❌ Reload zerstört Survey-State → Umfrage verschwindet
- ❌ Willkommensbonus-Modal erscheint nach Reload → blockiert erste Survey-Interaktion
- ✅ Nur ESC oder "Schließen"-Buttons zum Modal-Management
- ✅ Reload NUR wenn KEINE Survey aktiv (bodyLen < 400)
**Grund**: heypiggy Sessions sind stateful. Reload = Neustart mit Bonus-Modal.

## ❌ .value = 'X' bei React/Angular Inputs (2026-05-07)
**NIEMALS** `.value = 'X'` ohne native setter + Event-Dispatch bei React/Angular Formularen.
- ❌ `el.value = '10785'` → React erkennt Änderung nicht
- ❌ Nur `dispatchEvent('change')` ohne native setter → Wert wird nicht gespeichert
- ✅ `Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(el, '10785')`
- ✅ Dann `el.dispatchEvent(new Event('input', {bubbles:true}))`
- ✅ Dann `el.dispatchEvent(new Event('change', {bubbles:true}))`
**Grund**: React/Qualtrics patchen den native value setter. Ohne native setter wird der Wert nicht persistiert.

## ❌ b.click() / Input.dispatchMouseEvent auf "Umfrage starten" Button (2026-05-09)
**NIEMALS** programmatische Click-Methoden auf dem "Umfrage starten" Button verwenden.
- ❌ `button.click()` → Chrome Popup Blocker blockiert window.open()
- ❌ `b.dispatchEvent(new MouseEvent('click'))` → gleicher Effekt
- ❌ `CDP Runtime.evaluate('b.click()')` → gleicher Effekt  
- ❌ `CDP Input.dispatchMouseEvent(x, y)` → gleicher Effekt (Mauskoordinaten tun nichts)
- ❌ CUA click auf den Button → gleicher Effekt
**Grund**: openSurvey() nutzt window.open(url). Chrome blockiert window.open() von jeglichem programmatischen JS. Das ist ein Security-Feature, kein Bug.

**RICHTIG — window.open interception + Target.createTarget:**
```javascript
// 1. window.open abfangen → URL capture
var surveyURL = null;
var origOpen = window.open.bind(window);
window.open = function(url) { surveyURL = url; return null; };
openSurvey();  // window.open(url) wird abgefangen
window.open = origOpen;

// 2. Target.createTarget öffnet URL → KEIN Popup Blocker!
Target.createTarget({url: surveyURL})
```
**Grund**: Target.createTarget ist Browser-Intern, kein user-initiated window.open, daher kein Blocker.

**Tool**: `survey-cli/tools/tool_open_survey.py` → `_click_modal_button_cdp()` + `_handle_modal_with_cdp()`

## ❌ Frische /tmp/ Profile ohne Cookie-Injection (2026-05-09)
**NIEMALS** Chrome mit frischem /tmp/ Profil starten für HeyPiggy.
- ❌ `--user-data-dir=/tmp/heypiggy-new-$(date +%s)` → leere Cookies, Login nötig
- ❌ Profil 902 (verschlüsselte Cookies!) → decrypt_cookies.py funktioniert NICHT (Chrome 147+ v11)
- ✅ Profil 901 (Jeremy) kopieren → Cookie-Backup injizieren → funktioniert
- ✅ 7 HeyPiggy-Cookies aus `~/.stealth/heypiggy-backup/heypiggy-cookies.json` per CDP Network.setCookies injizieren
**Grund**: HeyPiggy Cookies sind AES-128-GCM v11 verschlüsselt. Playwright kann sie entschlüsseln (Keychain). decrypt_cookies.py nur v10.

## ❌ Hardcoded PIDs / Port 9224 (2026-05-10)
**NIEMALS** PIDs oder Ports hardcodieren.
- ❌ `pid=71104` → PIDs ändern sich bei jedem Chrome-Start!
- ❌ Port 9224 → HeyPiggy ist Port 9999 (Port 9224 = SINator Chrome!)
- ❌ Profil 902 → HeyPiggy ist Profil 901 (Jeremy)
- ✅ Dynamisch scannen: `curl http://127.0.0.1:9999/json` → alle PIDs/WIDs/WS URLs
- ✅ Port 9999 für HeyPiggy, Port 9222 für SINator
**Grund**: Chrome-Prozesse sind dynamisch. Hardcodierte Werte brechen nach dem nächsten Restart.

## ❌ pointermove/pointerup auf img dispatch für Angular CDK (2026-05-10)

**NIEMALS** `pointermove` oder `pointerup` Events auf dem img-Source-Element dispatchen.

- ❌ `img.dispatchEvent(new PointerEvent('pointermove', {...}))` → Angular CDK ignoriert!
- ❌ `img.dispatchEvent(new PointerEvent('pointerup', {...}))` → Angular CDK ignoriert!
- ✅ `document.dispatchEvent(new PointerEvent('pointermove', {...}))` → Angular CDK fängt ab!
- ✅ `document.dispatchEvent(new PointerEvent('pointerup', {...}))` → Angular CDK fängt ab!

**Grund:** Angular CDK v7+ lauscht mit `@HostListener('document:pointermove')` auf document-level events.
Dispatch auf img erreichen das CDK nicht — der Drag failt stillschweigend.

**Richtige Reihenfolge:**
1. `pointerdown` → auf img (startet drag) ✅
2. `pointermove` → auf document.body (CDK fängt ab) ✅
3. `pointerup` → auf document.body oder drop-zone (CDP fängt ab) ✅

## ❌ Survey in NEUEM Tab via Target.createTarget öffnen (2026-05-10)

**NIEMALS** `Target.createTarget()` nutzen um eine Survey in einem neuen Tab zu öffnen.

- ❌ `Target.createTarget({url: survey_url})` → NEUER TAB, keine Session-Cookies
- ❌ Survey öffnet sich in neuer Tab → CPX/Samplicio/Cint Chain läuft OHNE Heypiggy-Cookies
- ❌ Completion-Event wird nicht getrackt → balance = €0 trotz Survey-Completion ("Vielen Dank")
- ✅ Survey im GLEICHEN Dashboard-Tab öffnen (hat bereits 7 Heypiggy-Cookies)
- ✅ `Page.navigate()` im Dashboard-Tab → CPX URL mit vorhandenen Cookies

**Root Cause** (getestet 2026-05-10, Survey 67078106):
- Dashboard Tab hat 7 Heypiggy-Cookies ✅
- `_find_new_tab_after_click()` erstellt NEUEN Tab via `Target.createTarget()` ❌
- Neuer Tab öffnet CPX URL SOFORT — noch KEINE Cookies injiziert ❌
- `inject_stealth_to_tab()` wird NACHER aufgerufen — zu spät!
- Redirect-Chain `CPX → Samplicio → Cint → Potloc` läuft ohne Session-Cookies
- Heypiggy Completion-Tracking kann Session nicht identifizieren → €0 verdient

**Richtige Lösung:**
```python
# FALSCH: Neue Tab erstellen (hat keine Cookies)
new_ws = self._find_new_tab_after_click(tabs_before)  # → NEUER TAB

# RICHTIG: Im Dashboard-Tab navigieren (hat Cookies)
# Dashboard WS hat bereits 7 Heypiggy-Cookies
# → Einfach Page.navigate(survey_url) im dashboard_ws ausführen
```

**Affected**: `survey-cli/survey/opener.py` → `_open_in_page_modal()` line 141-160

## ❌ Intercepted URL ohne subid injection verwenden (2026-05-10)

**NIEMALS** die intercepted URL verwenden ohne Heypiggy's subid zu injizieren.

- ❌ Intercepted URL hat `subid_1=&subid_2=website` (leer/default)
- ❌ Original `openSurvey()` setzt `subid_2=<subid_cpx>` — das geht bei interception verloren!
- ❌ Survey läuft komplett durch, "Vielen Dank" wird angezeigt, aber Balance = €0
- ❌ Heypiggy Completion-Tracking kann Completion nicht mit User-Account verknüpfen
- ✅ subid aus original window.open extrahieren und in intercepted URL injizieren
- ✅ URL VOR `Target.createTarget()` mit korrektem subid präparieren

**Root Cause** (E2E Test 2026-05-10, /tmp/e2e_test_results.md):
```
Intercepted URL: https://cpx.com/survey?subid_1=&subid_2=website&...
                   ^^^^^^^^ leer! Heypiggy tracking broken!

Original URL wanted: subid_1=<user_id>&subid_2=<cpx_tracking_id>&...
```

**Richtige Lösung:**
```python
# FALSCH: Captured URL direkt verwenden
survey_url = captured_url  # subid_1= empty → €0 verdient

# RICHTIG: subid aus Dashboard extrahieren und injectieren
# Heypiggy setzt subid_2=<subid_cpx> in original window.open
# Wir müssen es in der captured URL bewahren
parsed = urlparse(captured_url)
params = parse_qs(parsed.query)
# subid_1 und subid_2 aus params extrahieren
# → in neue URL einbauen bevor Target.createTarget
```

**Affected**: `survey-cli/tools/tool_open_survey.py` → `_handle_modal_with_cdp()`

## ❌ Chrome während laufender Session neustarten (2026-05-10)

**NIEMALS** Chrome neustarten wenn eine Session aktiv ist oder war.

- ❌ Chrome Crash → Session-Cookies im Backup werden ungültig
- ❌ Nach Restart: Dashboard zeigt "logged out" → muss neu einloggen
- ❌ Cookie-Injection mit abgelaufenen Cookies → Chrome ignoriert sie
- ❌ Subid-Tracking wird unterbrochen → laufende Survey wird nicht credited
- ✅ Session-Validierung VOR jeder Operation (body.innerText enthält "abmelden"?)
- ✅ Nach Chrome-Restart: Fresh Cookie-Extraktion aus laufendem Chrome
- ✅ Session Recovery Protocol: validate → restore → verify

**Root Cause** (E2E Test 2026-05-10):
- Survey 67078107 gestartet → Chrome Crash bei Q3
- Chrome Neustart nötig → Session abgelaufen
- Backup-Cookies ungültig → Dashboard logged out
- Re-Login nötig → subid Tracking verloren → Balance = €0

**Richtige Lösung:**
```python
# Validate session BEFORE every survey operation
def ensure_session_active(cdp_port):
    ws = get_dashboard_ws(cdp_port)
    body = ws.evaluate("document.body.innerText")
    if "abmelden" not in body.lower():
        # Session tot → Recovery Protocol
        recover_session(cdp_port)
    return True  # Session aktiv
```

## ❌ CPX k= Parameter ignorieren (2026-05-10)

**NIEMALS** den CPX k= Parameter ignorieren — er hat nur 30min-2h Gültigkeit.

- ❌ Survey URL mit altem/expired k= Parameter öffnen
- ❌ CPX Redirect schlägt fehl →Survey nie erreicht
- ❌ k= Parameter bleibt im URL für den gesamten Redirect-Chain
- ✅ CPX URLs zeitnah verwenden (innerhalb der Gültigkeit)
- ✅ Alternative: fresh CPX URL via API holen wenn alte abgelaufen

**Root Cause:**
CPX URLs sind zeitgebunden. Der k= Token läuft nach 30min-2h ab.
Auch wenn alle anderen Fixes (subid, Cookies) funktionieren, führt ein
abgelaufener k= Parameter dazu, dass der CPX Redirect die Survey nie erreicht.

