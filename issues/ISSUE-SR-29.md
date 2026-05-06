# ISSUE-SR-29: PureSpectrum CAPTCHA OCR Solver

| Feld | Wert |
|------|------|
| **ID** | SR-29 |
| **Priority** | 🔴 P0 — Critical |
| **Status** | 📋 TODO |
| **Created** | 2026-05-06 |
| **Labels** | `captcha`, `ocr`, `purespectrum`, `blocker` |
| **Plan** | `plan-sr-29-ps-captcha-ocr.md` |

## Problem
PureSpectrum (`screener.purespectrum.com`) zeigt eine Text-CAPTCHA (`data:image/png;base64,...`) mit der Aufforderung "Bitte geben Sie den folgenden Code ein". Der Code ist ein alphanumerischer String in einem 150×50px PNG. NVIDIA Vision API gab 404. Ohne Lösung sind **alle 12 aktuellen Survey-IDs** blockiert.

## Subissues

### SR-29.1 — Image Extraction
- [ ] `extract_captcha_img(ws_url)` → base64 PNG bytes
- [ ] CDP: `document.querySelector("img[src^='data:image/png']").src`
- [ ] Base64-Dekodierung → PNG-Bytes speichern
- [ ] Image-Validierung (mindestens 1000 Bytes)

### SR-29.2 — OCR Engine Selection
- [ ] **Option A**: `pytesseract` — local OCR, `brew install tesseract` + `pip install pytesseract`
- [ ] **Option B**: NVIDIA Omni Vision — `nvidia/llama-3.2-11b-vision-instruct` (API korrigieren)
- [ ] **Option C**: Google Vision API — Cloud OCR
- [ ] Test: Alle drei gegen echte Captcha-Bilder benchmarken
- [ ] Entscheiden basierend auf Accuracy + Speed

### SR-29.3 — Auto-Submit
- [ ] `solve_captcha(ws_url)` → Code lesen → `input.value = code` → Submit
- [ ] `input[type=text].value = code` + Event("input") + Event("change")
- [ ] `button[type=submit].click()`
- [ ] Verify: `document.body.innerText` nicht mehr "Bitte geben Sie den Code ein"

### SR-29.4 — Integration
- [ ] In `provider_patterns.py`: `PURESPECTRUM` Pattern mit captcha_handler
- [ ] In `survey_cdp.py`: automatischer Captcha-Solve vor Frage-Beantwortung
- [ ] Retry-Logik: 3 Versuche bei falschem Code

## Acceptance Criteria
- [ ] Captcha-Bild erfolgreich aus DOM extrahiert
- [ ] OCR erkennt Code mit >80% Accuracy
- [ ] Auto-Submit funktioniert in < 5 Sekunden
- [ ] Integration in Survey-Loop: Captcha automatisch gelöst

## Blocked By
- Installation von `pytesseract` + `tesseract`
- NVIDIA API Key / Vision Model Korrektur

## Betroffene Files
- `cli/modules/ps_captcha.py` → NEU
- `cli/modules/provider_patterns.py` → Update (PURESPECTRUM)
- `cli/modules/survey_cdp.py` → Update (captcha hook)
