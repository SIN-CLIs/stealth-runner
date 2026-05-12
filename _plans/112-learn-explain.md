# SR-112: `survey learn explain` — per-keyword inverse-lookup

**Status:** OPEN
**Owner:** v0-CEO-Session (Agent 1)
**Spawned by:** v0-CEO-Session am 2026-05-12 nach Abschluss SR-109
**Parallel-safe with:** PR #100, #105, #110, #111, #101, #106, #113

---

## Zweck

Die learn-Pipeline hat drei aggregierende read-only Views:

  - `status`  (#104) — Inbox-side: was wartet noch?
  - `audit`   (#109, PR #111) — Apply-side: was wurde global angewandt
                                / verworfen?
  - **`explain` (this issue)** — Apply-side **per-keyword**: "Warum ist
    `textbox:telefonnummer` in `FIELD_PATTERNS`? Wann + von welcher Source
    + mit welcher Confidence?"

Use-cases:

  1. Reviewer findet einen verdaechtigen FIELD_PATTERNS-Eintrag und will
     dessen Provenance verifizieren — bevor er rueckwaerts editiert
  2. LLM hat einen Fehler gemacht (#56-source=llm Entscheidung), Operator
     will den genauen `prompt_hash` + `model` finden um den Fall
     zu reproduzieren
  3. Audit-trail-Anfrage: "Wer/was hat in den letzten 30 Tagen `phone` so
     oft applied?" → granular pro-keyword statt aggregiert

---

## Scope (1 neue Datei + 2 MOD + 1 Test-Datei)

| Datei | Status | Aenderung |
|---|---|---|
| `survey-cli/survey/learn/explain.py` | NEU | Pure functions: `find_explanations`, `Explanation`, formatters |
| `survey-cli/survey/learn/cli.py` | MOD | Additiver `p_xpl` subparser block am Ende |
| `survey-cli/survey/learn/__init__.py` | MOD | Exports |
| `survey-cli/tests/test_learn_explain.py` | NEU | 16+ Tests |

### CLI

```
survey learn explain <query>
  [--logs DIR | --input PATH]
  [--by {label,family,keyword}]    # default: auto (sniff via ':')
  [--limit N]                       # default: 5 (newest first)
  [--include-rejects]               # default: false (applied-only)
  [--json]
```

### Query-Syntax

  - `phone` → matched gegen `family` field
  - `telefonnummer` → matched gegen `keyword` field (applied) UND
                       `entry.normalized_label` field (rejects)
  - `textbox:telefonnummer` → matched gegen tuple (role, label)
  - `--by family|keyword|label` → forces specific match mode

Match ist **case-insensitive substring** (NOT exact) — Operator typt schnell.

### Output (human, default)

```
[learn] explain query: "telefonnummer"  (matched as keyword)

Found 3 audit-record(s) (newest first), limited to top 5:

[1] 2026-05-10T12:00:00Z  applied
    family:       phone
    keyword:      telefonnummer
    role (from entry):  textbox
    source:       llm
    confidence:   0.87
    model:        openai/gpt-5-mini
    prompt_hash:  abc12345...
    log-file:     learn-applied-20260510T120000Z.jsonl

[2] 2026-05-05T08:30:00Z  applied
    family:       phone
    keyword:      telefonnummer-mobil
    source:       substring
    confidence:   1.00
    model:        (n/a)
    log-file:     learn-applied-20260505T083000Z.jsonl

[3] 2026-05-02T14:15:00Z  applied
    family:       phone
    keyword:      telefon
    source:       substring
    confidence:   1.00
    model:        (n/a)
    log-file:     learn-applied-20260502T141500Z.jsonl

(0 reject records matched; use --include-rejects to include them)
```

### Output (`--json`)

```json
{
  "query": "telefonnummer",
  "match_mode": "keyword",
  "limit": 5,
  "include_rejects": false,
  "total_matches": 3,
  "explanations": [
    {
      "decision": "applied",
      "family": "phone",
      "keyword": "telefonnummer",
      "role": "textbox",
      "source": "llm",
      "confidence": 0.87,
      "model": "openai/gpt-5-mini",
      "prompt_hash": "abc12345...",
      "timestamp": "2026-05-10T12:00:00Z",
      "log_file": "learn-applied-20260510T120000Z.jsonl"
    },
    ...
  ]
}
```

---

## Architektur-Entscheidungen

**A) Pure functions in `explain.py`** — identisches Pattern wie
`status.py` (#104) und `audit.py` (#109). `find_explanations(records,
query, mode, limit, include_rejects) -> List[Explanation]` ist
deterministisch und ohne I/O.

**B) Reuse audit.py normalizers wo moeglich.** `_normalize_source`,
`_normalize_family`, `_extract_timestamp` aus `audit.py` werden
importiert und re-used. Keine Duplikation der defensive fallback-Kette.

**C) Match-mode auto-detection.** Wenn `query` ein `:` enthaelt, fallback
auf `label` mode (role:label tuple match). Wenn `--by` explizit gegeben,
ueberschreibt das.

**D) Strict read-only.** Test `test_explain_never_opens_files_for_writing`
mit mock-`builtins.open`.

**E) Sortierung: newest first.** Records werden nach `timestamp` desc
sortiert. Records ohne timestamp sortieren ans Ende (defensiv).

**F) Reject-records sind opt-in.** Default: applied-only (Operator will
in 80% der Faelle wissen "was hat es ins Pattern geschafft"). `--include-
rejects` schaltet rejects dazu — nuetzlich fuer die "warum NICHT applied"-
Diagnose.

---

## Out-of-Scope (LOCK)

- KEINE Aenderung an `aggregator.py`, `apply.py`, `suggester.py`,
  `llm_client.py`, `review.py`, `status.py`, `audit.py`
- KEINE Aenderung an `qualification_rules.py` (#103/#105)
- KEINE Aenderung an `survey/captcha/*`, `survey/graph/*` (#106)
- KEINE Aenderung an `evals/*` (#101)
- KEINE Aenderung an `.github/workflows/*`
- KEINE Aenderung an `scripts/*` (#108, #113)
- Explain-CLI darf NIE schreiben (kein `--unapply`, `--rollback`, etc.)
- KEINE neuen runtime-Dependencies
- Subparser bleibt singulaer `p_xpl`

---

## Acceptance Criteria

- [ ] `explain.py` pure functions ohne I/O (testbar isoliert)
- [ ] 16+ Tests in `test_learn_explain.py`, alle gruen
- [ ] `survey learn explain --help` zeigt 6 neuen Flags
- [ ] Multi-file scan default `survey-cli/logs/learn-applied-*.jsonl`
- [ ] `--input PATH` override
- [ ] Auto-detect: `:` im query → `label` mode
- [ ] `--by family|keyword|label` overridet auto-detect
- [ ] Case-insensitive substring match
- [ ] `--limit N` limitiert Output
- [ ] Default: applied-only; `--include-rejects` schaltet rejects dazu
- [ ] Newest-first Sortierung (records ohne timestamp ans Ende)
- [ ] `--json` parseable
- [ ] Read-only audit (mock-open Test)
- [ ] Bestehende Tests bleiben gruen
- [ ] `survey learn --help` listet `explain`
- [ ] Commit-Message referenziert `Closes #112`
- [ ] `_plans/112-learn-explain.md` geloescht (rule A4)

---

## Test Plan (16+ Tests)

**TestFindExplanations:**
- Empty input → empty list
- Match by keyword (case-insensitive)
- Match by family (exact)
- Match by label tuple (role:label, case-insensitive)
- Auto-detect: query mit ':' → label mode
- Auto-detect: query ohne ':' → keyword-then-family
- Newest-first sorting
- Records ohne timestamp sortieren ans Ende
- `limit` truncates after sort
- `include_rejects=False` excludes rejects
- `include_rejects=True` includes rejects

**TestCmdExplain (CLI integration):**
- Multi-file scan
- `--input` override
- `--json` parseable
- `--by keyword` forces mode
- `--limit` works
- Empty result emits friendly message

**TestReadOnlyExplain:**
- mock-builtins.open garantiert: explain oeffnet KEINE Datei mit w/a/x/+

---

## File-Boundary-Matrix

| Surface | PR #100 | #105 | #101 | #106 | #110 | #111 | **#112** | #113 |
|---|---|---|---|---|---|---|---|---|
| `survey/learn/explain.py` | unchanged | unchanged | unchanged | unchanged | unchanged | unchanged | **NEW** | unchanged |
| `survey/learn/cli.py` | MOD `p_app` | unchanged | unchanged | unchanged | unchanged | MOD additive `p_aud` | **MOD additive `p_xpl`** | unchanged |
| `survey/learn/__init__.py` | unchanged | unchanged | unchanged | unchanged | unchanged | MOD | **MOD** | unchanged |
| `survey/learn/{apply,aggregator,suggester,llm_client,review,status,audit}.py` | various | unchanged | unchanged | unchanged | unchanged | NEW audit | **unchanged** | unchanged |
| `survey/qualification_rules.py` | unchanged | MOD | unchanged | unchanged | unchanged | unchanged | unchanged | unchanged |
| `survey/captcha/*`, `graph/*` | unchanged | unchanged | unchanged | MOD | unchanged | unchanged | unchanged | unchanged |
| `evals/*` | unchanged | unchanged | NEW | unchanged | unchanged | unchanged | unchanged | unchanged |
| `.github/workflows/*` | NEW | unchanged | NEW | unchanged | unchanged | unchanged | unchanged | unchanged |
| `scripts/*` | unchanged | unchanged | unchanged | unchanged | NEW (#108) | unchanged | unchanged | **NEW (#113)** |
| `tests/test_learn_explain.py` | unchanged | unchanged | unchanged | unchanged | unchanged | unchanged | **NEW** | unchanged |

`cli.py`-Hunks: PR #100 `p_app`, #104 (merged) `p_sts`, PR #111 `p_aud` ans Ende, #112 `p_xpl` nach `p_aud`. Alle additive verschiedene Hunks. Konfliktrisiko = 0.

---

## Estimated complexity

**S** — vergleichbar mit SR-109. Pure functions + thin CLI wrapper + 16+
Tests. One-PR-cycle.

---

## References

- #104 (closed) — `status.py` pattern reference
- #109 / PR #111 — `audit.py` pattern reference, normalizers re-used
- `apply.py:595-655` — audit-record schemas
