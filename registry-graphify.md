# registry-graphify.md — Graphify Commands Registry

> **Category**: Graph | **Master**: [registry.md](registry.md)

---

## C‑graphify‑build
**Command**: `graphify update .`
**Purpose**: Knowledge Graph aus Codebase bauen/aktualisieren
**Returns**: Graph-Statistiken (Nodes, Edges, Communities)
**Zugehörige Commands**: [graphify-query](#c‑graphify‑query) | [graphify‑path](#c‑graphify‑path)

---

## C‑graphify‑query
**Command**: `graphify query "<frage>"`
**Purpose**: Semantische Abfrage des Knowledge Graphen
**Example**: `graphify query "Wie hängen playstealth-launch und CUA zusammen?"`
**Zugehörige Commands**: [graphify‑build](#c‑graphify‑build)

---

## C‑graphify‑path
**Command**: `graphify path "<NodeA>" "<NodeB>"`
**Purpose**: Kürzesten Pfad zwischen zwei Nodes finden
**Example**: `graphify path "playstealth" "cua-driver"`

---

## C‑graphify‑analyze
**Command**: `graphify analyze --god-nodes --unexpected-links`
**Purpose**: Anomalien im Graph finden (God-Nodes, unerwartete Verbindungen)
**Zugehörige Commands**: [graphify‑build](#c‑graphify‑build) | [graph-report](graph-report.md)

---

## Workflow

```bash
# 1. Graph bauen
graphify update .
# 2. Auf Anomalien prüfen
graphify analyze --god-nodes --unexpected-links
# 3. Bei Auffälligkeiten: Report lesen
cat graph-report.md
```

**Letztes Update**: 2026-05-05
