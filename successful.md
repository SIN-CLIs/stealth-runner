# successful.md – Was funktioniert (SOTA 2026-05-01)

## Core-Loop

1. Browser starten → `playstealth-cli launch` ✅
2. Screenshot mit SoM → `skylight-cli screenshot --mode som` ✅
3. Vision-Entscheidung → Nemotron 3 Nano Omni (`reasoning`-Feld) ✅
4. Unsichtbarer Klick → AXPress via `skylight-cli click --element-index` ✅
5. SSE Streaming → `stream: true` + `Accept: text/event-stream` ✅
6. Rolling Video Buffer → screen-follow + ffmpeg + Omni Conv3D ✅
7. Stealth-Verifikation → `unmask-cli verify-stealth` ✅

## Google Login (vollständig automatisiert)

1. `playstealth launch --url 'https://heypiggy.com/?page=dashboard'` → PID
2. Google Login-Symbol klicken (Index variiert)
3. E-Mail eingeben (EMAIL (ENTFERNT – siehe profiles/))
4. Weiter klicken (Google prüft E-Mail)
5. Passwort eingeben (ZOE.jerry2024)
6. Weiter klicken (Google prüft Passwort)
7. Weiter klicken (Google Bestätigung)
8. ✅ Eingeloggt auf heypiggy.com Dashboard

## Architektur

- State Machine mit 10 Zuständen ✅
- Checkpoint-Resume nach Crash ✅
- Human-Profile (scipy.stats PDFs) ✅
- Temp-Profile pro Session ✅
- Graphify Knowledge Graph (6 Repos merged) ✅
- Semgrep Architecture Guard (11 Regeln) ✅
- screen-follow Video Recording (Daueraufnahme) ✅

## Vision

- **Modell**: `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`
- **API**: `POST https://integrate.api.nvidia.com/v1/chat/completions`
- **Modi**: Screenshot (schnell) + Rolling Video (temporal, Conv3D)
- **SSE**: `stream: true` → tokenweise Antwort
- **Parsing**: `msg.get("reasoning") or msg.get("content") or ""`

## Knowledge Graph (Graphify)

- 4.820 Nodes, 10.860 Edges, 284 Communities
- 6 Repos → 1 Merged Graph
- Auto-Rebuild via post-commit hooks

## NICHT funktionierend

- DOM-Prescan (ENTFERNT – klickte blind Element 1)
- `CGEventPostToPid` (TOT auf Chrome 148)
- skylight-cli MCP (BANNED – Profil-Konflikt)
- playstealth launch (isolierte PID))
- openai-Client (BANNED – nur NVIDIA NIM httpx)
