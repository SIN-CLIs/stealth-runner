# Plan: Issue #20 — ADR-001 Cloud Provider Decision Record

> Temporary planning file. **DELETE in the same PR that closes #20.**

## Goal
Per A9 (no separate doc files), the ADR text is embedded into AGENTS.md under a new section `## ADR-001 — Tiered Cloud Strategy` immediately under OPERATIONAL RULES.

## Content (verbatim from issue #20, condensed)
- **Tier 1 — Primary AI**: NVIDIA NIM (`nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`) for vision/audio/multi-modal
- **Tier 2 — AI Gateway** (Vercel) for general LLM tasks (`openai/gpt-5-mini` zero-config)
- **Tier 3 — Infrastructure**: existing Infra-OpenCode-Stack via Plane.so
- **Tier 4 — Image gen**: Antigravity if/when needed; fal/Vercel AI Gateway as alternatives
- **Cloudflare**: only for Tunnel/Workers when explicitly required, not for new app traffic
- **GCP**: not used unless a feature requires Vertex AI exclusively

## Implementation Checklist
- [ ] Append `ADR-001 — Tiered Cloud Strategy` section to AGENTS.md (under OPERATIONAL RULES)
- [ ] Include the Tier table + rationale (~30 lines)
- [ ] Update STATUS INDEX: #20 → DONE
- [ ] No new MD file is created (per A9)

## Acceptance Criteria
- ADR section exists in AGENTS.md
- Every future cloud-provider decision references this section by name

## Cleanup
After PR merge: `git rm _plans/20-adr-cloud-provider.md`.
