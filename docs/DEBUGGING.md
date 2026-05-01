# DEBUGGING.md – Heypiggy Login (SOTA-konform)

## 🔍 Dynamische Element-Indizes (React/SPA)

**Symptome**: `skylight-cli click --element-index 39` trifft Trustpilot-Link statt "Weiter"-Button.

**Debug-Schritte**:

1. DOM vor Aktion erfassen:

```bash
skylight-cli screenshot --pid 91214 --mode som --output /tmp/before.png
```

2. Aktion ausführen:

```bash
skylight-cli type --pid 91214 --element-index 38 --text "test@test.com" --post-delay 2000
```

3. DOM nach Aktion erfassen:

```bash
skylight-cli screenshot --pid 91214 --mode som --output /tmp/after.png
```

4. Elemente vergleichen:

```bash
skylight-cli inspect --pid 91214 --element-index 39
```

- **Vor Reload**: `{"label": "Weiter", "role": "AXButton"}`
- **Nach Reload**: `{"label": "Trustpilot reviews", "role": "AXLink"}`

5. Vision-LLM fragen:

```bash
python3 runner/step.py --screenshot /tmp/after.png --question "Wo ist der 'Weiter'-Button?"
```

→ Antwort: `{"action": "click", "element_id": 41}`

---

## 🛠️ Tools

| Tool                      | Zweck                            | Beispiel                                                             |
| ------------------------- | -------------------------------- | -------------------------------------------------------------------- |
| `skylight-cli screenshot` | DOM mit SoM-Markern erfassen     | `skylight-cli screenshot --mode som`                                 |
| `skylight-cli inspect`    | Element-Attribute prüfen         | `skylight-cli inspect --element-index 39`                            |
| `skylight-cli click`      | Klicken mit Validierung          | `skylight-cli click --expected-label "Weiter"`                       |
| `skylight-cli type`       | Text eingeben + Wartezeit        | `skylight-cli type --post-delay 2000`                                |
| `python3 runner/step.py`  | Agent-Orchestrator (Vision-Only) | `PYTHONPATH=/Users/jeremy/dev/stealth-runner python3 runner/step.py` |
