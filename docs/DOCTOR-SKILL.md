# /doctor — Agent-Driven Repository Health Auditor (v8)

Der Doctor ist KEIN automatisches Script das blind Docs überschreibt.
Der Doctor ist ein AGENT-WORKFLOW den du als AI-Agent Schritt für Schritt ausführst.

## Prinzipien

1. **KEINE automatischen Änderungen** — jeder Change wird von dir (AI) bewusst entschieden
2. **KEINE Text-Replacements in Docs** — Docs dokumentieren IST-Zustand, nicht SOLL
3. **JEDER Schritt durch LLM analysiert** — du verstehst WAS du änderst und WARUM
4. **VORHER lesen, NACHHER prüfen** — nie blind Dateien überschreiben

## Workflow (Du führst aus)

### Phase 1: Tool-Check
```bash
python3 runner/doctor_tools.py --check
```
→ Listet verfügbare Tools. Du siehst was da ist.

### Phase 2: Repo-Scan (pro Repo)
```bash
python3 runner/doctor_tools.py --scan <REPO_PATH>
```
→ Gibt JSON aus mit: Sprachen, Dateien, Commits, Missing-Docs, Semgrep-Warnings.
DU liest das JSON und verstehst den Zustand.

### Phase 3: LLM-Analyse (DU führst aus)
Du nimmst den Scan-Output und fragst DICH SELBST (LLM):
- Welche Docs fehlen WIRKLICH?
- Welche Docs sind veraltet?
- Welche Patterns sind problematisch?
- Was sollte geändert werden?

### Phase 4: Gezielte Änderungen (DU führst aus)
NUR die von dir (LLM) identifizierten Änderungen:
- Fehlende Docs erstellen (nur wenn wirklich nötig)
- Veraltete Docs updaten (nur spezifische Sektionen)
- Semgrep-Warnings fixen (nur in Source-Code, nie in Docs!)
- Prettier formatieren (nur Format, kein Inhalt)

### Phase 5: Commit
```bash
git add -A && git commit -m "docs: doctor-v8 — targeted updates"
```

## Geschützte Docs (NIE automatisch ändern)

Diese Docs dokumentieren Architektur-Entscheidungen und werden NUR manuell geändert:
- banned.md, brain.md, fix.md, successful.md
- learn.md, anti-learn.md, commands.md
- AGENTS.md, goal.md, architecture.md

## Tool-Liste

| Tool | Zweck | Befehl |
|------|-------|--------|
| cloc | Code-Statistiken | `cloc . --json` |
| git-log | Commit-Historie | `git log --oneline -20` |
| semgrep | Architecture-Guard | `semgrep --config=.semgrep_rules.yaml` |
| prettier | Markdown-Format | `prettier --write '*.md'` |
| graphify | Knowledge-Graph | `graphify update .` |
