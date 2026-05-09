# VERIFY-BOX PATTERN — Stealth-Runner Best Practices

> **Version**: 2026-05-08 v1.0
> **Scope**: Verify-Box Pattern für ALLE Aktionen (Klicks, Texteingaben, Navigation)
> **Status**: ACTIVE — PFLICHT für JEDE Aktion

---

## 1. PROBLEM: Agent wird belogen

```
 OHNE Verify-Box:
  Agent klickt "Männlich"
  → cua-driver: "✅ Performed"
  → Agent glaubt: Radio-Button ist selektiert
  → Agent macht weiter (nächste Frage)

 REALITÄT:
  → JS-Event-Listener hat NICHT gefeuert
  → Radio-Button ist NICHT selektiert
  → Agent macht 10 Schritte blind weiter
  → Survey DISQUALIFIZIERT
  → 10min verschwendet

 MIT Verify-Box:
  Agent klickt "Männlich"
  → cua-driver: "✅ Performed"
  → Verify: AX-Tree NEU scannen
  → Prüfen: Radio-Button "selected=true"?
  → FALSE → RETRY mit anderem Element-Index
  → ODER: FALSE → Fallback zu CDP JS click()
  → TRUE → Weiter mit nächster Frage
```

---

## 2. PATTERN: Verify nach JEDER Aktion

### Allgemeines Pattern

```python
def click_and_verify(pid: int, wid: int, element_idx: int,
                     expected_state: dict = None) -> bool:
    """
    ================================================================================
    Klickt ein Element und VERIFIZIERT dass der Zustand erreicht wurde.

    Pattern: ACTION → RESCAN → VERIFY → RETRY/RETURN

    WARUM Verify?
      Ohne Verify: cua-driver sagt "Performed", aber JS-EventListener
      hat nicht gefeuert → Zustand NICHT erreicht → Agent belogen.

    Args:
      pid (int): Chrome PID
      wid (int): Window ID
      element_idx (int): Element-Index aus AX-Tree
      expected_state (dict, optional): Erwarteter Zustand nach Klick.
        Format: {"role": "AXRadioButton", "selected": True}
        Oder:    {"role": "AXCheckBox", "checked": True}
        Oder:    {"role": "AXTextField", "value_contains": "text"}

    Returns:
      bool: True NUR wenn Zustand VERIFIZIERT erreicht.
            False = Retry nötig.

    Side Effects:
      - Führt Klick aus (cua-driver oder CDP)
      - Scannt AX-Tree NEU (zusätzlicher cua-driver Call)
      - Wartet auf DOM-Update (time.sleep)

    Race Conditions:
      - DOM ändert sich nach Klick aber VOR rescan
        → Lösung: Warte 0.5s nach Klick (genug für ein Event-Frame)

    Example:
      >>> # Radio-Button klicken und verifizieren
      >>> # WICHTIG: PIDs sind dynamisch! Niemals hardcoded (71104)!
      >>> # Dynamisch ermitteln: curl http://127.0.0.1:9999/json | jq '.[].processId'
      >>> chrome_pid = DYNAMIC_PID  # aus CDP JSON gescannt
      >>> ok = click_and_verify(chrome_pid, 56640, 42,
      ...     expected_state={"role": "AXRadioButton", "selected": True})
      >>> if not ok:
      ...     # Fallback: CDP JS click
      ...     cdp_js_click(".gender-male")
    ================================================================================
    """
    # ── SCHRITT 1: Aktion ausführen ──
    result = _execute_click(pid, wid, element_idx)
    if not result.get("success"):
        return False

    # ── SCHRITT 2: Kurz warten (DOM-Update) ──
    # WARUM 0.5s? Genug für ein Event-Frame (16ms × 30 ≈ 500ms).
    # WARUM nicht time.sleep(0)? DOM-Update ist asynchron — braucht Zeit.
    time.sleep(0.5)

    # ── SCHRITT 3: AX-Tree NEU scannen ──
    # WARUM neu scannen? Alter AX-Tree ist veraltet.
    # WARUM gleiches Window? Klick könnte WID geändert haben (Popup) —
    #   prüfe ob WID noch gültig.
    tree = _get_tree(pid, wid)

    # ── SCHRITT 4: Zustand verifizieren ──
    if expected_state:
        return _verify_state(tree, element_idx, expected_state)

    return True
```

### Verify für Radio-Buttons

```python
def verify_radio_selected(pid: int, wid: int, element_idx: int) -> bool:
    """
    Verifiziert dass ein Radio-Button selektiert ist.

    WARUM spezielle Funktion?
      Radio-Buttons sind der HÄUFIGSTE Fehlerfall!
      cua-driver click feuert AXPress, aber JS onClick wird nicht getriggert.
      → Element sieht "geklickt" aus, ist aber NICHT selektiert.

    Verify-Schritte:
      1. AX-Tree neu scannen
      2. Element [N] finden
      3. Prüfen: Zeile enthält "selected"?
         - AXRadioButton: "selected=true" oder "selected: 1"
         - AXCheckBox: "checked=true" oder "checked: 1"
      4. Wenn nicht: Fallback zu CDP JS click
    """
    tree = _get_tree(pid, wid)

    for line in tree.split("\n"):
        if f"[{element_idx}]" in line:
            # Prüfe auf "selected" oder "checked"
            if "selected" in line.lower() or "checked" in line.lower():
                # Extrahiere den Wert
                if "true" in line.lower() or ": 1" in line:
                    return True
                if "false" in line.lower() or ": 0" in line:
                    return False
            return False

    # Element nicht mehr im Tree → WID hat sich geändert?
    return False


def click_radio_with_verify(pid, wid, element_idx, cdp_ws=None, selector=None):
    """
    Radio-Button klicken mit Verify + CDP-Fallback.

    WARUM zwei Methoden? cua-driver ist PRIMARY für AX-Klicks,
    CDP JS ist Fallback für Fälle wo AX nicht funktioniert.

    WARUM nicht immer CDP? CDP Runtime.evaluate() feuert JS direkt —
    das ist OK aber weniger "natürlich" (AX ist robuster).

    Flow:
      1. cua-driver click
      2. Verify (rescan + check selected=true)
      3. Wenn FALSE → CDP JS dispatchEvent click
      4. Verify erneut
      5. Wenn immer noch FALSE → ERROR (Survey weiter? Screen-out?)
    """
    # Attempt 1: cua-driver
    if click_and_verify(pid, wid, element_idx,
                        expected_state={"role": "AXRadioButton", "selected": True}):
        return True

    # Attempt 2: CDP JS Fallback
    if cdp_ws and selector:
        cdp_js = f"""
        (function() {{
            var el = document.querySelector('{selector}');
            if (el) {{
                el.click();
                el.dispatchEvent(new Event('change', {{bubbles: true}}));
                return true;
            }}
            return false;
        }})()
        """
        result = _cdp_evaluate(cdp_ws, cdp_js)
        if result.get("value"):
            time.sleep(0.5)
            # Verify erneut
            if verify_radio_selected(pid, wid, element_idx):
                return True

    return False
```

### Verify für Text-Eingaben

```python
def verify_text_value(pid: int, wid: int, element_idx: int,
                      expected_text: str) -> bool:
    """
    Verifiziert dass Text in ein Feld geschrieben wurde.

    WARUM Verify bei Text?
      cua-driver set_value setzt AXValue direkt — funktioniert meistens.
      Aber: Manche SPAs validieren onBlur oder onChange.
      → AXValue wird gesetzt, aber Formular validiert nicht.
      → Survey sagt "Bitte füllen Sie dieses Feld aus".

    Verify-Schritte:
      1. AX-Tree neu scannen
      2. Element finden
      3. AXValue prüfen: enthält es expected_text?
      4. Wenn nicht: CDP JS value setzen + dispatchEvent
    """
    tree = _get_tree(pid, wid)

    for line in tree.split("\n"):
        if f"[{element_idx}]" in line:
            if "AXValue" in line or "value" in line.lower():
                if expected_text in line:
                    return True
            # Auch prüfen ob der Text im Label-Teil steht
            if expected_text in line:
                return True

    return False
```

### Verify für Button-Klicks (Seiten-Transition)

```python
def verify_page_transition(pid: int, old_wid: int, old_url: str,
                           cdp_ws: str, wait_s: float = 3.0) -> Tuple[bool, str]:
    """
    Verifiziert dass ein Seiten-Übergang nach Button-Klick stattgefunden hat.

    WARUM spezielle Verify-Funktion?
      Nach "Weiter" klicken: Seite ändert sich.
      Wenn nicht: Button war disabled, oder Page hat nicht geladen.
      → Warten und erneut prüfen.

    Returns:
      (True, new_url) wenn Transition erfolgreich
      (False, "") wenn keine Transition

    Signale für Transition:
      - URL hat sich geändert (CDP /json)
      - WID hat sich geändert (Popup/Modal)
      - Fragen haben sich geändert (document.body.innerText)
      - Progress hat sich geändert (z.B. "3/10" → "4/10")
    """
    time.sleep(wait_s)

    # Check 1: WID geändert?
    windows = _list_windows()
    current_wids = [w["window_id"] for w in windows if w["pid"] == pid]
    if old_wid not in current_wids:
        new_wid = current_wids[0] if current_wids else None
        if new_wid:
            return True, f"WID_CHANGED:{new_wid}"

    # Check 2: URL geändert?
    pages = _cdp_pages(pid=pid)
    for p in pages:
        if p.get("url") != old_url:
            return True, p.get("url", "")

    # Check 3: Inhalt geändert? (via CDP JS)
    content_check = _cdp_evaluate(cdp_ws, "document.body.innerText.substring(0,200)")
    # ... (vergleiche mit vorherigem Inhalt)

    return False, ""
```

---

## 3. VERIFY-BOX INTEGRATION IN BEFEHLE

### cua-driver mit Verify

```bash
# OHNE Verify (BANNED!)
# PIDs sind dynamisch — NIEMALS 71104 hardcodieren!
cua-driver call click '{"pid": DYNAMIC_PID, "window_id": 56640, "element_index": 42}'

# MIT Verify (PFLICHT!)
# PID dynamisch ermitteln: curl http://127.0.0.1:9999/json | jq '.[].processId'
cua-driver call click '{"pid": DYNAMIC_PID, "window_id": 56640, "element_index": 42, "verify": true}'
```

### stealth-exec mit Verify

```bash
# OHNE Verify (BANNED!)
stealth-exec cua-touch --action click --label "Männlich"

# MIT Verify (PFLICHT!)
stealth-exec cua-touch --action click --label "Männlich" --verify
```

### Python Wrapper

```python
def cua_click_with_verify(pid, wid, element_idx, verify_state=None):
    """
    Wrapper um cua-driver click MIT Verify.

    Diese Funktion SOLLTE von ALLEM Code verwendet werden der cua-driver nutzt.
    Direkte cua-driver click() Calls sind BANNED (siehe sinrules.md §BANNED).
    """
    params = {"pid": pid, "window_id": wid, "element_index": element_idx}

    if verify_state:
        params["verify"] = True
        params["expected_state"] = verify_state

    result = _run(["cua-driver", "call", "click"], json.dumps(params))

    return result.get("success", False)
```

---

## 4. ANTI-PATTERNS (NIEMALS!)

```python
# ❌ ANTI-PATTERN 1: Ohne Verify blind weitermachen
_cua(pid, wid, "click", {"element_index": 42})
# → "Performed" → Agent glaubt es → Weiter...
# → NIEMALS! IMMER verify!

# ❌ ANTI-PATTERN 2: Verify mit veraltetem Tree
tree = _get_tree(pid, wid)  # Alter Tree
_cua(pid, wid, "click", {"element_index": 42})
time.sleep(0)  # KEIN Warten!
# Verify mit ALTEM tree → immer "nicht gefunden" — sinnlos!

# ✅ RICHTIG: Rescan NACH Klick
_cua(pid, wid, "click", {"element_index": 42})
time.sleep(0.5)  # DOM-Update abwarten
tree = _get_tree(pid, wid)  # NEUER Tree
verify_element_state(tree, 42, selected=True)

# ❌ ANTI-PATTERN 3: Nur einmal verify
if not verify():
    # Kein Fallback! Einfach aufgeben.
    raise SurveyError("Verify failed")

# ✅ RICHTIG: Fallback-Kette
if not verify_cua():
    if not verify_cdp():
        log_error("verify_failed_twice", ...)
        # Entscheidung: Survey abbrechen oder letzten Versuch?
```

---

## 5. CHECKLISTE: Verify-Box

Vor JEDER cua-driver Aktion (click, set_value, press_key):

- [ ] Ist `verify: true` im JSON-Parameter gesetzt?
- [ ] Ist `expected_state` definiert? (selected, checked, value_contains)
- [ ] Wird der AX-Tree **nach** der Aktion NEU gescannt?
- [ ] Wird time.sleep(0.5) zwischen Aktion und Verify gewartet?
- [ ] Gibt es einen Fallback (CDP JS) wenn Verify fehlschlägt?
- [ ] Wird der Fehler geloggt wenn Verify 2× fehlschlägt?
- [ ] Ist die Funktion dokumentiert dass Verify enthalten ist?

---

**Dieses Dokument ist LEBENDIG. Jede neue Aktion MUSS diese Verify-Patterns implementieren.**

*Letzte Aktualisierung: 2026-05-08*
