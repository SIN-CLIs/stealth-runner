# fix.md – ALL Fixes

> **← [sinrules.md](sinrules.md) ist die zentrale Regeldatei. §2 definiert Banned-Patterns.**
> **← [issues.md](issues.md) dokumentiert das Index-Problem.**
> **← [brain.md](brain.md) dokumentiert die CDP+AX Trinity Lösung.**

---

## 🔴 KRITISCH: Survey-Suche in neuen Tabs statt In-Page (2026-05-04)

### Symptom
clickSurvey() wird aufgerufen, aber ich suche nach neuen Tabs:
```python
Target.getTargets()  # → findet nichts → "Surveys öffnen sich nicht" ❌
```

### Root Cause
clickSurvey() öffnet den Survey als IN-PAGE Modal im Dashboard (showTypeOkay/showTypeQuestion).
Der Inhalt erscheint im selben Tab, nicht als neuer Browser-Tab.

### Fix
Nach clickSurvey() den AX-Tree rescanen:
```python
time.sleep(8)  # Warten auf API-Response
tree = cua.get_window_state(pid=pid, window_id=wid)
# Suche nach: "Umfrage starten", "Starten", ">>", "Willkommensbonus"
```

### Prävention
- NIEMALS Target.getTargets() nach Survey-Start
- IMMER AX-Tree rescanen nach In-Page Content
- "Willkommensbonus-Strecke" = erfolgreicher Survey!

---

## 🔴 KRITISCH: skylight-cli element-index Instabilität (2026-05-03)

### Symptom
`skylight-cli click --pid X --element-index 29` klickt ein Browser-Icon statt "Weiter".
Der User: *"du hast ein icon in der browser leiste angeklickt statt weiter button"*

### Root Cause
`skylight-cli list-elements` returned **flachen AX-Baum** mit Browser-Chrome + Web-Content.
Der Index verschiebt sich während Page-Load.

### Lösung: CDP+AX Trinity
**Fusioniert aus 3 Forschungsansätzen + 120+ analysierten Webseiten:**

| Ansatz | Genutzt als |
|--------|-------------|
| CDP `Accessibility.queryAXTree()` | FIND: NUR Web-Content |
| CDP `DOM.getContentQuads()` | LOCATE: Bounding Box |
| `AXUIElementCopyElementAtPosition()` + `AXPress` | CLICK: Positionsbasiert |
| `AXEnhancedUserInterface = true` | Unterstützt vollen AX-Tree |
| skylight-cli `find_by_label` | Fallback |
| cua-driver `get_window_state` click | Popup-Fallback |

### Implementierung
**Modul**: `cli/modules/cdp_click.py` (NEU, geplant)

```python
async def click_by_label(pid, cdp_port, label, role):
    """CDP queryAXTree → bounding box → AXPress"""
    ws = await _connect_cdp(cdp_port)
    backend_id = await _query_ax(ws, label, role)
    quad = await _get_quad(ws, backend_id)
    center = ((quad[0] + quad[2]) / 2, (quad[1] + quad[3]) / 2)
    return _ax_click_at(pid, *center)
```

**Key Fixes:**
- Word-Boundary in Label-Matching (`\bWeiter\b` ≠ "Weitere")
- CDP liefert NUR Web-Content (kein Browser-Chrome)
- Position-basiert statt Index-basiert (stabil)

---

## ✅ E2E LOGIN FIX (2026-05-03, PID 16811)

**Problem**: Passkey "Fortfahren" wurde nicht gefunden/geklickt.
**Root Cause**: 
  1. Fortfahren ist IM Google OAuth Popup (nicht im Hauptfenster!)
  2. Code nutzte skylight statt cua für Popup-Klicks
  3. ax_scan stderr wurde nicht erfasst
  4. Popup-Titel ändert sich → "Passkey" fehlte in title_patterns

**Lösung** (5 Commits):
  1. `passkey_popup.py`: cua-only → `cua.get_window_state(popup_wid)` → find "Fortfahren" → `cua.click`
  2. `consent_screen.py`: cua-only → kein skylight-Fallback mehr
  3. `ax_scan.py`: stderr capture, robust JSON parsing
  4. `heypiggy_login.py`: 15× Retry mit 1.5s, _safe_click für FaceID-Timeout
  5. `cua_popup.py`: "Passkey" zu title_patterns

## ✅ MACOS-AX-CLI `find` funktioniert, `windows list` crashed
**Problem**: `macos-ax-cli windows list` → NSInvalidArgumentException crash
**Lösung**: Swift `[[String: Any]]` statt `__SwiftValue` für listAllWindowsDict()

## ✅ ax_scan stderr Capture
**Problem**: macos-ax-cli schreibt Output nach stderr statt stdout.
**Fix**: `_run()` liest `r.stdout or r.stderr`.

## 🔧 Word-Boundary Label Fix (2026-05-03)
**Problem**: `label_lower in el_label` matched "Weiter" in "Weitere Informationen"
**Fix**: `re.search(r'\b' + re.escape(label) + r'\b', el_label, re.IGNORECASE)`
**Betroffen**: `find_by_label()`, `_find_element()`, `_find_in_elements()`, `wait_for_element()`

## 🔧 cua-touch Label Parsing
**Problem**: 3 verschiedene Label-Formate im AX-Tree
**Fix**: Parsing für `": \"Label\""`, `"= \"X\" (Label)"`, `"= \"X\""` Formate

## 🔧 Prompt- und API-Fixes
- Nemotron Omni: `content > reasoning` Priority
- `max_tokens: 300 → 1000` (Reasoning braucht ~400 Tokens)
- Image Resize: 50% Thumbnail (960px) für API-Timeout-Fix
- Page Detection via AXWebArea-Label
