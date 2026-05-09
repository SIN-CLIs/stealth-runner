# GITNEXUS × GRAPHIFY — State of the Art Best Practices

> **Version**: 2026-05-08 v1.0
> **Scope**: Code Intelligence Layer — GitNexus Knowledge Graph + Graphify Visual Reports
> **Status**: ⚠️ GitNexus Index STALE (40 commits behind) — Re-Indexing PFLICHT

---

## 1. ARCHITEKTUR — Zwei Layer, ein Ziel

```
+=============================================================================+
|                        CODE INTELLIGENCE LAYER                               |
+=============================================================================+
|                                                                              |
|  +─────────────────────────────────+  +─────────────────────────────────+   |
|  │        GitNexus v1.6.3          │  │        graphify                  │   |
|  │  Knowledge Graph (LadybugDB)    │  │  Static AST + HTML Reports       │   |
|  │                                 │  │                                 │   |
|  │  • 11.739 nodes / 14.337 edges  │  │  • graph.json (5.2 MB)          │   |
|  │  • 126 communities / 106 procs  │  │  • graph.html (4.0 MB)          │   |
|  │  • MCP-queryable (16 tools)     │  │  • GRAPH_REPORT.md (200 KB)     │   |
|  │  • Cross-repo via group sync    │  │  • Git pre-commit auto-rebuild  │   |
|  │                                 │  │                                 │   |
|  │  CONSUMER: AI Agent (OpenCode)  │  │  CONSUMER: Human (Browser)      │   |
|  +─────────────────────────────────+  +─────────────────────────────────+   |
|                                                                              |
+=============================================================================+
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
            OpenCode MCP Tools              docs/graph-intelligence.md
            (query, context, impact,        (Human-readable architecture)
             cypher, detect_changes,
             rename, route_map, etc.)
```

**WARUM zwei Layer?**
- GitNexus: Für AI Agents, die Code strukturell verstehen müssen (Call-Chains, Impact, Refactoring)
- Graphify: Für Menschen, die visuelle Reports und HTML-Dashboards brauchen
- Kein Konflikt: Beide arbeiten auf demselben Code, aber mit unterschiedlichen Datenmodellen

---

## 2. GITNEXUS — INSTALLATION & KONFIGURATION

### 2.1 Installation

```bash
# GitNexus CLI installieren (global)
npm install -g gitnexus@1.6.3

# ODER: npx (ohne globale Installation)
npx gitnexus@1.6.3 --version
```

**WARUM v1.6.3 (pinned)?**
- v1.6.x = stable API (keine Breaking Changes)
- v1.7+ = mögliche Schema-Änderungen
- NEVER `@latest` — breaking changes würden alle Queries brechen

### 2.2 Repository-Konfiguration (.gitnexus.yml)

```yaml
# JEDES Repo braucht .gitnexus.yml im Root
version: "1.0"

project:
  name: "stealth-runner"
  root: "."

output:
  path: ".gitnexus"          # Lokal, gitignored, privat

analysis:
  extract:
    imports: true             # Import-Beziehungen (WARUM? Dependency-Analyse)
    calls: true               # Aufruf-Beziehungen (WARUM? Call-Chain-Analyse)
    inheritance: true         # Vererbung (WARUM? OOP-Impact-Analyse)
    type_references: true     # Typ-Referenzen (WARUM? Type-Safety-Checks)
    dataflow: true            # Datenfluss (WARUM? Data-Impact-Analyse)
  max_file_size_kb: 2048      # WARUM 2048? Große Dateien >2MB = Graph-Dateien
  ignore:
    - "**/node_modules/**"    # Kein JS-Code im Python-Repo
    - "**/__pycache__/**"     # Bytecode
    - "**/.venv/**"           # Virtuelle Umgebung
    - "**/.git/**"            # Git-Interna
    - "**/graphify-out/**"    # graphify Output (WARUM? Endlos-Rekursion!)
    - "**/logs/**"            # Log-Dateien
    - "**/tests/**"           # Optional: Tests separat indexieren?

cache:
  enabled: true
  directory: ".gitnexus/cache"

strict: false                  # Non-strict = graceful bei Parse-Fehlern
```

### 2.3 Indexierung — WANN?

```bash
# PFLICHT: Nach JEDEM Commit der Code ändert
# Grund: Stale Index = falsche Queries = Agent trifft falsche Entscheidungen

# Re-Index nach Commit:
git commit -m "..." && gitnexus analyze --skip-agents-md

# ODER: Pre-Commit Hook (automatisch):
# .git/hooks/post-commit
#!/bin/sh
npx gitnexus@1.6.3 analyze --skip-agents-md --drop-embeddings --quiet &
```

**WARUM nicht bei jedem Save?**
- `gitnexus analyze` dauert 5-10s pro Repo
- Zu häufig = nervig beim Entwickeln
- Richtiger Zeitpunkt: Post-Commit (wenn der Code stabil ist)

**WARUM --skip-agents-md?**
- Ohne Flag überschreibt GitNexus AGENTS.md/CLAUDE.md
- → Custom Agent Instructions gehen verloren
- → IMMER --skip-agents-md verwenden

**WARUM --drop-embeddings?**
- Embeddings = Vector Search (teuer, langsam)
- Für strukturelle Queries (Call-Chains, Dependencies) nicht nötig
- Spart ~50% Build-Zeit

---

## 3. GITNEXUS — MCP TOOLS (16 Tools)

### 3.1 Vor jedem Code-Edit (PFLICHT)

```python
# VOR JEDEM Code-Edit → Impact-Analyse
# gitnexus_impact(target="function_name", direction="upstream")
# → WER ruft diese Funktion auf? (d=1: WILL BREAK)
# → WAS hängt indirekt davon ab? (d=2-3)
# → CRITICAL? HIGH? MEDIUM? LOW? Risk Assessment

# VOR Refactoring → Context + Impact
# gitnexus_context(name="ClassName") → 360° View
# gitnexus_impact(target="ClassName", direction="upstream") → Blast Radius

# VOR Rename → gitnexus_rename mit dry_run=true (Preview!)
# gitnexus_rename(symbol_name="old_name", new_name="new_name", dry_run=true)
```

### 3.2 Tool-Übersicht

| Tool | WANN nutzen | Beispiel |
|------|------------|----------|
| `gitnexus_query` | Code verstehen (Call-Chains) | `query("survey agent run_survey")` |
| `gitnexus_context` | 360° View eines Symbols | `context(name="SurveyAgent")` |
| `gitnexus_impact` | Blast Radius vor Änderung | `impact(target="execute", direction="upstream")` |
| `gitnexus_cypher` | Komplexe Graph-Queries | `MATCH (f)-[:CALLS]->(g) RETURN f.name` |
| `gitnexus_detect_changes` | Pre-Commit: was ist betroffen? | `detect_changes(scope="unstaged")` |
| `gitnexus_rename` | Sicheres Refactoring | `rename(symbol_name="old", new_name="new")` |
| `gitnexus_route_map` | API-Routen verstehen | `route_map(route="/api/surveys")` |
| `gitnexus_tool_map` | MCP-Tools verstehen | `tool_map(tool="survey_run")` |
| `gitnexus_shape_check` | API/Consumer Mismatch | `shape_check(route="/api/surveys")` |
| `gitnexus_api_impact` | API-Änderungsanalyse | `api_impact(route="/api/surveys")` |

### 3.3 Query Patterns (Best Practices)

```python
# PATTERN 1: Vor Refactoring → Impact
impact = gitnexus_impact(
    target="SurveyAgent.run_survey",
    direction="upstream",         # Wer ruft MICH auf?
    maxDepth=3,                   # Tiefe der Analyse
    relationTypes=["CALLS", "IMPORTS", "EXTENDS"]
)
# → d=1: survey-cli/survey.py, run_survey.py, tests/
# → RISK: HIGH (wenn d=1 mehr als 3 Callers)

# PATTERN 2: Debugging → Context + Cypher
context = gitnexus_context(name="auto_google_login")
cypher = gitnexus_cypher("""
    MATCH (f:Function)-[:CALLS]->(g:Function)
    WHERE f.name = 'auto_google_login'
    RETURN f.name, g.name, g.filePath
""")
# → Alle direkten Aufrufe von auto_google_login

# PATTERN 3: Pre-Commit → Detect Changes
changes = gitnexus_detect_changes(scope="unstaged")
# → Welche Prozesse sind betroffen?
# → Welche Module wurden geändert?
# → Risk Summary

# PATTERN 4: Cross-Repo → Group Query
# (Erfordert group_sync zuerst!)
results = gitnexus_query(
    repo="@stealth-suite",
    query="session management login",
    goal="find all login implementations across repos"
)
```

---

## 4. GRAPHIFY — VISUAL REPORTS

### 4.1 Pipeline

```
git commit → pre-commit hook → graphify rebuild → graphify-out/ aktualisiert

graphify-out/
├── .graphify_root          # Marker-Datei (32 bytes)
├── cache/                  # Build-Cache (schnellere Rebuilds)
├── graph.json              # Graph-Daten (5.2 MB — Maschinen-lesbar)
├── graph.html              # Interaktives HTML (4.0 MB — Mensch-lesbar)
└── GRAPH_REPORT.md         # Text-Report (200 KB — Agent-lesbar)
```

### 4.2 Auto-Rebuild (Pre-Commit Hook)

```bash
# .git/hooks/pre-commit (aktuell: NUR Semgrep!)
# SOLLTE auch graphify rebuild triggern:

#!/bin/sh
# 1. Semgrep Architecture Guard
echo "🔍 Semgrep Architecture Guard…"
semgrep --config=.semgrep_rules.yaml --error . 2>&1

# 2. graphify auto-rebuild (NEU!)
if command -v graphify &> /dev/null; then
    echo "📊 graphify rebuild…"
    graphify rebuild --quiet || echo "⚠️  graphify rebuild failed (non-blocking)"
fi
```

### 4.3 WANN graphify, WANN GitNexus?

| Scenario | Tool | Grund |
|----------|------|-------|
| "Wie ist die Architektur?" | graphify (graph.html) | Visuell, interaktiv, übersichtlich |
| "Wer ruft X auf?" | GitNexus (context) | Präzise Call-Chains, 360° View |
| "Was bricht wenn ich X ändere?" | GitNexus (impact) | Automatische Blast-Radius-Analyse |
| "Wie viele Module gibt es?" | graphify (GRAPH_REPORT.md) | Übersicht, Communities |
| "Zeig mir den Code von X" | GitNexus (context + include_content) | Direkter Code-Zugriff |
| "API Endpunkte" | GitNexus (route_map) | API-Consumer Mapping |
| "Repo-Landing-Page" | graphify (graph.html) | Schön für README |
| "Cross-Repo Query" | GitNexus (group query) | Multi-Repo strukturell |

---

## 5. AKTUELLER STATUS (2026-05-08)

### GitNexus

| Metrik | Wert | Status |
|--------|------|--------|
| **Repos indexiert** | 21 | ✅ |
| **stealth-runner nodes** | 11.739 | ✅ |
| **stealth-runner edges** | 14.337 | ✅ |
| **stealth-runner communities** | 126 | ✅ |
| **stealth-runner processes** | 106 | ✅ |
| **Index-Frische (stealth-runner)** | **40 commits behind** | 🔴 KRITISCH |
| **Index-Frische (alle anderen)** | 1 commit behind | 🟡 WARNUNG |
| **Queries funktionieren** | **Leer (Index zu alt)** | 🔴 KRITISCH |
| **CLI Binary** | **Nicht in PATH** | 🟡 WARNUNG |
| **MCP Server** | Aktiv (OpenCode) | ✅ |
| **Group Sync** | stealth-suite Gruppe existiert | ✅ |
| **Auto-Reindex** | **KEIN Post-Commit Hook** | 🔴 FEHLT |

### Graphify

| Metrik | Wert | Status |
|--------|------|--------|
| **graph.json** | 5.2 MB | ✅ |
| **graph.html** | 4.0 MB | ✅ |
| **GRAPH_REPORT.md** | 200 KB | ✅ |
| **Letzter Rebuild** | 2026-05-08 00:54 | ✅ |
| **Auto-Rebuild (Pre-Commit)** | **NUR Semgrep, kein graphify** | 🟡 WARNUNG |

---

## 6. SOFORT-MASSNAHMEN (Priorisiert)

### 🔴 P0 — JETZT

1. **GitNexus RE-INDEX von stealth-runner**
   ```bash
   npx gitnexus@1.6.3 analyze --drop-embeddings --skip-agents-md
   # → 40 commits catch-up → Queries werden wieder funktionieren
   ```
   WARUM: Ohne funktionierende Queries kann kein Agent Code strukturell verstehen. Impact-Analysen sind unmöglich.

2. **GitNexus in PATH installieren**
   ```bash
   npm install -g gitnexus@1.6.3
   which gitnexus  # → /usr/local/bin/gitnexus
   ```

### 🟡 P1 — Heute

3. **Post-Commit Hook für GitNexus Auto-Reindex**
   ```bash
   # .git/hooks/post-commit
   #!/bin/sh
   npx gitnexus@1.6.3 analyze --skip-agents-md --drop-embeddings --quiet &
   ```

4. **Pre-Commit Hook um graphify erweitern**
   ```bash
   # Zusätzlich zu Semgrep: graphify rebuild
   if command -v graphify &> /dev/null; then
       graphify rebuild --quiet &
   fi
   ```

5. **Group Sync für Cross-Repo Queries**
   ```bash
   npx gitnexus@1.6.3 group sync stealth-suite
   ```

### 🟢 P2 — Diese Woche

6. **Auto-Index in AGENTS.md dokumentieren** → Agent weiß, dass er vor Code-Änderungen `detect_changes` ausführen muss

7. **GitNexus Health Check in `survey.py doctor` integrieren**
   ```python
   # Prüft: Ist GitNexus Index aktuell? (meta.json vs HEAD)
   # Prüft: Sind Queries möglich? (test query)
   ```

---

## 7. INTEGRATION IN WORKFLOW

### Vor jedem Code-Edit

```python
# 1. GitNexus Index prüfen
staleness = check_gitnexus_staleness()
if staleness["commits_behind"] > 0:
    print(f"⚠️  GitNexus index is {staleness['commits_behind']} commits behind!")
    print("   Run: npx gitnexus@1.6.3 analyze --drop-embeddings --skip-agents-md")
    # OPTIONAL: Auto-reindex wenn weniger als 5 commits behind

# 2. Impact-Analyse (vor Änderung)
impact = gitnexus_impact(target="function_to_change", direction="upstream")
if impact["risk"] == "CRITICAL" or impact["risk"] == "HIGH":
    print(f"⚠️  HIGH RISK change — {len(impact['affectedCallers'])} callers affected")
    # Zeige betroffene Dateien an
```

### Nach jedem Commit

```python
# 1. Graphify Rebuild (automatisch via hook)
# 2. GitNexus Re-Index (automatisch via hook)
# 3. graphify-out/ committen (wenn Auto-Rebuild aktiv)
```

---

## 8. KNOWN ISSUES

### Issue 1: GitNexus Index Staleness (P0)
- **Symptom**: Queries return empty, `staleness: 40 commits behind`
- **Root Cause**: Kein Post-Commit Auto-Reindex
- **Fix**: Post-Commit Hook + manuelles Re-Index

### Issue 2: graphify Pre-Commit Hook fehlt
- **Symptom**: graph.html zeigt alten Stand
- **Root Cause**: Hook nur für Semgrep, kein graphify
- **Fix**: Hook erweitern

### Issue 3: GitNexus CLI nicht in PATH
- **Symptom**: `gitnexus: command not found`
- **Root Cause**: Nicht global installiert
- **Fix**: `npm install -g gitnexus@1.6.3`

---

*Letzte Aktualisierung: 2026-05-08*