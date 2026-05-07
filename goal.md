# goal.md – Stealth Runner Hauptziel

> **← [sinrules.md](sinrules.md) ist die zentrale Regeldatei.**
> **← [brain.md](brain.md) dokumentiert die NEMO Architektur.**

## Primärziel

Heypiggy.com automatisieren: Google-Login → Surveys abschließen → EUR > 0 verdienen
**mit NEMO Architektur — Compact Snapshot + NIM + Batch Execute.**

---

## NEMO Architektur: Hauptziel 2026-05-06

**Problem:** skylight-cli's flacher Element-Index ist instabil (Browser-Chrome + Web-Content gemischt).
**Lösung:** Compact Snapshot (skylight/CDP) → Nemotron Decision (NIM) → Batch Execute (CDP)

### Meilensteine

| Datum | Meilenstein | Status |
|-------|-------------|--------|
| 2026-05-03 | ~~CDP+AX Grundlage~~ (LEGACY/DEPRECATED) | ✅ |
| 2026-05-06 | **NEMO Grundlage**: `src/stealth_survey/` SurveyAgent + NIMClient + BatchExecutor | ✅ |
| 2026-05-06 | **Compact Snapshot**: skylight-cli snapshot-compact → @eN Element-Refs | ✅ |
| 2026-05-06 | **NIM Decision**: Nemotron 3 Omni entscheidet pro Seite | ✅ |
| 2026-05-06 | **Batch Execute**: Alle Actions in EINEM CDP WebSocket Call | ✅ |

### Erfolgskriterien

- "Weiter" Klick trifft NIE "Weitere Informationen" (word-boundary + kein Index)
- Browser-Chrome wird NIE geklickt (CDP tree hat kein Chrome)
- 100× hintereinander stabil

---

## Bisherige Erfolge

| Datum | Erfolg | Details |
|-------|--------|---------|
| 2026-05-03 | **Google Login (PID 16811)** | Email → Consent → Dashboard ✅ |
| 2026-05-03 | **Google-Login-in-Google (PID 33926)** | Email → Passwort → FaceID ✅ |
| 2026-05-03 | **Label-basierte Erkennung** | find_by_label word-boundary fix |
| 2026-05-03 | **cua-touch + macos-ax-cli** | System-weite Popup-Erkennung |

### Live-Trio-Architektur (erreicht)
- ✅ **EYES**: skylight-cli list_windows / macos-ax-cli (Popups erkennen)
- ✅ **BRAIN**: CDP queryAXTree (Web-Elemente finden)
- ✅ **HANDS**: AXUIElementCopyElementAtPosition + AXPress (Klick ohne Index)

### Alles dokumentiert
- ✅ `brain.md` – CDP+AX Trinity Architektur
- ✅ `issues.md` – Kritisches Index-Problem dokumentiert
- ✅ `AGENTS.md` – Fusionierte Tool-Befehle
- ✅ `plan.md` – Implementierungsplan
- ✅ `fix.md` – Root Cause Fix
- ✅ `learn.md` – Fusionierte Learnings
- ✅ `commands.md` – Neue CDP+AX Befehle
- ✅ `sinrules.md` – Neue Regeln

## Nächste Schritte (2026-05-07)

> **CRASH-TEST STATUS**: 10+ Live-Entdeckungen. Survey navigiert zu Qualtrics im NEUEN TAB. Balance lesen funktioniert. React-Formulare per native Setter füllbar. 5 neue Fixes dokumentiert.

### P0 — Auszahlung erreichen
1. **Qualtrics-Loop vollenden**: Sprache wählen → Land auswählen → Fragen beantworten → ">>"/Weiter → Abschluss erkennen → Balance-Check
2. **Tab-Wechsel automatisieren**: Nach clickSurvey() Tabs prüfen, neuen Tab erkennen, CDP umschalten
3. **Completion Detection**: Balance vorher/nachher vergleichen, "Danke"/"abgeschlossen" Keywords über ALLE Tabs scannen

### P1 — Stabilisierung
4. **Qualtrics-Provider-Selektoren**: `.NextButton`, `.LabelWrapper`, `.ChoiceStructure` in PROVIDER_COMMANDS
5. **Form-Validierung**: Age-Feld "Value must be like '53'" → intelligent auf 53 anpassen
6. **Anti-Stuck**: State-Hash detection (kein DOM-Change nach 5 Iterationen → Abbruch)

### P2 — Architektur
7. **cua-driver reaktivieren**: Chrome mit `--force-renderer-accessibility` starten für AX-Tree-Zugriff
8. **Tab-Switching Integrationstest**: `test_tab_switching.py`
9. **Stacked-Modal Cleaner**: Vor jeder Survey-Interaktion alle "Schließen"-Buttons klicken

### Meilenstein-Tracker
| Datum | Meilenstein | Status |
|-------|-------------|--------|
| 2026-05-03 | Google Login | ✅ |
| 2026-05-06 | NEMO Architektur + 4 Root Causes gefixt | ✅ |
| 2026-05-07 | **Live Crash-Test: 10+ Discoveries, Survey bis Qualtrics navigiert** | ✅ |
| 2026-05-07 | Balance-Fix + React-Form-Fill + Tab-Detection | ✅ |
| 🔜 | **Erste Auszahlung (EUR > 0)** | 🔴 |
| 🔜 | 10× stabiler Survey-Durchlauf | 🔴 |
| 🔜 | cua-driver AX-Tree aktiv | 🔴 |
