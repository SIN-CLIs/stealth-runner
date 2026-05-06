# Issues — Stealth Runner

> Alle Issues sind in `issues/ISSUE-SR-*.md`.  
> Pläne sind in `plan-sr-XX-*.md`.

---

## 📊 Übersicht

| Status | Count |
|--------|-------|
| ✅ Completed | 17 (SR-11 bis SR-27) |
| 📋 Active | 9 (SR-28 bis SR-36) |
| 🚧 Blocked | 1 (PureSpectrum CAPTCHA) |

---

## 📋 AKTIV — Offene Coding-Aufgaben

| Issue | Priority | Status | Titel | Plan |
|-------|----------|--------|-------|------|
| [SR-28](issues/ISSUE-SR-28.md) | 🔴 P0 | 📋 TODO | **CDP Survey Module** — cua-driver → CDP WebSocket Rewrite | [plan-sr-28](plan-sr-28-cdp-survey-module.md) |
| [SR-29](issues/ISSUE-SR-29.md) | 🔴 P0 | 🚧 BLOCKED | **PureSpectrum CAPTCHA OCR Solver** | [plan-sr-29](plan-sr-29-ps-captcha-ocr.md) |
| [SR-30](issues/ISSUE-SR-30.md) | 🔴 P0 | 📋 TODO | **Dashboard Poller + Auto-Loop** | [plan-sr-30](plan-sr-30-dashboard-poller.md) |
| [SR-31](issues/ISSUE-SR-31.md) | 🟠 P1 | 📋 TODO | **Flow Compiler FCTES — Production Promotion** | [plan-sr-31](plan-sr-31-fctes-promotion.md) |
| [SR-32](issues/ISSUE-SR-32.md) | 🟠 P1 | 📋 TODO | **Provider Auto-Detect Engine** | [plan-sr-32](plan-sr-32-provider-detect.md) |
| [SR-33](issues/ISSUE-SR-33.md) | 🟠 P1 | 📋 TODO | **Persona System** — Dynamic Profile statt Hardcode | [plan-sr-33](plan-sr-33-persona-system.md) |
| [SR-34](issues/ISSUE-SR-34.md) | 🟡 P2 | 📋 TODO | **Survey Flow Test Suite** | [plan-sr-34](plan-sr-34-test-suite.md) |
| [SR-35](issues/ISSUE-SR-35.md) | 🟡 P2 | 📋 TODO | **Chrome Lease Manager + Safety** | [plan-sr-35](plan-sr-35-chrome-safety.md) |
| [SR-36](issues/ISSUE-SR-36.md) | 🟢 P3 | 📋 TODO | **Generated Docs De-Duplication** | [plan-sr-36](plan-sr-36-docs-cleanup.md) |

### Priority Map

```
P0 (BLOCKER — kein Einkommen ohne):
  SR-28  CDP Survey Module        ← JEDER Survey braucht das
  SR-29  PureSpectrum OCR          ← 12 Survey-IDs blockiert
  SR-30  Dashboard Poller          ← Automatischer Loop

P1 (Enabler — macht alles schneller):
  SR-31  FCTES Promotion           ← 10× → frozen → 1-Click
  SR-32  Provider Detect           ← URL → Pattern auto
  SR-33  Persona System            ← Keine Disqualifikation mehr

P2 (Qualität):
  SR-34  Test Suite                ← Stabilität
  SR-35  Chrome Safety             ← User-Chrome-Schutz

P3 (Nice-to-have):
  SR-36  Docs Cleanup              ← 470+ Dateien aufräumen
```

### Sub-Issues pro Issue

| Issue | Sub-Count | Sub-Issues |
|-------|-----------|------------|
| SR-28 | 5 | CDP Client, Provider Registry, Answer Engine, Full Runner, Demographics |
| SR-29 | 4 | Image Extraction, OCR Selection, Auto-Submit, Integration |
| SR-30 | 5 | ID Extractor, API Filter, Provider Router, Auto-Loop, Balance Tracker |
| SR-31 | 5 | Flow Definition, Tracker Repair, Compiler Hardening, Signature, opencode.json |
| SR-32 | 4 | URL Detection, DOM Fallback, Pre-Qualifier, Provider Stats |
| SR-33 | 4 | Profile File, Age Calculator, Question Matcher, Integration |
| SR-34 | 5 | Provider Detect Tests, Answer Pattern Tests, Persona Tests, Mock Server, E2E |
| SR-35 | 4 | KillGuard, Lease System, PID Registry, Auto-Recovery |
| SR-36 | 4 | Inventar, Quality Scoring, De-Duplication, Cleanup Script |

---

## ✅ COMPLETED — Abgeschlossene Issues

| Issue | Status | Priority | Titel |
|-------|--------|----------|-------|
| [SR-11](issues/ISSUE-SR-11.md) | ✅ | 🔴 | CI/CD — GitHub Actions, Pre-Commit, Auto-Release |
| [SR-12](issues/ISSUE-SR-12.md) | ✅ | 🔴 | Test Suite — Unit, Integration, E2E |
| [SR-13](issues/ISSUE-SR-13.md) | ✅ | 🟠 | Survey Provider Adapter — Samplicio.us, Cint, Nfield |
| [SR-14](issues/ISSUE-SR-14.md) | ✅ | 🟠 | Audio Capture Module — BlackHole + ffmpeg + Omni |
| [SR-15](issues/ISSUE-SR-15.md) | ✅ | 🟡 | Captcha Solving — Simple, GeeTest v4, Lemin Puzzle |
| [SR-16](issues/ISSUE-SR-16.md) | ✅ | 🟡 | Error Recovery — Disqualification, Modal Error, Timeout |
| [SR-17](issues/ISSUE-SR-17.md) | ✅ | 🔴 | CUA-ONLY Migration — skylight-cli → cua-driver |
| [SR-18](issues/ISSUE-SR-18.md) | ✅ | 🔴 | stealth-session — Warm Daemon for <50ms Command Execution |
| [SR-19](issues/ISSUE-SR-19.md) | ✅ | 🔴 | stealth-axiom — 3-Tier Hierarchical Model Router |
| [SR-20](issues/ISSUE-SR-20.md) | ✅ | 🔴 | RecursiveMAS — RecursiveLink + Survey MAS Pipeline |
| [SR-21](issues/ISSUE-SR-21.md) | ✅ | 🔴 | stealth-sota — Chaos/Security/Healing/Observability/Determinism |
| [SR-22](issues/ISSUE-SR-22.md) | ✅ | 🔴 | stealth-core + stealth-dynamic — Basis-Klassen + Dynamic Engine |
| [SR-23](issues/ISSUE-SR-23.md) | ✅ | 🔴 | stealth-memory — Eternal Memory (opencode.db Poller) |
| [SR-24](issues/ISSUE-SR-24.md) | ✅ | 🔴 | E2E Test: GoCaptcha Slide with Real Browser |
| [SR-25](issues/ISSUE-SR-25.md) | ✅ | 🟠 | README.md + CLI Documentation for @stealth/captcha |
| [SR-26](issues/ISSUE-SR-26.md) | ✅ | 🟠 | Unit Tests: CDP Client + HitTester + Memory |
| [SR-27](issues/ISSUE-SR-27.md) | ✅ | 🟡 | stealth-suite: Incident Resolution + Monitoring |

---

## 🏭 SURVEY FINDINGS (2026-05-06)

### Qualtrics HUK Coburg (+0.38€)
- **File**: `commands/surveys/qualtrics-huk-survey.md`
- **Pattern**: `.NextButton` + `input[type=radio]` global indices + `table.ChoiceStructure` matrix
- **Flow**: 21 pages, insurance brand perception study
- **Balance impact**: 1.77€ → 2.15€

### TolunaStart (+0.09€, 92%)
- **File**: `commands/tolunastart-survey.md`
- **Pattern**: JS `.click()` on `.cf-radio`/`.cf-checkbox` (NOT MouseEvent!)
- **Remaining**: Demographics section (8%)

### Strat7 Audiences (+0.03-0.09€)
- **File**: `commands/strat7-survey.md`
- **Pattern**: `.bsbutton` grid + consent flow

### Brand Ambassador (+0.02€)
- **File**: `commands/brand-ambassador-survey.md`
- **Pattern**: Attention checks with hidden inputs

### Insights-Today (Screen-out)
- **File**: `commands/insights-today-survey.md`
- **Pattern**: `<select>` for age, LABEL click for income
- **Issue**: Universitätsabschluss → screen-out. Try Abitur.

### PureSpectrum (BLOCKED — CAPTCHA)
- **File**: `commands/purespectrum-survey.md`
- **Issue**: Base64 PNG text CAPTCHA blocks all 12 current survey IDs
- **Blocked by**: Need OCR solver (SR-29)

### Survey Routing
```
heypiggy → CPX API → click.cpx-research.com →
  → eu.qualtrics.com          ✅ +0.38€
  → tolunastart.com           ✅ +0.09€
  → strat7audiences.com       ✅ +0.03-0.09€
  → brand-ambassador.com      ✅ +0.02€
  → insights-today.com        ❌ Screen-out
  → purespectrum.com          ❌ CAPTCHA (12 IDs)
  → surveyrouter.com          ❌ Hangs
  → surveys.com (GfK)         ❌ Cookie wall
```

---

## 🚨 PERSISTENT ISSUES (nicht in SR-Nummern)

| # | Titel | Status | Fix |
|---|-------|--------|-----|
| 1 | **PureSpectrum CAPTCHA** | 🚧 BLOCKED | SR-29 — OCR Solver |
| 2 | **Surveyrouter** | ❌ HANGS | Tab schließen, nächsten Survey |
| 3 | **CPX URL Single-Use** | ⚠️ BEKANNT | Immer neuen API-Call machen |
| 4 | **Balance-Desync** | ⚠️ BEKANNT | Dashboard-Reload nach jedem Survey |
| 5 | **Insights-Today Education** | ⚠️ PENDING | Abitur statt Universität (SR-33) |
| 6 | **orchestrator.py Import** | ✅ FIXED | `auto_google_login` statt `heypiggy_login_box` |
