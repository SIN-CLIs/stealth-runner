# Plan: Fix Survey-CLI — Manual Works, Daemon Fails (2026-05-06)

> **STATUS: ALL FIXES CRASH-TESTED ✅** — 282 tests passing, 1 survey completed in production (36.3s)
> **Date completed**: 2026-05-06
>
> **What was done**: All 4 root causes resolved. P0 (pre-qualifiers): `handle_pre_qualifier()` now called in `run_loop()`, 13 tests, LIVE-verified (6 pre-qualifiers processed). P1 (stealth): `create_blank_tab()` → `inject_stealth_to_tab()` → `navigate_tab()`, 19 tests, LIVE-verified. P1 (CDP): CDPConnection class (sync, 229 lines), 15 tests, LIVE-verified (0 "No such target" errors). P3 (balance): read BEFORE tab creation, `max(0, earned)`, 5 tests, LIVE-verified. Bonus: `message_button` in CPX POST, pre-qualifier failure cache, `started_count`, `read_page_text`/`detect_error_page` static methods.

---

## 🔴 CRITICAL: Root Cause Summary

```
MANUAL SURVEY:     Dashboard → clickSurvey() → In-page modal → Survey tab opens
                   → cua-driver WINDOW-based (stable) → Balance visible throughout

DAEMON SURVEY:     Dashboard → extract IDs → CPX API → filter
                   → Creates new tab via Target.createTarget
                   → Caches tab_id / WS URL → Navigation invalidates it
                   → "No such target id" → Circuit breaker → 0€ earned
```

### 4 Root Causes (nach Priorität)

| # | Root Cause | Impact | Fix Location |
|---|-----------|--------|--------------|
| P0 | **Pre-qualifiers SKIPPED** — `run_loop()` silently `continue`s on `provider=="pre_qualifier"` | ~40% Surveys wasted (3 surveys × 25 loops = 75 wasted cycles) | `runner.py:run_loop()` |
| P1 | **Zero stealth injection** — no `navigator.webdriver=false`, no canvas jitter, no WebGL patch | PureSpectrum/Cint detect automation immediately | `chrome.py` + new `stealth_inject.py` |
| P2 | **Stale CDP WS** — cached `webSocketDebuggerUrl` becomes invalid after navigation | "No such target id" (500) on every survey | `runner.py:_refresh_tab_ws()` + `CDPClient` from stealth-captcha |
| P3 | **Balance read fails** — `read_balance()` uses dashboard WS that disappears after survey opens | All 8 completed surveys show `amount_eur: 0.0` | `runner.py` post-survey section |

---

## 📋 Sub-Plans

| Plan | File | Status |
|------|------|--------|
| Pre-qualifier fix | `plan_prequalifier.md` | ✅ FIXED |
| Stealth injection | `plan_stealth.md` | ✅ FIXED |
| CDP WS reconnect | `plan_cdp_reconnect.md` | ✅ FIXED |
| Balance fix | `plan_balance.md` | ✅ FIXED |
| Full execution | `plan_execution.md` | ✅ ALL COMPLETED |

---

## ✅ Vorbedingungen (already met)

- [x] survey-cli hat 230 Tests passing
- [x] `stealth-captcha/src/stealth_captcha/cdp/client.py` → Production-ready `CDPClient`
- [x] `stealth-captcha/stealth/scripts/stealth_main.js` → 12-module stealth bundle
- [x] `handle_pre_qualifier()` existiert bereits in `runner.py` (nie aufgerufen)
- [x] `_refresh_tab_ws()` existiert bereits in `runner.py` (funktioniert falsch)
- [x] Alle Fixes sind im stealth-runner Workspace — nichts extern nötig

---

## 🚀 Execution Order — ALLE ABGESCHLOSSEN

```
1. ✅ plan_prequalifier.md    → Fix P0 (Pre-qualifier Skip) — ERFOLGREICH
2. ✅ plan_stealth.md         → Fix P1 (Zero Stealth Injection) — ERFOLGREICH
3. ✅ plan_cdp_reconnect.md   → Fix P2 (Stale CDP WS) — ERFOLGREICH
4. ✅ plan_balance.md         → Fix P3 (Balance Read Fails) — ERFOLGREICH
5. ✅ plan_execution.md       → Alle Fixes + Tests + Live Crash-Test — ERFOLGREICH
```

---

## 📊 Erreichte Ergebnisse nach Fix

| Metric | Before | After |
|--------|--------|-------|
| Surveys analyzed per loop | 3 (rest skipped) | 3 (all processed) |
| Pre-qualifier handling | 0% (skipped) | 100% (6 pre-qualifiers LIVE-verified) |
| Stealth modules active | 0 | 12 (navigator, canvas, WebGL, audio, etc.) |
| "No such target id" errors | 20+ per session | 0 (CDPConnection auto-reconnect) |
| Balance capture | 0.0€ (always) | Actual € captured per survey |
| Production survey completed | 0 | 1 (36.3s) |
| Test count | 230 | 282 |
