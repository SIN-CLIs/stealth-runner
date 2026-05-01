# FAILURE_MODES.md – Heypiggy Login (SOTA-konform)

## FM-003: Stale Element Indices nach React-State-Updates

**Beschreibung**: Nach einer Seitenänderung (z. B. E-Mail-Eingabe) stimmen die zuvor erfassten Element-Indizes nicht mehr mit der aktuellen DOM-Struktur überein.

**Auslöser**:

- `skylight-cli type` → Seite lädt neu → Indizes verschieben sich.
- Keine Revalidierung der Elemente vor dem Klick.

**Impact**: Falsches Element wird angeklickt (z. B. Trustpilot statt Login-Button).

---

## Detection

| Methode                | Befehl                                               | Erwartetes Ergebnis                     |
| ---------------------- | ---------------------------------------------------- | --------------------------------------- |
| `skylight-cli inspect` | `skylight-cli inspect --element-index 39`            | `{"label": "Trustpilot reviews", ...}`  |
| Vision-LLM             | `python3 runner/step.py --screenshot /tmp/after.png` | `{"action": "click", "element_id": 41}` |
| `skylight-cli click`   | `skylight-cli click --element-index 39`              | Fails mit `expected_label_mismatch`     |

---

## Mitigation

1. **Revalidierung erzwingen**:

```bash
skylight-cli screenshot --mode som --output /tmp/after_action.png
python3 runner/step.py --screenshot /tmp/after_action.png --question "Wo ist der 'Weiter'-Button?"
```

2. **AXPath nutzen**:

```bash
skylight-cli click --axpath "//AXButton[@label='Weiter']"
```

3. **Fallback zu Vision-LLM**:

```python
if not element_found:
    vision_llm_fallback(question="Finde den 'Weiter'-Button und klicke ihn.")
```

---

## Prevention

- **Nie Indizes hartcodieren**.
- **Immer DOM nach State-Changes neu erfassen**.
- **`--expected-label` und `--expected-role` in `skylight-cli click` erzwingen**.

---

## Tests

```bash
pytest tests/test_skylight_expected_label.py -v
pytest tests/test_axpath.py -v
pytest tests/test_revalidation.py -v
```
