# Issue 008: Endpoint-Architektur — Individuelle Endpoints vs. Monolith

> **Status**: ✅ VERIFIZIERT  
> **Datum**: 2026-05-08  
> **Priorität**: CRITICAL — Monolith verboten per AGENTS.md

---

## Das Problem

Der monolithische Endpoint `POST /workflow/run-best` versucht ALLES in einer Funktion:
- Dashboard scannen
- Survey auswählen
- Klicken
- Fragen beantworten
- Bewerten

**Das ist verboten per AGENTS.md §Goldene Regel:**
> "Monolithische Endpoints wie POST /survey/run-one die ALLES in einer Funktion machen — UNDEBUGGABLE"

---

## Die Lösung (Implementiert)

### Moderne Endpoints (survey_tools.py)

```python
# survey_tools.py — Jeder Endpoint macht EINE SACHE

POST /survey/open   → Survey öffnen (click-card + "Umfrage starten")
POST /survey/fill   → Fragen beantworten (pro Seite Batch)
POST /survey/rate   → Bewertung abgeben
POST /survey/close  → Tab schließen
```

### Legacy Endpoints (survey_actions.py — DEPRECATED)

```python
# survey_actions.py — Alte Endpoints, noch für Kompatibilität

POST /survey/click-card    → Survey-Karte klicken
GET  /survey/modal         → Modal-Inhalt lesen
POST /survey/click-button  → Button klicken
POST /survey/select-option → Radio/Checkbox auswählen
POST /survey/fill-text     → Text eingeben
POST /survey/run-one       → Kompletter Loop (DEPRECATED)
```

---

## Warum getrennte Endpoints?

| Kriterium | Monolith (/workflow/run-best) | Individuelle Endpoints |
|-----------|--------------------------------|------------------------|
| **Debug** | Unmöglich — wo ist der Fehler? | Jeder Schritt isoliert testbar |
| **Wiederverwendung** | Nicht möglich | /survey/fill kann allein genutzt werden |
| **Fehlerbehandlung** | Alles oder nichts | Einzelne Schritte retry-bar |
| **Token-Effizienz** | 5000+ Tokens pro Call | ~500 Tokens pro Seite |
| **Tests** | Ein riesiger Test | Viele kleine, gezielte Tests |

---

## Implementierungs-Details

### survey_tools.py (MODERN)

```python
# Router: prefix="/survey", tags=["survey-tools"]
router = APIRouter(prefix="/survey", tags=["survey-tools"])

@router.post("/open", response_model=OpenSurveyResponse)
async def open_survey(req: OpenSurveyRequest):
    """Survey öffnen — click-card + "Umfrage starten" + Tab finden"""
    ...

@router.post("/fill", response_model=FillSurveyResponse)
async def fill_survey(req: FillSurveyRequest):
    """Fragen beantworten — Compact Snapshot → NIM Decision → Batch Execute"""
    ...

@router.post("/rate", response_model=RateSurveyResponse)
async def rate_survey(req: RateSurveyRequest):
    """Bewertung abgeben"""
    ...
```

### Registrierung in main.py

```python
from api.survey_tools import router as survey_tools_router

app.include_router(survey_tools_router)  # MODERN
app.include_router(survey_router)          # LEGACY (deprecated)
```

---

## NEMO Loop (pro Seite)

```
while survey_active:
    1. Compact Snapshot (skylight-cli / CDP) → ~200 tokens
    2. Nemotron Decision (NVIDIA NIM) → ~100 tokens
    3. Batch Execute (CDP WebSocket) → 1 WebSocket call
    4. Memory + Guardian → log_step()
```

**Vorteil**: 1 LLM-Call PRO SEITE statt pro Element
→ 10× schneller, 90% Token-Ersparnis

---

## Was gelöscht wurde (und wiederhergestellt werden muss)

Die `git checkout --` Katastrophe hat `survey_tools.py` Router-Registrierung in `main.py` gelöscht.

### Fix (bereits appliziert):
```python
# main.py Zeile ~235
from api.survey_tools import router as survey_tools_router

# main.py Zeile ~510
app.include_router(survey_tools_router)
```

---

## Tests

- `test_api.py` — 9 Tests für survey_tools Endpoints
- `test_run_survey.py` — 55 Tests für kompletten Flow
- `test_opener.py` — 8 Tests für Tab-Öffnung

**Alle Tests müssen passen bevor merged wird!**

---

## Banned

- `POST /workflow/run-best` — MONOLITH, nicht mehr verwenden
- `POST /survey/run-one` — DEPRECATED, verwende /survey/open + /fill

---

## Session-Referenz

- Session: `ses_1fb699b0effeULfoLPQHb1rBpi`
- Teil: `prt_e0a8f9d1e001mP63VtZfwZTgYK`
- "SCHWERWIEGENDER FEHLER. `git checkout` hat survey_actions.py, main.py, schemas.py ALLE Änderungen verworfen"
