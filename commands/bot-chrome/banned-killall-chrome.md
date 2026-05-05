# BANNED: killall Google Chrome ❌

## Status
**BANNED** — 2026-05-05

## Warum verboten
Killt ALLE Chrome-Prozesse — BOT und USER Chrome vollständig.

## Warum es kaputt ist
`killall` matched nach ProzessNAME, nicht nach user-data-dir.
Alle Chrome-Instanzen haben den Namen "Google Chrome":
- BOT: `heypiggy-bot-XXXXXXXX` Profile
- USER: DeepSeek, localhost, API keys, etc.

**KONSEQUENZ: Alle Chrome-Fenster geschlossen. USER verliert alle Tabs.**

## Korrekte Alternative
→ `/commands/kill-bot-chrome.md` — killt NUR heypiggy-bot-* Chrome-Main-Prozesse