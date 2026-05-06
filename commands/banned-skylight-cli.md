# SKYLIGHT-CLI STATUS — RE-ACTIVATED (2026-05-06) ✅

## Status
**RE-ACTIVATED** — 2026-05-06, per AGENTS.md + sinrules.md.
`snapshot-compact` und `batch` sind PRIMARY. Nur `click --element-index` bleibt BANNED.

## ✅ ERLAUBT (PRIMARY)
- `skylight-cli snapshot-compact --pid X --semantic` — Compact @eN Snapshot
- `skylight-cli find --role button --text "Weiter"` — Element-Suche
- `skylight-cli batch '[{"ref":"@e0","action":"click"}]'` — Batch-Ausführung

## ❌ BANNED (unverändert)
- `skylight-cli click --element-index` — Index instabil
- `skylight-cli query` — veraltet
- `skylight-cli screenshot` — veraltet (nutze CDP Page.captureScreenshot)

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
NEMO UPDATE (2026-05-06):
- CUA-DRIVER = DEPRECATED (Legacy-Fallback, kein neuer Code)
- CDPConnection (survey/cdp_client.py) = PRIMARY für CDP-Interaktionen
- BatchExecutor = PRIMARY für Survey-Actions
- StealthInjection = PRIMARY für Anti-Detection

- 2026-05-06: NEMO PRIMARY, skylight-cli snapshot-compact + batch RE-ACTIVATED, cua-driver DEPRECATED

## Alternative
- NUR cua-driver für macOS UI Automation
- playstealth launch für Chrome-Start