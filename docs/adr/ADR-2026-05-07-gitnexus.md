# ADR-2026-05-07: GitNexus Code Intelligence Integration

**Status:** ACCEPTED (2026-05-07)  
**Scope:** All 21 Stealth Suite repositories  
**Drivers:** MCP-based code intelligence, structural querying, cross-repo impact analysis  

## Context
AI coding assistants (OpenCode, Claude Code, Cursor) lack structural code understanding.
They guess dependencies, miss call chains, and break things blind.
Stealth-runner already has `graphify` (static AST graph, HTML reports), but that is not
MCP-queryable and not live-synchronized with the codebase.

## Decision
Integrate GitNexus v1.6.3 as the code-intelligence layer across the entire Stealth Suite.

**Architecture:**
```
   GitNexus (Knowledge Graph, LadybugDB, MCP stdio)
          |
   OpenCode (via MCP — query/context/impact/cypher tools)
          |
   graphify (static visual reports — unchanged, coexists)
```

## Alternatives Considered
1. **DeepWiki** — cloud-hosted, code leaves machine. Rejected (privacy requirement).
2. **Repomix** — flattens code into text, no structural querying. Too shallow.
3. **Custom graph build** — would take months. GitNexus is production-ready.

## Scope
- 21 Stealth Suite repos indexed: 17.433 nodes, 23.816 edges, 336 clusters, 277 processes
- Multi-Repo Group `stealth-suite` with 11 core repos synced for cross-repo queries
- MCP server enabled globally in OpenCode config
- Local, private, zero-server architecture

## Configuration
- `.gitnexus.yml` in every repo root
- `.gitignore` updated with `.gitnexus/` in every repo
- Index stored locally in `repo/.gitnexus/` (gitignored)
- Global registry at `~/.gitnexus/registry.json`
- `--drop-embeddings` for faster indexing (vector search not needed for structural queries)
- `--skip-agents-md` to preserve custom AGENTS.md/CLAUDE.md files

## Tradeoffs
| Pro | Con |
|-----|-----|
| Structural code understanding via MCP | Incremental index build on first commit |
| Cross-repo queries via group sync | PolyForm Noncommercial license (enterprise needed for commercial use) |
| Local, private, zero-server | ~5-10s per `gitnexus analyze` run |
| ~24K edges, 336 clusters | Version must be pinned (`gitnexus@1.6.3`) |

## Consequences
1. OpenCode can now execute `query`, `context`, `impact`, `cypher`, `detect_changes`
2. Cross-repo queries: `group_query @stealth-suite "balance"` returns results from all repos
3. Pre-commit impact analysis: `detect_changes` before every commit
4. graphify pipeline unchanged — both layers coexist
