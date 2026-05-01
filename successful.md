# successful.md – Was funktioniert (SOTA 2026-05-01)

## TRIO LAYER (Live Auge-Hirn-Hand)
```
EYES:  cua-driver list_windows → Popup erkannt ✅
BRAIN: cua-driver get_window_state --window-id → Nur Popup-Elemente ✅
HANDS: cua-driver click --pid --window-id --element-index → RICHTIGES Fenster ✅
```
- **Popup-Erkennung** funktioniert (Google Login Popup wird erkannt: WindowID=30380)
- **Element-Index im Popup** funktioniert (Weiter=Index 35, E-Mail=Index 25)
- **Live 250ms Polling** für Echtzeit-Erkennung

## Google Login (vollständig automatisiert)
1. `playstealth launch --url 'https://heypiggy.com/?page=dashboard'` → PID
2. Google Login-Symbol klicken (Index variiert)
3. E-Mail eingeben (zukunftsorientierte.energie@gmail.com)
4. Weiter klicken (Google prüft E-Mail)
5. Passwort eingeben (ZOE.jerry2024)
6. Weiter klicken (Google prüft Passwort)
7. ✅ Eingeloggt auf heypiggy.com Dashboard

## Core-Loop
1. Browser starten → `playstealth launch` ✅
2. Popup-Erkennung → `cua-driver list_windows` ✅
3. Elemente im Popup → `cua-driver get_window_state --window-id` ✅
4. Vision-Entscheidung → Nemotron Omni (`reasoning`-Feld) ✅
5. Unsichtbarer Klick → `cua-driver click --element-index` ✅
6. SSE Streaming → `stream: true` + `Accept: text/event-stream` ✅
7. Rolling Video Buffer → screen-follow + ffmpeg + Omni Conv3D ✅

## Doctor CLI v6 (28 Tools)
| Kategorie | Tools |
|-----------|-------|
| Deep Analysis | cloc, tokei, lizard, pydeps, pyreverse |
| Deps & Flow | dependency-cruiser, code2flow, plantuml |
| Doc Generation | sphinx, mkdocs, pdoc, typedoc, doxygen, terraform-docs, pandoc |
| Quality | vale, standard-readme, prettier, repomix, gitingest |
| Changelog | git-cliff, conventional-changelog, auto-changelog |

## NICHT funktionierend
- skylight-cli OHNE window-id bei Popups (klickt ins falsche Fenster)
- DOM-Prescan (ENTFERNT – klickte blind Element 1)
- `CGEventPostToPid` (TOT auf Chrome 148)
- `cua-driver --x --y` (BANNED – Koordinatenraten)
