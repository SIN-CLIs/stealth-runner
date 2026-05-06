# ✅ FIXED — 13 tests, LIVE-verified (6 pre-qualifiers processed)

**What was implemented**: `handle_pre_qualifier()` is now called from `run_loop()` for all `provider=="pre_qualifier"` surveys. The CPX multi-step API loop (GET question → match profile → POST answer → repeat until "okay") processes pre-qualifiers inline. Added `message_button` to POST payload, `started_count` for session stats, and pre-qualifier failure cache to avoid retrying known-bad surveys. 13 regression tests pass, 6 pre-qualifiers LIVE-verified in production.

---

# Plan: P0 Fix — Pre-qualifiers SKIPPED → Answered

## Problem
`run_loop()` silently skips ALL surveys with `provider == "pre_qualifier"`:
```python
# runner.py:490-491
if survey.get("provider") == "pre_qualifier":
    continue  # silently skip pre-qualifiers
```

Von 3 OK surveys pro Loop:
- Survey 1: OK (qualtrics)
- Survey 2: pre_qualifier → skipped
- Survey 3: pre_qualifier → skipped

→ 0% pre-qualifier handling despite `handle_pre_qualifier()` existing in the same file.

## Root Cause
`handle_pre_qualifier()` exists (200+ lines, handles multi-step CPX API loop with profile matching), but is NEVER called from `run_loop()`.

## Fix Strategy

### Option A: API-based handling (preferred — already implemented, just not called)

`handle_pre_qualifier()` tut folgendes:
1. `GET details_url + survey_id` → `{type: "question", question_text, question_key, answers}`  
2. Match question to profile → select answer index  
3. `POST details_url + survey_id + question_key + answer_key`  
4. Repeat until `type == "okay"` → return `href` (actual survey URL)  
5. Max 8 retries

**Das funktioniert bereits** — muss nur aus `run_loop()` aufgerufen werden.

### Option B: Browser-based handling (fallback)

Falls API keine `href` zurückgibt → Survey-ID in Dashboard per JS klicken:
```python
# Click survey card via CDP JS
ws.send(json.dumps({
    "method": "Runtime.evaluate",
    "params": {"expression": f"clickSurvey('{survey_id}')"}
}))
# Handle in-page pre-qualifier modal
```

## Implementation

### Change `run_loop()` logic

**Current** (lines ~38-48):
```python
ok_surveys = [s for s in viable if s.get("provider") != "pre_qualifier"]
# ...
if survey.get("provider") == "pre_qualifier":
    continue  # silently skip pre-qualifiers
```

**Fixed**:
```python
for i, survey in enumerate(viable):
    if i >= self.config.max_surveys:
        break

    # Handle pre-qualifiers via CPX API loop
    if survey.get("provider") == "pre_qualifier":
        survey_id = survey["id"]
        # handle_pre_qualifier needs survey_id + survey_details (filter_surveys output)
        survey_details = survey  # has: id, type, href, provider, question_text, answers
        survey_url = self.handle_pre_qualifier(survey_id, survey)
        if survey_url:
            survey = survey.copy()
            survey["href"] = survey_url
            survey["provider"] = "pre_qualifier_answered"
        else:
            print(f"[LOOP] Pre-qualifier failed for {survey_id} → skipping")
            continue
```

### Fix `handle_pre_qualifier()` to work with survey dict

Das Problem: `handle_pre_qualifier()` erwartet `survey_details` als Dict mit `answers`, `question_text`, `question_key`. Aber `filter_surveys()` baut das bereits:

```python
# scanner.py:filter_surveys() setzt:
entry["answers"] = resp.get("answers", {})
entry["question_key"] = resp.get("question_key", "")
entry["message_button"] = resp.get("message_button", "einreichen")
```

Also: `survey` dict aus `filter_surveys()` kann direkt an `handle_pre_qualifier()` übergeben werden.

### Profile data availability

`handle_pre_qualifier()` nutzt `self.profile`:
- `age` → aus `date_of_birth` (bereits in persona.py)
- `gender` ("male"/"female")
- `city` ("Berlin")
- `education` ("abitur"/"meister")
- `employment` ("employed"/"not employed")
- `household_income`, `household_size`

→ Muss in `run_loop()` laden: `self._load_profile()`

## Files to Change

| File | Change | Risk |
|------|--------|------|
| `survey/runner.py` | `run_loop()`: remove skip, call `handle_pre_qualifier()` | Low — existing code, just wiring |
| `survey/runner.py` | `handle_pre_qualifier()`: fix `self.profile` reference | Low — profile already loaded |
| `survey/runner.py` | Add profile loading in `run_loop()` | Low |

## Tests to Add

```python
# tests/test_prequalifier.py (NEW)
class TestHandlePreQualifier:
    def test_returns_href_on_okay_response()
    def test_loops_on_multiple_questions()
    def test_returns_none_on_screen_out()
    def test_returns_none_on_max_retries_exceeded()
    def test_profile_matching_gender()
    def test_profile_matching_age_brackets()
    def test_profile_matching_berlin()

class TestRunLoopPreQualifiers:
    def test_prequalifier_answered_via_api()
    def test_prequalifier_skipped_when_api_fails()
    def test_prequalifier_fallback_to_browser()
    def test_prequalifier_not_counted_twice()
```

## Verification

```bash
# Before: "All 3 surveys are pre-qualifiers (browser-based, skipped)"
# After: Pre-qualifiers answered → real survey URLs obtained
python3 -m survey run --mode loop --max 3 --debug
```

## Estimate

- **Effort**: 2-3h
- **Impact**: +40% survey coverage per loop
- **Risk**: Low (existing code, just calling it)
