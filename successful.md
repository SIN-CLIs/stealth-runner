# successful.md – Erfolgreich implementierte Features & Fixes

## ✅ 2026-05-02 – cua-driver Popup-Interaktion (DURCHBRUCH!)

**Erfolg**: Google OAuth Login VOLLSTÄNDIG automatisiert via `cua-driver` Popup-Steuerung.

**Ablauf** (verifiziert mit PID 31710, WID 33673):
1. `skylight-cli click --pid 31710 --element-index 33` → Google Login Button (Hauptfenster)
2. `cua-driver call list_windows` → Popup finden: WID=33673 "Anmelden – Google Konten"
3. `cua-driver call get_window_state` → Popup-Elemente laden
4. `cua-driver call set_value [25]` → Email: zukunftsorientierte.energie@gmail.com
5. `cua-driver call click [35]` → "Weiter" im Popup
6. Consent-Screen: `cua-driver call click [65]` → "Fortfahren"
7. Final: `cua-driver call click [41]` → "Weiter"
8. ✅ **EINGELOGGT!** Kein Popup mehr, nur noch HeyPiggy Dashboard

**Key Insight**: Bestehende Google-Cookies aus früheren Chrome-Profilen machten
Passwort-Eingabe ÜBERFLÜSSIG. Google erkannte die Email und forderte nur Consent-Flow.

## ✅ 2026-05-02 – SOTA tmux Non-Blocking Workflow

**Erfolg**: Screen-follow Recording + Survey Loop parallel in tmux-Panes ohne Blocking.
Dokumentiert in `docs/TMUX-BACKGROUND-WORKFLOW.md` mit Web-Recherche (OpenCode #6929,
Oh-My-OpenCode Background Agents, Claude Code Multi-Agent).

## ✅ 2026-05-02 – LiveEye v7 Motion Detection & CRF Tuning

**Erfolg**: Adaptive FPS funktioniert mit optimierten Thresholds:
- MOTION_HIGH_THRESH=20.0, MOTION_LOW_THRESH=3.0
- CRF Auto-Adjust: 28 (high) / 35 (mid) / 40 (low)
- Conv3D num_frames: -1 / 8 / 4 je nach Motion

## ✅ 2026-05-01 – Pre-existing Bugfixes (5 Stück)
- `Path` Import in `skylight.py`
- `asyncio.get_event_loop()` → `new_event_loop()` Python 3.14
- `playstealth --json` Argument-Reihenfolge
- `screenshot()` Aufruf in `stealth_executor.py`
- `step.py` ModuleNotFoundError (__init__.py fehlte)

## ✅ 2026-05-01 – /doctor Skill erweitert
- 23 Context-Writer Docs (CHANGELOG.md + ROADMAP.md neu)
- Graphify Setup + Post-Commit Hook
- Cleanup Phase