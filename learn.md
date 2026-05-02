# learn.md - Session Learnings (2026-05-01)

## 2026-05-02: Neue Commits

- `b571372 feat: doctor graphify setup — install, update, post-commit hook`
- `77f95fd feat: doctor cleanup phase — AST-Cache, __pycache__, alte Chrome-Profile, alte Artefakte`
- `7fd1df3 feat: doctor context writer für usage.md, faq.md, benchmarks.md, troubleshooting.md, acknowledgments.md, SUPPORT.md, CODE_OF_CONDUCT.md, CONTRIBUTING.md, SECURITY.md`
- `04172ca feat: doctor context writer für architecture.md, commands.md, testing.md, goal.md, api.md`
- `c67bf78 docs: SKILL.md — context writer für alle 7 SOTA-Docs dokumentiert`
- `57b019d feat: doctor context writer für brain.md, fix.md, issues.md, successful.md, learn.md, anti-learn.md, history.md`
- `8b6edbb feat: doctor history.md context writer — auto-generates history entries from git log + diff`
- `616432d docs: history.md — LiveEye v7 Changelog`
- `9940e05 feat: LiveEye v7 optimizations + docs + agent cleanup`
- `7ce191b feat: gRPC Function-ID gefunden + Dual-Mode vorbereitet`

**Sprachen:** TypeScript, JSON, JavaScript, Markdown, Python

## 1. Nemotron Omni reasoning-Feld

- **Problem**: `response["choices"][0]["message"]["content"]` ist null
- **Gelernt**: Omni schreibt Antwort in `reasoning` (nicht `content`)
- **Fix**: `msg.get("reasoning") or msg.get("content") or ""`
- **Betrifft**: Alle NIM-API-Calls mit Nemotron Omni Modell

## 2. Model-Name ohne doppelten Prefix

- **Problem**: `nvidia/nemotron (doppelter Prefix entfernt)-3-nano-omni-30b-a3b-reasoning` → 404
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
