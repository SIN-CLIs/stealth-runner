# architecture.md – CUA-ONLY STACK + Survey Flow

## 2026-05-04: Aktuelle Architektur

### Survey Flow (In-Page Pattern)
```
heypiggy Dashboard
  │
  ├── clickSurvey(id) → CDP JS
  │   └── fetch zu live-api.cpx-research.com
  │       ├── type="okay"   → showTypeOkay()   → Modal/Dashboard Overlay
  │       ├── type="question" → showTypeQuestion() → Frage in Seite
  │       └── type="not_okay" → disqualifiziert, nächster Survey
  │
  ├── AX-Tree rescanen (KEIN neuer Tab!)
  │   ├── "Umfrage starten" Button → klicken → neuer Tab (Samplicio.us/Cint/Toluna)
  │   ├── "Starten" / ">>" → klicken → Fragen beantworten
  │   └── Fragen (ARIA radio, input, checkbox) → Persona-Antworten
  │
  └── Survey complete → zurück zu Dashboard → nächster Survey
```

### Module Stack (2026-05-04)

| Layer | Tool | Zweck |
|-------|------|-------|
| LAUNCH | `playstealth` | Chrome starten |
| LOGIN | CUA-only (7 Steps) | Google OAuth via macOS Keychain |
| SURVEY | `survey_runner.py` | Survey Start + Antworten |
| AUDIO | `audio_box.py` | BlackHole + ffmpeg + Omni |
| CUA | `cua-driver` | AX-Interaktionen |
| CDP | WebSocket JS | DOM lesen + JS klicken |

### Wichtige Regeln
1. Nach clickSurvey() NIEMALS nach neuen Tabs suchen → AX-Tree rescanen!
2. Survey erscheint IN-PAGE im Dashboard (showTypeOkay/Question)
3. Nach "Umfrage starten" Klick → neuer Tab mit Provider
4. Provider-Tab: Consent → Fragen → Complete/Disqual

## 2026-05-02: Architecture Scan (Legacy)

**Komponenten (15 Module):**

- `./` (4 Python Dateien)
- `.opencode/plugins/` (0 Python Dateien)
- `.venv/bin/` (1 Python Dateien)
- `.venv/lib/python3.12/site-packages/` (1 Python Dateien)
- `runner/` (38 Python Dateien)
- `runner/drivers/` (5 Python Dateien)
- `runner/vision_client/` (3 Python Dateien)
- `sin_survey_core/` (1 Python Dateien)
- `sin_survey_core/errors/` (2 Python Dateien)
- `sin_survey_core/panels/` (2 Python Dateien)

**Sprachen:** TypeScript, JSON, JavaScript, Markdown, Python

**Total Dateien:** 2689

## Live Auge-Hirn-Hand Architektur

```
                    ╔══════════════════════╗
                    ║   TRIO LAYER v2     ║
                    ║  250ms Live-Zyklus  ║
                    ╚══════════════════════╝
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
      ┌─────────────┐ ┌──────────┐ ┌──────────────┐
      │   EYES      │ │  BRAIN   │ │   HANDS      │
      │ list_windows│ │ get_win  │ │ click        │
      │ Popup-Erkenn│ │ _state   │ │ set_value    │
      │ .25s Polling│ │ Omni     │ │ 5ms Execute  │
      └─────────────┘ └──────────┘ └──────────────┘
              │             │             │
              ▼             ▼             ▼
      ┌──────────────────────────────────────────┐
      │           skylight-cli (macOS)             │
      │  list_windows | get_window_state | click  │
      │  mit --pid --window-id --element-index   │
      └──────────────────────────────────────────┘
              │
              ▼
      ┌──────────────────────────────────────────┐
      │           playstealth Chrome             │
      │  Isolierte Instanz, eigene PID           │
      │  Heypiggy.com + Google Login Popup       │
      └──────────────────────────────────────────┘
```

## Fenster-Isolation

```
PID 42296 (playstealth Chrome):
├── WindowID=30380  "Anmelden – Google Konten"   ← Popup
│   └── get_window_state → "Weiter" Index 35     ← RICHTIG
│
└── WindowID=30364  "HeyPiggy – Verdienen..."    ← Hauptseite
    └── get_window_state → "Weiter" Index 39     ← FALSCH (aber früher geklickt!)
```

## Tools

| Layer  | Tool          | Befehl                                                |
| ------ | ------------- | ----------------------------------------------------- |
| EYES   | skylight-cli  | `list_windows' -- 250ms Polling                       |
| BRAIN  | skylight-cli  | `get_window_state --pid --window-id`                  |
| BRAIN  | Nemotron Omni | `POST https://integrate.api.nvidia.com/v1`            |
| HANDS  | skylight-cli  | `click --pid --window-id --element-index`             |
| LAUNCH | playstealth   | `launch --url 'https://heypiggy.com/?page=dashboard'` |


## Architecture Decision Records (ADRs)

### ADR-001: Tiered Cloud Provider Strategy

**Status:** Accepted ✅
**Date:** 2026-05-04

The OpenSIN/sincode stealth-runner platform adopts a tiered cloud provider strategy:

- **Tier 1 (AI Vision):** NVIDIA NIM (`nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`)
  - Single API for Video+Audio+Image+Text
  - 256K context, 30B-A3B MoE architecture
  - Cost: $0.50 per 1M tokens

- **Tier 2 (Orchestration):** OpenCode Stack (self-hosted)
  - Python state machines, Redis, Diskcache
  - CUA-ONLY Trinity architecture (no CDP, no user Chrome)
  - Cost: ~$50/month (amortized)

- **Tier 3 (Optional):** Antigravity/Cloudflare
  - Image generation and CDN services
  - Pay-as-you-go model

**Rationale:** Balances performance, cost, and reliability while maintaining CUA-ONLY principles.

**Document:** [docs/architecture/adr-001-cloud-provider-strategy.md](docs/architecture/adr-001-cloud-provider-strategy.md)

---

**See Also:**
- [CUA-ONLY Trinity Architecture](brain.md)
- [AGENTS.md: Architecture Guard](AGENTS.md)

## 2026-05-04: stealth-session Architektur

```
OpenCode LLM → stealth-exec
    │
    ▼
┌──────────────────────────────────┐
│  stealth-session Daemon          │
│  (Unix-Socket, /tmp/stealth-     │
│   session.sock)                  │
│                                  │
│  1. IdiotProofGuard              │
│     → 8 Schutzmuster            │
│     → Blockiert/Repariert       │
│                                  │
│  2. WarmExecutor                 │
│     → CUA-Only, <50ms           │
│     → Auto PID/WID aus Cache    │
│                                  │
│  3. Verify-Box                   │
│     → Prüft nach jedem Klick    │
│     → selected? checked? wert?   │
│                                  │
│  4. WindowManager                │
│     → CDP Target-Domain         │
│     → Trackt Popups in Echtzeit │
│                                  │
│  5. SessionWatchdog              │
│     → Chrome mit accessibility  │
│     → Auto-Neustart bei Crash   │
└──────────────────────────────────┘
```
