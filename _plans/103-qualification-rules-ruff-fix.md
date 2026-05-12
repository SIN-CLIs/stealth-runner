# SR-103: Fix pre-existing ruff W293/F841 in qualification_rules.py

**Status:** OPEN
**Owner:** Kollege-Agent
**Spawned by:** v0-CEO-Session am 2026-05-12 nach #100-Status-Bericht
**Parallel-safe with:** PR #100 (smoke-workflow), Issue #101 (eval-harness), v0-CEO-Sessions naechste `learn/`-Arbeit

---

## Zweck

Beim CI-Lauf von PR #100 schmierte `test (3.13)` mit `ruff check survey-cli/survey --select E,W,F` ab. Der Kollege-Agent hat verifiziert: das Problem ist **pre-existing auf `main`** und betrifft NICHT seinen PR — `survey-cli/survey/qualification_rules.py` hat 27 Violations, alle aus einem frueheren Commit.

**Impact:** Solange diese Datei rot ist, **bricht CI auf jeder PR**. PR #100 ist davon betroffen, jeder zukuenftige PR auch.

Das ist daher **THE blocker** fuer den gesamten Merge-Train. Beheben hat hoechste ROI/Aufwand-Ratio aller offenen Tracks.

---

## Diagnose (verifiziert via `ruff check ... --statistics`)

```
26  W293  [-] blank-line-with-whitespace   (9 auto-fix safe, 17 in docstrings)
 1  F841  [ ] unused-variable              (line 363: tool_tasks)
```

**W293 sample (line 54):**
```python
r"arbeitslos",
r"nicht\s*berufstätig",
    ← trailing whitespace on blank line
# Englisch
r"prefer\s*not\s*(to\s*)?(say|answer|disclose)",
```

**F841 (line 350-368):**
```python
def get_nvidia_model_for_task(task: str) -> str:
    vision_tasks = ["screenshot_analysis", "captcha", "image_selection", "drag_drop"]
    tool_tasks = ["answer_selection", "form_filling", "navigation"]  # ← UNUSED

    if task in vision_tasks:
        return NVIDIA_MODELS["vision"]
    else:
        return NVIDIA_MODELS["tool_use"]   # falls through, ignoriert tool_tasks
```

Der `tool_tasks`-Identifier war offenbar als positive Liste fuer den `tool_use`-Pfad gedacht, wurde aber nie in einer `elif`-Bedingung verwendet. Der `else`-Branch faengt heute ALLES Non-Vision (auch unbekannte Task-Strings) — das **Verhalten** soll diese PR nicht aendern.

---

## Scope (exakt 1 modifizierte Datei)

| Datei | Status | Aenderung |
|---|---|---|
| `survey-cli/survey/qualification_rules.py` | MOD | 26x W293 fix + 1x F841 fix |

**26x W293 fix:** entferne trailing-whitespace auf blank lines (mechanisch via `ruff check --fix --unsafe-fixes survey/qualification_rules.py` — `--unsafe-fixes` ist hier safe, weil's nur whitespace in docstring-blank-lines betrifft, kein behavior).

**1x F841 fix:** loesche Zeile 363 (`tool_tasks = [...]`). Behavior bleibt identisch (else-branch unveraendert).

---

## Out-of-Scope (LOCK — bitte nicht aufweichen)

- **KEINE Aenderung an `.github/workflows/ci.yml`** (insbesondere NICHT `--select E,W,F` aufweichen, NICHT Ignores erweitern — AGENTS.md §13.8.1 verlangt ein Debt-Tracker-Issue bevor sich der Gate-Vertrag aendert)
- **KEINE Refactorings am Verhalten** von `get_nvidia_model_for_task`. Der `tool_tasks`-Identifier wird **nur geloescht**, NICHT in eine `elif`-Bedingung verdrahtet. Wenn der Author die Intent wiederherstellen will, ist das ein separates Issue ("SR-???: Wire tool_tasks as explicit elif branch")
- **KEINE Aenderung an `survey/learn/*.py`** (v0-CEO-Session-Territorium)
- **KEINE Aenderung an `evals/*`** (#101-Territorium)
- **KEINE neuen Tests** (es gibt 200 bestehende, die das Verhalten von `qualification_rules` ueber `survey.learn.*`-Pfade indirekt abdecken — die bleiben gruen, das reicht als Regression-Guard)
- **KEINE anderen ruff-Fixes** in anderen Dateien (selbst wenn ruff sie meldet — scope-creep blockt diesen Fast-Path)

---

## Acceptance Criteria

- [ ] `ruff check survey-cli/survey/qualification_rules.py --select E,W,F` → "All checks passed!"
- [ ] `ruff check survey-cli/survey --select E,W,F` → "All checks passed!" (gesamtes survey/ tree gruen)
- [ ] `pytest survey-cli/tests -q` → gruen, identische Test-Anzahl wie vor diesem Fix (kein versehentlicher Test-Skip)
- [ ] Behavior von `get_nvidia_model_for_task` unveraendert: gleiche return-values fuer alle vision_tasks und alle else-cases (Caller-Tests bleiben gruen)
- [ ] Commit-Message referenziert `Closes #103`
- [ ] `_plans/103-qualification-rules-ruff-fix.md` geloescht im selben commit (rule A4)

---

## Test Plan

1. **Local ruff:** `cd survey-cli && ruff check survey/qualification_rules.py --select E,W,F` → 0 errors
2. **Local pytest:** `cd survey-cli && pytest tests -q` → genau die Anzahl tests gruen die vor dem Fix gruen waren (Erwartung: 200)
3. **CI on PR:** test (3.13) und test (3.12) muessen gruen sein. **Das ist das primaere success-signal** dieser PR — die Matrix war wegen genau dieser Datei rot.
4. **Behavioral spot-check:** `python -c "from survey.qualification_rules import get_nvidia_model_for_task; assert get_nvidia_model_for_task('screenshot_analysis') == 'meta/llama-3.2-90b-vision-instruct' or '...vision...' in get_nvidia_model_for_task('screenshot_analysis')"` — nur als Sanity, NICHT als formaler Test.

---

## File-Boundary-Vertrag (parallel-safety matrix)

| Surface | PR #100 | Issue #101 | **SR-103** | v0-CEO future learn/ |
|---|---|---|---|---|
| `survey/qualification_rules.py` | unchanged | unchanged | **MOD (single file)** | unchanged |
| `survey/learn/*.py` | unchanged | unchanged | **unchanged** | MOD |
| `evals/*` | unchanged | NEW | **unchanged** | unchanged |
| `.github/workflows/*` | NEW (smoke) | NEW (eval) | **unchanged** | unchanged |
| `tests/*` | NEW (fixtures) | NEW (test_eval_*) | **unchanged** | NEW (test_review*) |

Konfliktrisiko = 0. Single-file edit, mechanischer auto-fix.

---

## Estimated complexity

**XS** — 1 file, 27 violations, davon 26 mechanisch via `ruff --fix --unsafe-fixes`, 1 manuelle Zeilen-Loeschung. One-PR-cycle, dauert weniger als #99 oder #101.

---

## Why this is the highest-priority next track

| Track | Status | Was wird unblockt? |
|---|---|---|
| **#103 (this)** | OPEN | **ALLE PRs** — CI ist auf `main` rot wegen einer einzigen Datei |
| #100 | open PR | wartet auf Merge — Smoke-Job ist gruen, nur test-matrix rot wegen #103 |
| #101 | OPEN | kann starten, aber wird auch in test-matrix rot ankommen ohne #103 |
| #43 | OPEN low-prio | unabhaengig, kann warten |

**ROI: 1 file edit unblockt 3 in-flight tracks.** Daher dieser jump-the-queue.

---

## References

- Pre-#100 Status-Kommentar des Kollege-Agent zu PR #100 (test-(3.13)-Failure-Diagnose)
- `.github/workflows/ci.yml` §74-75 — der harte ruff-gate
- AGENTS.md §13.8.1 SR-62 — Vertrag dass `--select E,W,F` NICHT aufgeweicht wird
- Kommentar in `ci.yml`:69-73 — explicit warning gegen widening ignore-list ohne debt-issue
