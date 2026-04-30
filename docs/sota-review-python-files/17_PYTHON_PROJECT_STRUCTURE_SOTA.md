# 📦 Python-Dateistruktur & Modul-Architektur SOTA (Python 3.12+)
_Abgestimmt auf stealth-runner: 9-State ASM, CLI-Triade, Vision-First, Audit-Log_

## 🗂️ Empfohlenes `src/`-Layout (SOTA-Standard)
```
stealth-runner/
├── src/stealth_runner/
│   ├── __init__.py, __main__.py, config.py
│   ├── state_machine.py, executor.py, vision_client.py
│   ├── audit_logger.py, unmask_verifier.py
│   ├── drivers/{base.py, skylight.py}
│   └── utils/{async_helpers.py, crypto.py}
├── tests/{unit/, integration/, replay/, mocks/}
└── docs/
```

## 🔑 SOTA-Prinzipien
| Prinzip | Umsetzung |
|---------|-----------|
| `src/`-Layout | Vermeidet `sys.path`-Konflikte |
| Explicit Imports | `__all__` pro Modul, absolute imports |
| Type-First | PEP 484 + PEP 695, `mypy --strict` |
| Async-Native | `asyncio` durchgängig, `TaskGroup` |
| CLI-Isolation | Subprocess-Wrapper mit Timeout + Exit-Code-Mapping |
| Config-Driven | `pydantic-settings` + YAML, keine Hardcoded-Values |
| Error Classification | Custom Exceptions, keine Bare `except` |
| Audit-First | JSONL mit `O_SYNC`, Correlation-ID |
