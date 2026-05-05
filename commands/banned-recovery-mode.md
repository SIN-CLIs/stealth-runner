# DEPRECATED: RECOVERY_MODE (YAML Config) ⚠️

## Status
**DEPRECATED** — 2026-05-05

## Wichtig: Zwei verschiedene Dinge!

| Konzept | Beschreibung |
|---------|-------------|
| `recovery_mode: true` (YAML) | **DEPRECATED** — some config option (siehe unten) |
| macOS Recovery Mode (`csrutil disable`) | **VERIFIED SECRET WAY** → `/commands/macos-recovery-mode.md` |

Das YAML `recovery_mode: true` ist ANDERS als macOS Recovery Mode!

## Über dieses File
Dieses File Dokumentiert den YAML Config-Wert `recovery_mode: true`.
Dieser ist in manchen Kontexten deprecated aber hat NICHTS mit macOS Recovery Mode zu tun.

## Falls du `recovery_mode: true` siehst
```yaml
# Alt / deprecated:
recovery_mode: true

# Richtig: Nemotron Primary
current_model: nvidia/nemotron-3-nano-omni-30b-a3b-reasoning
```

## Für macOS Recovery Mode (SIP deaktivieren)
→ **SIEHE: `/commands/macos-recovery-mode.md`**

Dort ist der wahre "Secret Way" dokumentiert:
- `csrutil disable` in Recovery Mode
- Accessibility API freischalten
- Chrome-UI-Steuerung ermöglichen