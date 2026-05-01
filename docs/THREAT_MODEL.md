# Threat Model – stealth-runner v0.3.1

## STRIDE Analysis

- Spoofing: CLI-Spoofing → SHA256-Checksummen
- Tampering: Prompt-Injection → Hardening
- Info Disclosure: Credential-Leak → .gitignore
- DoS: API Rate-Limit → tenacity + NVIDIA fallback
- Elevation: N/A (user-level agent)
