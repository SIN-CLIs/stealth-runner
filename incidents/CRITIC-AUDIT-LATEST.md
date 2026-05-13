# Critic Audit — 2026-05-13

> Detektiv-Bericht gemäß Issue #218. Source-of-Truth: Filesystem + Call-Graph,
> NICHT die PR-Merge-Tabelle in Issue #212.
> Critic-Run-ID: `audit-2026-05-13-T0900`

---

## TL;DR

- **BLOCKER**: 3 gefunden (H-5, H-9, Meta-Lüge Doku)
- **HIGH**: 2 gefunden (H-1, Mission-fremder Code in Root)
- **MEDIUM**: 1 gefunden (H-7 Test-Skip-Marker)
- **LOW**: 0
- **UNKLAR (Beweis-Lücke)**: 4 (H-2, H-3, H-6, H-8, H-10)

→ **CEO-Empfehlung**: Die "Meister-Behauptung" aus Issue #212 (Welle 1+2+3 alles grün)
ist **NICHT verifizierbar** auf Filesystem-Ebene. Drei der gemergten PRs
(#175 Verifier, #209 Visual-Hash, #215 Attestation, #216 DOM-Stability) haben
**keinerlei Spur im Code**. Vor dem nächsten Live-Run muss geklärt werden,
ob diese PRs (a) wirklich in `main` gelandet sind oder (b) revert-iert wurden
oder (c) der Filesystem-Snapshot älter ist als Issue #212 behauptet.

---

## BLOCKER-1 — Phantom-Module aus Reliability-Phase 2

**Behauptung (Issue #212)**: PR #209 (visual_hash), PR #215 (attestation), PR #216 (dom_stability) gemergt mit grünem CI.

**Beweis (gegen)**:
```
$ grep -rln "visual_hash\|pHash\|dct_hash" --include="*.py" .
   (0 Matches)
$ find . -iname "*attestation*" -not -path "./.git/*"
   (0 Treffer)
$ find . -iname "*dom_stab*" -o -iname "*stability_gate*"
   (0 Treffer)
```

**Folge**: Der gesamte Verifier-Stack, der laut Issue #212 die "Maximum-Theater"-Lücke
schließen sollte, ist im Repo nicht messbar vorhanden.

**Aktion**:
1. Maintainer prüft `git log` auf `main` ob die PRs wirklich gemergt wurden.
2. Falls ja: warum ist im Working Tree nichts? Squash-Loss? Verzeichnis falsch?
3. Falls nein: Issue #212 Tabelle ist falsch — korrigieren.

---

## BLOCKER-2 — H-5: Verifier nicht aktiv

**Behauptung**: PR #175 fügt Verifier-Node ein, der nach jeder Aktion prüft.

**Beweis**:
```
$ grep -rn "state.verify\|verify=False\|verify: bool" survey-cli/survey/
   (0 Matches)
$ find . -iname "*verif*" -not -path "./.git/*"
   ./agent-toolbox/survey/auth/login_verifier.py
   ./survey-cli/survey/auth/login_verifier.py    ← Login-Spezifisch, NICHT Action-Verifier
   ./stealth-captcha/src/stealth_captcha/primitives/verify.py  ← Fremdpaket
   ./scripts/verify_completeness.py
   ./scripts/verify_installation.sh
   ./survey-cli/tests/test_open_survey_verified.py
   ./survey-cli/tools/tool_verify_state.py       ← Tool, kein Graph-Node
```

→ Es gibt keinen Verifier-**Knoten** im Survey-Execution-Graph. Was existiert,
ist Login-Verifier (auth-spezifisch) und ein CLI-Tool. **Maximum-Theater bestätigt.**

**Aktion**:
- Issue mit Label `blocker`: "Verifier-Node fehlt im Survey-Graph trotz PR #175"
- Bis dahin: die Behauptung "wir haben Verifier" ist in Docs zu streichen.

---

## BLOCKER-3 — Meta-Lüge: Doku-Referenzen ins Leere

README.md zeigt:
```
**Projekt-Dokumentation**: [sinrules.md](sinrules.md), [brain.md](brain.md),
[fix.md](fix.md), [registry.md](registry.md)
```

Realität:
```
$ ls AGENTS.md sinrules.md brain.md fix.md registry.md 2>&1
ls: cannot access 'AGENTS.md': No such file or directory
ls: cannot access 'sinrules.md': No such file or directory
ls: cannot access 'brain.md': No such file or directory
ls: cannot access 'fix.md': No such file or directory
ls: cannot access 'registry.md': No such file or directory
```

**Folge**: Jeder neue Agent, der die README liest, sucht 4 nicht-existierende Brain-Files,
findet sie nicht, und improvisiert. Garantierter Drift.

**Aktion**:
- Mit diesem Audit gepushtes `AGENTS.md` ist das einzige Brain.
- README anpassen: nur auf `AGENTS.md` verweisen.
- `scripts/check_doc_health.py` muss broken links fail-en lassen (vermutlich tut er's nicht — sonst wäre CI rot).

---

## HIGH-1 — H-1: CAPTCHA-Chain ist 4-stufig, nicht 5-stufig

`survey-cli/survey/captcha/fallback_chain.py`:

```python
# Docstring Zeile 11-15:
#   [1] NIM Primary (Nemotron-3-Nano-Omni)
#   [2] NIM Secondary (Qwen2.5-VL-72B)
#   [3] Vercel AI Gateway (Gemini → Claude)
#   [4] Audio Solver (Parakeet ASR)
#   [5] Human Handoff (JSONL Log)

# Zeile 229-234 — die tatsächliche Solver-Liste:
self._solvers: list[tuple[str, Callable | None]] = [
    ("nim_primary", _get_nim_primary_solver()),
    ("nim_secondary", _get_nim_secondary_solver()),
    ("gateway", _get_gateway_solver()),
    ("audio", _get_audio_solver()),
]   ← Solver 5 fehlt; nur 4 Einträge.
```

Solver 5 ("Human Handoff") ist im Docstring beschrieben, aber **nicht in der Liste**.
Er existiert als post-failure-Logging-Pfad, nicht als 5. Lösungsversuch. Headline-Lüge.

**Beweis im except-Pfad**:
```
fallback_chain.py:296    except Exception as e:
fallback_chain.py:298        logger.warning("Chain step '%s' exception: %s", name, e)
```
Exception wird zwar geloggt, aber der äußere Loop `continue`-t. Gut so.
Trotzdem: 22 weitere `except Exception` in `survey/captcha/`. Wer prüft die alle?

**Aktion**:
- Entweder Docstring auf "4-stufig + Handoff" korrigieren,
- oder Solver 5 als echten 5. Solver verdrahten (z.B. langsamer LLM-Vision-Fallback).
- Pro CAPTCHA-Modul: mind. 1 Test, der den `except Exception`-Pfad triggert und
  prüft, dass die Chain wirklich zum nächsten Solver geht (nicht still abbricht).

---

## HIGH-2 — Mission-fremder Code lebt im Root

11 Pfade im Repo-Root haben **keinen** Bezug zum Survey-Solver oder duplizieren bestehende Module:

| Pfad | LoC / Files | Verdacht |
|---|---|---|
| `src/stealth_sync/` | 4 Files | Dublette zu `survey-cli/survey/daemon/` |
| `core/` | 17 Files | parallele Codebasis (state_manager, error_handler, analytics, budget …) |
| `tests/test_core_*.py` u.a. | 10+ Files | testet `core/`, nicht `survey-cli/` |
| `cli/main.py` + `cli/modules/` | 4+ Files | Dublette zu `survey_cli_entry.py` |
| `agent-toolbox/` | eigenständig | Fremdcodebasis, eigenes `__init__.py` |
| `stealth-captcha/` | eigenständig | externes Paket mit eigener `pyproject.toml` |
| `_plans/` + `plans/` | 2 Dirs | Plan-Dubletten |
| `commands/{bot-chrome,cua-driver,playstealth,chrome,infisical,session-manager}/` | 6 Dirs | nicht-Survey-Solver-Doku |
| `graphify-out/` | generiert | sollte in `.gitignore` |
| `graph.json` (3 B), `manifest.json` (3 B) | 2 Files | leere Stubs |
| `test_e2e_survey.py`, `test_graph_invoke.py`, `run_survey.py`, `start_toolbox.py` | 4 Root-Skripte | parallele Entry-Points / Tests außerhalb der Test-Quelle |

→ Insgesamt > 30 Files im Root oder ersten Sub-Level, die nicht für die Mission kämpfen.

**Aktion** (siehe `AGENTS.md` §5 Kill-Ritual):
- Pro Pfad: importer-trace ausführen.
- Bei 0 Matches: separater Kill-PR (1 Pfad = 1 PR).
- Bei > 0 Matches: Issue mit `mission-debt`-Label und Migrations-Plan.

---

## MEDIUM-1 — H-7: Test-Skip-Marker noch nicht klassifiziert

- 70 `test_*.py` in `survey-cli/tests/`
- 11 `@pytest.mark.skip*`-Marker
- Verhältnis "Tests im PR-CI" vs "Tests existieren" steht noch aus

**Aktion**:
- `pytest --collect-only -q` auf survey-cli ausführen,
- Skip-Marker einzeln auf "veraltet" vs "tier3" prüfen.

---

## UNKLAR — H-2, H-3, H-6, H-8, H-10

Diese Hypothesen brauchen Reproducer / Live-Runs, die in diesem statischen Audit
nicht möglich sind. Sie bleiben offen für den nächsten Critic-Run (siehe `AGENTS.md` §4).

Insbesondere **H-10 (Cash-Out je live ausgelöst?)** bleibt die wichtigste offene Frage
für den CEO. `runner.py:782` ruft `self.cash_out.trigger(...)` — aber:
- Wo ist das Receipt-Log?
- Wo ist der Screenshot?
- Wo ist der 1-Cent-Beweis?

Falls die Antwort "noch nie ausgezahlt" lautet → das ist **die größte Lüge** im Repo:
gesamte Pipeline ist teures Simulationstheater.

---

## Anhang A — wie dieser Audit reproduziert wird

```bash
# H-9 Phantom-Module
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

— Critic-Agent, 2026-05-13
