# architecture.md — stealth-runner v2.0

## Systemübersicht
```
playstealth-cli (launch) → skylight-cli (screenshot+click) → Llama 4 Scout (vision) → unmask-cli (verify)
```

## State Machine (10 Zustände)
```
IDLE → LAUNCH_BROWSER → WAIT_READY → CAPTURE → VISION → EXECUTE → VERIFY → DONE
                                                                    ↘ RECOVERY
```

## Datenfluss pro Aktion
1. CAPTURE: `skylight-cli screenshot --mode som` → PNG mit Element-IDs
2. VISION: `VisionClient.get_action(image, prompt)` → JSON `{"action":"click","element_id":N}`
3. EXECUTE: `skylight-cli click --element-index N` → CGEventPostToPid
4. VERIFY: `unmask-cli verify-stealth` → detected: true/false

## Projektstruktur
```
stealth-runner/
├── runner/
│   ├── stealth_executor.py   (CLI Bridge — only skylight-cli)
│   ├── state_machine.py      (10-state orchestrator)
│   ├── vision_client.py      (Llama 4 Scout via Cloudflare)
│   ├── prompt_kit.py         (SYSTEM_PROMPT, 1742 chars)
│   ├── human_profile.py      (Jitter, Bezier, Typing)
│   └── audit_log.py          (JSONL trace)
├── sin_survey_core/
│   ├── panels/detectors.py   (8 Panel-Provider)
│   ├── rewards/extractor.py  (EUR-Parsing)
│   └── errors/templates.py   (DQ-Klassifikation)
├── tests/
├── 8 md files (docs)
└── main.py
```
