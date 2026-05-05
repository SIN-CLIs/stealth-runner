# BANNED: CDP COMMANDS ❌

## Status
**BANNED** — 2026-05-03, AGENTS.md Line 5

## Warum BANNED?
```
CDP + skylight-cli + webauto-nodriver sind ALLE BANNED.
(AGENTS.md — CUA-ONLY Trinity Architektur)
```

- Chrome blockiert eingehende CDP WebSocket Verbindungen (403 Forbidden)
- Origin check verhindert CDP-Verbindungen
- **CUA-DRIVER ist die einzige erlaubte Lösung**

## Symptom
```
WebSocketBadStatusException: Handshake status 403 Forbidden
Rejected an incoming WebSocket connection from the http://localhost:XXXXX origin.
Use --remote-allow-origins=* to allow connections from this origin.
```

## Verbote
```bash
# ❌ FALSCH - BANNED:
python3 cli/modules/cdp_click.py
from cli.modules.cdp_click import click_by_label
asyncio.run(click_by_label(pid=X, cdp_port=Y, ...))
chrome.debugger.send('Runtime.evaluate', {...})
ws://127.0.0.1:PORT DevTools connection
```

## RICHTIG: CUA-DRIVER
```bash
# ✅ RICHTIG:
echo '{"pid": PID, "window_id": WID}' | cua-driver call get_window_state
echo '{"pid": PID, "window_id": WID, "element_index": IDX}' | cua-driver call click
```

## Fallback
```bash
# Wenn CUA komplett leer ist (Accessibility prüfen):
python3 -c "
import subprocess
r = subprocess.run(['system_profiler', 'SPAccessibilityDataType', '-json'],
    capture_output=True, text=True)
print(r.stdout)
"
```

## History
- 2026-05-03: CDP WebSocket blockiert (403 Forbidden)
- 2026-05-03: CDP BANNED, CUA-DRIVER PRIMARY
- 2026-05-05: CUA-DRIVER funktioniert einwandfrei (PID=78708, 8 Steps)