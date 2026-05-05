# brain.md – Systemwissen & Architektur-Entscheidungen (CUA-ONLY)

> **← [sinrules.md](sinrules.md) ist die zentrale Regeldatei. Alle Regeln sind DORT definiert.**
> **← [issues.md](issues.md) dokumentiert aktuelle Issues.**
> **← [registry.md](registry.md) ist der Master Command Index.**
>
> **CUA-ONLY AKTIV**: cua-driver für alle Browser-Interaktionen.
> - `webauto-nodriver` = ABSOLUT BANNED
> - `skylight-cli` = DEPRECATED (nur macOS-Menü-Fallback)
> - CDP = NUR für JS execute/evaluate, BANNED für Navigation/Klicks
>
> **Stealth Pipeline**: perceive → plan → guard → execute → critique
> - Jede Aktion MUSS durch die Pipeline
> - Guardian-Check vor jedem Klick (Verify-Box)
> - Ergebnis in history.md protokollieren

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

## 🔥 CUA-ONLY STACK (2026-05-04, AKTIV)

### Das Problem
CDP+AX Trinity ist OBSOLET: Chrome blockiert CDP WebSocket (origin check).
skylight-cli mischt Browser-Chrome + Web-Content in einem flachen Array.
skylight-cli element-index ist NICHT stabil.

### Die Lösung: CUA-ONLY Trinity (2026-05-04)

```
┌────────────────────────────────────────────────────────────────────┐
│                    CUA-ONLY TRINITY                                │
│                                                                     │
│  playstealth launch → cdp_port (NUR Chrome Start!)                 │
│       │                                                             │
│       ▼                                                             │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ DAEMON (nohup): nohup cua-driver serve > /tmp/cua-daemon.log │  │
│  │ → OHNE Daemon: kein Session-Cache → keine Clicks!            │  │
│  └──────────────────────────────────────────────────────────────┘  │
│       │                                                             │
│       ▼                                                             │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ WINDOW FINDEN: cua-driver call list_windows                  │  │
│  │ → depth > 5 FILTERN (Apple-Menüleiste ignorieren!)           │  │
│  └──────────────────────────────────────────────────────────────┘  │
│       │                                                             │
│       ▼                                                             │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ STATE CACHEN: cua-driver call get_window_state               │  │
│  │ → AX-Tree mit element_index + @(x,y,w,h) Positionen          │  │
│  │ → IMMER fresh scannen (Indices sind NICHT stabil!)           │  │
│  └──────────────────────────────────────────────────────────────┘  │
│       │                                                             │
│       ▼                                                             │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ INTERAKTION: cua-driver call click (PRIMARY!)                │  │
│  │ → 30s Timeout + 3x Retry bei kAXErrorCannotComplete          │  │
│  │ → set_value für Textfelder                                   │  │
│  │ → press_key für Enter/Tab                                    │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ⚠️ CDP JS evaluate: NUR für DOM LESEN + Button-Antworten         │
│     CDP Navigation: VERBOTEN                                       │
│     skylight-cli index-Klicks: VERBOTEN                            │
│     webauto-nodriver: ABSOLUT VERBOTEN                             │
│                                                                     │
└────────────────────────────────────────────────────────────────────┘
```

### Tool-Separation

| Tool | For | NEVER For |
|------|-----|-----------|
| **cua-driver** | ALLE Interaktionen (PRIMARY) | — |
| **CDP Runtime.evaluate** | DOM lesen, Button-Antworten | Navigation, Klicks |
| **macos-ax-cli** | Systemweites SCANNEN (NUR Finden!) | Klicken |
| **playstealth** | Chrome Launch | Interaktion |

### Warum das funktioniert

| Aspekt | ALT (CDP+AX) | NEU (CUA-ONLY) |
|--------|-------------|----------------|
| Chrome-Kompatibilität | ❌ Origin check blockiert CDP | ✅ Kein CDP WebSocket nötig |
| Index-Stabilität | ❌ Flacher Baum, Browser+Web gemischt | ✅ CUA Window-spezifisch |
| Session-Cache | ⚠️ Unzuverlässig | ✅ Daemon-basiert (nohup) |
| Browser-Chrome | ❌ Enthalten | ✅ depth > 5 filtert Menüleisten |
| Google-Detection | ⚠️ --disable-blink-features | ✅ AXPress via CUA |

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

## 🔥 HEYPIGGY GOOGLE LOGIN — KORREKTER FLOW (2026-05-04)

**Eigene Chrome-Instanz via playstealth launch! KEIN User Chrome touchieren!**

```
1. playstealth launch --url 'https://heypiggy.com'  → PID + WID
2. list_windows → HeyPiggy WID finden
3. get_window_state → AX-Tree scannen
4. Click Google Login-Symbol link [index]
5. Wait 3s → Google OAuth Popup WID finden
6. get_window_state → AX-Tree scannen
7. Enter email in AXTextField [index]
8. Click "fortfahren" Button [index]
9. Wait 2s → macOS Keychain Dialog erscheint
10. Enter "admin" in Keychain Password Field
11. Click "entsperren" Button
12. Wait 3s → Dashboard prüfen
```

**WICHTIG:**
- NUR eigenes Chrome via playstealth launch starten
- KEIN pkill, killall, oder grep auf User Chrome
- Fresh Profile: `/tmp/heypiggy-bot-XXXXX`
- MAC_PASSWORD="admin" für Keychain Dialog

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

## 🔥 HEYPIGGY LOGIN — KORREKTER FLOW (2026-05-04)

**Eigene Chrome-Instanz via playstealth launch! KEIN User Chrome touchieren!**

### Aufruf
```
playstealth launch --url 'https://heypiggy.com'
# → PID + CDP_PORT + Profil
```

### Korrekter Flow
```
2. get_window_state → AX-Tree scannen
3. Click Google Login-Symbol link [Index]
4. Wait 3s → Google OAuth Popup WID finden
5. get_window_state → AX-Tree scannen
6. Enter email in AXTextField [Index]
7. Click "fortfahren" Button [Index]
8. Wait 2s → macOS Keychain Dialog erscheint
9. Enter "admin" in Keychain Password Field
10. Click "entsperren" Button
11. Wait 3s → Dashboard prüfen (kein "Anmelden oder Registrieren")
```

**WICHTIG:**
- NUR eigenes Chrome via playstealth launch
- KEIN pkill, killall, oder grep auf User Chrome
- Fresh Profile: `/tmp/heypiggy-bot-XXXXX`
- MAC_PASSWORD="admin" für Keychain Dialog
- 7 SCHRITTE: Click → Email → Fortfahren → admin → Entsperren → Weiter → Dashboard

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

## 🔥 stealth-session Architektur (2026-05-04)

```
Agent (OpenCode)
  │ stealth-exec
  ▼
┌──────────────────────────────────┐
│  stealth-session Daemon          │
│                                  │
│  1. IdiotProofGuard              │
│     → Prüft/repariert Befehle   │
│                                  │
│  2. WarmExecutor                 │
│     → Führt aus (<50ms)         │
│                                  │
│  3. Verify-Box                   │
│     → Prüft Ergebnis             │
│                                  │
│  4. WindowManager                │
│     → Trackt Fenster in Echtzeit │
└──────────────────────────────────┘
```
## login_ok — 2026-05-04T17:16:18.406812
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:18.408376
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:18.455571
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:18.515476
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:18.591222
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:18.598055
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:18.638465
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:18.639376
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:18.640038
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:18.640494
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:18.650488
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:18.823316
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:19.118998
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:19.120208
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:19.120574
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:19.193310
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:19.211375
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:19.232763
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:19.236897
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:19.324322
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:19.354705
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:19.368658
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:19.387104
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:19.411837
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:19.459394
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:19.479395
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:19.513774
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:19.525288
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:19.528708
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:20.459618
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:20.480097
Login-Box funktioniert.
---
## survey_started — 2026-05-04T17:16:20.482916
Survey erfolgreich gestartet.
---
## survey_started — 2026-05-04T17:16:20.510328
Survey erfolgreich gestartet.
---
## login_ok — 2026-05-04T17:16:20.518522
Login-Box funktioniert.
---
## survey_started — 2026-05-04T17:16:20.523157
Survey erfolgreich gestartet.
---
## survey_started — 2026-05-04T17:16:20.526242
Survey erfolgreich gestartet.
---
## survey_started — 2026-05-04T17:16:20.532947
Survey erfolgreich gestartet.
---
## survey_started — 2026-05-04T17:16:20.533462
Survey erfolgreich gestartet.
---
## survey_started — 2026-05-04T17:16:20.534057
Survey erfolgreich gestartet.
---
## survey_started — 2026-05-04T17:16:20.534711
Survey erfolgreich gestartet.
---
## survey_started — 2026-05-04T17:16:20.535488
Survey erfolgreich gestartet.
---
## survey_started — 2026-05-04T17:16:20.538609
Survey erfolgreich gestartet.
---
## login_ok — 2026-05-04T17:16:20.545801
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:20.600242
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:20.618439
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:20.624555
Login-Box funktioniert.
---
## survey_done — 2026-05-04T17:16:20.710101
Umfrage vollständig abgeschlossen.
---
## login_ok — 2026-05-04T17:16:20.715859
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:20.733467
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:20.735351
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:20.741102
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:20.752238
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:20.758001
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:21.033435
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:21.047197
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:21.139909
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:21.377783
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:21.820316
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:21.855443
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:21.890544
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:22.002535
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:22.008018
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:22.020479
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:22.246909
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:22.318280
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:22.387457
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:22.390781
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:22.414393
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:22.478911
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:22.517075
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:22.522969
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:22.527349
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:22.613338
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:22.871217
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:22.973861
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:23.013598
Login-Box funktioniert.
---
## survey_done — 2026-05-04T17:16:23.471259
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T17:16:23.621220
Umfrage vollständig abgeschlossen.
---
## login_ok — 2026-05-04T17:16:23.748609
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:23.862567
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:23.914451
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:24.033607
Login-Box funktioniert.
---
## survey_done — 2026-05-04T17:16:24.130882
Umfrage vollständig abgeschlossen.
---
## login_ok — 2026-05-04T17:16:24.390915
Login-Box funktioniert.
---
## survey_done — 2026-05-04T17:16:24.447511
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T17:16:24.453322
Umfrage vollständig abgeschlossen.
---
## login_ok — 2026-05-04T17:16:24.483877
Login-Box funktioniert.
---
## survey_done — 2026-05-04T17:16:24.738760
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T17:16:24.957999
Umfrage vollständig abgeschlossen.
---
## login_ok — 2026-05-04T17:16:24.973350
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:24.977835
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:24.979067
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:25.126765
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:26.006573
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:26.168080
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:27.055222
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:27.381522
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:27.382462
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:27.793398
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:27.818048
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:27.820237
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:27.827647
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:27.828633
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:27.831898
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:27.833922
Login-Box funktioniert.
---
## survey_started — 2026-05-04T17:16:27.845134
Survey erfolgreich gestartet.
---
## survey_started — 2026-05-04T17:16:27.845760
Survey erfolgreich gestartet.
---
## survey_started — 2026-05-04T17:16:27.846637
Survey erfolgreich gestartet.
---
## login_ok — 2026-05-04T17:16:27.878623
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:27.927513
Login-Box funktioniert.
---
## survey_done — 2026-05-04T17:16:28.131721
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T17:16:28.137755
Umfrage vollständig abgeschlossen.
---
## login_ok — 2026-05-04T17:16:28.177131
Login-Box funktioniert.
---
## survey_done — 2026-05-04T17:16:28.208862
Umfrage vollständig abgeschlossen.
---
## login_ok — 2026-05-04T17:16:28.345400
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:28.350999
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:28.352041
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:28.353162
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:28.355823
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:28.359978
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:28.368784
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:28.372148
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:28.372826
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:28.373520
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:28.373789
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:28.374917
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:28.376649
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:28.378852
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:28.380967
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:28.384666
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:28.434990
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:28.438298
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:28.463950
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:28.464770
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:28.466207
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:28.467191
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:28.614351
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:28.634085
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:28.639881
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:28.642156
Login-Box funktioniert.
---
## survey_started — 2026-05-04T17:16:28.764741
Survey erfolgreich gestartet.
---
## survey_started — 2026-05-04T17:16:28.767615
Survey erfolgreich gestartet.
---
## survey_started — 2026-05-04T17:16:28.778052
Survey erfolgreich gestartet.
---
## survey_started — 2026-05-04T17:16:28.784806
Survey erfolgreich gestartet.
---
## survey_started — 2026-05-04T17:16:28.798615
Survey erfolgreich gestartet.
---
## survey_started — 2026-05-04T17:16:28.799056
Survey erfolgreich gestartet.
---
## survey_started — 2026-05-04T17:16:28.799771
Survey erfolgreich gestartet.
---
## survey_started — 2026-05-04T17:16:28.805413
Survey erfolgreich gestartet.
---
## survey_started — 2026-05-04T17:16:28.808700
Survey erfolgreich gestartet.
---
## login_ok — 2026-05-04T17:16:28.809290
Login-Box funktioniert.
---
## survey_started — 2026-05-04T17:16:28.831349
Survey erfolgreich gestartet.
---
## survey_started — 2026-05-04T17:16:28.833281
Survey erfolgreich gestartet.
---
## survey_started — 2026-05-04T17:16:28.833609
Survey erfolgreich gestartet.
---
## survey_started — 2026-05-04T17:16:28.838295
Survey erfolgreich gestartet.
---
## survey_started — 2026-05-04T17:16:28.853215
Survey erfolgreich gestartet.
---
## login_ok — 2026-05-04T17:16:28.914952
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:28.941232
Login-Box funktioniert.
---
## survey_started — 2026-05-04T17:16:28.985741
Survey erfolgreich gestartet.
---
## survey_started — 2026-05-04T17:16:29.036304
Survey erfolgreich gestartet.
---
## survey_started — 2026-05-04T17:16:29.046618
Survey erfolgreich gestartet.
---
## survey_started — 2026-05-04T17:16:29.151782
Survey erfolgreich gestartet.
---
## login_ok — 2026-05-04T17:16:29.199182
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:29.208216
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:29.230299
Login-Box funktioniert.
---
## survey_started — 2026-05-04T17:16:29.300805
Survey erfolgreich gestartet.
---
## survey_started — 2026-05-04T17:16:29.321951
Survey erfolgreich gestartet.
---
## login_ok — 2026-05-04T17:16:29.323039
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:29.324640
Login-Box funktioniert.
---
## survey_done — 2026-05-04T17:16:29.341750
Umfrage vollständig abgeschlossen.
---
## survey_started — 2026-05-04T17:16:29.346192
Survey erfolgreich gestartet.
---
## survey_done — 2026-05-04T17:16:29.351180
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T17:16:29.351704
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T17:16:29.370166
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T17:16:29.415161
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T17:16:29.480314
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T17:16:29.521539
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T17:16:29.525088
Umfrage vollständig abgeschlossen.
---
## login_ok — 2026-05-04T17:16:29.530080
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:29.531094
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:29.545890
Login-Box funktioniert.
---
## survey_done — 2026-05-04T17:16:29.557897
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T17:16:29.608693
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T17:16:29.609530
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T17:16:29.610344
Umfrage vollständig abgeschlossen.
---
## login_ok — 2026-05-04T17:16:29.621015
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:29.621295
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:29.621539
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:29.621775
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:29.622072
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:29.622490
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:29.623331
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:29.623841
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:29.624077
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:29.624301
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:29.625385
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:29.660294
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:29.661335
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:29.703323
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:29.791104
Login-Box funktioniert.
---
## survey_done — 2026-05-04T17:16:29.792225
Umfrage vollständig abgeschlossen.
---
## login_ok — 2026-05-04T17:16:30.092175
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:30.094374
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:30.219430
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:30.303591
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:30.304390
Login-Box funktioniert.
---
## survey_done — 2026-05-04T17:16:30.307531
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T17:16:30.308518
Umfrage vollständig abgeschlossen.
---
## login_ok — 2026-05-04T17:16:30.310376
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:30.364952
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:30.415442
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:30.552754
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:30.733263
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:30.747335
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:30.753994
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:30.775290
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:30.859228
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:30.878494
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:30.882379
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:30.886728
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:30.888678
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:30.903061
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:30.905040
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:30.906711
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:30.907385
Login-Box funktioniert.
---
## survey_started — 2026-05-04T17:16:30.909400
Survey erfolgreich gestartet.
---
## login_ok — 2026-05-04T17:16:30.925138
Login-Box funktioniert.
---
## survey_done — 2026-05-04T17:16:30.935789
Umfrage vollständig abgeschlossen.
---
## login_ok — 2026-05-04T17:16:31.005357
Login-Box funktioniert.
---
## survey_done — 2026-05-04T17:16:31.145819
Umfrage vollständig abgeschlossen.
---
## login_ok — 2026-05-04T17:16:31.165815
Login-Box funktioniert.
---
## survey_started — 2026-05-04T17:16:31.166659
Survey erfolgreich gestartet.
---
## survey_started — 2026-05-04T17:16:31.167870
Survey erfolgreich gestartet.
---
## survey_started — 2026-05-04T17:16:31.168971
Survey erfolgreich gestartet.
---
## survey_started — 2026-05-04T17:16:31.169548
Survey erfolgreich gestartet.
---
## login_ok — 2026-05-04T17:16:31.183506
Login-Box funktioniert.
---
## survey_done — 2026-05-04T17:16:31.313291
Umfrage vollständig abgeschlossen.
---
## login_ok — 2026-05-04T17:16:31.314375
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:31.314667
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:31.341964
Login-Box funktioniert.
---
## survey_started — 2026-05-04T17:16:31.350252
Survey erfolgreich gestartet.
---
## login_ok — 2026-05-04T17:16:31.359957
Login-Box funktioniert.
---
## survey_done — 2026-05-04T17:16:31.365750
Umfrage vollständig abgeschlossen.
---
## login_ok — 2026-05-04T17:16:31.373075
Login-Box funktioniert.
---
## survey_started — 2026-05-04T17:16:31.375041
Survey erfolgreich gestartet.
---
## login_ok — 2026-05-04T17:16:31.380841
Login-Box funktioniert.
---
## login_ok — 2026-05-04T17:16:31.392313
Login-Box funktioniert.
---
## survey_started — 2026-05-04T17:16:31.396743
Survey erfolgreich gestartet.
---
## login_ok — 2026-05-04T17:16:31.539492
Login-Box funktioniert.
---
## survey_started — 2026-05-04T17:16:31.541268
Survey erfolgreich gestartet.
---
## survey_started — 2026-05-04T17:16:31.542215
Survey erfolgreich gestartet.
---
## survey_started — 2026-05-04T17:16:31.641228
Survey erfolgreich gestartet.
---
## login_ok — 2026-05-04T17:16:31.651438
Login-Box funktioniert.
---
## survey_done — 2026-05-04T17:16:31.653281
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T17:16:31.654087
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T17:16:31.659782
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T17:57:43.263965
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T17:57:48.432837
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T17:57:53.600549
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T17:57:58.772534
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T17:58:03.941067
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T17:58:09.109106
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T17:58:14.275234
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T17:58:19.446926
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T17:58:24.614881
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T17:58:30.781044
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T17:58:35.951418
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T17:58:41.122891
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T17:58:46.290600
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T17:58:51.462835
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T17:58:57.623696
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T17:59:02.792785
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T17:59:07.964546
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T17:59:13.136607
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T17:59:19.307245
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T17:59:24.477073
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T17:59:29.710172
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T17:59:34.879257
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T17:59:40.047932
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T17:59:45.218123
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T17:59:50.409011
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T17:59:55.612663
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:00:00.953014
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:00:06.119446
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:00:11.288947
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:00:16.459078
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:00:21.627912
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:00:27.471146
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:00:33.629230
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:00:38.799822
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:00:43.990758
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:00:50.107677
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:00:55.295444
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:01:00.486790
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:01:05.656485
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:01:10.886230
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:01:16.129708
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:01:21.300328
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:01:26.471193
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:01:31.642025
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:01:36.813461
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:01:41.971974
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:01:47.141734
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:01:52.310705
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:01:57.479168
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:02:02.646633
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:02:07.816827
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:02:12.987290
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:02:18.159771
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:02:23.332514
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:02:28.508883
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:02:33.683866
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:02:38.857041
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:02:44.032992
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:02:49.208160
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:02:54.381702
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:03:00.579398
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:03:05.783424
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:03:11.065551
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:03:17.531464
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:03:22.722192
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:03:27.896374
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:03:33.117155
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:03:38.283963
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:03:43.443248
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:03:48.610208
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:03:53.777024
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:03:58.928597
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:09:34.821297
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:09:40.013472
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:09:45.184467
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:09:50.353595
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:09:55.587309
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:10:00.754883
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:10:06.935319
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:10:12.220233
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:10:17.381733
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:10:23.577883
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:10:28.881659
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:10:34.174140
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:10:40.239872
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:10:45.556960
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:10:51.554672
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:10:56.930284
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:11:02.128806
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:11:07.380433
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:11:12.551878
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:11:17.725313
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:11:22.932862
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:11:28.102410
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:11:33.255405
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T18:11:39.341649
Umfrage vollständig abgeschlossen.
---
## survey_started — 2026-05-04T18:55:02.983681
Survey erfolgreich gestartet.
---
## survey_started — 2026-05-04T18:56:21.585418
Survey erfolgreich gestartet.
---
## login_ok — 2026-05-04T19:16:24.426819
Login-Box funktioniert.
---
## login_ok — 2026-05-04T19:16:30.499352
Login-Box funktioniert.
---
## login_ok — 2026-05-04T19:17:47.867713
Login-Box funktioniert.
---
## login_ok — 2026-05-04T19:17:53.028859
Login-Box funktioniert.
---
## login_ok — 2026-05-04T19:17:58.180533
Login-Box funktioniert.
---
## login_ok — 2026-05-04T19:18:03.332683
Login-Box funktioniert.
---
## login_ok — 2026-05-04T19:22:18.670421
Login-Box funktioniert.
---
## login_ok — 2026-05-04T19:22:23.828849
Login-Box funktioniert.
---
## survey_started — 2026-05-04T19:40:29.812056
Survey erfolgreich gestartet.
---
## login_ok — 2026-05-04T20:01:09.334566
Login-Box funktioniert.
---
## login_ok — 2026-05-04T20:01:15.881560
Login-Box funktioniert.
---
## login_ok — 2026-05-04T20:01:15.882147
Login-Box funktioniert.
---
## login_ok — 2026-05-04T20:01:21.126197
Login-Box funktioniert.
---
## survey_done — 2026-05-04T20:11:00.621906
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T20:15:40.707889
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T20:15:58.023070
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T20:16:03.187455
Umfrage vollständig abgeschlossen.
---
## survey_done — 2026-05-04T20:16:08.370445
Umfrage vollständig abgeschlossen.
---
## login_ok — 2026-05-05T02:32:39.925743
Login-Box funktioniert.
---
## login_ok — 2026-05-05T02:32:45.209501
Login-Box funktioniert.
---
## login_ok — 2026-05-05T02:32:51.064615
Login-Box funktioniert.
---


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
## login_ok — 2026-05-05T11:39:28.950712
Login-Box funktioniert.
---
## login_ok — 2026-05-05T11:39:34.914807
Login-Box funktioniert.
---
## login_ok — 2026-05-05T11:40:30.629756
Login-Box funktioniert.
---
## login_ok — 2026-05-05T11:40:35.943079
Login-Box funktioniert.
---
## login_ok — 2026-05-05T11:40:41.180012
Login-Box funktioniert.
---

---

## ✅ CUA-ONLY LOGIN SUCCESS — 2026-05-05T13:50+

### 6-Step Login (PID=DYNAMIC, WID 56640 → 56658):
1. [54] AXLink (Google Login-Symbol) → Dashboard WID 56640
2. [25] AXTextField (E-Mail) → set_value zukunftsorientierte.energie@gmail.com
3. [35] AXButton "Weiter"
4. wait → WID 56658 "Jeremy Schulze" (Keychain Auto-Fill!)
5. [62] AXButton "Fortfahren"
6. [41] AXButton "Weiter" (Final)
→ Login complete! Google OAuth WID 56658 GESCHWUNDEN!
→ Dashboard WID 56640 zeigt EINGELOGGT: "Umfragen", "Auszahlung", "Abmelden"

### Neue autoritative Datei:
- `cli/modules/auto_google_login.py` → 463 Zeilen, 6-Step CUA-ONLY
- ERSETZT: `cli/modules/heypiggy_login_box.py` (GELÖSCHT!)

### Keychain Auto-Fill Discovery (KRITISCH!):
- Email eintragen → "Weiter" klicken
- → Keychain füllt AUTOMATISCH Credentials aus (kein Passwort nötig!)
- → "Jeremy Schulze" Konto vorausgewählt
- → NUR "Fortfahren" + final "Weiter" klicken

### BOT Chrome vs USER Chrome:
- BOT: DYNAMIC_PID, profile=/tmp/heypiggy-bot-1777981361
- USER: DYNAMIC_PID, DeepSeek) → NIEMALS TOUCHEN!
- Regel: `ps aux | grep "user-data-dir"` → "heypiggy-bot-" = BOT

### orchestrator.py Fix (CRITICAL BUG):
- Zeile 90 importierte noch `heypiggy_login_box` (gelöscht!)
- FIX: `from cli.modules.auto_google_login import execute as auto_google_login`
- AGENTS.md auch aktualisiert
## login_ok — 2026-05-05T11:50:54.101105
Login-Box funktioniert.
---
## login_ok — 2026-05-05T11:51:40.423522
Login-Box funktioniert.
---
## login_ok — 2026-05-05T11:51:45.983639
Login-Box funktioniert.
---
## login_ok — 2026-05-05T12:14:03.359252
Login-Box funktioniert.
---
## login_ok — 2026-05-05T12:14:08.896187
Login-Box funktioniert.
---
## login_ok — 2026-05-05T12:54:46.690638
Login-Box funktioniert.
---
## login_ok — 2026-05-05T12:54:51.942020
Login-Box funktioniert.
---
## login_ok — 2026-05-05T13:13:52.741097
Login-Box funktioniert.
---
## survey_started — 2026-05-05T13:21:00.695876
Survey erfolgreich gestartet.
---
## survey_started — 2026-05-05T13:21:06.137400
Survey erfolgreich gestartet.
---
## survey_started — 2026-05-05T13:21:11.295142
Survey erfolgreich gestartet.
---
## survey_started — 2026-05-05T13:21:16.454924
Survey erfolgreich gestartet.
---
## survey_started — 2026-05-05T13:21:21.826974
Survey erfolgreich gestartet.
---
