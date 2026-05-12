# -*- coding: utf-8 -*-
"""Tests for scripts/graph_promotion_report.py (SR-123)."""

from __future__ import annotations

import io
import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

# Make `scripts/` importable when pytest is run from repo root.
_HERE = Path(__file__).resolve().parent
_SCRIPTS = _HERE.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import graph_promotion_report as gpr  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

NOW = datetime(2026, 5, 12, 12, 0, 0, tzinfo=timezone.utc)


def _record(
    outer_ts: datetime,
    sha: str,
    *,
    bytes_written: int = 1024,
    snapshot_ts: datetime | None = None,
) -> dict:
    snap_ts = snapshot_ts or outer_ts
    return {
        "event": "graph_promotion",
        "timestamp": outer_ts.isoformat().replace("+00:00", "Z"),
        "snapshot": {
            "path": f"survey-cli/survey/graph/snapshots/{sha[:8]}.py",
            "sha256": sha,
            "bytes_written": bytes_written,
            "timestamp": snap_ts.strftime("%Y%m%dT%H%M%SZ"),
            "mode_octal": "0o444",
            "chmod_applied": True,
        },
    }


def _write_log(tmpdir: Path, records: list[dict]) -> Path:
    p = tmpdir / "graph-promotions.jsonl"
    with p.open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")
    return p


def _run(argv: list[str], *, now: datetime = NOW) -> tuple[int, str, str]:
    """Invoke main() with captured stdout/stderr."""
    stdout = io.StringIO()
    stderr = io.StringIO()
    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = stdout, stderr
    try:
        rc = gpr.main(argv, now=now)
    finally:
        sys.stdout, sys.stderr = old_out, old_err
    return rc, stdout.getvalue(), stderr.getvalue()


# ---------------------------------------------------------------------------
# T1 — Empty log → "No promotions recorded", rc=0
# ---------------------------------------------------------------------------


def test_t1_empty_log_returns_zero_with_message():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        log = tmp / "graph-promotions.jsonl"
        log.touch()
        rc, out, err = _run(["--log", str(log)])
        assert rc == 0, err
        assert "No promotions recorded" in out
        assert err == ""


def test_t1b_empty_log_json_mode_has_total_zero():
    with tempfile.TemporaryDirectory() as d:
        log = Path(d) / "graph-promotions.jsonl"
        log.touch()
        rc, out, _ = _run(["--log", str(log), "--json"])
        assert rc == 0
        payload = json.loads(out)
        assert payload["total"] == 0
        assert payload["message"] == "No promotions recorded"


# ---------------------------------------------------------------------------
# T2 — Missing log file → rc=2
# ---------------------------------------------------------------------------


def test_t2_missing_log_returns_two():
    with tempfile.TemporaryDirectory() as d:
        missing = Path(d) / "does-not-exist.jsonl"
        rc, out, err = _run(["--log", str(missing)])
        assert rc == 2
        assert "not found" in err
        assert out == ""


def test_t2b_missing_log_quiet_no_stderr():
    with tempfile.TemporaryDirectory() as d:
        missing = Path(d) / "nope.jsonl"
        rc, _, err = _run(["--log", str(missing), "--quiet"])
        assert rc == 2
        assert err == ""


# ---------------------------------------------------------------------------
# T3 — Single promotion → count=1, no cadence stats
# ---------------------------------------------------------------------------


def test_t3_single_promotion_no_cadence():
    with tempfile.TemporaryDirectory() as d:
        log = _write_log(
            Path(d), [_record(NOW - timedelta(days=2), "a" * 64)]
        )
        rc, out, _ = _run(["--log", str(log)])
        assert rc == 0
        assert "Total promotions: **1**" in out
        assert "Not enough data for cadence stats" in out


# ---------------------------------------------------------------------------
# T4 — Multiple promotions → correct count
# ---------------------------------------------------------------------------


def test_t4_multiple_promotions_counted():
    records = [
        _record(NOW - timedelta(days=i), f"{i:064d}") for i in range(1, 6)
    ]
    with tempfile.TemporaryDirectory() as d:
        log = _write_log(Path(d), records)
        rc, out, _ = _run(["--log", str(log)])
        assert rc == 0
        assert "Total promotions: **5**" in out


# ---------------------------------------------------------------------------
# T5 — --last-days N filters older records out
# ---------------------------------------------------------------------------


def test_t5_last_days_filters_records():
    records = [
        _record(NOW - timedelta(days=1), "a" * 64),
        _record(NOW - timedelta(days=3), "b" * 64),
        _record(NOW - timedelta(days=40), "c" * 64),  # outside 7d
        _record(NOW - timedelta(days=60), "d" * 64),  # outside 7d
    ]
    with tempfile.TemporaryDirectory() as d:
        log = _write_log(Path(d), records)
        rc, out, _ = _run(["--log", str(log), "--last-days", "7", "--json"])
        assert rc == 0
        payload = json.loads(out)
        assert payload["total"] == 2


# ---------------------------------------------------------------------------
# T6 — Inter-promotion interval: median computed correctly
# ---------------------------------------------------------------------------


def test_t6_median_interval():
    # Gaps: 1h, 1h, 1h → median = 3600.
    records = [
        _record(NOW - timedelta(hours=3), "a" * 64),
        _record(NOW - timedelta(hours=2), "b" * 64),
        _record(NOW - timedelta(hours=1), "c" * 64),
        _record(NOW, "d" * 64),
    ]
    with tempfile.TemporaryDirectory() as d:
        log = _write_log(Path(d), records)
        rc, out, _ = _run(["--log", str(log), "--json"])
        assert rc == 0
        payload = json.loads(out)
        assert payload["median_interval_seconds"] == 3600.0


# ---------------------------------------------------------------------------
# T7 — Inter-promotion interval: mean computed correctly
# ---------------------------------------------------------------------------


def test_t7_mean_interval():
    # Gaps: 1h, 2h, 3h → mean = 2h = 7200.
    records = [
        _record(NOW - timedelta(hours=6), "a" * 64),
        _record(NOW - timedelta(hours=5), "b" * 64),
        _record(NOW - timedelta(hours=3), "c" * 64),
        _record(NOW, "d" * 64),
    ]
    with tempfile.TemporaryDirectory() as d:
        log = _write_log(Path(d), records)
        rc, out, _ = _run(["--log", str(log), "--json"])
        assert rc == 0
        payload = json.loads(out)
        assert payload["mean_interval_seconds"] == pytest.approx(7200.0)


# ---------------------------------------------------------------------------
# T8 — Unique sha256 count
# ---------------------------------------------------------------------------


def test_t8_unique_sha_count():
    records = [
        _record(NOW - timedelta(hours=3), "a" * 64),
        _record(NOW - timedelta(hours=2), "b" * 64),
        _record(NOW - timedelta(hours=1), "c" * 64),
        _record(NOW, "a" * 64),  # duplicate
    ]
    with tempfile.TemporaryDirectory() as d:
        log = _write_log(Path(d), records)
        rc, out, _ = _run(["--log", str(log), "--json"])
        assert rc == 0
        payload = json.loads(out)
        assert payload["unique_sha256"] == 3


# ---------------------------------------------------------------------------
# T9 — Duplicate sha256 detection: flagged in output
# ---------------------------------------------------------------------------


def test_t9_duplicate_sha_flagged_in_markdown():
    records = [
        _record(NOW - timedelta(hours=2), "a" * 64),
        _record(NOW - timedelta(hours=1), "b" * 64),
        _record(NOW, "a" * 64),  # duplicate
    ]
    with tempfile.TemporaryDirectory() as d:
        log = _write_log(Path(d), records)
        rc, out, _ = _run(["--log", str(log)])
        assert rc == 0
        assert "Duplicate sha256" in out
        # The short sha appears in the duplicates table.
        assert "aaaaaaaaaaaa" in out


def test_t9b_duplicates_in_json_payload():
    records = [
        _record(NOW - timedelta(hours=2), "a" * 64),
        _record(NOW - timedelta(hours=1), "a" * 64),
    ]
    with tempfile.TemporaryDirectory() as d:
        log = _write_log(Path(d), records)
        rc, out, _ = _run(["--log", str(log), "--json"])
        assert rc == 0
        payload = json.loads(out)
        assert len(payload["duplicates"]) == 1
        dup = payload["duplicates"][0]
        assert dup["sha256"] == "a" * 64
        assert dup["count"] == 2
        assert len(dup["occurrences"]) == 2


# ---------------------------------------------------------------------------
# T10 — No duplicates: section says "all snapshots unique"
# ---------------------------------------------------------------------------


def test_t10_no_duplicates_message():
    records = [
        _record(NOW - timedelta(hours=2), "a" * 64),
        _record(NOW - timedelta(hours=1), "b" * 64),
        _record(NOW, "c" * 64),
    ]
    with tempfile.TemporaryDirectory() as d:
        log = _write_log(Path(d), records)
        rc, out, _ = _run(["--log", str(log)])
        assert rc == 0
        assert "All snapshots unique" in out
        assert "Duplicate sha256" not in out


# ---------------------------------------------------------------------------
# T11 — Markdown output has required section headers
# ---------------------------------------------------------------------------


def test_t11_markdown_required_section_headers():
    records = [
        _record(NOW - timedelta(hours=2), "a" * 64),
        _record(NOW - timedelta(hours=1), "b" * 64),
    ]
    with tempfile.TemporaryDirectory() as d:
        log = _write_log(Path(d), records)
        rc, out, _ = _run(["--log", str(log)])
        assert rc == 0
        assert "# Graph Promotion Log Report" in out
        assert "## Summary" in out
        assert "## Cadence" in out
        assert "## SHA-256 Distribution" in out


# ---------------------------------------------------------------------------
# T12 — --json output parseable, has required fields
# ---------------------------------------------------------------------------


def test_t12_json_output_parseable_with_required_fields():
    records = [
        _record(NOW - timedelta(days=2), "a" * 64),
        _record(NOW - timedelta(days=1), "b" * 64),
        _record(NOW, "c" * 64),
    ]
    with tempfile.TemporaryDirectory() as d:
        log = _write_log(Path(d), records)
        rc, out, _ = _run(["--log", str(log), "--json"])
        assert rc == 0
        payload = json.loads(out)
        required = {
            "total",
            "last_30d_count",
            "newest_timestamp",
            "oldest_timestamp",
            "newest_snapshot",
            "median_interval_seconds",
            "mean_interval_seconds",
            "weeks",
            "unique_sha256",
            "duplicates",
            "generated_at",
            "log_path",
        }
        missing = required - set(payload.keys())
        assert not missing, f"Missing keys: {missing}"


# ---------------------------------------------------------------------------
# Hardening — extras beyond the plan-file's 12-test minimum
# ---------------------------------------------------------------------------


def test_h1_malformed_lines_are_skipped():
    """A truncated/corrupt line must not blow up; it gets skipped."""
    with tempfile.TemporaryDirectory() as d:
        log = Path(d) / "log.jsonl"
        with log.open("w", encoding="utf-8") as fh:
            fh.write(json.dumps(_record(NOW, "a" * 64)) + "\n")
            fh.write("{not-valid-json\n")
            fh.write("\n")  # blank
            fh.write(json.dumps({"event": "other"}) + "\n")  # wrong event
            fh.write(json.dumps(_record(NOW - timedelta(hours=1), "b" * 64))
                     + "\n")
        rc, out, _ = _run(["--log", str(log), "--json"])
        assert rc == 0
        payload = json.loads(out)
        assert payload["total"] == 2


def test_h2_quiet_suppresses_stdout():
    records = [_record(NOW, "a" * 64)]
    with tempfile.TemporaryDirectory() as d:
        log = _write_log(Path(d), records)
        rc, out, _ = _run(["--log", str(log), "--quiet"])
        assert rc == 0
        assert out == ""


def test_h3_last_30d_count_independent_of_last_days_filter():
    """`last_30d_count` is always measured against the live window —
    independent of `--last-days` (which is a pre-filter)."""
    records = [
        _record(NOW - timedelta(days=2), "a" * 64),
        _record(NOW - timedelta(days=5), "b" * 64),
    ]
    with tempfile.TemporaryDirectory() as d:
        log = _write_log(Path(d), records)
        rc, out, _ = _run(["--log", str(log), "--json"])
        assert rc == 0
        payload = json.loads(out)
        assert payload["last_30d_count"] == 2


def test_h4_newest_oldest_use_outer_timestamp():
    """Newest / oldest are derived from outer timestamp (log-write
    order), not the snapshot timestamp."""
    old_outer = NOW - timedelta(days=5)
    new_outer = NOW
    # Snapshot timestamps reversed vs outer — the hand-off-notes rule
    # says we use the OUTER for ordering.
    rec_old = _record(old_outer, "a" * 64, snapshot_ts=new_outer)
    rec_new = _record(new_outer, "b" * 64, snapshot_ts=old_outer)
    with tempfile.TemporaryDirectory() as d:
        log = _write_log(Path(d), [rec_old, rec_new])
        rc, out, _ = _run(["--log", str(log), "--json"])
        assert rc == 0
        payload = json.loads(out)
        assert payload["oldest_timestamp"].startswith("2026-05-07")
        assert payload["newest_timestamp"].startswith("2026-05-12")


def test_h5_parse_record_timestamp_handles_z_suffix():
    dt = gpr.parse_record_timestamp("2026-05-12T11:38:14Z")
    assert dt is not None
    assert dt.tzinfo is not None
    assert dt.year == 2026 and dt.month == 5 and dt.day == 12


def test_h6_parse_snapshot_timestamp_handles_compact_format():
    dt = gpr.parse_snapshot_timestamp("20260512T113814Z")
    assert dt is not None
    assert dt.year == 2026 and dt.hour == 11 and dt.minute == 38


def test_h7_humanize_seconds_buckets():
    assert gpr._humanize_seconds(30) == "30s"
    assert gpr._humanize_seconds(125) == "2m 05s"
    assert gpr._humanize_seconds(3600 * 2 + 60 * 5) == "2h 05m"
    assert gpr._humanize_seconds(86400 * 3 + 3600 * 4) == "3d 04h"


def test_h8_week_bucket_iso_format():
    dt = datetime(2026, 1, 5, 12, 0, 0, tzinfo=timezone.utc)
    assert gpr.week_bucket(dt) == "2026-W02"


def test_h9_negative_last_days_rejected():
    records = [_record(NOW, "a" * 64)]
    with tempfile.TemporaryDirectory() as d:
        log = _write_log(Path(d), records)
        rc, _, err = _run(["--log", str(log), "--last-days", "-1"])
        assert rc == 2
        assert "must be >= 0" in err


def test_h10_per_week_histogram_present_for_multi_records():
    records = [
        _record(NOW - timedelta(days=14), "a" * 64),
        _record(NOW - timedelta(days=7), "b" * 64),
        _record(NOW, "c" * 64),
    ]
    with tempfile.TemporaryDirectory() as d:
        log = _write_log(Path(d), records)
        rc, out, _ = _run(["--log", str(log), "--json"])
        assert rc == 0
        payload = json.loads(out)
        # 3 records spanning 3 distinct ISO weeks.
        assert len(payload["weeks"]) >= 2
        for entry in payload["weeks"]:
            assert "week" in entry and "count" in entry
