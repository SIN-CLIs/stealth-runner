#!/usr/bin/env python3
# =============================================================================
# SR-218: Status-Reporting validator — "merged" claims must match GitHub truth.
#
# WHY THIS FILE EXISTS
# --------------------
# CRITIC-AUDIT-2026-05-13 found that Issue #212 ("CEO-Status") listed 4 PRs
# as "Merged" / "✅" / "11/11 CI green" while the GitHub API reported them
# all as `state: OPEN, mergedAt: null`. Branches existed, code existed,
# nothing was on `main`. This single reporting defect explained every
# downstream symptom (missing visual_hash, 4-stage instead of 5-stage
# CAPTCHA chain, no verifier in survey graph).
#
# This script is the PREVENTION-GATE: scan a status document (issue body,
# markdown file, stdin), extract every PR-number near a "merged"/"done"
# claim, ask the GitHub API for ground truth, and fail loudly if any
# claim contradicts reality.
#
# CONTRACT
# --------
# - Reads only. NEVER writes to disk, NEVER touches git.
# - Network: calls `gh api repos/<owner>/<repo>/pulls/<n>` (read-only).
# - Default mode: print violation table, exit 0 (advisory).
# - `--exit-non-zero-on-violation`: exit 1 iff violations > 0 (CI/gate mode).
# - `--json`: machine-parseable JSON to stdout.
# - `--repo OWNER/REPO`: override repo (default: SIN-CLIs/stealth-runner).
#
# INPUTS
# ------
# Exactly one of:
#   --file PATH        Read markdown/text from PATH.
#   --issue N          Fetch issue N body via `gh issue view`.
#   --stdin            Read from stdin (default if nothing else given).
#
# DETECTION RULES
# ---------------
# A claim is matched when a PR-reference (`#NNN`, `PR #NNN`, `PR NNN`,
# `pull/NNN`) appears within MERGE_CONTEXT_WINDOW characters of any
# MERGED_KEYWORD. Keywords cover EN+DE and the unicode check mark.
# This is intentionally over-permissive — false positives are cheap
# (one extra API call), false negatives are the bug we are preventing.
#
# DESIGN
# ------
# - Standalone, no survey-cli imports — same convention as the other
#   scripts/check_*.py files. Runs in CI before the package is installed.
# - Shells out to `gh` (already in CI containers and dev machines) instead
#   of pulling in `requests` or `PyGithub`. Auth is whatever `gh` has.
# - Two-phase: parse all claims first, then dedupe PR numbers, then one
#   API call per unique PR. Keeps the rate-limit footprint tiny even for
#   long status updates.
# =============================================================================
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, asdict
from typing import Iterable

DEFAULT_REPO = "SIN-CLIs/stealth-runner"
MERGE_CONTEXT_WINDOW = 80  # chars between PR-ref and merge-keyword

MERGED_KEYWORDS = [
    r"merged",
    r"gemerged",
    r"gemergt",
    r"merge complete",
    r"done",
    r"erledigt",
    r"shipped",
    r"deployed",
    r"\bdelivered\b",
    r"\u2705",  # ✅
    r"ci\s*(?:11/11|all\s*green|gr[uü]n)",
]

PR_REF_RE = re.compile(
    r"(?P<full>"
    r"(?:PR\s*#?|pull(?:/|\s+#?)|#)"
    r"(?P<num>\d{1,5})"
    r"(?!\d)"
    r")",
    re.IGNORECASE,
)

KEYWORD_RE = re.compile("|".join(f"(?:{k})" for k in MERGED_KEYWORDS), re.IGNORECASE)


@dataclass
class Claim:
    pr_number: int
    snippet: str
    source_line: int


@dataclass
class Truth:
    pr_number: int
    state: str | None
    merged_at: str | None
    title: str | None
    error: str | None = None

    @property
    def is_actually_merged(self) -> bool:
        return self.state == "MERGED" and self.merged_at is not None


@dataclass
class Violation:
    pr_number: int
    claim_snippet: str
    truth_state: str | None
    truth_merged_at: str | None
    source_line: int

    def as_dict(self) -> dict:
        return asdict(self)


def extract_claims(text: str) -> list[Claim]:
    """Find every PR-ref that sits within MERGE_CONTEXT_WINDOW chars of a
    'merged'-style keyword. Window is checked in BOTH directions because
    real status updates write either '#175 ✅ Merged' or 'Merged: #175'."""
    claims: list[Claim] = []
    seen: set[tuple[int, int]] = set()  # (pr_num, line) — dedupe per source line

    # Pre-compute line offsets so we can attribute matches to a line number.
    line_offsets = [0]
    for i, ch in enumerate(text):
        if ch == "\n":
            line_offsets.append(i + 1)

    def line_of(offset: int) -> int:
        # Binary search would be faster, but status docs are short.
        for ln, start in enumerate(line_offsets, start=1):
            if start > offset:
                return ln - 1
        return len(line_offsets)

    for pr_match in PR_REF_RE.finditer(text):
        pr_num = int(pr_match.group("num"))
        # Skip obvious non-PR digits like years or huge issue numbers.
        if pr_num == 0 or pr_num > 99999:
            continue

        start = max(0, pr_match.start() - MERGE_CONTEXT_WINDOW)
        end = min(len(text), pr_match.end() + MERGE_CONTEXT_WINDOW)
        window = text[start:end]

        if not KEYWORD_RE.search(window):
            continue

        ln = line_of(pr_match.start())
        key = (pr_num, ln)
        if key in seen:
            continue
        seen.add(key)

        # Snippet = the actual source line, trimmed.
        line_start = text.rfind("\n", 0, pr_match.start()) + 1
        line_end = text.find("\n", pr_match.start())
        if line_end == -1:
            line_end = len(text)
        snippet = text[line_start:line_end].strip()
        if len(snippet) > 200:
            snippet = snippet[:197] + "..."

        claims.append(Claim(pr_number=pr_num, snippet=snippet, source_line=ln))

    return claims


def fetch_truth(pr_number: int, repo: str) -> Truth:
    """One `gh api` call. Returns Truth with error filled if the PR doesn't
    exist or `gh` is unauthenticated — we treat 'cannot verify' as a
    violation so missing auth in CI fails loudly instead of silently passing."""
    try:
        proc = subprocess.run(
            [
                "gh",
                "api",
                f"repos/{repo}/pulls/{pr_number}",
                "--jq",
                "{state: .state, merged: .merged, merged_at: .merged_at, title: .title}",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except FileNotFoundError:
        return Truth(pr_number, None, None, None, error="gh CLI not found on PATH")
    except subprocess.TimeoutExpired:
        return Truth(pr_number, None, None, None, error="gh api timed out after 15s")

    if proc.returncode != 0:
        err = proc.stderr.strip().splitlines()[-1] if proc.stderr.strip() else "unknown gh error"
        return Truth(pr_number, None, None, None, error=err)

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        return Truth(pr_number, None, None, None, error=f"bad gh json: {e}")

    # `gh api` returns `state: "open"` / `"closed"` (lowercase) and a separate
    # `merged: true|false`. Normalize to MERGED/OPEN/CLOSED for clarity.
    raw_state = (data.get("state") or "").upper()
    is_merged = bool(data.get("merged"))
    normalized = "MERGED" if is_merged else raw_state or "UNKNOWN"

    return Truth(
        pr_number=pr_number,
        state=normalized,
        merged_at=data.get("merged_at"),
        title=data.get("title"),
    )


def find_violations(claims: Iterable[Claim], repo: str) -> tuple[list[Violation], dict[int, Truth]]:
    truths: dict[int, Truth] = {}
    violations: list[Violation] = []
    for claim in claims:
        if claim.pr_number not in truths:
            truths[claim.pr_number] = fetch_truth(claim.pr_number, repo)
        truth = truths[claim.pr_number]

        if truth.error is not None or not truth.is_actually_merged:
            violations.append(
                Violation(
                    pr_number=claim.pr_number,
                    claim_snippet=claim.snippet,
                    truth_state=truth.state,
                    truth_merged_at=truth.merged_at,
                    source_line=claim.source_line,
                )
            )
    return violations, truths


def render_table(violations: list[Violation], truths: dict[int, Truth]) -> str:
    if not violations:
        return "OK — every 'merged' claim matches GitHub reality.\n"

    lines = [
        "STATUS-TRUTH VIOLATIONS",
        "=" * 72,
        f"{len(violations)} claim(s) contradict GitHub.",
        "",
    ]
    for v in violations:
        truth = truths.get(v.pr_number)
        title = truth.title if truth and truth.title else "(unknown title)"
        actual = v.truth_state or "ERROR"
        if truth and truth.error:
            actual = f"ERROR: {truth.error}"
        lines.extend(
            [
                f"PR #{v.pr_number}  ({title})",
                f"  line {v.source_line}: {v.claim_snippet}",
                f"  claim:  merged",
                f"  actual: {actual}"
                + (f" at {v.truth_merged_at}" if v.truth_merged_at else ""),
                "",
            ]
        )
    lines.append("Source of truth: `gh api repos/<owner>/<repo>/pulls/<n>`.")
    lines.append("Fix the status document OR merge the PR. Don't reverse the test.")
    return "\n".join(lines) + "\n"


def render_json(violations: list[Violation], truths: dict[int, Truth]) -> str:
    return json.dumps(
        {
            "violations": [v.as_dict() for v in violations],
            "truths": {str(k): asdict(t) for k, t in truths.items()},
            "violation_count": len(violations),
        },
        indent=2,
        sort_keys=True,
    )


def load_input(args: argparse.Namespace) -> str:
    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            return f.read()
    if args.issue is not None:
        proc = subprocess.run(
            [
                "gh",
                "issue",
                "view",
                str(args.issue),
                "-R",
                args.repo,
                "--json",
                "body",
                "--jq",
                ".body",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if proc.returncode != 0:
            sys.stderr.write(f"gh issue view failed: {proc.stderr.strip()}\n")
            sys.exit(2)
        return proc.stdout
    return sys.stdin.read()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify 'merged' claims in a status document against GitHub."
    )
    src = parser.add_mutually_exclusive_group()
    src.add_argument("--file", help="Read input from a markdown/text file.")
    src.add_argument("--issue", type=int, help="Fetch issue body via gh issue view.")
    src.add_argument("--stdin", action="store_true", help="Read from stdin (default).")
    parser.add_argument(
        "--repo",
        default=os.environ.get("STATUS_TRUTH_REPO", DEFAULT_REPO),
        help=f"owner/repo (default: {DEFAULT_REPO}).",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of table.")
    parser.add_argument(
        "--exit-non-zero-on-violation",
        action="store_true",
        help="Exit 1 if any violation found (CI/gate mode).",
    )
    args = parser.parse_args(argv)

    text = load_input(args)
    claims = extract_claims(text)
    violations, truths = find_violations(claims, args.repo)

    if args.json:
        sys.stdout.write(render_json(violations, truths) + "\n")
    else:
        sys.stdout.write(render_table(violations, truths))

    if violations and args.exit_non_zero_on_violation:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
