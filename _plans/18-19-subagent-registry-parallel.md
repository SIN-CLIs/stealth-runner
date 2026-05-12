# Plan: Issues #18 + #19 — Subagent Registry + Parallel Execution

> Temporary planning file. **DELETE in the same PR that closes both #18 and #19.**
> Tracked together because the registry (#19) is a prerequisite for principled parallel execution (#18).

## #19 — Subagent Registry (do first)
- [ ] Create `survey-cli/survey/agents/registry.py` with `register_agent(name, fn, *, blocking, est_ms)` decorator
- [ ] Migrate existing hardcoded imports (`cookie_modal`, `audio_box`, `stealth_captcha`, `vision_gate`, `logic_module`) into registered agents
- [ ] CLI: `survey agents list` shows registered agents with timing class
- [ ] Config: env var `STEALTH_DISABLED_AGENTS` to skip agents at runtime
- [ ] Test: mock registration + lookup

## #18 — Parallel Execution (depends on #19)
- [ ] Add `survey-cli/survey/agents/executor.py` with `run_parallel(agents, *, timeout)`
- [ ] Classify each agent: `fast` (<1s), `medium` (~2s), `slow` (≥5s)
- [ ] Strategy: launch all non-blocking agents concurrently via `asyncio.gather`, gather results with per-agent timeout
- [ ] Preserve current blocking semantics where order matters (consent → captcha → audio)
- [ ] Test: 5-agent fixture with deterministic latencies → assert wall-time ≈ slowest agent, not sum

## Agent timing model (from issue body)
| Agent | Class |
|-------|-------|
| `vision_gate` | fast (<1s) |
| `audio_box` | slow (6s+) |
| `cookie_modal` | medium (~2s) |
| `stealth_captcha` | slow (10-30s) |
| `logic_module` | fast (<1s) |

## Acceptance Criteria
- `survey agents list` returns the migrated agents
- Parallel run completes in ≈ max(agent_time), not sum
- Existing sequential ordering preserved where mandated by survey flow

## Files Affected
- `survey-cli/survey/agents/registry.py` (new)
- `survey-cli/survey/agents/executor.py` (new)
- `survey-cli/survey_runner.py` (refactor imports → registry lookups)
- Tests in `tests/test_agent_registry.py`, `tests/test_agent_executor.py`

## Cleanup
After both issues closed: `git rm _plans/18-19-subagent-registry-parallel.md`.
