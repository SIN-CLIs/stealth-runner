#!/usr/bin/env python3
"""SR-159 Path-Guard — enforce single-source-of-truth repo layout.

================================================================================
WHY THIS EXISTS  (read before you "fix" this file or argue with its verdict)
================================================================================

The stealth-runner repo has historically accumulated parallel Python source
trees because successive agents disagreed on the canonical layout. The empirical
record (do not lose this — it is the entire reason this guard exists):

    ┌──────┬────────────────────────────────────────────────────────────────┐
    │ SR # │ Drift event                                                    │
    ├──────┼────────────────────────────────────────────────────────────────┤
    │ 154  │ PR reformatted 100+ files into `agent-toolbox/core/network/`.  │
    │      │ That tree did not exist in the canonical layout. PR had to be  │
    │      │ discarded; cherry-picking onto `survey-cli/survey/network/`    │
    │      │ was ~10× faster than resolving conflicts.                      │
    │ 162  │ `survey-cli/survey/daemon.py` (file) coexisted with            │
    │      │ `survey-cli/survey/daemon/`  (package). Python silently makes  │
    │      │ the package win → `DaemonManager` becomes unreachable. CI was  │
    │      │ red for 7+ consecutive runs before anybody traced it.          │
    │ 159  │ This guard. Codifies the doctrine in a 5-line CI check so      │
    │      │ neither failure mode can recur.                                │
    └──────┴────────────────────────────────────────────────────────────────┘

This script is the *executable form* of the path doctrine that lives in
`survey-cli/AGENTS.md`. If the two ever disagree, AGENTS.md is intent and this
file is enforcement — patch BOTH or you have created the next SR-154.

================================================================================
THE DOCTRINE  (the only Python source root is survey-cli/survey/)
================================================================================

Allowed top-level entries:
    survey-cli/        ← ALL Python production code + tests + per-package docs
    stealth-captcha/   ← captcha solver subsystem (in-scope for the project)
    scripts/           ← bash + python utility scripts (CI helpers, audits)
    .github/           ← workflows, issue templates, CODEOWNERS
    docs/              ← markdown docs that are NOT AGENTS.md
                        (kept as a *directory* — individual doc files are
                         discouraged per project rule "docs go in code,
                         AGENTS.md is the brain". The directory is allowed so
                         legacy content can be deleted incrementally without
                         needing a guard-exception each time.)
    + root config files (pyproject.toml, README.md, CHANGELOG.md, ROADMAP.md,
      Makefile, .gitignore, .pre-commit-config.yaml, .semgrep_rules.yaml,
      .env.example, .gitnexus.yml, uv.lock, opencode.json, manifest.json,
      graph.json, skills-lock.json, com.stealth-sync.daemon.plist)

Banned top-level entries (any NEW file under these in a PR → guard fails):
    agent-toolbox/   ← dead, Agent 11's tree, replaced by survey-cli/survey/
    agent_toolbox/   ← typo-fork of above, dead on arrival
    core/            ← top-level `core` was a failed attempt from #154
    lib/             ← never canonical
    src/             ← never canonical for this repo (survey-cli/ is the src)

Banned drift patterns (anywhere in the tree):
    <X>.py + <X>/    ← module-vs-package shadow. Python silently picks the
                       package and makes the file unreachable. SR-162 saga.

================================================================================
HOW THE GUARD RUNS
================================================================================

Two modes:

    --diff [<base-ref>]
        CI mode. Compares working tree against <base-ref> (default:
        origin/main, or $GITHUB_BASE_REF if set by GitHub Actions). Fails
        only on files *introduced or modified* by this PR. Pre-existing
        legacy paths are grandfathered — this is intentional, so SR-159
        itself can land without first deleting agent-toolbox/. Shadow
        pairs are likewise only blocking if the PR touches one half of
        the pair; pre-existing shadows are reported as warnings (visible
        on every PR but non-blocking until a dedicated cleanup PR fixes
        them).

    --audit
        Local / manual mode. Walks the entire tree and reports every
        violation (banned dir, shadow pair, stray Python file) but exits 0.
        Use this to plan cleanup PRs.

    --strict
        Same as --audit but exits non-zero on any violation. Will be
        wired into CI *after* the cleanup PR removes legacy dirs.

Exit codes: 0 = clean | 1 = violations found | 2 = invocation error.

================================================================================
DESIGN NOTES  (so the next agent does not "refactor" this away)
================================================================================

- Pure stdlib. No deps. Must run on a fresh runner before `pip install`.
- No regex on commit messages, no parsing of issue numbers. Path manifest
  is a Python dict literal in this file. Single source of truth.
- The manifest is intentionally NOT moved into a YAML or markdown file —
  doing so would (a) re-introduce the "docs vs reality" drift class this
  guard exists to prevent and (b) violate the project rule that
  documentation lives inside the code that uses it.
- Pre-commit hook and CI workflow both shell out to this script with
  identical args. Keep CLI flags stable across both.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from typing import Iterable

# --- MANIFEST ---------------------------------------------------------------
# Everything below this line is "the doctrine in machine-readable form".
# Edit here, then mirror the human-readable version into
# `survey-cli/AGENTS.md` under the PATH DOCTRINE section. Do not let the
# two drift.

#: Top-level directories that are allowed to contain *new* files.
ALLOWED_TOP_DIRS: frozenset[str] = frozenset({
    "survey-cli",
    "stealth-captcha",
    "scripts",
    ".github",
    "docs",
})

#: Top-level directories that must not receive any *new* files via PRs.
#: Listed explicitly (rather than "everything not allowed") so that the
#: failure message can cite the historical SR that killed the directory.
BANNED_TOP_DIRS: dict[str, str] = {
    "agent-toolbox": "dead since SR-154 — code moved to survey-cli/survey/",
    "agent_toolbox": "typo-fork of agent-toolbox, never canonical",
    "core":          "top-level 'core' was rejected in SR-154; use "
                     "survey-cli/survey/<subpackage>/",
    "lib":           "never canonical for this repo",
    "src":           "never canonical for this repo; "
                     "survey-cli/ is the source tree",
}

#: Top-level files that are allowed at repo root. Anything *new* added at
#: root that is not in this allowlist (and is not a directory entry) trips
#: the guard. Existing root files are grandfathered.
ALLOWED_ROOT_FILES: frozenset[str] = frozenset({
    "pyproject.toml", "README.md", "CHANGELOG.md", "ROADMAP.md", "Makefile",
    ".gitignore", ".pre-commit-config.yaml", ".semgrep_rules.yaml",
    ".env.example", ".gitnexus.yml", "uv.lock", "opencode.json",
    "manifest.json", "graph.json", "skills-lock.json",
    "com.stealth-sync.daemon.plist",
})

#: Hidden top-level dirs that are tool config (`.claude`, `.opencode`,
#: `.qwen`, `.agents`). They are not policed by the guard — they only
#: contain prompts/config, never importable code.
IGNORED_TOP_PREFIXES: tuple[str, ...] = (".",)


# --- HELPERS ----------------------------------------------------------------


def _run(cmd: list[str]) -> str:
    """Run a subprocess and return stdout. Empty string on failure."""
    try:
        return subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def _changed_files(base_ref: str) -> list[str]:
    """Return files changed vs base_ref. Excludes deletions (we only police
    additions/modifications; deleting from a banned dir is *good*).
    """
    # `--diff-filter=d` excludes deletions. ACMRTUXB is everything else.
    out = _run(["git", "diff", "--name-only", "--diff-filter=ACMRTUXB",
                f"{base_ref}...HEAD"])
    return [line for line in out.splitlines() if line.strip()]


def _all_tracked_files() -> list[str]:
    out = _run(["git", "ls-files"])
    return [line for line in out.splitlines() if line.strip()]


def _top_segment(path: str) -> str:
    """First path segment. For root files, returns the filename itself."""
    return path.split("/", 1)[0]


# --- CHECKS -----------------------------------------------------------------


def check_banned_top_dirs(files: Iterable[str]) -> list[str]:
    """Flag any file whose top-level segment is in BANNED_TOP_DIRS."""
    violations = []
    for f in files:
        top = _top_segment(f)
        if top in BANNED_TOP_DIRS:
            violations.append(
                f"  BANNED DIR     {f}\n"
                f"                 reason: {BANNED_TOP_DIRS[top]}"
            )
    return violations


def check_unknown_top(files: Iterable[str]) -> list[str]:
    """Flag any file whose top-level segment is neither allowed, banned,
    a tool-config dot-dir, nor a recognised root file.
    """
    violations = []
    for f in files:
        top = _top_segment(f)
        if top in ALLOWED_TOP_DIRS:
            continue
        if top in BANNED_TOP_DIRS:
            continue  # already reported by check_banned_top_dirs
        if top.startswith(IGNORED_TOP_PREFIXES):
            continue
        if "/" not in f:  # root file
            if top in ALLOWED_ROOT_FILES:
                continue
            violations.append(
                f"  UNKNOWN ROOT   {f}\n"
                f"                 add it to ALLOWED_ROOT_FILES in "
                f"scripts/path_guard.py if it is intentional"
            )
        else:
            violations.append(
                f"  UNKNOWN DIR    {f}\n"
                f"                 top-level '{top}/' is not on the "
                f"allowlist; if this is a new canonical area, propose it "
                f"on the issue first (STOP-rule, see AGENTS.md)"
            )
    return violations


def find_shadow_pairs(all_files: Iterable[str]) -> list[tuple[str, str]]:
    """Return every `<X>.py` ↔ `<X>/` sibling pair in the tracked tree as
    (file_path, dir_path) tuples. Python will pick the package and silently
    hide the module — see SR-162.

    This is split from the "format violations" step so the caller can decide
    whether a given pair is *introduced by this PR* (→ blocking) or *already
    existed in main* (→ informational warning that should not block a
    governance PR — see SR-159 PR body).
    """
    files_by_parent: dict[str, set[str]] = {}
    dirs_by_parent: dict[str, set[str]] = {}
    for f in all_files:
        parent = os.path.dirname(f)
        name = os.path.basename(f)
        files_by_parent.setdefault(parent, set()).add(name)
        # every intermediate segment of f is a directory under its own parent
        parts = f.split("/")
        for i in range(1, len(parts)):
            d_parent = "/".join(parts[: i - 1]) if i > 1 else ""
            d_name = parts[i - 1]
            dirs_by_parent.setdefault(d_parent, set()).add(d_name)

    pairs: list[tuple[str, str]] = []
    for parent, names in files_by_parent.items():
        dirs_here = dirs_by_parent.get(parent, set())
        for name in names:
            if not name.endswith(".py"):
                continue
            stem = name[:-3]
            if stem in dirs_here:
                full_file = f"{parent}/{name}" if parent else name
                full_dir = f"{parent}/{stem}/" if parent else f"{stem}/"
                pairs.append((full_file, full_dir))
    return pairs


def _format_shadow(file_path: str, dir_path: str) -> str:
    return (
        f"  SHADOW PAIR    {file_path} vs {dir_path}\n"
        f"                 Python imports the package and hides the module. "
        f"Rename one (SR-162 precedent)."
    )


def partition_shadow_pairs(
    all_files: Iterable[str],
    changed_files: Iterable[str],
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Split shadow pairs into (touched_by_diff, preexisting). A pair is
    'touched_by_diff' if either half is in `changed_files`.

    The 'touched' set blocks CI in --diff mode (the PR is actively making
    the problem worse or introducing it fresh). The 'preexisting' set is
    surfaced as a warning so it stays visible but does not block governance
    work — see SR-159 PR body for rationale.
    """
    changed = set(changed_files)
    touched: list[tuple[str, str]] = []
    preexisting: list[tuple[str, str]] = []
    for file_path, dir_path in find_shadow_pairs(all_files):
        # A directory match means any changed file *under* that directory.
        dir_prefix = dir_path  # already ends with '/'
        if file_path in changed or any(c.startswith(dir_prefix) for c in changed):
            touched.append((file_path, dir_path))
        else:
            preexisting.append((file_path, dir_path))
    return touched, preexisting


# --- MAIN -------------------------------------------------------------------


def _resolve_base_ref(explicit: str | None) -> str:
    if explicit:
        return explicit
    # GitHub Actions sets this on pull_request events.
    ref = os.environ.get("GITHUB_BASE_REF")
    if ref:
        return f"origin/{ref}"
    return "origin/main"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="SR-159 Path-Guard: enforce repo layout doctrine.",
    )
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--diff", nargs="?", const="", default=None,
                      metavar="BASE_REF",
                      help="check files changed vs BASE_REF "
                           "(default: $GITHUB_BASE_REF or origin/main)")
    mode.add_argument("--audit", action="store_true",
                      help="walk entire tree, report violations, exit 0")
    mode.add_argument("--strict", action="store_true",
                      help="walk entire tree, exit non-zero on any violation")
    args = p.parse_args(argv)

    if args.diff is not None:
        base_ref = _resolve_base_ref(args.diff or None)
        files = _changed_files(base_ref)
        mode_label = f"diff vs {base_ref}"
    elif args.audit or args.strict:
        files = _all_tracked_files()
        mode_label = "full-tree audit"
    else:
        base_ref = _resolve_base_ref(None)
        files = _changed_files(base_ref)
        mode_label = f"diff vs {base_ref} (default)"

    if not files:
        print(f"path-guard: {mode_label}: no files to check — OK")
        return 0

    print(f"path-guard: {mode_label}: {len(files)} file(s) to check")

    violations: list[str] = []
    violations += check_banned_top_dirs(files)
    violations += check_unknown_top(files)

    # Shadow-pair handling depends on mode.
    #
    # --strict / --audit: report every shadow pair in the tree (`files`
    # already equals the full tracked set in those modes).
    # --diff: only *touched* shadow pairs are blocking — pre-existing pairs
    # are surfaced as warnings so we do not punish governance/cleanup PRs
    # for tech debt they did not create. See SR-159 PR body.
    all_tracked = _all_tracked_files()
    warnings: list[str] = []
    if args.audit or args.strict:
        for fp, dp in find_shadow_pairs(all_tracked):
            violations.append(_format_shadow(fp, dp))
    else:
        touched, preexisting = partition_shadow_pairs(all_tracked, files)
        for fp, dp in touched:
            violations.append(_format_shadow(fp, dp))
        for fp, dp in preexisting:
            warnings.append(_format_shadow(fp, dp))

    if warnings:
        print("")
        print("path-guard: pre-existing shadow pairs (warnings, not blocking):")
        print("─" * 72)
        for w in warnings:
            print(w)
        print("─" * 72)
        print("Run `python scripts/path_guard.py --strict` locally to see "
              "the full list. Resolve in a dedicated cleanup PR (SR-162-class).")

    if not violations:
        if warnings:
            print("path-guard: OK — no new violations from this PR.")
        else:
            print("path-guard: OK — layout matches SR-159 doctrine.")
        return 0

    print("")
    print("path-guard: VIOLATIONS")
    print("─" * 72)
    for v in violations:
        print(v)
    print("─" * 72)
    print("")
    print("Doctrine: survey-cli/AGENTS.md § PATH DOCTRINE (SR-159).")
    print("If you believe this verdict is wrong, STOP and comment on the "
          "issue rather than working around the guard.")

    if args.audit and not args.strict:
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
