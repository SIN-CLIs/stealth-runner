# ISSUE-SR-36: Generated Docs De-Duplication & Quality Check

| Feld | Wert |
|------|------|
| **ID** | SR-36 |
| **Priority** | 🟢 P3 — Low |
| **Status** | 📋 TODO |
| **Created** | 2026-05-06 |
| **Labels** | `documentation`, `cleanup`, `quality` |
| **Plan** | `plan-sr-36-docs-cleanup.md` |

## Problem
Das `scripts/generate_missing_docs.py` Script hat in **24 Repos × ~40 Dateien** generierte Docs erstellt (`agents.md`, `anti-learn.md`, `api.md`, `architecture.md`, `banned.md`, etc.). Die meisten sind leere Templates oder Boilerplate ohne Inhalt. Das verursacht:
1. **470+ Dateien** ohne echten Inhalt
2. **Token-Verschwendung** beim Laden in Agent-Kontext
3. **Duplicate Content** über alle Repos hinweg
4. **Unklarer Zustand** — welche Docs sind echt, welche generiert?

## Subissues

### SR-36.1 — Inventar aller generierten Docs
- [ ] `scripts/audit_docs.py` — scannt alle 24 Repos
- [ ] Report: welche Dateien existieren, welche haben Inhalte > 100 Zeilen
- [ ] Report: welche sind leer/boilerplate (Inhalt < 500 Zeichen)
- [ ] `doc_health_report.json` — maschinenlesbar

### SR-36.2 — Content-Quality Scoring
- [ ] Pro Datei: `score_doc(filepath)` → 0-100
- [ ] Kriterien: word_count, heading_count, code_blocks, external_links, specificity_check
- [ ] Threshold: Score < 20 → Flag als "low quality"
- [ ] `doc_quality_report.md` — Markdown-Report

### SR-36.3 — De-Duplication
- [ ] `scripts/dedup_docs.py` — identifiziert identische Docs über Repos
- [ ] SHA256-Hash-Vergleich
- [ ] Report: welche Dateien sind in wie vielen Repos identisch
- [ ] Option: zentralisierte Docs (Symlink oder single-source)

### SR-36.4 — Cleanup Script
- [ ] `scripts/cleanup_low_quality_docs.py` — interaktiv
- [ ] Löscht leere/boilerplate Docs (mit Bestätigung)
- [ ] Behält Docs mit Score > 30
- [ ] Backup vor Löschung

## Acceptance Criteria
- [ ] Audit-Report zeigt alle 470+ generierten Docs
- [ ] Quality-Score pro Datei
- [ ] Duplicates identifiziert
- [ ] Cleanup-Log: was wurde gelöscht, was behalten

## Betroffene Repos
- Alle 24 Stealth-Repos unter `/Users/jeremy/dev/`
