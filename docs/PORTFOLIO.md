# SIN-CLIs portfolio — single source of truth

> **Status:** Authoritative. Owner: CEO. Last reviewed: 2026-05-17.
> **Pairs with:** [`AGENTS.md`](../AGENTS.md), [`docs/BRANCH_PROTECTION.md`](./BRANCH_PROTECTION.md), [`docs/EVAL_HARNESS.md`](./EVAL_HARNESS.md), the CEO Audit memo (sessions/, dated 2026-05-17).

This file is the **only** place that says which SIN-CLIs repository is in which lifecycle state. If GitHub's UI, an agent's memory, or a session-log narrative says otherwise, this file wins until a separate PR updates it.

## North Star (90 days)

> One product, one repo, one truth. By 17.08.2026, deliver a single-account `stealth-runner` that reproducibly clears **≥85 % completion rate** on the top-3 providers, with **€0 captcha cost per survey**, **MTTR ≤ 30 s** after crash via SqliteSaver checkpointer + cash-out idempotency ledger, and **0** Status-Truth violations per sprint.

KPIs are tracked in `survey-cli/logs/earnings-*.jsonl` (real money) and `evals/trajectory/last-report.json` (graph behaviour).

## The 30 → 5 consolidation plan

We have 30 SIN-CLIs repositories for 1 revenue product. The CEO audit (2026-05-13 → 2026-05-17) ruled that this is sprawl, not portfolio. The target end-state is **5 repos**.

### KEEP — five repos, named and final

| repo | role | rationale |
|---|---|---|
| **`SIN-CLIs/stealth-runner`** | Production monorepo. The product. | Where the money flows through. Default branch `main`, branch-protected per `docs/BRANCH_PROTECTION.md`, gated on `truth-gate` + the new `trajectory eval`. |
| **`SIN-CLIs/stealth-suite`** | Reusable Python packages: `core`, `guardian`, `router`, `memory`, `cache`, `config`, `cost`, `swarm`, `optimizer`. | Single source for cross-cutting building blocks. `stealth-runner` consumes them as installed wheels, not as embedded copies. |
| **`SIN-CLIs/stealth-skills`** | Private domain-knowledge skills (HeyPiggy / provider-specifics). | Intentionally non-public. Never spun out. |
| **`SIN-CLIs/stealth-captcha`** | Captcha solver chain (5 stages, €0 default chain). | Has standalone value as a possible OSS spin-out for hiring/marketing. Already pinned with `[stealth]` Patchright extra in pyproject. |
| **`SIN-CLIs/cua-touch`** | Cross-platform CUA actuation (Python + Swift). | Until macOS/Linux primitives diverge enough to fork properly, this stays its own repo. Re-evaluate at end of Welle 3. |

### MERGE & ARCHIVE — wave-1 inbound consolidation (Tag 8-30)

Pull these into `stealth-runner/` as packages, then archive the upstream repo. Archive ≠ delete: GitHub keeps the history; nobody can push or open issues against it.

| upstream repo | destination in `stealth-runner` | first PR |
|---|---|---|
| `stealth-mind` | `survey-cli/survey/learn/mind/` | TBD |
| `stealth-sync` | `survey-cli/survey/daemon/sync/` | TBD (the embedded `pyproject.toml` already points here) |
| `stealth-sota` | `survey-cli/survey/reliability/sota/` | TBD |
| `stealth-dynamic` | `survey-cli/survey/providers/dynamic/` | TBD |
| `stealth-session` | `survey-cli/survey/daemon/session/` | TBD |

### MERGE INTO `stealth-suite` (Tag 31-60)

Already-redundant standalone packages collapse into the monorepo:

`stealth-core`, `stealth-axiom` (→ `@stealth/router`), `stealth-guardian`, `stealth-memory`, `stealth-cache`, `stealth-config`, `stealth-cost`, `stealth-swarm`, `stealth-optimizer`, `stealth-compressor`, `stealth-batch`, `stealth-lora`, `stealth-lora-transfer`.

Per package, the consolidation PR must (a) rebase the package's tests under `packages/<name>/tests/`, (b) update the package's `pyproject.toml` so it ships under the `@stealth/<name>` namespace, (c) add a redirect note to the upstream repo's README, (d) archive the upstream repo.

### ARCHIVE NOW — banned / legacy / wrong-platform

Done in the next chore PR (`chore(portfolio): archive deprecated repos — SR-241`):

| repo | reason |
|---|---|
| `skylight-cli` | LEGACY (25 open issues, AXPress drift on Chrome 148/macOS 26). Wrong platform for our Linux-browser stack. |
| `playstealth-cli` | DEPRECATED + on `banned.md`. Was replaced by Patchright via [#236](https://github.com/SIN-CLIs/stealth-runner/pull/236). |
| `webauto-nodriver` | ABSOLUTE BANNED (recorded in `banned.md` since 2026-05-04). |
| `unmask-cli` | TypeScript drift, no caller in `stealth-runner`. |
| `screen-follow` | macOS-only Swift, not on the production path. |
| `ax-graph` | macOS-only, replaced by `cdp_universal.scan()`. |
| `macos-ax-cli` | Same as above. |

### TBD — re-evaluate at end of each wave

- `survey-cli` (already embedded under `stealth-runner/survey-cli/`) — separate top-level repo only because git history was easier to keep that way during the embed. Mirror, not source. Archive once the embedded copy has 30 days of clean Status-Truth runs.
- `cua-touch` — separate repo OK for now, but if Linux primitives stay in `stealth-runner/survey-cli/survey/cdp_actuator.py` we collapse this in Welle 3.

## What MUST NOT happen

- **No new repo creation.** If anyone wants a "small clean place for X", the answer is a new package directory in `stealth-suite` or a folder in `stealth-runner`. Period. New repos are a 30-day-CEO-veto-required event.
- **No `--force-push` to archived repos.** Archived means archived. If history needs a redo, open the repo, do it, archive it again.
- **No "I'll merge it later" features in soon-to-be-archived repos.** That work is wasted; tell the team in standup, not in a PR.
- **No Direct-Pushes against `stealth-runner/main`.** `truth-gate` plus branch protection enforce this; bypassing them per `docs/BRANCH_PROTECTION.md` requires an `incidents/` document AND CEO countersign.

## Definition of Done for this consolidation

The portfolio is "consolidated" when:

1. The 5 KEEP repos are alive and have green CI.
2. Every other repo on the GitHub org page is in `archived` state.
3. `stealth-runner` and `stealth-suite` consume each other only via versioned wheels (no `git submodule`, no path-injection).
4. This file's `MERGE & ARCHIVE` and `MERGE INTO stealth-suite` tables are empty (or contain only the entries that were already moved, marked DONE with a PR link).

That state is what we're measuring against in retros.

## How to update this file

1. Open a PR titled `chore(portfolio): <change> — <reason>`.
2. Update only this file plus, if needed, the matching CI gate.
3. CEO is required reviewer. No same-day landings without a Slack thread.
4. The PR body MUST link to the relevant `incidents/` doc when archiving anything that someone is currently using.

## Why this file exists

CRITIC-AUDIT 2026-05-13 found a pattern we cannot afford: status documents disagreed with GitHub reality, repos were referenced as "the new home" without anyone moving the code, and one PR could land referencing four "merged" branches that were all still open. `docs/BRANCH_PROTECTION.md` solves the per-PR symptom; this file solves the per-repo symptom. Read together they say: every claim about "where the code lives" or "what state the repo is in" has exactly one truth, and that truth is checked into version control.
