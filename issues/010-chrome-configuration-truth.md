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
| AGENTS.md (neu) | 9999 | 902 Kopie | HeyPiggy (FALSCH) |
| Session-Test | 9224 | 902 | HeyPiggy (korrekt) |
| Aktuell (Backup) | 9999 | /tmp/heypiggy-new-* | Isoliert (tot) |

---

## Die Wahrheit (aus Session-DB extrahiert)

### Profile 901 (Jeremy) = HeyPiggy
- **User Data Dir**: `/Users/jeremy/Library/Application Support/Google Chrome`
- **Profile**: `Profile 901 (Jeremy)`
- **CDP Port**: 9222 (automatisch von Chrome gewählt)
- **Eigentümer**: jeremy (NICHT simoneschulze!)
- **Status**: Eingeloggt, 2.23€ Balance, 12 Surveys

### Profile 902 = SIN-Agent Heypiggy (nicht aktiv)
- **User Data Dir**: Gleiches Verzeichnis
- **Profile**: `Profile 902`
- **Status**: Cookies vorhanden, aber KEIN Prozess aktiv
- **Warum**: Chrome erlaubt nur EINEN Prozess pro user-data-dir

---

## Warum die Verwirrung?

1. **Dual-Instance Setup**: Zwei Profile im gleichen user-data-dir
2. **SingletonLock**: Chrome blockiert zweiten Prozess
3. **Kopie-Lösung**: `launch_parallel.py` kopiert Profil 902 → `~/tmp/chrome-instance-B`
4. **Cookie-Verschlüsselung**: Kopie hat VERSCHLÜSSELTE Cookies → Login nötig

---

## Korrekte Konfiguration (aus Session)

### Für HeyPiggy (Survey-Automation):
```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9999 \
  --remote-allow-origins="*" \
  --force-renderer-accessibility \
  --no-first-run \
  --user-data-dir="/Users/jeremy/Library/Application Support/Google Chrome" \
  --profile-directory="Profile 901 (Jeremy)" \
  "https://www.heypiggy.com/?page=dashboard"
```

**WICHTIG**:
- Port 9999 ist der API-Standard (nicht 9222)
- Profile 901 ist das aktive HeyPiggy-Profil (nicht 902)
- `--force-renderer-accessibility` MUSS gesetzt sein (für CUA)
- `--remote-allow-origins="*"` MIT Quotes (zsh glob expand!)

---

## Cookie-Management

### Extraktion (funktioniert nur von ORIGINAL, nicht Kopie):
```python
# Port 9999 (HeyPiggy-Instanz)
curl -s http://127.0.0.1:9999/json/list
# → WebSocket URL finden
# → Network.getAllCookies
```

### Backup-Standorte:
```
Working:  agent-toolbox/data/heypiggy-cookies.json
Backup:   ~/.stealth/heypiggy-backup/heypiggy-cookies-master.json (chmod 444)
```

### Recovery-Protokoll:
1. Session validieren: "Abmelden" sichtbar?
2. Wenn TOT: Nichts speichern!
3. Chrome beenden (PID, nicht pkill!)
4. Working-Cookies LÖSCHEN
5. Backup → Working kopieren
6. Chrome neu starten

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
- `--user-data-dir=/tmp/...` für HeyPiggy — verliert Cookies
- Profile 902 für HeyPiggy — ist nicht das aktive Profil
