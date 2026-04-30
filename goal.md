# goal.md — stealth-runner

## Primärziel
Automatisierte, unsichtbare Umfrage-Teilnahme via Stealth-Triade.
**Klick-Mechanismus: AXPress (Accessibility-API) — funktioniert auf Chrome 148/macOS 26.**

## Status (30.4.2026)
- ✅ Klick funktioniert (AXUIElementPerformAction + kAXPressAction)
- ⚠️ Chrome braucht `--force-renderer-accessibility`, stürzt nach ~30s
- ✅ safe_click.py eliminiert Apple-Menü-Fehler
- ❌ Login-Flow noch nicht automatisiert (Google OAuth)

## OKRs Q2 2026
1. 50 Live-Surveys ohne Bot-Detektion
2. Survey-Dauer 40% reduziert (kein CDP-Overhead)
3. Crash-Recovery 100% (Resume-Fähigkeit)
4. 0 unmask-cli Detektionen

## Technische Ziele
- ZERO cua-driver Referenzen ✅
- skylight-cli v0.2.0 als einziger Aktions-Executor ✅
- 10-State Machine mit LAUNCH_BROWSER ✅
- 1742-char SYSTEM_PROMPT mit 10 Aktionen ✅
- sin_survey_core mit 8 Panel-Providern ✅
