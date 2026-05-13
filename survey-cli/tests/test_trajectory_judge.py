"""
test_trajectory_judge.py — Unit tests for SR-170 PR1.

Covers:
  - survey.reliability.trajectory_judge:    10 tests
  - survey.reliability.personas_quarantine:  9 tests

All LLM calls are mocked via a plain Callable[[str], str]. No `openai`
package is required at test time. All filesystem operations use the
pytest `tmp_path` fixture for full determinism.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from survey.reliability.personas_quarantine import (
    PersonaNotQuarantined,
    QuarantineEntry,
    is_quarantined,
    list_active,
    quarantine,
    release,
)
from survey.reliability.personas_quarantine import (
    get as quarantine_get,
)
from survey.reliability.trajectory_judge import (
    SCORE_FIELDS,
    JudgeConfig,
    JudgeEmptyTrajectoryError,
    JudgeParseError,
    JudgeRangeError,
    JudgeScoreCard,
    TrajectoryJudge,
)


# ── HELPERS ──────────────────────────────────────────────────────────────────


_FAKE_PROMPT = "AUDIT PROMPT — do the thing."

_GOOD_TRAJECTORY: list[dict[str, Any]] = [
    {"step": 0, "page": "q1", "answer": "yes"},
    {"step": 1, "page": "q2", "answer": "blue"},
    {"step": 2, "page": "q3", "answer": "agree"},
]


def _make_judge(response: str, *, config: JudgeConfig | None = None) -> TrajectoryJudge:
    """Build a judge that always returns the given fixed response string."""
    return TrajectoryJudge(
        llm_callable=lambda _prompt: response,
        prompt=_FAKE_PROMPT,
        config=config or JudgeConfig(),
        model_name="mock",
    )


def _good_response(
    compliance: float = 0.9,
    efficiency: float = 0.8,
    accuracy: float = 0.85,
    coherence: float = 0.95,
    rationale: str = "looks fine.",
) -> str:
    return json.dumps(
        {
            "compliance": compliance,
            "efficiency": efficiency,
            "accuracy": accuracy,
            "coherence": coherence,
            "rationale": rationale,
        }
    )


# =============================================================================
# TRAJECTORY JUDGE TESTS
# =============================================================================


def test_audit_returns_scorecard_with_four_fields() -> None:
    """audit() must return a JudgeScoreCard with all four canonical scores."""
    judge = _make_judge(_good_response())
    card = judge.audit(_GOOD_TRAJECTORY)
    assert isinstance(card, JudgeScoreCard)
    for f in SCORE_FIELDS:
        assert hasattr(card, f), f"missing score field {f}"
    assert card.compliance == 0.9
    assert card.efficiency == 0.8
    assert card.accuracy == 0.85
    assert card.coherence == 0.95
    assert card.rationale == "looks fine."


def test_audit_parses_plain_json_response() -> None:
    """A bare JSON object (no markdown) must parse cleanly."""
    judge = _make_judge(
        '{"compliance": 0.5, "efficiency": 0.6, "accuracy": 0.7, "coherence": 0.8, "rationale": "ok"}'
    )
    card = judge.audit(_GOOD_TRAJECTORY)
    assert card.compliance == 0.5
    assert card.coherence == 0.8


def test_audit_strips_markdown_code_fence() -> None:
    """LLMs love wrapping JSON in ```json fences; we must tolerate that."""
    wrapped = (
        "```json\n"
        '{"compliance": 0.4, "efficiency": 0.4, "accuracy": 0.4, '
        '"coherence": 0.4, "rationale": "wrapped"}\n'
        "```"
    )
    judge = _make_judge(wrapped)
    card = judge.audit(_GOOD_TRAJECTORY)
    assert card.compliance == 0.4
    assert card.rationale == "wrapped"


def test_audit_raises_on_invalid_json() -> None:
    """Garbage from the LLM must raise JudgeParseError, not crash."""
    judge = _make_judge("definitely not json {{{")
    with pytest.raises(JudgeParseError):
        judge.audit(_GOOD_TRAJECTORY)


def test_audit_raises_on_missing_score_field() -> None:
    """If the LLM omits one of the 4 required score fields → JudgeParseError."""
    judge = _make_judge(
        '{"compliance": 0.9, "efficiency": 0.9, "accuracy": 0.9, "rationale": "missing coherence"}'
    )
    with pytest.raises(JudgeParseError, match="coherence"):
        judge.audit(_GOOD_TRAJECTORY)


def test_audit_raises_on_out_of_range_score() -> None:
    """Score outside [0.0, 1.0] → JudgeRangeError."""
    judge = _make_judge(_good_response(compliance=1.5))
    with pytest.raises(JudgeRangeError, match="compliance"):
        judge.audit(_GOOD_TRAJECTORY)


def test_audit_raises_on_non_numeric_score() -> None:
    """Non-numeric score (e.g. string label) → JudgeRangeError."""
    judge = _make_judge(
        '{"compliance": "high", "efficiency": 0.8, "accuracy": 0.8, '
        '"coherence": 0.8, "rationale": "bad"}'
    )
    with pytest.raises(JudgeRangeError, match="compliance"):
        judge.audit(_GOOD_TRAJECTORY)


def test_audit_raises_on_nan_score() -> None:
    """NaN must be rejected even though it's technically a float."""
    judge = _make_judge(
        # JSON doesn't natively support NaN; we synthesize a value the parser
        # turns into nan via "Infinity" trick — but standard json rejects that.
        # Easier route: feed a parseable-but-NaN value through a custom path.
        # Use Python json with allow_nan=True roundtrip is unavailable in pure
        # JSON. Instead, mock the response to be JSON5-style "NaN" which the
        # stdlib's json.loads can actually parse — it accepts "NaN" non-spec.
        '{"compliance": NaN, "efficiency": 0.8, "accuracy": 0.8, '
        '"coherence": 0.8, "rationale": "bad"}'
    )
    with pytest.raises(JudgeRangeError, match="NaN"):
        judge.audit(_GOOD_TRAJECTORY)


def test_audit_raises_on_empty_trajectory() -> None:
    """Empty list must raise before any LLM call."""
    judge = _make_judge(_good_response())
    with pytest.raises(JudgeEmptyTrajectoryError):
        judge.audit([])


def test_audit_records_latency_and_prompt_hash() -> None:
    """ScoreCard must carry latency_ms ≥ 0 and a non-empty prompt_hash."""
    judge = _make_judge(_good_response())
    card = judge.audit(_GOOD_TRAJECTORY)
    assert card.latency_ms >= 0
    assert card.latency_ms < 1000  # mock callable is instant
    assert len(card.prompt_hash) == 16
    assert all(c in "0123456789abcdef" for c in card.prompt_hash)
    assert card.model == "mock"


def test_scorecard_min_mean_and_frozen() -> None:
    """min_score()/mean_score() helpers + frozen-dataclass invariant."""
    card = JudgeScoreCard(
        compliance=0.4, efficiency=0.6, accuracy=0.8, coherence=1.0, rationale=""
    )
    assert card.min_score() == pytest.approx(0.4)
    assert card.mean_score() == pytest.approx(0.7)
    # Frozen → assignment must fail. dataclasses raises FrozenInstanceError
    # which is a subclass of AttributeError, so catching either is fine.
    with pytest.raises((AttributeError, TypeError, Exception)):
        card.compliance = 0.0  # type: ignore[misc]


def test_judge_rejects_empty_prompt_in_constructor() -> None:
    """Constructing with whitespace-only prompt must raise."""
    with pytest.raises(ValueError):
        TrajectoryJudge(
            llm_callable=lambda _p: _good_response(),
            prompt="   \n  ",
        )


def test_require_rationale_can_be_disabled() -> None:
    """With require_rationale=False, omitting the rationale must NOT raise."""
    cfg = JudgeConfig(require_rationale=False)
    judge = _make_judge(
        '{"compliance": 0.7, "efficiency": 0.7, "accuracy": 0.7, "coherence": 0.7}',
        config=cfg,
    )
    card = judge.audit(_GOOD_TRAJECTORY)
    assert card.rationale == ""


# =============================================================================
# PERSONA QUARANTINE TESTS
# =============================================================================


def test_quarantine_creates_entry_file(tmp_path: Path) -> None:
    """quarantine() must produce a readable JSON at <root>/<id>.json."""
    entry = quarantine(
        "p-001",
        reason="judge below threshold",
        judge_scores={"compliance": 0.2},
        store_root=tmp_path,
        now=1_700_000_000,
    )
    target = tmp_path / "p-001.json"
    assert target.is_file()
    on_disk = json.loads(target.read_text("utf-8"))
    assert on_disk["persona_id"] == "p-001"
    assert on_disk["reason"] == "judge below threshold"
    assert on_disk["quarantined_at"] == 1_700_000_000
    assert on_disk["released_at"] is None
    assert entry.is_active()


def test_is_quarantined_lifecycle(tmp_path: Path) -> None:
    """False → quarantine → True → release → False."""
    assert is_quarantined("p-002", store_root=tmp_path) is False
    quarantine("p-002", reason="drift", store_root=tmp_path, now=10)
    assert is_quarantined("p-002", store_root=tmp_path) is True
    release("p-002", override_reason="manual review ok", store_root=tmp_path, now=20)
    assert is_quarantined("p-002", store_root=tmp_path) is False


def test_list_active_sorted_by_quarantined_at(tmp_path: Path) -> None:
    """list_active() must return entries ordered by quarantined_at ASC."""
    quarantine("p-late", reason="r", store_root=tmp_path, now=300)
    quarantine("p-early", reason="r", store_root=tmp_path, now=100)
    quarantine("p-mid", reason="r", store_root=tmp_path, now=200)
    actives = list_active(store_root=tmp_path)
    assert [e.persona_id for e in actives] == ["p-early", "p-mid", "p-late"]
    # And after releasing one, it must vanish from the list.
    release("p-mid", override_reason="ok", store_root=tmp_path, now=400)
    actives = list_active(store_root=tmp_path)
    assert [e.persona_id for e in actives] == ["p-early", "p-late"]


def test_release_raises_for_non_quarantined(tmp_path: Path) -> None:
    """release() on an id that was never quarantined → PersonaNotQuarantined."""
    with pytest.raises(PersonaNotQuarantined):
        release("never-existed", override_reason="x", store_root=tmp_path)


def test_release_raises_when_already_released(tmp_path: Path) -> None:
    """release() twice → second call raises PersonaNotQuarantined."""
    quarantine("p-twice", reason="r", store_root=tmp_path, now=10)
    release("p-twice", override_reason="first", store_root=tmp_path, now=20)
    with pytest.raises(PersonaNotQuarantined):
        release("p-twice", override_reason="second", store_root=tmp_path, now=30)


def test_quarantine_idempotent_preserves_original_timestamp(tmp_path: Path) -> None:
    """
    Re-quarantining an already-active id must keep the original
    quarantined_at (so we don't reset audit history when caller updates
    the reason).
    """
    quarantine("p-rq", reason="first", store_root=tmp_path, now=1000)
    second = quarantine(
        "p-rq",
        reason="updated reason",
        judge_scores={"min": 0.1},
        store_root=tmp_path,
        now=9999,
    )
    assert second.quarantined_at == 1000  # NOT 9999
    assert second.reason == "updated reason"
    assert second.judge_scores == {"min": 0.1}


def test_entry_json_roundtrip_preserves_all_fields(tmp_path: Path) -> None:
    """Quarantine → release → re-read must preserve every field byte-faithfully."""
    quarantine(
        "p-rt",
        reason="r-reason",
        judge_scores={"compliance": 0.3, "rationale": "low"},
        store_root=tmp_path,
        now=42,
    )
    release("p-rt", override_reason="manual", store_root=tmp_path, now=99)
    got = quarantine_get("p-rt", store_root=tmp_path)
    assert got.persona_id == "p-rt"
    assert got.reason == "r-reason"
    assert got.judge_scores == {"compliance": 0.3, "rationale": "low"}
    assert got.quarantined_at == 42
    assert got.released_at == 99
    assert got.release_reason == "manual"
    assert got.schema_version >= 1


def test_quarantine_entry_is_frozen() -> None:
    """QuarantineEntry must be immutable to prevent post-hoc audit tampering."""
    e = QuarantineEntry(persona_id="x", reason="y", quarantined_at=1)
    with pytest.raises((AttributeError, TypeError, Exception)):
        e.reason = "tampered"  # type: ignore[misc]


def test_persona_id_with_slashes_and_spaces_is_sanitized(tmp_path: Path) -> None:
    """
    persona_ids containing '/' or whitespace must be sanitized to safe filenames.
    The sanitizer replaces those chars with '_'.
    """
    entry = quarantine(
        "weird id/with slashes",  # No leading dots
        reason="r",
        store_root=tmp_path,
        now=1,
    )
    # The file must live inside tmp_path (not escape it).
    files = list(tmp_path.glob("*.json"))
    assert len(files) == 1
    assert files[0].parent == tmp_path
    # And the entry can be looked up by the same (un-sanitized) id, because
    # the sanitization is deterministic.
    assert is_quarantined("weird id/with slashes", store_root=tmp_path) is True
    assert entry.persona_id == "weird id/with slashes"  # stored verbatim in JSON


def test_persona_id_starting_with_dot_raises_valueerror(tmp_path: Path) -> None:
    """
    persona_ids that sanitize to a filename starting with '.' must raise
    ValueError to prevent hidden files (security concern).
    """
    with pytest.raises(ValueError, match="sanitizes to empty/hidden filename"):
        quarantine(
            "../weird id",  # After sanitization: '..weird_id' starts with '.'
            reason="r",
            store_root=tmp_path,
            now=1,
        )
