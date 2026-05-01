# goal.md — stealth-runner (Updated 2026-05-01)

## Primärziel
Automatisierte, unsichtbare Umfrage-Teilnahme via Stealth-Quad.
**Klick: AXPress (Accessibility-API). Chrome-Accessibility: VoiceOver-Trick (kein Flag nötig).**
**Vision-free Fast Path: DOM prescan mit Confidence Gate — 60% weniger Vision-Costs.**

## SOTA Status (Mai 2026)
- ✅ Cross-Repo Integration: Alle 4 CLIs orchestriert via state_machine.py
- ✅ Vision-free Fast Path: runner/dom_prescan.py mit Threshold 0.85
- ✅ CreepJS CI Gate: playstealth-cli CI prüft ≥ 80%
- ✅ CEO Strategic Verdict: docs/CEO_STRATEGIC_VERDICT_2026-05-01.md
- 🔬 SOTA-Pläne: 7 Pläne in A2A docs/sota-plans/

## Status (30.4.2026, 10:35 · v0.3.1)
- ✅ AXPress-Klick funktioniert auf Chrome 148/macOS 26
- ✅ VoiceOver-Trick: Web-Elemente OHNE --force-renderer-accessibility
- ✅ Google Login-Dialog erfolgreich geöffnet
- ✅ DOM prescan + confidence classification
- ✅ Screen-follow recording orchestriert
- ⚠️ Login-Flow (E-Mail/Passwort) noch nicht automatisiert
- ❌ Survey-Loop + EUR noch nicht erreicht

## OKRs Q2 2026
1. ✅ Vision-free Fast Path implementiert (Commit b1eee1e)
2. ✅ Cross-Repo Integration abgeschlossen
3. 🔴 Erster EUR > 0 auf heypiggy.com
4. 🟡 Test coverage ≥ 40% in allen Repos

## Technische Ziele (erreicht)
- ZERO cua-driver Referenzen ✅
- skylight-cli v0.2.0 als einziger Aktions-Executor ✅
- 10-State Machine mit DOM_PRESCAN State ✅
- unmask-cli dom scan integration ✅
- screen-follow recording lifecycle ✅
