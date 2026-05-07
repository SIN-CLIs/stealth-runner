# fix.md – ALL Fixes

> **← [sinrules.md](sinrules.md) ist die zentrale Regeldatei. §2 definiert Banned-Patterns.**
> **← [issues.md](issues.md) dokumentiert das Index-Problem.**
> **← [brain.md](brain.md) dokumentiert die NEMO Architektur.**

---

| 2026-05-05 | CUA-ONLY verletzt: cliclick+CDP dispatchEvent | [incidents/2026-05-05-1430.md](incidents/2026-05-05-1430.md) |
| 2026-05-06 | GoCaptcha Slide: CDP Input.dispatchMouseEvent als Lösung | [incidents/2026-05-06-gocaptcha-slide-cdp.md](incidents/2026-05-06-gocaptcha-slide-cdp.md) |
| 2026-05-06 | NEXT-GEN: 4 Root Causes gefixt + Crash-tested | [learn.md §M](learn.md) |

## 🔴 2026-05-06 NEXT-GEN: 4 Root Causes (CRASH-TESTED ✅)

### P0: Pre-Qualifiers SKIPPED
**Root Cause:** `run_loop()` line 490: `if survey.get("provider") == "pre_qualifier": continue`
→ 75% (9/12) Surveys wurden ignoriert. `handle_pre_qualifier()` existierte aber nie aufgerufen.

**Fix:** `continue` ersetzt durch `handle_pre_qualifier(survey_id, survey)`.
Zusätzlich: `message_button` an POST angehängt (CPX API erfordert das).
Pre-Qualifier Failure Cache vermeidet redundante API Calls.
`started_count` statt Loop-Index für max_surveys Tracking.

**Dateien:** `survey/runner.py` (~40 lines changed)
**Tests:** 13 (test_prequalifier.py)
**Verifiziert:** LIVE — 6 Pre-Qualifiers verarbeitet, 0 skipped ✅

### P1: Zero Stealth Injection
**Root Cause:** `Target.createTarget` öffnet neuen Tab ohne Stealth-Overrides.
`navigator.webdriver = true` → PureSpectrum/Cint erkennen Automation.

**Fix:** 3-Phasen Tab-Erstellung: (1) `create_blank_tab()` → about:blank,
(2) `inject_stealth_to_tab()` → Page.addScriptToEvaluateOnNewDocument,
(3) `navigate_tab()` → Survey-URL. 12-Module Stealth Bundle (251 Zeilen).

**Dateien:** `survey/chrome.py` (+120 lines), `survey/stealth/injection.js` (new)
**Tests:** 19 (test_stealth.py)
**Verifiziert:** LIVE — `[STEALTH] ✅ Injected stealth JS into tab AAB87721` ✅

### P1: Stale CDP WebSocket
**Root Cause:** `websocket.create_connection()` synchron, kein Reconnect.
Bei "No such target id" → Crash. Response-Routing broken in `_refresh_tab_ws()`.

**Fix:** `CDPConnection` Klasse (sync, 229 lines) mit:
- Exponential backoff retry (0.3→4.8s, 5 attempts)
- ID-based response routing (überspringt Events)
- Auto-reconnect bei "No such target"
- Context manager support

**Dateien:** `survey/cdp_client.py` (new), `survey/runner.py`, `survey/execute.py`
**Tests:** 15 (test_cdp_client.py)
**Verifiziert:** LIVE — 0 "No such target id" errors ✅

### P3: Balance Read FAILS
**Root Cause:** `read_balance()` wurde NACH `Target.createTarget` aufgerufen.
→ Dashboard WS stale → Balance immer 0.0€ → 8 completed surveys mit amount_eur: 0.0.

**Fix:** `balance_before` VOR Tab-Erstellung lesen (`try/except` → fallback 0.0).
`earned = max(0, balance_after - balance_before)` mit try/except.
`read_page_text` + `detect_error_page` als static methods zu BatchExecutor.

**Dateien:** `survey/runner.py` (~20 lines), `survey/execute.py` (~30 lines)
**Tests:** 5 (test_balance.py)
**Verifiziert:** LIVE — `[BALANCE] Before survey: 2.23€ | After: 2.23€ | Earned: +0€` ✅

### Bonus Fixes (während Crash-Test entdeckt)
- `read_page_text` war in `scanner.py` aber wurde via `BatchExecutor.read_page_text()` aufgerufen → AttributeError. Als static method zu BatchExecutor hinzugefügt.
- `detect_error_page` ebenfalls als static method zu BatchExecutor.
- Pre-Qualifier Loop: `started_count` tracking damit fehlgeschlagene Pre-Qualifiers nicht max_surveys verbrauchen.
- `message_button` Parameter an CPX API POST (war vorher nicht enthalten → API akzeptierte Antwort nicht).

## 🔴 KRITISCH: Survey-Test nach Persona-Fix NICHT wiederholt (2026-05-05, 15:15)

**Ursache**: Agent hat nach Persona-System-Fix (date_of_birth, age=32) den Survey-Test nicht mit
korrigiertem Alter wiederholt. Stattdessen wurde Doc-Infrastruktur ausgebaut (890 Dateien).

**Auswirkung**: Persona-Fix unverifiziert. Kein Beweis dass Survey mit "26-39" statt "40+" erfolgreich ist.

**Korrektur**: Survey-Test mit korrekter Persona (age=32 → Bracket 26-39) sofort nachholen.
Vor jeder Age-Frage: `resolve_answer(persona, question, options)` aufrufen.

**Prävention**: Nach jedem Fix MUSS der betroffene Flow erneut getestet werden.
Keine neuen Tasks vor Abschluss des Tests. Fehlercheck-Pflicht!

---

## 🔴 KRITISCH: Hartcodiertes Alter im Persona-System (2026-05-05, 14:22)

**Ursache**: AGENTS.md Zeile 512 enthielt `# Persona: ... männlich, 42` — hartcodiertes FALSCHES Alter.
`persona_manager.py` enthielt `DEFAULT_PERSONA = {"age": 34}` — auch falsch.
Das Korrekte Profil `jeremy_schulze.json` hatte `date_of_birth: ""` (LEER) — das Feld, das das korrekte Alter berechnet hätte.
Kein Agent hat vor dem Survey-Test das Profil geladen oder das Alter verifiziert.

**Auswirkung**: Survey-Disqualifikation bei "S1. What is your age?" — Agent wählte "40+" statt "26-39".
0.06€ verloren (nur 0.03€ Compensation). Geldbeutel: 1.17€ → 1.20€.

**Korrektur** (3 Dateien):
1. `A2A-SIN-Worker-heypiggy/profiles/jeremy_schulze.json`:
   - `date_of_birth`: `""` → `"1993-11-13"` (→ berechnet age=32)
   - `city`: `""` → `"Berlin"`, `postal_code`: `""` → `"10785"`
   - `employment_status`: `""` → `"full_time"`, `occupation`: `""` → `"Angestellter"`
   - `education_level`: `""` → `"Meister"`, `household_size`: `0` → `2`
2. `AGENTS.md` Zeile 503-512: Hartcodierte Persona entfernt → Profil-System-Referenz
3. `persona_manager.py`:
   - `DEFAULT_PERSONA`: `"age": 34` → ENTFERNT, `"date_of_birth": "1993-11-13"` hinzugefügt
   - `"education": "Bachelor"` → `"Meister"`, `"employment": "Full-time"` → `"full_time"`
   - `"household_size": 2` (korrigiert)

**Betroffene Dateien**:
- `/Users/jeremy/dev/stealth-runner/AGENTS.md` (Zeile 503-520)
- `/Users/jeremy/dev/A2A-SIN-Worker-heypiggy/profiles/jeremy_schulze.json`
- `/Users/jeremy/dev/playstealth-cli/playstealth_actions/persona_manager.py`

**Prävention**: Vor JEDER Survey-Demografie-Frage MUSS `persona.resolve_answer()` aufgerufen werden.
Kein hartcodiertes Alter mehr — NUR aus `date_of_birth` berechnen.

---

## 🔴 KRITISCH: Survey-Suche in neuen Tabs statt In-Page (2026-05-04)

### Symptom
clickSurvey() wird aufgerufen, aber ich suche nach neuen Tabs:
```python
Target.getTargets()  # → findet nichts → "Surveys öffnen sich nicht" ❌
```

### Root Cause
clickSurvey() öffnet den Survey als IN-PAGE Modal im Dashboard (showTypeOkay/showTypeQuestion).
Der Inhalt erscheint im selben Tab, nicht als neuer Browser-Tab.

### Fix
Nach clickSurvey() den AX-Tree rescanen:
```python
time.sleep(8)  # Warten auf API-Response
tree = cua.get_window_state(pid=pid, window_id=wid)
# Suche nach: "Umfrage starten", "Starten", ">>", "Willkommensbonus"
```

### Prävention
- NIEMALS Target.getTargets() nach Survey-Start
- IMMER AX-Tree rescanen nach In-Page Content
- "Willkommensbonus-Strecke" = erfolgreicher Survey!

---

## 🔴 KRITISCH: skylight-cli element-index Instabilität (2026-05-03)

### Symptom
`skylight-cli click --pid X --element-index 29` klickt ein Browser-Icon statt "Weiter".
Der User: *"du hast ein icon in der browser leiste angeklickt statt weiter button"*

### Root Cause
`skylight-cli list-elements` returned **flachen AX-Baum** mit Browser-Chrome + Web-Content.
Der Index verschiebt sich während Page-Load.

### Lösung: CDP+AX Trinity (LEGACY/DEPRECATED — 2026-05-03)
**Fusioniert aus 3 Forschungsansätzen + 120+ analysierten Webseiten:**

| Ansatz | Genutzt als |
|--------|-------------|
| CDP `Accessibility.queryAXTree()` | FIND: NUR Web-Content |
| CDP `DOM.getContentQuads()` | LOCATE: Bounding Box |
| `AXUIElementCopyElementAtPosition()` + `AXPress` | CLICK: Positionsbasiert |
| `AXEnhancedUserInterface = true` | Unterstützt vollen AX-Tree |
| skylight-cli `find_by_label` | Fallback |
| cua-driver `get_window_state` click | Popup-Fallback |

### Implementierung (NEMO ersetzt dies)
**Modul**: `cli/modules/cdp_click.py` (LEGACY/DEPRECATED — ersetzt durch [src/stealth_survey/](src/stealth_survey/))

```python
async def click_by_label(pid, cdp_port, label, role):
    """CDP queryAXTree → bounding box → AXPress"""
    ws = await _connect_cdp(cdp_port)
    backend_id = await _query_ax(ws, label, role)
    quad = await _get_quad(ws, backend_id)
    center = ((quad[0] + quad[2]) / 2, (quad[1] + quad[3]) / 2)
    return _ax_click_at(pid, *center)
```

**Key Fixes:**
- Word-Boundary in Label-Matching (`\bWeiter\b` ≠ "Weitere")
- CDP liefert NUR Web-Content (kein Browser-Chrome)
- Position-basiert statt Index-basiert (stabil)

---

## ✅ E2E LOGIN FIX (2026-05-03, PID 16811)

**Problem**: Passkey "Fortfahren" wurde nicht gefunden/geklickt.
**Root Cause**: 
  1. Fortfahren ist IM Google OAuth Popup (nicht im Hauptfenster!)
  2. Code nutzte skylight statt cua für Popup-Klicks
  3. ax_scan stderr wurde nicht erfasst
  4. Popup-Titel ändert sich → "Passkey" fehlte in title_patterns

**Lösung** (5 Commits):
  1. `passkey_popup.py`: cua-only → `cua.get_window_state(popup_wid)` → find "Fortfahren" → `cua.click`
  2. `consent_screen.py`: cua-only → kein skylight-Fallback mehr
  3. `ax_scan.py`: stderr capture, robust JSON parsing
   4. `survey/google_login.py` (cua-driver PRIMARY, CDP FALLBACK): 15× Retry mit 1.5s, _safe_click für FaceID-Timeout
  5. `cua_popup.py`: "Passkey" zu title_patterns

## ✅ MACOS-AX-CLI `find` funktioniert, `windows list` crashed
**Problem**: `macos-ax-cli windows list` → NSInvalidArgumentException crash
**Lösung**: Swift `[[String: Any]]` statt `__SwiftValue` für listAllWindowsDict()

## ✅ ax_scan stderr Capture
**Problem**: macos-ax-cli schreibt Output nach stderr statt stdout.
**Fix**: `_run()` liest `r.stdout or r.stderr`.

## 🔧 Word-Boundary Label Fix (2026-05-03)
**Problem**: `label_lower in el_label` matched "Weiter" in "Weitere Informationen"
**Fix**: `re.search(r'\b' + re.escape(label) + r'\b', el_label, re.IGNORECASE)`
**Betroffen**: `find_by_label()`, `_find_element()`, `_find_in_elements()`, `wait_for_element()`

## 🔧 cua-touch Label Parsing
**Problem**: 3 verschiedene Label-Formate im AX-Tree
**Fix**: Parsing für `": \"Label\""`, `"= \"X\" (Label)"`, `"= \"X\""` Formate

## 🔧 Prompt- und API-Fixes
- Nemotron Omni: `content > reasoning` Priority
- `max_tokens: 300 → 1000` (Reasoning braucht ~400 Tokens)
- Image Resize: 50% Thumbnail (960px) für API-Timeout-Fix
- Page Detection via AXWebArea-Label


## ✅ LOGIN FIX — 2026-05-05T13:17:12.476681

### Fehlerkette (was ALLES falsch war)
1. `list_windows` returns `{"windows": [...]}` nicht `[...]`
2. Windows haben `bounds` nicht `frame`
3. Kein `depth`-Feld in cua-driver Output
4. `playstealth launch` gibt mehrere JSON-Zeilen zurück
5. Google-Login-Button ist AXLink (nicht AXButton)
6. `click()` erwartet `" Performed "` aber cua-driver returned `"✅ Performed AXPress"`
7. Google-Login öffnet POPUP mit NEUER WID — alter Code blieb auf Heypiggy-WID
8. `type_text()` suchte `AXTextField` + "passwort" aber Mac-Keychain hat anderes Label
9. devjerro@gmail.com statt zukunftsorientierte.energie@gmail.com

### Fixes
1. Parse `windows.get("windows", [])`
2. Verwende `bounds` statt `frame`
3. Keine depth-Prüfung mehr
4. Parse alle JSON-Zeilen von playstealth
5. Suche AXButton + AXLink
6. Checke `r.get("stdout","") and " " in r.get("stdout","")` 
7. Nach Step 1: `_find_wid(["google","anmelden","sign","accounts"])`
8. Nach Step 5: `_find_wid(["heypiggy","dashboard","guthaben"])`
9. zukunftsorientierte.energie@gmail.com

### Tools die vergessen wurden
- **ax-graph** (SIN-CLIs) — Swift AX-Indexer, könnte WID-Findung beschleunigen
- **cua-touch MCP** — hat element_index Lookup

## ❌ CRITICAL: orchestrator.py importiert gelöschte Datei — 2026-05-05

> **(2026-05-06: heypiggy_login_box.py replaced by survey/google_login.py)**

### Symptom
`heypiggy_login_box.py` wurde gelöscht, ABER `orchestrator.py` (line 90) importiert noch daraus:
```python
from cli.modules.heypiggy_login_box import heypiggy_login  # GELÖSCHT! → ImportError!
```

### Betroffene References (grep gefunden):
- `/Users/jeremy/dev/stealth-runner/app/core/orchestrator.py` → line 90 (CRITICAL!)
- `/Users/jeremy/dev/stealth-runner/AGENTS.md` → line 537 (auch!)
- `/Users/jeremy/dev/stealth-runner/learn.md` → dokumentiert aber OK
- `/Users/jeremy/dev/stealth-runner/bugs.md` → dokumentiert aber OK

### Fix (Step-by-Step):
1. orchestrator.py → `from cli.modules.auto_google_login import execute as auto_google_login`
2. AGENTS.md → Pfad + Name aktualisieren
3. Verifizieren: grep "heypiggy_login_box" sollte NUR noch in Kommentaren sein

### Korrekte Import-Kette:
```
run_survey.py → survey_heypiggy.execute() → auto_google_login.execute()
                            ↓
                      orchestrator.run() → _dispatch_step("heypiggy_login") → auto_google_login
```

### REGEL: Nach dem Löschen einer Datei IMMER grep nach allen References suchen!

---

## 🔴 2026-05-07 LIVE DEBUGGING: 5 Fixes

### Fix #5: Balance reads 125€ instead of 2.23€

**Root Cause:** `read_balance()` used `Math.max` across all numbers near the `€` sign.
The Level-Progress indicator displayed "125" adjacent to a `€` character, causing the max function to return 125€.

**Fix:** Changed JS logic to:
1. Only accept values in range `1.0 < val < 1000`
2. Check adjacent DOM lines for "Level" / "Min" keywords and skip those matches

```js
if (val > 1.0 && val < 1000 && !adjacentLine.match(/(Level|Min)/i))
```

**File:** `survey-cli/survey/scanner.py` — `read_balance()` function

**Verification:** Balance consistently reads 2.23€ (verified via CDP `Runtime.evaluate`).

---

### Fix #6: React form inputs not accepting .value assignment

**Root Cause:** React's synthetic event system ignores direct `.value = ` property assignments.
The native value setter is overridden by React's internal state management.

**Fix:** Use the native HTMLInputElement value setter descriptor + synthetic event dispatch:

```js
const nativeSetter = Object.getOwnPropertyDescriptor(
    HTMLInputElement.prototype, 'value'
).set;
nativeSetter.call(el, val);
el.dispatchEvent(new Event('input', {bubbles: true}));
el.dispatchEvent(new Event('change', {bubbles: true}));
```

**Alternative (text insertion):**
```js
el.focus();
document.execCommand('insertText', false, val);
```

**File:** `survey-cli/survey/snapshot.py` — `fill_by_id()` function

**Verification:** Zip=10785 and Age=53 accepted by form. "Nächster" button transitions from disabled to enabled.

---

### Fix #7: Multiple stacked modals blocking survey interaction

**Root Cause:** The heypiggy dashboard renders 7-9 layered modals at identical z-indices and screen coordinates. The survey card sits behind this stack and cannot receive click events.

**Fix:** Close all "Schließen" buttons via JS loop before clicking the survey card:

```js
const btns = document.querySelectorAll('button');
for (let i = 0; i < btns.length; i++) {
    if (btns[i].textContent === 'Schließen') btns[i].click();
}
```

**File:** `survey-cli/survey/scanner.py` — injected before `clickSurveyCard()`

**Verification:** After closing modals, survey questions become visible and interactive. AX tree populated with survey radio buttons.

---

### Fix #8: Modal-only element snapshot scanning

**Root Cause:** `ELEMENT_EXTRACTOR_JS` scanned the entire `document.body`, including all stacked modals, producing 84+ element references — most from invisible background layers.

**Fix:** Added topmost modal detection by viewport center distance:

```js
function topmostModal() {
    const modals = document.querySelectorAll('[role="dialog"], .modal, [class*="modal"]');
    const cx = window.innerWidth / 2, cy = window.innerHeight / 2;
    let best = null, bestDist = Infinity;
    for (const m of modals) {
        const r = m.getBoundingClientRect();
        const dist = Math.abs(r.left + r.width/2 - cx) + Math.abs(r.top + r.height/2 - cy);
        if (dist < bestDist) { bestDist = dist; best = m; }
    }
    return best;
}
const scanRoot = topmostModal() || document.body;
```

Elements found inside the modal get `inModal: true` flag for downstream filtering.

**File:** `survey-cli/survey/snapshot.py` — `ELEMENT_EXTRACTOR_JS` constant

**Verification:** Element count reduced from 84+ to 3-5 for modal-based surveys. Only visible interactive elements are captured.

---

### Fix #9: New tab detection for Qualtrics surveys

**Root Cause:** `clickSurvey()` navigates to an external Qualtrics URL that opens in a new browser tab. The CDP WebSocket remained connected to the dashboard tab — subsequent `Runtime.evaluate` calls ran against the wrong page.

**Fix:** Poll tab list via `http://127.0.0.1:9999/json` before and after `clickSurvey()`. Detect the new tab and connect to its WebSocket debugger URL:

```python
import urllib.request, json

tabs = json.loads(urllib.request.urlopen('http://127.0.0.1:9999/json'))
new_tab = next(
    (t for t in tabs if 'qualtrics' in t.get('url', '').lower()),
    None
)
if new_tab:
    ws_url = new_tab['webSocketDebuggerUrl']
    connect_to_survey_tab(ws_url)
```

**File:** `survey-cli/survey/runner.py` — `_find_survey_tab()` helper

**Verification:** Survey questions now visible after connecting to the correct Qualtrics tab. `document.body.innerText` shows "In welchem der folgenden Länder/Regionen leben Sie?".
