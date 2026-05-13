# AGENTS.md — Das Brain

> **Diese Datei ist die einzige Wahrheit.** Wenn andere Docs widersprechen, gewinnt diese.
> Wer hier einen Pfad oder eine Regel ändert, muss `incidents/` einen Eintrag mit Begründung + Datum hinterlassen.
> Erstellt: 2026-05-13 (Critic-Agent-Brief #218, Issue #212).

---

## 1. Mission (nicht verhandelbar)

**Stealth-Runner ist ein Survey-Solver. Punkt.**

- Ziel: Hochintelligenter, 24/7 autonomer Survey-Agent, der echtes Geld verdient.
- Output-Metrik: **Cents pro Tag auf einem realen Heypiggy-Account**, nichts anderes.
- Was im Repo lebt, muss für genau diese Metrik kämpfen.

### Was zählt als "Survey-Solver-Code"?

Genau diese Verantwortlichkeiten — alles andere ist verdächtig:

1. **Survey-Discovery** — Heypiggy / Civey / PureSpectrum / Qualtrics / Toluna / Nfield-Dashboards scannen, eine offene Umfrage finden.
2. **Pre-Qualifier** — entscheiden ob eine gefundene Umfrage überhaupt gestartet werden soll.
3. **Survey-Execution-Graph** — DOM lesen, Fragetypen erkennen (radio/checkbox/slider/matrix/open-text/ranking), antworten, Seite weiterklicken.
4. **Answer-Engine** — kontextkonsistente Persona-Antworten produzieren, Anti-Drift via question_hash.
5. **CAPTCHA-Fallback-Chain** — 4 Solver + Human-Handoff-Log (real, nicht Behauptung — siehe H-1 unten).
6. **Stealth/Anti-Detection** — Browser-Fingerprint, Human-Like Timing, Session/Cookie/IP-Rotation.
7. **Auth / Login** — Login-Flow + Login-Verifier pro Plattform.
8. **Daemon-Lifecycle** — 24/7-Lauf, Auto-Recovery, Heartbeat, State-Persistenz.
9. **Reliability** — Network-State-Gate, DOM-Stability-Gate, Visual-Hash, Attestation (sobald sie wirklich existieren — siehe H-5/H-9).
10. **Cash-Out** — Schwelle erreicht → Auszahlung triggern → Log + Beweis.

Eine Datei, die keiner dieser 10 Verantwortlichkeiten dient, gehört nicht in dieses Repo.

---

## 2. Repo-Topologie (Soll-Zustand)

```
/
├── AGENTS.md                    # ← diese Datei. Das Brain.
├── README.md                    # Kurzbeschreibung + Verweis auf AGENTS.md
├── ROADMAP.md                   # was als nächstes implementiert wird
├── CHANGELOG.md                 # was geändert wurde
├── survey-cli/                  # DAS PRODUKT (alle 10 Verantwortlichkeiten leben hier)
│   ├── survey/                  # Implementation
│   ├── commands/                # CLI-Subcommands
│   ├── tests/                   # einzige Test-Quelle
│   ├── tools/                   # interne Tools
│   ├── evals/                   # Eval-Harness
│   ├── data/                    # statische Daten (Personas, Frage-Patterns)
│   ├── plan_*.md                # technische Pläne (mission-spezifisch)
│   ├── pyproject.toml
│   └── survey_cli_entry.py      # einziger Entry-Point
├── plans/                       # CEO-Pläne (chronologisch nummeriert)
├── incidents/                   # Postmortems + Kill-Logs
├── issues/                      # offene Tickets (markdown)
├── scripts/                     # repo-weite Maintenance-Skripte
├── docs/                        # mission-relevante externe Doku
├── profiles/                    # Chrome-Profile (nicht versioniert, .gitignore)
├── .agents/ .claude/ .opencode/ .qwen/   # Agent-Konfigs (read-only)
└── .github/                     # CI
```

**Alles andere ist Kill-Candidate** (siehe Sektion 5 — Audit 2026-05-13).

---

## 3. Critic-Agent — Rolle & Autorität

Es gibt im Repo **drei Agentenrollen**:

| Rolle | Aufgabe | Darf …                                            |
|---|---|---|
| **Builder-Agent** | implementiert Features | Code schreiben, PRs öffnen |
| **Reviewer-Agent** | reviewt offene PRs auf Style/Tests | PRs kommentieren, mergen |
| **Critic-Agent** | jagt stillen Failure-Modus + tötet Mission-fremden Code | Code als Kill-Candidate markieren, BLOCKER-Issues anlegen, KEINE Builds |

Der Critic-Agent ist **Anwalt des CEOs**, nicht der Programmierer. Default-Annahme: **Behauptung = Lüge bis zum Gegenbeweis**.

### Erste Pflicht jedes Critic-Runs

Bevor irgendeine Aktion gestartet wird:

1. Lies dieses Brain komplett.
2. Lies Issue **#212** (Status-Update CEO) und Issue **#218** (Detektiv-Brief).
3. Lies `incidents/CRITIC-AUDIT-LATEST.md` (oder den jüngsten datierten Audit).
4. Lies `survey-cli/AGENTS.md` (operative Regeln des Survey-CLI).
5. Lies die zehn Hypothesen (Sektion 4) und prüfe pro Hypothese: hat sich seit letztem Audit etwas geändert?

### Code-Style ist NICHT die Aufgabe

- Linter, Formatter, Type-Checks → `ruff`, `mypy` machen das in CI.
- PR-Reviews → Reviewer-Agent.
- Style-Kommentare in PRs vom Critic sind verboten.

---

## 4. Die 10 stehenden Hypothesen (H-1 .. H-10)

Diese Hypothesen sind **permanent**. Jeder Critic-Run muss sie alle re-prüfen. Sie wurden in Issue #218 vom Auftraggeber definiert.

| # | Hypothese | Letzter Status (2026-05-13) |
|---|---|---|
| H-1 | CAPTCHA-Chain ist 5-stufig | **WIDERLEGT als headline** — `_solvers` Liste hat 4 Einträge (siehe `fallback_chain.py:229-234`). Solver 5 = nur Log-Handoff. |
| H-2 | Anti-Drift via question_hash hält Matrix-Fragen | **UNKLAR** — reproducer fehlt. |
| H-3 | Daemon kann 24h laufen | **UNKLAR** — kein 30-min-Memory-Plot, kein Heartbeat-Recovery-Test. |
| H-4 | Alle 5 Solver echt verdrahtet | **PARTIAL** — Solver-Dateien existieren, aber kein Integration-Test gegen echte API. |
| H-5 | Verifier (#175) wird aktiv aufgerufen | **WIDERLEGT** — `state.verify` 0 Matches in `survey-cli/survey/`. Verifier lebt nur in `stealth-captcha/` (Fremdpaket). |
| H-6 | Pre-Qualifier (413 LoC) filtert sinnvoll | **UNKLAR** — Regeln noch nicht zusammengefasst. |
| H-7 | 70 Test-Dateien, davon wieviele tot? | 11 `@pytest.mark.skip`-Marker, Restzahl noch nicht klassifiziert. |
| H-8 | Network-Gate (#185) hat keinen toten Pfad | **UNKLAR** — Default-Timeout-Verhalten ungeprüft. |
| H-9 | Visual-Hash (#209) ist real & nützlich | **BLOCKER** — `visual_hash.py` existiert nicht. 0 Matches für `visual_hash\|pHash\|dct_hash`. PR #209 hat 11/11 CI grün, aber der gemergte Code ist im Repo nicht auffindbar. |
| H-10 | Cash-Out wurde je live ausgelöst | **UNKLAR** — `runner.py:782` ruft `self.cash_out.trigger(...)`, aber kein Receipt-Log, kein Screenshot, kein 1-Cent-Beweis. |

### Output-Format pro Hypothese

Jeder Critic-Bericht hat exakt diese Struktur (siehe Issue #218 §4):

```markdown
### H-N: <Hypothese>
Status: BESTÄTIGT | WIDERLEGT | UNKLAR
Schweregrad: BLOCKER | HIGH | MEDIUM | LOW
Beweis:
  - <Datei:Zeile> — <ein Satz>
  - reproducer: <Befehl oder Schritte>
Aktion:
  - <1-2 Zeilen>
```

---

## 5. Kill-Liste (Mission-fremder Code, 2026-05-13)

Verdächtige Pfade — jede Zeile braucht **vor dem Löschen** Beweis durch den Critic-Agent (call-graph trace, grep nach Importen, Beweis dass kein Survey-Solver-Pfad ihn berührt).

| Pfad | Verdacht | Beweismittel benötigt |
|---|---|---|
| `src/stealth_sync/` (4 Dateien) | Dublette zu `survey-cli/survey/daemon/` | grep nach `from stealth_sync` außerhalb von `src/` und `tests/` |
| `core/` | parallele Codebasis | grep nach `from core` außerhalb der eigenen Tests |
| `tests/test_core_*.py`, `tests/test_event_handlers.py`, `tests/test_form_validation.py` | testet Code aus `core/` | wenn `core/` stirbt, stirbt mit |
| `cli/main.py` + `cli/modules/` | Dublette zu `survey_cli_entry.py` | importer-trace |
| `agent-toolbox/` | Fremdcodebasis, eigenes `__init__.py`, separate Pfade | importer-trace |
| `stealth-captcha/` | externes Paket mit eigener `pyproject.toml` | sollte als Git-Submodule oder PyPI-Dep eingebunden sein, nicht inline |
| `_plans/` UND `plans/` | zwei Plan-Verzeichnisse | konsolidieren in `plans/` |
| `commands/bot-chrome/`, `commands/cua-driver/`, `commands/playstealth/`, `commands/chrome/`, `commands/infisical/`, `commands/session-manager/` | nicht-Survey-Solver-Doku | hat README einen mission-relevanten Bezug? |
| `graphify-out/` | generierte Artefakte | sollte in `.gitignore`, nicht committed |
| `manifest.json` (3 Bytes), `graph.json` (3 Bytes) | leere Dateien | löschen oder sinnvoll füllen |
| `test_e2e_survey.py` (Root), `test_graph_invoke.py` (Root) | Tests außerhalb der Test-Quelle | nach `survey-cli/tests/` verschieben oder löschen |
| `start_toolbox.py`, `run_survey.py` (Root) | parallele Entry-Points | konsolidieren mit `survey_cli_entry.py` |

### Kill-Ritual (Pflicht-Sequenz)

Für jeden Kill-Candidate:

1. **Beweisen**, dass kein Survey-Solver-Pfad ihn erreicht:
   ```bash
   grep -rn "from <pfad>" survey-cli/ scripts/ --include="*.py"
   grep -rn "import <pfad>" survey-cli/ scripts/ --include="*.py"
   ```
2. Wenn 0 Matches: **Eintrag in `incidents/KILL-LOG-YYYY-MM-DD.md`** mit Pfad + Beweis + Datum + Critic-Run-ID.
3. Per separatem PR löschen (1 Kill = 1 PR), Titel: `kill: <pfad> — no survey-solver caller`.
4. PR-Description enthält den grep-Output vollständig.
5. Wenn Matches > 0: **kein Kill**, statt dessen Issue mit Label `mission-debt` und Migrations-Plan.

---

## 6. Meta-Lügen, die heute (2026-05-13) im Repo stehen

Diese werden separat in `incidents/CRITIC-AUDIT-2026-05-13.md` belegt. Kurzfassung:

1. README verweist auf `AGENTS.md`, `sinrules.md`, `brain.md`, `fix.md`, `registry.md` am Root — nur diese Datei (`AGENTS.md`) existiert; die anderen vier fehlen.
2. Issue #212 listet PRs #209, #215, #216 als "merged, CI grün". Die zugehörigen Module (`visual_hash`, `attestation`, `dom_stability`) sind im Repo nicht auffindbar.
3. PR #175 ("Verifier-Node") ist als gemergt gelistet, aber kein `state.verify`-Flag oder Verifier-Knoten im Survey-Graph.

→ **Konsequenz für Critic**: PR-Merge-Status der Issue-Tracker-Tabelle ist keine Quelle der Wahrheit. **Source of Truth = Filesystem + Call-Graph.**

---

## 7. Eskalation

Jeder BLOCKER (etwas, das den nächsten Live-Run garantiert killt):

1. Sofort separates Issue mit Label `blocker` (Critic schlägt vor; nur Maintainer öffnen).
2. Pointer-Kommentar in **Issue #212** (CEO-Status).
3. Eintrag in `incidents/CRITIC-AUDIT-LATEST.md` (Sektion BLOCKER).
4. Nicht warten bis Gesamtbericht fertig ist.

---

## 8. Anti-Patterns (Critic darf NICHT tun)

- "Looks good" sagen ohne Beweis.
- Tests als Beweis akzeptieren, ohne den Produktionspfad zu prüfen.
- Neue Features vorschlagen — wir wollen **weniger** Lügen, nicht mehr Code.
- Mass-Delete ohne Beweis-Sequenz aus Sektion 5.
- PRs reviewen (das macht der Reviewer-Agent).
- Code-Style anmerken (das macht `ruff`).

---

## 9. Schluss

> Du musst nichts beweisen. Du musst nur die Wahrheit finden, ob unsere "Meister"-Behauptung Bestand hat
> oder ob wir uns selbst belügen. **Im Zweifel: Annahme = Lüge bis zum Gegenbeweis.**
> — Agent One, 2026-05-13 (Issue #218)
