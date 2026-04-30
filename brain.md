# brain.md — stealth-runner

## Backend: skylight-cli (PRIMARY)
- Kompiliert aus SIN-CLIs/skylight-cli (`swift build -c release`)
- Installiert in `~/.local/bin/skylight-cli`
- Auto-detection via `shutil.which("skylight-cli")`
- Targeted Window Capture via `CGWindowListCreateImage` (nur Chrome-Buffer)
- SoM-Screenshots mit AX-Elementen
- SkyLight `CGEventPostToPid` — kein Cursor-Sprung

## State Machine
IDLE → CAPTURE → VISION → EXECUTE → VERIFY → (loop) → DONE

## StealthExecutor
- `screenshot(mode="som"|"grid"|"ocr", capture_mode="window"|"display")`
- `click(element_id=N)` via skylight-cli
- `verify_stealth()` via unmask-cli (graceful fallback)

## Vision Client
- Cloudflare Llama 4 Scout (PRIMARY) / NVIDIA Mistral 675B (FALLBACK)
- SoM-aware prompts with AX element references

## Bugs Fixed (9/9)
1. ask_vision() hang → use ask_vision_text() internally
2. Chrome UI clicks → validate_click_coordinates()
3. AX-Tree collapse → _AXObserverAddNotificationAndCheckRemote
4. action["type"] KeyError → action.get("action")
5. Canvas-only UIs → OCR-Grounding (Apple Vision)
6. Grid overlay noise → disabled grid
7. cua_click() missing → added coordinate click
8. Wrong Chrome window → 4-stage fallback
9. Display capture leak → targeted window capture (skylight-cli)

## Tests: 18/18 PASS
