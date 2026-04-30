# states.md — Google Login/Logout State Machine

## Zustände
```
IDLE → LOGOUT → LOGIN_PAGE → GOOGLE_CLICK → EMAIL → PASSWORD → DONE
  │        │         │            │            │         │
  └────────┴─────────┴────────────┴────────────┴─────────┘
                    CAPTCHA / 2FA (Recovery)
```

## Transitionen

| Von | Nach | Bedingung |
|-----|------|-----------|
| IDLE | LOGOUT | `--action logout` |
| LOGOUT | LOGIN_PAGE | Cookies gelöscht / Incognito |
| LOGIN_PAGE | GOOGLE_CLICK | Google-Login-Button gefunden |
| GOOGLE_CLICK | EMAIL | Popup geöffnet, Email-Feld sichtbar |
| EMAIL | PASSWORD | `type` erfolgreich, Google Auto-Advance |
| PASSWORD | DONE | `type` + `click` Weiter → eingeloggt |
| * | CAPTCHA | Captcha erkannt → recovery.md |
| * | FAIL | Invalid credentials / Timeout |
