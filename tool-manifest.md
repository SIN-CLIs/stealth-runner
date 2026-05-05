# tool-manifest.md — Tool Manifest (JSON Schema)

> **← [tool-registry.md](tool-registry.md) für Tool-Liste | → [registry.md](registry.md) für Master-Registry**

---

## Manifest Struktur

Jedes Tool hat einen JSON-Manifest-Eintrag mit:

```json
{
  "name": "cua-driver-click",
  "description": "Element per AXPress klicken",
  "category": "actuation",
  "command": "cua-driver call click",
  "parameters": {
    "pid": "number",
    "window_id": "number",
    "element_index": "number",
    "verify": "boolean (optional)"
  },
  "file": "commands/cua-driver/click.md",
  "banned": false
}
```

## Manifest-Generator

```bash
# In playstealth-cli:
python3 -c "from playstealth_actions.tool_manifest import generate; print(generate())"
```

## Registrierte Tools

Siehe [tool-registry.md](tool-registry.md) für die vollständige Liste mit 16 Tools.

**Letztes Update**: 2026-05-05
