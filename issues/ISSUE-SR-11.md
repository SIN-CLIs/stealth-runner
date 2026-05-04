# SR-11: ax-graph Swift CLI — Unified AX Indexer

- **Status:** ✅ COMPLETED (2026-05-04)
- **Priority:** 🔴 Critical
- **Repo:** [`SIN-CLIs/ax-graph`](https://github.com/SIN-CLIs/ax-graph)
- **Plan:** [`plans/plan-ax-graph.md`](../plans/plan-ax-graph.md)
- **Source:** Plane Wiki `chat verlauf mit agent 2`

## Description

Created a new Swift CLI `ax-graph` that combines all three AX sources (System-AX + Chrome-AX + CDP) into one unified graph with SHA256-stable node IDs and live mutation tracking.

## Deliverables

- [x] GitHub repo created: `SIN-CLIs/ax-graph`
- [x] `Package.swift` with ArgumentParser + Crypto dependencies
- [x] `main.swift` — CLI entry point with Snapshot/Watch/Resolve subcommands
- [x] `AXAttributes.swift` — Attribute reader (string, bool, point, size, children, actionNames)
- [x] `AXNode.swift` — Node struct + SHA256-based `NodeID.make()`
- [x] `AXTreeWalker.swift` — Recursive tree walker with depth limit + DOM attributes
- [x] `AppEnumerator.swift` — NSWorkspace-based app + window enumeration
- [x] `Snapshot.swift` — `ax-graph snapshot --all/--pid/--bundle`
- [x] `Watch.swift` — AXObserver-based live mutation streaming
- [x] `Resolve.swift` — `ax-graph resolve --node-id --press`
- [x] `.github/workflows/ci.yml` — Build + lint
- [x] `.swiftlint.yml`, `.gitignore`, `LICENSE` (MIT), `README.md` (with Stealth Suite table)

## Acceptance Criteria

- [x] Repo created and pushed to `SIN-CLIs/ax-graph`
- [x] Swift package compiles with `swift build -c release`
- [x] CI workflow builds on `macos-14` with Xcode 16.2
- [ ] Tested with real Chrome PID on local machine

## Files

- `/Users/jeremy/dev/ax-graph/` — local repo
- `https://github.com/SIN-CLIs/ax-graph` — GitHub
