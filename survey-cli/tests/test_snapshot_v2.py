"""
Tests for survey.snapshot_v2 — subtree_hash determinism and frame diffs.

The verifier (#167) and Phase 2 skip-on-stable (#168) both rely on:
    * Two identical control lists producing the same subtree_hash and page_hash.
    * Reordered DOM (same logical content) still producing the same hash.
    * Any value/checked change producing a different hash.
"""

from __future__ import annotations

from survey.snapshot_v2 import from_controls, SnapshotV2


def _radio(qid: str, value: str, checked: bool) -> dict:
    return {
        "qid": qid, "tag": "input", "type": "radio", "role": "radio",
        "name": qid, "value": value, "checked": checked,
        "selected": None, "disabled": False, "visible": True,
    }


def test_identical_controls_produce_identical_hash():
    controls = [_radio("q1", "a", False), _radio("q1", "b", True)]
    a = from_controls("https://x", controls)
    b = from_controls("https://x", list(controls))  # fresh list, same content

    assert a.page_hash == b.page_hash
    assert a.frames["q1"].subtree_hash == b.frames["q1"].subtree_hash


def test_reordered_controls_produce_identical_hash():
    """DOM order can shift between renders; hash must be order-independent within a frame."""
    c1 = [_radio("q1", "a", False), _radio("q1", "b", True)]
    c2 = [_radio("q1", "b", True), _radio("q1", "a", False)]

    h1 = from_controls("u", c1).frames["q1"].subtree_hash
    h2 = from_controls("u", c2).frames["q1"].subtree_hash

    assert h1 == h2


def test_visible_flag_does_not_affect_hash():
    """visible: false can flicker due to layout pass; must not change subtree_hash."""
    c1 = [{**_radio("q1", "a", True), "visible": True}]
    c2 = [{**_radio("q1", "a", True), "visible": False}]

    assert from_controls("u", c1).frames["q1"].subtree_hash == from_controls("u", c2).frames["q1"].subtree_hash


def test_checked_change_changes_hash():
    h_before = from_controls("u", [_radio("q1", "a", False)]).frames["q1"].subtree_hash
    h_after = from_controls("u", [_radio("q1", "a", True)]).frames["q1"].subtree_hash

    assert h_before != h_after


def test_diff_hashes_surfaces_changed_qids():
    before = from_controls("u", [_radio("q1", "a", False), _radio("q2", "x", True)])
    after = from_controls("u", [_radio("q1", "a", True), _radio("q2", "x", True)])

    diff = after.diff_hashes(before)
    assert diff == {"q1"}


def test_to_dict_round_trip():
    snap = from_controls("u", [_radio("q1", "a", True)])
    d = snap.to_dict()
    restored = SnapshotV2.from_dict(d)

    assert restored is not None
    assert restored.page_hash == snap.page_hash
    assert restored.frames["q1"].subtree_hash == snap.frames["q1"].subtree_hash


def test_from_dict_none_returns_none():
    assert SnapshotV2.from_dict(None) is None
    assert SnapshotV2.from_dict({}) is None or isinstance(SnapshotV2.from_dict({}), SnapshotV2) is False


def test_orphan_controls_without_qid_excluded_from_frames():
    """Controls without [data-question-id] container are tolerated but get no frame."""
    snap = from_controls("u", [{
        "qid": "", "tag": "input", "type": "text", "role": "input",
        "name": "freeform", "value": "hi", "checked": None,
        "selected": None, "disabled": False, "visible": True,
    }])
    assert snap.frames == {}
    assert snap.page_hash  # still hashes (empty frames map)
