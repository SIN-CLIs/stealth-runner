# STATUS.md — Stealth-Runner Live State

> **Letztes Update:** 2026-05-10 | **Auto-Update nach jeder Session**

---

## CHROME STATUS

| Key | Value |
|-----|-------|
| **Chrome Port** | 9999 |
| **Profile** | Profile 901 (Jeremy) — HeyPiggy |
| **Cookie-Backup** | `~/.stealth/heypiggy-backup/heypiggy-cookies.json` |
| **Bot Profile** | `/tmp/chrome-jeremy-heypiggy-9999/` |
| **Chrome PID** | (nach Start: `ps aux | grep "remote-debugging-port=9999" | grep -v grep` ) |
| **Tabs** | Dashboard + Survey (wenn offen) |

### Chrome Start Recipe (COPY EXACT)
```bash
# 1. Profil kopieren
cp -R "$HOME/Library/Application Support/Google Chrome/Profile 901 (Jeremy)" /tmp/chrome-jeremy-heypiggy-9999

# 2. Chrome starten
nohup "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --remote-debugging-port=9999 \
  --remote-allow-origins="*" \
  --force-renderer-accessibility \
  --no-first-run \
  --user-data-dir="/tmp/chrome-jeremy-heypiggy-9999" \
  "https://www.heypiggy.com/?page=dashboard" &>/dev/null &
sleep 4

# 3. 7 HeyPiggy-Cookies injizieren
python3 -c "
import json, asyncio, websockets, urllib.request
COOKIE_FILE = '~/.stealth/heypiggy-backup/heypiggy-cookies.json'
with open(COOKIE_FILE.expanduser()) as f:
    data = json.load(f)
heypiggy = [{'name':c['name'],'value':c['value'],'domain':c['domain'],'path':c.get('path','/'),'expires':c.get('expires',-1),'secure':c.get('secure',False),'httpOnly':c.get('httpOnly',False)} for c in data.get('cookies',[]) if 'heypiggy' in c.get('domain','')]
pages = json.load(urllib.request.urlopen('http://127.0.0.1:9999/json/list'))
ws = [p['webSocketDebuggerUrl'] for p in pages if p.get('type')=='page' and 'heypiggy' in p.get('url','')][0]
async def run():
    async with websockets.connect(ws) as ws2:
        await ws2.send(json.dumps({'id':1,'method':'Network.setCookies','params':{'cookies':heypiggy}}))
        await ws2.recv()
        await ws2.send(json.dumps({'id':2,'method':'Page.navigate','params':{'url':'https://www.heypiggy.com/?page=dashboard'}}))
        await asyncio.sleep(4)
        await ws2.send(json.dumps({'id':3,'method':'Runtime.evaluate','params':{'expression':'document.body.innerText.substring(0,500)'}}))
        r = await ws2.recv()
        print('EINGELOGGT!' if 'abmelden' in json.loads(r).get('result',{}).get('result',{}).get('value','').lower() else 'FEHLER')
asyncio.run(run())
"
```

### Chrome Kill Recipe (NUR Bot, NIEMALS user Chrome!)
```bash
pkill -f "remote-debugging-port=9999"  # FALSCH — killt ALLE Chrome mit Port 9999!
# RICHTIG:
ps aux | grep "Google Chrome" | grep "remote-debugging-port=9999" | grep -v grep | awk '{print $2}' | xargs kill 2>/dev/null
# ODER:
pkill -f "chrome-jeremy-heypiggy-9999"
```

---

## BALANCE & EARNINGS

| Key | Value | Datum |
|-----|-------|-------|
| **Letzte bekannte Balance** | €2.60 | 2026-05-09 |

### Session-Regel
- Balance NUR nach echter Survey-Completion prüfen (vorher/nachher)
- NIEMALS "Surveys completed/failed" behaupten wenn nicht verifiziert

---

## DASHBOARD

| Key | Value |
|-----|-------|
| **Dashboard URL** | `https://www.heypiggy.com/?page=dashboard` |
| **Surveys verfügbar** | (nach jeder Session scannen via `document.querySelectorAll('.survey-item')`) |

---

## BLOCKER & PROBLEME

### 🚨 P0 — Survey verdient kein Geld
- **Problem:** 13 Surveys completed aber 0€ ausgezahlt
- **Ursache:** Unbekannt — nie untersucht
- **Nächster Schritt:** Nächste Survey manuell durchklicken und Balance vorher/nachher prüfen

### 🚨 P0 — PureSpectrum Drag-Drop Puzzle
- **Status:** 🔄 FIX COMMITTED — needs live retest (2026-05-10)
- **Problem:** "Zahl X" Angular CDK Drag-Drop bei ~66%
- **Ursache:** Angular CDK reagiert nur auf PointerEvents, MouseEvents werden ignoriert
- **Solution:** `stealth-captcha/src/stealth_captcha/solver/drag_drop_angular.py`
- **Key fix:** pointermove/pointerup MUSS auf document.body dispatch werden, NICHT auf img element!
  - `pointerdown` → dispatch on img (source element) ✅
  - `pointermove` → dispatch on document.body ✅
  - `pointerup` → dispatch on document.body ✅
- **Nächster Schritt:** In echter PureSpectrum Survey testen

### ⚠️ P1 — Qualtrics hängt bei Sprache-Auswahl
- **Status:** ✅ FIXED (2026-05-10)
- **Problem:** `.NextButton` nicht gefunden, `<select class="Q_lang">` nicht klickbar
- **Fix:** `selectedIndex` + `dispatchEvent('change')` — committed

### ⚠️ P1 — SurveyRouter hängt bei "Umfrage starten"
- **Status:** ✅ FIXED — window.open interception + Target.createTarget

### ⚠️ P2 — CUA AX-Tree leer für Web-Content
- **Status:** BEKANNT — CUA funktioniert nur für native macOS Popups/Sheets
- **Workaround:** CDP JS ist PRIMARY für alle Browser-Interaktionen

### ✅ P0 — Cookie Timing: Survey öffnet sich in NEUEM Tab ohne Session-Cookies (FIXED)
- **Status:** ✅ VERIFIED (2026-05-10)
- **Problem:** Target.createTarget() öffnet Survey in NEUEM Tab → Cookies fehlen im Redirect-Chain
- **Fix:** `_create_tab()` injiziert 7 HeyPiggy-Cookies VOR `Page.navigate` via `Network.setCookies`
- **Code:** `opener.py` lines 409-430, `tool_open_survey.py` lines 121-180
- **Tests:** 17/18 passed (1 pre-existing failure unrelated)
- **E2E Verified:** Survey 66695822 (Cint → Tivian) — Balance €2.70 → €2.75 (+€0.05) ✅
- **Note:** Early termination with compensation, but balance DID increase — fixes work!

### ✅ P1 — subid Parameter Missing in Intercepted URL — FIXED & VERIFIED (2026-05-10)
- **Problem:** window.open interception captures URL BEFORE subid injection
- **Root cause:** intercepted URL has subid_1=&subid_2=website (defaults, EMPTY)
- **Fix:** `tool_open_survey.py:open_survey()` behält CPX API URL (mit subid) statt intercepted URL
- **Code:** `tool_open_survey.py` lines 545-575
- **Tests:** 18/18 passed
- **E2E Verified:** Survey 66695822 — CPX API URL mit subid erfolgreich verwendet ✅

### 🚨 P1 — Chrome Crash During Survey (Q3 CloudResearch)
- **Problem:** Chrome crashed at cognitive question Q3 during CloudResearch redirect
- **Possible causes:** memory leak, CDP connection issue, JS error in complex survey
- **Impact:** Survey never completes, balance never updates, crash leaves zombie tab
- **Fix:** Unknown — needs investigation, possibly CDP crash handler or survey timeout
- **Status:** 🔴 UNRESOLVED — needs debugging

### ⚠️ P2 — Session Expires After Chrome Restart
- **Problem:** Cookie backup becomes invalid after Chrome restart
- **Root cause:** Sessions have limited lifetime (30min-2h), backup taken during one session may be expired in next
- **Impact:** Must re-login after every Chrome restart — cookie injection may fail with stale cookies
- **Fix:** Session recovery protocol — validate session before every operation, fresh cookies after restart
- **Status:** ⚠️ KNOWN ISSUE — session validation protocol needed

---

## VERIFIZIERTE FLOWS

| Flow | Status | Letzter Test |
|------|--------|--------------|
| **Google Login (CUA)** | ✅ VERIFIED | 2026-05-05 |
| **Cookie-Injection** | ✅ VERIFIED | 2026-05-09 |
| **window.open interception** | ✅ VERIFIED | 2026-05-09 |
| **Survey öffnet sich in Tab** | ✅ VERIFIED | 2026-05-09 |
| **Survey-Tab findet (nach open)** | ✅ VERIFIED | 2026-05-09 |
| **Consent click (.cky-btn-accept)** | ✅ VERIFIED | 2026-05-09 |
| **CDP Input.dispatchMouseEvent** | ✅ VERIFIED | 2026-05-09 |
| **React native value setter** | ✅ VERIFIED | 2026-05-09 |
| **Tab re-discovery via /json** | ✅ VERIFIED | 2026-05-09 |
| **Balance lesen (range filter)** | ✅ VERIFIED | 2026-05-09 |
| **Survey-Rating (+€0.01 Bonus)** | ✅ VERIFIED | 2026-05-06 |

---

## PROVIDER STATUS

| Provider | URL Pattern | Status | Letzter Test |
|----------|------------|--------|--------------|
| **TolunaStart** | `enter.ipsosinteractive.com` | ✅ FUNKTIONIERT | 2026-05-07 (+€0.09) |
| **Strat7 Audiences** | various | ✅ FUNKTIONIERT | 2026-05-06 (+€0.09) |
| **Qualtrics HUK** | `bceconsulting.az1.qualtrics.com` | ✅ FUNKTIONIERT | 2026-05-06 (+€0.38) |
| **Samplicio.us** | `rx.samplicio.us/consent/` | ✅ FUNKTIONIERT | 2026-05-06 |
| **SurveyRouter** | heypiggy internal | ✅ FIXED | 2026-05-09 |
| **CloudResearch** | various | ⚠️ PARTIELL | 2026-05-06 |
| **PureSpectrum** | `screener.purespectrum.com` | 🔄 FIXED — pointer events on body, needs live test | 2026-05-10 |
| **Cint/Tivian** | `sw.cint.com/` | ✅ FUNKTIONIERT | 2026-05-10 (+€0.05 Kompensation) |
| **Insights-Today** | various | ❌ SCREEN-OUT | 2026-05-06 |
| **Brand Ambassador** | `brand-ambassador.com` | ⚠️ SCREEN-OUT | 2026-05-06 |

---

## WICHTIGE DATEIEN

| Datei | Zweck |
|-------|-------|
| `AGENTS.md` | Chrome Recipe, Survey Flow, Tool-Status |
| `survey-cli/survey/execute.py` | Survey-Ausführung pro Provider |
| `survey-cli/survey/opener.py` | Survey-Öffnung + Tab-Management |
| `survey-cli/survey/runner.py` | Survey-Loop + Pre-Qualifier |
| `survey-cli/survey/cdp_client.py` | CDP WebSocket Client (sync) |
| `survey-cli/survey/pre_qualifier.py` | CPX API Pre-Qualifier |
| `survey-cli/survey/providers/purespectrum.py` | PureSpectrum Captcha + Drag |
| `agent-toolbox/api/survey_tools.py` | FastAPI Endpoints |
| `stealth-captcha/src/stealth_captcha/solver/drag_drop_angular.py` | **GERADE COMMITTET — UNGETESTET** |
| `~/.stealth/heypiggy-backup/heypiggy-cookies.json` | 7 HeyPiggy Session-Cookies |

---

## NÄCHSTE SCHRITTE (nach jeder Session updaten)

1. **Chrome starten** → Recipe oben
2. **Balance prüfen** → aktuellen Wert eintragen
3. **Survey scannen** → `document.querySelectorAll('.survey-item')`
4. **Survey öffnen** → window.open interception
5. **Manuell durchklicken** → CDP JS
6. **Balance vorher/nachher** → prüfen ob Balance gestiegen
7. **STATUS.md updaten** → NUR verifizierte Werte eintragen, nichts erfinden

---

## SESSION LOG

| Datum | Balance vorher | Aktion | Balance nachher | Ergebnis |
|-------|---------------|--------|-----------------|----------|
| 2026-05-10 | €2.70 | Survey 66695822 (Cint→Tivian) — cookie+subid fix VERIFIED | €2.75 | ✅ +€0.05 Kompensation (Early Termination) — FIXES WORK! |
| 2026-05-10 | €2.70 | Survey 67078106 (Cint) completed, cookie timing fix attempted | €2.70 | ❌ €0 earned — subid missing in intercepted URL |
| 2026-05-10 | €2.70 | Survey 67078107 (CPX→PureSpectrum→Potloc→CloudResearch) — subid empty, Chrome crashed at Q3 | €2.70 | ❌ €0 earned — multiple issues |
| 2026-05-09 | €2.60 | — | — | — |
| 2026-05-07 | €2.23 | TolunaStart, Strat7, Qualtrics | €2.23 | 0€ verdient (Balance nicht gestiegen!) |
| 2026-05-06 | €1.54 | TolunaStart, Strat7, Qualtrics, Samplicio | €2.15 | +€0.61 verdient |
| 2026-05-05 | ~€1.50 | Civey, Proquoai, My-Take | ~€1.54 | +€0.04 verdient |

**KRITISCHE ERKENNTNIS:** ✅ BALANCE STEIGT WIEDER! Cookie+Subid Fix verifiziert (2026-05-10, Survey 66695822, +€0.05). Letzter vorheriger Payout: 2026-05-06 (+€0.38 Qualtrics HUK). Die Fixes funktionieren!

---

*Update dieses Dokument nach jeder Session!*
*Füge neue Erkenntnisse in die entsprechende Sektion ein.*
*Lösche nichts — füge hinzu.*