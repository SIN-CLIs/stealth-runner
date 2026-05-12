# SR-104: `survey learn status` — read-only inbox dashboard

**Status:** OPEN
**Owner:** v0-CEO-Session
**Spawned by:** v0-CEO-Session am 2026-05-12 nach Close von #102
**Parallel-safe with:** PR #100 (smoke), #101 (eval-harness), #103 (qualification_rules.py)

---

## Zweck

Nach Merge von #56 (Phase 2 LLM-Suggester) und #102 (source-aware batch-review)
hat ein Operator eine `pattern-suggestions-*.jsonl`-Inbox mit drei Status-
Zustaenden (`open`/`accepted`/`rejected`) und zwei Source-Tags
(`substring`/`llm`). Bisher gibt es **keine Moeglichkeit, den State der
Inbox zu sehen** ohne JSONL manuell zu greppen.

Typische Fragen die heute unbeantwortet sind:

- "Wieviele open suggestions habe ich, aufgeschluesselt nach source?"
- "Welche family ist am haeufigsten requested?"
- "Wie alt ist die aelteste open suggestion?"
- "Ist die Inbox drained (fuer CI smoke-check)?"

`survey learn status` schliesst diese Lücke. Pure read-only — schreibt
NIE in die Inbox, NIE in profile-Dateien, NIE in audit-logs.

---

## Scope (exakt 1 neue Datei + 1 modifizierte + 1 Test-Datei)

| Datei | Status | Aenderung |
|---|---|---|
| `survey-cli/survey/learn/status.py` | NEU | Pure functions: `summarize_inbox`, `StatusReport`, formatting helpers |
| `survey-cli/survey/learn/cli.py` | MOD | NEW `p_sts` subparser + `cmd_status` function (additiv, neuer Block) |
| `survey-cli/survey/learn/__init__.py` | MOD | Exports |
| `survey-cli/tests/test_learn_status.py` | NEU | 15+ Tests |

### CLI

```
survey learn status [--input PATH | --logs DIR]
                    [--filter-source {all,substring,llm}]
                    [--filter-status {all,open,accepted,rejected}]
                    [--top N]
                    [--json]
                    [--require-empty]
```

Defaults:
- `--input` not set: scan all `pattern-suggestions-*.jsonl` in `--logs` dir
- `--filter-*` = `all`
- `--top` = 10 (limit fuer top-families und top-labels)
- `--json` = false (human table by default)
- `--require-empty` = false (siehe unten)

### Output (human, default)

```
[learn] inbox summary  (2 files, 47 records)

By status:
  open       28   59.6%
  accepted   15   31.9%
  rejected    4    8.5%

By source (open records only):
  substring  19   67.9%
  llm         9   32.1%

Top families (open records):
  phone           7
  household_size  5
  income          4
  <NEW>           3   (no family suggested)
  ...

Top labels (open, by count):
  textbox  "telefonnummer"   count=12
  textbox  "haushaltsgrosse" count=8
  ...

Oldest open record: 2026-04-22 (20 days ago)
```

### Output (`--json`)

```json
{
  "total_records": 47,
  "files_scanned": 2,
  "by_status": {"open": 28, "accepted": 15, "rejected": 4},
  "by_source_open": {"substring": 19, "llm": 9},
  "top_families_open": [{"family": "phone", "count": 7}, ...],
  "top_labels_open": [{"role": "textbox", "label": "telefonnummer", "count": 12}, ...],
  "oldest_open_iso": "2026-04-22T14:33:01",
  "oldest_open_age_days": 20
}
```

### `--require-empty`

Returns exit 1 if any `open` records exist (after filters applied).
Use case: CI smoke-check that inbox is drained before a release.
Pure status-flag, no side effects.

---

## Architektur-Entscheidungen

**A) Pure functions in `status.py`.** `summarize_inbox(records: Iterable[dict]) -> StatusReport` ist deterministisch und ohne I/O. CLI macht das I/O.

**B) Read-only, ohne ausnahme.** Status-CLI oeffnet keine Datei mit `"w"` oder `"a"`, schreibt keine logs, ruft keine apply-Funktionen.

**C) Datum-Heuristik:** Suchen `first_seen` Feld auf records (existiert in aggregator output ab #56 — pruefen, ansonsten field `created_at` oder mtime des input-files als fallback). Wenn keine Daten available, `oldest_open_*` = null.

**D) Multi-file scan default.** In `survey-cli/logs/` existieren typically mehrere `pattern-suggestions-YYYYMMDD.jsonl` files. `--input` overridet auf single-file.

**E) Skip status-flip semantics.** Records mit `status` field missing → behandeln als `"open"` (consistent mit `apply.py:InboxEntry.from_dict` default und `review.py:plan_action`).

---

## Out-of-Scope (LOCK)

- KEINE Aenderung an `aggregator.py`, `apply.py`, `suggester.py`, `llm_client.py`, `review.py`
- KEINE Aenderung an `qualification_rules.py` (#103 territory)
- KEINE Aenderung an `evals/*` (#101 territory)
- KEINE Aenderung an `.github/workflows/*` (#100 territory)
- KEINE neuen runtime-Dependencies
- KEINE neuen Subparser ausser `p_sts`
- Status-CLI darf NIE schreiben (auch nicht `--repair` / `--migrate` / aehnlich)

---

## Acceptance Criteria

- [ ] `status.py` enthaelt pure functions ohne I/O (testbar isoliert)
- [ ] 15+ Tests in `test_learn_status.py`, alle gruen
- [ ] `survey learn status --help` zeigt alle 6 neuen Flags
- [ ] Default-Mode scannt `survey-cli/logs/pattern-suggestions-*.jsonl`
- [ ] `--input PATH` overridet auf single file
- [ ] `--filter-source {all,substring,llm}` filtert correctly im output
- [ ] `--filter-status {all,open,accepted,rejected}` filtert correctly
- [ ] `--top N` limitiert top-families und top-labels listen
- [ ] `--json` emittiert parseable JSON (validated via `json.loads`)
- [ ] `--require-empty` exit 1 wenn open-count > 0, else exit 0
- [ ] Default-Mode (kein --require-empty) immer exit 0 (read-only diagnostic)
- [ ] Status-CLI oeffnet KEINE Datei mit `"w"` oder `"a"` (audit via test)
- [ ] Bestehende 200 Tests bleiben gruen
- [ ] Closes #104 in commit-message
- [ ] `_plans/104-learn-status-dashboard.md` geloescht im selben commit (rule A4)

---

## Test Plan

15+ Tests in `test_learn_status.py`:

**TestSummarizeInbox (pure functions):**
- Empty records → zero counts
- Mixed status counts correctly
- Missing status field → treated as "open"
- Missing source field → treated as "substring"
- Top-N truncation respected
- `<NEW>` bucket for records with `suggested_family == null`
- Oldest open uses `first_seen` if present, falls back to null

**TestFilters (pure functions):**
- `filter_source="llm"` excludes substring records
- `filter_status="open"` excludes accepted/rejected
- Combined filters compose correctly

**TestCmdStatus (integration via main()):**
- Multi-file scan finds all `pattern-suggestions-*.jsonl`
- Single-file via `--input` works
- `--json` output is valid JSON
- `--require-empty` exit 1 with open records
- `--require-empty` exit 0 with no open records
- `--require-empty` exit 0 after filter excludes all open
- Read-only audit: status command does NOT create accepted/rejected files

---

## File-Boundary-Matrix

| Surface | PR #100 | #101 | #103 | **#104 (this)** |
|---|---|---|---|---|
| `survey/learn/status.py` | unchanged | unchanged | unchanged | **NEW** |
| `survey/learn/cli.py` | MOD (`p_app` `--target`) | unchanged | unchanged | **MOD (`p_sts` NEW block)** |
| `survey/learn/__init__.py` | unchanged | unchanged | unchanged | **MOD (exports)** |
| `survey/learn/{aggregator,apply,review,suggester,llm_client}.py` | unchanged | unchanged | unchanged | **unchanged** |
| `survey/qualification_rules.py` | unchanged | unchanged | MOD | **unchanged** |
| `evals/*` | unchanged | NEW | unchanged | **unchanged** |
| `.github/workflows/*` | NEW | NEW | unchanged | **unchanged** |
| `tests/test_learn_status.py` | unchanged | unchanged | unchanged | **NEW** |

`cli.py`: PR #100 modifiziert `p_app` Block (lines ~250-265), SR-104 fuegt einen
NEUEN `p_sts` Block hinzu (am Ende der subparser-Definitionen). Verschiedene
Hunks, git-auto-merge mechanisch trivial.

Konfliktrisiko: 0.

---

## Estimated complexity

**S** — kleiner als #102, klar abgegrenzte read-only Surface. Pure functions
+ trivialer CLI wrapper. Ein PR-Cycle.

---

## References

- #102 (closed `ecc6ba1`) — fuehrt das `status`-Feld ein, das hier aggregiert wird
- #56 (closed `424e928`) — fuehrt das `source`-Feld ein, das hier gruppiert wird
- `survey/learn/aggregator.py:128-167` — record-Schema
- AGENTS.md §13.8 — CI-Trigger-Matrix (status-CLI ist nicht gate-tauglich → kein CI-Job)
