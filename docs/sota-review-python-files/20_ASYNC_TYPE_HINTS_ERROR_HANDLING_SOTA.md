# ⚡ Async, Type Hints & Error Handling SOTA (Python 3.12+)

## PEP 695 Type Aliases
```python
type StateHandler = Callable[[dict], Awaitable[None]]
type CLIResponse = dict[str, str | int | float | bool | None]
type VisionAction = Literal["click","type","scroll","drag","wait","captcha","noop"]
```

## Async Best Practices
- `asyncio.TaskGroup` für parallele Tasks
- `asyncio.wait_for(coro, timeout=...)` mit Cancellation
- Keine `time.sleep()`, `requests.get()`, `subprocess.run()` im Event-Loop
- `async with` / `try...finally` für Cleanup

## Error Hierarchy
```
StealthRunnerError
├── RetryableError
│   ├── VisionConfidenceError
│   └── CLITimeoutError
├── FatalError
│   └── CLIExitError
└── StealthDegradedError
```

## Match/Case State Routing
```python
match ctx.get("verify_status"):
    case "pass": ctx["next_state"] = "CAPTURE"
    case "fail_soft": ctx["next_state"] = "RECOVERY"
    case "fail_hard": ctx["next_state"] = "DONE"
```
