# learn.md — UNVERBRÜCHLICHE WAHRHEITEN (2026-05-06)

## 🔥 GOOGLE LOGIN — VERIFIED WORKING FLOW

**PID=86834, 2026-05-06, cua-driver, 0 Fehler, Passkey Flow.**

### Exakter Ablauf:
```
1. Chrome mit --force-renderer-accessibility + --remote-allow-origins=* starten
2. cua-driver daemon: nohup cua-driver serve &
3. cua-driver call list_windows → Dashboard WID finden
4. cua-driver call get_window_state → tree_markdown parsen
5. Regex: - [N] AXLink (Google Login-Symbol) → element_index
6. cua-driver call click {pid, wid, element_index}
7. OAuth Popup WID finden (list_windows)
8. Regex: - [N] AXTextField (E-Mail…) → set_value email
9. Regex: - [N] AXButton "Weiter" → click
10. Passkey: Regex "weiter" → click → macOS TouchID auto
11. Regex "fortfahren" → click
12. Regex "weiter" → click (Consent)
13. Verify: "Abmelden" + "Umfragen" in tree_markdown
```

### KRITISCH: cua-driver Output-Formate

| Command | Output Format | Parser |
|---------|--------------|--------|
| `list_windows` | JSON `{"windows": [...]}` | `json.loads()` |
| `get_window_state` | JSON `{"tree_markdown": "...", "element_count": N}` | `json.loads()`, dann Regex auf markdown |
| `click` | TEXT `"✅ Performed AXPress on [N] AXRole."` | `"Performed" in stdout` |
| `set_value` | TEXT `"✅ Set AXValue on [N] AXRole."` | `"Set" in stdout` |

**NIEMALS `json.loads()` auf `click`/`set_value` Output!**

### Markdown-Parser Regex (beide Formate)
```python
# Format 1: - [35] AXButton (Weiter)
# Format 2: - [35] AXButton "Weiter"
re.compile(r'-\s*\[(\d+)\]\s+' + role + r'\s+[\(“\"]([^\)\"”]+)[\)\"”]')
```

## 🔥 CHROME: IMMER beide Flags

```
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9999 \
  --remote-allow-origins=* \
  --force-renderer-accessibility \
  --no-first-run \
  --user-data-dir=/tmp/heypiggy-bot \
  'https://www.heypiggy.com/?page=dashboard'
```

⚠️ `playstealth launch` setzt NICHT `--force-renderer-accessibility`. NIE für Produktion nutzen.

## 🔥 NIM Nemotron 3 Omni: REASONING Model
- max_tokens=600 (nicht 200!)
- KEIN system prompt
- Chain-of-thought user prompt

## 🔥 Angular v19: JS .click() ignoriert
- Nur CDP `Input.dispatchMouseEvent` (isTrusted=true)

## 🔥 PureSpectrum Flow
1. ROBOT textarea + CDP-click Nächste
2. Text captcha: base64 → Vision OCR → fill + CDP-click
3. Drag puzzle: __ngContext__ → dropListRef.drop()

## 🔥 Gelöscht (Lügen)
- `survey/login.py`: Behauptete "already_logged_in" auf Landing-Page
