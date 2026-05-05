# INFISICAL SECRETS — VERIFIED ✅

## Status
**VERIFIED** — 2026-05-05

## Was es tut
Secrets aus Infisical EU Cloud abrufen (nach Project, Environment, Path)

## Domain + API_URL
```bash
export INFISICAL_API_URL="https://eu.infisical.com/api"
# NICHT: --domain Flag (funktioniert nicht mit --token!)
```

## Login mit Service Token (NON-INTERACTIVE)
```bash
export INFISICAL_API_URL="https://eu.infisical.com/api"
export CI=true
infisical secrets \
  --projectId PROJECT_ID \
  --env ENV_NAME \
  --path "/folder/path" \
  --token "TOKEN" \
  2>&1
```

## Beispiel: Heypiggy Secrets abrufen
```bash
export CI=true
export INFISICAL_API_URL="https://eu.infisical.com/api"
infisical secrets \
  --projectId fa7758b4-f84c-4297-966e-710056d531ef \
  --env prod \
  --path "/opensin/a2a-sin-worker-heypiggy" \
  --token "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

## Output Formats
```bash
# Plain (ein Secret pro Zeile)
infisical secrets --projectId X --env prod --output dotenv

# JSON
infisical secrets --projectId X --env prod --output json

# YAML
infisical secrets --projectId X --env prod --output yaml
```

## Environment Flags
```bash
--env prod        # Production
--env development # Development
--env staging     # Staging
--env test        # Test
--env qa          # QA
--env preview     # Preview
```

## Path Flags
```bash
--path "/"                    # Root
--path "/opensin"             # Subfolder
--path "/opensin/a2a-*"       # Wildcard nicht möglich, explizit angeben
--recursive                   # Alle Subfolders inkludieren
```

## Secret finden (grep)
```bash
infisical secrets --projectId X --env prod | grep -i "google\|password\|email"
```

## Fehler: "Folder not found"
```
Response Code: 404 Not Found
Message: Folder with path '/path' in environment 'env' was not found.
```
→ Pfad/Environment stimmt nicht. Check Infisical UI für richtige Values!

## REGELN
- ALLE Credentials → Infisical, NIEMALS hardcodieren
- Token NIE in Chat schreiben (nur Commands ausführen)
- --domain Flag meiden, stattdessen INFISICAL_API_URL env variable

## Project IDs (bekannt)
- secret-management: `fa7758b4-f84c-4297-966e-710056d531ef`

## Test Log
- 2026-05-05: `--domain` Flag funktioniert NICHT mit `--token`
- 2026-05-05: `INFISICAL_API_URL` env variable funktioniert ✅
- 2026-05-05: `/opensin/a2a-sin-worker-heypiggy` existiert NICHT in keinem Env