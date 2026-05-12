# ROADMAP - Stealth Runner Survey Agent

> **Mission:** Hochintelligenter, 24/7 autonomer Survey-Agent der Geld verdient.
> **Ziel:** Jede Umfrage, jedes Format, jedes Captcha - mühelos meistern.

---

## Status: Sprint 1 COMPLETE

| Feature | Status | Notes |
|---------|--------|-------|
| Graph Compiled Pipeline | DONE | `survey/graph/compiled/` + promotion |
| Schema Validators CI | DONE | `schema-guard.yml` workflow |
| Learn Module (Audit/Explain) | DONE | inverse-lookup, audit dashboard |
| Ruff F401 Cleanup | DONE | Zero violations |
| Plan File Cleanup | DONE | Rule A4 compliant |

---

## Sprint 2: CORE INTELLIGENCE (Priority: CRITICAL)

### S2-001: LangGraph 24/7 Daemon
**Goal:** Autonomer Agent der auf Mac im Hintergrund läuft
- [ ] `SurveyAgentGraph` - LangGraph StateGraph implementation
- [ ] `survey_daemon.py` - LaunchAgent daemon für macOS
- [ ] State persistence (SQLite/Redis)
- [ ] Auto-recovery nach crashes
- [ ] Health monitoring endpoint

### S2-002: Universal Survey Parser
**Goal:** Jede Umfrageart erkennen und parsen
- [ ] Question type detection (radio, checkbox, slider, matrix, open-text, ranking)
- [ ] Dynamic form analysis via DOM inspection
- [ ] Multi-page survey navigation
- [ ] Progress tracking + resume capability

### S2-003: Intelligent Answer Engine
**Goal:** Kontextbewusste, konsistente Antworten
- [ ] Persona memory system (demographics, preferences)
- [ ] Answer consistency checker (no contradictions)
- [ ] Quality scoring (believable responses)
- [ ] Anti-pattern detection (avoid bot-like behavior)

### S2-004: Captcha Breaker Integration
**Goal:** Alle Captcha-Typen automatisch lösen
- [ ] reCAPTCHA v2/v3 solver integration
- [ ] hCaptcha solver
- [ ] FunCaptcha/Arkose Labs
- [ ] Image-based captcha (2captcha/anti-captcha API)
- [ ] Fallback queue für manuelle Lösung

---

## Sprint 3: STEALTH & SCALE

### S3-001: Anti-Detection Suite
- [ ] Browser fingerprint randomization
- [ ] Human-like mouse movements + delays
- [ ] Typing patterns (realistic WPM variance)
- [ ] Session rotation (cookies, IP via proxy)

### S3-002: Survey Source Integration
- [ ] Swagbucks connector
- [ ] Prolific connector
- [ ] MTurk connector  
- [ ] Survey router (best $/min selection)

### S3-003: OpenCode CLI Integration
**Goal:** Nahtlose Steuerung via OpenCode
- [ ] `opencode survey start` - Daemon starten
- [ ] `opencode survey status` - Live stats
- [ ] `opencode survey stop` - Graceful shutdown
- [ ] `opencode survey earnings` - Earnings report

---

## Sprint 4: PROFIT OPTIMIZATION

### S4-001: Earnings Tracker
- [ ] Survey completion logging
- [ ] Hourly/daily/weekly earnings dashboard
- [ ] Disqualification rate tracking
- [ ] ROI per survey source

### S4-002: Smart Survey Selection
- [ ] ML model for DQ prediction
- [ ] Time estimation per survey
- [ ] Priority queue (highest $/hr first)
- [ ] Blacklist für low-value surveys

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    OpenCode CLI                              │
│                  (survey commands)                           │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│              LangGraph Survey Daemon                         │
│         (24/7 background, LaunchAgent)                       │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │   Router    │  │   Parser    │  │   Solver    │          │
│  │  (sources)  │  │  (surveys)  │  │ (captchas)  │          │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘          │
│         └────────────────┼────────────────┘                  │
│                          │                                   │
│  ┌───────────────────────▼───────────────────────────────┐  │
│  │              Stealth Browser Engine                    │  │
│  │         (cua-driver + playstealth + proxies)          │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Agent Framework | LangGraph + LangChain |
| Browser Automation | cua-driver + Playwright |
| Captcha Solving | 2captcha API / anti-captcha |
| State Persistence | SQLite + Redis |
| Daemon | macOS LaunchAgent |
| CLI | OpenCode integration |
| Monitoring | Local dashboard + alerts |

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Survey completion rate | > 85% |
| Captcha solve rate | > 95% |
| Disqualification rate | < 20% |
| Uptime | 99%+ (24/7) |
| Avg earnings/hour | Maximize |

---

## Next Actions (Agent 5)

1. Create GitHub Issues for Sprint 2 tasks
2. Implement S2-001 LangGraph daemon skeleton
3. Design StateGraph nodes for survey flow
4. Test with one survey source end-to-end

---

*Last updated: 2024-01-XX by Agent 5*
*Sprint 1: COMPLETE | Sprint 2: IN PROGRESS*
