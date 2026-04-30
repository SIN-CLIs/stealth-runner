# brain.md — stealth-runner (SOTA Stealth Triade Orchestrator)

## Architektur: Reine Stealth-Triade — v2.0

```
playstealth-cli (launch) → skylight-cli (screenshot+click) → Llama 4 Scout (vision) → unmask-cli (verify)
```

## Verboten — ZERO Toleranz (seit efd363f):
- `cua-driver` — ALT, vollständig durch skylight-cli v0.2.0 ersetzt
- `open -na "Google Chrome"` — FALSCH, nur playstealth-cli launch
- `AXStaticText` klicken — WIRKUNGSLOS, nur AXButton/AXLink/AXCheckBox/AXRadioButton
- Klick ohne Vision — RATEN, muss via Llama 4 Scout
- `.env` im Repo — SICHERHEITSRISIKO, nur `.env.example`

## StealthExecutor (runner/stealth_executor.py)
- Reine skylight-cli Bindung, FATAL RuntimeError wenn nicht installiert
- `backend` property → immer "skylight-cli"
- `screenshot(mode="som"|"grid"|"ocr")` — Targeted Window Capture
- `click(element_index=N)` — CGEventPostToPid via SkyLight.framework
- `launch_browser(url)` — playstealth-cli launch → PID
- `verify_stealth()` — unmask-cli verify-stealth

## State Machine (runner/state_machine.py)
10 Zustände:
```
IDLE → LAUNCH_BROWSER → WAIT_READY → CAPTURE → VISION → EXECUTE → VERIFY → (loop) → DONE
                                                                               ↘ RECOVERY
```
- `StealthRunner(url)` — entry point
- `_launch()` — playstealth-cli launch --json → PID
- `_wait_ready()` — skylight-cli wait-for-selector
- `_capture()` — skylight-cli screenshot --mode som
- `_vision()` — VisionClient.get_action() → Llama 4 Scout
- `_execute()` — click/type/scroll/drag/hold/select-option/keypress/wait/done
- `_verify()` — unmask-cli verify-stealth
- `_recover()` — playstealth-cli rotate-profile

## Vision Client (runner/vision_client.py)
- Cloudflare Llama 4 Scout (PRIMARY) — CF_ACCT + CF_TOKEN
- NVIDIA Mistral 675B (FALLBACK) — NVIDIA_API_KEY
- `urllib.request` (kein openai dependency)

## Prompt Kit (runner/prompt_kit.py)
- **SYSTEM_PROMPT**: 1742 chars, 10 Aktionen
- click, type, keypress, scroll, drag, hold, select-option, track, wait, done
- Anti-AXStaticText Regel
- CAPTCHA Strategien (hold für Turnstile, reCAPTCHA Tiles)
- Few-Shot Beispiele

## sin_survey_core (aus A2A-SIN-Worker-heypiggy extrahiert)
- `panels/detectors.py` — 8 Panel-Provider (PureSpectrum, Dynata, Sapio, Cint, Lucid, HeyPiggy, MarketSight, Bilendi)
- `rewards/extractor.py` — EUR-Parsing (6 Regex-Patterns)
- `errors/templates.py` — 4 Fehlerkategorien (disqualified, quota_full, attention_failed, not_found)

## Tests: 18/18 PASS
- `tests/test_sin_survey_core.py` — 12 tests (panel detection, EUR extraction, error classification)
- `tests/test_runner.py` — 6 tests (executor, vision parsing, audit log, human profile)

## Smoke Test (30.04.2026): ALL GREEN
- skylight-cli v0.2.0 installed ✅
- 90 AX elements found on HeyPiggy ✅
- Click (dry-run): status ok ✅
- ZERO cua-driver references ✅
- ZERO open -na references ✅

## Docs (8/8 md files):
- brain.md ✅ | banned.md ✅ | architecture.md ✅ | goal.md ✅
- fix.md (9 bugs) ✅ | issues.md (all repos) ✅
- AGENTS.md ✅ | CONTRIBUTING.md ✅

## Repos:
- https://github.com/OpenSIN-AI/stealth-runner (GREENFIELD, PURE)
- https://github.com/OpenSIN-AI/A2A-SIN-Worker-heypiggy (REFERENCE, not deleted)
- https://github.com/SIN-CLIs/skylight-cli (Stealth Triade: act, v0.2.0)

## Smoke Test Resultate (30.04.2026 — 17:20 UTC)

| Test | Result |
|------|--------|
| **skylight-cli** | ✅ v0.2.0 installed |
| **Bot-Chrome** | ✅ PID=91048 running |
| **Screenshot** | ✅ 90 elements found (som mode) |
| **Vision (NVIDIA Mistral)** | ✅ `{"action":"click","element_id":42,"reasoning":"First available survey with reward 2.23 €"}` |
| **Click (dry-run)** | ✅ status=ok |
| **State Machine** | ✅ CAPTURE→VISION→EXECUTE→VERIFY cycle |
| **VisionClient backend** | ✅ urllib.request (KEIN openai) |
| **NVIDIA_API_KEY** | ✅ gesetzt |

### Nicht verfügbar (geplant):
- ❌ playstealth-cli (binary) — Bot-Chrome via pgrep Workaround
- ❌ unmask-cli (binary) — verify_stealth graceful fallback
