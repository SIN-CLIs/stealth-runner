# MACOS RECOVERY MODE — SECRET WAY 🔒

## Status
**VERIFIED** — 2026-05-03, BRAIN.md (A2A-SIN-Worker-heypiggy)

## Was es ist
macOS Recovery Mode = Boot in spezielle System-Umgebung um **SIP zu deaktivieren**.
SIP = System Integrity Protection (schützt macOS vor Code-Injection).

## Warum WICHTIG?
```
macOS Requirement: Accessibility (Bedienungshilfen) Permission + 
SIP disabled (via Recovery Mode `csrutil disable`)

→ Ohne SIP-Disabling: Accessibility API (AXPress, cua-driver) funktioniert NICHT!
→ Mit SIP-Disabling: cua-driver kann Chrome-UI direkt steuern!
```

## Command: SIP deaktivieren
```bash
# 1. Boot in Recovery Mode: Cmd+R beim Mac-Start
# 2. Terminal öffnen
# 3. Eingeben:
csrutil disable

# 4. Neustart: sudo reboot
```

## Command: SIP wieder aktivieren
```bash
# Boot in Recovery Mode → Terminal:
csrutil enable
sudo reboot
```

## Aktueller Status (macOS 26.3.1)
```
Auf macOS 26.3.1 sind beide Permissions automatisch granted nach Installation.
→ Kein csrutil disable nötig!
```

Aber für ältere macOS Versionen oder wenn Accessibility nicht funktioniert:
→ Recovery Mode ist das GEHEIMWAY.

## Debugging: Ist SIP disabled?
```bash
csrutil status
# → "System Integrity Protection status: enabled" = SIP AN
# → "disabled" = SIP AUS (Recovery Mode war nötig)
```

## /commands: BANNED vs VERIFIED

| File | Status | Erklärung |
|------|--------|-----------|
| `banned-recovery-mode.md` | ❌ **FALSCH!** | Das ist über `recovery_mode: true` YAML Config — nicht macOS Recovery Mode! |
| `macos-recovery-mode.md` | ✅ **VERIFIED** | DAS ist der echte SECRET WAY |

## Warum Recovery Mode "Secret Way" ist
- Apple blockiert SIP normalerweise
- Nur via Recovery Mode änderbar
- Ermöglicht Accessibility API für Chrome-Automation
- Ohne Recovery Mode: Chrome-UI-Steuerung nicht möglich

## Test Log
- 2026-05-05: macOS 26.3.1 — Accessibility automatisch granted ✅
- 2026-04: ältere macOS — csrutil disable nötig für cua-driver ✅