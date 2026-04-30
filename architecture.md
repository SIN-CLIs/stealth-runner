# architecture.md — stealth-runner

## Systemübersicht

```
┌─────────────────────────────────────────────────┐
│                   stealth-runner                 │
│     State Machine  ◄──  Vision Client (Llama)    │
│          │                                       │
│     StealthExecutor                              │
│     ┌────┴────┬───────────┬──────────┐          │
│     ▼         ▼           ▼          ▼          │
│   play      unmask     skylight    sin_survey   │
│  stealth     -cli        -cli       _core       │
│   -cli                                          │
└─────────────────────────────────────────────────┘
```

## Zustandsdiagramm

```
IDLE → CAPTURE → VISION → EXECUTE → VERIFY → (loop) → DONE
```

## Datenfluss einer Aktion

1. **CAPTURE**: `skylight-cli screenshot --mode som` → `{"status":"ok","file":"step_N.png"}`
2. **VISION**: `VisionClient.analyze(screenshot, session)` → `{"action":"click","element_id":N}`
3. **EXECUTE**: `StealthExecutor.click(element_id=N)` → `skylight-cli click --element-index N`
4. **VERIFY**: `unmask-cli verify-stealth` → `{"status":"ok","detected":false}`

## Recovery-Strategie

- Crash → State aus `~/.stealth_runner/state.json` wiederherstellen
- Bot-Detektion → `playstealth-cli rotate-profile`
- Vision-Fehler → Grid-Mode Fallback

## Projektstruktur

```
stealth-runner/
├── runner/
│   ├── state_machine.py
│   ├── stealth_executor.py
│   ├── vision_client.py
│   ├── human_profile.py
│   └── audit_log.py
├── sin_survey_core/
│   ├── panels/detectors.py
│   ├── rewards/extractor.py
│   └── errors/templates.py
├── main.py
├── AGENTS.md
├── brain.md
└── architecture.md
```
