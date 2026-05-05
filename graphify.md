# graphify.md — Graphify Knowledge Graph Integration

> **← [registry-graphify.md](registry-graphify.md) für Command-Registry**

---

## 🔗 Graphify im Stealth Suite Ökosystem

**Graphify** (`safishamsi/graphify`) baut einen Knowledge Graphen aus dem gesamten Codebase.
Er wird in **stealth-runner** und den aktiv genutzten Repos eingesetzt.

### Stats (letzter Build)
```
📊 4.820 Nodes, 10.860 Edges, 284 Communities
   ├── stealth-runner         (457 nodes,  36 communities)
   ├── playstealth-cli       (1.166 nodes, 78 communities)
   ├── skylight-cli          (120 nodes,  19 communities)
   ├── screen-follow         (252 nodes,  17 communities)
   ├── unmask-cli            (214 nodes,  25 communities)
   └── A2A-SIN-Worker        (2.625 nodes, 110 communities)
```

### Nutzung

```bash
# Graph bauen/aktualisieren
graphify update .

# Query: Wie hängen X und Y zusammen?
graphify query "Wie hängen X und Y zusammen?"

# Kürzesten Pfad finden
graphify path "ModulA" "ModulB"

# God-Nodes und unerwartete Links prüfen
graphify analyze --god-nodes --unexpected-links
```

### Report

Der letzte Report liegt in [graph-report.md](graph-report.md). Vor jeder größeren Aktion sollte der Graph aktualisiert und der Report auf Anomalien geprüft werden.

### Integration

- **Stealth Pipeline**: `perceive`-Phase prüft Graphify auf Code-Abhängigkeiten
- **Guardian**: Blockiert Aktionen wenn Graphify unerwartete God-Nodes findet
- **Kommandos**: [registry-graphify.md](registry-graphify.md) listet alle graphify-Befehle

**Letztes Update**: 2026-05-05
