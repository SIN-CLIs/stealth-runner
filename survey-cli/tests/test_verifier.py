"""
Tests for SR-167 post-action verifier.

Covers:
    * Per-QuestionType happy paths (RADIO, CHECKBOX, DROPDOWN, OPEN_TEXT, SLIDER, NUMBER)
    * Mismatch detection for each type
    * dom_unstable signal when snapshot_before == snapshot_after
    * unchanged_qids surfacing for Phase 2 (#168)
    * VerificationResult round-trip via to_dict()
"""

from __future__ import annotations

import pytest

from survey.snapshot_v2 import from_controls
from survey.daemon.survey_parser import Question, QuestionType, QuestionOption
from survey.daemon.answer_engine import Answer
from survey.daemon.verifier import verify_action, Mismatch, VerificationResult


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


def _q(qid: str, qtype: QuestionType, opts: list[tuple[str, str]] | None = None) -> Question:
    options = [QuestionOption(value=v, label=lbl) for v, lbl in (opts or [])]
    return Question(id=qid, type=qtype, text=qid, options=options, required=True, element_selector=None)


def _radio_controls(qid: str, checked_value: str | None, all_values: list[str]) -> list[dict]:
    return [
        {
            "qid": qid, "tag": "input", "type": "radio", "role": "radio",
            "name": qid, "value": v, "checked": (v == checked_value),
            "selected": None, "disabled": False, "visible": True,
        }
        for v in all_values
    ]


def _checkbox_controls(qid: str, checked_values: list[str], all_values: list[str]) -> list[dict]:
    return [
        {
            "qid": qid, "tag": "input", "type": "checkbox", "role": "checkbox",
            "name": qid, "value": v, "checked": (v in checked_values),
            "selected": None, "disabled": False, "visible": True,
        }
        for v in all_values
    ]


def _dropdown_controls(qid: str, value: str) -> list[dict]:
    return [{
        "qid": qid, "tag": "select", "type": "select-one", "role": "select",
        "name": qid, "value": value, "checked": None,
        "selected": [value], "disabled": False, "visible": True,
    }]


def _text_controls(qid: str, value: str) -> list[dict]:
    return [{
        "qid": qid, "tag": "input", "type": "text", "role": "input",
        "name": qid, "value": value, "checked": None,
        "selected": None, "disabled": False, "visible": True,
    }]


def _slider_controls(qid: str, value: str) -> list[dict]:
    return [{
        "qid": qid, "tag": "input", "type": "range", "role": "slider",
        "name": qid, "value": value, "checked": None,
        "selected": None, "disabled": False, "visible": True,
    }]


# --------------------------------------------------------------------------- #
# Happy paths
# --------------------------------------------------------------------------- #


def test_radio_match_passes():
    q = _q("q1", QuestionType.RADIO, [("a", "A"), ("b", "B")])
    a = Answer(question_id="q1", value="a", confidence=0.9)
    before = from_controls("u", _radio_controls("q1", None, ["a", "b"]))
    after = from_controls("u", _radio_controls("q1", "a", ["a", "b"]))

    result = verify_action([q], [a], before, after)

    assert result.success is True
    assert result.mismatches == []
    assert result.dom_unstable is False


def test_checkbox_set_match_passes():
    q = _q("q1", QuestionType.CHECKBOX, [("a", "A"), ("b", "B"), ("c", "C")])
    a = Answer(question_id="q1", value=["a", "c"], confidence=0.9)
    before = from_controls("u", _checkbox_controls("q1", [], ["a", "b", "c"]))
    after = from_controls("u", _checkbox_controls("q1", ["a", "c"], ["a", "b", "c"]))

    result = verify_action([q], [a], before, after)

    assert result.success is True


def test_dropdown_match_passes():
    q = _q("q1", QuestionType.DROPDOWN, [("us", "US"), ("de", "DE")])
    a = Answer(question_id="q1", value="de", confidence=0.9)
    before = from_controls("u", _dropdown_controls("q1", ""))
    after = from_controls("u", _dropdown_controls("q1", "de"))

    assert verify_action([q], [a], before, after).success is True


def test_open_text_match_passes():
    q = _q("q1", QuestionType.OPEN_TEXT)
    a = Answer(question_id="q1", value="hello world", confidence=0.9)
    before = from_controls("u", _text_controls("q1", ""))
    after = from_controls("u", _text_controls("q1", "Hello World"))  # case/whitespace tolerant

    assert verify_action([q], [a], before, after).success is True


def test_open_text_autocomplete_prefix_match_passes():
    """Some UIs append autocomplete suggestion text; verifier accepts startswith."""
    q = _q("q1", QuestionType.OPEN_TEXT)
    a = Answer(question_id="q1", value="berl", confidence=0.9)
    before = from_controls("u", _text_controls("q1", ""))
    after = from_controls("u", _text_controls("q1", "berlin, germany"))

    assert verify_action([q], [a], before, after).success is True


def test_slider_numeric_match_passes():
    q = _q("q1", QuestionType.SLIDER)
    a = Answer(question_id="q1", value=7, confidence=0.9)
    before = from_controls("u", _slider_controls("q1", "0"))
    after = from_controls("u", _slider_controls("q1", "7"))

    assert verify_action([q], [a], before, after).success is True


def test_number_match_passes():
    q = _q("q1", QuestionType.NUMBER)
    a = Answer(question_id="q1", value=42, confidence=0.9)
    before = from_controls("u", _text_controls("q1", ""))
    after = from_controls("u", _text_controls("q1", "42"))

    assert verify_action([q], [a], before, after).success is True


# --------------------------------------------------------------------------- #
# Mismatch detection
# --------------------------------------------------------------------------- #


def test_radio_wrong_value_detected():
    q = _q("q1", QuestionType.RADIO, [("a", "A"), ("b", "B")])
    a = Answer(question_id="q1", value="a", confidence=0.9)
    before = from_controls("u", _radio_controls("q1", None, ["a", "b"]))
    after = from_controls("u", _radio_controls("q1", "b", ["a", "b"]))  # wrong one checked

    result = verify_action([q], [a], before, after)

    assert result.success is False
    assert len(result.mismatches) == 1
    assert result.mismatches[0].reason == "wrong_value"
    assert result.mismatches[0].expected == "a"


def test_radio_not_checked_detected():
    q = _q("q1", QuestionType.RADIO, [("a", "A"), ("b", "B")])
    a = Answer(question_id="q1", value="a", confidence=0.9)
    before = from_controls("u", _radio_controls("q1", None, ["a", "b"]))
    after = from_controls("u", _radio_controls("q1", None, ["a", "b"]))  # NOTHING checked

    result = verify_action([q], [a], before, after)

    assert result.success is False
    # Either "not_checked" OR dom_unstable (because page_hash matches) — both are valid failures.
    assert (any(m.reason == "not_checked" for m in result.mismatches)) or result.dom_unstable


def test_checkbox_wrong_set_detected():
    q = _q("q1", QuestionType.CHECKBOX, [("a", "A"), ("b", "B"), ("c", "C")])
    a = Answer(question_id="q1", value=["a", "c"], confidence=0.9)
    before = from_controls("u", _checkbox_controls("q1", [], ["a", "b", "c"]))
    after = from_controls("u", _checkbox_controls("q1", ["a", "b"], ["a", "b", "c"]))  # b instead of c

    result = verify_action([q], [a], before, after)

    assert result.success is False
    assert result.mismatches[0].reason == "wrong_set"


def test_missing_control_detected():
    q = _q("q_missing", QuestionType.RADIO, [("a", "A")])
    a = Answer(question_id="q_missing", value="a", confidence=0.9)
    before = from_controls("u", [])
    after = from_controls("u", [])  # frame for q_missing never appears

    result = verify_action([q], [a], before, after)

    assert result.success is False
    assert result.mismatches[0].reason == "missing_control"


def test_number_out_of_range_detected():
    q = _q("q1", QuestionType.NUMBER)
    a = Answer(question_id="q1", value=10, confidence=0.9)
    before = from_controls("u", _text_controls("q1", ""))
    after = from_controls("u", _text_controls("q1", "not-a-number"))

    result = verify_action([q], [a], before, after)

    assert result.success is False
    assert result.mismatches[0].reason == "out_of_range"


# --------------------------------------------------------------------------- #
# DOM stability signal
# --------------------------------------------------------------------------- #


def test_dom_unstable_when_no_change_at_all():
    """If we tried to answer but page_hash_before == page_hash_after, the action never landed."""
    q = _q("q1", QuestionType.RADIO, [("a", "A")])
    a = Answer(question_id="q1", value="a", confidence=0.9)
    # Both snapshots identical → no DOM movement
    same = _radio_controls("q1", None, ["a"])
    before = from_controls("u", same)
    after = from_controls("u", same)

    result = verify_action([q], [a], before, after)

    assert result.dom_unstable is True
    assert result.success is False


def test_unchanged_qids_reported_for_phase2():
    """qids that we answered but whose subtree didn't shift go into unchanged_qids."""
    q1 = _q("q1", QuestionType.RADIO, [("a", "A")])
    q2 = _q("q2", QuestionType.RADIO, [("x", "X")])
    a1 = Answer(question_id="q1", value="a", confidence=0.9)
    a2 = Answer(question_id="q2", value="x", confidence=0.9)

    before = from_controls("u",
        _radio_controls("q1", None, ["a"]) + _radio_controls("q2", None, ["x"]))
    # q1 moved (a got checked), q2 still untouched
    after = from_controls("u",
        _radio_controls("q1", "a", ["a"]) + _radio_controls("q2", None, ["x"]))

    result = verify_action([q1, q2], [a1, a2], before, after)

    assert "q2" in result.unchanged_qids
    assert "q1" not in result.unchanged_qids


def test_no_snapshot_before_skips_dom_unstable_check():
    """First page / cold start: no baseline available, must still pass on real success."""
    q = _q("q1", QuestionType.RADIO, [("a", "A")])
    a = Answer(question_id="q1", value="a", confidence=0.9)
    after = from_controls("u", _radio_controls("q1", "a", ["a"]))

    result = verify_action([q], [a], None, after)

    assert result.success is True
    assert result.dom_unstable is False
    assert result.page_hash_before is None


# --------------------------------------------------------------------------- #
# VerificationResult serialization (AgentState round-trip)
# --------------------------------------------------------------------------- #


def test_verification_result_to_dict_is_json_safe():
    import json

    q = _q("q1", QuestionType.RADIO, [("a", "A"), ("b", "B")])
    a = Answer(question_id="q1", value="a", confidence=0.9)
    before = from_controls("u", _radio_controls("q1", None, ["a", "b"]))
    after = from_controls("u", _radio_controls("q1", "b", ["a", "b"]))

    result = verify_action([q], [a], before, after)
    d = result.to_dict()

    # Must round-trip through JSON without TypeError
    roundtripped = json.loads(json.dumps(d))
    assert roundtripped["success"] is False
    assert roundtripped["mismatches"][0]["reason"] == "wrong_value"
    assert "page_hash_after" in roundtripped


def test_unknown_question_type_requires_frame_presence():
    """Unknown QuestionType still flags missing controls but doesn't strict-match values."""
    # Synthesize a question of a type the verifier dispatch table doesn't know.
    # We use GRID since most QuestionType enums include it but verifier doesn't map it.
    grid_type = None
    for t in QuestionType:
        if t.value not in ("radio", "checkbox", "dropdown", "open_text", "slider", "number"):
            grid_type = t
            break
    if grid_type is None:
        pytest.skip("No 'unknown to verifier' QuestionType available in this build")

    q = _q("qg", grid_type)
    a = Answer(question_id="qg", value="anything", confidence=0.5)

    # Frame present → no mismatch
    after_present = from_controls("u", _text_controls("qg", "anything"))
    assert verify_action([q], [a], None, after_present).success is True

    # Frame absent → missing_control
    after_absent = from_controls("u", [])
    r = verify_action([q], [a], None, after_absent)
    assert any(m.reason == "missing_control" for m in r.mismatches)
