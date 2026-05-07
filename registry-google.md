# registry-google.md — Google Commands Registry

> **Category**: Auth/Google | **Master**: [registry.md](registry.md)

---

## C‑google‑login
**Command**: Google OAuth Login (7 Steps, PASSKEY Edition)
**File**: [cli/modules/auto_google_login.py](cli/modules/auto_google_login.py) (VERIFIED 6-Step CUA-ONLY Flow)
**Purpose**: Automatisierter Google Login via CUA (Email → Passkey → Consent → Dashboard)
**Zugehörige Commands**: [registry-credentials.md](registry-credentials.md)

---

## Google OAuth Flow

1. Heypiggy → Google Login-Symbol klicken
2. Email eintragen (zukunftsorientierte.energie@gmail.com)
3. "Weiter" → Keychain Auto-Fill → Passkey
4. "Weiter" (Passkey-Bildschirm, NICHT "Andere Option wählen"!)
5. "Fortfahren" (Account bestätigen)
6. "Weiter" (Consent)
7. Dashboard geladen → "Abmelden" sichtbar

**Letztes Update**: 2026-05-05
