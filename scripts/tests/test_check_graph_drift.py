"""tests for scripts/check_graph_drift.py — SR-122.

Test coverage (10+ tests, mapped to plan-file SR-122 test minimum):

  T1  — sha256 of identical file → no drift
  T2  — sha256 of differing file → drift detected
  T3  — Snapshot age computed from compact-UTC timestamp
  T4  — `--max-age-days` honored: just-promoted → rc=0
  T5  — `--max-age-days` honored: 30-day-old → rc=1
  T6  — `--exit-non-zero-on-drift` honored on drift → rc=1
  T7  — `--exit-non-zero-on-drift` honored on no-drift → rc=0
  T8  — Missing promotion log → rc=2 with clear message on stderr/stdout
  T9  — Empty promotion log → rc=2 with "no snapshots recorded yet"
  T10 — `--json` produces parseable JSON with required fields

Plus extra hardening tests for:
  - graph.py missing → rc=2
  - `--quiet` suppresses stdout
  - newest snapshot is the LAST line (append-order trust)
  - malformed lines are skipped, not fatal
  - `parse_snapshot_timestamp` rejects garbage
"""

import io
import json
import tempfile
from contextlib import redirect_stdout
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from check_graph_drift import (
    compute_drift,
    format_human,
    format_json,
    main,
    parse_snapshot_timestamp,
    read_newest_snapshot,
    sha256_of_file,
)

# -- Fixtures ----------------------------------------------------------------


def _write_graph(tmp: Path, content: bytes = b"print('graph v1')\n") -> Path:
    """Write a fake live graph.py at <tmp>/graph.py and return its path."""
    p = tmp / "graph.py"
    p.write_bytes(content)
    return p


def _write_log(
    tmp: Path,
    records: list,
    name: str = "graph-promotions.jsonl",
) -> Path:
    """Write a JSONL promotion log with the given records (in append order)."""
    p = tmp / name
    with p.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    return p


def _make_record(
    sha: str,
    ts: str = "20260512T120000Z",
    path: str = "survey-cli/logs/snapshots/graph.20260512T120000Z.py",
) -> dict:
    """Build a SR-49-shape promotion record."""
    return {
        "event": "graph_promotion",
        "timestamp": "2026-05-12T12:00:00Z",
        "snapshot": {
            "path": path,
            "sha256": sha,
            "bytes_written": 42,
            "timestamp": ts,
            "mode_octal": "0o444",
            "chmod_applied": True,
        },
    }


# -- T1 / T2: sha256 identity vs difference ----------------------------------


class TestSha256:
    """Drift detection via sha256 equality."""

    def test_t1_identical_file_no_drift(self):
        """T1: live graph.py byte-identical to snapshot → no drift."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            graph = _write_graph(tmp_p, b"print('v1')\n")
            sha = sha256_of_file(graph)
            log = _write_log(tmp_p, [_make_record(sha)])

            result, err = compute_drift(graph, log)

            assert err is None
            assert result["drift"] is False
            assert result["current_sha256"] == sha
            assert result["snapshot_sha256"] == sha

    def test_t2_differing_file_drift_detected(self):
        """T2: live graph.py differs from snapshot → drift detected."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            graph = _write_graph(tmp_p, b"print('v2 edited!')\n")
            stale_sha = "0" * 64
            log = _write_log(tmp_p, [_make_record(stale_sha)])

            result, err = compute_drift(graph, log)

            assert err is None
            assert result["drift"] is True
            assert result["current_sha256"] != stale_sha
            assert result["snapshot_sha256"] == stale_sha


# -- T3: age from snapshot.timestamp -----------------------------------------


class TestAge:
    """Age computation from compact UTC snapshot.timestamp."""

    def test_t3_age_computed_from_iso_timestamp(self):
        """T3: age_days is derived from snapshot.timestamp, not record.timestamp."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            graph = _write_graph(tmp_p)
            sha = sha256_of_file(graph)
            # Snapshot is from 2026-05-02; "now" is 2026-05-12 → 10 days.
            log = _write_log(tmp_p, [_make_record(sha, ts="20260502T120000Z")])
            fake_now = datetime(2026, 5, 12, 12, 0, 0, tzinfo=UTC)

            result, err = compute_drift(graph, log, now=fake_now)

            assert err is None
            assert result["age_days"] is not None
            assert abs(result["age_days"] - 10.0) < 1e-6


# -- T4 / T5: --max-age-days behavior ----------------------------------------


class TestMaxAgeDays:
    """`--max-age-days` exit-code semantics."""

    def test_t4_just_promoted_passes(self):
        """T4: snapshot taken "now" with --max-age-days 7 → rc=0."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            graph = _write_graph(tmp_p)
            sha = sha256_of_file(graph)
            now = datetime.now(UTC)
            ts = now.strftime("%Y%m%dT%H%M%SZ")
            log = _write_log(tmp_p, [_make_record(sha, ts=ts)])

            rc = main(
                [
                    "--graph-source",
                    str(graph),
                    "--promotion-log",
                    str(log),
                    "--max-age-days",
                    "7",
                    "--quiet",
                ]
            )
            assert rc == 0

    def test_t5_thirty_day_old_fails(self):
        """T5: 30-day-old snapshot with --max-age-days 7 → rc=1."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            graph = _write_graph(tmp_p)
            sha = sha256_of_file(graph)
            old = datetime.now(UTC) - timedelta(days=30)
            ts = old.strftime("%Y%m%dT%H%M%SZ")
            log = _write_log(tmp_p, [_make_record(sha, ts=ts)])

            rc = main(
                [
                    "--graph-source",
                    str(graph),
                    "--promotion-log",
                    str(log),
                    "--max-age-days",
                    "7",
                    "--quiet",
                ]
            )
            assert rc == 1


# -- T6 / T7: --exit-non-zero-on-drift behavior ------------------------------


class TestExitOnDrift:
    """`--exit-non-zero-on-drift` exit-code semantics."""

    def test_t6_drift_returns_one(self):
        """T6: drift + --exit-non-zero-on-drift → rc=1."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            graph = _write_graph(tmp_p, b"edited!\n")
            log = _write_log(tmp_p, [_make_record("0" * 64)])

            rc = main(
                [
                    "--graph-source",
                    str(graph),
                    "--promotion-log",
                    str(log),
                    "--exit-non-zero-on-drift",
                    "--quiet",
                ]
            )
            assert rc == 1

    def test_t7_no_drift_returns_zero(self):
        """T7: no drift + --exit-non-zero-on-drift → rc=0."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            graph = _write_graph(tmp_p)
            sha = sha256_of_file(graph)
            log = _write_log(tmp_p, [_make_record(sha)])

            rc = main(
                [
                    "--graph-source",
                    str(graph),
                    "--promotion-log",
                    str(log),
                    "--exit-non-zero-on-drift",
                    "--quiet",
                ]
            )
            assert rc == 0


# -- T8 / T9: config-error handling ------------------------------------------


class TestConfigErrors:
    """Missing/empty inputs must produce rc=2 with clear messages."""

    def test_t8_missing_promotion_log_rc2(self):
        """T8: missing promotion log → rc=2 with explicit message."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            graph = _write_graph(tmp_p)
            missing_log = tmp_p / "does-not-exist.jsonl"

            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = main(
                    [
                        "--graph-source",
                        str(graph),
                        "--promotion-log",
                        str(missing_log),
                    ]
                )
            output = buf.getvalue()
            assert rc == 2
            assert "promotion log not found" in output

    def test_t9_empty_promotion_log_rc2(self):
        """T9: empty promotion log → rc=2 with 'no snapshots recorded yet'."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            graph = _write_graph(tmp_p)
            log = tmp_p / "graph-promotions.jsonl"
            log.write_text("")  # empty

            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = main(
                    [
                        "--graph-source",
                        str(graph),
                        "--promotion-log",
                        str(log),
                    ]
                )
            output = buf.getvalue()
            assert rc == 2
            assert "no snapshots recorded yet" in output


# -- T10: --json output ------------------------------------------------------


class TestJsonOutput:
    """`--json` must emit a parseable object with the documented fields."""

    REQUIRED_KEYS = {
        "drift",
        "current_sha256",
        "snapshot_sha256",
        "snapshot_path",
        "snapshot_timestamp",
        "age_days",
        "graph_source",
        "promotion_log",
        "error",
        "ok",
    }

    def test_t10_json_has_required_fields(self):
        """T10: --json output parses and contains all required keys."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            graph = _write_graph(tmp_p)
            sha = sha256_of_file(graph)
            log = _write_log(tmp_p, [_make_record(sha)])

            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = main(
                    [
                        "--graph-source",
                        str(graph),
                        "--promotion-log",
                        str(log),
                        "--json",
                    ]
                )
            assert rc == 0

            data = json.loads(buf.getvalue())
            assert self.REQUIRED_KEYS.issubset(data.keys())
            assert data["ok"] is True
            assert data["drift"] is False
            assert data["error"] is None


# -- Hardening tests ---------------------------------------------------------


class TestHardening:
    """Extra robustness checks beyond the plan-file minimum."""

    def test_graph_source_missing_rc2(self):
        """graph.py missing → rc=2."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            log = _write_log(tmp_p, [_make_record("a" * 64)])
            missing_graph = tmp_p / "graph.py"  # never created

            rc = main(
                [
                    "--graph-source",
                    str(missing_graph),
                    "--promotion-log",
                    str(log),
                    "--quiet",
                ]
            )
            assert rc == 2

    def test_quiet_suppresses_stdout(self):
        """--quiet → no stdout emitted at all."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            graph = _write_graph(tmp_p)
            sha = sha256_of_file(graph)
            log = _write_log(tmp_p, [_make_record(sha)])

            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = main(
                    [
                        "--graph-source",
                        str(graph),
                        "--promotion-log",
                        str(log),
                        "--quiet",
                    ]
                )
            assert rc == 0
            assert buf.getvalue() == ""

    def test_newest_is_last_line(self):
        """When the log has many records, the LAST one wins (append order)."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            graph = _write_graph(tmp_p, b"newest!\n")
            cur_sha = sha256_of_file(graph)
            records = [
                _make_record("1" * 64, ts="20260101T000000Z"),
                _make_record("2" * 64, ts="20260201T000000Z"),
                _make_record(cur_sha, ts="20260512T120000Z"),
            ]
            log = _write_log(tmp_p, records)

            result, err = compute_drift(graph, log)
            assert err is None
            assert result["drift"] is False
            assert result["snapshot_sha256"] == cur_sha

    def test_malformed_lines_are_skipped(self):
        """A garbage line between good records must not abort drift check."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            graph = _write_graph(tmp_p)
            sha = sha256_of_file(graph)
            log = tmp_p / "graph-promotions.jsonl"
            with log.open("w", encoding="utf-8") as f:
                f.write("{ this is not json }\n")
                f.write(json.dumps(_make_record(sha)) + "\n")

            result, err = compute_drift(graph, log)
            assert err is None
            assert result["drift"] is False

    def test_parse_snapshot_timestamp_rejects_garbage(self):
        """parse_snapshot_timestamp rejects non-conforming inputs."""
        assert parse_snapshot_timestamp(None) is None
        assert parse_snapshot_timestamp("") is None
        assert parse_snapshot_timestamp("   ") is None
        assert parse_snapshot_timestamp("2026-05-12T12:00:00Z") is None
        assert parse_snapshot_timestamp("20260512T120000") is None
        assert parse_snapshot_timestamp(12345) is None

    def test_parse_snapshot_timestamp_accepts_canonical(self):
        """parse_snapshot_timestamp returns UTC datetime for canonical form."""
        dt = parse_snapshot_timestamp("20260512T120000Z")
        assert dt is not None
        assert dt.year == 2026 and dt.month == 5 and dt.day == 12
        assert dt.hour == 12 and dt.tzinfo == UTC

    def test_read_newest_snapshot_returns_dict(self):
        """read_newest_snapshot returns the snapshot sub-dict, not the wrapper."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            log = _write_log(tmp_p, [_make_record("b" * 64)])
            snap, err = read_newest_snapshot(log)
            assert err is None
            assert snap is not None
            assert snap["sha256"] == "b" * 64

    def test_format_human_drift_message(self):
        """Human formatter mentions DRIFT when drift=True."""
        result = {
            "drift": True,
            "current_sha256": "a" * 64,
            "snapshot_sha256": "b" * 64,
            "snapshot_path": "p",
            "snapshot_timestamp": "20260101T000000Z",
            "age_days": 1.0,
            "graph_source": "g",
            "promotion_log": "l",
        }
        out = format_human(result, error=None)
        assert "DRIFT" in out

    def test_format_json_error_path(self):
        """format_json sets ok=False and surfaces error message."""
        result = {
            "drift": None,
            "current_sha256": None,
            "snapshot_sha256": None,
            "snapshot_path": None,
            "snapshot_timestamp": None,
            "age_days": None,
            "graph_source": "g",
            "promotion_log": "l",
        }
        out = format_json(result, error="boom")
        data = json.loads(out)
        assert data["ok"] is False
        assert data["error"] == "boom"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
