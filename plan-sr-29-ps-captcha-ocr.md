# Plan SR-29: PureSpectrum CAPTCHA OCR Solver

## Overview
Automatically read and submit PureSpectrum text CAPTCHAs. Blocks 12 current survey IDs.

## Problem Details

### Page Structure
```
screener.purespectrum.com/?survey_id=XXXXX
  → "Bitte geben Sie den folgenden Code in das Textfeld ein:"
  → <img src="data:image/png;base64,iVBORw0KGgo...">  (150×50px)
  → <input type="text" class="alpha-numeric-input border-0 border-bottom">
  → <button type="submit">Nächste</button>
```

### Image Details
- Format: PNG, base64 encoded in `src` attribute
- Size: ~150×50 pixels
- Content: 4-6 alphanumeric characters, possibly distorted/noisy
- Color: Typically black text on white/gray background with noise

## Solution Options

### A: Local pytesseract (recommended first attempt)
```python
import pytesseract
from PIL import Image
import base64, io

def ocr_captcha(ws_url):
    # Extract base64
    img_src = eval_js('document.querySelector("img[src^=\\"data:image\\"]").src')
    b64_data = img_src.split(',')[1]
    img_bytes = base64.b64decode(b64_data)
    
    # OCR with preprocessing
    img = Image.open(io.BytesIO(img_bytes))
    img = img.convert('L')  # grayscale
    img = img.point(lambda x: 0 if x < 128 else 255)  # threshold
    
    code = pytesseract.image_to_string(img, config='--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789')
    return code.strip()
```

### B: NVIDIA Omni Vision (backup)
```python
def ocr_nvidia(img_bytes):
    payload = {
        "model": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": "Read the alphanumeric code. Return ONLY the code."},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64.b64encode(img_bytes).decode()}"}}
            ]
        }]
    }
    # POST to https://integrate.api.nvidia.com/v1/chat/completions
```

### C: Gemini Vision (Google)
```python
def ocr_gemini(img_bytes):
    # Use sin-vision-colab skill — REST API, no browser needed
```

## Submit Function

```python
def submit_code(ws_url, code):
    js = f'''(function() {{
        var inp = document.querySelector("input[type=text]");
        inp.value = "{code}";
        inp.dispatchEvent(new Event("input", {{bubbles: true}}));
        inp.dispatchEvent(new Event("change", {{bubbles: true}}));
        document.querySelector("button[type=submit]").click();
    }})()'''
    eval_js(js)
```

## Integration

```python
# In provider_patterns.py
PURESPECTRUM = ProviderPattern(
    name='purespectrum',
    url_patterns=['screener.purespectrum.com'],
    captcha_handler=ps_captcha_solve,  # hook
    click_next='document.querySelector("button[type=submit]").click()',
    click_radio='...',
    fill_textarea='...',
)

# In survey_cdp.py
class SurveyCDP:
    def answer_page(self, ws, provider_pattern, persona):
        # Check for captcha first
        if provider_pattern.captcha_handler:
            if 'Code' in self.eval(ws, 'document.body.innerText'):
                code = provider_pattern.captcha_handler(ws)
                if code:
                    self.submit_code(ws, code)
                    time.sleep(3)
                    return
        # Normal answering...
```

## Implementation Steps

| Step | Task | Time |
|------|------|------|
| 1 | Install tesseract + pytesseract | 15min |
| 2 | Build extract + OCR pipeline | 1h |
| 3 | Test against real captchas (save PNGs from live surveys) | 30min |
| 4 | Build auto-submit + verify | 30min |
| 5 | Integrate into provider_patterns | 30min |
| 6 | End-to-end test | 30min |

**Total: ~3h**
