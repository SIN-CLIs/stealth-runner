# learn.md – Heutige Learnings

## 2026-05-02

### 🔑 cua-driver Popup-Interaktion (CRITICAL)
- `skylight-cli` sieht NUR das Hauptfenster – Popup-Element-Indices sind INVALID
- `cua-driver` kann Popups via `window_id` targetieren
- `get_window_state` MUSS vor `click` aufgerufen werden (cacht Element-Indices)
- Google OAuth Flow: Email → "Weiter" → "Fortfahren" (Consent) → "Weiter" → ✅ Login
- Bei bestehenden Google-Cookies KEINE Passwort-Eingabe nötig

### 🔑 tmux Non-Blocking Pattern
- `bash("command &")` blockiert trotzdem die Shell
- `interactive_bash(tmux_command="new-session -d ...")` ist der korrekte Weg
- `tmux send-keys` für Commands, `tmux capture-pane` für Logs

### 🔑 Nemotron Omni API
- `stream: true` + SSE für tokenweise Antwort
- Antwort-Feld ist `msg.get("reasoning")` nicht `msg.get("content")`
- Große PNGs verursachen Timeout → JPEG quality=40 benutzen

### 🔑 skylight-cli v0.2.0 Workaround
- `--output` wird ignoriert → schreibt immer nach `./skylight_screenshot.png`
- Workaround: temporäres Verzeichnis als CWD

### 🔑 playstealth Argument-Reihenfolge
- `playstealth --json launch --url X` (nicht `playstealth launch --json --url X`)
