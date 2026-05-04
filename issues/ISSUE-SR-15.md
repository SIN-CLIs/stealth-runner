# SR-15: Audio-Capture Integration — BlackHole + Omni

- **Status:** ✅ COMPLETED (modules exist, integrated in survey_runner.py)
- **Priority:** 🟡 High
- **Plan:** [`plans/plan-audio-capture.md`](../plans/plan-audio-capture.md)

## Description

Audio modules (`audio_capture.py`, `audio_box.py`) are fully implemented and integrated into `survey_runner.py`. Audio questions are automatically detected and answered via BlackHole + ffmpeg + NVIDIA Omni.

## Deliverables

- [x] `audio_capture.py` (364 lines) — BlackHole capture + ffmpeg + Omni analysis
- [x] `audio_box.py` (156 lines) — `detect_audio_question()`, `capture_and_analyze()`
- [x] `check_audio_pipeline()` — verifies BlackHole installation
- [x] `_detect_audio_question(pid)` in survey_runner.py (line 36)
- [x] `_handle_audio_question(pid, options)` in survey_runner.py (line 66)
- [x] Called automatically in `prequalify()` flow
- [x] BlackHole not installed → warning + skip
- [x] CLI: `python3 -m cli.modules.audio_capture --capture --analyze`

## Acceptance Criteria

- [x] `_detect_audio_question()` detects `<video>` with blob: URL
- [x] `_handle_audio_question()` captures + analyzes audio
- [x] Integrated in `survey_runner.prequalify()` flow
- [ ] Requires BlackHole + SIP-off for full end-to-end test

## Files

- `cli/modules/audio_capture.py` (364 lines)
- `cli/modules/audio_box.py` (156 lines)
- `cli/modules/survey_runner.py` (lines 36-98, 513-532)
