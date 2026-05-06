# Issues — Stealth Runner

> Alle Issues sind in `issues/ISSUE-SR-*.md`.

| Issue | Status | Priority | Titel |
|-------|--------|----------|-------|
| [SR-11](issues/ISSUE-SR-11.md) | ✅ COMPLETED | 🔴 Critical | CI/CD — GitHub Actions, Pre-Commit, Auto-Release |
| [SR-12](issues/ISSUE-SR-12.md) | ✅ COMPLETED | 🔴 Critical | Test Suite — Unit, Integration, E2E |
| [SR-13](issues/ISSUE-SR-13.md) | ✅ COMPLETED | 🟠 High | Survey Provider Adapter — Samplicio.us, Cint, Nfield |
| [SR-14](issues/ISSUE-SR-14.md) | ✅ COMPLETED | 🟠 High | Audio Capture Module — BlackHole + ffmpeg + Omni |
| [SR-15](issues/ISSUE-SR-15.md) | ✅ COMPLETED | 🟡 Medium | Captcha Solving — Simple, GeeTest v4, Lemin Puzzle |
| [SR-16](issues/ISSUE-SR-16.md) | ✅ COMPLETED | 🟡 Medium | Error Recovery — Disqualification, Modal Error, Timeout |
| [SR-17](issues/ISSUE-SR-17.md) | ✅ COMPLETED | 🔴 Critical | CUA-ONLY Migration — skylight-cli → cua-driver |
| [SR-18](issues/ISSUE-SR-18.md) | ✅ COMPLETED | 🔴 Critical | stealth-session — Warm Daemon für <50ms Command Execution |
| [SR-19](issues/ISSUE-SR-19.md) | ✅ COMPLETED | 🔴 Critical | stealth-axiom — 3-Tier Hierarchical Model Router |
| [SR-20](issues/ISSUE-SR-20.md) | ✅ COMPLETED | 🔴 Critical | RecursiveMAS — RecursiveLink + Survey MAS Pipeline |
| [SR-21](issues/ISSUE-SR-21.md) | ✅ COMPLETED | 🔴 Critical | stealth-sota — Chaos/Security/Healing/Observability/Determinism |
| [SR-22](issues/ISSUE-SR-22.md) | ✅ COMPLETED | 🔴 Critical | stealth-core + stealth-dynamic — Basis-Klassen + Dynamische Engine |
| [SR-23](issues/ISSUE-SR-23.md) | ✅ COMPLETED | 🔴 Critical | stealth-memory — Ewiges Gedächtnis (opencode.db Poller) |
| [SR-24](issues/ISSUE-SR-24.md) | ✅ COMPLETED | 🔴 Critical | **E2E Test: GoCaptcha Slide mit echtem Browser** |
| [SR-25](issues/ISSUE-SR-25.md) | ✅ COMPLETED | 🟠 High | **README.md + CLI Dokumentation für @stealth/captcha** |
| [SR-26](issues/ISSUE-SR-26.md) | ✅ COMPLETED | 🟠 High | **Unit Tests: CDP Client + HitTester + Memory** |
| [SR-27](issues/ISSUE-SR-27.md) | ✅ COMPLETED | 🟡 Medium | **stealth-suite: Incident Resolution + Monitoring** |

---

## 🔴 NEW — Qualtrics HUK Coburg Survey (2026-05-06)

| Feld | Wert |
|------|------|
| Status | ✅ COMPLETED + DOCUMENTED |
| Priority | 🟠 High |
| Payout | **+0.38€** (highest single survey so far!) |
| Gefunden | 2026-05-06 |

### Discovery
Qualtrics surveys (`eu.qualtrics.com/jfe/form/`) are a DIFFERENT platform from TolunaStart.
They use:
- `.NextButton` for page advancement
- `input[type=radio]` with global indices
- `input[type=checkbox]` for multi choice
- `textarea.InputText` for text input with Event dispatch
- `table.ChoiceStructure` for matrix tables (rows × columns)
- Webpack SPA — requires 3-5s wait for render

### Flow (21 pages)
```
Welcome → Gender → Age → Contracts → Insurance Products →
Insurance Companies → Assign to Company → Target Confirmation →
NPS (0-10) → NPS Reason → Info Sources → Brand Matrix (8×5) →
Self/Agent → Price/Service → Family Status → Household Size →
State → Employment → Education → HH Income → Personal Income
```

### File
- `/commands/surveys/qualtrics-huk-survey.md` → NEW ✅

---

## 🔴 CRITICAL — SURVEY RATING MANDATORY — 2026-05-06

| Feld | Wert |
|------|------|
| Status | ✅ DOCUMENTED + VERIFIED |
| Priority | 🔴 Critical |
| Gefunden | 2026-05-06 |

### Problem
Every heypiggy/CPX survey ends with a rating page. Without rating, you lose the **+0.01€ bonus**.

### Solution
```python
# After survey completion, find the rating tab
for p in pages:
    if 'rating.php' in p.get('url',''):
        ws_url = p.get('webSocketDebuggerUrl')
        break

# Click the rating button
ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate', 'params': {'expression': 'document.querySelector("button").click()'}}))
```

### Betroffene Files
- `/commands/heypiggy/rating-page.md` → NEW ✅
- `/commands/quick-reference.md` → UPDATED ✅
- `/sessions/2026-05-06.md` → UPDATED ✅

### Flow
```
Survey completes → "Diese Umfrage bewerten" link → rating.php → +0.01€ → "Zurück zur Website"
```

---

## 🟠 HIGH — TolunaStart JS .click() Pattern — 2026-05-06

| Feld | Wert |
|------|------|
| Status | ✅ VERIFIED |
| Priority | 🟠 High |
| Gefunden | 2026-05-06 |

### Discovery
For `survey.tolunastart.com`, CDP MouseEvent on .cf-radio/.cf-checkbox **FAILS**.
JS `.click()` on these elements **ALWAYS WORKS**.

### Solution
```python
# RADIO (single select)
ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate', 'params': {'expression': '(function(){var rs=document.querySelectorAll(".cf-radio");rs[INDEX].click();})()'}}))

# CHECKBOX (multi select)
ws.send(json.dumps({'id': 0, 'method': 'Runtime.evaluate', 'params': {'expression': '(function(){var cbs=document.querySelectorAll(".cf-checkbox");[0,2,3].forEach(function(i){cbs[i].click();});})()'}}))

# BUTTON
document.querySelector("button").click()

# INPUT
i.value = "32"; i.dispatchEvent(new Event("input", {bubbles:true}))
```

### Betroffene Files
- `/commands/tolunastart-survey.md` → NEW ✅ (37 steps documented)
- `/commands/quick-reference.md` → UPDATED ✅

---

## 🟠 HIGH — Insights-Today SELECT + LABEL Pattern — 2026-05-06

| Feld | Wert |
|------|------|
| Status | ⚠️ SCREEN-OUT at education |
| Priority | 🟠 High |
| Gefunden | 2026-05-06 |

### Discovery
Insights-Today uses:
1. `<select>` for age (not radio buttons)
2. Labels for income radio groups (MouseEvent on LABEL needed)
3. Screen-out at "Universitätsabschluss" education

### Solution
```python
# Age: SELECT dropdown
sel = document.querySelector("select");
sel.value = "32";
sel.dispatchEvent(new Event("change", {bubbles: true}));

# Income: MouseEvent on LABEL containing "30.000"
for label in labels:
    if "30.000" in label.textContent:
        # MouseEvent click on label

# Education: Try Abitur instead of Universitätsabschluss
rs = document.querySelectorAll("input[name=education]");
rs[3].click();  # Abitur instead of rs[6] (Universität)
```

### Betroffene Files
- `/commands/insights-today-survey.md` → NEW ✅

---

## 🔴 CRITICAL — orchestrator.py importiert gelöschte Datei — 2026-05-05

| Feld | Wert |
|------|------|
| Status | ✅ FIXED |
| Priority | 🔴 Critical |
| Gefunden | 2026-05-05 |
| Gefixt | 2026-05-05 |

### Problem
`heypiggy_login_box.py` gelöscht aber `orchestrator.py` (line 90) importiert noch davon.

### Fix
`orchestrator.py` → `from cli.modules.auto_google_login import execute as auto_google_login`

### Betroffene Files
- `/Users/jeremy/dev/stealth-runner/app/core/orchestrator.py` → FIXED ✅
- `/Users/jeremy/dev/stealth-runner/AGENTS.md` → FIXED ✅

---

## Open Issues Summary

| # | Titel | Status | Nächste Aktion |
|---|-------|--------|----------------|
| — | **PureSpectrum CAPTCHA** | ❌ BLOCKED | Solve base64 PNG OCR for 12 survey IDs |
| — | **Surveyrouter** | ❌ HANGS | Page never loads content |
| — | **Insights-Today retry** | ⚠️ PENDING | Try Abitur education level |
| SR-27 | stealth-suite: Incident Resolution & Monitoring | ✅ COMPLETED | 5 Incident-Files deployed |

---

## Neue dokumentierte Provider (2026-05-06)

| Provider | Survey | Ergebnis | Dokumentation |
|----------|--------|----------|----------------|
| **Qualtrics (HUK)** | 66844385 | ✅ **+0.38€** COMPLETED | `surveys/qualtrics-huk-survey.md` |
| TolunaStart | 66583827 | ✅ +0.09€ (92% complete) | `tolunastart-survey.md` |
| Insights-Today | 66291306 | ❌ Screen-out | `insights-today-survey.md` |
| CPX Rating | (post-survey) | ✅ +0.01€ bonus | `heypiggy/rating-page.md` |
| **PureSpectrum** | 66845098 + more | ❌ CAPTCHA blocked | `purespectrum-survey.md` |
