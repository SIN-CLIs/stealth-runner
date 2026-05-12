# SR-102: Source-aware batch-review fuer pattern-suggestions inbox

**Status:** OPEN
**Owner:** v0-CEO-Session
**Parallel-safe with:** Kollege-Agent (#100 PR fuer #99, #101 eval-harness)

## Zweck

`cmd_review` in `cli.py` existiert bereits (interaktiver a/r/s/q flow), hat aber konkrete Limitationen die durch #56 (Phase-2-LLM) sichtbar wurden:

1. **Nur interaktiv** — stdin-prompts machen es nicht CI-/script-tauglich
2. **Source-blind** — zeigt nicht ob suggestion von Heuristik oder LLM kam (`source`, `model`, `prompt_hash` aus #56 werden nicht angezeigt)
3. **Keine Batch-Modi** — high-conf substring auto-accepten und low-conf LLM auto-rejecten ist ueblicher Workflow, aber unmoeglich
4. **Nicht idempotent** — re-run dupliziert `pattern-suggestions-accepted.jsonl` per append, status im input-file wird nicht geflippt
5. **Null Tests** — `cmd_review` ist komplett ungetestet (verifiziert: `grep test_review tests/` = leer)

## Scope

| Datei | Status | Zweck |
|---|---|---|
| `survey-cli/survey/learn/review.py` | NEU | Pure-Function-Logik: filter, gate, plan_actions |
| `survey-cli/survey/learn/cli.py` | MOD | `cmd_review` ruft pure funcs auf + neue Flags |
| `survey-cli/survey/learn/__init__.py` | MOD | Exports |
| `survey-cli/tests/test_learn_review.py` | NEU | 15+ Tests |

## Neue CLI-Flags fuer `survey learn review`

- `--auto-accept-substring-above CONF` — auto-accept fuer `source=substring` mit `confidence >= CONF` (default off)
- `--auto-reject-llm-below CONF` — auto-reject fuer `source=llm` mit `confidence < CONF` (default off)
- `--filter-source {substring,llm,all}` — nur diese source-records anzeigen/verarbeiten (default `all`)
- `--non-interactive` — kein stdin; nur auto-rules anwenden, rest = skip
- (bestehend) `--dry-run` — bleibt unveraendert

## Verhalten

1. Lies input JSONL
2. Fuer jeden record: `plan_action(entry, rules) -> "accept" | "reject" | "ask" | "filtered"`
3. `filtered`: ueberspring (kein output, kein status-flip)
4. `accept`/`reject`: schreibe in entsprechende output-JSONL, **flip status im input-file zu "accepted"/"rejected"**
5. `ask`: nur wenn `--non-interactive` NICHT gesetzt — stdin-prompt
6. Re-run faehrt nur ueber records mit `status=="open"` (idempotenz!)
7. Output-JSONLs werden mit `open(..., "a")` geschrieben (bestehendes Verhalten), aber per-run dedupliziert anhand `(role, normalized_label)`

## File-Boundary mit #100 (parallel)

| Funktion | #100 (PR offen) | SR-102 (dieses) |
|---|---|---|
| `cmd_aggregate` | unchanged | unchanged |
| `cmd_review` | unchanged | **MOD** (this surface) |
| `cmd_apply` | MOD (`target_path=args.target`) | unchanged |
| `p_agg` parser | unchanged | unchanged |
| `p_rev` parser | unchanged | **MOD** (new args) |
| `p_app` parser | MOD (`--target`) | unchanged |

Drei verschiedene Hunks in cli.py, git-auto-merge mechanisch trivial.

## Acceptance Criteria

- [ ] `review.py` enthaelt pure functions ohne I/O (testbar isoliert)
- [ ] 15+ Tests in `test_learn_review.py`, alle gruen
- [ ] `--auto-accept-substring-above 0.9` akzeptiert nur `source=substring AND conf>=0.9`
- [ ] `--auto-reject-llm-below 0.85` rejected nur `source=llm AND conf<0.85`
- [ ] `--filter-source llm` zeigt/verarbeitet nur LLM-records
- [ ] `--non-interactive` ohne auto-rules → 0 accepts, 0 rejects, alle skip
- [ ] Re-run idempotent: zweiter Aufruf mit gleichem input macht 0 changes
- [ ] Display zeigt `source`, `model` (truncated), `prompt_hash` fuer LLM-records
- [ ] Bestehender interaktiver Flow funktioniert weiter (regression-frei)
- [ ] Bestehende test_learn*.py Suite gruen (kein regression)
- [ ] `_plans/102-learn-review-batch.md` Plan-File geloescht im selben commit

