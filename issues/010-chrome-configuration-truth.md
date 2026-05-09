# Issue 010: Chrome-Konfiguration — Korrekte Ports und Profile

> **Status**: ⚠️ KONFLIKT AUFGETRETEN  
> **Datum**: 2026-05-08  
> **Lösung**: Dokumentation korrigiert, Profile 901 = HeyPiggy

---

## Das Chaos

Während der Session gab es mehrere widersprüchliche Chrome-Konfigurationen:

| Quelle | Port | Profil | Status |
|--------|------|--------|--------|
| AGENTS.md (alt) | 9222 | 901 | SINator Fireworks |
| AGENTS.md (alt) | 9999 | 902 Kopie | HeyPiggy (FALSCH — Profil 902 ist verschlüsselt!) |
| Session-Test | 9224 | 902 | HeyPiggy (korrekt, aber Profil tot) |
| **KORREKT** | 9999 | Profil 901 Kopie → /tmp | HeyPiggy + Cookie-Injection |

---

## ⚠️ FALSCHE WEGE (NIEMALS VERWENDEN!)

- ❌ `/tmp/heypiggy-new-*` (frisches Profil) → Login nötig, keine Cookies
- ❌ `launch_parallel.py` → Profil 902 Kopie = verschlüsselt, Login nötig
- ❌ `--user-data-dir="/Users/jeremy/Library/Application Support/Google Chrome"` ohne Kopie → Chrome läuft bereits (Simone), Konflikt
- ❌ Port 9222 → SINator Chrome, nicht HeyPiggy

---

## Die Wahrheit (aus Session-DB extrahiert)

### Profile 901 (Jeremy) = HeyPiggy (AKTIV)
- **User Data Dir**: `/Users/jeremy/Library/Application Support/Google Chrome`
- **Profile**: `Profile 901 (Jeremy)`
- **CDP Port**: 9999 (explizit gesetzt)
- **Eigentümer**: jeremy (NICHT simoneschulze!)
- **Status**: 2.60€ Balance, 12 Surveys verfügbar

### Profile 902 = SIN-Agent Heypiggy (NICHT HeyPiggy!)
- **User Data Dir**: Gleiches Verzeichnis
- **Profile**: `Profile 902`
- **Status**: Cookies vorhanden, aber VERSCHLÜSSELT (AES-128-GCM MAC-Challenge)
- **FALSCH**: Dieser Profil-Kopien sind NICHT das HeyPiggy-Login!

---

## Warum die Verwirrung?

1. **Profile 901 ist das EINZIGE funktionierende HeyPiggy-Profil**
2. **Verschlüsselung**: Profile-Kopien haben Chrome-verschlüsselte Cookies → Login nötig
3. **SingletonLock**: Chrome blockiert zweiten Prozess im selben user-data-dir
4. **Cookie-Injection rettet**: 7 HeyPiggy-Cookies aus Backup injectieren → Login ohne Neuanmeldung!

---

## Korrekte Konfiguration (aus Session)

### Für HeyPiggy (Survey-Automation) — COPY EXACT:
```bash
# 1. Profil kopieren
cp -R "$HOME/Library/Application Support/Google Chrome/Profile 901 (Jeremy)" /tmp/chrome-jeremy-heypiggy-9999

# 2. Chrome starten
nohup "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --remote-debugging-port=9999 \
  --remote-allow-origins="*" \
  --force-renderer-accessibility \
  --no-first-run \
  --user-data-dir="/tmp/chrome-jeremy-heypiggy-9999" \
  "https://www.heypiggy.com/?page=dashboard" &>/dev/null &
sleep 4

# 3. 7 HeyPiggy-Cookies injizieren (Network.setCookies batch)
# → ERFOLG wenn body.innerText "Abmelden" enthält
```

**WICHTIG**:
- Port 9999 ist der API-Standard (nicht 9222)
- Profile 901 Kopie ist das funktionierende HeyPiggy-Profil (nicht 902!)
- Profile-Kopie ist VERSCHLÜSSELT → Cookies MÜSSEN injectiert werden
- 7 HeyPiggy-Cookies: `user_session`, `PHPSESSID`, `user_id`, `user_a_b_group`, `lang_pig`, `g_state`, `referer`
- Backup: `~/.stealth/heypiggy-backup/heypiggy-cookies.json` (54 Cookies, 7 HeyPiggy)

---

## Cookie-Management

### Extraktion (funktioniert nur von ORIGINAL, nicht Kopie):
```python
# Port 9999 (HeyPiggy-Instanz)
curl -s http://127.0.0.1:9999/json/list
# → WebSocket URL finden
# → Network.getAllCookies → heypiggy-cookies.json
```

### Backup-Standorte:
```
Backup:   ~/.stealth/heypiggy-backup/heypiggy-cookies.json (54 Cookies, 7 HeyPiggy)
```

### Recovery-Protokoll:
1. Session validieren: "Abmelden" sichtbar?
2. Wenn TOT: Nichts speichern/extrahieren!
3. Chrome beenden (kill PID mit `lsof -i :9999`)
4. Profil 901 kopieren → `/tmp/chrome-jeremy-heypiggy-9999`
5. Chrome neu starten
6. 7 HeyPiggy-Cookies aus Backup injectieren

---

## Session-Referenz

- Session: `ses_1fb699b0effeULfoLPQHb1rBpi`
- Teil: `prt_e09bf28f9001V5ZqlzpP5u2JvE` — Cookie-Test erfolgreich
- Teil: `prt_e09aae6f50014hCu82Ujuij7RH` — Profile-Verwirrung aufgelöst
- Teil: `prt_e095d9149001Iy7nNYAJ3exLXL` — "COOKIES FUNKTIONIEREN!"

---

## Korrekte FastAPI Ports

| Service | Port | Zweck |
|---------|------|-------|
| Chrome CDP | 9999 | Browser-Steuerung |
| FastAPI | 8889 | API-Server |

**Session-Tests verwendeten 8888/9224** — das war für SINator/Special-Cases.

---

## Banned

- `pkill -f "Google Chrome"` — tötet ALLE Instanzen (USER + BOT)
- `launch_parallel.py` + Profil 902 Kopie — verschlüsselte Cookies, Login nötig
- Frisches Profil in `/tmp/` — keine Cookies, Login nötig
- Profile 902 für HeyPiggy — ist nicht das aktive Profil (Profile 901!)
- Port 9222 für HeyPiggy — SINator Chrome, nicht HeyPiggy

---

## ✅ EINZIG RICHTIGER WEG (2026-05-09)

1. Profil 901 (Jeremy) kopieren → `/tmp/chrome-jeremy-heypiggy-9999`
2. Chrome starten auf 9999 mit Kopie
3. 7 HeyPiggy-Cookies aus Backup injectieren
4. Dashboard navigieren → eingeloggt!

**Kein anderer Weg funktioniert. Keiner.**
