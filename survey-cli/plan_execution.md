# Plan: Execution — Fix Survey-CLI (All 4 Root Causes)

> **STATUS: ALL PHASES COMPLETED ✅** — 282 tests passing, 1 survey in production (36.3s)
> **Date completed**: 2026-05-06

---

## Execution Order — ALLE PHASEN ABGESCHLOSSEN

```
✅ Phase 1: P0 Pre-qualifier fix  — 13 tests, 6 pre-qualifiers LIVE-verified
✅ Phase 2: P1 Stealth injection  — 19 tests, 3-phase tab creation (blank→inject→navigate)
✅ Phase 3: P1 CDP WS reconnect   — 15 tests, sync CDPConnection (229 lines), 0 "No such target" errors
✅ Phase 4: P3 Balance read       — 5 tests, moved before tab creation, max(0, earned)
✅ Phase 5: Regression tests      — 282 total passing (all 4 test files + existing)
✅ Phase 6: Live crash-test       — 1 survey completed in production (36.3s)
────────────────────────────────────────
Total: ALL COMPLETE
```

---

## Final Verification Results

```
=== PHASE 1: P0 Pre-qualifier ===
✅ handle_pre_qualifier() called from run_loop()
✅ multi-step CPX API loop: GET question → POST answer → repeat until "okay"
✅ message_button added to POST payload
✅ pre-qualifier failure cache (don't retry known-failures)
✅ started_count tracking for session stats
✅ 13 tests, LIVE-verified: 6 pre-qualifiers processed successfully
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

=== PHASE 2: P1 Stealth Injection ===
✅ create_blank_tab() → inject_stealth_to_tab() → navigate_tab()
✅ Page.addScriptToEvaluateOnNewDocument for persistence
✅ 12-module stealth bundle from stealth-captcha
✅ navigator.webdriver, canvas jitter, WebGL spoof, plugins, audio context
✅ 19 tests, LIVE-verified: navigator.webdriver === undefined confirmed
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

=== PHASE 3: P1 CDP WS Reconnect ===
✅ CDPConnection class (sync, 229 lines) — no async refactor needed
✅ Exponential backoff: 0.3s → 0.6s → 1.2s → 2s
✅ ID-based response routing via _pending dict
✅ Auto-reconnect on "No such target" + connection reset
✅ 15 tests, LIVE-verified: 0 "No such target" errors in production run
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

=== PHASE 4: P3 Balance Read ===
✅ balance_before read BEFORE create_blank_tab()
✅ try/except wrapper on both before and after reads
✅ max(0, earned) — never negative delta
✅ read_page_text() / detect_error_page() static methods
✅ 5 tests, LIVE-verified: balance delta captured correctly
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

=== PHASE 5: Regression Tests ===
✅ tests/test_prequalifier.py — 13 tests passing
✅ tests/test_stealth.py — 19 tests passing
✅ tests/test_cdp_reconnect.py — 15 tests passing
✅ tests/test_balance.py — 5 tests passing
✅ All 230 existing tests still pass
✅ TOTAL: 282 tests passing
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

=== PHASE 6: Live Crash-Test ===
✅ 1 survey completed in production (36.3s)
✅ Pre-qualifier answered → real survey → completed → balance captured
✅ Zero CDP errors, zero detection, zero balance failures
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Success Criteria — ALLE ERFÜLLT

- ✅ Pre-qualifiers answered (not skipped) — 6 LIVE-verified
- ✅ Stealth modules active in new tabs — 12 modules confirmed
- ✅ Zero "No such target id" errors — CDPConnection tested
- ✅ Balance shows delta > 0 for completed surveys — captured
- ✅ All 282 tests still pass

## Git Commit Structure

```bash
git add -A && git commit -m "fix(prequalifier): call handle_pre_qualifier() in run_loop()"

git add -A && git commit -m "fix(stealth): inject 12-module stealth bundle on tab creation"

git add -A && git commit -m "fix(cdp): add sync CDPConnection with ID routing and auto-reconnect"

git add -A && git commit -m "fix(balance): read balance before survey tab opens"

git add -A && git commit -m "test(regression): 52 new tests for all 4 fixes"
```

## Rollback Plan

If a fix breaks existing tests:

```bash
# Revert specific commit
git revert HEAD
# Run tests
python -m pytest tests/ -v
# Debug, then re-apply fix
```

Each phase is independently testable before moving to next.
