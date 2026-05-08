# 🤖 Agent-Toolbox

High-Performance Automation API for Browser, Login, and Survey Tasks.

## 🚀 Quick Start

```bash
# 1. Install dependencies
pip install -r agent-toolbox/requirements.txt

# 2. Copy and fill .env
cp agent-toolbox/.env.example .env
# Edit .env with your secrets

# 3. Start the API
python start_toolbox.py
```

The API will be available at:
- **API Base**: http://localhost:8000
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 🏗 Architecture

```text
agent-toolbox/
├── core/
│   └── browser_manager.py    # Warm Browser Singleton (Playwright)
├── api/
│   ├── main.py               # FastAPI app with endpoints
│   └── schemas.py            # Pydantic request/response models
├── profiles/                 # Persistent browser profiles
├── .env.example              # Configuration template
├── requirements.txt          # Dependencies
└── README.md                 # This file
```

## 📡 Endpoints

### Browser Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/browser/start` | Start/reuse browser with profile |
| POST | `/browser/stop` | Stop browser gracefully |
| GET | `/browser/health` | Check browser status |

### Services

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/services/heypiggy/login` | Login to HeyPiggy via Google OAuth |

### Surveys

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/survey/run-one` | Run one survey (demo/proof-of-concept) |

### Tools

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/tools/extract-cookies` | Extract cookies from session |
| POST | `/tools/navigate` | Navigate browser to URL |
| POST | `/tools/screenshot` | Take screenshot (full page or element) |
| POST | `/tools/page-content` | Extract page text and HTML |

## 🔧 Agent Usage

An agent can discover and use the API automatically via the OpenAPI schema:

```python
import httpx

# 1. Start browser (warm start)
r = httpx.post("http://localhost:8000/browser/start",
               json={"profile_name": "default", "headless": true})
print(r.json())
# {"status": "success", "profile": "default", "headless": true, ...}

# 2. Login to HeyPiggy
r = httpx.post("http://localhost:8000/services/heypiggy/login",
               json={"profile_name": "default"})
print(r.json())
# {"status": "success", "service": "heypiggy", ...}

# 3. Run one survey (demo/proof-of-concept)
r = httpx.post("http://localhost:8000/survey/run-one",
               json={"profile_name": "default", "cdp_port": 9999, "max_pages": 20})
print(r.json())
# {"status": "completed", "pages_completed": 5, "elapsed_s": 45.2, ...}

# 4. Navigate and screenshot
r = httpx.post("http://localhost:8000/tools/navigate",
               json={"profile_name": "default", "url": "https://example.com"})
print(r.json())
# {"status": "success", "url": "https://example.com", "title": "Example Domain"}

r = httpx.post("http://localhost:8000/tools/screenshot",
               json={"profile_name": "default", "full_page": true})
print(r.json())
# {"status": "success", "base64_image": "iVBORw0KGgo..."}

# 5. Extract cookies
r = httpx.post("http://localhost:8000/tools/extract-cookies",
               json={"profile_name": "default"})
print(r.json())
# {"status": "success", "count": 42, "cookies": [...]}

# 6. Stop browser
r = httpx.post("http://localhost:8000/browser/stop")
print(r.json())
# {"status": "success", "message": "Browser stopped"}
```

## ⚡ Speed Optimization

- **Warm Starts**: The `BrowserManager` singleton keeps the browser alive between calls.
- **Persistent Profiles**: Cookies and logins survive across sessions.
- **Headless Default**: No GUI overhead unless explicitly disabled.

## 🔒 Security

- **Isolated Profiles**: Each profile uses a separate browser data directory.
- **No Hardcoded Secrets**: All credentials via `.env` file (never commit!).
- **CDP Port**: Configurable, defaults to 9999.

## 🛠 Extending

To add a new service endpoint:

1. Add schema in `api/schemas.py`
2. Add endpoint in `api/main.py`
3. Import and wrap existing logic from `cli/modules/`

Example:
```python
@app.post("/services/new-provider/login", response_model=LoginResponse)
async def new_provider_login(req: LoginRequest):
    # Wrap existing provider login logic
    ...
```

## 📚 OpenAPI Schema

The full OpenAPI schema is available at:
```
http://localhost:8000/openapi.json
```

This can be consumed by any agent to discover available endpoints dynamically.

## 🧪 Testing

```bash
# Run all API tests
pytest agent-toolbox/tests/

# Run with survey-cli tests
pytest agent-toolbox/tests survey-cli/tests

# Test locally
curl -X POST http://localhost:8000/browser/start \
  -H "Content-Type: application/json" \
  -d '{"profile_name": "test"}'
```

## 📊 Test Status

**640 passing, 6 skipped**

- `agent-toolbox/tests/` — 12 API endpoint tests
- `survey-cli/tests/` — 628 survey and auth tests

## 📄 License

Part of the stealth-runner project.
