# brain.md - Aktueller Wissensstand (2026-05-01)

## Systemarchitektur (vollständig)

```
┌────────────────────────────────────────────────────────┐
│  ARCHITEKTUR                                           │
├────────────────────────────────────────────────────────┤
│                                                        │
│  1. playstealth launch → isolierte Chrome-Instanz      │
│     → eigene PID, kein Nutzer-Chrome                   │
│                                                        │
│  2. LiveOmniMonitor (live_omni_monitor.py)             │
│     → Screenshot (schnell, 1-2 FPS)                    │
│     → Rolling Video Buffer (4s Clip, alle 5 Steps)     │
│     → SSE Streaming (tokenweise Antwort)               │
│     → NVIDIA NIM: integrate.api.nvidia.com/v1           │
│     → Model: nvidia/nemotron-3-nano-omni-30b-a3b      │
│                                                        │
│  3. skylight-cli click/type --element-index            │
│     → KEINE Mausbewegung, keine Koordinaten            │
│                                                        │
│  4. Graphify Knowledge Graph (6 Repos merged)          │
│     → 4.820 Nodes, 10.860 Edges, 284 Communities      │
│     → Auto-Rebuild via post-commit hooks               │
│                                                        │
│  5. Semgrep Architecture Guard                         │
│     → 11 Regeln, blockiert BANNED Muster im Commit     │
│                                                        │
│  6. Video-Analyse (post-mortem)                        │
│     → screen-follow Recording → Omni Video Analyse     │
│     → Fehler, Captcha, Flow-Erkennung                  │
└────────────────────────────────────────────────────────┘
```

## Wichtige Erkenntnisse
- Model-Name: `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` (OHNE doppeltes nvidia/)
- SSE Streaming: `stream: true` + `Accept: text/event-stream` → tokenweise Antwort
- Rolling Video Buffer: screen-follow + ffmpeg + Omni Conv3D Analyse
- semgrep blockiert BANNED Muster im pre-commit
- Graphify rebuild automatisch nach jedem Commit

## Credentials
- Google: zukunftsorientierte.energie@gmail.com / ZOE.jerry2024
- NVIDIA API Key: nvapi-... (Prefix)
- Heypiggy Profil: profiles/jeremy.yaml

## Bugs gefixt
- [FIXED] Model-Name: `nvidia/nvidia/` → `nvidia/` (doppelter Prefix → 404)
- [FIXED] SkylightDriver pid optional → TypeError vermieden
- [FIXED] vision_client/core.py dead code → YAML lädt jetzt korrekt
- [FIXED] cli/heypiggy-login: osascript entfernt, nur skylight-cli
