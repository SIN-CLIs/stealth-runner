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

## Tests (18/18 PASSED)
- sin_survey_core: 12 tests (panel detection, EUR extraction, error classification)
- runner: 6 tests (StealthExecutor, VisionClient, AuditLog, HumanProfile)
- Run: `python3 tests/test_sin_survey_core.py && python3 tests/test_runner.py`

## Docs: fix.md + issues.md
- fix.md: 8 Bugs behoben (Tabelle aller Fixes mit Commits)
- issues.md: Alle Issues per Repo (Tabelle mit Status)

## Survivor #127: Continuous Stealth Verification ✅
- `StealthExecutor.verify_stealth()` — unmask-cli guard loop
- Graceful fallback if unmask-cli not installed
- Stealth breach triggers RECOVERY state

## Survivor Status
- #127: ✅ Closed (unmask guard loop)
- #148: ✅ Closed (error recovery)
- #153: ✅ Closed (sin_survey_core)
- #157: ✅ Closed (CONTRIBUTING.md)
- #160: ✅ Closed (SoM prompts)
- #164: ⬜ CLI help text
- #165: ⬜ CLI flags section
- #166: ⬜ CLI flags examples
- #167: ⬜ Epic tracker

## Issue #9 — P0-PRIVACY: Targeted Window Capture
- Bug: Full-Display Screenshot leak private Fenster an Vision-LLM
- Fix: PID-basierter Window Capture via `CGWindowListCreateImage`
- Status: OPEN
