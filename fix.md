# fix.md - Bekannte Bugs & Fixes (2026-05-01)

## Gefixt

### P0: Omni reasoning-Feld Parsing
- **Bug**: `msg["content"]` ist null bei Nemotron Omni (antwortet in `reasoning`)
- **Fix**: `msg.get("reasoning") or msg.get("content") or ""`
- **Dateien**: `runner/live_omni_monitor.py`, `runner/nemotron_omni.py`, `runner/vision_client/core.py`
- **Status**: ✅ Omni API liefert jetzt korrekte Antworten

### P0: Model-Name doppelter Prefix → 404
- **Bug**: `**nvidia/nemotron (doppelter Prefix entfernt)**-3-nano-omni-30b-a3b-reasoning`
- **Fix**: `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`
- **Dateien**: `config/vision_models.yaml`, `runner/nemotron_omni.py`, `runner/live_omni_monitor.py`
- **Status**: ✅ HTTP 200, SSE funktioniert

### P0: SkylightDriver TypeError
- **Bug**: `SkylightDriver.__init__() missing 1 required positional argument: 'pid'`
- **Fix**: pid optional gemacht (default None)
- **Datei**: `runner/drivers/skylight.py`
- **Status**: ✅

### P0: vision_client/core.py dead code
- **Bug**: `_load_config()` wurde nie aufgerufen (nach return)
- **Fix**: In `__init__` verschoben
- **Datei**: `runner/vision_client/core.py`
- **Status**: ✅

### P1: cli/heypiggy-login nutzte osascript
- **Bug**: `osascript -e 'tell app "Google Chrome"...'` manipuliert Nutzer-Chrome
- **Fix**: Nur skylight-cli, PID als Argument
- **Datei**: `cli/heypiggy-login`
- **Status**: ✅

### P1: safe_click.py IndexError
- **Bug**: `PID = int(sys.argv[1])` ohne argv[1] → IndexError
- **Fix**: main()-Wrapper mit Fehlerbehandlung
- **Datei**: `runner/safe_click.py`
- **Status**: ✅

## Bekannte Bugs (ungelöst)
- [ ] skylight-cli `--output` Bug: Parameter wird ignoriert, schreibt immer `skylight_screenshot.png` ins CWD
- [ ] Dieses Modell (deepseek-v4-pro) kann keine Screenshots sehen → OmniVision als Workaround
- [ ] Survey-Loop nach Login noch nicht getestet (OmniSurveyRunner bereit)

## NIE TUN (semgrep blockiert)
- ❌ `**playstealth launch (isolierte PID)**"`
- ❌ `**BANNED – niemand importiert pyautogui**` / `**BANNED – niemand importiert pynput**`
- ❌ `**httpx an NVIDIA NIM**` / `**httpx an NVIDIA NIM**`
- ❌ `skylight-cli click --x ...` (Koordinaten)
- ❌ **skylight-cli** MCP
- ❌ Nutzer-Chrome manipulieren
- ❌ Ohne Primer klicken
- ❌ `recovery_mode: true`
