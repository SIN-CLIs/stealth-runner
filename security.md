# security.md — Sicherheitsrichtlinien (Stealth Runner)

> **← [CONTRIBUTING.md](CONTRIBUTING.md) für Beitragsrichtlinien**

---

## 🔐 Credentials

- **NIE** Passwörter in Code oder .md-Dateien speichern
- **NIE** API-Keys in Git commiten
- Secrets via Infisical: [infisical.md](infisical.md)

## 🚫 Verbotene Aktionen

- NIE `pkill -f "heypiggy-bot"` → killt USER Chrome
- NIE `killall Google Chrome` → killt ALLE Chrome-Instanzen
- NIE `rm -rf ~/.stealth/` ohne vorherige Sicherung

## 🛡️ Chrome-Sicherheit

- BOT Chrome MUSS via `playstealth launch` gestartet werden
- User-data-dir MUSS in `~/tmp/chrome-instance-B (Profil 902 Kopie)` liegen
- BOT Chrome NIE mit User-Chrome-Profilen mischen

**Letztes Update**: 2026-05-05
