---
title: "AGENTS.md LIES FOUND & FIXED (2026-05-09)"
severity: critical
status: fixed
created: 2026-05-09
---

# Issue 012: 15 LIES/FALSCH-informationen in AGENTS.md gefunden und gefixt

## KRITISCHE LÜGEN (knnen Production brechen)

### 1. REGEL 4 Recipe (Linie 36-79) — VÖLLIG FALSCH
**Problem:** Recipe nutzt `decrypt_cookies.py` zuerst → schafft NICHT für Chrome 147+ (v11 AES-GCM)!
- Output-Pfad existiert nicht → Cookie-Injection schlägt fehl → Session tot
**Fix:** decrypt_cookies.py entfernt, Backup-Cookies-Methode als einziger Weg dokumentiert

### 2. Cookie-Anzahl (Linie 20)
**Problem:** "54 Cookies total" — Backup hat 40!
**Fix:** "40 Cookies total" + "aktive Session: 7 HeyPiggy, Rest Google/misc"

### 3. Falscher Profile-Pfad (Linie 276)
**Problem:** `--user-data-dir=/tmp/heypiggy-new-$(date +%s)` — falscher Pattern!
**Fix:** `/tmp/chrome-jeremy-heypiggy-9999` (korrekter Pattern aus REGELN 1-4)

### 4. playstealth launch als Option (Linie 294)
**Problem:** "`playstealth launch --url '...'`" als gültiger Restart-Weg
**Fix:** Recipe REGELN 1-4 als einzige gültige Methode

### 5. src/stealth_survey/ als ERLAUBT (Linie 447)
**Problem:** Tabelle listet es als "ERLAUBT" obwohl es INTENTIONALLY DELETED ist (Linie 424-430)
**Fix:** "❌ DELETED — INTENTIONALLY DELETED 2026-05-08"

### 6. app/ Imports (Linien 832-838, 843-849)
**Problem:** `from app.core.orchestrator import run` + `app/flows/learning/` — app/ ist DELETED!
**Fix:** survey-cli/survey/runner.py + survey-cli/survey/ als korrekte Pfade

### 7. persona.py Import (Linie 856-867)
**Problem:** `from persona import load_persona, resolve_answer` — persona.py existiert nicht als standalone
**Fix:** `from survey_cli.survey.profile_loader import ProfileLoader`

### 8. playstealth launch in CUA-ONLY Trinity Diagramm (Linie 465-466)
**Problem:** playstealth launch als Start-Step im Diagramm
**Fix:** "Chrome Recipe (REGELN 1-4) -> {\"port\": 9999}"

## INKONSISTENZEN GEFIXT

### 9. TOOLS Tabelle (Linie 521-528)
**Problem:** cua-driver als PRIMARY, aber NEMO ist PRIMARY
**Fix:** skylight-cli + CDP WebSocket als PRIMARY, cua-driver = LEGACY

### 10. ERLAUBT Sektion (Linien 1012-1016)
**Problem:** CDP als "Fallback" bezeichnet, aber es ist PRIMARY
**Fix:** "PRIMARY für Snapshot + Batch"

### 11. survey.py Architektur (Linie 1035)
**Problem:** "CDP WebSocket (port 9222)" — 9222 ist SINator-Port, nicht HeyPiggy
**Fix:** "CDP WebSocket (port 9999) -> HeyPiggy Chrome"

### 12. playstealth Erwähnung AX-Tree (Linie 896)
**Problem:** playstealth als Vergleich erwähnt (auch nach BANNED-Markierung)
**Fix:** Klarstellung dass playstealth DESHALB BANNED ist

### 13. playstealth Erwähnung CDP Section (Linien 890-891)
**Problem:** "Selbst mit playstealth kann der Origin-Check noch aktiv sein"
**Fix:** "Selbst mit korrekten Flags" (playstealth nicht erwähnen)

### 14. Stealth Suite (Linie 1065)
**Problem:** `A2A-SIN-Worker-heypiggy/` im Suite-Liste — Verzeichnis existiert NICHT
**Fix:** Entfernt

### 15. cli/modules/auto_google_login.py (Linien 925, 987)
**Status:** Datei existiert tatsächlich! Kein Fix nötig, aber als LÜGE markiert weil der Pfad nicht ins survey-cli System passt.
**Note:** Datei existiert in `/Users/jeremy/dev/stealth-runner/cli/modules/` — korrekter Pfad, kein Fix nötig.

---

## Verification

```bash
# Nach allen Fixes:
curl -s -X POST http://localhost:8889/dashboard/scan -H "Content-Type: application/json" -d '{"cdp_port": 9999}'
# Erwartet: status=success, 12 surveys

curl -s -X POST http://localhost:8889/dashboard/balance -H "Content-Type: application/json" -d '{}'
# Erwartet: balance_eur=2.60
```
