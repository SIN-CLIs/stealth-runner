# SR-150 — Extended Question-Type Support (drag-drop, hotspot, conjoint, max-diff, video-ad, audio-ad)

## Context

`AnswerEngine` currently dispatches 11 question types in `_generate_by_type`:
RADIO, CHECKBOX, SLIDER, DROPDOWN, OPEN_TEXT, MATRIX, NUMBER, DATE, LIKERT, NPS, RANKING.

Real-world heypiggy.com surveys (after redirects to Lucid, Cint, Toluna, Dynata, PureSpectrum panels) include question types currently **routed to `_generate_default_answer`** which is a brittle fallback. These are: drag-and-drop ranking, image hotspot, conjoint choice, MaxDiff (best/worst), video-ad attention (must play N seconds), audio-ad attention. When the default-fallback fires, the runner produces low-quality answers and gets disqualified — directly hurting completion-rate.

## Goal

Add 6 new `QuestionType` enum members + 6 new `_generate_*_answer` methods + 6 new parser detectors. After this lands, the agent solves all question types observed across the top-5 panel providers without falling through to `_generate_default_answer`.

## Files

### NEW (1)
- `survey-cli/tests/test_answer_engine_extended_types.py` — 24+ unit tests (4 per new type)

### MODIFY (3, all surgical)
- `survey-cli/survey/daemon/survey_parser.py`
  - Extend `QuestionType` enum with `DRAG_DROP`, `HOTSPOT`, `CONJOINT`, `MAX_DIFF`, `VIDEO_AD`, `AUDIO_AD`
  - Extend `SurveyParser._detect_question_type` heuristics with selectors / DOM signatures for each new type
- `survey-cli/survey/daemon/answer_engine.py`
  - Add 6 new `_generate_*_answer` methods following the existing pattern (deterministic hash → option weights → store in SQLite)
  - Register all 6 in the `generators` dict inside `_generate_by_type`
- `survey-cli/survey/daemon/browser_driver.py`
  - Add `drag_element(source_sel, target_sel)` + `play_media(sel, seconds)` primitives (CDP-based, no Playwright API leaks)

## Question-Type Specs

### 1. DRAG_DROP (drag-to-rank, drag-to-bucket)
- **Detection:** `[draggable="true"]`, `ui-sortable`, `react-beautiful-dnd-draggable`, `.sortable-handle`, `data-rbd-draggable-id`
- **Answer strategy:** Persona-weighted ordering, deterministic via `hash(question_id + persona_id)`
- **Browser primitive:** `drag_element(source, target)` — CDP `Input.dispatchMouseEvent` with `mouseDown` → `mouseMoved` (10-step path with timing jitter) → `mouseUp`

### 2. HOTSPOT (click image regions)
- **Detection:** `<img>` + sibling `<map>`, `[data-hotspot]`, `clickable-image`, Qualtrics `QID*` hotspot wrappers
- **Answer strategy:** Click center of the "most-likely-intended" region (use NVIDIA Nemotron Vision to identify regions if available, else pick centroid of the largest hotspot)
- **Browser primitive:** `click_at(x, y)` already exists — wire it to hotspot picker

### 3. CONJOINT (Sawtooth-style A vs B vs C choice cards)
- **Detection:** N profile-cards in a row with checkboxes/radios "Choose this product"; `[data-conjoint-task]`; Sawtooth `<form name="ConjointForm">`
- **Answer strategy:** Score each card by persona-preference-features (price-sensitive, brand-loyal, etc.), pick highest score
- Persona JSON now needs a `conjoint_preferences` block (price_weight, brand_weight, feature_weights) — add to all 4 existing profiles

### 4. MAX_DIFF (best/worst scaling, 3-7 items per task)
- **Detection:** Two adjacent radio columns labeled "Most" / "Least" (English) or "Am meisten" / "Am wenigsten" (German), `[data-maxdiff]`
- **Answer strategy:** Rank persona-relevance of items, pick rank-1 as "Most" + rank-N as "Least"
- One Answer record stores both selections

### 5. VIDEO_AD (must-watch attention)
- **Detection:** `<video>` element + "Continue" button disabled until video ends, or `data-min-watch-seconds`
- **Answer strategy:** Read `video.duration` via CDP `Runtime.evaluate`, play with `media.play()`, wait `duration + 0.5s` jitter, then click Continue
- Defensive: if duration > 120s, log warning and proceed (some surveys have skippable long ads)
- **Browser primitive:** `play_media(selector, seconds=None)` — if seconds is None, waits for `ended` event

### 6. AUDIO_AD (must-listen attention)
- **Detection:** `<audio>` element + locked Continue button
- **Answer strategy:** Same as VIDEO_AD but for `<audio>` tag
- Mute the audio via `audio.muted = true` before play (no noise on host)

## Acceptance Criteria

### Parser (survey_parser.py)
- [ ] `QuestionType` enum has 6 new members in proper alphabetical/grouped order
- [ ] `SurveyParser._detect_question_type` returns each new type for at least 2 distinct selector signatures (e.g. DRAG_DROP for both `[draggable="true"]` and `data-rbd-draggable-id`)
- [ ] No regression: all 11 existing types still detected correctly

### Answer engine (answer_engine.py)
- [ ] 6 new private methods present, following naming `_generate_<type>_answer(question, question_hash) -> Answer`
- [ ] `_generate_by_type` `generators` dict has all 6 new entries
- [ ] Each method writes to the SQLite history table via `_store_answer` so consistency-checks across panels work
- [ ] Each method uses `hash(persona_id + question_hash)` as randomness seed → same persona always answers same question identically

### Browser driver (browser_driver.py)
- [ ] `drag_element(source_sel: str, target_sel: str, jitter: bool = True) -> bool` — returns success
- [ ] `play_media(selector: str, max_seconds: float | None = None) -> float` — returns actual seconds played
- [ ] Both use CDP raw calls; no Playwright `page.mouse.down()` calls (matches existing pattern)

### Persona JSON (4 profiles)
- [ ] `conjoint_preferences` block added to each of: `anna_meyer.json`, `jeremy_schulze.json`, `sin_agent_heypiggy.json`, `thomas_weber.json`
- [ ] Block schema: `{"price_weight": float, "brand_weight": float, "feature_weights": {feature_name: float}}` — weights sum to 1.0

### Tests (test_answer_engine_extended_types.py)
- [ ] 24+ tests total, ≥ 4 per new type:
  - 1 happy-path (parser detects + engine generates)
  - 1 determinism (same input → same output, 100 runs)
  - 1 persona-consistency (same persona+question → same answer across calls)
  - 1 edge-case (empty options / missing video duration / etc.)
- [ ] No real browser launch — use `unittest.mock` for `browser_driver` primitives

### Quality
- [ ] ruff clean (E,W,F line-length 100, py312 target)
- [ ] No new pip deps
- [ ] Closes #150 in commit + PR body
- [ ] Branch: `feat/150-extended-question-types`

## Out of Scope

- New question types beyond the 6 listed (semantic-differential, constant-sum, card-sort → future SR-153+)
- CDP infrastructure changes outside browser_driver (cdp_client.py untouched)
- Anti-detection / proxy work (SR-151 owns that)
- Reliability hardening (SR-152 owns that)
- New providers (none of the 7 existing adapters change)

## References

- Existing parser: https://raw.githubusercontent.com/SIN-CLIs/stealth-runner/main/survey-cli/survey/daemon/survey_parser.py
- Existing engine: https://raw.githubusercontent.com/SIN-CLIs/stealth-runner/main/survey-cli/survey/daemon/answer_engine.py
- Existing browser driver: https://raw.githubusercontent.com/SIN-CLIs/stealth-runner/main/survey-cli/survey/daemon/browser_driver.py
- Personas dir: https://github.com/SIN-CLIs/stealth-runner/tree/main/survey-cli/survey/profiles

## Parallel-Safety

Zero file overlap with SR-151 (proxy/anti-detection) or SR-152 (reliability/DLQ). All 3 can land any order.

## Dependencies

None. Start immediately.
