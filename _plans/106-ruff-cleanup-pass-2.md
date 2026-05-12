> **MASTER ISSUE: #106** (created by Kollege-Agent at 2026-05-12T09:40Z, ~90s before my parallel attempt at #107). This plan-file supplements that issue with additional behavior-risk diagnosis for the 3 non-trivial cases (`graph/graph.py:177` F401, `graph/nodes.py:316` W605, `graph/nodes.py:340` F841). Both #106 and this plan-file agree on scope, AC, and out-of-scope LOCK. #107 was closed as duplicate.

---

# SR-106: Ruff cleanup pass 2 — clear remaining 75 violations in survey/ (7 files)

**Status:** OPEN
**Owner:** Kollege-Agent
**Spawned by:** v0-CEO-Session am 2026-05-12 nach scope-vs-AC-Catch in #103
**Depends-on:** #103 / PR #105 (sequencing only — kein file-conflict)
**Parallel-safe with:** PR #100 (smoke), #101 (evals), #104 closed

---

## Zweck

Nach AC-Korrektur von #103 (siehe Comment am 2026-05-12) ist klar: PR #105
fixt nur 27/102 violations. Die restlichen 75 violations verteilen sich
auf 7 weitere Dateien. Erst wenn diese auch gruen sind, ist der CI ruff-
gate `ruff check survey/ --select E,W,F` vollstaendig.

Dieser Track schließt die Luecke.

---

## Diagnose (verifiziert via `ruff check ... --statistics`)

| Datei | W293 | W605 | F401 | F841 | E401 | W291 | Total | Behavior-Risk? |
|---|---|---|---|---|---|---|---|---|
| `survey/captcha/drag_drop_solver.py` | 3 | — | — | — | 1 | — | 4 | **NEIN** |
| `survey/captcha_router.py` | 2 | — | — | — | — | — | 2 | **NEIN** |
| `survey/cdp_actuator.py` | 1 | — | — | 1 | — | 1 | 3 | **NEIN** |
| `survey/cua_fallback.py` | 40 | — | — | — | — | — | 40 | **NEIN** |
| `survey/graph/graph.py` | — | — | 1 | — | — | — | 1 | **JA** — availability-probe |
| `survey/graph/nodes.py` | 18 | 4 | 1 | 1 | — | — | 24 | **TEILWEISE** — siehe unten |
| `survey/graph/state.py` | 1 | — | — | — | — | — | 1 | **NEIN** |
| **TOTAL** | **65** | **4** | **2** | **2** | **1** | **1** | **75** | |

---

## Per-Violation-Plan

### Trivial mechanisch (66 violations, kein behavior-risk)

**W293 / W291 (66 violations)** — `ruff check --fix --unsafe-fixes` auf jede
betroffene Datei. `--unsafe-fixes` weil ein Teil in docstring-blank-lines
liegt. Zero behavior impact.

**E401 in `drag_drop_solver.py:28`:**
```python
# vorher
import json, asyncio, random, websocket
# nachher
import asyncio
import json
import random
import websocket
```
Mechanisch, `ruff --fix --unsafe-fixes` macht das automatisch.

### Mechanisch mit kleinem review-Aufwand (6 violations)

**F841 in `cdp_actuator.py:402`:**
```python
except CDPError as e:           # e nicht verwendet
    # Bei Error trotzdem kurz warten (fallback)
    time.sleep(0.30)
    elapsed_ms = int((time.time() - t0) * 1000)
    return False, float(elapsed_ms)
```
**Fix:** `except CDPError:` (variable droppen). Behavior identisch — `e`
wurde nirgends referenziert.

**F841 in `graph/nodes.py:340`:**
```python
except Exception as e:          # e nicht verwendet
    state.drag_drop_detected = False
    state.drag_drop_target = None
```
**Fix:** `except Exception:`. **Follow-up note:** der bare-except
verschluckt alle Fehler stumm. Das ist ein separates code-smell und
gehoert in ein eigenes Issue ("Add logging to silent except in
nodes.py:340"). NICHT Teil dieser PR.

**F401 in `graph/nodes.py:405`:**
```python
from ..captcha_router import CaptchaDetection, CaptchaResult
# CaptchaResult wird nicht verwendet, nur CaptchaDetection
```
**Fix:** Import auf `CaptchaDetection` reduzieren. Die Variable
`result` weiter unten kommt aus dem return-value von
`angular_drag_drop_solve()` und braucht keinen type-import.

**W605 (4x in `graph/nodes.py:316`):** Es handelt sich um eine **JavaScript-
regex innerhalb einer Python-string**, die via CDP eval ausgefuehrt wird:
```python
var numMatch = bodyText.match(/zahl\s*(\d+)|number\s*(\d+)/i);
```
Python sieht `\s` und `\d` als ungueltige escape-sequences, obwohl
sie fuer JS bestimmt sind.

**Fix-Optionen (in Reihenfolge der Empfehlung):**
1. **Empfohlen:** den enthaltenden Python-string raw machen
   (`r"""..."""` statt `"""..."""`). Ruff happy, JS unveraendert.
2. Alternative: backslashes verdoppeln (`\\s`, `\\d`). Hassbar zu
   lesen, vermeiden.

Erst die enthaltende string-literal identifizieren (vermutlich
`SCAN_JS_TEMPLATE` oder aehnlich), dann das string-prefix anpassen.
**KEIN inhaltlicher Eingriff am JS.**

### **Behavior-Risk** (1 violation, real review noetig)

**F401 in `graph/graph.py:177`:**
```python
try:
    from core import (
        bootstrap_core,         # F401 — imported but unused
        BudgetExceededError,
    )
    CORE_AVAILABLE = True
except ImportError as _core_err:
    CORE_AVAILABLE = False
```

Das ist eine **import-availability-probe**: `bootstrap_core` wird
nicht direkt verwendet, aber die import-Anwesenheit ist Teil der
`CORE_AVAILABLE`-Detection. Wenn `bootstrap_core` selbst nicht
installiert ist (aber andere `core`-Symbole schon), faellt der
import; `CORE_AVAILABLE = False`. Mit einfachem Loeschen geht
dieser Schutz verloren.

**Fix-Optionen:**

1. **Empfohlen:** `# noqa: F401` annotation mit comment-explainer:
   ```python
   from core import (
       bootstrap_core,  # noqa: F401  - kept for availability probe
       BudgetExceededError,
   )
   ```
   Zero behavior change, ruff happy, intent dokumentiert.

2. Alternative: refactor zu `importlib.util.find_spec("core")`
   (das ist auch ruffs Vorschlag). Aber **das ist ein verhalten-
   aendernder refactor** — `find_spec` checkt nur den Modul-namen,
   nicht ob `bootstrap_core` und `BudgetExceededError` einzeln
   importierbar sind. Aus-Scope fuer diese PR.

3. Alternative: explizit consumieren via `assert bootstrap_core is not
   None`. Funktioniert, aber Option 1 ist idiomatischer.

**Entscheidung: Option 1 (noqa-annotation) waehlen.** Dokumentiert
absicht, zero behavior change.

---

## Scope (exakt 7 modifizierte Dateien)

| Datei | Status | Aenderung |
|---|---|---|
| `survey-cli/survey/captcha/drag_drop_solver.py` | MOD | 3x W293 + 1x E401 auto-fix |
| `survey-cli/survey/captcha_router.py` | MOD | 2x W293 auto-fix |
| `survey-cli/survey/cdp_actuator.py` | MOD | 1x W293 + 1x W291 + 1x F841 (drop `as e`) |
| `survey-cli/survey/cua_fallback.py` | MOD | 40x W293 auto-fix |
| `survey-cli/survey/graph/graph.py` | MOD | 1x F401 → `# noqa: F401` annotation |
| `survey-cli/survey/graph/nodes.py` | MOD | 18x W293 + 4x W605 (raw-string) + 1x F401 (drop CaptchaResult) + 1x F841 (drop `as e`) |
| `survey-cli/survey/graph/state.py` | MOD | 1x W293 auto-fix |

---

## Out-of-Scope (LOCK)

- KEINE Aenderung an `.github/workflows/ci.yml`
- KEINE Aenderung an `survey/qualification_rules.py` (#103 territory — wird via PR #105 gefixt)
- KEINE Aenderung an `survey/learn/*` (v0-CEO-Session-Territorium)
- KEINE Aenderung an `evals/*` (#101 territory)
- KEINE Aenderung an `tests/*`
- KEINE neuen Tests (bestehende Tests + ruff-gate = Regression-Guard)
- KEINE refactorings ueber das per-violation-plan oben hinaus
- INSBESONDERE NICHT: `bootstrap_core` durch `find_spec` refactoring
- INSBESONDERE NICHT: silent-except in `nodes.py:340` loggen (separates Issue)

---

## Acceptance Criteria

- [ ] `ruff check survey-cli/survey/captcha/drag_drop_solver.py --select E,W,F` → All checks passed
- [ ] `ruff check survey-cli/survey/captcha_router.py --select E,W,F` → All checks passed
- [ ] `ruff check survey-cli/survey/cdp_actuator.py --select E,W,F` → All checks passed
- [ ] `ruff check survey-cli/survey/cua_fallback.py --select E,W,F` → All checks passed
- [ ] `ruff check survey-cli/survey/graph/graph.py --select E,W,F` → All checks passed
- [ ] `ruff check survey-cli/survey/graph/nodes.py --select E,W,F` → All checks passed
- [ ] `ruff check survey-cli/survey/graph/state.py --select E,W,F` → All checks passed
- [ ] **`ruff check survey-cli/survey --select E,W,F` → All checks passed** (das tree-weite AC, das in #103 falsch positioniert war — gehoert hier hin, NACH #105+#106-merge)
- [ ] `pytest survey-cli/tests -q` → gruen, identische Test-Anzahl wie pre-PR (Erwartung: 226+ tests in learn+profile scope; pre-existing `test_tool_*` collection-errors via fehlendem `websocket` modul sind nicht von dieser PR adressierbar)
- [ ] `from survey.graph.graph import CORE_AVAILABLE` funktioniert weiterhin (post-noqa-fix)
- [ ] `graph/nodes.py:316` JS-regex JSON-output unveraendert (`numMatch`-feld liefert dieselben matches wie vorher)
- [ ] Commit-Message referenziert `Closes #106`
- [ ] `_plans/106-ruff-cleanup-pass-2.md` geloescht im selben commit (rule A4)

---

## Test Plan

1. **Local ruff per file:** Loop alle 7 Dateien einzeln, jede muss
   `All checks passed!` liefern.
2. **Local ruff tree-weit:** `ruff check survey-cli/survey --select E,W,F`
   → gruen. Bonus check: `--select ALL` zeigt nur noch warnings, keine
   E/W/F errors mehr.
3. **Local pytest:** `cd survey-cli && pytest tests
   --ignore-glob='tests/test_tool_*' --ignore=tests/test_run_survey.py
   -q` → 226+ tests gruen (`test_tool_*` + `test_run_survey.py` haben
   pre-existing collection errors via fehlendem `websocket` modul, nicht
   reparable in #106).
4. **Behavior spot-check graph/graph.py:** `python -c "from survey.graph.graph
   import CORE_AVAILABLE; print(CORE_AVAILABLE)"` muss True/False liefern
   abhaengig davon ob `core` installiert ist (identisches Verhalten zu
   pre-noqa).
5. **Behavior spot-check graph/nodes.py:316:** Vor und nach raw-string-fix
   muss `json.loads(extracted_text)` dieselbe Struktur liefern fuer
   einen Test-bodyText mit `"Bitte legen Sie die Zahl 5"`. Falls noch
   keine Fixture vorhanden, ad-hoc-test:
   ```python
   import re
   pat = re.compile(r"zahl\s*(\d+)|number\s*(\d+)", re.I)
   assert pat.search("zahl 5").group(1) == "5"
   ```
   (Reine sanity, NICHT als formaler test commit.)
6. **CI on PR:** `test (3.12)` und `test (3.13)` muessen gruen sein.
   Erst gemeinsam mit PR #105 (= nach Merge von beiden) wird der
   ruff-gate komplett gruen.

---

## File-Boundary-Matrix

| Surface | #100 PR | #101 | #103 PR | #104 closed | **#106 (this)** |
|---|---|---|---|---|---|
| `survey/qualification_rules.py` | unchanged | unchanged | **MOD** | unchanged | unchanged |
| `survey/learn/*` | MOD (apply.py) | unchanged | unchanged | MOD (status/cli/__init__) | unchanged |
| `survey/captcha/*` | unchanged | unchanged | unchanged | unchanged | **MOD (drag_drop_solver.py)** |
| `survey/captcha_router.py` | unchanged | unchanged | unchanged | unchanged | **MOD** |
| `survey/cdp_actuator.py` | unchanged | unchanged | unchanged | unchanged | **MOD** |
| `survey/cua_fallback.py` | unchanged | unchanged | unchanged | unchanged | **MOD** |
| `survey/graph/*` | unchanged | unchanged | unchanged | unchanged | **MOD (3 Dateien)** |
| `evals/*` | unchanged | NEW | unchanged | unchanged | unchanged |
| `.github/workflows/*` | NEW (smoke) | NEW (eval) | unchanged | unchanged | unchanged |
| `tests/*` | NEW (fixtures) | NEW (eval tests) | unchanged | NEW (status tests) | unchanged |

Konfliktrisiko mit allen in-flight Tracks: **0**.

---

## Estimated complexity

**S** — 7 Dateien, davon 5 rein mechanisch (W293/W291/W605/E401 auto-fix
mit `--unsafe-fixes`), 2 mit kleinem review-Aufwand (F841 except-drops),
1 mit dokumentierter behavior-risk-Mitigation (`# noqa: F401` mit
comment-explainer). One-PR-cycle, etwa SR-103-Komplexitaet x2.

---

## Sequencing

**Empfohlen: SR-106 nach Merge von PR #105 starten.** Begruendung:

- Beide modifizieren NICHT dieselben Dateien (`survey/qualification_rules.py`
  vs. 7 andere) — git-conflict-frei
- ABER: das tree-weite AC8 (`ruff check survey/`) braucht **beide** PRs
  gemerged. Wenn #106 vor #105 mergt, ist der tree-weite check **noch
  rot wegen qualification_rules.py** — die PR-Verification-Tabelle waere
  irrefuehrend
- Reverse-Reihenfolge geht auch, aber das CI-Story ist sauberer wenn
  #105 zuerst durchgeht und #106 dann als "complete-the-tree" framed

**Hard requirement: KEIN gleichzeitiger merge.** Beide PRs muessen
sequentiell durch die CI, sonst koennen sie sich gegenseitig die
"checks passed"-Verifikation invalidieren.

---

## References

- Issue #103 + AC-Korrektur-Comment (2026-05-12)
- `.github/workflows/ci.yml` §74-75 — der harte ruff-gate (unveraendert)
- AGENTS.md §13.8.1 SR-62 — Vertrag dass `--select E,W,F` NICHT
  aufgeweicht wird (#106 erfuellt den Vertrag mit fix-not-suppress)
- Behavior-risk-Mitigationen: option-A jeweils gewaehlt (siehe Per-
  Violation-Plan oben)
