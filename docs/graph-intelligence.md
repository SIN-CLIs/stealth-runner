# Graph Intelligence: GitNexus × graphify Coexistence

> **Version:** 1.0 | **Date:** 2026-05-07

## The Two Layers

| Aspect | graphify | GitNexus |
|--------|----------|----------|
| **Purpose** | Static visual repo graph, community report, HTML dashboard | MCP-queryable knowledge graph for AI agents |
| **Storage** | `graphify-out/` (committed, tracked) | `.gitnexus/` (local, gitignored) |
| **Trigger** | Git pre-commit hook (auto-rebuild) | Manual `npx gitnexus analyze` |
| **Query Interface** | Static HTML/JSON file | MCP stdio server (16 tools) |
| **Scope** | Single repo per run | Multi-repo groups (11 repos in `stealth-suite`) |
| **Relationship Types** | AST structure + communities | Calls, imports, extends, implements, processes, routes, tools |
| **Consumer** | Human reader (graph.html) | AI agent (OpenCode via MCP) |

## Usage Rules

### When to use graphify
- Documentation updates (auto-rebuild on commit)
- Human-readable architecture reports
- Repository landing page README integration

### When to use GitNexus
- AI agent code understanding (query/context/impact)
- Before every significant code change (impact analysis)
- Cross-repo dependency tracking (group sync)
- Refactoring planning (rename tool)
- Pre-commit blast radius check (detect_changes)

### Conflict Rules
1. **NEVER** commit `.gitnexus/` — it's gitignored everywhere
2. **NEVER** run `gitnexus analyze --skills` — it may overwrite `.claude/skills/` custom skills
3. **ALWAYS** use `--skip-agents-md` to preserve AGENTS.md/CLAUDE.md
4. **ALWAYS** pin version: `gitnexus@1.6.3` (not `latest`)
5. Both can run on the same repo simultaneously — no data conflict
