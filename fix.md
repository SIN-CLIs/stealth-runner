# fix.md - Bekannte Bugs & Fixes (2026-05-01)

## P0: Popup-Fenster-Bug (GEFIXT)
- **Bug**: Google Login Popup öffnet sich, skylight-cli klickt "Weiter" auf der HEPIGGY-Seite statt im Popup
- **Ursache**: skylight-cli hat keinen `--window-id` Parameter, returned Elemente AUS ALLEN Fenstern
- **Fix**: cua-driver nutzen (hat `--window-id` + `--element-index` Support)
  ```python
  # ALT (falsch): Klickt in Hauptseite statt Popup
  skylight-cli click --pid 42296 --element-index 39  # → Weiter auf Heypiggy-Seite!
  
  # NEU (richtig): Klickt GARANTIERT im Google Popup
  cua-driver click --pid 42296 --window-id 30380 --element-index 35  # → Weiter im Popup!
  ```
- **Dateien**: `runner/trio_live.py`, `banned.md`, `brain.md`
- **Status**: ✅ cua-driver mit window-id fix

## P0: Omni reasoning-Feld Parsing
- **Bug**: `msg["content"]` ist null bei Nemotron Omni (antwortet in `reasoning`)
- **Fix**: `msg.get("reasoning") or msg.get("content") or ""`
- **Dateien**: `runner/live_omni_monitor.py`, `runner/nemotron_omni.py`, `runner/vision_client/core.py`
- **Status**: ✅

## P0: Model-Name doppelter Prefix → 404
- **Bug**: `nvidia/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`
- **Fix**: `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`
- **Dateien**: `config/vision_models.yaml`, `runner/nemotron_omni.py`
- **Status**: ✅

## P0: SkylightDriver TypeError
- **Bug**: `SkylightDriver.__init__() missing 1 required positional argument: 'pid'`
- **Fix**: pid optional gemacht (default None)
- **Datei**: `runner/drivers/skylight.py`
- **Status**: ✅

## cua-driver: Wann erlaubt, wann nicht
- ✅ **ERLAUBT**: `cua-driver get_window_state --pid --window-id`
- ✅ **ERLAUBT**: `cua-driver click --pid --window-id --element-index`
- ❌ **BANNED**: `cua-driver click --x --y` (Koordinatenraten)
