# registry-credentials.md — Credential & Auth Commands Registry

> **Category**: Auth/Credentials | **Master**: [registry.md](registry.md)

---

## C‑google‑login
**Command**: Google Login Flow (7 Steps, CUA-ONLY)
**File**: [cli/modules/auto_google_login.py](cli/modules/auto_google_login.py) (VERIFIED 6-Step CUA-ONLY Flow)
**Purpose**: Automatisierter Google Login für Heypiggy Dashboard
**Zugehörige Commands**: [infisical‑secrets](#c‑infisical‑secrets)

---

## C‑infisical‑secrets
**Command**: `sm-cli inject` / `sm-cli get`
**File**: [commands/infisical/secrets.md](commands/infisical/secrets.md)
**Purpose**: Secrets aus Infisical EU beziehen
**Zugehörige Commands**: [infisical‑login](#c‑infisical‑login)

---

## C‑infisical‑login
**Command**: `sm-cli login`
**File**: [commands/infisical/login.md](commands/infisical/login.md)
**Purpose**: Bei Infisical EU anmelden
**Zugehörige Commands**: [infisical‑secrets](#c‑infisical‑secrets)

---

## C‑heypiggy‑credentials
**File**: [commands/heypiggy/credentials.md](commands/heypiggy/credentials.md)
**Purpose**: Heypiggy Login Credentials (Email, Passwort)
**Enthält**: zukunftsorientierte.energie@gmail.com / ZOE.jerry2024

---

## 🔐 Sicherheitsregeln

- Secrets NIE in Logs ausgeben (Auto-Redaction aktiv)
- NIE `.env`-Dateien mit Secrets in Git commiten
- Infisical Token NIE teilen — jede Session neu via `sm-cli inject`

**Letztes Update**: 2026-05-05
