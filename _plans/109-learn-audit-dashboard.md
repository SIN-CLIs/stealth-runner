# SR-109: `survey learn audit` — read-only audit-log dashboard

**Status:** OPEN
**Owner:** v0-CEO-Session
**Spawned by:** v0-CEO-Session am 2026-05-12
**Parallel-safe with:** PR #100, PR #105, #101, #106, #108

---

## Zweck

#104 (`survey learn status`) gibt einem Operator die View auf das, was
**noch im Inbox steckt**. Diese Story braucht die symmetrische Pendant-View:
was wurde **schon angewendet**, und mit welchen Entscheidungen?

`apply.py` schreibt audit-records nach `logs/learn-applied-{ISO}.jsonl`
(`_audit_log_path`). Schema-Record (verifiziert):

```python
{
  "decision": "applied" | "rejected_by_gate" | "rejected_by_reviewer"
              | "rejected_by_ast",
  "reason":    "<wenn reject>",   # optional
  "family":    "phone",            # nur bei "applied"
  "keyword":   "telefonnummer",    # nur bei "applied"
  "source":    "substring" | "llm",
  "confidence": 0.85,
  "model":     "openai/gpt-5-mini" | null,
  "prompt_hash": "abc123..." | null,
  "entry":     {<full InboxEntry dict, bei rejects>}
}
```

Diese sind die einzige machine-readable Spur dessen, was apply tatsaechlich
gemacht hat. `survey learn audit` aggregiert sie.

---

## Scope (1 neue Datei + 2 MOD + 1 Test-Datei)

| Datei | Status | Aenderung |
|---|---|---|
| `survey-cli/survey/learn/audit.py` | NEU | Pure functions: `summarize_audit`, `AuditReport`, formatters |
| `survey-cli/survey/learn/cli.py` | MOD | Additiver `p_aud` subparser block (am Ende) |
| `survey-cli/survey/learn/__init__.py` | MOD | Exports |
| `survey-cli/tests/test_learn_audit.py` | NEU | 18+ Tests |

### CLI

```
survey learn audit [--logs DIR | --input PATH]
                   [--filter-decision X]   # all/applied/rejected_*
                   [--filter-source X]     # all/substring/llm
                   [--filter-family F]
                   [--since ISO]           # only records >= timestamp
                   [--top N]
                   [--json]
```

Defaults: `--logs` = `survey-cli/logs/`, `--filter-*` = `all`,
`--top` = 10, `--json` = false.

### Output (human, default)

```
[learn] audit summary  (3 file(s), 145 record(s))

By decision:
  applied              98   67.6%
  rejected_by_gate     31   21.4%
  rejected_by_reviewer 12    8.3%
  rejected_by_ast       4    2.8%

By source (applied only):
  substring   72   73.5%
  llm         26   26.5%

Top families (applied):
  phone               18
  household_size      14
  income              12
  age                  9
  ...

Top labels (applied, by frequency):
  textbox  "telefonnummer"    applied 8x
  textbox  "haushaltsgrosse"  applied 5x
  ...

Top LLM models used (applied):
  openai/gpt-5-mini      24x
  anthropic/claude-...    2x

Time-range:
  first applied: 2026-04-15T...
  last applied:  2026-05-11T...
```

### Output (`--json`)

```json
{
  "files_scanned": 3,
  "total_records": 145,
  "by_decision": {"applied": 98, "rejected_by_gate": 31, ...},
  "by_source_applied": {"substring": 72, "llm": 26},
  "top_families_applied": [{"family": "phone", "count": 18}, ...],
  "top_labels_applied": [{"role": "textbox", "label": "telefonnummer",
                          "count": 8}, ...],
  "by_model": {"openai/gpt-5-mini": 24, ...},
  "first_applied_iso": "2026-04-15T...",
  "last_applied_iso":  "2026-05-11T..."
}
```

---

## Architektur-Entscheidungen

**A) Pure functions in `audit.py`.** Identisches Pattern wie `status.py`
(SR-104): `summarize_audit(records, filters) -> AuditReport` ist
deterministisch und ohne I/O. CLI macht das I/O. Macht die Tests trivial.

**B) Strict read-only.** Audit-CLI darf NIE schreiben. Audit via Test
`test_audit_never_opens_files_for_writing` (mock `builtins.open` analog
zu #104).

**C) Defensive schema-defaults.** Records ohne `source`-Feld werden mit
`"substring"` defaulted (legacy records pre-#56). Records ohne `decision`
gibt es nicht — `apply.py` schreibt das Feld immer.

**D) Records mit `decision != "applied"` haben NICHT `family`/`keyword`
top-level.** Das `entry`-dict enthaelt sie aber. Bei rejects holen wir
`source` aus `entry.source` als fallback. Symmetrie:

```python
def _normalize_source(rec):
    src = rec.get("source")
    if src:
        return src
    entry = rec.get("entry") or {}
    return entry.get("source") or "substring"
```

**E) `--since` Filter.** ISO-timestamp parsing wie in #104. Records werden
nach ihrem Datei-timestamp (im filename `learn-applied-{ISO}.jsonl`)
zugeordnet — kein per-record-timestamp im audit-schema. Wenn ein
`--since 2026-05-01` gegeben ist, wird die Datei-`{ISO}`-Komponente
geparsed und gefiltert.

**F) `by_model` ist neu (kein Pendant in #104).** Zaehlt nur applied-
records mit nicht-leerem `model`-Feld. Gibt einem Operator einsight ob
sein LLM-Phase-2 (#56) tatsaechlich relevant beitraegt vs. nur substring.

---

## Out-of-Scope (LOCK)

- KEINE Aenderung an `aggregator.py`, `apply.py`, `suggester.py`,
  `llm_client.py`, `review.py`, `status.py`
- KEINE Aenderung an `qualification_rules.py` (#103/#105)
- KEINE Aenderung an `survey/captcha/*`, `survey/graph/*` (#106)
- KEINE Aenderung an `evals/*` (#101)
- KEINE Aenderung an `.github/workflows/*` (#100, #101)
- KEINE Aenderung an `scripts/*` (#108)
- KEINE neuen runtime-Dependencies
- KEINE Subparser ausser `p_aud`
- KEINE Modifikation der `learn-applied-*.jsonl` files
- Audit-CLI darf NIE schreiben (kein `--repair`, `--rotate`, aehnlich)

---

## Acceptance Criteria

- [ ] `audit.py` enthaelt pure functions ohne I/O (testbar isoliert)
- [ ] 18+ Tests in `test_learn_audit.py`, alle gruen
- [ ] `survey learn audit --help` zeigt alle 7 neuen Flags
- [ ] Default-Mode scannt `survey-cli/logs/learn-applied-*.jsonl`
- [ ] `--input PATH` overridet auf single file
- [ ] `--filter-decision {all,applied,rejected_by_gate,rejected_by_reviewer,rejected_by_ast}` filtert correctly
- [ ] `--filter-source {all,substring,llm}` filtert correctly
- [ ] `--filter-family F` filtert auf top-level `family` UND `entry.family`
- [ ] `--since ISO` filtert correctly (Datei-timestamp basiert)
- [ ] `--top N` limitiert top-listen
- [ ] `--json` emittiert parseable JSON
- [ ] Read-only audit: command oeffnet KEINE Datei mit `"w"/"a"/"x"/"+"`
- [ ] Bestehende 226+ Tests bleiben gruen
- [ ] `survey learn --help` listet `audit` als subcommand
- [ ] Commit-Message referenziert `Closes #109`
- [ ] `_plans/109-learn-audit-dashboard.md` geloescht im selben commit (rule A4)

---

## Test Plan

18+ Tests:

**TestSummarizeAudit (pure functions):**
- Empty input → zero counts
- by_decision counts correctly
- by_source_applied excludes non-applied records
- Top-N families limited correctly
- _normalize_source falls back to `entry.source` for rejects
- _normalize_source defaults to "substring" if missing everywhere
- by_model only counts applied + non-empty model
- Time-range first/last extracted from records

**TestFilters (pure functions):**
- filter_decision="applied" excludes rejects
- filter_source="llm" excludes substring
- filter_family="phone" excludes other families
- Combined filters compose (AND)
- --since timestamp filter respects filename ISO

**TestCmdAudit (integration via main()):**
- Multi-file scan finds all `learn-applied-*.jsonl`
- Single-file via `--input` works
- JSON output is valid JSON
- Empty logs dir → exit 0
- All filter flags + JSON output

**TestReadOnlyAudit:**
- audit command does NOT open any file with "w"/"a"/"x"/"+"

---

## File-Boundary-Matrix

| Surface | PR #100 | PR #105 | #101 | #106 | #108 | **#109 (this)** |
|---|---|---|---|---|---|---|
| `survey/learn/audit.py` | unchanged | unchanged | unchanged | unchanged | unchanged | **NEW** |
| `survey/learn/cli.py` | MOD (`p_app` `--target`) | unchanged | unchanged | unchanged | unchanged | **MOD (additive `p_aud`)** |
| `survey/learn/__init__.py` | unchanged | unchanged | unchanged | unchanged | unchanged | **MOD (exports)** |
| `survey/learn/{apply,aggregator,suggester,llm_client,review,status}.py` | various | unchanged | unchanged | unchanged | unchanged | **unchanged** |
| `survey/qualification_rules.py` | unchanged | MOD | unchanged | unchanged | unchanged | unchanged |
| `survey/captcha/*`, `graph/*` | unchanged | unchanged | unchanged | MOD | unchanged | unchanged |
| `evals/*` | unchanged | unchanged | NEW | unchanged | unchanged | unchanged |
| `.github/workflows/*` | NEW | unchanged | NEW | unchanged | unchanged | unchanged |
| `scripts/*` | unchanged | unchanged | unchanged | unchanged | NEW | unchanged |
| `tests/test_learn_audit.py` | unchanged | unchanged | unchanged | unchanged | unchanged | **NEW** |

`cli.py`-Konflikt-Analyse: PR #100 patcht `p_app` Block, SR-104 hat
`p_sts` als neuen Block hinzugefuegt, SR-109 fuegt `p_aud` Block hinzu.
Alle drei sind verschiedene Hunks. PR #100 ist gemerged → main hat
geupdateten `p_app`. SR-109 fuegt am Ende `p_aud` an. Auto-merge trivial.

Konfliktrisiko: 0.

---

## Estimated complexity

**S** — vergleichbar mit #104 (status). Pure functions + thin CLI
wrapper + 18+ Tests. One-PR-cycle.

---

## References

- #104 (closed `573070e`) — Schwester-Track, inbox-side, dasselbe pattern
- #56 (closed `424e928`) — fuehrt `source`/`model`/`prompt_hash` ein
- `survey/learn/apply.py:461-475` — `_audit_log_path`
- `survey/learn/apply.py:595-650` — audit-record schemas
