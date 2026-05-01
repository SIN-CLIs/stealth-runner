# CONTRIBUTING.md — stealth-runner

> **Merge-Regeln, Code-Konventionen, PR-Checkliste**
> Stand: 2026-04-30 · v0.3.1 Greenfield

---

## 1. Architektur-Regel (nicht verhandelbar)

- **Dies ist ein CLI-Orchestrator, kein Server.** Kein MCP, kein REST, keine persistenten Prozesse.
- **Jede Aktion ist atomar.** Der `StealthExecutor` kapselt alle CLI-Aufrufe – kein direkter `subprocess.run` außerhalb dieser Klasse.
- **Kein Fallback auf `skylight-cli`.** `StealthExecutor.__init__` wirft `RuntimeError`, wenn `skylight-cli` nicht installiert ist.
- **State Machine ist die einzige Kontrollstruktur.** Kein `while True` außerhalb von `run()`.

---

## 2. Merge-Workflow

1. **Branch**: `feat/<name>` oder `fix/<name>`
2. **Commit**: Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`, `security:`)
3. **PR**: gegen `main`, braucht mindestens 1 Review
4. **Merge**: Squash & Merge

---

## 3. PR Checklist (ALLE Punkte müssen erfüllt sein)

- [ ] `brain.md` aktualisiert (falls Architektur-Änderung)
- [ ] `architecture.md` aktualisiert (falls neue/geänderte Komponenten)
- [ ] `issues.md` aktualisiert (gelöste Issues markiert, neue dokumentiert)
- [ ] `banned.md` konsultiert – KEINE verbotenen Patterns eingeführt
- [ ] Tests laufen: `python -m pytest tests/` → 18/18 PASS
- [ ] Keine `skylight-cli`-Referenzen
- [ ] Keine CDP/DOM-Referenzen
- [ ] `StealthExecutor`-Backend ist **ausschließlich** `skylight-cli`
- [ ] `VisionClient` hat vollständigen `SYSTEM_PROMPT` (10 Aktionen)
- [ ] `unmask-cli verify-stealth` ist im `VERIFY`-State integriert
- [ ] `playstealth-cli launch` ist im `LAUNCH_BROWSER`-State
- [ ] Alle neuen Funktionen haben Type-Hints

---

## 4. Code-Konventionen

### 4.1 Allgemein

- Python 3.12+, Type-Hints auf allen public functions
- `async/await` für alle Zustandsübergänge
- Panel-Logik ausschließlich in `sin_survey_core`, nicht im Runner

### 4.2 State Machine

- Neue Zustände brauchen eine `async`-Methode `_<state>()`
- Nach jedem `EXECUTE` MUSS `VERIFY` folgen

### 4.3 StealthExecutor

- Alle CLI-Aufrufe NUR über `self.run(cmd)`
- JSON-Parsing von stdout, Fehler von stderr

### 4.4 VisionClient

- `get_action(image_path, step)` — einzige öffentliche Methode
- Fallback-Kaskade: CF → NVIDIA → Parse-Fallback → harter Fallback
- Prompt-Änderungen in `runner/prompt_kit.py`

---

## 5. Verbotene Patterns (siehe `banned.md`)

- ❌ `skylight-cli` · ❌ `open -na Chrome` · ❌ CDP/DOM · ❌ Cursor-Stealing
- ❌ `AXStaticText` klicken · ❌ Klick ohne Vision · ❌ `.env` mit Secrets

---

## 6. Tests

```bash
python tests/test_runner.py
python tests/test_sin_survey_core.py
```

---

## 7. Dokumentation

| Datei             | Wann aktualisieren           |
| ----------------- | ---------------------------- |
| `brain.md`        | Architektur-Änderungen       |
| `architecture.md` | Neue/geänderte Komponenten   |
| `issues.md`       | Issues gelöst/erstellt       |
| `banned.md`       | Neue verbotene Patterns      |
| `fix.md`          | Jeder Bugfix mit Commit-Hash |

---

## 8. Commit-Messages

```
feat: add OCR fallback for Canvas elements
fix: prevent AXStaticText clicks in Vision prompt
docs: update architecture.md
security: remove .env with real credentials
```
