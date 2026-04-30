# brain.md — stealth-runner

## ARCHITEKTUR: Reine Stealth-Triade
```
playstealth-cli (launch) → skylight-cli (act) → unmask-cli (verify)
```

## VERBOTEN (NIEMALS):
- cua-driver — ALT, ersetzt durch skylight-cli v0.2.0
- open -na "Google Chrome" — FALSCH, nur playstealth-cli launch
- AXStaticText klicken — WIRKUNGSLOS, nur AXButton/AXLink/AXCheckBox/AXRadioButton
- Klick ohne Vision — RATEN, muss via Llama 4 Scout

## PIPELINE:
1. playstealth-cli launch → PID
2. skylight-cli screenshot --mode som → Bild mit Element-IDs
3. Llama 4 Scout → element_id
4. skylight-cli click --element-index ID
5. unmask-cli verify-stealth

## StealthExecutor:
- Nur skylight-cli (kein cua-driver Fallback)
- Window Capture via CGWindowListCreateImage
- Click via CGEventPostToPid (SkyLight.framework)

## State Machine:
IDLE → CAPTURE → VISION → EXECUTE → VERIFY → DONE

## Vision Client:
- Cloudflare Llama 4 Scout (PRIMARY)
- NVIDIA Mistral 675B (FALLBACK)
- SoM-aware prompts

## sin_survey_core:
- panels/detectors.py — PureSpectrum, Dynata, Sapio, Cint, Lucid, HeyPiggy
- rewards/extractor.py — EUR-Parsing
- errors/templates.py — DQ-Erkennung

## Tests: 18/18 PASS

## SYSTEM_PROMPT: 1742 chars, 10 actions
- click, type, keypress, scroll, drag, hold, select-option, track, wait, done
- Anti-AXStaticText regel
- Captcha strategies (hold, reCAPTCHA tile click)
- Few-shot examples

## StealthRunner class (renamed from SurveyRunner)
- LAUNCH_BROWSER → playstealth-cli launch
- WAIT_READY → skylight-cli wait-for-selector
- 10-state machine: IDLE→LAUNCH→WAIT→CAPTURE→VISION→EXECUTE→VERIFY→(loop)→DONE
