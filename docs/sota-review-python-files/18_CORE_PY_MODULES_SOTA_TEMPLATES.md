# 🧩 Core `.py` Module SOTA-Templates (Python 3.12+)

## 1. config.py — Strict Configuration (pydantic-settings)

- `StealthConfig(BaseSettings)` mit `env_file=".env"`, `extra="forbid"`
- Felder: cf_account_id, cf_api_token, vision_model, timeout, dry_run

## 2. state_machine.py — Async 9-State ASM + Recovery

- `State(StrEnum)`: IDLE→LAUNCH→WAIT→CAPTURE→VISION→EXECUTE→VERIFY→RECOVERY→DONE
- `Transition(source, target, handler, on_error)` Dataclass
- `AsyncStateMachine` mit `asyncio.Lock`, `add_transition()`, `run(ctx)`

## 3. executor.py — CLI Orchestrierung (asyncio + JSONL)

- `run_cli_atomic(cmd, timeout)` mit `asyncio.create_subprocess_exec`
- Exit-Code-Mapping: 0=OK, 1=Retryable, 2+=Fatal
- `RetryableCLIError`, `FatalCLIError`

## 4. vision_client.py — Structured Output + Retry + Cache

- `VisionDecision(BaseModel)`: action, target_element_id, confidence, reasoning
- `tenacity` Retry mit `wait_exponential`
- `diskcache` für Semantic Caching, SHA256-basierte Cache-Keys

## 5. audit_logger.py — Crash-Safe JSONL + Correlation ID

- `os.open(O_SYNC)`, `fcntl.flock(LOCK_EX)`, atomare Writes
- `session_id` pro Survey-Durchlauf, `ts` ISO8601
