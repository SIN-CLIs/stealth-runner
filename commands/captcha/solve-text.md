# captcha-solve-text.md — Text Captcha mit Mistral pixtral-large ✅

## Status
**VERIFIED** — 2026-05-05, PureSpectrum Captcha "QXem34"

## Command
```bash
# 1. Captcha-Bereich screenshotten
screencapture -R"<x>,<y>,<w>,<h>" /tmp/captcha.png

# 2. pixtral-large Vision API aufrufen
python3 -c "
import base64, httpx
with open('/tmp/captcha.png','rb') as f:
    b64 = base64.b64encode(f.read()).decode()
r = httpx.post('https://api.mistral.ai/v1/chat/completions',
    headers={'Authorization': 'Bearer \$MISTRAL_API_KEY', 'Content-Type': 'application/json'},
    json={'model': 'pixtral-large-latest',
          'messages': [{'role': 'user', 'content': [
              {'type': 'text', 'text': 'Read the captcha code shown in this image. Return ONLY the text, nothing else.'},
              {'type': 'image_url', 'image_url': f'data:image/png;base64,{b64}'}]}],
          'max_tokens': 20, 'temperature': 0}, timeout=15)
print(r.json()['choices'][0]['message']['content'].strip())
"

# 3. Captcha-Code ins Textfeld eingeben
echo '{"pid": PID, "window_id": WID, "element_index": IDX, "value": "CODE"}' | cua-driver call set_value
```

## Live Example (PureSpectrum, 2026-05-05)
```bash
# Captcha: "Bitte geben Sie den folgenden Code in das Textfeld ein"
# Element: [35] AXTextField "Type the characters you see in the image"
# Image: [30] AXImage "PS Captcha" @(584,305,150,50)

screencapture -R"520,280,320,120" /tmp/captcha_fresh.png
# → pixtral-large: "QXem34"

echo '{"pid": 78708, "window_id": 57128, "element_index": 35, "value": "QXem34"}' | cua-driver call set_value
# → ✅ Set AXValue — Next button enabled
```

## Modelle getestet

| Modell | Ergebnis | Bewertung |
|--------|----------|-----------|
| **pixtral-large-latest** | "QXem34" ✅ | BESTE — liest korrekt |
| mistral-small-latest | "XerBA" ❌ | Falsch |
| txtcaptcha (CRNN) | "c7334" ❌ | Lokaler OCR-Versuch, ungenau |
| gemini-2.0-flash | Error | API-Fehler |
| nvidia/neva-22b | Leer | Keine Antwort |
| nvidia/nemotron-omni | Leer | Keine Bildunterstützung im Setup |

## Voraussetzungen
- `MISTRAL_API_KEY` in `~/.stealth/.env`
- `screencapture` (macOS built-in)
- `cua-driver` Daemon muss laufen

## Zugehörige Commands
- [captcha-solve-drag.md](captcha-solve-drag.md) — Drag & Drop Captcha
- [captcha-solve-geetest.md](captcha-solve-geetest.md) — GeeTest v4 Slider
- [cua-driver/set-value.md](../cua-driver/set-value.md) — Text in Feld eingeben
- [cua-driver/click.md](../cua-driver/click.md) — Button klicken
