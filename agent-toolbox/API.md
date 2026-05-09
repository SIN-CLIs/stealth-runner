# Agent-Toolbox API Dokumentation

## Überblick

Die Agent-Toolbox API bietet Endpunkte für Browser-Automation, Survey-Ausführung und Login-Automatisierung.

- **API Base URL**: `http://127.0.0.1:8889`
- **Swagger UI**: `http://127.0.0.1:8889/docs`
- **ReDoc**: `http://127.0.0.1:8889/redoc`

## Architektur

```
┌─────────────────────────────────────────────────────────────┐
│                    Chrome (CDP Port 9999)                     │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Profil 901 (Jeremy) Kopie → /tmp/chrome-jeremy-*   │   │
│  │  + 7 HeyPiggy-Cookies aus ~/.stealth/... injectiert  │   │
│  │  ┌─────────────────────────────────────────────────┐  │   │
│  │  │  CDP WebSocket → Runtime.evaluate, setCookies  │  │   │
│  │  │  ┌─────────────────────────────────────────┐  │  │   │
│  │  │  │  HeyPiggy Dashboard / Survey Pages    │  │  │   │
│  │  │  └─────────────────────────────────────────┘  │  │   │
│  │  └─────────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │ HTTP/CDP
┌─────────────────────────────────────────────────────────────┐
│                  FastAPI Server (Port 8889)                 │
│  ┌─────────────────────────────────────────────────────┐     │
│  │  Endpunkte:                                        │     │
│  │  • POST /browser/start → Chrome starten           │     │
│  │  • GET  /browser/health → Status prüfen           │     │
│  │  • POST /survey/click-card → Survey öffnen        │     │
│  │  • POST /survey/run-one → Survey ausführen        │     │
│  └─────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

## Chrome Setup

Chrome wird für HeyPiggy so gestartet (COPY EXACT!):

1. **Profil 901 (Jeremy) kopieren**:
   ```bash
   cp -R "$HOME/Library/Application Support/Google Chrome/Profile 901 (Jeremy)" /tmp/chrome-jeremy-heypiggy-9999
   ```
2. **Chrome starten**: mit `--remote-debugging-port=9999`
3. **7 HeyPiggy-Cookies injectieren**: aus `~/.stealth/heypiggy-backup/heypiggy-cookies.json`

**Wichtige Flags**:
- `--remote-debugging-port=9999` — CDP Endpoint (NICHT 8888!)
- `--remote-allow-origins="*"` — WebSocket Origin (MIT Quotes!)
- `--force-renderer-accessibility` — für CUA AX-Tree
- `--user-data-dir="/tmp/chrome-jeremy-heypiggy-9999"` — Profil 901 Kopie

**Cookie-Injection (nach Start)**:
```python
import json, asyncio, websockets, urllib.request
with open('/Users/jeremy/.stealth/heypiggy-backup/heypiggy-cookies.json') as f:
    data = json.load(f)
heypiggy_cookies = [{'name':c['name'],'value':c['value'],'domain':c['domain'],'path':c.get('path','/'),'expires':c.get('expires',-1),'secure':c.get('secure',False),'httpOnly':c.get('httpOnly',False)} for c in data['cookies'] if 'heypiggy' in c.get('domain','')]
pages = json.load(urllib.request.urlopen('http://127.0.0.1:9999/json/list'))
ws = [p['webSocketDebuggerUrl'] for p in pages if p.get('type')=='page' and 'heypiggy' in p.get('url','')][0]
async def run():
    async with websockets.connect(ws) as ws2:
        await ws2.send(json.dumps({'id':1,'method':'Network.setCookies','params':{'cookies':heypiggy_cookies}}))
        await ws2.recv()
        await ws2.send(json.dumps({'id':2,'method':'Page.navigate','params':{'url':'https://www.heypiggy.com/?page=dashboard'}}))
asyncio.run(run())
```
- `--user-data-dir="/tmp/chrome-jeremy-heypiggy-9999"` — Profil 901 (Jeremy) Kopie
- `--profile-directory="Profile 901 (Jeremy)"` — Profil-Name

## API Endpunkte

### Browser Management

#### POST /browser/start
Chrome starten oder wiederverwenden.

**Request**:
```json
{
"profile_name": "Profile 901 (Jeremy)",
  "headless": false,
  "cdp_port": 9999
}
```

**Response**:
```json
{
  "status": "success",
  "profile": "Profile 901 (Jeremy)",
  "headless": false,
  "cdp_port": 9999,
  "message": "Browser started (warm)"
}
```

#### POST /browser/stop
Chrome beenden und aufräumen.

**Response**:
```json
{
  "status": "success",
  "message": "Browser stopped"
}
```

#### GET /browser/health
Browser-Status prüfen.

**Response**:
```json
{
  "running": true,
  "profile": "Profile 901 (Jeremy)",
  "last_used": 1741234567.0,
  "idle_seconds": 45.2
}
```

### Survey Actions

#### POST /survey/click-card
Survey-Karte auf Dashboard klicken.

**Request**:
```json
{
  "survey_id": null,
  "cdp_port": 9999,
  "profile_name": "default"
}
```

**Response**:
```json
{
  "status": "success",
  "survey_id": "12345",
  "modal_visible": true,
  "modal_text": "Umfrage starten...",
  "modal_buttons": ["Umfrage starten", "Abbrechen"],
  "message": "Clicked survey card (12345)"
}
```

#### GET /survey/modal
Modal-Inhalt lesen (Buttons, Felder, Text).

**Request**:
```json
{
  "cdp_port": 9999,
  "profile_name": "default"
}
```

**Response**:
```json
{
  "status": "success",
  "modal_visible": true,
  "elements": [
    {"ref": "@b0", "role": "button", "text": "Weiter", "visible": true}
  ],
  "text": "Frage 1 von 5...",
  "page_title": "Survey",
  "provider": "qualtrics",
  "progress": "1/5",
  "message": "Modal with 3 elements"
}
```

#### POST /survey/click-button
Button im Modal klicken.

**Request**:
```json
{
  "button_label": "Weiter",
  "cdp_port": 9999,
  "profile_name": "default",
  "timeout_ms": 5000
}
```

#### POST /survey/select-option
Radio/Checkbox auswählen.

**Request**:
```json
{
  "option_text": "Männlich",
  "cdp_port": 9999,
  "profile_name": "default",
  "wait_after_ms": 1000
}
```

#### POST /survey/fill-text
Text-Eingabe füllen.

**Request**:
```json
{
  "input_label": "Alter",
  "value": "32",
  "cdp_port": 9999,
  "profile_name": "default"
}
```

#### POST /survey/run-one
Komplette Survey ausführen (Step-by-step Loop).

**Request**:
```json
{
  "survey_id": null,
  "cdp_port": 9999,
  "profile_name": "default",
  "max_pages": 20
}
```

**Response**:
```json
{
  "status": "completed",
  "survey_id": "12345",
  "pages_completed": 5,
  "earned": 2.50,
  "elapsed_s": 45.2,
  "message": "Survey completed after 5 pages"
}
```

### Service Endpoints

#### POST /services/heypiggy/login
HeyPiggy Login via Google OAuth.

**Request**:
```json
{
  "profile_name": "default",
  "cdp_port": 9999,
  "pid": null
}
```

**Response**:
```json
{
  "status": "success",
  "service": "heypiggy",
  "profile": "default",
  "message": "Login successful",
  "details": {
    "pid": 12345,
    "wid": 67890
  }
}
```

### Utility Endpoints

#### POST /tools/navigate
Zu URL navigieren.

**Request**:
```json
{
  "url": "https://www.heypiggy.com/?page=dashboard",
  "wait_until": "networkidle"
}
```

#### POST /tools/screenshot
Screenshot erstellen.

**Request**:
```json
{
  "full_page": true,
  "selector": null
}
```

**Response**:
```json
{
  "status": "success",
  "profile": "default",
  "base64_image": "iVBORw0KGgo...",
  "mime_type": "image/png"
}
```

#### POST /tools/page-content
Seiteninhalt extrahieren.

**Request**:
```json
{
  "selector": null,
  "max_length": 5000
}
```

## Fehlerbehandlung

Alle Fehler werden als JSON mit `status: "error"` zurückgegeben:

```json
{
  "status": "error",
  "error_code": "internal_error",
  "message": "Chrome not reachable on port 9999"
}
```

## Port-Konfiguration

| Service | Port | Zweck |
|---------|------|-------|
| Chrome CDP | 9999 | Chrome DevTools Protocol |
| FastAPI | 8889 | API Endpunkte |

**Wichtig**: Chrome CDP und FastAPI müssen auf unterschiedlichen Ports laufen!

## Umgebungsvariablen

```bash
# Optional
export BROWSER_HEADLESS="false"  # Headless-Modus
export CHROME_BINARY=""            # Custom Chrome Pfad
export PROFILE_DIR="./profiles"    # Profil-Verzeichnis
```

## Beispiel-Workflow

```bash
# 1. API starten
python3 -m uvicorn api.main:app --port 8889 --host 127.0.0.1

# 2. Chrome starten
curl -X POST http://127.0.0.1:8889/browser/start \
  -H "Content-Type: application/json" \
  -d '{"profile_name": "Profile 901 (Jeremy)", "cdp_port": 9999}'

# 3. Zu HeyPiggy navigieren
curl -X POST http://127.0.0.1:8889/tools/navigate \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.heypiggy.com/?page=dashboard"}'

# 4. Screenshot für Analyse
curl -X POST http://127.0.0.1:8889/tools/screenshot \
  -H "Content-Type: application/json" \
  -d '{"full_page": true}'

# 5. Survey ausführen
curl -X POST http://127.0.0.1:8889/survey/run-one \
  -H "Content-Type: application/json" \
  -d '{"cdp_port": 9999, "max_pages": 20}'

# 6. Chrome stoppen
curl -X POST http://127.0.0.1:8889/browser/stop
```

## Technische Details

### BrowserManager (SINator-Style)

```python
from core.browser_manager import BrowserManager

# Chrome mit Profil 901 (Jeremy) auf Port 9999
bm = BrowserManager(
    profile_name="Profile 901 (Jeremy)",
    cdp_port=9999,
    headless=False
)

# Starten
ctx = await bm.start()

# Page holen
page = await bm.get_page()

# Stoppen
await bm.stop()
```

### CDP Direktzugriff

```python
import urllib.request, json

# Tabs auflisten
pages = json.loads(urllib.request.urlopen(
    "http://127.0.0.1:9999/json"
).read())

# WebSocket URL für Dashboard
ws_url = next(
    p["webSocketDebuggerUrl"] 
    for p in pages 
    if "dashboard" in p.get("url", "").lower()
)
```

## Bekannte Probleme

1. **Google Login (Passkey)**: Shadow DOM Buttons nicht via CDP/JS automatisierbar. Manuelle Eingabe oder Passwort-basierter Login nötig.

2. **Port-Konflikt**: Chrome CDP und FastAPI dürfen nicht auf demselben Port laufen. Chrome: 9999, API: 8889.

3. **Profil-Kopie**: Chrome verschlüsselt Cookies mit dem Pfad als Key. Kopieren (nicht Symlink!) ist nötig.

## Changelog

- **2026-05-08**: API auf Port 8889, Chrome CDP auf 8888 (veraltet)
- **2026-05-09**: Chrome CDP auf 9999 (Profile 901 Kopie + Cookie-Injection)
- **2026-05-08**: SINator-Style BrowserManager mit Profil-Kopie
- **2026-05-08**: `--remote-allow-origins=*` ohne Quotes (zsh glob fix)
- **2026-05-08**: Survey Actions mit CDP WebSocket + Origin Header
