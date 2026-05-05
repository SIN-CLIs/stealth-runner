# BANNED: AppleScript für Chrome Browser-Steuerung ❌

## Status
**BANNED** — 2026-05-05

## Warum verboten
`osascript -e 'tell application "Google Chrome" to open location "..."'` öffnet/changed ALLE Chrome-Instanzen (BOT + USER).

**Konsequenz: USER Chrome wird manipuliert, falsches Window aktiviert.**

## Warum es kaputt ist
AppleScript spricht mit der **Application** (Google Chrome) — nicht mit einem spezifischen Chrome-Profil.
Alle Chrome-Instanzen desselben Users reagieren auf `tell application "Google Chrome"`.

## Banned Commands
```bash
osascript -e 'tell application "Google Chrome" to open location "..."'
osascript -e 'tell application "Google Chrome" to tell window 1...'
osascript -e 'tell application "Google Chrome" to activate'
```

## Korrekte Alternative
→ CUA-Driver Address Bar Methode (bot-spezifisch):
```bash
# Fokussiere Address Bar + navigiere im BOT Chrome
echo '{"pid": BOT_PID, "window_id": BOT_WID, "element_index": 7}' | cua-driver call click   # Address bar
echo '{"pid": BOT_PID, "window_id": BOT_WID, "element_index": 7, "value": "https://..."}' | cua-driver call set_value
echo '{"pid": BOT_PID, "window_id": BOT_WID}' | cua-driver call press_key '{"pid": BOT_PID, "window_id": BOT_WID, "key": "return"}'
```

## Test Log
- 2026-05-05: `osascript -e 'tell application "Google Chrome" to open location "chrome://settings/passwords"'` → Settings Window geöffnet ❌
- Effekt: USER Chrome Settings Page beeinflusst, Login-Flow komplett zerstört