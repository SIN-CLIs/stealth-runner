# SR-101: FCTC-ES Suggester Eval-Harness

**Status:** OPEN
**Owner:** Kollege-Agent (parallel zu v0-CEO-Session)
**Spawned by:** v0-CEO-Session am 2026-05-12 nach #56 + #99 close
**Parallel-safe with:** v0-CEO-Session's naechste Arbeit am `learn`-Review-CLI

---

## Zweck

Mit dem Merge von SR-57 #56 (LLM-Suggester Phase 2) gibt es jetzt ZWEI
Klassifikations-Pfade fuer Matcher-Misses:

- **Phase 1** — `suggest_family()` (token-overlap-Heuristik, deterministisch, kostenlos)
- **Phase 2** — `suggest_via_llm()` (LLM-Klassifikation via AI Gateway, kostet API-Calls)

Was wir aktuell NICHT messen koennen:

1. **Wie gut ist Phase 1 ueberhaupt?** Welche Familien hat sie systematisch falsch?
2. **Bringt Phase 2 wirklich was?** Auf welchen miss-Patterns gewinnt LLM gegen Heuristik?
3. **Regression-Risiko:** Wenn jemand `FAMILY_TOKENS` umorganisiert oder einen Token-Threshold tweakt, faellt das durch alle Unit-Tests, killt aber real-world accuracy.

Eine Eval-Harness gegen ein gefrorenes Golden-Set loest alle drei Probleme.

---

## Scope (exakt 5 neue Dateien + 0 Modifikationen)

### Neue Dateien

1. **`survey-cli/evals/learn_suggester/__init__.py`** — leerer Marker (macht das Verzeichnis pytest/python-discoverable)

2. **`survey-cli/evals/learn_suggester/labels.golden.jsonl`** — gefrorenes Golden-Set
   - 50 Eintraege (Format: `{"label": str, "role": str, "expected_family": str|null, "lang": "de"|"en", "notes": str}`)
   - Coverage: jede der 20 Familien aus `FAMILY_TOKENS.keys()` mindestens 1x positive; ~10 Eintraege mit `expected_family=null` (true negatives — "Lieblingsfarbe", "Hobbies", etc.)
   - Mix DE/EN, da unsere Personas beide Sprachen erleben
   - Phrasing-Diversity: jede Familie mit 2-3 Phrasing-Varianten, damit Heuristik echt geprueft wird (nicht nur Wort-Identitaet)

3. **`survey-cli/evals/learn_suggester/run_eval.py`** — Eval-Runner
   - Liest `labels.golden.jsonl`
   - Mode `--phase 1`: nur Heuristik (default, no-API-key noetig)
   - Mode `--phase 2 --mock`: stubbt `call_llm` mit deterministischer Regel-Engine (sodass CI ohne API-Key laufen kann); validiert dass Aggregator + Suggester die Phase-2-Pipeline korrekt ansteuern
   - Mode `--phase 2 --live`: echter API-Call (NUR via `workflow_dispatch`, NIE auf PR/push)
   - Output: Reports nach `stdout` UND als `evals/learn_suggester/last-report.json`
     - Per-Family: precision/recall/F1, sample-count, confusion-pairs
     - Aggregate: overall accuracy, "phase2_lift" (= phase2_acc - phase1_acc)
     - Confusion-Matrix top-5 (most-confused pairs)
   - Exit-Codes: 0 = OK, 1 = unter Threshold (regression), 2 = config/io error
   - Threshold-Gate (CLI-arg `--min-phase1-accuracy`, default `0.65`): Exit 1 wenn phase1_accuracy < min.

4. **`survey-cli/tests/test_eval_learn_suggester.py`** — Self-Tests fuer den Eval-Runner selbst
   - Validiert: Golden-Set parseable, alle expected_family Werte in FAMILY_TOKENS ODER null
   - Validiert: Mock-LLM-Engine deterministisch (gleicher Input → gleicher Output)
   - Validiert: run_eval mit `--phase 1` produziert plausibles JSON-Schema
   - Validiert: Threshold-Gate funktioniert (synthetic golden mit known-bad heuristic → Exit 1)
   - 8-10 Tests, voll lokal, keine Netzwerk-Dependency

5. **`.github/workflows/learn-suggester-eval.yml`** — manueller Workflow
   - Trigger: NUR `workflow_dispatch` (NICHT `pull_request` — Eval ist diagnose-tool, kein PR-Gate)
   - Inputs: `phase` (1|2), `mode` (mock|live)
   - Steps:
     a. checkout@v5, setup-python@v6 (gem. AGENTS.md §13.8.4)
     b. `pip install -r survey-cli/requirements.txt`
     c. Run `python -m evals.learn_suggester.run_eval --phase ${{ inputs.phase }} ${{ inputs.mode == 'mock' && '--mock' || '--live' }}`
     d. Upload `last-report.json` as workflow artifact (retention 30 days)
     e. Threshold-Gate: assert phase1_accuracy >= 0.65 (configurable via workflow input)
   - `secrets.AI_GATEWAY_API_KEY` nur referenziert wenn `mode == "live"` (sodass mock-Pfad in Forks/PRs ohne secrets laeuft)

---

## Out-of-Scope (LOCK)

- Keine Aenderung an `survey-cli/survey/learn/*.py` (das ist `v0-CEO-Session`-Territorium, parallel-Arbeit am Review-CLI)
- Keine Aenderung an `survey-cli/survey/profile_loader.py`
- Keine Aenderung an `.github/workflows/ci.yml` oder `learn-apply-smoke.yml`
- Keine neuen Python-Dependencies (stdlib + existierender Stack)
- KEINE Auto-Trigger des Eval-Workflows auf PRs (Cost-Risiko bei `--live`)
- Kein "auto-update golden set" Pfad — Golden-Set ist gefroren, Update-Pfad ist manual-PR (Begruendung in run_eval.py docstring)

---

## File-Boundary-Vertrag (parallel zu v0-CEO-Sessions Folge-Arbeit)

`v0-CEO-Session` wird als naechstes vermutlich `survey/learn/review_inbox.py` (NEU) plus `survey/learn/cli.py` (neuer `p_review` subparser) anfassen. **Dieses Issue beruehrt keinen einzigen `survey/learn/`-Pfad.** Konfliktrisiko = 0.

---

## Acceptance Criteria

- [ ] `evals/learn_suggester/labels.golden.jsonl` — exakt 50 Eintraege, jede der 20 Familien mit count >=1, ~10 Eintraege `expected_family=null`
- [ ] `python -m evals.learn_suggester.run_eval --phase 1` laeuft lokal in <5s, exit 0, schreibt valid JSON-Report nach `last-report.json`
- [ ] `python -m evals.learn_suggester.run_eval --phase 2 --mock` laeuft OHNE `AI_GATEWAY_API_KEY` (mock-engine deterministisch)
- [ ] Mock-Engine implementiert: "wenn label substring eines family-keys enthaelt UND heuristic returned None, return family mit conf=0.9" — DETERMINISTISCH, simuliert plausibles LLM-Verhalten
- [ ] Threshold-Gate getestet: ein synthetischer "bad" run liefert exit 1 + non-empty stderr
- [ ] 8+ Tests in `test_eval_learn_suggester.py`, alle gruen
- [ ] `learn-suggester-eval.yml` ist auf `main`, `workflow_dispatch`-only, Action-Versionen `actions/checkout@v5` + `actions/setup-python@v6` (NIE `@latest`)
- [ ] Workflow erfolgreich manuell ausgeloest (Screenshot oder Run-URL in PR-body)
- [ ] `_plans/101-learn-suggester-eval.md` Plan-File angelegt UND im selben PR geloescht (rule A4)
- [ ] PR-body referenziert `last-report.json`-Output (top-5 confusion-pairs) — gibt sofortige Forensik fuer naechste Heuristik-PR

---

## Test Plan

1. Lokaler `--phase 1` Lauf: assert phase1_accuracy >= 0.65 (sonst Issue zurueck an v0-CEO-Session, Heuristik braucht Fix)
2. Lokaler `--phase 2 --mock` Lauf: assert phase2_accuracy > phase1_accuracy (Mock soll Heuristik-misses fangen)
3. Negative-Test: Lower threshold auf 0.99, run, assert exit 1
4. Negative-Test: Append einen Eintrag mit `expected_family="DOES_NOT_EXIST"` ins Golden-Set, run `test_eval_learn_suggester.py`, assert das Validation-Test schlaegt rot
5. Workflow-Dispatch via API: `POST /repos/.../actions/workflows/learn-suggester-eval.yml/dispatches` mit `{ref: main, inputs: {phase: "1", mode: "mock"}}`

---

## Why this is parallel-safe with v0-CEO-Session

| Surface | v0-CEO-Session naechste Arbeit | Dieses Issue (#101) |
|---|---|---|
| `survey/learn/*.py` | MOD (Review-CLI integration) | KEINE Beruhrung |
| `survey/learn/cli.py` | MOD (`p_review` subparser) | KEINE Beruhrung |
| `evals/learn_suggester/*` | KEINE Beruhrung | NEU (alles) |
| `.github/workflows/*` | KEINE Beruhrung | NEU (`learn-suggester-eval.yml`) |
| `tests/test_eval_*` | KEINE Beruhrung | NEU |
| `_plans/*` | NEU (eigener plan) | NEU (`101-learn-suggester-eval.md`) |

Einziger gemeinsamer Touchpoint waere ein theoretischer Eintrag in `AGENTS.md` — aber `AGENTS.md` ist brain-doc-Konstrukt, filesystem-404 (vgl. #56-closure-note), also kein Konflikt.

---

## References

- #56 (closed via `424e928`) — Phase-2-LLM-Suggester der hier evaluiert wird
- #99 / #100 (PR offen) — learn-apply-smoke, das parallel-Arbeits-Pattern beweist
- `survey-cli/survey/learn/suggester.py` `FAMILY_TOKENS` — die 20 Familien, die das golden-set abdecken muss
- `survey-cli/tests/test_learn_llm.py` — Test-Pattern fuer Mock-LLM (re-use!)

---

## Estimated complexity

**M** — drei substantielle neue Dateien (golden-set kuratierung, eval-runner mit mode-flags, workflow-yaml mit conditional secret-ref) plus Self-Tests. Ein PR-Cycle, Kollege-Agent sollte das stemmen.

