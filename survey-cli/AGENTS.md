---
content: |
  # AGENTS.md - Stealth Survey CLI
  
  **← [../AGENTS.md](../AGENTS.md) ist das MASTER Regelwerk.**
  **← [../sinrules.md](../sinrules.md) ist das zentrale Regelwerk.**
  
  ---
  
  ##  ARCHÄOLOGIE-TSUNAMI - ABSOLUTE PFLICHT VOR JEDER AKTION
  
  **️ VERSTOSS = SOFORTIGER STOP + RISIKO FÜR USER-DATEN/CHROME ️**
  
  **REGEL: Jeder Agent MUSS vor dem ERSTEN Code-Edit einen vollständigen Archäologie-Tsunami starten. KEINE AUSNAHMEN. NICHT VERHANDELBAR.**
  
  ### Warum?
  - **Alter Code = extrem gefährlich** (tötet User Chrome, leaked Credentials, destroyed sessions)
  - **Falscher Code = verwirrt Agents unnötig** (wie DICH! Du denkst du weißt es, aber du LÜGST!)
  - **Lügen-Code = das Schlimmste was in einer Entwicklung geschehen kann** (zerstört Production-Systeme)
  - **Nicht ausreichend kommentierter Code = nächster Agent zerstört alles wieder** (und der nächste, und der nächste...)
  
  ### ️ WARNUNG AN ALLE AGENTS: IHR LÜGT ALLE!
  **Jeder Agent denkt er "kennt den Code". Jeder Agent denkt er "weiß wie es funktioniert". Jeder Agent denkt er "braucht nicht recherchieren".**
  
  **FALSCH. IHR LÜGT ALLE. IMMER.**
  
  - Gestern war alles anders
  - Der Code den du denkst zu kennen wurde gestern Nacht geändert
  - Die PIDs die du auswendig gelernt hast sind DYNAMISCH
  - Die Tools die du nutzen willst sind VIELLEICHT BANNED
  - **RECHERCHIEREN IST NICHT OPTIONAL. ES IST PFLICHT.**
  
  ### Pflicht-Prozedur (IN DIESER REIHENFOLGE - KEIN VERKÜRZEN!):
  1. **Explore Subagent STARTEN**\: Scan ALLER Repos und Code-Dateien (rekursiv!)
  2. **Kategorisieren**\:  DELETE (alt/broken/banned) | ️ LEGACY |  ACTIVE
  3. **BANNED-Patterns prüfen**\: playstealth, webauto-nodriver, pkill -f Google Chrome, hardcoded PIDs, --remote-allow-origins=* ohne Quotes
  4. **Löschen**\: Alle  DELETE Dateien SOFORT entfernen (kein "vielleicht noch nützlich")
  5. **Kommentieren**\: Jede verbleibende Code-Datei mit EXTREMEN Kommentaren ausstatten:
     - **Was macht diese Datei?** (WARUM existiert sie?)
     - **Was ist die Architektur?** (Wie passt sie ins Gesamtbild?)
     - **Was sind die Abhängigkeiten?** (Was bricht wenn diese Datei fehlt?)
     - **BANNED-Methoden als WARNUNG** (in JEDER Datei!)
     - **Jede Funktion dokumentieren** (Args, Returns, Side-Effects, Race-Conditions)
     - **Jede Konstante erklären** (Warum dieser Wert? Warum nicht anders?)
     - **Warum-Fragen beantworten** (Warum 10 Erfolge? Warum 3x Retry? Warum 8s Sleep?)
  6. **Test-Dateien**\: Kein Tool ohne Test-Dateien! KEINE AUSNAHME!
  7. **Commits prüfen**\: `git log --oneline -20` - Was wurde zuletzt geändert?
  8. **Issues prüfen**\: Sind bekannte Bugs dokumentiert?
  
  ### Bei Abweichung (Code entspricht nicht Schema / sieht komisch aus / du verstehst es nicht):
  1. **SOFORT STOP** - Keine weiteren Änderungen!
  2. **Deep-Recherche starten** (alle Repos, Issues, Commits, READMEs)
  3. **ALLE betroffenen Dateien identifizieren**
  4. **Kommentare/Dokumentation in ALLEN betroffenen Dateien nachholen**
  5. **BANNED-Patterns in Code UND Doku markieren**
  6. **Erst DANN weiterarbeiten**
  
  ---
  
  ##  EXPLICITE VERBOTE (UNVERBRÜCHLICH)
  
  ### Chrome Startup
  -  `playstealth launch` - setzt NICHT --force-renderer-accessibility
  -  Chrome OHNE `--force-renderer-accessibility` - cua-driver AX-Tree LEER
  -  Chrome OHNE `--remote-allow-origins="*"` (MIT Quotes!) - CDP WebSocket 403
  -  Chrome MANUELL starten: `/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9999 --remote-allow-origins="*" --force-renderer-accessibility --no-first-run --user-data-dir=/tmp/heypiggy-new-$(date +%s) URL`
  
  ### User Chrome
  -  `pkill -f "Google Chrome"` - VERBOTEN (tötet User Chrome!)
  -  `killall Google Chrome` - VERBOTEN
  -  `kill <pid>` auf USER Chrome PIDs - VERBOTEN
  -  NUR Bot-Chrome beenden (profile=/tmp/heypiggy-new-*)
  
  ### Tools
  -  webauto-nodriver - ABSOLUT BANNED
  -  cua-driver click (raw index) - instabil, nutze tool_click.py
  -  skylight-cli click --element-index - Index instabil
  -  Hardcoded PIDs - dynamisch, niemals hardcodieren
  
  ## NEMO Architecture
  
  ```
  Compact Snapshot (skylight/CDP) → Nemotron Decision (NIM) → Batch Execute (CDP) → Memory/Guardian
  ```
  
  Vorteil: 1 LLM-Call PRO SEITE (nicht pro Element!) = 10× effizienter
  
  ---
  
  ## PATH DOCTRINE (SR-159)
  
  **Status:** foundational, enforced by CI (`.github/workflows/path-guard.yml`)
  and pre-commit (`scripts/path_guard.py`). Every agent reads this section
  before writing the first line of code. The guard is the executable mirror
  of this section — they MUST stay in sync.
  
  ### Authority Statement
  
  **`survey-cli/survey/` is the only Python source root. Anything else is
  dead, legacy, or out-of-scope. New Python code that lands anywhere else
  is a CI failure, not a stylistic preference.**
  
  ### Why this exists (empirical record — do not lose this)
  
  - **SR-154:** PR landed reformatting 100+ files into `agent-toolbox/core/network/`.
    That tree did not exist in the canonical layout. PR was discarded;
    cherry-picking onto `survey-cli/survey/network/` was ~10× faster than
    resolving conflicts.
  - **SR-162:** `survey-cli/survey/daemon.py` (file with `DaemonManager`)
    coexisted with `survey-cli/survey/daemon/` (package with `SurveyDaemon`).
    Python silently picked the package → `DaemonManager` became unreachable
    → CI red for 7+ consecutive runs before anybody traced it. No reviewer
    caught it — looked like two unrelated PRs at review time.
  - **SR-159 (this section):** codifies both failure modes as a 5-line CI
    check. From now on neither can recur without explicit override.
  
  ### Allowed top-level entries
  
  ```
  stealth-runner/
  ├── survey-cli/         ← ALL Python production code + tests
  ├── stealth-captcha/    ← captcha solver subsystem (in-scope)
  ├── scripts/            ← bash + python utility scripts (CI, audits)
  ├── .github/            ← workflows, issue templates, CODEOWNERS
  ├── docs/               ← legacy docs dir; new docs go in AGENTS.md
  └── (root config files only — see scripts/path_guard.py ALLOWED_ROOT_FILES)
  ```
  
  Tool-config dot-dirs (`.agents/`, `.claude/`, `.opencode/`, `.qwen/`) are
  out-of-scope for the guard. They contain prompts/config only.
  
  ### Banned top-level entries
  
  | Dir              | Why dead                                                |
  |------------------|---------------------------------------------------------|
  | `agent-toolbox/` | dead since SR-154 — code moved to `survey-cli/survey/`  |
  | `agent_toolbox/` | typo-fork of above, never canonical                     |
  | `core/`          | top-level `core` rejected in SR-154                     |
  | `lib/`           | never canonical                                         |
  | `src/`           | never canonical; `survey-cli/` is the source tree       |
  
  Existing files under these dirs are **grandfathered** — the guard runs
  in `--diff` mode, so legacy state is tolerated until a dedicated cleanup
  PR removes it. Adding *new* files under any banned dir trips the guard.
  
  ### Banned drift patterns (anywhere in tree)
  
  - **Module-vs-package shadow:** `<X>.py` and `<X>/` siblings in the same
    parent. Python silently picks the package; the module becomes
    unreachable. SR-162 burned a week on exactly this. The guard's
    behaviour here depends on mode:
    - `--diff` (CI default): only blocks if the PR touches one half of
      the pair. Pre-existing shadows are reported as warnings — visible
      on every PR but non-blocking, so a governance PR is not held
      hostage to unrelated tech debt.
    - `--strict` / `--audit`: blocks on every shadow pair in the tree.
    There is currently one known pre-existing shadow
    (`survey-cli/survey.py` vs `survey-cli/survey/`) that must be
    resolved in a dedicated follow-up PR.
  
  ### Recommended sub-packages under `survey-cli/survey/`
  
  ```
  survey/
  ├── daemon/           ← LangGraph + FastAPI orchestrator (single-daemon loop)
  ├── reliability/      ← retry, DLQ, verifier (SR-167)
  ├── network/          ← proxy, IP-quality (SR-151)
  ├── captcha/          ← solver router + adapters (SR-138)
  ├── observability/    ← events, traces, autodoc
  ├── providers/        ← heypiggy, qualtrics, toluna, ...
  └── (top-level modules: snapshot.py, accessibility.py, safe_executor.py, ...)
  ```
  
  ### Pre-flight checklist (must pass before opening a PR)
  
  - [ ] Read this section in full
  - [ ] Read the issue you are working on, in full
  - [ ] Glob the top-level layout — confirm only allowed dirs are touched
  - [ ] If your plan requires a NEW top-level dir → **STOP**, open a
        clarification comment on the issue *before* writing code
  - [ ] If you see code in `agent-toolbox/`, `agent_toolbox/`, top-level
        `core/`, `lib/`, `src/` — it is dead. Do not modify unless you are
        deleting it.
  - [ ] If you create a module named `<X>.py`, confirm there is no
        `<X>/` directory next to it (and vice versa)
  - [ ] Run `python scripts/path_guard.py --diff` locally before pushing
  
  ### STOP rule (non-negotiable)
  
  If your plan deviates from the layout above — **STOP**. File a
  clarification on the issue. Do not improvise. Working around the guard
  (e.g. renaming a file just to make CI pass while smuggling the same
  code into a banned location) is a fireable offence in this repo's
  governance model.
  
  ### Deprecation-shim pattern (for retiring a module without breaking imports)
  
  When a module moves from old → new path, leave the old path as a shim
  for one release cycle:
  
  ```python
  # old/path/module.py
  """DEPRECATED — moved to new.path.module (SR-NNN, will be removed in vX.Y)."""
  import warnings
  warnings.warn(
      "old.path.module is deprecated; import from new.path.module",
      DeprecationWarning,
      stacklevel=2,
  )
  from new.path.module import *  # noqa: F401,F403
  ```
  
  Then delete the shim in the next release. Never leave shims indefinitely
  — they are SR-154 in slow motion.
  
  ### Python-version compatibility (hard requirement)
  
  - Targets: **3.12 + 3.13** (CI matrix in `.github/workflows/ci.yml`)
  - `asyncio.run(...)` — never `asyncio.get_event_loop()`
  - `datetime.now(timezone.utc)` — never `datetime.utcnow()`
  - Zero deprecation warnings under either interpreter — CI fails on them
  
  ### Test discipline
  
  - Production tests live in `survey-cli/tests/`
  - Fixtures live in `survey-cli/tests/fixtures/`
  - **Never** put tests inside production modules
  - **Never** put production code inside `survey-cli/tests/`
  
  ### Ruff / lint discipline
  
  - Line length: **100** (configured in `pyproject.toml`)
  - `F401` (unused imports) is **hard** — no global ignore
  - `# noqa` is allowed sparingly, but every occurrence must carry a
    rationale comment on the same line
  
  ### Branch / commit / PR conventions
  
  - **Branch:** `feat/sr-NNN-short-description` or `fix/sr-NNN-...`
  - **Commits:** conventional commits
    (`feat(area): ...`, `fix(area): ...`, `chore(area): ...`)
  - **PR title:** `feat(area): SR-NNN — title (#NNN)`
  - **PR body:** must reference the issue, must include a before/after
    summary of what an agent could not do before and can do now
  
  ### How the guard runs
  
  - **CI:** `.github/workflows/path-guard.yml` runs on every PR. Calls
    `python scripts/path_guard.py --diff` with `$GITHUB_BASE_REF`.
    Failure posts an annotated comment on the PR.
  - **Local:** `.pre-commit-config.yaml` runs the same command on commit.
    Use `pre-commit install` once per clone.
  - **Audit:** `python scripts/path_guard.py --audit` walks the entire
    tree and reports every violation without failing. Use this to plan
    cleanup PRs.
  - **Strict:** `python scripts/path_guard.py --strict` walks the entire
    tree and fails on any violation. Will be wired into CI *after* the
    cleanup PR removes the grandfathered legacy dirs.
  
  ### Out-of-scope (will be removed by follow-up PRs, not this one)
  
  This section ONLY introduces governance. The cleanup of existing
  violations (deleting `agent-toolbox/`, `agent_toolbox/`, top-level
  `core/`, `src/`, resolving the `survey.py` vs `survey/` shadow) lives
  in separate, narrowly-scoped PRs that the guard itself makes safe to
  land. Mixing governance and bulk-delete into one PR is exactly how
  SR-154 happened.
