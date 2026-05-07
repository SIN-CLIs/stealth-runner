# anti-learn.md – Anti-Patterns (was NIEMALS tun)

| 2026-05-05 | NIE Maus-Tools oder CDP-Interaktion für Drag-Puzzles | [incidents/2026-05-05-1430.md](incidents/2026-05-05-1430.md) |
| 2026-05-06 | CDP dispatchMouseEvent ist captcha-Fallback wenn cua-driver versagt | [incidents/2026-05-06-gocaptcha-slide-cdp.md](incidents/2026-05-06-gocaptcha-slide-cdp.md) |

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
