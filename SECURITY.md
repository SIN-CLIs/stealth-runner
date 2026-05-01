# Security Policy

## Supported Versions: 0.2.x ✅ Active

## Responsible Disclosure: openssin@proton.me (verschlüsselt)

## Threat Model Summary

| Vektor           | Schwere  | Mitigation                   |
| ---------------- | -------- | ---------------------------- |
| CLI-Spoofing     | Kritisch | SHA256-Checksummen (geplant) |
| Prompt-Injection | Hoch     | Prompt-Hardening             |
| Credential-Leak  | Hoch     | .gitignore, .env.example     |
| Rate-Limit       | Mittel   | tenacity Retry               |
