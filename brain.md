# brain.md – Zentrales Gedächtnis des stealth-runner v2.0

## 1. Ziel
Vollautomatisches, unsichtbares Ausfüllen von Webumfragen mit maximaler Tarnung.

## 2. Architektur (final)
- Greenfield-Neubau als `stealth-runner`
- Stealth-Triade: `playstealth-cli` · `skylight-cli` · `unmask-cli`
- Alter `A2A-SIN-Worker-heypiggy` archiviert

## 3. Kernmodule (alle in `runner/`)
| Modul | Zweck |
|-------|-------|
| `state_machine.py` | 10-Zustands-Orchestrator (SurveyRunner) |
| `stealth_executor.py` | Zustandslose CLI-Bridge |
| `vision_client.py` | Cloudflare + NVIDIA Vision-API |
| `vision_models.py` | Pydantic V2 Validierung |
| `prompt_kit.py` | SYSTEM_PROMPT + Prompt-Builder |
| `human_profile.py` | Realistische Verhaltensparameter |
| `audit_log.py` | Thread-sicheres JSONL-Log |
| `resilience.py` | Retry, Circuit Breaker, Shutdown |
| `logging_config.py` | structlog + Correlation-IDs |
| `survey_queue.py` | SQLite-Queue für parallele Instanzen |
| `config.py` | dotenv-Loader + Validierung |

## 4. Verbote
- ❌ cua-driver · open -na Chrome · AXStaticText klicken · CDP/DOM · Cursor-Stealing

## 5. Nächste SOTA-Aufgaben
- [ ] Semantic Caching · OpenTelemetry · Dry-Run/Replay · Cross-Platform
