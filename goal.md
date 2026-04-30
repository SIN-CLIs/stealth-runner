# goal.md — stealth-runner

## Primärziel
Automatisierte, unsichtbare Umfrage-Teilnahme via Stealth-Triade.
**Klick: AXPress (Accessibility-API). Chrome-Accessibility: VoiceOver-Trick (kein Flag nötig).**

## Status (30.4.2026, 10:35 · v0.3.1)
- ✅ AXPress-Klick funktioniert auf Chrome 148/macOS 26
- ✅ VoiceOver-Trick: Web-Elemente OHNE --force-renderer-accessibility
- ✅ Google Login-Dialog erfolgreich geöffnet
- ⚠️ Login-Flow (E-Mail/Passwort) noch nicht automatisiert
- ❌ Survey-Loop + EUR noch nicht erreicht

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
