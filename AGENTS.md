# AGENTS.md — stealth-runner

## Architecture
- **StealthExecutor**: Wraps cua-driver CLI calls (click, screenshot, type_text, scroll)
- **VisionClient**: Cloudflare Llama 4 Scout (PRIMARY) / NVIDIA Mistral 675B (FALLBACK)
- **StateMachine**: IDLE → CAPTURE → VISION → EXECUTE → VERIFY → (loop) → DONE

## Stealth Triad
- `skylight-cli` → MVP: `cua-driver` (SkyLight framework, no cursor jump)
- `playstealth-cli` → Browser launch with fingerprint protection
- `unmask-cli` → Stealth verification and bot detection

## Usage
```bash
source .env  # HEYPIGGY_EMAIL, HEYPIGGY_PASSWORD, CF_TOKEN, NVIDIA_API_KEY
python3 main.py
```
