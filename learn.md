# learn.md – KRITISCHE Learnings (2026-05-02)

## 🔑 Survey Questions Need TEXT Answers Too!

**NIEMALS** nur klicken. Umfragen haben Textfelder (Einkommen, Alter, PLZ).
Omni zuerst fragen: "Describe EXACTLY what you see. What question? What answer format?"
Dann die passende Action ausführen: `type` (Textfeld) ODER `click` (Radio/Button).

## 🔑 Image Resize Before API (thumbnail 50%)
1200×1006 → 960×805 = ~67KB JPEG statt 300KB PNG. Kein API-Timeout mehr.
`Image.thumbnail((960, 960), Image.LANCZOS)` in `_image_to_jpeg_b64()`.

## 🔑 Nemotron Omni: content > reasoning
Der Model schreibt JSON in `msg["content"]`, Reasoning-Text in `msg["reasoning"]`.
Content MUSS Priority haben.

## 🔑 max_tokens: 300→1000 für Reasoning-Models
Reasoning braucht Tokens zum Denken. JSON kommt ERST danach.
300 Tokens = JSON abgeschnitten → parse-fail → "wait".

## 🔑 Page Detection via skylight-cli
AXWebArea-Label zeigt Seitentitel: "HeyPiggy" vs "PureSpectrum" vs "Google".
In state speichern → an prompt übergeben → Model passt sich an.

## 🔑 cua-driver für Popups, skylight für Hauptfenster
Popup = `cua-driver call click "{...\"window_id\":WID,...}"`
Hauptfenster = `skylight-cli click --pid X --element-index Y`
NIE mischen!
