# ISSUE-SR-32: Provider Auto-Detect Engine

| Feld | Wert |
|------|------|
| **ID** | SR-32 |
| **Priority** | 🟠 P1 — High |
| **Status** | 📋 TODO |
| **Created** | 2026-05-06 |
| **Labels** | `detection`, `routing`, `provider` |
| **Plan** | `plan-sr-32-provider-detect.md` |

## Problem
Wenn ein Survey via `Target.createTarget` geöffnet wird, redirected er durch mehrere URLs:
```
click.cpx-research.com → eu.qualtrics.com  ODER
click.cpx-research.com → screener.purespectrum.com  ODER
click.cpx-research.com → survey.tolunastart.com  ODER
click.cpx-research.com → *.cint.com  ODER
click.cpx-research.com → *.strat7audiences.com  ODER
...
```
Aktuell wird der Provider MANUELL erkannt (durch Blick auf die URL). Das Auto-Detect-Modul soll nach dem Redirect automatisch erkennen, welcher Provider geladen wurde und das richtige Pattern aus `provider_patterns.py` aktivieren.

## Subissues

### SR-32.1 — URL-Based Detection
- [ ] `detect_by_url(tab_url)` → provider_name
- [ ] URL-Pattern-Tabelle aus allen bekannten Providern
- [ ] Prioritized matching: exact domain → path pattern → fallback
- [ ] Handle multi-redirect: wait 3-5s for final URL

### SR-32.2 — DOM-Based Detection (Fallback)
- [ ] Wenn URL nicht erkannt: DOM-Struktur analysieren
- [ ] Qualtrics: `.NextButton` exists
- [ ] TolunaStart: `.cf-radio` exists
- [ ] PureSpectrum: `screener.purespectrum.com` in HTML / "ROBOT" text
- [ ] Strat7: `.bsbutton` exists

### SR-32.3 — Pre-Qualifier Detection
- [ ] `detect_pre_qualifier(tab_url, tab_content)` → bool
- [ ] API `type:question` → pre-qualifier
- [ ] CDP: document.body.innerText auf "pre-qualifier" patterns prüfen

### SR-32.4 — Provider Statistics
- [ ] `ProviderStats` Dataclass: total_attempts, total_completed, total_earned, avg_earned, success_rate
- [ ] `~/.stealth/provider_stats.json`
- [ ] Auto-Priorisierung: Provider mit höchster success_rate zuerst

## Acceptance Criteria
- [ ] Alle 6 bekannten Provider werden via URL erkannt
- [ ] DOM-Fallback funktioniert wenn URL-Pattern fehlt
- [ ] Pre-Qualifier wird vor Survey-Start erkannt
- [ ] Provider-Statistiken werden gespeichert

## Betroffene Files
- `cli/modules/provider_patterns.py` → NEU
- `cli/modules/survey_cdp.py` → Integration
- `~/.stealth/provider_stats.json` → NEU
