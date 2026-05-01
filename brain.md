# brain.md - Aktueller Wissensstand (2026-05-01)

## TRIO LAYER: Live Auge-Hirn-Hand System

```
┌──────────────────────────────────────────────────────────────┐
│                    TRIO LAYER v2                             │
│                                                              │
│  EYES (250ms Polling)                                        │
│  ├─ cua-driver list_windows → ALLE Fenster erkennen         │
│  ├─ Popup-Detektion: "Anmelden – Google Konten" (WID=30380)│
│  └─ OnScreen-Flag: Nur sichtbare Fenster                    │
│                                                              │
│  BRAIN (5-15ms Analyse)                                      │
│  ├─ cua-driver get_window_state --pid --window-id            │
│  ├─ → NUR Elemente im POPUP (nicht auf Hauptseite!)         │
│  └─ Omni analysiert + entscheidet nächste Aktion             │
│                                                              │
│  HANDS (2-5ms Ausführung)                                    │
│  ├─ cua-driver click --pid --window-id --element-index       │
│  ├─ → GARANTIERT im richtigen Fenster                        │
│  └─ Kein Koordinatenraten, kein Apple-Menü-Risiko            │
└──────────────────────────────────────────────────────────────┘
```

## Wichtige Erkenntnisse
- **cua-driver** hat `get_window_state` mit `--window-id` → zeigt NUR Elemente im Popup
- **`click --pid --window-id --element-index`** → klickt GARANTIERT im richtigen Fenster
- **Alter Bug**: skylight-cli hat kein `--window-id`, findet "Weiter" auf der FALSCHEN Seite
- **TriO Loop**: 250ms Polling = live wie menschliches Auge
- cua-driver ist KEIN Koordinaten-Tool mehr (hat element_index + window_id)

## Credentials
- Google: Siehe `profiles/jeremy.yaml` (NICHT in Docs!)
- NVIDIA API Key: `$NVIDIA_API_KEY` (env var, Prefix: `nvapi-...`)
- Heypiggy Profil: `profiles/jeremy.yaml` (im .gitignore, nicht committed)
