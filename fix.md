# fix.md – ALL Fixes (2026-05-02)

## 🔧 CRITICAL: Survey Questions Need TEXT Answers Too!

**Problem**: step.py klickte immer nur "Go to next question" aber die Umfrage fragte
nach "Jährliches Einkommen: € ____" – ein TEXTFELD. Ohne Texteingabe bleibt die Seite hängen.

**Root Cause**: Der Prompt fragte nur nach "click" Actions. Der Model erkannte nicht,
dass auch `type`-Actions nötig sind.

**Gelöst**: Omni fragt zuerst nach der Seitenbeschreibung (`Describe EXACTLY what you see...`),
dann wird die passende Action (click|type) ausgeführt.

## 🔧 Image Resize (50%) – API Timeout Fix
**Problem**: 1200×1006 PNG → 300KB → Omni API timeout.
**Gelöst**: `img.thumbnail((960,960))` in `_image_to_jpeg_b64()` → JPEG ~67KB, kein Timeout.

## 🔧 Page Detection in step.py
**Problem**: step.py nahm an, immer auf heypiggy.com zu sein. Tatsächlich
redirected HeyPiggy zu PureSpectrum (Drittanbieter-Umfrage). Prompt war falsch.
**Gelöst**: `skylight-cli list-elements` nach jedem Screenshot → `state["page"]`
wird an `build_prompt()` übergeben.

## 🔧 Nemotron Omni: content vs reasoning Priority
**Problem**: `_call_model()` nutzte `msg.get("reasoning") or msg.get("content")`.
Nemotron Omni schreibt JSON-Antwort in `content`, Reasoning-Text in `reasoning`.
**Gelöst**: `msg.get("content")` hat PRIORITY vor `msg.get("reasoning")`.

## 🔧 max_tokens=300 → 1000
**Problem**: Reasoning-Model braucht ~400 Tokens zum Denken + ~100 Tokens für JSON.
Bei 300 Tokens wurde die JSON-Antwort abgeschnitten.
**Gelöst**: `config/vision_models.yaml`: `max_tokens: 1000`

## 🔧 cua-driver Popup-Interaktion
**Problem**: `skylight-cli` sieht nur Hauptfenster, nicht Google OAuth Popup.
**Gelöst**: cua-driver mit `window_id` für alle Popup-Klicks. Siehe `docs/cua-driver-popup-pattern.md`.

## 🔧 skylight-cli Screenshot Workaround
**Problem**: `skylight-cli screenshot --output X` ignoriert `--output`.
**Gelöst**: Temporäres Verzeichnis als CWD in `_screenshot_with_workaround()`.

## 🔧 prompt_kit.py: Set-of-Marks Annahme entfernt
**Problem**: Prompt nahm an, dass Screenshots [1],[2],[3] Marker haben – haben sie nicht.
**Gelöst**: Dynamischer Prompt ohne SoM, mit Page-Context.
