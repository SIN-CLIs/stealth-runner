# Issue #6: NIM Runtime Failures — Keine Fallback-Strategie bei NIM-Ausfall (P0)

> **Status**: OPEN
> **Severity**: 🔴 P0 — NIM-Ausfall = 0 Surveys (wenn use_nim=True)
> **Reporter**: SIN-Agent Automated Analysis (2026-05-08)
> **Betroffene Dateien**: `src/stealth_survey/survey_agent.py`, `src/stealth_survey/nim_client.py`

---

## Problem-Beschreibung

Wenn NVIDIA NIM nicht erreichbar ist (API Key expired, Rate Limit, Netzwerk-Fehler), schlägt der Survey-Loop komplett fehl:

```python
# survey_agent.py:672
if self.nim and self.config.use_nim:
    decision = self.nim.decide(...)  # ❌ Exception hier → Survey abgebrochen!
```

**Impact**: 
- NIM API Key expired → ALLE Surveys fehlgeschlagen
- Rate Limit erreicht → ALLE Surveys fehlgeschlagen
- Netzwerk-Fehler → ALLE Surveys fehlgeschlagen

---

## Root-Cause-Analyse

### Ursache 1: Kein Timeout-Handling
`NIMSurveyClient.decide()` hat kein explizites Timeout-Handling:
```python
# nim_client.py — kein try/except für Netzwerk-Fehler!
response = urllib.request.urlopen(req, timeout=30)
# Wenn timeout=30 erreicht → urllib.error.URLError → Exception!
# → Exception propagiert zu SurveyAgent → Survey abgebrochen
```

### Ursache 2: Kein Fallback zu Auto-Pilot
Wenn NIM fehlschlägt, sollte Auto-Pilot übernehmen. Aktuell tut es das NICHT:
```python
if self.nim and self.config.use_nim:
    decision = self.nim.decide(...)  # Exception → KEIN Fallback!
else:
    actions = self._simple_actions(snapshot)  # ❌ Nur wenn NIM nicht konfiguriert
```

### Ursache 3: Kein Retry mit Backoff
NIM-Ausfälle sind oft temporär (Rate Limit, kurze Netzwerk-Störung). Ein Retry mit Exponential Backoff würde viele Fehler automatisch beheben.

---

## Ziel

NIM-Ausfall = Auto-Pilot Fallback + Retry + Logging. Kein Survey wird wegen NIM-Fehler abgebrochen.

---

## Akzeptanzkriterien

- [ ] `NIMSurveyClient.decide()` hat try/except mit Timeout, Rate-Limit, und Netzwerk-Fehler
- [ ] `SurveyAgent.run_survey()` fällt auf `_simple_actions()` zurück wenn NIM 3× fehlschlägt
- [ ] Exponential Backoff bei NIM-Retries (1s, 2s, 4s, max 10s)
- [ ] Jeder NIM-Fehler wird geloggt (event_type="nim_error")
- [ ] `nim.available` Property wird aktualisiert (False nach 3 Fehlern)
- [ ] Auto-Recovery: Nach 5 Minuten wird `nim.available` wieder auf True gesetzt (erneuter Versuch)

---

## Implementierungs-Plan

### 1. NIMClient mit Fehler-Handling

```python
class NIMSurveyClient:
    def __init__(self, ...):
        self.consecutive_failures = 0
        self.last_failure_time = 0.0
        self._available = True

    @property
    def available(self) -> bool:
        """NIM verfügbar? Auto-Recovery nach 5min."""
        if self._available:
            return True
        if time.time() - self.last_failure_time > 300:
            self._available = True  # Auto-Recovery
            self.consecutive_failures = 0
        return self._available

    def decide(self, snapshot, profile, learnings, history,
               temperature=0.1, max_retries=3) -> dict:
        """
        NIM Decision mit Retry + Fallback.

        Retry-Strategie:
          1. Erster Versuch: 30s Timeout
          2. Bei Fehler: Exponential Backoff (1s, 2s, 4s)
          3. Max 3 Retries
          4. Nach 3 Fehlern: self.available = False, Fallback

        Error-Types:
          - URLError: Netzwerk nicht erreichbar → Retry
          - HTTPError 401: API Key invalid → KEIN Retry (permanent)
          - HTTPError 429: Rate Limit → Retry mit Backoff
          - HTTPError 5xx: Server Error → Retry
          - Timeout: Retry
        """
        for attempt in range(max_retries):
            try:
                response = urllib.request.urlopen(req, timeout=30)
                # Success → Reset failures
                self.consecutive_failures = 0
                return self._parse_response(response)
            except urllib.error.HTTPError as e:
                if e.code == 401:
                    # API Key invalid — KEIN Retry
                    log_error("nim_auth_failed", {"code": 401})
                    self._available = False
                    self.last_failure_time = time.time()
                    raise FatalError("NIM API Key invalid")
                elif e.code == 429:
                    # Rate Limit — Retry mit Backoff
                    wait = min(10, 2 ** attempt)
                    log_warn("nim_rate_limit", {"attempt": attempt, "wait": wait})
                    time.sleep(wait)
                    continue
                else:
                    # Other HTTP errors — Retry
                    time.sleep(2 ** attempt)
                    continue
            except urllib.error.URLError as e:
                log_error("nim_network_error", {"attempt": attempt})
                time.sleep(2 ** attempt)
                continue
            except Exception as e:
                log_error("nim_unexpected_error", {"error": str(e)})
                time.sleep(2 ** attempt)
                continue

        # All retries exhausted
        self.consecutive_failures += 1
        self.last_failure_time = time.time()
        if self.consecutive_failures >= 3:
            self._available = False

        # Fallback: empty actions → auto-pilot übernimmt
        return {"actions": [], "fallback": True, "reason": "nim_unavailable"}
```

### 2. SurveyAgent mit Fallback

```python
# survey_agent.py — run_survey() Loop
if self.nim and self.nim.available and self.config.use_nim:
    try:
        decision = self.nim.decide(...)
        if decision.get("fallback"):
            # NIM gab Fallback zurück → Auto-Pilot
            actions = self._simple_actions(snapshot)
        else:
            actions = decision.get("actions", [])
    except FatalError:
        # NIM permanent unavailable → Auto-Pilot
        actions = self._simple_actions(snapshot)
else:
    # NIM nicht konfiguriert → Auto-Pilot
    actions = self._simple_actions(snapshot)
```

---

## Dateien

- **Ändern**: `src/stealth_survey/nim_client.py` → Retry + Fehler-Handling
- **Ändern**: `src/stealth_survey/survey_agent.py` → Fallback zu Auto-Pilot
- **Neu**: `src/stealth_survey/nim_client_test.py` → Tests für Fehlerfälle
- **Update**: `learn.md` → NIM-Fehler dokumentieren

---

*Erstellt: 2026-05-08*