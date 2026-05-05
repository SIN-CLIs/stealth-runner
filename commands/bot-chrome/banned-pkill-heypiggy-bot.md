# BANNED: pkill -f "heypiggy-bot" ❌

## Status
**BANNED** — 2026-05-05

## Warum verboten
Killt ALLE Prozesse die "heypiggy-bot" enthalten — inkl. Chrome-Helper-Prozesse von USER Chrome.

## Warum es kaputt ist
`pkill -f` matched **jeden Prozess** dessen Command-Line "heypiggy-bot" enthält.
Chrome-Child-Prozesse (Renderer, GPU, Helper) haben "heypiggy-bot" im Command:
```
/Applications/Google Chrome.app/Contents/.../Google Chrome Helper (Renderer) ... --user-data-dir=/tmp/heypiggy-bot-XXXXXXXX
```

Resultat: USER Chrome stirbt, alle Tabs gone, alle Sessions verloren.

## Korrekte Alternative
→ `/commands/kill-bot-chrome.md` — killt NUR Main-Prozesse mit korrektem Pattern-Match