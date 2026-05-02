# issues.md – Offene Issues & Known Bugs

## 🔴 KRITISCH – call_omo_agent BROKEN (9/9 Timeouts)
- Alle 9 `call_omo_agent` Tasks timed out nach 30min
- explore, librarian, oracle – ALLE betroffen
- Workaround: Direkte Tool-Nutzung (grep, ast-grep, lsp, bash)

## 🟡 Google OAuth 2FA – Manuelle Intervention nötig
- Bei Accounts mit aktivierter 2FA kann cua-driver den zweiten Faktor nicht lösen
- Passkey-Abfrage (Touch ID) nicht automatisierbar
- Lösung: Consent-Flow nutzen (Email reicht bei bestehenden Cookies)

## 🟡 skylight-cli v0.2.0 Bug: --output ignoriert
- `skylight-cli screenshot --output /tmp/x.png` schreibt nach `./skylight_screenshot.png`
- Workaround: `_screenshot_with_workaround()` in `skylight.py`

## 🟢 Survey Loop nach Login
- Login funktioniert jetzt via cua-driver
- Survey-Automation muss getestet werden
- `PYTHONPATH=. python3 runner/step.py "https://heypiggy.com/?page=dashboard"`

## 🟢 Motion Detection Tuning validieren
- Neue Thresholds (20.0/3.0) müssen mit echten Surveys getestet werden
- JPEG quality=40 muss auf Survey-Bildern validiert werden