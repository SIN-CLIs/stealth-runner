# STATUS.md — Stealth-Runner Live State

> **Letztes Update:** 2026-05-09 | **Auto-Update nach jeder Session**

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
| **Aktuelle Balance** | €2.60 | 2026-05-09 |
| **Heute verdient** | €0.00 | 2026-05-09 |
| **Gesamt verdient** | ~€0.50 | seit Beginn |
| **Surveys completed** | 13 | seit Beginn |
| **Surveys failed** | 107 | seit Beginn |
| **Payouts bestätigt** | 0 | kein Survey hat je ausgezahlt! |

### Warum 0€ Payouts?
- **Unbekannt** — nie analysiert
- Mögliche Gründe: CPX Profil-Screening, Disqualifikation, falsche Answers, Reward-Condition nicht erfüllt

---

## DASHBOARD

| Key | Value |
|-----|-------|
| **Dashboard URL** | `https://www.heypiggy.com/?page=dashboard` |
| **Surveys verfügbar** | ~12 ( variiert ) |
| **Survey-IDs (Beispiele)** | 66950684, 67064749, 67064991, 66949962 |
| **Payout-Range** | €0.11 — €0.48 |

---

## BLOCKER & PROBLEME

### 🚨 P0 — Survey verdient kein Geld
- **Problem:** 13 Surveys completed aber 0€ ausgezahlt
- **Ursache:** Unbekannt — nie untersucht
- **Nächster Schritt:** Nächste Survey manuell durchklicken und Balance vorher/nachher prüfen

### 🚨 P0 — PureSpectrum Drag-Drop Puzzle
- **Problem:** "Zahl X" Angular CDK Drag-Drop bei ~66%
- **Ursache:** Angular CDK reagiert nur auf PointerEvents, MouseEvents werden ignoriert
- **Solution:** `stealth-captcha/src/stealth_captcha/solver/drag_drop_angular.py` — gerade committed, **NIEMALS GETESTET**
- **Nächster Schritt:** In echter PureSpectrum Survey testen

### ⚠️ P1 — Qualtrics hängt bei Sprache-Auswahl
- **Problem:** `.NextButton` nicht gefunden, `<select class="Q_lang">` nicht klickbar
- **Fix:** `selectedIndex` + `dispatchEvent('change')` — nie getestet

### ⚠️ P1 — SurveyRouter hängt bei "Umfrage starten"
- **Status:** ✅ FIXED — window.open interception + Target.createTarget

### ⚠️ P2 — CUA AX-Tree leer für Web-Content
- **Status:** BEKANNT — CUA funktioniert nur für native macOS Popups/Sheets
- **Workaround:** CDP JS ist PRIMARY für alle Browser-Interaktionen

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
| **PureSpectrum** | `screener.purespectrum.com` | ❌ BLOCKED | 2026-05-09 (drag puzzle) |
| **Cint/Nfield** | `sw.cint.com/` | 🔄 UNGETESTET | — |
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
2. **Balance prüfen** → `Balance: €2.60`
3. **Survey scannen** → `document.querySelectorAll('.survey-item')`
4. **Survey 66950684 öffnen** → window.open interception
5. **Manuell durchklicken** → CDP JS
6. **Balance vorher/nachher** → prüfen ob €0.00€ verdient wurde!
7. **STATUS.md updaten** → dieses Dokument

---

## SESSION LOG

| Datum | Balance vorher | Aktion | Balance nachher | Ergebnis |
|-------|---------------|--------|-----------------|----------|
| 2026-05-09 | €2.60 | — | — | — |
| 2026-05-07 | €2.23 | TolunaStart, Strat7, Qualtrics | €2.23 | 0€ verdient (Balance nicht gestiegen!) |
| 2026-05-06 | €1.54 | TolunaStart, Strat7, Qualtrics, Samplicio | €2.15 | +€0.61 verdient |
| 2026-05-05 | ~€1.50 | Civey, Proquoai, My-Take | ~€1.54 | +€0.04 verdient |

**KRITISCHE ERKENNTNIS:** Balance steigt NICHT nach Survey-Completion. Letzter verifizierter Payout war am 2026-05-06 (+€0.38 Qualtrics HUK). Seitdem: 0€.

---

*Update dieses Dokument nach jeder Session!*
*Füge neue Erkenntnisse in die entsprechende Sektion ein.*
*Lösche nichts — füge hinzu.*