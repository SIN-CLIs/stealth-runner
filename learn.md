# learn.md - Session Learnings (2026-05-01)

## 1. Nemotron Omni reasoning-Feld
- **Problem**: `response["choices"][0]["message"]["content"]` ist null
- **Gelernt**: Omni schreibt Antwort in `reasoning` (nicht `content`)
- **Fix**: `msg.get("reasoning") or msg.get("content") or ""`
- **Betrifft**: Alle NIM-API-Calls mit Nemotron Omni Modell

## 2. Model-Name ohne doppelten Prefix
- **Problem**: `nvidia/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` → 404
- **Gelernt**: Korrekter Name ist `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`
- **Fix**: YAML + Code korrigiert

## 3. skylight-cli --output Bug
- **Problem**: `skylight-cli screenshot --output /tmp/foo.png` → Datei liegt im CWD
- **Gelernt**: skylight-cli v0.2.0 ignoriert `--output`, schreibt immer `skylight_screenshot.png` ins CWD
- **Workaround**: Datei nach screenshot aus CWD kopieren

## 4. Google Login Flow (5 Schritte)
- **Gelernt**: Google Login braucht 3 "Weiter"-Klicks (Email → Passwort → Bestätigung)
- **Wichtig**: Nach jedem Schritt `list-elements` neu abfragen (Indizes ändern sich)
- **Erfolg**: PID 11255, alle Schritte dokumentiert

## 5. screen-follow Video Recording
- **Gelernt**: `screen-follow record` startet nur Event-Logging
- **Fix**: `screen-follow record --video` für MP4-Aufnahme
- **Datei**: `/tmp/omni_session.mp4`
- **Integration**: Rolling Buffer via ffmpeg für Omni Analyse

## 6. SSE Streaming funktioniert
- **Gelernt**: NVIDIA NIM unterstützt `stream: true`
- **Format**: `Accept: text/event-stream` → SSE Chunks
- **Vorteil**: Tokenweise Antwort statt komplettem JSON warten
