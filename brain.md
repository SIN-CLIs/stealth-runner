# brain.md — stealth-runner

## Architektur
Stealth Triade orchestrierter Survey-Runner (Greenfield-Reimplementation)

```
unmask-cli (sense) → playstealth-cli (think) → skylight-cli (act)
```

## State Machine
IDLE → CAPTURE → VISION → EXECUTE → VERIFY → (loop) → DONE

## Backends
- Primary: `skylight-cli` (Swift, CGEventPostToPid, kein Cursor-Sprung)
- Fallback: `cua-driver` (Python, SkyLight framework, kein Cursor-Sprung)

## StealthExecutor
- Auto-detection skylight-cli vs cua-driver
- Click by element-index (skylight) / element_id (cua-driver)
- Screenshot with SoM overlay (skylight-cli screenshot --mode som)
- JSON stdout contract, exit codes 0-5

## Vision Client
- Primary: Cloudflare Llama 4 Scout (FREE, 300 req/min)
- Fallback: NVIDIA Mistral 675B (~15s)
- SoM-aware prompts with element references [N] AXRole "text"

## sin_survey_core (aus A2A-SIN-Worker-heypiggy extrahiert)
- panels/detectors.py — PureSpectrum, Dynata, Sapio, Cint, Lucid, HeyPiggy
- rewards/extractor.py — EUR-Parsing aus Screenshots
- errors/templates.py — DQ/Quota/Attention-Fehler-Erkennung

## Crash Recovery
- State-Persistenz via ~/.stealth_runner/state.json
- Resume vom letzten State nach Crash
- Max 3 Recovery-Versuche

## GitHub Issues
- Epic #1: Stealth Triad Greenfield Build
- Tasks #2-#8: CLI docs, SoM, merge workflow, panel docs, error recovery

## Update: OCR-Grounding Integration (`8a8280a`)
- StealthExecutor unterstützt jetzt `screenshot(mode="ocr")`
- Dreistufiger Fallback: SoM → Grid → OCR
- Nutzt Apple Vision VNRecognizeTextRequest via skylight-cli
- `screenshot_ocr()` und `screenshot_grid()` convenience methods

## Gap-Status (Issue #76)
- ✅ #3 AX-Tree-Kollaps — Fixed in skylight-cli
- ✅ #2 OCR-Grounding — Implemented in skylight-cli + stealth-runner
- ⬜ #1 track calibration — Pending
- ⬜ #4 Right-click Chromium — Known limitation
- ⬜ #6 JA4 TLS Fingerprinting — Pending
- ⬜ #7 macOS Monitoring — Pending
