# CONTRIBUTING.md — stealth-runner

## Merge Workflow
1. Branch: `feat/<issue-number>-<short-description>`
2. Commit: conventional commits (`feat:`, `fix:`, `docs:`, `chore:`)
3. PR: gegen `main`, braucht mindestens 1 Review
4. Merge: Squash & Merge

## PR Checklist
- [ ] BRAIN.md aktualisiert
- [ ] Tests laufen (`python -m pytest tests/`)
- [ ] Keine CDP/DOM-Referenzen eingeführt
- [ ] StealthExecutor-Backend auto-detection funktioniert

## Code-Konventionen
- Python 3.11+, Type-Hints auf allen public functions
- Keine f-string SQL, keine String-Concatenated Selectors
- `audit.log(event, **kv)` für alle Observables
- Panel-Logik in `sin_survey_core`, nicht im Runner

## Verbotene Patterns (siehe banned.md)
- Keine CDP/DOM-Zugriffe
- Keine Chrome Extensions
- Kein cursor-stealing
