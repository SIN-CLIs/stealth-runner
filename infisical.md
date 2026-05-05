# infisical.md — Infisical Secrets Management

> **← [commands/infisical/](commands/infisical/) für CLI-Commands**

---

## 🔑 Infisical im Stealth Suite Ökosystem

**Infisical** ist das zentrale Secrets-Management für alle Stealth Suite Repos.
Credentials werden NIE in .env-Dateien oder Code gespeichert, sondern über Infisical EU bezogen.

### Konfiguration

```bash
# Infisical EU API
export INFISICAL_API_URL="https://eu.infisical.com/api"
export INFISICAL_TOKEN="st.xxx..."
export INFISICAL_PROJECT_ID="xxx..."
export INFISICAL_ENV="dev"  # oder prod, staging
```

### CLI Commands

| Command | Zweck | File |
|---------|-------|------|
| `sm-cli get` | Secrets abrufen (redacted) | [infisical/secrets.md](commands/infisical/secrets.md) |
| `sm-cli inject` | Secrets als export-Statements | [infisical/secrets.md](commands/infisical/secrets.md) |
| `sm-cli login` | Bei Infisical anmelden | [infisical/login.md](commands/infisical/login.md) |
| `sm-cli sync` | Cache aktualisieren | [infisical/secrets.md](commands/infisical/secrets.md) |

### Wichtige Secrets

| Secret | Environment | Verwendung |
|--------|-------------|------------|
| `HEYPIGGY_EMAIL` | Development | Google Login Email |
| `HEYPIGGY_PASSWORD` | Development | Google Login Passwort |
| `NVIDIA_API_KEY` | Alle | NVIDIA NIM Vision API |

### Sicherheit

- Secrets werden NIE im Klartext in Logs ausgegeben (Auto-Redaction)
- Lokaler Cache: Fernet-Verschlüsselt (AES-128-CBC)
- Cache-TTL: 3600s (konfigurierbar via `SM_CACHE_TTL`)

**Letztes Update**: 2026-05-05
