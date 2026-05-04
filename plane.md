# plane.md — Plane.so API Nutzung (2026-05-04)

> **Plane** = Open-Source Projektmanagement-Tool. Self-Hosted oder Cloud.
> **Stealth-Runner** nutzt Plane als Wissensdatenbank / Issue-Tracking / Chat-Logs.
> **API-Key**: `plane_api_a73428aaf90b4f90a09caa73f7dd607c` (→ `.env` + Infisical)

---

## 1. BASIS-KONFIGURATION

### Workspace
```
Slug:      opensin-ai
Base URL:  https://api.plane.so/api/v1/workspaces/opensin-ai
Dashboard: https://app.plane.so/opensin-ai
Region:    Cloud (api.plane.so)
```

### Authentifizierung
```bash
# Via API-Key (Header)
curl -H "X-API-Key: $PLANE_API_KEY" "https://api.plane.so/api/v1/workspaces/opensin-ai/pages/"

# Via OAuth Bearer Token
curl -H "Authorization: Bearer $TOKEN" "https://api.plane.so/api/v1/workspaces/opensin-ai/pages/"
```

### Python SDK
```bash
pip install plane-sdk
```
```python
from plane.client import PlaneClient

client = PlaneClient(
    base_url="https://api.plane.so",
    api_key="plane_api_a73428aaf90b4f90a09caa73f7dd607c"
)

# Workspace Pages
pages = client.pages.list("opensin-ai")
for p in pages.results:
    print(f"{p.id}: {p.name}")
```

---

## 2. WIKI-SEITEN (Pages)

### 2.1 Alle Wiki-Seiten auflisten
```bash
curl -s "https://api.plane.so/api/v1/workspaces/opensin-ai/pages/?per_page=100" \
  -H "X-API-Key: $PLANE_API_KEY"
```

**Antwort:**
```json
{
  "results": [
    {"id": "256966ad-...", "name": "chat verlauf mit agent 2"},
    {"id": "3ded2380-...", "name": "Dateien"},
    {"id": "0ff16687-...", "name": "stealth-runner"},
    ...
  ]
}
```

**Alle 14 Pages im Workspace:**
| ID | Name | Typ |
|----|------|-----|
| `256966ad-01d0-40df-a4d4-c60931c9b294` | chat verlauf mit agent 2 | ✅ Content |
| `3ded2380-f453-4a9e-a1c3-90ac36943a80` | Dateien | ⚠️ leer |
| `0ff16687-f496-4e3d-8a24-e9e8a6ab4587` | stealth-runner | ✅ |
| `5cc9cda9-a6f0-4ac5-b86b-99e2fdc6d0ea` | *(unbenannt)* | ✅ |
| `95513f05-abb8-4038-81e0-93f49121ac7c` | Agents in opencode & oh-my-opencode | ✅ |
| `2b1b7414-809a-4b84-9c27-12a4f678e7cd` | *(unbenannt)* | ✅ |
| `9e5d280b-1fef-4a58-9e84-45054b7ab9a9` | Warum SIN besser ist... | ✅ |
| `591d4caf-79bf-4c57-9a24-4f0cd9634a87` | Fortschrittliche Architekturen... | ✅ |
| `eed1a51b-b30c-45d7-aa37-ee50e5e1eafc` | HuggingFace | ✅ |
| `d548ec17-692a-4191-adca-63501d46807c` | Fireworks AI | ✅ |
| `10c06336-b7f8-4231-9f62-ebf1859a29a9` | Free AI | ✅ |
| `f949ff19-c390-48c5-9c7e-dc25ec50c4e2` | 🔥 Das echte Ziel... | ✅ |
| `9e43d149-987b-4ce0-8b50-4d231f7dd8a8` | Prompt Library | ✅ |
| `a6c48f47-65d4-400f-9daf-17e34fb7a1c0` | Welcome to Company's Wiki | ✅ |

### 2.2 Einzelne Seite lesen (mit Content)
```bash
PAGE_ID="256966ad-01d0-40df-a4d4-c60931c9b294"
curl -s "https://api.plane.so/api/v1/workspaces/opensin-ai/pages/$PAGE_ID/" \
  -H "X-API-Key: $PLANE_API_KEY"
```

**Wichtige Felder:**
| Feld | Typ | Beschreibung |
|------|-----|-------------|
| `id` | UUID | Eindeutige Seiten-ID |
| `name` | string | Seitentitel |
| `description_html` | string | **Voller Content (HTML!)** |
| `owned_by` | UUID | Ersteller |
| `access` | int | 0=public, 1=private |
| `is_locked` | bool | Gesperrt? |
| `created_at` | timestamp | Erstellungsdatum |
| `updated_at` | timestamp | Letzte Änderung |

### 2.3 Seite erstellen
```bash
curl -X POST "https://api.plane.so/api/v1/workspaces/opensin-ai/projects/{project_id}/pages/" \
  -H "X-API-Key: $PLANE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Meine neue Seite",
    "description_html": "<h1>Titel</h1><p>Inhalt...</p>",
    "access": 0
  }'
```

### 2.4 Seite aktualisieren (PATCH — je nach Host)
```bash
curl -X PATCH "https://api.plane.so/api/v1/workspaces/opensin-ai/pages/$PAGE_ID/" \
  -H "X-API-Key: $PLANE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "Neuer Titel", "description_html": "<p>Neuer Content</p>"}'
```

---

## 3. PROJEKTE (Workspace)

### 3.1 Alle Projekte auflisten
```bash
curl -s "https://api.plane.so/api/v1/workspaces/opensin-ai/projects/" \
  -H "X-API-Key: $PLANE_API_KEY"
```

**8 Projekte im Workspace:**
| ID | Name |
|----|------|
| `55441915-4458-4980-9d36-3b88e711203a` | OpenSIN-AI/SIN-Rotator |
| `f0b9ddb7-d58b-4c28-a50b-9573defb9a69` | OpenSIN AI |
| `7563951b-9fc4-49b0-bfac-dd95e47a04c6` | Infra-OpenCode-Stack |
| `ade59eea-4d7d-4618-8ae8-b6dafad83c98` | OpenSIN-/SIN-CLIs |
| `4c175e61-0d4a-4726-9f94-88162ecae38f` | OpenSIN-AI/SIN-Skills |
| `9ccfdbdd-5c94-4bb1-a379-7899599de234` | OpenSIN-AI/Agents |
| `38301c3e-bc09-478e-a94d-2a4e64de7a12` | GPT-5.5 in OpenCode integrieren |
| `d2d29331-b9f3-45f1-a5d0-6e4eb372f647` | OpenSIN - Design |

### 3.2 Project-Pages (pro Projekt)
```bash
curl -s "https://api.plane.so/api/v1/workspaces/opensin-ai/projects/f0b9ddb7-d58b-4c28-a50b-9573defb9a69/pages/" \
  -H "X-API-Key: $PLANE_API_KEY"
```

**Aktuelle Project-Pages:**
| Projekt | Pages |
|---------|-------|
| OpenSIN AI | 1 (Project Design Spec) |
| GPT-5.5 Integration | 2 (Overview: GPT-5.5) |

---

## 4. WORK ITEMS (Issues)

### 4.1 Alle Work Items in einem Projekt
```bash
curl -s "https://api.plane.so/api/v1/workspaces/opensin-ai/projects/{project_id}/work-items/" \
  -H "X-API-Key: $PLANE_API_KEY"
```

### 4.2 Work Item erstellen
```bash
curl -X POST "https://api.plane.so/api/v1/workspaces/opensin-ai/projects/{project_id}/work-items/" \
  -H "X-API-Key: $PLANE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Task Name",
    "description": "Beschreibung",
    "priority": "medium",
    "state": "{state_uuid}",
    "assignees": ["{user_uuid}"],
    "labels": ["{label_uuid}"]
  }'
```

### 4.3 Work Item aktualisieren
```bash
curl -X PATCH "https://api.plane.so/api/v1/workspaces/opensin-ai/projects/{project_id}/work-items/{item_id}/" \
  -H "X-API-Key: $PLANE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Neuer Name",
    "description": "Neue Beschreibung",
    "priority": "high",
    "state": "{new_state_uuid}"
  }'
```

### 4.4 Work Item löschen
```bash
curl -X DELETE "https://api.plane.so/api/v1/workspaces/opensin-ai/projects/{project_id}/work-items/{item_id}/" \
  -H "X-API-Key: $PLANE_API_KEY"
```

### 4.5 Seite mit Work Item verknüpfen
```bash
curl -X POST "https://api.plane.so/api/v1/workspaces/opensin-ai/projects/{project_id}/work-items/{item_id}/pages/" \
  -H "X-API-Key: $PLANE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"page_id": "{page_uuid}"}'
```

---

## 5. MODULE & CYCLES

### 5.1 Modul erstellen
```bash
curl -X POST "https://api.plane.so/api/v1/workspaces/opensin-ai/projects/{project_id}/modules/" \
  -H "X-API-Key: $PLANE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Sprint 1",
    "description": "Erster Sprint",
    "start_date": "2026-05-01",
    "target_date": "2026-05-15",
    "status": "in-progress"
  }'
```

### 5.2 Work Items zu Modul hinzufügen
```bash
curl -X POST "https://api.plane.so/api/v1/workspaces/opensin-ai/projects/{project_id}/modules/{module_id}/module-issues/" \
  -H "X-API-Key: $PLANE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"issues": ["{work_item_id_1}", "{work_item_id_2}"]}'
```

---

## 6. API-LIMITS & BESONDERHEITEN

| Feature | Status | Anmerkung |
|---------|--------|-----------|
| **Pages lesen** | ✅ Vollständig | description_html = Content |
| **Pages listen** | ✅ | Workspace + Project-level |
| **Pages erstellen** | ✅ | name + description_html |
| **Pages aktualisieren** | ⚠️ | PATCH — je nach Host-Version |
| **Pages löschen** | ⚠️ | Nicht auf allen Hosts |
| **Work Items CRUD** | ✅ | Volles Create/Read/Update/Delete |
| **Module** | ✅ | Inkl. Zuweisung von Work Items |
| **Cycles** | ✅ | Inkl. Zuweisung von Work Items |
| **Python SDK** | ✅ | `pip install plane-sdk` |

---

## 7. INFISICAL INTEGRATION

```bash
# Key aus Infisical holen
export PLANE_API_KEY=$(infisical secrets get PLANE_API_KEY --plain)

# Key in .env
echo "PLANE_API_KEY=plane_api_a73..." >> .env

# Infisical Konfiguration
# Organization: OpenSIN AI
# Project:      My-OpenSIN-Secrets
# Region:       EU (eu.infisical.com)
```

---

## 8. PRAKTISCHE BEISPIELE

### Chat-Log von Agent 2 lesen
```python
import requests, re

KEY = "plane_api_a73428aaf90b4f90a09caa73f7dd607c"
BASE = "https://api.plane.so/api/v1/workspaces/opensin-ai"

resp = requests.get(f"{BASE}/pages/256966ad-01d0-40df-a4d4-c60931c9b294/",
    headers={"X-API-Key": KEY})
data = resp.json()
html = data["description_html"]
# HTML-Tags entfernen
text = re.sub(r'<[^>]+>', '', html)
print(text)
```

### Neue Wiki-Seite erstellen
```python
import requests

KEY = "plane_api_a73428aaf90b4f90a09caa73f7dd607c"
BASE = "https://api.plane.so/api/v1/workspaces/opensin-ai"

resp = requests.post(f"{BASE}/projects/{project_id}/pages/",
    headers={"X-API-Key": KEY, "Content-Type": "application/json"},
    json={
        "name": "Mein neuer Eintrag",
        "description_html": "<p>Inhalt der Seite...</p>",
        "access": 0  # public
    })
print(resp.json())
```

### Work Item erstellen + Seite verknüpfen
```python
import requests

KEY = "plane_api_a73428aaf90b4f90a09caa73f7dd607c"
BASE = "https://api.plane.so/api/v1/workspaces/opensin-ai"

# Work Item erstellen
wi = requests.post(f"{BASE}/projects/{project_id}/work-items/",
    headers={"X-API-Key": KEY},
    json={"name": "Dokumentation schreiben", "priority": "medium"}).json()

# Mit Seite verknüpfen
requests.post(f"{BASE}/projects/{project_id}/work-items/{wi['id']}/pages/",
    headers={"X-API-Key": KEY},
    json={"page_id": "{page_uuid}"})
```
