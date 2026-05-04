# PLAN: Survey Runner Completion — Multi-Survey + Balance + Provider Intelligence

> **Quelle:** issues.md, survey_runner.py (972 Zeilen), agent research  
> **Abhängigkeiten:** audio-capture (SR-15), captcha-integration (SR-16)  
> **Priorität:** 🔴 KRITISCH  
> **Aufwand:** Groß

---

## 🔍 Recherche-Ergebnisse (Codebase Scan)

**Aktueller Stand survey_runner.py (972 Zeilen):**
- ✅ Phase 1: `scan_surveys()` — verfügbare Surveys erkennen + nach Auszahlung sortieren
- ✅ Phase 2: `prequalify()` — Vorqualifizierung mit Vision-Gate
- ✅ Phase 3: `complete_survey()` — Survey in neuem Tab verarbeiten
- ✅ Phase 4: `run()` — kompletter Ablauf (scan → start → qualify → complete → review)
- ✅ Audio-Detektion + Handling (`_detect_audio_question`, `_handle_audio_question`)
- ✅ Persona-basierte Antwortlogik (`_persona_antwort`)
- ✅ Balance-Check (`check_balance`)
- ✅ Captcha-Integration (Zeilen 581-596)
- ✅ Review-Feld-Handling (`handle_review`)

**Fehlt:**
- ❌ `survey_queue.py` existiert ABER ist NICHT in `survey_runner.run()` integriert
- ❌ Keine parallele Survey-Ausführung (nur sequentiell)
- ❌ Balance-Change-Tracking (kein VORHER/NACHHER-Vergleich)
- ❌ Keine Provider-Intelligence (kein Tracking pro Provider)

---

## 🎯 Ziel

`survey_runner.py` von sequentieller Einzel-Survey-Verarbeitung auf eine vollständige Multi-Survey-Automation umstellen mit Queue, Parallelisierung, Balance-Tracking und Provider-Intelligence.

## 📋 Sub-Projekte

### A. Multi-Survey Queue Integration 🟡 HOCH

**Aktuell:** `survey_runner.run()` verarbeitet Surveys in einer einfachen for-Schleife.  
`survey_queue.py` existiert aber wird nicht genutzt.

**Sub-Tasks:**
- [ ] `survey_queue.py` in `survey_runner.run()` integrieren
- [ ] Queue-basierte Aufgabenverteilung (Claim → Process → Done/Fail)
- [ ] Priorisierung nach Auszahlung (höchste zuerst)
- [ ] Failed-Task Recovery nach 24h
- [ ] Queue-Status-Logging

### B. Parallel Survey Execution 🟡 HOCH

**Aktuell:** Nur sequentiell, ein Survey nach dem anderen.

**Sub-Tasks:**
- [ ] `concurrent.futures.ThreadPoolExecutor` für parallele Surveys
- [ ] Chrome-Instanz-Isolation pro Survey (eigene PID)
- [ ] Resource Monitoring (max N parallele Surveys)
- [ ] Error Isolation (ein fehlgeschlagener Survey killt nicht alle)

### C. Balance Verification Automation 🟢 MITTEL

**Aktuell:** `check_balance()` prüft ob Balance-Element existiert, aber kein Change-Tracking.

**Sub-Tasks:**
- [ ] Balance VOR Survey speichern
- [ ] Balance NACH Survey speichern
- [ ] Differenz = Verdienst
- [ ] EUR/h Metrik berechnen
- [ ] Earning-History persistieren (`~/.stealth-runner/earnings.json`)

### D. Survey Provider Intelligence 🔵 NIEDRIG

**Aktuell:** Keine Tracking-Daten pro Provider.

**Sub-Tasks:**
- [ ] Provider (Samplicio.us, Cint, Nfield) Erfolgsrate tracken
- [ ] Provider-spezifische Optimierungen
- [ ] Auto-Skip von Problem-Providern
- [ ] Historical Data in `~/.stealth-runner/provider_stats.json`

## 🏗️ Implementation

```python
# Neue Struktur in survey_runner.py
def run(self, max_concurrent=2, max_per_session=10):
    """Multi-Survey mit Queue + Parallelisierung."""
    queue = SurveyQueue(self.pid)
    with ThreadPoolExecutor(max_workers=max_concurrent) as pool:
        futures = []
        for _ in range(max_per_session):
            task = queue.claim()
            if not task:
                break
            future = pool.submit(self._process_survey, task)
            futures.append(future)
        for future in as_completed(futures):
            result = future.result()
            if result.get("earned"):
                self._log_earnings(result["earned"])
```

## 📂 Verwandte Dateien

| Datei | Rolle |
|-------|-------|
| `cli/modules/survey_runner.py` | Hauptdatei (972 Zeilen) |
| `runner/survey_queue.py` | Queue-System (existiert, nicht integriert) |
| `runner/flow_optimizer.py` | Flow-Promotion-System |
| `cli/modules/dashboard_verify.py` | Balance-Prüfung |

## 🔗 Issue

[ISSUE-SR-14: Survey Runner Completion](../issues/ISSUE-SR-14.md)
