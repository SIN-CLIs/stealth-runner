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
│  2. screen-follow record --video → Daueraufnahme       │
│     → Rolling Video Buffer für Omni Analyse            │
│                                                        │
│  3. LiveOmniMonitor (live_omni_monitor.py)             │
│     → Screenshot (schnell, 1-2 FPS)                    │
│     → Rolling Video Buffer (4s Clip, alle 5 Steps)     │
│     → SSE Streaming (tokenweise Antwort)               │
│     → NVIDIA NIM: integrate.api.nvidia.com/v1           │
│     → Model: nvidia/nemotron-3-nano-omni-30b-a3b      │
│                                                        │
│  4. skylight-cli click/type --element-index            │
│     → KEINE Mausbewegung, keine Koordinaten            │
│                                                        │
│  5. Graphify Knowledge Graph (6 Repos merged)          │
│     → 4.820 Nodes, 10.860 Edges, 284 Communities      │
│     → Auto-Rebuild via post-commit hooks               │
│                                                        │
│  6. Semgrep Architecture Guard                         │
│     → 11 Regeln, blockiert BANNED Muster im Commit     │
│                                                        │
│  7. Video-Analyse (post-mortem)                        │
│     → screen-follow Recording → Omni Video Analyse     │
│     → Fehler, Captcha, Flow-Erkennung                  │
└────────────────────────────────────────────────────────┘
```

## Wichtige Erkenntnisse

- Model-Name: `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` (OHNE doppeltes nvidia/)
- Omni schreibt Antwort ins `reasoning`-Feld, nicht `content` (wenn thinking enabled)
- SSE Streaming: `stream: true` + `Accept: text/event-stream` → tokenweise Antwort
- Rolling Video Buffer: screen-follow + ffmpeg + Omni Conv3D Analyse
- Google Login erfolgreich getestet (PID 11255): 5 Schritte, eingeloggt ✅
- skylight-cli `--output` wird ignoriert → schreibt immer nach `skylight_screenshot.png` im CWD
- semgrep blockiert BANNED Muster im pre-commit
- Graphify rebuild automatisch nach jedem Commit

## Credentials

- Google: Siehe `profiles/jeremy.yaml` (NICHT in Docs!)
- NVIDIA API Key: `$NVIDIA_API_KEY` (env var, Prefix: `nvapi-...`)
- Heypiggy Profil: `profiles/jeremy.yaml` (im .gitignore, nicht committed)

## Bugs gefixt

- [FIXED] Model-Name: `nvidia/nvidia/` → `nvidia/` (doppelter Prefix → 404)
- [FIXED] Omni reasoning-Feld Parsing (content ist null)
- [FIXED] SkylightDriver pid optional → TypeError vermieden
- [FIXED] vision_client/core.py dead code → YAML lädt jetzt korrekt
- [FIXED] cli/heypiggy-login: osascript entfernt, nur skylight-cli
- [KNOWN] skylight-cli --output Bug: ignoriert Pfad, schreibt ins CWD
