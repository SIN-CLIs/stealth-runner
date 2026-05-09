# PLAYSTEALTH LAUNCH — BANNED für HeyPiggy (2026-05-09)

## Status
**BANNED** für HeyPiggy — NICHT verwenden!

## Warum BANNED?
- `playstealth launch` setzt NICHT `--force-renderer-accessibility` → AX-Tree leer
- `playstealth launch` nutzt frisches Profil → keine Cookies, Login nötig
- Profil 902 Kopie → verschlüsselte Cookies (AES-GCM v11), Login nötig

## FALSCH (alte Docs behaupteten):
- Port 9224 ❌ → HeyPiggy ist Port 9999
- Profil 902 Kopie ❌ → Profil 901 (Jeremy) Kopie + Cookie-Injection
- `/tmp/heypiggy-bot-*` ❌ → `/tmp/chrome-jeremy-heypiggy-9999`

## RICHTIGER WEG: Recipe in AGENTS.md ganz oben (REGELN 1-4)
```bash
# 1. Profil 901 (Jeremy) kopieren
cp -R "$HOME/Library/Application Support/Google Chrome/Profile 901 (Jeremy)" /tmp/chrome-jeremy-heypiggy-9999

# 2. Chrome starten
nohup "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --remote-debugging-port=9999 \
  --remote-allow-origins="*" \
  --force-renderer-accessibility \
  --no-first-run \
  --user-data-dir="/tmp/chrome-jeremy-heypiggy-9999" \
  "https://www.heypiggy.com/?page=dashboard" &>/dev/null &

# 3. 7 HeyPiggy-Cookies injectieren (aus ~/.stealth/heypiggy-backup/heypiggy-cookies.json)
# → Network.setCookies batch → Page.navigate → eingeloggt!
```