# CUA-DRIVER SET VALUE — VERIFIED ✅

## Status
**VERIFIED** — 2026-05-05

## Was es tut
Text in ein AXTextField eintragen (z.B. Email, Passwort, URL).

## Command
```bash
echo '{"pid": PID, "window_id": WID, "element_index": IDX, "value": "TEXT"}' | cua-driver call set_value
```

## Live Beispiele (Google Login 2026-05-05)

### Email eintragen
```bash
echo '{"pid": 78708, "window_id": 57141, "element_index": 25, "value": "zukunftsorientierte.energie@gmail.com"}' | cua-driver call set_value
→ ✅ Set AXValue on [25] AXTextField ""
```

### Passwort eintragen (manual fallback)
```bash
echo '{"pid": 75167, "window_id": 56885, "element_index": 26, "value": "ZOE.jerry2024"}' | cua-driver call set_value
→ ✅ Set AXValue on [26] AXTextField ""
```

## Parameter
| Parameter | Typ | Beschreibung |
|-----------|-----|-------------|
| `pid` | int | Chrome Process ID |
| `window_id` | int | AXWindow ID |
| `element_index` | int | Element-Index aus get_window_state |
| `value` | str | Einzutragender Text |

## Antwort
```
✅ Set AXValue on [N] AXTextField ""
```

## Typische Use Cases
- Email-Feld befüllen
- Passwort-Feld befüllen
- URL in Adressleiste eintragen
- Suchfeld befüllen
- Textarea-Inhalt setzen

## REGELN
- Element-Index IMMER dynamisch via `get_window_state` finden
- Nie hardcoden (Indizes variieren)
- `set_value` NUR auf AXTextField/AXTextArea Elemente
- Bei AXSecureTextField dasselbe Pattern

## Test Log
- 2026-05-05: Email [25] set_value → ✅
- 2026-05-05: Passwort [26] set_value → ✅ (ZOE.jerry2024)