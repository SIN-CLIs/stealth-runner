# brain.md – Systemwissen & Architektur-Entscheidungen

## 🔑 CRITICAL: Popup-Interaktion via cua-driver (nicht skylight!)

**Regel**: `skylight-cli` operiert NUR auf dem HAUPTFENSTER. Popup-Indices von `skylight-cli list-elements` sind INVALID für Popup-Content. Für Google OAuth, Consent-Dialoge, etc. IMMER `cua-driver` verwenden:

```bash
# Popup finden
cua-driver call list_windows '{}'

# Popup-Elemente laden (cacht pro window_id)
cua-driver call get_window_state '{"pid":PID,"window_id":WID}'

# Im Popup klicken/tippen
cua-driver call click '{"pid":PID,"window_id":WID,"element_index":N,"action":"press"}'
cua-driver call set_value '{"pid":PID,"window_id":WID,"element_index":N,"value":"text"}'
```

Siehe `docs/cua-driver-popup-pattern.md` für vollständige Doku.

## AKTIVES MODELL
- **Name**: `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`
- **API**: `POST https://integrate.api.nvidia.com/v1/chat/completions`
- **Key**: `$NVIDIA_API_KEY` (Prefix: `nvapi-...`)
- **gRPC**: Function-ID `c4ed50ff-b5c3-409d-ab57-b79c33f5bb39` (nur REST, gRPC=502)

## AKTIVER CODE
- `~/dev/stealth-runner/runner/live_eye.py` – LiveEye v7 (Motion Detection)
- `~/dev/stealth-runner/runner/live_omni_monitor.py` – Hybrid Monitor
- `~/dev/stealth-runner/cli/heypiggy-login` – Google OAuth Login (cua-driver)

## ARCHIVIERT
- `~/dev/A2A-SIN-Worker-heypiggy` – Legacy Worker (BRAIN.md sagt "ARCHIVIERT")

## TMUX NON-BLOCKING PATTERN
Immer `interactive_bash` (tmux) für long-running Commands, NIE `bash` mit `&`:
```python
interactive_bash(tmux_command="new-session -d -s mysession")
interactive_bash(tmux_command='send-keys -t mysession "command" Enter')
```

## MOTION DETECTION (LiveEye v7)
```python
MOTION_HIGH_THRESH = 20.0  # Scroll/Page-Transition
MOTION_LOW_THRESH = 3.0   # Statische Frames (Survey-Fragen)
MOTION_CRF_MAP = {"high": 28, "mid": 35, "low": 40}
MOTION_NUM_FRAMES_MAP = {"high": -1, "mid": 8, "low": 4}
```

## JPEG QUALITY
`live_omni_monitor.py`: `quality=40` → 90% Payload-Reduktion
## 🔑 cua-driver Daemon (2026-05-02, CRITICAL)
cua-driver Daemon MUSS laufen (`cua-driver serve &`) vor allen element-index Klicks.
Ohne Daemon: "No cached AX state" → Klick schlägt fehl.
