# BANNED: WEBauto-NODRIVER ❌

## Status
**BANNED** — 2026-05-03, AGENTS.md Line 5

## Warum BANNED?
```
webauto-nodriver ist ABSOLUT BANNED. skylight-cli snapshot-compact + batch sind ERLAUBT.
(AGENTS.md — NEMO Architektur)
```

- Nutzt CDP WebSocket (Origin check blockiert Chrome)
- Browser-Chrome + Web-Content werden vermischt
- **CUA-DRIVER ist die einzige erlaubte Lösung**

## Verbote
```bash
# ❌ FALSCH - BANNED:
webauto-nodriver MCP server
nodriver.start()
webauto_health
webauto_goto
webauto_click
webauto_screenshot
```

## RICHTIG: CUA-DRIVER
```bash
# ✅ RICHTIG:
echo '{"pid": PID, "window_id": WID}' | cua-driver call get_window_state
echo '{"pid": PID, "window_id": WID, "element_index": IDX}' | cua-driver call click
```

## Alternative
- NUR cua-driver für macOS UI Automation
- playstealth launch für Chrome-Start