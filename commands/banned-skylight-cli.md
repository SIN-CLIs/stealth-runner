# BANNED: SKYLIGHT-CLI ❌

## Status
**BANNED** — 2026-05-03, AGENTS.md Line 5

## Warum BANNED?
```
CDP + skylight-cli + webauto-nodriver sind ALLE BANNED.
(AGENTS.md — CUA-ONLY Trinity Architektur)
```

- skylight-cli nutzt Browser-Chrome + Web-Content vermischt
- Element-Indizes sind instabil (ändern sich bei Page-Load)
- Index passt nicht zwischen Sessions
- **CUA-DRIVER ist die einzige erlaubte Lösung**

## Verbote
```bash
# ❌ FALSCH - BANNED:
skylight-cli click --pid X --element-index Y
skylight-cli type --pid X --element-index Y --text "..."
skylight-cli screenshot --pid X

# ❌ FALSCH - BANNED (MCP):
skylight-cli MCP server
```

## RICHTIG: CUA-DRIVER
```bash
# ✅ RICHTIG:
echo '{"pid": PID, "window_id": WID, "element_index": IDX}' | cua-driver call click
echo '{"pid": PID, "window_id": WID, "element_index": IDX, "value": "TEXT"}' | cua-driver call set_value
```

## History
- 2026-05-03: skylight-cli BANNED wegen instabiler Indizes
- 2026-05-05: CUA-DRIVER ist PRIMARY für alle Browser-Interaktionen

## Alternative
- NUR cua-driver für macOS UI Automation
- playstealth launch für Chrome-Start