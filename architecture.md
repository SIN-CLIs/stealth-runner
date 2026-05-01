# architecture.md – TRIO LAYER

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
      │           cua-driver (macOS)             │
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
| Layer | Tool | Befehl |
|-------|------|--------|
| EYES | cua-driver | `list_windows' -- 250ms Polling |
| BRAIN | cua-driver | `get_window_state --pid --window-id` |
| BRAIN | Nemotron Omni | `POST https://integrate.api.nvidia.com/v1` |
| HANDS | cua-driver | `click --pid --window-id --element-index` |
| LAUNCH | playstealth | `launch --url 'https://heypiggy.com/?page=dashboard'` |
