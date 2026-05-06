# ✅ FIXED — 5 tests, LIVE-verified (balance delta captured correctly)

**What was implemented**: Balance reading moved BEFORE `create_blank_tab()` — dashboard WS is read while the dashboard tab is still valid, guaranteeing the before-reading succeeds. After survey completes (or fails), a second balance read is attempted with a try/except wrapper (graceful failure if WS is stale). Delta calculated as `max(0, balance_after - balance_before)` to ensure earned is never negative. Also added `read_page_text()` and `detect_error_page()` static methods for robust page interaction. 5 regression tests pass, LIVE-verified in production.

---

# Plan: P3 Fix — Balance Read FAILS → Read Before Survey Opens

## Problem
`run_loop()` reads balance AFTER survey tab opens — but the dashboard WS (used to read balance) becomes invalid when the survey tab opens via `Target.createTarget`.

```python
# Current order in run_loop():
survey_result = self._run_survey(survey, driver_info)
# ... survey tab open → dashboard tab stale ...
balance = self._read_balance(driver_info)  # ← FAILS (dashboard WS invalid)
self._update_log(balance)
```

## Root Cause

1. `Target.createTarget` opens a NEW tab in Chrome
2. Dashboard tab loses focus (or gets backgrounded)
3. Dashboard WS becomes stale or closed
4. `_read_balance(driver_info)` tries to use dashboard WS → fails
5. Balance remains at default `0.0` even for completed surveys

## Fix Strategy

### Read balance BEFORE survey tab opens

```python
# run_loop() — FIXED ORDER
# 1. Read balance NOW (dashboard WS still valid)
balance_before = self._read_balance(driver_info)
print(f"[LOOP] Balance before survey: {balance_before}")

# 2. Run survey (creates new tab, dashboard WS may become stale)
survey_result = self._run_survey(survey, driver_info)

# 3. Read balance AFTER (dashboard tab restored OR reconnected)
# Use cached balance_before if dashboard WS fails
balance_after = self._try_read_balance(driver_info)  # may fail
earned = max(0, balance_after - balance_before)  # delta = survey earnings
```

### Alternative: Read balance via heypiggy REST API

Instead of CDP JS on dashboard tab, hit the API directly:

```python
def _read_balance_via_api(self) -> float:
    """Read balance via heypiggy.com REST API (no WS needed)."""
    try:
        resp = requests.get(
            "https://heypiggy.com/api/dashboard/balance",
            headers={"Authorization": f"Bearer {self._get_token()}"},
            timeout=10
        )
        return resp.json().get("balance", 0.0)
    except Exception:
        return 0.0
```

### Alternative: Use dashboard tab's persistent WS

Keep dashboard tab WS alive by NOT navigating away from it:

```python
# In _run_survey():
# OLD: Target.createTarget creates new tab → dashboard tab loses focus
# NEW: Use already-open dashboard tab for survey (if in-page modal flow)

# Check if survey can be started in-page (manual flow does this):
if survey.get("can_start_in_page", False):
    # Click survey card via dashboard WS (no new tab)
    dashboard_ws.send(json.dumps({
        "method": "Runtime.evaluate",
        "params": {"expression": f"clickSurvey('{survey_id}')"}
    }))
    # Survey opens as overlay/modal in same tab
    # Dashboard WS stays valid → balance readable throughout
else:
    # Fall back to new tab (CPX/pre-qualifier flow)
    pass
```

## Files to Change

| File | Change | Risk |
|------|--------|------|
| `survey/runner.py` | Move balance read BEFORE survey execution | Low |
| `survey/runner.py` | Add `_try_read_balance()` with graceful failure | Low |
| `survey/runner.py` | Calculate `earned = delta` instead of absolute | Low |
| `survey/runner.py` | Add `_read_balance_via_api()` as fallback | Medium — new API call |

## Implementation Details

### Balance read timing

```python
def run_loop(self):
    for survey in ok_surveys:
        if self._should_stop():
            break

        # Read balance BEFORE survey opens
        try:
            balance_before = self._read_balance(self.driver_info)
        except Exception as e:
            print(f"[WARN] Balance read before failed: {e}")
            balance_before = None

        # Run survey (may open new tab)
        result = self._run_survey(survey, self.driver_info)

        # Read balance AFTER (may fail if new tab broke dashboard WS)
        balance_after = None
        try:
            balance_after = self._read_balance(self.driver_info)
        except Exception:
            pass  # graceful failure

        # Calculate delta
        if balance_before is not None and balance_after is not None:
            earned = balance_after - balance_before
            self._update_log(survey_id=survey["id"], earned=earned,
                           balance_before=balance_before, balance_after=balance_after)
        elif balance_before is not None:
            # After failed — use before as estimate
            self._update_log(survey_id=survey["id"], earned=0.0,
                           balance_before=balance_before, balance_after=None,
                           note="after-read-failed")
        else:
            self._update_log(survey_id=survey["id"], earned=0.0, note="both-reads-failed")
```

### Log format for balance tracking

```python
# In _update_log():
{
    "survey_id": survey_id,
    "timestamp": datetime.now().isoformat(),
    "balance_before": 2.23,      # nullable
    "balance_after": 3.23,        # nullable
    "earned": 1.00,              # balance_after - balance_before
    "result": "completed",       # or "failed", "disqualified"
    "note": None                 # "after-read-failed", "both-reads-failed"
}
```

## Tests to Add

```python
# tests/test_balance.py (NEW)
class TestBalanceTracking:
    def test_reads_balance_before_survey()
    def test_calculates_delta_earned()
    def test_handles_before_read_failure_gracefully()
    def test_handles_after_read_failure_gracefully()
    def test_logs_earned_per_survey()
    def test_zero_earned_on_failure()
```

## Verification

```bash
# Before: 8 completed surveys, all show amount_eur: 0.0
# After: 8 completed surveys show actual amounts (e.g., 0.32, 0.88, 1.20)
python3 -m survey run --mode loop --max 3 --debug
# Check logs: balance_before, balance_after, earned per survey
```

## Estimate

- **Effort**: 1-2h
- **Impact**: Captures actual earnings per survey (currently 0% captured)
- **Risk**: Low — simple timing fix
