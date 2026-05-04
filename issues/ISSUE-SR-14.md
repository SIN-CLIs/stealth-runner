# SR-14: Survey Runner Completion — Multi-Survey + Balance

- **Status:** ✅ COMPLETED (2026-05-04)
- **Priority:** 🔴 Critical
- **Plan:** [`plans/plan-survey-runner-complete.md`](../plans/plan-survey-runner-complete.md)

## Description

Updated `survey_runner.py` with queue integration, balance tracking, and improved error handling.

## Deliverables

- [x] `run()` accepts `queue_db` parameter to activate SQLite queue
- [x] `runner/survey_queue.py` activated: claim → process → done/fail
- [x] Balance VOR Survey captured
- [x] Balance NACH Survey captured
- [x] VORHER/NACHHER comparison to detect earnings
- [x] Queue: failed tasks marked with error reason
- [x] Queue: break on empty queue
- [x] "No surveys" case handled gracefully

## Acceptance Criteria

- [x] `run(pid, queue_db="/tmp/test.db")` uses queue-based task management
- [x] Balance checked before + after survey
- [x] Failed surveys marked in queue with error reason

## Files

- `cli/modules/survey_runner.py` — main file (updated `run()` function)
- `runner/survey_queue.py` — SQLite queue (activated)
