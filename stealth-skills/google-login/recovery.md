# recovery.md — Fehlerbehandlung

## Captcha erkannt
1. Screenshot aufnehmen: `skylight-cli screenshot --pid X --mode raw --out /tmp/captcha.png`
2. screen-follow pausieren (wenn aktiv)
3. Captcha manuell lösen oder Captcha-Solver aufrufen
4. Login fortsetzen

## 2FA erforderlich
1. 2FA-Code vom Nutzer anfordern
2. `type` in 2FA-Feld: `skylight-cli type --pid X --element-index N --text "123456"`
3. Enter/Weiter klicken

## Timeout
- 45s Timeout pro Schritt
- Bei Timeout: `list-elements` erneut → Zustand prüfen → fortsetzen oder FAIL
- Max 2 Retries

## Invalid Credentials
- Sofort abbrechen
- Nutzer informieren
- Keine weiteren Versuche (Account-Sperre vermeiden)
