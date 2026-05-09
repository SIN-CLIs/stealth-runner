---
title: "DAEMON WAY Architektur-Prinzip zu AGENTS.md und sinrules.md hinzugefügt"
severity: high
status: completed
created: 2026-05-09
---

# Issue 013: DAEMON WAY Architektur-Prinzip implementiert

## Was wurde getan

### AGENTS.md — Neuer Abschnitt "DAEMON WAY" (§1-§10, 295 Zeilen hinzugefügt)

Vollständige State-of-the-Art Architektur-Dokumentation:

| Section | Inhalt |
|---------|--------|
| §1 SINGLE SOURCE OF TRUTH | AGENTS.md als permanente Brain-Datei |
| §2 DAEMON WAY | Learning-by-Doing Loop (SCAN→PROBIEREN→ERFOLG→FEHLER→DELETE) |
| §3 DELETE WRONG IMMEDIATELY | Sofortiges Löschen fehlerhafter Commands/Code |
| §4 ONCE VERIFIED = READ-ONLY | chmod 444 auf verifizierte Files |
| §5 FEED AGENTS.MD FOREVER | Jede Erkenntnis sofort nach AGENTS.md |
| §6 FASTFAPI ALS DAEMON-HIRN | Zentrale Steuerung via 8889 Endpoints |
| §7 COMMAND VERZEICHNIS | /commands/ als permanente Wissensbasis |
| §8 SURVEY TYP KATALOG | Alle Survey-Typen dokumentiert |
| §9 DEFINITION OF DONE | Wann ist Task FERTIG für die KI? |
| §10 ANTI-PATTERN | Niemals monolithische Endpoints, keine Hardcoded PIDs |

### sinrules.md — DAEMON WAY Sektion + Fixes

1. **Neuer §10** am Ende: Verweis auf AGENTS.md §DAEMON WAY + Kernprinzipien
2. **Fix**: src/stealth_survey/ von ERLAUBT → DELETED
3. **Cross-Reference Update**: AGENTS.md verweist jetzt auf DAEMON WAY
4. **Date**: 2026-05-06 → 2026-05-09

### Fixes in bestehenden Sektionen

- Line 447: src/stealth_survey/ als ERLAUBT → DELETED ✅
- Lines 832-849: app/ Imports → survey-cli Pfade ✅
- Line 856: persona.py → ProfileLoader ✅
- Line 465: playstealth launch → Chrome Recipe ✅
- Line 1035: Port 9222 → 9999 ✅
- Line 521-528: cua-driver PRIMARY → NEMO PRIMARY ✅
- Line 1065: A2A-SIN-Worker-heypiggy/ → entfernt ✅

## Verification

```bash
# API noch funktionsfähig:
curl -X POST http://localhost:8889/dashboard/scan -d '{"cdp_port": 9999}'
# Erwartet: status=success, 12 surveys ✅

# Dateien:
# - AGENTS.md: 1356 Zeilen (vorher ~1061, +295 DAEMON WAY)
# - sinrules.md: 395 Zeilen (vorher 369, +26 DAEMON WAY)
```

## Warum das wichtig ist

Die KI ist wie ein "hochbegabter Praktiker mit ADHS":
- Ohne vollständigen Bauplan: improvisiert → Schuldenberg-Müll
- Mit AGENTS.md: voller Kontext bei jedem Prompt → funktioniert direkt
- Token-Kosten: 1€ = 100× billiger als 1h Bug-Suche

**Single Source of Truth = AGENTS.md. Alles andere ergibt sich.**
