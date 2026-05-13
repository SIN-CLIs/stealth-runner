"""tests for scripts/check_status_truth.py — SR-218.

Test coverage:
  - AC1: extract_claims finds PR#NNN near 'merged' keywords (EN+DE)
  - AC2: extract_claims ignores PR#NNN without a merge claim nearby
  - AC3: extract_claims handles unicode checkmark (✅)
  - AC4: extract_claims dedupes same PR on same line
  - AC5: extract_claims attributes correct source line
  - AC6: fetch_truth parses `gh api` JSON correctly (merged / open / closed)
  - AC7: fetch_truth flags gh CLI errors as violations
  - AC8: find_violations only flags claims that contradict reality
  - AC9: --exit-non-zero-on-violation flag behavior
  - AC10: --json output format
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

# scripts/ is on sys.path when pytest runs from repo root via the existing
# scripts/tests/__init__.py convention (same as test_check_audit_log_schema).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from check_status_truth import (  # noqa: E402
    Claim,
    Truth,
    Violation,
    extract_claims,
    fetch_truth,
    find_violations,
    main,
    render_json,
    render_table,
)


# ---------------------------------------------------------------------------
# AC1..AC5 — extract_claims (pure function, no network)
# ---------------------------------------------------------------------------
class TestExtractClaims:
    def test_finds_pr_near_merged_en(self):
        text = "PR #209 ✅ Merged, 11/11 CI green"
        claims = extract_claims(text)
        assert len(claims) == 1
        assert claims[0].pr_number == 209

    def test_finds_pr_near_merged_de(self):
        text = "PR #175 wurde gemerged."
        claims = extract_claims(text)
        assert [c.pr_number for c in claims] == [175]

    def test_finds_pr_when_keyword_comes_first(self):
        text = "Merged: #216"
        claims = extract_claims(text)
        assert [c.pr_number for c in claims] == [216]

    def test_ignores_pr_without_merge_keyword(self):
        text = "PR #215 is awaiting review."
        assert extract_claims(text) == []

    def test_ignores_unrelated_hash_numbers(self):
        # '#212' is far from any merge keyword.
        text = "See Issue #212 for background. (separate paragraph)\n\nNothing happened."
        assert extract_claims(text) == []

    def test_handles_unicode_checkmark(self):
        text = "#215 \u2705"  # ✅
        claims = extract_claims(text)
        assert [c.pr_number for c in claims] == [215]

    def test_dedupes_same_pr_on_same_line(self):
        text = "PR #209 ✅ Merged — see PR #209 history."
        claims = extract_claims(text)
        assert [c.pr_number for c in claims] == [209]

    def test_keeps_same_pr_on_different_lines(self):
        text = "PR #209 ✅ Merged\nLater: #209 done"
        claims = extract_claims(text)
        assert [c.source_line for c in claims] == [1, 2]

    def test_attributes_correct_source_line(self):
        text = "line 1\nline 2\nPR #99 merged here\nline 4"
        claims = extract_claims(text)
        assert claims[0].source_line == 3

    def test_window_boundary(self):
        # 80-char window between PR-ref and keyword.
        far = "PR #1" + " " * 200 + "merged"
        assert extract_claims(far) == []
        near = "PR #1 " + "x" * 70 + " merged"
        assert [c.pr_number for c in extract_claims(near)] == [1]

    def test_snippet_truncation(self):
        long_line = "PR #500 merged " + "x" * 500
        claims = extract_claims(long_line)
        assert len(claims[0].snippet) <= 200
        assert claims[0].snippet.endswith("...")

    def test_ignores_absurd_pr_numbers(self):
        text = "merged 2026 — see #999999"
        # 2026 has no '#' so PR_REF doesn't match it; 999999 is > 99999.
        assert extract_claims(text) == []


# ---------------------------------------------------------------------------
# AC6..AC7 — fetch_truth (mocks subprocess.run)
# ---------------------------------------------------------------------------
def _fake_run(stdout: str = "", stderr: str = "", returncode: int = 0):
    """Build a callable that mimics subprocess.run for monkeypatch."""

    def _run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0] if args else [],
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
        )

    return _run


class TestFetchTruth:
    def test_parses_merged_pr(self, monkeypatch):
        payload = json.dumps(
            {
                "state": "closed",
                "merged": True,
                "merged_at": "2026-05-12T10:00:00Z",
                "title": "feat: visual_hash",
            }
        )
        monkeypatch.setattr(subprocess, "run", _fake_run(stdout=payload))
        truth = fetch_truth(209, "SIN-CLIs/stealth-runner")
        assert truth.state == "MERGED"
        assert truth.merged_at == "2026-05-12T10:00:00Z"
        assert truth.is_actually_merged is True

    def test_parses_open_pr(self, monkeypatch):
        payload = json.dumps(
            {"state": "open", "merged": False, "merged_at": None, "title": "wip"}
        )
        monkeypatch.setattr(subprocess, "run", _fake_run(stdout=payload))
        truth = fetch_truth(175, "SIN-CLIs/stealth-runner")
        assert truth.state == "OPEN"
        assert truth.is_actually_merged is False

    def test_parses_closed_unmerged_pr(self, monkeypatch):
        payload = json.dumps(
            {"state": "closed", "merged": False, "merged_at": None, "title": "rejected"}
        )
        monkeypatch.setattr(subprocess, "run", _fake_run(stdout=payload))
        truth = fetch_truth(42, "SIN-CLIs/stealth-runner")
        assert truth.state == "CLOSED"
        assert truth.is_actually_merged is False

    def test_gh_error_becomes_truth_error(self, monkeypatch):
        monkeypatch.setattr(
            subprocess,
            "run",
            _fake_run(returncode=1, stderr="HTTP 404: Not Found"),
        )
        truth = fetch_truth(99999, "SIN-CLIs/stealth-runner")
        assert truth.error is not None
        assert truth.is_actually_merged is False

    def test_bad_json_becomes_truth_error(self, monkeypatch):
        monkeypatch.setattr(subprocess, "run", _fake_run(stdout="not json"))
        truth = fetch_truth(1, "SIN-CLIs/stealth-runner")
        assert truth.error is not None
        assert "bad gh json" in truth.error


# ---------------------------------------------------------------------------
# AC8 — find_violations integration
# ---------------------------------------------------------------------------
class TestFindViolations:
    def test_no_violation_when_truth_matches_claim(self, monkeypatch):
        payload = json.dumps(
            {"state": "closed", "merged": True, "merged_at": "2026-01-01T00:00:00Z", "title": "x"}
        )
        monkeypatch.setattr(subprocess, "run", _fake_run(stdout=payload))
        claims = [Claim(pr_number=1, snippet="#1 merged", source_line=1)]
        violations, _ = find_violations(claims, "any/repo")
        assert violations == []

    def test_violation_when_pr_is_open(self, monkeypatch):
        payload = json.dumps(
            {"state": "open", "merged": False, "merged_at": None, "title": "wip"}
        )
        monkeypatch.setattr(subprocess, "run", _fake_run(stdout=payload))
        claims = [Claim(pr_number=209, snippet="#209 merged", source_line=1)]
        violations, _ = find_violations(claims, "any/repo")
        assert len(violations) == 1
        assert violations[0].pr_number == 209
        assert violations[0].truth_state == "OPEN"

    def test_single_api_call_per_pr_number(self, monkeypatch):
        call_counter = {"n": 0}
        payload = json.dumps(
            {"state": "open", "merged": False, "merged_at": None, "title": "x"}
        )

        def counting_run(*args, **kwargs):
            call_counter["n"] += 1
            return subprocess.CompletedProcess(args=[], returncode=0, stdout=payload, stderr="")

        monkeypatch.setattr(subprocess, "run", counting_run)
        claims = [
            Claim(pr_number=42, snippet="#42 merged", source_line=1),
            Claim(pr_number=42, snippet="#42 merged again", source_line=5),
            Claim(pr_number=42, snippet="#42 done", source_line=9),
        ]
        find_violations(claims, "any/repo")
        assert call_counter["n"] == 1


# ---------------------------------------------------------------------------
# AC9..AC10 — CLI surface
# ---------------------------------------------------------------------------
class TestCli:
    def test_exit_zero_when_no_violations(self, monkeypatch, tmp_path, capsys):
        f = tmp_path / "status.md"
        f.write_text("Nothing claimed here.")
        rc = main(["--file", str(f), "--exit-non-zero-on-violation"])
        assert rc == 0

    def test_exit_one_when_violations_and_flag_set(self, monkeypatch, tmp_path):
        f = tmp_path / "status.md"
        f.write_text("PR #209 merged")
        payload = json.dumps(
            {"state": "open", "merged": False, "merged_at": None, "title": "wip"}
        )
        monkeypatch.setattr(subprocess, "run", _fake_run(stdout=payload))
        rc = main(["--file", str(f), "--exit-non-zero-on-violation"])
        assert rc == 1

    def test_exit_zero_without_flag_even_on_violation(self, monkeypatch, tmp_path):
        f = tmp_path / "status.md"
        f.write_text("PR #209 merged")
        payload = json.dumps(
            {"state": "open", "merged": False, "merged_at": None, "title": "wip"}
        )
        monkeypatch.setattr(subprocess, "run", _fake_run(stdout=payload))
        rc = main(["--file", str(f)])
        assert rc == 0  # advisory mode

    def test_json_output_is_parseable(self, monkeypatch, tmp_path, capsys):
        f = tmp_path / "status.md"
        f.write_text("PR #209 merged")
        payload = json.dumps(
            {"state": "open", "merged": False, "merged_at": None, "title": "wip"}
        )
        monkeypatch.setattr(subprocess, "run", _fake_run(stdout=payload))
        main(["--file", str(f), "--json"])
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["violation_count"] == 1
        assert data["violations"][0]["pr_number"] == 209


# ---------------------------------------------------------------------------
# Real-world fixture — the exact text from Issue #212 that triggered SR-218
# ---------------------------------------------------------------------------
class TestRegressionIssue212:
    def test_all_four_phantom_prs_are_caught(self, monkeypatch):
        body = """
        ## Status

        - PR #175 Verifier-Node ✅ Merged
        - PR #209 visual_hash ✅ Merged, 11/11 CI green
        - PR #215 attestation ✅ Merged
        - PR #216 stability_gate ✅ Merged
        """
        payload = json.dumps(
            {"state": "open", "merged": False, "merged_at": None, "title": "open pr"}
        )
        monkeypatch.setattr(subprocess, "run", _fake_run(stdout=payload))
        claims = extract_claims(body)
        assert sorted(c.pr_number for c in claims) == [175, 209, 215, 216]
        violations, _ = find_violations(claims, "SIN-CLIs/stealth-runner")
        assert sorted(v.pr_number for v in violations) == [175, 209, 215, 216]
