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
| LOGIN | `heypiggy_login_box.py` | Google OAuth (FLOW A/B) |
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
