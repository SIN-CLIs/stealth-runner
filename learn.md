# learn.md — HEUTE GELERNT (2026-05-06)

## 🔥 GOOGLE LOGIN — VERIFIED WORKING (PID=95165, PID=86834)

### Der Flow (cua-driver PRIMARY, CDP FALLBACK)
```
1. Invariants prüfen: daemon, Chrome port, Accessibility, AX-Tree elements
2. cua-driver list_windows → Dashboard WID finden (per TITLE, nicht owner!)
3. cua-driver get_window_state → tree_markdown regex parsen
4. Regex: - [N] AXLink (Google Login-Symbol) → element_index
5. cua-driver click → OAuth Popup erscheint (NEUE WID)
6. Regex: - [N] AXTextField (E-Mail…) → set_value email
7. Regex: - [N] AXButton "Weiter" → click
8. Passkey: Regex "weiter" oder "fortfahren" → click → macOS TouchID auto
9. Regex "fortfahren" → click
10. Regex "weiter" → click (Consent)
11. Verify: "Abmelden" + "Umfragen" in tree_markdown
```

### KRITISCH: cua-driver Output-Formate (DAS hat Stunden gekostet)

| Command | Output | Parser |
|---------|--------|--------|
| `list_windows` | JSON | `json.loads()` ✅ |
| `get_window_state` | JSON mit `tree_markdown` String | `json.loads()`, dann Regex |
| `click` | **TEXT** `"✅ Performed AXPress on [N]"` | `"Performed" in stdout` |
| `set_value` | **TEXT** `"✅ Set AXValue on [N]"` | `"Set" in stdout` |

**NIE `json.loads()` auf `click`/`set_value` Output!**
**NIE `el.get("children", [])` auf `get_window_state` — nutze `tree_markdown`!**
**NIE `owner` Feld nutzen (ist LEER) — nutze `title` für Fenster-Identifikation!**

### Markdown-Parser Regex (MUSS beide Formate matchen)
```python
# Format 1: - [35] AXButton (Weiter)         ← mit Klammern
# Format 2: - [35] AXButton "Weiter"         ← mit Anführungszeichen
re.compile(r'-\s*\[(\d+)\]\s+' + role + r'\s+[\(“\"]([^\)\"”]+)[\)\"”]')
```

## 🔥 CHROME — UNVERBRÜCHLICHE REGELN

```bash
# NUR SO starten:
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9999 \
  --remote-allow-origins=* \
  --force-renderer-accessibility \
  --no-first-run \
  --user-data-dir=/tmp/heypiggy-bot \
  'URL'
```

- ❌ `playstealth launch` — setzt NICHT `--force-renderer-accessibility`
- ❌ Ohne `--force-renderer-accessibility` — cua-driver AX-Tree LEER (0 children, 0 tree_markdown)
- ❌ Ohne `--remote-allow-origins=*` — CDP WebSocket 403
- ✅ Profil `/tmp/heypiggy-bot` FEST (nicht timestamped) → Login-Cookies persistent
- ✅ Chrome NIEMALS killen nach Accessibility-Grant (Permission geht verloren)

## 🔥 NIM NEMOTRON 3 OMNI — REASONING MODEL

- `max_tokens=600` (nicht 200!) — Model braucht Tokens zum DENKEN
- KEIN system prompt (verwirrt das Reasoning-Model)
- Chain-of-thought: "Think step by step… Your JSON:"
- Alternativ: `openai/gpt-oss-120b` ist 10× schneller für einfache Fragen

## 🔥 Angular v19: JS .click() IGNORIERT

- Nur CDP `Input.dispatchMouseEvent` funktioniert (isTrusted=true)
- Alle PureSpectrum-Buttons brauchen CDP-Click via `cdp_click_button()`
- JS `.click()` und `dispatchEvent(new MouseEvent(...))` werden ignoriert

## 🔥 PureSpectrum Flow (vollständig)

```
1. Cookie Consent: JS querySelector('button') → click
2. ROBOT Textarea: textarea.value = 'ROBOT ...' → CDP-click Nächste
3. Text Captcha: base64 img src → NVIDIA Vision OCR → fill input → CDP-click Nächste
4. Drag Puzzle: __ngContext__ recursive → findInstance → dropListRef.drop()
```

## 🔥 CPX API: details_url MUSS vom Dashboard kommen

```python
# ❌ Hardcoded URL → "No surveys available"
# ✅ Live URL vom Dashboard via Runtime.evaluate:
details_url = js_eval("details_url")
```
Dashboard hat zusätzliche Parameter: `secure_hash_offerwall`, `m`, `m_1`, etc.

## 🔥 Zombie-Tabs — TOD für tab_ws Tracking

- Vor JEDEM Survey-Run: alle nicht-Dashboard Tabs schließen
- `_find_survey_tab_ws()` muss den NEUESTEN Tab priorisieren
- Nie `chrome.find_survey_tab()` als Fallback (findet Zombie-Tabs)

## 🔥 Gelöschte Dateien (Lügen/Fehler)

- `survey/login.py`: Behauptete "already_logged_in" auf Landing-Page → GELÖSCHT
- Alte `_find_by_role()`: Traversierte `el.get("children", [])` das nicht existiert → ERSETZT

## 🔥 Chrome auf Port 9999 — NIE anders

```python
# login.py startet Chrome IMMER auf 9999:
subprocess.Popen([
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "--remote-debugging-port=9999",
    "--remote-allow-origins=*",
    "--force-renderer-accessibility",
    "--no-first-run",
    "--user-data-dir=/tmp/heypiggy-bot",
    launch_url,
])
```
- Nach Login: Dashboard auf Port 9999 ist eingeloggt
- Daemon nutzt Port 9999 → sieht eingeloggten Zustand
- Profil `/tmp/heypiggy-bot` persistent → Cookies bleiben
- **Nie playstealth (random Port). Nie ohne Accessibility.**

## 🔥 VERIFIED HEUTE (2026-05-06)

| PID | Tool | Ergebnis |
|-----|------|----------|
| 86834 | cua-driver login | ✅ First success after regex fix |
| 95165 | cua-driver login | ✅ Full flow: Google→OAuth→Passkey→Fortfahren→Consent |
| 97688 | cua-driver login | ✅ On port 9999, daemon-ready |
| 9999 | Daemon scan | ✅ 12 surveys, 2.15€ balance |

## 🔥 Invariant-Guard Pattern (für ALLE zukünftigen Tools)

```python
def _verify_invariants():
    errors = []
    if not daemon_running: errors.append("cua-driver daemon NOT running")
    if not chrome_on_9999: errors.append("Chrome NOT on port 9999")
    if not accessibility_enabled: errors.append("AX-Tree < 100 elements")
    if errors: return False
    return True
```
**JEDES Tool MUSS einen Invariant-Guard haben.**
