# Threat Model – stealth-runner v2.0
## STRIDE Analysis
- Spoofing: CLI-Spoofing → SHA256-Checksummen
- Tampering: Prompt-Injection → Hardening
- Info Disclosure: Credential-Leak → .gitignore
- DoS: API Rate-Limit → tenacity + NVIDIA fallback
- Elevation: N/A (user-level agent)
