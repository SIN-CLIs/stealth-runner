# Agent-Toolbox API Dokumentation

## Überblick

Die Agent-Toolbox API bietet Endpunkte für Browser-Automation, Survey-Ausführung und Login-Automatisierung.

- **API Base URL**: `http://127.0.0.1:8889`
- **Swagger UI**: `http://127.0.0.1:8889/docs`
- **ReDoc**: `http://127.0.0.1:8889/redoc`

## Architektur

```
┌─────────────────────────────────────────────────────────────┐
│                    Chrome (CDP Port 8888)                     │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Profil 73 (kopiert nach /tmp/sinator-chrome-*)      │   │
│  │  ┌─────────────────────────────────────────────────┐  │   │
│  │  │  Playwright via connect_over_cdp()            │  │   │
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

Chrome wird mit der **SINator-Methode** gestartet:

1. **Profil kopieren**: `Local State` + `Profile 73` → `/tmp/sinator-chrome-{timestamp}`
2. **Chrome starten**: `subprocess.Popen` mit `--remote-debugging-port=8888`
3. **Playwright verbinden**: `connect_over_cdp("http://127.0.0.1:8888")`

**Wichtige Flags**:
- `--remote-debugging-port=8888` — CDP Endpoint
- `--remote-allow-origins=*` — WebSocket Origin (OHNE Quotes!)
- `--user-data-dir=/tmp/sinator-chrome-*` — Kopiertes Profil
- `--profile-directory=Profile 73` — Profil-Name

## API Endpunkte

### Browser Management

#### POST /browser/start
Chrome starten oder wiederverwenden.

**Request**:
```json
{
  "profile_name": "Profile 73",
  "headless": false,
  "cdp_port": 8888
}
```

**Response**:
```json
{
  "status": "success",
  "profile": "Profile 73",
  "headless": false,
  "cdp_port": 8888,
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
  "profile": "Profile 73",
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
  "cdp_port": 8888,
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
  "cdp_port": 8888,
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
  "cdp_port": 8888,
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
  "cdp_port": 8888,
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
  "cdp_port": 8888,
  "profile_name": "default"
}
```

#### POST /survey/run-one
Komplette Survey ausführen (Step-by-step Loop).

**Request**:
```json
{
  "survey_id": null,
  "cdp_port": 8888,
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
  "cdp_port": 8888,
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

### Cookie Management Endpoints

#### POST /cookies/extract
Cookies aus dem Browser extrahieren und speichern.

**Request**:
```json
{
  "domain_filter": "heypiggy",
  "save_to_file": true,
  "filename": "heypiggy-cookies.json"
}
```

**Response**:
```json
{
  "status": "success",
  "profile": "default",
  "cookies": [
    {
      "name": "PHPSESSID",
      "value": "...",
      "domain": "www.heypiggy.com",
      "path": "/",
      "expires": -1,
      "httpOnly": false,
      "secure": false,
      "sameSite": "Lax"
    }
  ],
  "count": 4,
  "stats": {
    "total": 4,
    "domains": {"www.heypiggy.com": 4},
    "http_only": 0,
    "secure": 0,
    "session_cookies": 1
  },
  "saved_to": "data/heypiggy-cookies.json",
  "execution_time": "0.27s"
}
```

#### POST /cookies/inject
Gespeicherte Cookies in den Browser injizieren.

**Request**:
```json
{
  "filename": "heypiggy-cookies.json",
  "verify_session": true
}
```

**Response**:
```json
{
  "status": "success",
  "injected_count": 4,
  "session_active": true,
  "execution_time": "0.15s"
}
```

#### POST /cookies/verify
HeyPiggy Session-Status prüfen.

**Response**:
```json
{
  "status": "success",
  "session_active": true,
  "url": "https://www.heypiggy.com/?page=dashboard"
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
  "message": "Chrome not reachable on port 8888"
}
```

## Port-Konfiguration

| Service | Port | Zweck |
|---------|------|-------|
| Chrome CDP | 8888 | Chrome DevTools Protocol |
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
  -d '{"profile_name": "Profile 73", "cdp_port": 8888}'

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
  -d '{"cdp_port": 8888, "max_pages": 20}'

# 6. Chrome stoppen
curl -X POST http://127.0.0.1:8889/browser/stop
```

## Technische Details

### BrowserManager (SINator-Style)

```python
from core.browser_manager import BrowserManager

# Chrome mit Profil 73 auf Port 8888
bm = BrowserManager(
    profile_name="Profile 73",
    cdp_port=8888,
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
    "http://127.0.0.1:8888/json"
).read())

# WebSocket URL für Dashboard
ws_url = next(
    p["webSocketDebuggerUrl"] 
    for p in pages 
    if "dashboard" in p.get("url", "").lower()
)
```

## Status

### Funktioniert ✅
- Chrome starten mit Profil 73 auf Port 8888
- Playwright via CDP verbinden (Port 8888)
- API Server auf Port 8889
- Navigate, Screenshot, Page Content
- Health Check mit CDP-Reachability
- **Dashboard Scan**: 12 Surveys gefunden, 2.07€ total rewards
- **Balance**: 2.23€ ausgelesen
- **Cookie Extract/Inject/Verify**: Session-Persistenz funktioniert
- **Workflow /workflow/run-best**: Session-Check → Scan → Beste Survey → Card-Click → Modal (5.7s)

### Blockiert ❌
- **Google Login**: Passkey/Shadow DOM nicht automatisierbar via CDP/Playwright
  - Google Login Seite zeigt "Passkey verwenden" oder "Passwort eingeben"
  - Buttons sind im geschützten Shadow DOM
  - Lösung: Manuelles Login im Chrome Fenster, dann API nutzen

### Workaround für Login
1. Chrome Fenster öffnet sich automatisch (headless: false)
2. Manuell auf "Anmelden" klicken
3. Google Account wählen
4. Passkey/Passwort eingeben
5. **POST /cookies/extract** — Cookies speichern (Session persistieren!)
6. Dann API Endpunkte nutzen: `/workflow/run-best`, `/survey/click-card`

## Workflow Beispiel

### Ein Call: Alles automatisch

```bash
# 1. Session prüfen, besten Survey finden, Card klicken
curl -s -X POST http://127.0.0.1:8889/workflow/run-best \
  -H "Content-Type: application/json" \
  -d '{"strategy": "efficiency", "max_reward_filter": 0.05}'
```

**Response**:
```json
{
  "status": "success",
  "session_active": true,
  "balance_eur": 2.23,
  "surveys_found": 12,
  "survey_selected": {
    "survey_id": "67006251",
    "reward_eur": 0.23,
    "duration_min": 2,
    "provider": "unknown",
    "title": ""
  },
  "card_clicked": true,
  "modal_buttons": ["Nächste", "Umfrage starten", "Schließen"],
  "message": "Session active. Found 12 surveys. Selected 0.23€/2min survey. Card clicked: True.",
  "elapsed_s": 5.70
}
```

### Schritt-für-Schritt (Low-Level)

```bash
# 1. Cookies prüfen
curl -s -X POST http://127.0.0.1:8889/cookies/verify | jq

# 2. Dashboard scannen
curl -s -X POST http://127.0.0.1:8889/dashboard/scan \
  -H "Content-Type: application/json" \
  -d '{"cdp_port": 8888}' | jq '.available_surveys[] | {id: .survey_id, reward: .reward_eur, duration: .duration_min}'

# 3. Survey Card klicken
curl -s -X POST http://127.0.0.1:8889/survey/click-card \
  -H "Content-Type: application/json" \
  -d '{"survey_id": "67006251", "cdp_port": 8888}' | jq

# 4. "Umfrage starten" klicken
curl -s -X POST http://127.0.0.1:8889/survey/click-button \
  -H "Content-Type: application/json" \
  -d '{"button_label": "umfrage starten", "cdp_port": 8888}' | jq
```

## Bekannte Probleme

1. **Google Login (Passkey)**: Shadow DOM Buttons nicht via CDP/JS automatisierbar. Manuelle Eingabe nötig. Workaround: Einmalig einloggen → Cookies extrahieren → Session persistiert.

2. **Port-Konflikt**: Chrome CDP und FastAPI dürfen nicht auf demselben Port laufen. Chrome: 8888, API: 8889.

3. **Profil-Kopie**: Chrome verschlüsselt Cookies mit dem Pfad als Key. Kopieren (nicht Symlink!) ist nötig.

4. **Titel-Extraktion**: Survey-Titel ist nicht perfekt (zeigt Reward-Präfixe). Reward und ID sind korrekt.

## Changelog

- **2026-05-08**: `/workflow/run-best` — Combined Session-Check + Scan + Select + Click (5.7s)
- **2026-05-08**: `/dashboard/scan` — 12 Surveys, 2.07€ total rewards
- **2026-05-08**: `/dashboard/balance` — 2.23€ Balance ausgelesen
- **2026-05-08**: `/cookies/extract`, `/cookies/inject`, `/cookies/verify` — Session-Persistenz
- **2026-05-08**: API auf Port 8889, Chrome CDP auf 8888
- **2026-05-08**: SINator-Style BrowserManager mit Profil-Kopie
- **2026-05-08**: `--remote-allow-origins=*` ohne Quotes (zsh glob fix)
- **2026-05-08**: Survey Actions mit CDP WebSocket + Origin Header
- **2026-05-08**: BrowserManager auto-connect zu bestehendem Chrome
- **2026-05-08**: Health Check mit CDP-Reachability Fallback
