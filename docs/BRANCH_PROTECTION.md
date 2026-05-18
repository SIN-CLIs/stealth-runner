# Branch Protection — Single Source of Truth

> **Status:** Required for `main`. Owner: CEO. Last reviewed: 2026-05-17.
>
> This document is the *only* place that names which CI checks must be
> green to merge. If GitHub's UI and this file disagree, this file wins
> and someone fixes the UI.

## Why this matters

The 2026-05-13 audit found a status document listing four pull requests
as completed and CI-green while the GitHub API reported all four as still
open with no merge timestamp. Branches existed, code existed, the merge
event never happened. The downstream symptoms (missing visual_hash, a
shorter captcha chain than documented, no verifier in the survey graph)
all flowed from that one reporting defect.

We are closing this hole with three locks:

1. **No direct pushes to `main`.** Period. Even one-line "trivial" fixes
   go through a PR.
2. **`truth-gate` is required.** Every PR's claim about merged work is
   cross-checked against `gh api repos/.../pulls/<n>` before merge.
3. **One required status name** so workflow refactors don't silently
   un-protect `main`.

## Required status checks (Branch protection rule for `main`)

Set in **Settings → Branches → Branch protection rules → `main`**:

| Setting | Value |
|---|---|
| Require a pull request before merging | ✅ |
| Require approvals | 1 |
| Dismiss stale pull request approvals when new commits are pushed | ✅ |
| Require status checks to pass before merging | ✅ |
| Require branches to be up to date before merging | ✅ |
| **Required status check** | **`truth-gate`** (SR-218 / CEO-WAVE-1) |
| Require conversation resolution before merging | ✅ |
| Require linear history | ✅ |
| Do not allow bypassing the above settings | ✅ (applies to admins, including CEO) |
| Restrict who can push to matching branches | empty (everyone goes via PR) |
| Allow force pushes | ❌ |
| Allow deletions | ❌ |

> ⚠️ Only `truth-gate` is the required check name on purpose. The
> underlying `scan-markdown` and `scan-issue-body` jobs are
> implementation detail and can be renamed without touching the
> protection rule. `truth-gate` aggregates them and reports one stable
> name.

## Why no `paths:` filter on `status-truth.yml`

GitHub's required-check semantics treat a workflow that *does not run* on
a given PR as `expected, never reported`, which blocks the merge button
forever for any PR that does not touch the filtered paths. The earlier
version of `status-truth.yml` had a `paths: ["**/*.md", ...]` filter,
which would have made every PR with code-only changes unmergable once we
flip the required-check switch.

The current workflow runs on every PR but filters internally via
`git diff` before invoking `check_status_truth.py`. Cost: one
`actions/checkout` (fetch-depth 0) + one `git diff`. Benefit: legitimate
green checks for code-only PRs, real red on status-doc lies, no
permanently-skipped-required-check trap.

## Operational rules tied to this protection

- **PR-only merges.** "I'll just push this real quick" violates rule 1.
  Even the CEO opens a PR.
- **No `--no-verify`** unless the user explicitly approves it on the PR.
- **No `git push --force` to `main`.** Rebase locally, push to a branch,
  open a PR.
- **Closing an issue requires a PR link.** "Closed as not-a-bug" without
  a reproducer or a PR fix is rejected by the next reviewer who notices.

## How to verify locally before opening a PR

```bash
# 1. Are all the "merged" claims in the docs you touched real?
git diff --name-only --diff-filter=AM origin/main...HEAD -- '*.md' \
  | xargs -I {} python scripts/check_status_truth.py --file {} \
      --exit-non-zero-on-violation

# 2. Same for an issue body (replace 999 with the actual issue number):
python scripts/check_status_truth.py --issue 999 --exit-non-zero-on-violation
```

Both commands exit `0` when the document's claims match GitHub. Exit
`1` means at least one PR you said was merged is in fact not.

## Bypass procedure (intentionally annoying)

If a real emergency makes you want to skip `truth-gate`:

1. Open an `incident/` document explaining what is broken AND what
   guarantee `truth-gate` would have given that you are knowingly
   waiving.
2. CEO countersigns with a comment on the PR.
3. Temporarily mark the check non-required, merge, immediately re-mark
   it required.
4. The incident document gets reviewed in the next retro; if the bypass
   was wrong, we tighten further, not loosen.

There is no shortcut. The point of the gate is that nobody — least of
all the CEO — can tell the team "merged" when GitHub says "open".
