"""
Post-action verifier (SR-167).

Runs *between* ``_answer`` and ``_submit`` in ``SurveyAgentGraph``. Reads the
live DOM state and confirms each ``Answer`` actually landed before the page is
submitted. Without this, silent mis-clicks (wrong radio resolved by selector
collision, dropdown that snapped back, slider that didn't fire ``change``)
slip downstream and corrupt entire sessions.

Contract:
    * One ``SnapshotV2`` taken before ``_answer`` (``snapshot_before``).
    * One ``SnapshotV2`` taken inside the verifier (``snapshot_after``).
    * Per-question verification dispatched on ``QuestionType``.
    * Result is JSON-serializable (AgentState is TypedDict-of-primitives).

NOT in scope here (handled elsewhere):
    * Retry orchestration — verifier returns a result, the graph node decides.
    * DLQ writes — graph node calls ``reliability.dlq`` on terminal failure.
    * Skip-on-stable-hash — Phase 2 (#168) reads ``page_hash`` from the result.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

from ..snapshot_v2 import SnapshotV2, QuestionFrame
from .survey_parser import Question, QuestionType
from .answer_engine import Answer

logger = logging.getLogger(__name__)


class _DriverProto(Protocol):
    async def evaluate(self, js: str) -> Any: ...  # noqa: E704


# --------------------------------------------------------------------------- #
# Result types
# --------------------------------------------------------------------------- #


@dataclass
class Mismatch:
    question_id: str
    qtype: str
    expected: Any
    actual: Any
    reason: str  # "not_checked" | "wrong_value" | "missing_control" | "wrong_set" | "text_mismatch" | "out_of_range"

    def to_dict(self) -> dict:
        return {
            "question_id": self.question_id,
            "qtype": self.qtype,
            "expected": self.expected,
            "actual": self.actual,
            "reason": self.reason,
        }


@dataclass
class VerificationResult:
    success: bool
    attempt: int
    mismatches: list[Mismatch] = field(default_factory=list)
    dom_unstable: bool = False  # snapshot_before.page_hash == snapshot_after.page_hash AND we expected change
    page_hash_before: str | None = None
    page_hash_after: str | None = None
    # qids whose subtree_hash is unchanged vs. snapshot_before (Phase 2 #168 input)
    unchanged_qids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "attempt": self.attempt,
            "mismatches": [m.to_dict() for m in self.mismatches],
            "dom_unstable": self.dom_unstable,
            "page_hash_before": self.page_hash_before,
            "page_hash_after": self.page_hash_after,
            "unchanged_qids": self.unchanged_qids,
        }


# --------------------------------------------------------------------------- #
# Per-type verifier strategies
# --------------------------------------------------------------------------- #


def _checked_values(frame: QuestionFrame | None) -> list[str]:
    if frame is None:
        return []
    return [str(c.get("value")) for c in frame.controls if c.get("checked")]


def _first_value(frame: QuestionFrame | None) -> str | None:
    if frame is None or not frame.controls:
        return None
    # Prefer a checked control's value, else the first non-empty value
    for c in frame.controls:
        if c.get("checked"):
            return str(c.get("value")) if c.get("value") is not None else None
    for c in frame.controls:
        v = c.get("value")
        if v not in (None, ""):
            return str(v) if not isinstance(v, list) else (str(v[0]) if v else None)
    return None


def _verify_radio(q: Question, a: Answer, frame: QuestionFrame | None) -> Mismatch | None:
    if frame is None:
        return Mismatch(q.id, q.type.value, a.value, None, "missing_control")
    checked = _checked_values(frame)
    if not checked:
        return Mismatch(q.id, q.type.value, a.value, None, "not_checked")
    if str(a.value) not in checked:
        return Mismatch(q.id, q.type.value, a.value, checked, "wrong_value")
    return None


def _verify_checkbox(q: Question, a: Answer, frame: QuestionFrame | None) -> Mismatch | None:
    if frame is None:
        return Mismatch(q.id, q.type.value, a.value, None, "missing_control")
    expected = a.value if isinstance(a.value, list) else [a.value]
    expected_set = {str(v) for v in expected}
    actual_set = set(_checked_values(frame))
    if expected_set != actual_set:
        return Mismatch(q.id, q.type.value, sorted(expected_set), sorted(actual_set), "wrong_set")
    return None


def _verify_dropdown(q: Question, a: Answer, frame: QuestionFrame | None) -> Mismatch | None:
    if frame is None:
        return Mismatch(q.id, q.type.value, a.value, None, "missing_control")
    actual = _first_value(frame)
    if actual is None or actual != str(a.value):
        return Mismatch(q.id, q.type.value, a.value, actual, "wrong_value")
    return None


def _verify_open_text(q: Question, a: Answer, frame: QuestionFrame | None) -> Mismatch | None:
    if frame is None:
        return Mismatch(q.id, q.type.value, a.value, None, "missing_control")
    actual = _first_value(frame) or ""
    expected = str(a.value)
    # Tolerant compare: trim + lowercase. Survey UIs sometimes echo with stripped whitespace.
    if expected.strip().lower() != actual.strip().lower():
        # Accept "starts with" for autocomplete-style fields where suggestion text appends.
        if not actual.strip().lower().startswith(expected.strip().lower()):
            return Mismatch(q.id, q.type.value, expected, actual, "text_mismatch")
    return None


def _verify_numeric(q: Question, a: Answer, frame: QuestionFrame | None) -> Mismatch | None:
    if frame is None:
        return Mismatch(q.id, q.type.value, a.value, None, "missing_control")
    actual = _first_value(frame)
    try:
        if actual is None or float(actual) != float(a.value):
            return Mismatch(q.id, q.type.value, a.value, actual, "wrong_value")
    except (TypeError, ValueError):
        return Mismatch(q.id, q.type.value, a.value, actual, "out_of_range")
    return None


# Map QuestionType.value -> verifier callable. Unknown types fall back to a
# "frame must exist and changed" heuristic (handled in verify_action).
_VERIFIERS: dict[str, Any] = {
    QuestionType.RADIO.value: _verify_radio,
    QuestionType.CHECKBOX.value: _verify_checkbox,
    QuestionType.DROPDOWN.value: _verify_dropdown,
    QuestionType.OPEN_TEXT.value: _verify_open_text,
    QuestionType.SLIDER.value: _verify_numeric,
    QuestionType.NUMBER.value: _verify_numeric,
}


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #


def verify_action(
    questions: list[Question],
    answers: list[Answer],
    snapshot_before: SnapshotV2 | None,
    snapshot_after: SnapshotV2,
    attempt: int = 1,
) -> VerificationResult:
    """
    Inspect ``snapshot_after`` against the intended ``answers`` per question.

    ``snapshot_before`` is optional but recommended: it's used to detect
    "DOM didn't change at all" (likely a no-op click on a stale selector) and
    to surface ``unchanged_qids`` for Phase 2 skip logic (#168).
    """
    by_id = {a.question_id: a for a in answers}
    mismatches: list[Mismatch] = []

    for q in questions:
        a = by_id.get(q.id)
        if a is None:
            # No answer attempted — verifier doesn't fail here; the answer
            # engine is responsible for coverage. Skip silently.
            continue

        frame = snapshot_after.frame(q.id)
        verifier = _VERIFIERS.get(q.type.value)
        if verifier is None:
            # Unknown type: at minimum the frame must exist.
            if frame is None:
                mismatches.append(Mismatch(q.id, q.type.value, a.value, None, "missing_control"))
            continue

        m = verifier(q, a, frame)
        if m is not None:
            mismatches.append(m)

    # DOM-stability signal
    unchanged: list[str] = []
    dom_unstable = False
    if snapshot_before is not None:
        diff = snapshot_after.diff_hashes(snapshot_before)
        # qids that we tried to answer but whose subtree didn't change at all
        attempted_qids = {q.id for q in questions if q.id in by_id}
        unchanged = sorted(attempted_qids - diff)
        # If we attempted ANY answer and NOTHING in the DOM moved, the action
        # never landed — treat as DOM-unstable / no-op.
        if attempted_qids and not diff:
            dom_unstable = True

    result = VerificationResult(
        success=(not mismatches and not dom_unstable),
        attempt=attempt,
        mismatches=mismatches,
        dom_unstable=dom_unstable,
        page_hash_before=snapshot_before.page_hash if snapshot_before else None,
        page_hash_after=snapshot_after.page_hash,
        unchanged_qids=unchanged,
    )

    if not result.success:
        logger.warning(
            "verifier: attempt=%d success=False mismatches=%d dom_unstable=%s",
            attempt, len(mismatches), dom_unstable,
        )
    else:
        logger.info("verifier: attempt=%d success=True", attempt)

    return result


__all__ = ["verify_action", "VerificationResult", "Mismatch"]
