# 🧪 Testing, Mocks & pytest SOTA

## conftest.py Fixtures

- `config` — pydantic-settings Config
- `mock_cli_success` — AsyncMock für CLI-Calls
- `event_loop` — asyncio Loop

## Test-Strategie

- `pytest-asyncio` mit `asyncio_mode = "auto"`
- `AsyncMock` für CLI/LLM-Calls in Unit-Tests
- `hypothesis` für State-Machine Edge-Cases
- Replay-Fixtures für deterministische Vision-Tests
- Coverage ≥ 80%, `--cov-fail-under=80` in CI

## SOTA-Testing-Checkliste

- [ ] `pytest-asyncio` Mode auto
- [ ] AsyncMock für CLI/LLM
- [ ] conftest.py mit zentralen Fixtures
- [ ] Replay-Fixtures
- [ ] hypothesis für State Machine
- [ ] Coverage ≥ 80%
- [ ] Mock-Anti-Bot-Server für unmask-cli
- [ ] --dry-run Pfad getestet
