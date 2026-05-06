# ISSUE-SR-37: skylight-cli — Compact Snapshot + Find + Batch Commands

| Feld | Wert |
|------|------|
| **ID** | SR-37 |
| **Priority** | 🔴 P0 — Critical |
| **Status** | 📋 TODO (needs separate Swift repo) |
| **Created** | 2026-05-06 |
| **Labels** | `skylight`, `swift`, `snapshot`, `batch` |
| **Plan** | `plan-sr-37-skylight-compact.md` |

## Problem
`skylight-cli` ist aktuell deprecated (CUA-ONLY Ära). Die Next-Gen Architektur braucht es als PRIMARY Interaction Tool mit drei neuen Commands für den compact-batch NIM-Loop.

## Ziel
Swift-Erweiterungen für `skylight-cli`:

### 1. `snapshot-compact` Command
```
skylight-cli snapshot-compact --pid X --semantic
→ JSON mit @eN Refs, semantic grouping, progress, provider detection
```

### 2. `find` Command
```
skylight-cli find --role button --text "Weiter" --label "..."
→ @e42  (compact element reference)
```

### 3. `batch` Command
```
skylight-cli batch '[{"ref":"@e42","action":"click"},{"ref":"@e15","action":"fill","value":"32"}]'
→ [{"ref":"@e42","success":true},...]
```

## Subissues

### SR-37.1 — Compact Snapshot Generator (Swift)
- `CompactSnapshotCommand.swift` — Hauptbefehl
- `AXElementExtractor.swift` — Extrahiert interaktive Elemente aus AX-Tree
- `@eN`-Referenzierung mit sequenziellen Indices
- Semantic grouping: questions, buttons, progress
- Provider-Detektion aus Window-Title + URL
- Stealth-Score von `unmask-cli` integrieren

### SR-37.2 — Semantic Finder (Swift)
- `FindCommand.swift` — `--role`, `--text`, `--label` Flags
- Priorisierte Suche: role → visible text → label → fallback
- Gibt `@eN` Referenz zurück (z.B. `@e42`)

### SR-37.3 — Batch Executor (Swift)
- `BatchCommand.swift` — Nimmt JSON-Array von Actions
- Atomare Ausführung mit unmask/playstealth Checks
- Action-Types: click, fill, select, check, wait, submit
- Results-Array mit per-action success/error
- Auto-Incident-Logging bei Errors

### SR-37.4 — Package Integration
- `Package.swift` Update — neue Targets
- `main.swift` — neue Subcommands registrieren
- `CLI_REFERENCE.md` — Dokumentation
- Tests: `CompactSnapshotTests.swift`, `BatchCommandTests.swift`

## Acceptance Criteria
- [ ] `skylight-cli snapshot-compact --pid X` gibt JSON mit @eN refs
- [ ] `skylight-cli find --role button --text "Weiter"` gibt @e42
- [ ] `skylight-cli batch '[{"ref":"@e42","action":"click"}]'` führt aus
- [ ] Semantic grouping erkennt Questions, Buttons, Progress
- [ ] Performance: Snapshot < 200ms, Batch < 50ms pro Action

## Technische Notizen
- Swift Package in `Sources/skylight-cli/Commands/`
- AX API: `AXUIElementCopyAttributeValue`, `AXUIElementPerformAction`
- JSON: `Foundation.JSONEncoder` mit `.sortedKeys`
- Tests: `XCTest` mit Mock-AX-Elementen

## Dependencies
- `stealth-runner` (SR-28: SurveyAgent nutzt diese Commands)
- `unmask-cli` (Stealth-Score)
- `playstealth-cli` (Chrome Launch)
