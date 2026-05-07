# Issue #5: Code-Completeness-Verification — Automatische Prüfung fehlt (P0)

> **Status**: OPEN
> **Severity**: 🔴 P0 — Code kann unvollständig/ungetestet deployed werden
> **Reporter**: SIN-Agent Automated Analysis (2026-05-08)
> **Betroffene Dateien**: ALLE Code-Dateien, tests/, scripts/check_doc_health.py

---

## Problem-Beschreibung

Es gibt KEINE automatisierte Prüfung die sicherstellt dass:
1. Jede Funktion einen Docstring mit Args, Returns, Side Effects hat
2. Jede Konstante einen WARUM-Kommentar hat
3. Jede Aktion einen Verify-Step hat (oder dokumentiert warum nicht)
4. Jede Datei einen BANNED-Methods-Header hat
5. Jede öffentliche Funktion mindestens 3 Tests hat
6. Keine hardcoded Credentials/PIDs im Code sind

**Impact**: Code kann deployed werden der unvollständig dokumentiert ist, keine Verify-Box hat, oder keine Tests hat. Nächster Agent versteht den Code nicht → Fehler.

---

## Ziel

**Vor jedem Commit** muss eine automatisierte Prüfung alle 6 Punkte checken und den Commit BLOCKIEREN wenn nicht erfüllt.

---

## Akzeptanzkriterien

- [ ] `scripts/verify_completeness.py` existiert und prüft ALLE 6 Punkte
- [ ] Wird als pre-commit hook registriert (`.git/hooks/pre-commit`)
- [ ] Blockiert Commits die BANNED-Patterns enthalten
- [ ] Kann auch manuell ausgeführt werden: `python3 scripts/verify_completeness.py`
- [ ] Gibt klare, menschenlesbare Fehlermeldungen
- [ ] Integration in CI/CD (GitHub Actions)

---

## Implementierungs-Plan

### Check 1: Docstring-Präsenz
```python
# Prüft ob jede def/class einen Docstring hat
# Ignoriert: dunder methods (__init__, __repr__), private helpers (_ prefix)
for file in python_files:
    for func in parse_functions(file):
        if not func.has_docstring:
            errors.append(f"{file}:{func.lineno}: {func.name}() missing docstring")
```

### Check 2: BANNED-Methoden Header
```python
# Prüft ob Datei-Header "BANNED" Section enthält
for file in python_files:
    if "BANNED" not in open(file).read()[:2000]:
        errors.append(f"{file}: Missing BANNED methods section in header")
```

### Check 3: Hardcoded PIDs
```python
# Prüft auf Muster wie pid = 71104 oder "pid": 56640
for file in python_files:
    for line in open(file):
        if re.search(r'(pid|PID)\s*[=:]\s*\d{4,6}', line):
            if "WARUM" not in line and "BEISPIEL" not in line.upper():
                errors.append(f"{file}:{lineno}: Hardcoded PID detected: {line}")
```

### Check 4: Hardcoded Credentials
```python
# Prüft auf API Keys, Emails, Passwörter
for file in python_files:
    for line in open(file):
        if re.search(r'(nvapi-|sk-|fw_|api_key\s*=\s*["\'])', line):
            if "NVIDIA_API_KEY" not in line and "os.getenv" not in line:
                errors.append(f"{file}:{lineno}: Hardcoded credential: {line}")
```

### Check 5: playstealth usage
```python
# Prüft auf BANNED playstealth launch
for file in python_files:
    for line in open(file):
        if "playstealth" in line.lower() and "BANNED" not in line:
            errors.append(f"{file}:{lineno}: playstealth detected: {line}")
```

### Check 6: Test-Abdeckung
```python
# Prüft ob für jede .py Datei eine _test.py Datei existiert
for file in python_files:
    if file.endswith("_test.py"):
        continue
    if file.endswith("__init__.py"):
        continue
    test_file = file.replace(".py", "_test.py")
    if not os.path.exists(test_file):
        warnings.append(f"{file}: No corresponding test file: {test_file}")
```

---

## Dateien

- Neu: `scripts/verify_completeness.py`
- Neu: `.git/hooks/pre-commit` (oder `.pre-commit-config.yaml`)
- Update: `AGENTS.md` → §CODE REVIEW CHECKLIST → verweist auf verify_completeness.py

---

## Abhängigkeiten

- Keine externen Bibliotheken (nur Python Standardlib)
- Muss in <1s laufen (kein pytest, nur statische Analyse)

---

*Erstellt: 2026-05-08*
