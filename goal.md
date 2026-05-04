# goal.md – Stealth Runner Hauptziel

> **← [sinrules.md](sinrules.md) ist die zentrale Regeldatei.**
> **← [brain.md](brain.md) dokumentiert die CDP+AX Trinity Architektur.**

## Primärziel

Heypiggy.com automatisieren: Google-Login → Surveys abschließen → EUR > 0 verdienen
**mit CDP+AX Trinity — kein Element-Index-Shift mehr.**

---

## CDP+AX Trinity: Hauptziel 2026-05-03

**Problem:** skylight-cli's flacher Element-Index ist instabil (Browser-Chrome + Web-Content gemischt).
**Lösung:** CDP queryAXTree (NUR Web) → AXUIElementCopyElementAtPosition (Position ≠ Index)

### Meilensteine

| Datum | Meilenstein | Status |
|-------|-------------|--------|
| 2026-05-03 | **CDP+AX Grundlage**: `cdp_click.py` mit WebSocket + queryAXTree + AXPress | ⬜ |
| 2026-05-03 | **Google Login via CDP+AX**: Email → Weiter → Passwort → Dashboard | ⬜ |
| 2026-05-03 | **Fallback-Kette**: CDP → skylight → cua → macos-ax-cli | ⬜ |
| 2026-05-03 | **10× stabiler Google Login** mit CDP+AX | ⬜ |
| 2026-05-03 | **HeyPiggy Dashboard + Survey** via CDP+AX | ⬜ |

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

## Nächste Schritte

1. `cdp_click.py` implementieren (WebSocket + queryAXTree + AXPress)
2. Google Login via CDP+AX testen
3. Fallback-Kette validieren
4. 10× stabiler Durchlauf
