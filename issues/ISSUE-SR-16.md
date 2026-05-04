# SR-16: Captcha Auto-Solve — Automatic Captcha Detection + Solution

- **Status:** ✅ COMPLETED (modules exist, integrated in survey_runner.py)
- **Priority:** 🟡 High
- **Plan:** [`plans/plan-captcha-integration.md`](../plans/plan-captcha-integration.md)

## Description

Captcha detection and solving integrated into the survey flow. 21 captcha types tested via `captcha_crashtest.py`, automatic solving via `stealth-captcha` library.

## Deliverables

- [x] Captcha detection in `vision_gate.py` (lines 348-486) — AX tree scan
- [x] `survey_runner.py` detects captcha via keyword matching (line 286-287)
- [x] `captcha_crashtest.py` (161 lines) — 21 captcha types tested
- [x] `handle_captcha_in_survey()` called automatically in survey flow
- [x] pkill removed from both crashtest modules (PID-specific now)
- [x] CLI wrapper: `cli/captcha-crashtest <PID> [cycles]`
- [x] JSON logging via `_save_results()`
- [x] CI workflow: `.github/workflows/crashtest.yml`

## Acceptance Criteria

- [x] 21 captcha types defined in CAPTCHA_TYPES
- [x] Auto-detection in survey flow
- [x] No pkill in code (PID-specific kill only)
- [x] JSON results persisted to file

## Files

- `cli/modules/captcha_crashtest.py` (161 lines)
- `cli/modules/vision_gate.py` (lines 348-486)
- `cli/modules/survey_runner.py` (lines 579-585)
- `cli/captcha-crashtest` (CLI wrapper)
- `.github/workflows/crashtest.yml` (CI workflow)
