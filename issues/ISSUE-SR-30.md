# ISSUE-SR-30: Dashboard Poller + Auto-Loop

| Feld | Wert |
|------|------|
| **ID** | SR-30 |
| **Priority** | 🔴 P0 — Critical |
| **Status** | 📋 TODO |
| **Created** | 2026-05-06 |
| **Labels** | `dashboard`, `automation`, `poller`, `loop` |
| **Plan** | `plan-sr-30-dashboard-poller.md` |

## Problem
Survey-IDs auf dem Dashboard ändern sich dynamisch. Aktuell muss manuell `document.querySelectorAll("[onclick*=clickSurvey]")` ausgeführt und dann per API (`get-survey-details.php`) jeder Survey gecheckt werden. Das ist langsam und verschwendet Zeit. Ein automatischer Poller würde:
1. Dashboard alle 30s neuladen/scannen
2. Neue Survey-IDs extrahieren
3. Per API prüfen ob `type:okay`, `type:question`, `type:not_okay`
4. Nicht lohnende Provider (PureSpectrum, surveyrouter) rausfiltern
5. `type:okay` Surveys der Reihe nach an `run_survey()` übergeben

## Subissues

### SR-30.1 — ID Extractor
- [ ] `extract_survey_ids(dashboard_ws_url)` → List[str]
- [ ] CDP: `document.querySelectorAll("[onclick*=clickSurvey]")` → regex IDs
- [ ] Deduplication (IDs ändern sich, aber nicht bei jedem Scan)
- [ ] Cache: `~/.stealth/survey_ids_cache.json`

### SR-30.2 — API Pre-Filter
- [ ] `check_survey_type(survey_id)` → "okay" | "question" | "not_okay"
- [ ] POST an `details_url + &survey_id={id}`
- [ ] Antwort parsen: `data.get('type')`
- [ ] `href` speichern für "okay" surveys
- [ ] `not_okay` sofort verwerfen

### SR-30.3 — Provider Router Filter
- [ ] Nach API-Call: `href` auf bekannte blockierte Provider prüfen
- [ ] Blockiert: `purespectrum.com`, `surveyrouter.com`
- [ ] Skip-Liste: `~/.stealth/skip_providers.json`
- [ ] Optional: GfK `surveys.com` cookie-wall → auch skippen?

### SR-30.4 — Auto-Loop Engine
- [ ] `DashboardPoller` Klasse mit `poll_interval=30`
- [ ] Queue: priorisierte Survey-Liste
- [ ] `run_loop()` → poll → filter → `run_survey(id)` → poll → repeat
- [ ] Stopp-Kriterien: `max_surveys=10`, `balance_target=5.00`, `time_limit=3600`
- [ ] Error-Recovery: Survey-Fehler → nächster Survey

### SR-30.5 — Balance Tracker
- [ ] `read_balance(dashboard_ws)` → float
- [ ] Vor/Nach jedem Survey: Balance delta = earned
- [ ] Log: `~/.stealth/earnings_2026-05-06.jsonl`
- [ ] Console output: "💰 Earned +0.38€ | Balance: 2.53€"

## Acceptance Criteria
- [ ] Dashboard scan findet alle Survey-IDs (< 2s)
- [ ] API-Filter entfernt `not_okay` surveys
- [ ] Provider-Filter skip PureSpectrum + surveyrouter
- [ ] Loop läuft autonom für 10+ Surveys
- [ ] Balance wird korrekt getrackt

## Betroffene Files
- `cli/modules/dashboard_watcher.py` → NEU
- `cli/modules/survey_cdp.py` → Integration mit `run_survey()`
- `~/.stealth/survey_ids_cache.json` → NEU
- `~/.stealth/earnings_*.jsonl` → NEU
