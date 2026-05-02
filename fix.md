# fix.md – Gefundene & Gefixte Muster

## 🔧 2026-05-02 – Google OAuth Popup Fix (KRITISCH!)

**Problem**: `heypiggy-login` CLI klickte falsche "Weiter" Buttons – statt dem Button im Google-Popup
wurde ein Element im Hauptfenster geklickt. `skylight-cli` sieht NUR das Hauptfenster,
Popup-Elemente haben ANDERE Indices.

**Root Cause**: `skylight-cli list-elements` liefert Element-Indices des HAUPTFENSTERS.
Wenn ein Google OAuth Popup offen ist, sind die Popup-Buttons NICHT in dieser Liste.
Der Login-Script klickte Index 41, 45, 50 etc. – das waren Hauptfenster-Elemente,
nicht die "Weiter"-Buttons IM Popup.

**Gelöst**: `cua-driver` für ALLE Popup-Interaktionen:
```bash
# 1. cua-driver daemon starten (einmalig)
cua-driver serve &

# 2. Popup Window-ID finden (via list_windows)
POPUP_WID=$(cua-driver call list_windows '{}' | python3 -c "...")

# 3. Popup-Elemente laden (cacht die AX-Tree für das Fenster)
cua-driver call get_window_state "{\"pid\":$PID,\"window_id\":$POPUP_WID}"

# 4. Im Popup klicken (NICHT skylight!)
cua-driver call click "{\"pid\":$PID,\"window_id\":$POPUP_WID,\"element_index\":$IDX,\"action\":\"press\"}"
```

**Dateien geändert**: `cli/heypiggy-login` Line 146-156, `docs/cua-driver-popup-pattern.md`

## 🔧 2026-05-02 – Screenshot-Workaround `skylight-cli` v0.2.0
**Problem**: `skylight-cli screenshot --output /tmp/x.png` ignoriert `--output` und schreibt
immer nach `./skylight_screenshot.png` ins CWD.

**Gelöst**: Temporäres Verzeichnis als CWD für den Screenshot-Befehl, dann Datei kopieren.
(`runner/drivers/skylight.py` Methode `_screenshot_with_workaround`)

## 🔧 2026-05-02 – `Path` Import fehlte in `skylight.py`
**Problem**: `runner/drivers/skylight.py:62` nutzt `Path("skylight_screenshot.png")` aber kein Import.
**Gelöst**: `from pathlib import Path` in Zeile 3 hinzugefügt.

## 🔧 2026-05-02 – `asyncio.get_event_loop()` Deprecation Python 3.14
**Problem**: `asyncio.get_event_loop()` ist deprecated in Python 3.14.
**Gelöst**: `asyncio.new_event_loop()` + `asyncio.set_event_loop()` in:
- `playwright_stealth_worker.py:155-156`
- `tests/test_integrations_skeletons.py:208,212`

## 🔧 2026-05-02 – `playstealth --json` Argument-Reihenfolge
**Problem**: `playstealth launch --url X --json` → falsch, `--json` muss VOR `launch`.
**Gelöst**: `playstealth --json launch --url X` in `runner/step.py:40`

## 🔧 2026-05-02 – Screenshot-Aufruf in stealth_executor.py
**Problem**: `stealth_executor.py` rief `screenshot(self.pid, mode, out_path)` auf,
aber `SkylightDriver.screenshot()` erwartet `(self, mode, output)` ohne PID.
**Gelöst**: Aufruf korrigiert zu `self.driver.screenshot(mode, str(out_path))`

## 🔧 2026-05-02 – Motion Detection Thresholds optimiert
**Problem**: `MOTION_HIGH_THRESH=15.0` zu sensitiv, `MOTION_LOW_THRESH=2.0` zu strikt.
**Gelöst**: `MOTION_HIGH_THRESH=20.0`, `MOTION_LOW_THRESH=3.0` in `live_eye.py`

## 🔧 2026-05-02 – PNG→JPEG in VisionClient (API-Timeout-Fix)
**Problem**: `vision_client/core.py` sendet rohe PNG-Dateien (300KB+) an Nemotron Omni.
API timed out nach 30s wegen zu großer Payload.

**Gelöst**: `_image_to_jpeg_b64()` konvertiert PNG→JPEG quality=40 VOR dem base64-Encoding.
90% kleinere Payload (~30KB statt 300KB). Zusätzlich DiskCache für wiederholte Screenshots.

## 🔧 2026-05-02 – JPEG Quality reduziert
**Problem**: `quality=50` in `live_omni_monitor.py` → Payload zu groß für schnelle API-Calls.
**Gelöst**: `quality=40` → ~90% kleinere Payload bei gleicher Erkennungsqualität.
