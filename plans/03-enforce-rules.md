# Plan 03: Enforce Rules

> **Parent**: `ULTIMATE-PLAN.md`  
> **Phase**: 3  
> **Priority**: P0

## Ziel

Regeln werden automatisch erzwungen. Warntexte in Kommentaren sind nicht die Sicherheitsarchitektur.

## Aktueller Stand

Vorhanden:

- `.pre-commit-config.yaml`
- `scripts/check_banned_patterns.py`
- `scripts/verify_completeness.py`

Noch offen:

- CI-Gate.
- Secret-Scan Gate.
- `verify_completeness.py` auf sinnvolle Regeln tunen.
- Historische BANNED-Kommentarbloecke spaeter entfernen.

## Was falsch ist

Ein Repo mit tausenden Warnkommentar-Zeilen, aber ohne blockierende CI, ist gefaehrlich. Menschen und Agents ueberlesen Regeln. CI nicht.

## Gates

| Gate | Scope | Blockt |
|---|---|---|
| Ruff | Python | Syntax, Style, simple bugs |
| Ruff format check | Python | Format drift |
| Mypy/Pyright scoped | Core modules | Interface drift |
| detect-secrets | all files | Secrets |
| banned patterns | executable code | Chrome kill, hardcoded PID, unquoted origins, banned tools |
| tests | unit/integration | regressions |

## Banned Patterns

Mindestens blocken:

- `pkill -f "Google Chrome"`
- `killall Google Chrome`
- hardcoded PIDs in executable code
- `--remote-allow-origins=*` ohne Quotes
- fixed `/tmp/heypiggy-bot` Profil
- `webauto-nodriver`
- `skylight-cli click --element-index`
- echte Credential-Werte
- `os.kill(pid, 9)` ohne vorherigen SIGTERM-Fallback

## Completeness-Regeln sinnvoll machen

Nicht alles braucht einen langen Docstring. SOTA ist: wichtige Interfaces sind dokumentiert, invariants sind getestet, und Regeln werden automatisiert.

`verify_completeness.py` sollte blocken:

1. Public Interface ohne Docstring.
2. Neue Datei ohne Test, wenn sie Produktionslogik enthaelt.
3. Hardcoded Credential/PID/Email.
4. Neue Chrome-Prozess-Erzeugung ausserhalb `ChromeLauncher`.
5. Neue Provider-Sonderlogik ausserhalb `providers/`.

Nicht blocken:

- Jeden privaten Helper ohne Docstring.
- Jede Konstante ohne langen Kommentar.
- Historische Markdown-Warntexte.

## Arbeitsschritte

1. `.pre-commit-config.yaml` lokal validieren.
2. `scripts/check_banned_patterns.py` auf aktuelle False Positives tunen.
3. `scripts/verify_completeness.py` auf Interface-Regeln statt Kommentar-Manie begrenzen.
4. GitHub Actions Workflow fuer pre-commit und tests erstellen.
5. BANNED-Kommentarbloecke erst nach aktivem CI schrittweise entfernen.
6. ADR schreiben: "Rules live in CI, not comments".

## Verification

```bash
pre-commit run --all-files
python scripts/check_banned_patterns.py survey-cli cli run_survey.py
pytest survey-cli/tests -q
```

## Exit-Kriterien

- Ein PR/Commit mit banned pattern wird automatisch geblockt.
- Ein PR/Commit mit Secret wird automatisch geblockt.
- Historische Doku-Regeln sind mit CI-Regeln abgeglichen.
