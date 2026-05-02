# successful.md – Was funktioniert (SOTA 2026-05-01)

## 2026-05-02: Doctor Scan Results

**Verfügbare Tools (23):**

- ✅ cloc
- ✅ tokei
- ✅ lizard
- ✅ pydeps
- ✅ pyreverse
- ✅ dependency-cruiser
- ✅ code2flow
- ✅ plantuml
- ✅ sphinx
- ✅ mkdocs

**Scan-Ergebnisse:**

- Code-Statistiken: 2689 Dateien in TypeScript, JSON, JavaScript
- Fixes: 86 Muster aktualisiert

## TRIO LAYER (Live Auge-Hirn-Hand)

```
EYES:  skylight-cli list_windows → Popup erkannt ✅
BRAIN: skylight-cli get_window_state --window-id → Nur Popup-Elemente ✅
HANDS: skylight-cli click --pid --window-id --element-index → RICHTIGES Fenster ✅
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
2. Popup-Erkennung → `skylight-cli list_windows` ✅
3. Elemente im Popup → `skylight-cli get_window_state --window-id` ✅
4. Vision-Entscheidung → Nemotron Omni (`reasoning`-Feld) ✅
5. Unsichtbarer Klick → `skylight-cli click --element-index` ✅
6. SSE Streaming → `stream: true` + `Accept: text/event-stream` ✅
7. Rolling Video Buffer → screen-follow + ffmpeg + Omni Conv3D ✅

## Doctor CLI v6 (28 Tools)

| Kategorie      | Tools                                                          |
| -------------- | -------------------------------------------------------------- |
| Deep Analysis  | cloc, tokei, lizard, pydeps, pyreverse                         |
| Deps & Flow    | dependency-cruiser, code2flow, plantuml                        |
| Doc Generation | sphinx, mkdocs, pdoc, typedoc, doxygen, terraform-docs, pandoc |
| Quality        | vale, standard-readme, prettier, repomix, gitingest            |
| Changelog      | git-cliff, conventional-changelog, auto-changelog              |

## NICHT funktionierend

- skylight-cli OHNE window-id bei Popups (klickt ins falsche Fenster)
- DOM-Prescan (ENTFERNT – klickte blind Element 1)
- `CGEventPostToPid` (TOT auf Chrome 148)
- `skylight-cli --x --y` (BANNED – Koordinatenraten)
