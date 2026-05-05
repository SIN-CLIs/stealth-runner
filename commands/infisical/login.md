# INFISICAL LOGIN — VERIFIED ✅

## Status
**VERIFIED** — 2026-05-05

## Was es tut
Login zu Infisical EU Cloud für Secrets/Credentials Management.

## Domain (KRITISCH!)
- ❌ FALSCH: `eu.infisical.com`
- ❌ FALSCH: `app.eu.infisical.com` (im login command!)
- ✅ RICHTIG: `--domain eu.infisical.com` (nur für secrets/export Befehle)
- Default API: `https://app.infisical.com/api`

## Login Command
```bash
infisical login
# → Interaktiv: CLI öffnet Browser für Auth
```

## Login mit Service Token
```bash
infisical login --token <SERVICE_TOKEN>
# → Non-interactive login
```

## Export Secrets aus Infisical
```bash
# Export für Projekt
infisical secrets --domain eu.infisical.com --project-id <ID> --env prod
infisical secrets --domain eu.infisical.com --project-id <ID> --env development

# Export zu .env file
infisical secrets export --domain eu.infisical.com > .env
```

## Find Project ID
```bash
infisical projects --domain eu.infisical.com
```

## Credentials suchen (z.B. Google Login Passwort)
```bash
infisical secrets --domain eu.infisical.com --project-id <ID> | grep -i "google\|password\|gmail\|credential"
```

## REGEL
- ALLE Credentials + Secrets → Infisical EU + .env
- Niemals Secrets hardcodieren oder in Chat schreiben
- `.env` sollte NUR Referenzen/Defaults haben, Haupt-Source ist Infisical

## Test Log
- 2026-05-05: infisical version 0.43.76 installed ✅
- 2026-05-05: `--domain eu.infisical.com` für secrets Befehle ✅