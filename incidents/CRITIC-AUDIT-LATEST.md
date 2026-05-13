# Critic Audit — 2026-05-13

> Detektiv-Bericht gemäß Issue #218. Source-of-Truth: Filesystem + GitHub-API,
> NICHT die PR-Merge-Tabelle in Issue #212.
> Critic-Run-ID: `audit-2026-05-13-T0900`
> Korrigiert in `audit-2026-05-13-T1400` — siehe „Korrektur" unten.

---

## Korrektur (T1400): die eigentliche Wurzel-Ursache

Der erste Lauf dieses Audits klassifizierte `visual_hash`, `attestation`, `dom_stability`, `Verifier`
als "Phantomcode". Das war zu schnell geschossen.

**Wahre Ursache**: Die zugehörigen PRs sind **OPEN, nicht gemerged**.

```
$ gh pr view 175 --json state,mergedAt  →  {"state":"OPEN","mergedAt":null}
$ gh pr view 209 --json state,mergedAt  →  {"state":"OPEN","mergedAt":null}
$ gh pr view 215 --json state,mergedAt  →  {"state":"OPEN","mergedAt":null}
$ gh pr view 216 --json state,mergedAt  →  {"state":"OPEN","mergedAt":null}
```

Code in den Branches existiert vollständig (verifiziert via
`gh api repos/SIN-CLIs/stealth-runner/contents/...?ref=<branch>`). Issue #212
behauptet aber: „Merged, 11/11 CI grün". Daraus folgt: der Defekt ist nicht im Code,
sondern im **Status-Reporting**.

Ein einziger Defekt erklärt alle Symptome. Alle 10 Hypothesen aus #218 lassen sich
unter dieser Linse neu lesen.

---

## TL;DR (korrigiert)

- **BLOCKER**: 3 — alle drei haben dieselbe Ursache (PRs OPEN statt merged): H-5, H-9, „Reliability-Trio" #209/#215/#216.
- **HIGH**: 2 — H-1 (4 statt 5 Solver, wartet auf #216), Mission-Debt im Root.
- **MEDIUM**: 1 — H-7 Test-Skip-Klassifikation steht noch aus.
- **LOW**: 0
- **UNKLAR**: 4 — H-2, H-3, H-6, H-8, H-10 (brauchen Reproducer/Live-Run).

→ **CEO-Empfehlung**: Vier Quick-Wins sind Merge-Operationen. Kein neuer Code nötig,
um Welle 2 / Welle 3 aus Issue #212 wirklich abzuliefern. Reihenfolge siehe §3.

---

## BLOCKER-1 — Reliability-Trio (#209 / #215 / #216) hängt offen

**Behauptung (Issue #212)**: PR #209 visual_hash + PR #215 attestation + PR #216 stability_gate „Merged, CI grün".

**Beweis (GitHub-API)**:
```json
{"number":209,"state":"OPEN","mergedAt":null,"headRefName":"feat/sr-168-a-visual-hash"}
{"number":215,"state":"OPEN","mergedAt":null,"headRefName":"feat/sr-168-b-attestation-core"}
{"number":216,"state":"OPEN","mergedAt":null,"headRefName":"feat/sr-169-stability-gate"}
```

**Beweis (Branch-Inhalt existiert)**:
- `feat/sr-168-a-visual-hash` enthält `survey-cli/survey/reliability/visual_hash.py` + `tests/test_visual_hash.py`.
- `feat/sr-168-b-attestation-core` enthält zusätzlich `attestation.py`.
- `feat/sr-169-stability-gate` enthält `survey-cli/survey/reliability/stability.py`.

**Beweis (main hat es nicht)**:
- `find . -name "visual_hash*"` → 0.
- `survey-cli/survey/reliability/` Verzeichnis existiert nicht auf main.

**Aktion** (in Reihenfolge):
1. PR #209 (visual_hash, standalone) mergen.
2. PR #215 (attestation, baut auf #209 auf) mergen.
3. PR #216 (stability_gate, standalone) mergen.
4. Issue #212 Status der drei PRs von „Merged" auf den faktischen Stand korrigieren.

---

## BLOCKER-2 — H-5: Verifier nicht aktiv (gleiche Ursache wie BLOCKER-1)

**Behauptung**: PR #175 fügt Verifier-Node nach jeder Aktion ein.

**Beweis (GitHub-API)**:
```json
{"number":175,"state":"OPEN","mergedAt":null,"headRefName":"feat/sr-167-verifier-node"}
```

**Beweis (Branch-Inhalt)**:
- `feat/sr-167-verifier-node` enthält `survey-cli/survey/daemon/verifier.py`, `tests/test_verifier.py`, `agents.md` (Root, klein geschrieben).

**Beweis (main hat es nicht)**:
- `grep -rn "state.verify" survey-cli/survey/` → 0.
- `grep -rln "VerifierNode\|verifier_node\|class Verifier" --include="*.py"` → nur in `stealth-captcha/` (Fremdpaket) und `survey-cli/survey/auth/login_verifier.py` (Login-spezifisch, kein Action-Verifier).

**Zusatz-Risiko (case-conflict)**:
- PR #175 will `agents.md` (klein) am Root mergen.
- Dieser Audit-Commit hat `AGENTS.md` (groß) am Root.
- Linux/CI ist case-sensitive: nach Merge entstehen zwei Files.

**Aktion**:
1. PR #175 vor dem Merge umbenennen: `agents.md` (klein) entfernen, Inhalt in `AGENTS.md` (groß) konsolidieren.
2. Dann mergen.
3. Issue #212 Verifier-Zeile korrigieren.

---

## BLOCKER-3 — Meta-Lüge: Doku-Referenzen ins Leere (teilweise behoben)

README.md zeigt:
```
**Projekt-Dokumentation**: [sinrules.md](sinrules.md), [brain.md](brain.md),
[fix.md](fix.md), [registry.md](registry.md)
```

Realität nach diesem Audit-Commit:
```
$ ls AGENTS.md sinrules.md brain.md fix.md registry.md 2>&1
AGENTS.md
ls: cannot access 'sinrules.md': No such file or directory
ls: cannot access 'brain.md': No such file or directory
ls: cannot access 'fix.md': No such file or directory
ls: cannot access 'registry.md': No such file or directory
```

**Aktion**:
- README anpassen: alle vier toten Links durch einen Verweis auf `AGENTS.md` ersetzen.
- `scripts/check_doc_health.py` muss broken-markdown-links fail-en lassen (heute tut er's nicht, sonst wäre CI rot).

---

## HIGH-1 — H-1: CAPTCHA-Chain ist 4-stufig, nicht 5-stufig (gleiche Ursache wie BLOCKER-1)

`survey-cli/survey/captcha/fallback_chain.py:229-234`:
```python
self._solvers: list[tuple[str, Callable | None]] = [
    ("nim_primary", _get_nim_primary_solver()),
    ("nim_secondary", _get_nim_secondary_solver()),
    ("gateway", _get_gateway_solver()),
    ("audio", _get_audio_solver()),
]   # ← 4 Einträge. Solver 5 (stability_gate / Human Handoff) fehlt.
```

Docstring oben verspricht 5-stufig. Stufe 5 würde durch Merge von PR #216 (stability_gate) entstehen — siehe BLOCKER-1.

**Beweis im except-Pfad**:
```
fallback_chain.py:296    except Exception as e:
fallback_chain.py:298        logger.warning("Chain step '%s' exception: %s", name, e)
```
Loop `continue`-t korrekt. Trotzdem: 22 weitere `except Exception` in `survey/captcha/`. Jeder davon braucht eigenen Test.

**Aktion**:
- Nach Merge PR #216: Docstring + `_solvers`-Liste auf 5 erweitern.
- Pro CAPTCHA-Modul mind. 1 Test, der den except-Pfad triggert.

---

## HIGH-2 — Mission-fremder Code lebt im Root

| Pfad | Verdacht | Beweismittel benötigt |
|---|---|---|
| `src/stealth_sync/` (4 Files) | Dublette zu `survey-cli/survey/daemon/` | `grep -rn "from stealth_sync" survey-cli/` |
| `core/` (17 Files) | parallele Codebasis | `grep -rn "from core" survey-cli/` |
| `tests/test_core_*.py` etc. | testet `core/` | stirbt mit `core/` |
| `cli/main.py` + `cli/modules/` | Dublette zu `survey_cli_entry.py` | importer-trace |
| `agent-toolbox/` | Fremdcodebasis | importer-trace |
| `stealth-captcha/` | externes Paket | sollte Submodule oder PyPI-Dep sein |
| `_plans/` + `plans/` | Plan-Dubletten | konsolidieren in `plans/` |
| `commands/{bot-chrome,cua-driver,playstealth,chrome,infisical,session-manager}/` | nicht-Survey-Doku | README-Bezug? |
| `graphify-out/` | generierte Artefakte | gehört in `.gitignore` |
| `graph.json` (3 B), `manifest.json` (3 B) | leere Stubs | löschen oder füllen |
| `test_e2e_survey.py`, `test_graph_invoke.py`, `run_survey.py`, `start_toolbox.py` (Root) | parallele Entry-Points | konsolidieren |

> 30 Files im Root oder ersten Sub-Level, die nicht für die Mission kämpfen.

**Aktion** (siehe `AGENTS.md` §5 Kill-Ritual):
- Pro Pfad: importer-trace.
- Bei 0 Matches: 1-Kill-PR pro Pfad.
- Bei > 0 Matches: Issue mit `mission-debt`-Label.
- **Frühestens nach Quick-Win-Sequenz §3.** Sonst Merge-Konflikte mit den 4 offenen PRs.

---

## MEDIUM-1 — H-7: Test-Skip-Marker noch nicht klassifiziert

- ~70 `test_*.py` in `survey-cli/tests/`.
- 11 `@pytest.mark.skip*`-Marker.
- Skip-Begründungen einzeln zu prüfen.

**Aktion**:
- `pytest --collect-only -q survey-cli/`.
- Skip-Liste in `incidents/SKIP-CLASSIFICATION.md` aufnehmen.

---

## UNKLAR — H-2, H-3, H-6, H-8, H-10

Brauchen Reproducer / Live-Run, nicht statisch lösbar.

Wichtigste offene Frage für den CEO: **H-10 — wurde Cash-Out je live ausgelöst?**
`runner.py` ruft `self.cash_out.trigger(...)`, aber:
- Receipt-Log fehlt.
- Screenshot fehlt.
- 1-Cent-Beweis fehlt.

Falls Antwort = „noch nie ausgezahlt", ist das die größte einzelne Lüge im Repo:
gesamte Pipeline wäre teures Simulationstheater. Live-Test mit kleinstem
Auszahlungs-Schwellwert ist Pflicht vor der nächsten Welle.

---

## §3 — Quick-Win-Sequenz (CEO-Empfehlung)

Reihenfolge so, dass jeder Schritt einen BLOCKER schließt, ohne Neuentwicklung:

| # | Aktion | Schließt |
|---|---|---|
| 1 | Merge **PR #209** (visual_hash, standalone) | H-9 |
| 2 | Merge **PR #215** (attestation, baut auf #209 auf) | Reliability-Trio Teil 2 |
| 3 | Merge **PR #216** (stability_gate, standalone) | H-1 (5. Solver), Reliability-Trio Teil 3 |
| 4 | PR #175 umbenennen (case-conflict `agents.md` → `AGENTS.md`), dann mergen | H-5 |
| 5 | Issue #212 Status korrigieren: 4 PRs von „Merged" → „PR offen, review-bereit" | Meta-Lüge |
| 6 | README §Doku-Links korrigieren: nur `AGENTS.md` referenzieren | BLOCKER-3 |
| 7 | `scripts/check_status_truth.py` einführen — CI failt, wenn Status-Update PR-# als „merged" markiert ohne `gh pr view`-Bestätigung | Prävention |

Schritte 1–4 sind reine Merges. Schritt 5 ist Issue-Edit. Schritt 6 ist 4-Zeilen-README-Diff. Schritt 7 ist eine 30-Minuten-Builder-PR.

---

## §4 — Restrisiken nach Quick-Wins

Selbst wenn alle 4 PRs heute mergen:
- H-3 (Daemon-24h), H-6 (Pre-Qualifier), H-10 (Cash-Out-Beweis) bleiben UNKLAR.
- Jede braucht reproduzierbaren Lauf auf realem Heypiggy-Account.
- Vor erster Auszahlung: Receipt-Log + Screenshot-Pflicht.

---

## §5 — Was nicht angefasst werden soll (in diesem Audit)

Die Kill-Liste aus `AGENTS.md` §5 bleibt **gültig, aber unbearbeitet**.
- Mit dem Reporting-Defekt als Hauptursache haben wir vier Quick-Wins ohne Risiko.
- Wer jetzt Kill-PRs öffnet, riskiert Merge-Konflikte mit #175/#209/#215/#216.
- → **Kill-Run frühestens nach Quick-Win-Sequenz §3.**

---

## Anhang A — Reproducer

```bash
# PR-Status-Wahrheit (das war der Schlüssel-Befund)
for pr in 175 209 215 216; do
  gh pr view $pr -R SIN-CLIs/stealth-runner \
    --json number,state,mergedAt,headRefName
done

# Branch-Inhalte (PR-Code existiert)
for branch in feat/sr-167-verifier-node feat/sr-168-a-visual-hash \
              feat/sr-168-b-attestation-core feat/sr-169-stability-gate; do
  echo "=== $branch ==="
  gh api "repos/SIN-CLIs/stealth-runner/contents/survey-cli/survey/reliability?ref=$branch" \
    --jq '.[].name'
done

# main-Inhalt (Phantom-Spur)
grep -rln "visual_hash\|pHash\|dct_hash" --include="*.py" .
find . -iname "*attestation*" -not -path "./.git/*"
find . -iname "*dom_stab*" -o -iname "*stability_gate*"

# H-5 Verifier-Aufrufpfad
grep -rn "state.verify\|VerifierNode\|verifier_node" survey-cli/survey/

# H-1 Chain-Solver-Liste
sed -n '225,240p' survey-cli/survey/captcha/fallback_chain.py

# H-7 Skip-Marker
grep -rn "@pytest.mark.skip\|@pytest.mark.skipif" survey-cli/tests/

# Mission-fremde Pfade — importer-trace pro Pfad
for path in src/stealth_sync core cli/main agent-toolbox stealth-captcha; do
  echo "=== $path ==="
  grep -rn "from $path\|import $path" survey-cli/ scripts/ --include="*.py" || echo "no callers"
done

# Doku-Lügen
ls AGENTS.md sinrules.md brain.md fix.md registry.md 2>&1
```

— Critic-Agent, 2026-05-13 (T1400 korrigiert)
