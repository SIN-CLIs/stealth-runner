# SIN-HERMES v2.0 → stealth-runner Integration Plan

## 🚨 Context: Accidentally Pushed to Wrong Repo

**What happened:**
- v0 built SIN-HERMES v2.0 core modules (5 production-grade Python modules)
- Mistakenly pushed to `Delqhi/sin-hermes-agent` instead of `sin-clis/stealth-runner`
- Your colleague was correctly working on stealth-runner all along ✅

**What needs to happen:**
- Move core modules to `stealth-runner/core/`
- Integrate with existing LangGraph survey agent
- Update all imports and tests
- Achieve < 2min surveys, 0 errors

---

## 📋 Files to Integrate from sin-hermes-agent

### SIN-HERMES v2.0 Core Modules (Production-Grade)
**Location:** Delqhi/sin-hermes-agent/.open-auth-rotator/openai/core/

Files to port (Python equivalents):
- ✅ config.py - Environment detection, validation, immutable settings
- ✅ error_handler.py - Circuit breaker, exponential backoff, retry strategies
- ✅ security.py - Fernet encryption, credential vault, audit logging
- ✅ analytics.py - Metrics collection, Prometheus export, health checks
- ✅ state_manager.py - Checkpoint/restore, crash recovery, distributed state

---

## 🎯 Integration Checklist (GitHub Issues)

**Created:**
- **#81:** [P0] Integrate SIN-HERMES v2.0 Core Modules
- **#82:** [CLEANUP] Review accidental pushes to Delqhi/sin-hermes-agent
- **#83:** [P1] Production-Ready Error Handling & Observability

---

## 📊 Current stealth-runner Architecture (Already Correct!)

Your colleague built this correctly:
```
stealth-runner/
├── survey-cli/survey/
│   ├── graph.py           ✅ LangGraph orchestration
│   ├── cdp_universal.py   ✅ Universal CDP scanner
│   ├── cdp_actuator.py    ✅ Action execution
│   ├── captcha_router.py  ✅ CAPTCHA routing
│   └── chrome.py          ✅ Browser management
├── agent-toolbox/api/
│   └── endpoints/
│       ├── universal.py   ✅ v2 scan endpoint
│       ├── captcha.py     ✅ v2 captcha endpoint
│       └── actuator.py    ✅ v2 click/fill endpoint
└── AGENTS.md              ✅ Architecture spec
```

**This is the CORRECT repo for everything. Not Delqhi repos.**

---

## ❌ What NOT to Integrate

- ❌ Survey Builder UI (dashboard, forms, survey-plattform stuff)
- ❌ Supabase auth pages (login/register)
- ❌ Dashboard/analytics pages
- ❌ Landing pages
- ❌ General-purpose CAPTCHA widget

**These were for a different product. Keep ONLY agent-focused code.**

---

## ✅ What SHOULD be integrated

From SIN-HERMES v2.0 core/:
1. **config.py** → `stealth-runner/core/config.py`
2. **error_handler.py** → `stealth-runner/core/error_handler.py`
3. **security.py** → `stealth-runner/core/security.py`
4. **analytics.py** → `stealth-runner/core/analytics.py`
5. **state_manager.py** → `stealth-runner/core/state_manager.py`

Then update:
- LangGraph nodes with error handling
- FastAPI endpoints with state tracking
- Tests for all core modules
- AGENTS.md with updated architecture

---

## 🚀 Why This Matters

Your goal: **Surveys in < 2min with 0 errors**

These core modules provide:
- ✅ Circuit breaker (fail-safe when things break)
- ✅ Exponential backoff (smart retries)
- ✅ State persistence (resume after crashes)
- ✅ Encryption (secure credential storage)
- ✅ Audit logging (compliance + debugging)
- ✅ Metrics (Prometheus for monitoring)

**Result:** Production-ready reliability.

---

## 📌 Status

- ✅ stealth-runner is correct (your colleague did it right)
- ❌ sin-hermes-agent has accidental files (will cleanup)
- ⏳ Integration ready to start (see Issues #81-#83)

**Next:** Review issues, coordinate with team, start integration.
