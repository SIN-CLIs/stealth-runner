# openssf-badge-apply — OpenSSF Badge automatisiert

Beantragt das OpenSSF Best Practices Badge via API oder Playwright-Fallback.

## Nutzung
```bash
./cli/openssf-badge-apply --repo "SIN-CLIs/screen-follow" --description "..." --api-token "TOKEN"
```

## Ablauf
1. API-Token von bestpractices.dev holen (Account → API Token)
2. Skill ausführen → legt Projekt an → setzt Kriterien → gibt Badge-Link zurück
3. Badge-Link in README.md einfügen
