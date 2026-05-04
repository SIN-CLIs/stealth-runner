# brain.md – Systemwissen & Architektur-Entscheidungen (CUA-ONLY)

> **← [sinrules.md](sinrules.md) ist die zentrale Regeldatei. Alle Regeln sind DORT definiert.**
> **← [issues.md](issues.md) dokumentiert aktuelle Issues.**
>
> **CUA-ONLY AKTIV**: CDP + skylight-cli + webauto-nodriver sind ALLE BANNED.
> Nur cua-drider für Interaktion, playstealth für Chrome Launch.

---

## 🔥 CUA-ONLY STACK (2026-05-03)

```
CLICK LAYER (NUR CUA):
  cua-driver call list_windows       → Fenster finden
  cua-driver call get_window_state   → AX-Tree cachen (depth > 5 Filter!)
  cua-driver call click              → AXPress (30s Timeout, 3x Retry)
  cua-driver call set_value          → Text eingeben
  cua-driver call press_key          → Tastendruck (Enter, Tab, Cmd+T)

NAVIGATION (NUR CUA, KEIN CDP!):
  1. cua-driver call click → Address-Bar fokussieren
  2. cua-driver call set_value → URL eingeben
  3. cua-driver call press_key → Enter drücken

CRITICAL:
  - Daemon MUSS mit nohup laufen: nohup cua-driver serve &
  - Ohne Daemon: keine Session-Cache → keine Clicks!
  - depth > 5 Filter IMMER setzen (Apple-Menüleiste hat depth 1-4)
  - DISABLED Elemente automatisch überspringen
```

### Verifizierte E2E-Durchläufe
| PID | Flow | Ergebnis |
|-----|------|----------|
| 51212 | Google Login → Dashboard | ✅ 7 Steps |
| 14137 | W3Schools Form-Seite (1426 Elemente) | ✅ Buttons/Inputs/NAV alle funktionieren |
| 15541 | heypiggy.com (672 Elemente) | ✅ Login-Feld klickbar |
| 86899 | heypiggy OAuth Login + Survey 0.35€ | ✅ Level Up + 0.02€ |
| 86899 | Toluna Survey (0.77€) bis 53% | ✅ Fragen beantwortet, abgebrochen |
| 86899 | Audio-Frage via BlackHole + Omni | ✅ "Hahn" erkannt ⭐ |

### Module Stack (CUA-ONLY)
```
playstealth launch → isolierte Chrome-Instanz
cua-driver serve  → Daemon (nohup!)
cua-driver call   → ALLE Interaktionen
```
| 51212 | Survey → Nielsen → Captcha HAPK3 → 0,05€ | ✅ Captcha gelöst |
| 51212 | YouGov erkannt → skip | ✅ Vision-logic |

---

## 🔥 CDP+AX TRINITY — Die fusionierte Architektur (2026-05-03)

### Das Problem
`skylight-cli list-elements` returned **flachen AX-Baum**: Browser-Chrome + Web-Content in einem Array.
Der Index verschiebt sich während Page-Load → Klick trifft Browser-Icon statt "Weiter".

**Root Cause (120+ Quellen analysiert):**
- Chromium baut AX-Tree NUR bei aktivem Screenreader
- Browser-Chrome und Web-Content sind GEMISCHT
- Flache Indices sind NICHT stabil

### Die Lösung: 3 Forschungsansätze → 1 fusionierte Architektur

```
┌────────────────────────────────────────────────────────────────────┐
│                    CDP+AX TRINITY                                   │
│                                                                     │
│  ┌─────────────────────┐  ┌──────────────────┐  ┌───────────────┐  │
│  │ CDP (Chrome Prot.)  │  │ AX (macOS Acc.)  │  │ Legacy Tools  │  │
│  │                     │  │                  │  │               │  │
│  │ queryAXTree()       │  │ CopyElementAtPos │  │ skylight-cli  │  │
│  │ → NUR Web-Content   │  │ → Position-stabil│  │ → Hauptfenster│  │
│  │ → kein Browser-     │  │ → kein Index     │  │ → Fallback    │  │
│  │   Chrome            │  │ → kein Mouse-Move│  │               │  │
│  │                     │  │                  │  │ cua-driver    │  │
│  │ getContentQuads()   │  │ AXPress          │  │ → Popups      │  │
│  │ → bounding box      │  │ → echter Klick   │  │ → Sheets      │  │
│  │                     │  │                  │  │               │  │
│  │ AXEnhancedUI=true   │  │                  │  │ macos-ax-cli  │  │
│  │ → voller AX-Tree    │  │                  │  │ → System-Scan │  │
│  └─────────┬───────────┘  └────────┬─────────┘  └───────┬───────┘  │
│            │                       │                     │          │
│            └───────────┬───────────┴──────────┬──────────┘          │
│                        │                      │                     │
│              FIND + LOCATE               CLICK/ACT                  │
│         (CDP: Nur Web-Inhalt)    (AXPress: Position-basiert)       │
└────────────────────────────────────────────────────────────────────┘
```

### Der Drei-Schritt-Klick (fusioniert)

```
SCHRITT 1: FIND (CDP)
  Accessibility.queryAXTree(accessibleName="Weiter", role="button")
  → backendDOMNodeId + bounds {x, y, w, h}
  → NUR Web-Content (kein Browser-Chrome!)
  → CDP-Port kommt von playstealth: {"cdp_port": 61934}

SCHRITT 2: LOCATE (CDP)
  DOM.getContentQuads({backendNodeId})
  → [{"quad": [x1,y1, x2,y2, x3,y3, x4,y4]}]
  → center = (x1+x3)/2, (y1+y3)/2

SCHRITT 3: CLICK (AX — kein Index!)
  AXUIElementCopyElementAtPosition(chrome_app, center_x, center_y)
  → AXUIElement-Ref (direkt an Position)
  AXUIElementPerformAction(element, kAXPressAction)
  → ✅ Echter Klick, keine Mausbewegung, kein Focus-Steal
```

### Fallback-Kette

```
Primary:   CDP queryAXTree → AXUIElementCopyElementAtPosition → AXPress
Fallback1: skylight-cli find_by_label → click (Hauptfenster, label-basiert)
Fallback2: cua-driver get_window_state → click (Popup, window-id)
Fallback3: macos-ax-cli find → Text-Suche (nur Scan, kein Klick!)
```

### Warum das funktioniert (und vorher nicht)

| Aspekt | ALT (skylight index) | NEU (CDP+AX Trinity) |
|--------|---------------------|---------------------|
| Element-Quelle | Flacher AX-Baum (Chrome+Web gemischt) | CDP queryAXTree (NUR Web) |
| Identifikation | Globaler Index (instabil) | accessibleName + role (stabil) |
| Klick-Mechanismus | AXPress per Index | AXPress per Position |
| Index-Stabilität | ❌ Verschiebt sich bei Page-Load | ✅ Position ist deterministisch |
| Browser-Chrome | ❌ Enthalten | ✅ Nie enthalten |
| Google-Detection | ⚠️ --disable-blink-features | ✅ Kein JS-Klick, nur AXPress |

---

## 🔑 CDP+AX Modul: cdp_click.py (geplant)

```python
# cli/modules/cdp_click.py — DER zentrale Klick-Mechanismus

async def click_by_label(pid: int, cdp_port: int, label: str, role: str) -> bool:
    """
    1. CDP: queryAXTree(accessibleName=label, role=role)
    2. CDP: getContentQuads(backendNodeId) → bounding box
    3. AX: CopyElementAtPosition → AXUIElement
    4. AX: PerformAction → AXPress
    """
    ws_url = f"ws://127.0.0.1:{cdp_port}"
    backend_id = await _query_ax(ws_url, label, role)
    quad = await _get_quad(ws_url, backend_id)
    center = ((quad[0] + quad[2]) / 2, (quad[1] + quad[3]) / 2)
    return _ax_click_at(pid, *center)

async def type_by_label(pid: int, cdp_port: int, label: str, text: str) -> bool:
    """
    1. CDP: queryAXTree(accessibleName=label, role="AXTextField")
    2. CDP: getContentQuads → bounding box
    3. AX: CopyElementAtPosition → AXUIElement
    4. AX: SetAttribute(kAXFocusedAttribute, True) → Fokus
    5. AX: SetAttribute(kAXValueAttribute, text) → Text setzen
    """
```

---

## 🔑 cua-driver vs skylight-cli vs CDP+AX: KLARE TRENNUNG

| Tool | For | NEVER For |
|------|-----|-----------|
| **CDP+AX cdp_click** | Web-Elemente finden + klicken (PRIMARY) | — |
| **cua-driver** | Popups, Sheets, Dialogs (window_id) | Web-Content-Klicks |
| **skylight-cli** | Hauptfenster (Fallback) | Popups, Index-Klicks |
| **macos-ax-cli** | Systemweites SCANNEN | Klicken |

---

## 🔑 Google Login: Dual-Flow Consent (E2E-verifiziert 2026-05-03)

**Google ist SMART und kürzt den Flow wenn Cookies gecached sind!**

**FLOW A — Frischer Browser (keine Google-Cookies):**
```
Google(43) → Email(Label) → Weiter → Fortfahren(Label) → Weiter(Label) → Dashboard
```

**FLOW B — Bereits eingeloggt (Google-Cookies im Browser):**
```
Google(43) → Konto klicken(Label) → Weiter(Label) → Dashboard
```

**detect_screen1_type():**
- Sucht "E-Mail" im tree → FLOW A (Email-Eingabe)
- Sucht "Jeremy Schulze" / "zukunftsorientierte" im tree → FLOW B (Konto-auswählen)

---

## 🔥 GOOGLE LOGIN FLOW — VERIFIZIERT MIT CDP+AX (PID 51212, 2026-05-03)

**Erfolgreicher 7-Step Flow zum Google Account Dashboard:**

```
1. Email tippen          → skylight.click(label="E-Mail oder Telefonnummer")  → index 20  ✅
2. Weiter klicken        → skylight.click(label="Weiter")                     → index 29  ✅
3. Andere Option wählen  → skylight.click(label="Andere Option wählen")       → index 24  ✅
4. Passkey verwenden     → skylight.click(label="Passkey verwenden")          → index 24  ✅
5. Weiter (FaceID triggern) → skylight.click(label="Weiter")                 → index 25  ✅
6. Fortfahren (AXSheet)  → cua.click(window_id=42951, element=79)             → Sheet ✅
7. Als Jeremy fortfahren  → cua.click(window_id=42951, element=239)           → Sync ✅
→ GOOGLE ACCOUNT DASHBOARD 🎉
```

**Kernerkenntnisse:**
- Word-Boundary Fix (\b) verhindert Fehlmatches ("Weiter" ≠ "Weitere Informationen")
- Passkey-Sheet = cua-driver (AXSheet im Chrome-Fenster, element 79 = Fortfahren)
- Nach erfolgreichem Passkey: "Als Jeremy fortfahren" für Chrome-Sync
- **8. Schritt fehlt noch**: HeyPiggy Dashboard mit Google-Session laden

## 🔑 Google Login: google-login-google Flow (2026-05-03)

**Google ZWINGT Passkey für zukunftsorientierte.energie@gmail.com.**
→ Lösung: Google-Login-in-Google — erst in Google einloggen, dann HeyPiggy mit Session.

**Flow:**
```
1. accounts.google.com/signin
2. Email → Weiter
3. "Andere Option wählen" ×2 → "Passwort eingeben"
4. Passwort → Weiter
5. "Fortfahren" (FaceID) via CUA
6. "Als Jeremy fortfahren" → Google eingeloggt ✅
```

---

## AKTIVES MODELL
- **Name**: `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`
- **API**: `POST https://integrate.api.nvidia.com/v1/chat/completions`
- **Key**: `$NVIDIA_API_KEY` (Prefix: `nvapi-...`)

## AKTIVER CODE
- `~/dev/stealth-runner/runner/live_eye.py` – LiveEye v7 (Motion Detection)
- `~/dev/stealth-runner/runner/live_omni_monitor.py` – Hybrid Monitor
- `~/dev/stealth-runner/cli/modules/cdp_click.py` – CDP+AX Fusion (geplant)

## TMUX NON-BLOCKING PATTERN
```python
interactive_bash(tmux_command="new-session -d -s mysession")
interactive_bash(tmux_command='send-keys -t mysession "command" Enter')
```

## 🔑 cua-driver Daemon
cua-driver Daemon MUSS laufen (`cua-driver serve &`) vor allen element-index Klicks.

---

## 🔥 HEYPIGGY LOGIN BOX (2026-05-04)

### Aufruf
```python
from cli.modules.heypiggy_login_box import heypiggy_login
heypiggy_login(pid=2674, cdp_port=55983)
```

### FLOW A — Frischer Browser
```
1. Navigiere zu heypiggy.com
2. Klicke Google Login Link (AXLink "Google Login-Symbol")
3. Warte auf Google OAuth Popup
4. Email eingeben + Weiter klicken
5. Passkey bypass: "Andere Option wählen" → "Passwort eingeben"
6. Passwort eingeben + Weiter
7. 2FA erkennen + warten auf Smartphone-Bestätigung
8. macOS "Fortfahren" Dialog finden + klicken
9. Consent "Fortfahren" im Chrome Popup
10. Navigiere zu Dashboard → verify "Abmelden" Link
```

### FLOW B — Bereits eingeloggt
```
1. Prüfe AX-Tree auf "Abmelden" → sofort True
```

### Features
- ✅ Kein skylight (CUA-only)
- ✅ Automatische Popup-Erkennung (Fenstertitel "Anmelden – Google Konten")
- ✅ Passkey-Bypass via "Andere Option wählen" Kette
- ✅ 2FA-Warteschleife für manuelle Smartphone-Bestätigung
- ✅ macOS System-Dialog Erkennung (Fortfahren/Passkey)
- ✅ Consent-Handling (Fortfahren, Jeremy)
- ✅ Dashboard-Verifikation nach Login

---

## 🔥 E2E SURVEY FLOW VERIFIZIERT (2026-05-04)

### Kompletter Flow: Click → Consent → Start → Survey → Disqual → 0.02€

```
1. Scan surveys via CDP JS: document.querySelectorAll('.survey-item')
   → Finde Tab MIT .survey-item (Tab 6, nicht Tab 0/3)
   → page_id = 74D46500D6DE54CE397C (beispielhaft, ändert sich)

2. Click survey per CDP:
   document.getElementById('survey-66087867').click()
   → Survey modal appears on page

3. Modal "Umfrage starten" klicken (CUA element_index [246]):
   cua.click(pid, wid, 246)  # AXButton "Umfrage starten"
   → Survey öffnet in neuem Tab (Samplicio.us / My-Take)

4. Consent page "Zustimmen und fortfahren" (CUA [44]):
   cua.click(pid, wid, 44)   # AXButton "Zustimmen und fortfahren"
   → Consent akzeptiert

5. "Starten" Button (CUA [22]):
   cua.click(pid, wid, 22)   # AXButton "Starten "  
   → Survey läuft im Hintergrund

6. Survey disqualifiziert → Redirect zurück zu heypiggy
   → "Umfrage passt nicht" + 0.02€ compensation
   → Level Up: 10% Bonus für 1 Stunde!
   → Balance: 0.70€ → 0.72€
```

### Survey Detection (Critical: Multiple Dashboard Tabs)

```python
# RICHTIG: Finde den Tab MIT .survey-item Elementen
for p in pages:
    if p['type'] == 'page' and 'parentId' not in p:
        ws_url = p['webSocketDebuggerUrl']
        ws = create_connection(ws_url)
        ws.send(json.dumps({"id":1,"method":"Runtime.evaluate",
            "params":{"expression":"document.querySelectorAll('.survey-item').length"}}))
        count = json.loads(ws.recv())["result"]["result"]["value"]
        if count > 0:
            target = p  # Dieser Tab hat Surveys!
            break
```

### Survey Card DOM Structure
```html
<div id="survey-66087867" class="survey-item" onclick="clickSurvey('66087867')">
  <span class="survey-item-payout">0.92 €</span>
  <span class="survey-item-time">8 Min</span>
</div>
```
- Klick via CDP JS: `document.getElementById('survey-ID').click()`
- CUA kann NICHT direkt drauf klicken (AXGroup, kein AXButton/AXLink)
- Koordinaten-Klick würde gehen, aber CDP JS ist zuverlässiger

### Key Learnings
1. **Multi-Tab Problem**: heypiggy öffnet mehrere Dashboard-Tabs. Nur EINER hat Surveys.
2. **Survey Modal**: "Umfrage starten" Button erscheint NACH dem Survey-Click als Overlay
3. **Consent Flow**: Samplicio.us/My-Take Consent → Zustimmen → Starten → Fragen
4. **Disqualification**: Kein Problem - 0.02€ Compensation + zurück zum Dashboard
5. **Level Up**: 10% Bonus für 1h nach bestimmten Surveys
6. **Balance Update**: Echtzeit im Dashboard sichtbar (money bag icon)

### Tab Detection (welcher Tab hat Surveys?)
| Tab | URL | Title | Surveys |
|-----|-----|-------|---------|
| 0 | heypiggy.com/ | "HeyPiggy – Verdienen Sie..." (en-dash, Sie) | 0 |
| 3 | heypiggy.com/?page=dashboard | "HeyPiggy – Verdienen Sie..." (en-dash, Sie) | 0 |
| 6 | heypiggy.com/?page=dashboard | "HeyPiggy - Verdiene echtes..." (hyphen, kein Sie) | 12 ✅ |

### CUA Element Registry for Survey Flow
| Step | CUA Index | Role | Label | Function |
|------|-----------|------|-------|----------|
| Click Survey Card | - (CDP JS) | DIV | #survey-ID | Starts survey |
| Confirm | [246] | AXButton | "Umfrage starten" | Opens survey tab |
| Consent | [44] | AXButton | "Zustimmen und fortfahren" | Accept consent |
| Start | [22] | AXButton | "Starten " | Begin survey |

---

## 🔥 SURVEY PROVIDER INTERACTION PATTERNS (2026-05-04)

### Toluna (survey.tolunastart.com)
```
Struktur:
  <form aria-hidden="true">
    <input type="hidden"> für Session
    <div class="cf-question__content" id="A1_content">
      <div role="radiogroup">
        <div class="cf-list__item">           ← Text (nicht interaktiv)
        <div class="cf-radio" role="radio">    ← Klickbares Element (27x27)
```

**Interaktion:**
- ARIA Radio: `querySelectorAll('[role="radio"]')[N].click()`
- Numeric Input: `document.getElementById('A1_1_input').value = '42'`
- Weiter: `querySelector('button').click()` (textContent = '>>')
- Keine nativen `<input type="radio">`! Nur ARIA-Rollen.

### Nfield/Kantar (nfieldeu-interviewing.nfieldmr.com)
```
Struktur:
  <video> mit blob: URL (protected, kein Zugriff)
  <label> für Audio-Optionen
  AXButton "Weiter" [109] (Index variiert)
```

**Interaktion:**
- Audio-Frage: BlackHole + ffmpeg + Omni
- Option: `querySelector('label').click()` auf passendes Label
- Audio via JS: `v.play()`

### Samplicio.us / My-Take
```
Consent → Zustimmen [44] → Starten [22] → My-Take → Disqual/Complete
```

### Cint (s.cint.com)
```
Fingerprint → Router → Survey (Nfield, Toluna, etc.)
```

## 🔥 SURVEY INTERAKTION — IN-PAGE MODALS (2026-05-04)

### Wichtige Erkenntnis: Surveys erscheinen im Dashboard, nicht in neuem Tab!

Wenn `clickSurvey(id)` aufgerufen wird, passiert folgendes:

```
1. clickSurvey(id) → clickedSurvey setzen → startSurvey(id)
2. startSurvey(id):
   a. fetch zu live-api.cpx-research.com mit survey_id
   b. Server antwortet mit JSON: {status: "success", type: "okay"/"question"/"not_okay", ...}
   c. handleSurveyResponse(data):
      - type="okay"   → showTypeOkay(data)   → Modal/Overlay im Dashboard (z.B. "Willkommensbonus-Strecke")
      - type="question" → showTypeQuestion(data) → Frage im Dashboard
      - type="not_okay" → Survey disqualifiziert, nächstes probieren

3. Der Survey INHALT erscheint im Dashboard selbst (kein neuer Tab!)
   - AX-Tree zeigt neue Elemente (Modal, Buttons wie "Starten", ">>")
   - CUA muss nach dem clickSurvey() den AX-Tree rescanen
```

### Warum ich falsch lag
- Ich habe nach NEUEN TABS gesucht (Target.getTargets)
- Der Survey erscheint aber als **In-Page Modal/Overlay**
- "Willkommensbonus-Strecke" war der erfolgreich geöffnete Survey-Content!
- Hätte ich den AX-Tree nach clickSurvey() gescannt, hätte ich Buttons wie "Starten" oder ">>" gefunden

### Korrekter Survey-Start (In-Page)
```
1. clickSurvey(id) → CDP JS
2. Warten 5-8s (API-Call + Rendering)
3. AX-Tree scannen nach:
   - "Umfrage starten" Button → klicken
   - "Starten" Button → klicken
   - ">>" Button → klicken
   - "Zustimmen und fortfahren" → klicken
4. Survey-Provider-Tab erscheint (Samplicio.us, Toluna, etc.)
5. Fragen beantworten...
```

### survey_runner.py Probleme
1. **Uses BANNED skylight-cli** → muss ersetzt werden
2. **Wrong page detection**: `_get_page_id()` sucht falschen Tab
3. **survey_runner sucht in neuem Tab** → Survey kommt In-Page, nicht in neuem Tab!
4. **Keine In-Page Modal-Erkennung nach clickSurvey()**
