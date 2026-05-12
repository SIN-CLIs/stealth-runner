# SR-108: `scripts/triage_stale_suggestions.py` — Inbox-Hygiene-Script

**Status:** OPEN
**Owner:** Kollege-Agent
**Spawned by:** v0-CEO-Session am 2026-05-12
**Parallel-safe with:** PR #100, PR #105, #101, #106, #109

---

## Zweck

Nach #56 (LLM-Phase-2-Suggester) und #102 (source-aware batch-review) hat
die `pattern-suggestions-*.jsonl`-Inbox einen Lifecycle: `open` → `accepted`/
`rejected`. Aktuell kann ein Operator via `survey learn status` (#104) die
**aktuelle Verteilung** sehen — aber niemand verfolgt **Alter**. Records die
seit Wochen offen sind sind ein Smell: entweder bewusst ignoriert, oder
vergessen.

Dieses Script ist die **automation-side** Komplement zu #104:

  - `status` ist read-only-Diagnose fuer einen Menschen am Terminal
  - `triage_stale_suggestions.py` ist read-only-Diagnose fuer eine
    Cron-/CI-Hygiene-Job (machine-readable + non-zero-exit-Mode)

---

## Scope (1 neue Datei + 1 Test-Datei)

| Datei | Status | Aenderung |
|---|---|---|
| `scripts/triage_stale_suggestions.py` | NEU | Standalone read-only script |
| `scripts/tests/test_triage_stale_suggestions.py` | NEU | 8+ Tests |

KEINE Aenderung an `survey/`, `.github/workflows/`, `tests/`,
`pyproject.toml`, `requirements.txt`.

### CLI

```
python scripts/triage_stale_suggestions.py
    [--logs DIR]              # default: survey-cli/logs
    [--age-days N]            # default: 14
    [--filter-source X]       # all/substring/llm, default: all
    [--exit-non-zero-if-stale] # CI-Mode: rc=1 wenn stale records gefunden
    [--json]                  # JSON statt human output
```

### Output (human, default)

```
[triage] scanning survey-cli/logs/pattern-suggestions-*.jsonl
[triage] threshold: 14 days, source filter: all

Stale open records (older than 14 days):
  age=22d  source=substring  family=phone           label="telefonnummer"  count=12
  age=18d  source=llm        family=household_size  label="haushaltsgrosse"  count=8
  age=15d  source=substring  family=<NEW>           label="lieblingsfarbe" count=3

Total stale: 3 of 28 open records (10.7%)
Oldest: 22 days
```

### Output (`--json`)

```json
{
  "threshold_days": 14,
  "files_scanned": 2,
  "total_open": 28,
  "stale_count": 3,
  "stale_percent": 10.7,
  "oldest_age_days": 22,
  "stale_records": [
    {"age_days": 22, "source": "substring", "family": "phone",
     "role": "textbox", "label": "telefonnummer", "count": 12,
     "first_seen": "2026-04-20T..."},
    ...
  ]
}
```

### `--exit-non-zero-if-stale`

Returns exit 1 if at least one stale record is found. Default mode (without
this flag) always exits 0 (read-only diagnostic). Use case: cron job that
sends an alert when the inbox accumulates stale items.

---

## Architektur-Entscheidungen

**A) Standalone script, kein survey-package-import.** Das Script darf
`from survey.learn import ...` NICHT verwenden. Reason: scripts/ ist
sys-admin/hygiene territory und soll auch ohne installiertes survey-package
laufen. JSONL-parsing ist trivial, kein Code-Re-use noetig.

**B) Konsistent mit #104 status normalisierung.** Records ohne `status`-Feld
zaehlen als `"open"`. Records ohne `source`-Feld zaehlen als `"substring"`.
Records ohne `first_seen` werden als `age=unknown` behandelt — sie zaehlen
NICHT als stale (defensiv: kein false-positive auf legacy-records).

**C) Multi-file scan default.** Wie #104. Skipt `*-accepted.jsonl` und
`*-rejected.jsonl` Output-files; nur die roh-inbox.

**D) Pure stdout/stderr.** Script schreibt KEINE Dateien. Exit-codes sind
das einzige machine-signal neben dem JSON-output.

---

## Out-of-Scope (LOCK)

- KEINE Aenderung an `survey/learn/*`
- KEINE Aenderung an `.github/workflows/*` — die future CI-Integration ist
  ein separates Issue (siehe "Future work" unten)
- KEINE Aenderung an `pyproject.toml` / `requirements.txt` (nur stdlib)
- KEINE neuen runtime-Dependencies
- KEINE auto-fixing / status-flipping — das Script ist READ-ONLY
- KEINE Modifikation von pattern-suggestions-*.jsonl files

---

## Acceptance Criteria

- [ ] `scripts/triage_stale_suggestions.py` ist standalone executable
      (Shebang + chmod 755 erwuenscht)
- [ ] CLI zeigt alle 5 Flags via `--help`
- [ ] Multi-file scan default scannt `survey-cli/logs/pattern-suggestions-*.jsonl`
- [ ] `--age-days N` filtert correctly nach `(now - first_seen) > N days`
- [ ] `--filter-source` filtert correctly (substring/llm/all)
- [ ] Records ohne `first_seen` werden NICHT als stale gezaehlt
- [ ] `--json` Output ist parseable via `json.loads`
- [ ] `--exit-non-zero-if-stale` exit 1 wenn stale-count > 0, else exit 0
- [ ] Default-Mode exit 0 (auch wenn stale records existieren) —
      read-only diagnostic
- [ ] 8+ Tests in `scripts/tests/test_triage_stale_suggestions.py`
- [ ] Tests verwenden `tempfile.mkdtemp` + Aufraeumen, kein hardcoded /tmp
- [ ] Bestehende 226+ tests im scope (learn + profile) bleiben gruen
- [ ] Script oeffnet KEINE Datei mit `"w"/"a"/"x"/"+"` (read-only audit
      via mock builtins.open, optional aber empfohlen)
- [ ] Commit-Message referenziert `Closes #108`
- [ ] `_plans/108-triage-stale-suggestions.md` geloescht im selben commit (rule A4)

---

## Test Plan

Mindestens 8 Tests:

1. **Empty input** — no JSONL files in logs dir → exit 0, stale_count=0
2. **No stale records** — all open records < age-days → exit 0
3. **Stale records found** — some open records > age-days → exit 0
   (without --exit-non-zero-if-stale)
4. **--exit-non-zero-if-stale** with stale → exit 1
5. **--exit-non-zero-if-stale** with NO stale → exit 0
6. **--filter-source llm** excludes substring stale records
7. **Records without first_seen** are NOT counted as stale
8. **JSON output** is parseable + has expected schema
9. **Closed records** (`status=accepted`/`rejected`) are NEVER counted as stale
   (only `status=open` counts)

---

## Future work (out-of-scope here)

- CI-Integration: Wochentliches `triage` workflow das das Script ausfuehrt und
  GitHub-Issue erstellt wenn stale_count > threshold. Eigenes Issue.
- Auto-archiving: stale records nach M monaten automatisch in
  `pattern-suggestions-archived.jsonl` verschieben. Eigenes Issue (write-Operation
  + separater state-flip wie #102).

---

## File-Boundary-Matrix

| Surface | PR #100 | PR #105 | #101 | #106 | **#108 (this)** | #109 |
|---|---|---|---|---|---|---|
| `survey/learn/*` | MOD apply.py + cli.py | unchanged | unchanged | unchanged | **unchanged** | MOD (additive) |
| `survey/qualification_rules.py` | unchanged | MOD | unchanged | unchanged | **unchanged** | unchanged |
| `survey/captcha/*`, `graph/*` | unchanged | unchanged | unchanged | MOD | **unchanged** | unchanged |
| `evals/*` | unchanged | unchanged | NEW | unchanged | **unchanged** | unchanged |
| `.github/workflows/*` | NEW | unchanged | NEW | unchanged | **unchanged** | unchanged |
| `tests/*` | NEW fixtures | unchanged | NEW | unchanged | **unchanged** | NEW (test_learn_audit) |
| `scripts/*` | unchanged | unchanged | unchanged | unchanged | **NEW (triage)** | unchanged |

Konfliktrisiko mit allem in-flight: **0**.

---

## Estimated complexity

**XS-S** — single-file script (~120 LOC) + tests (~150 LOC). Vergleichbar
mit `scripts/check_banned_patterns.py`. One-PR-cycle.
