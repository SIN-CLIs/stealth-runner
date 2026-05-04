# PLAN: skylight-cli DOM Patch — AXDOMIdentifier/AXDOMClassList

> **Quelle:** Plane Wiki `chat verlauf mit agent 2` (256966ad) §4  
> **Abhängigkeiten:** Keine (Patch für bestehendes skylight-cli Repo ✅ SIN-CLIs/skylight-cli)  
> **Priorität:** 🟡 HOCH  
> **Aufwand:** Klein (Einzelfile Patch)

---

## 🔍 Recherche-Ergebnisse

`skylight-cli` (Swift, GitHub: SIN-CLIs/skylight-cli) liest bereits:
- `kAXIdentifierAttribute` über `AXElementFinder.swift`
- Nutzt bereits `_AXObserverAddNotificationAndCheckRemote` für Tree-Resilienz
- Aktuelle Element-Struct: `frame`, `label`, `role`, `path`, `axElement`

**Fehlt:** `AXDOMIdentifier` + `AXDOMClassList` lesen und in JSON-Output aufnehmen.

**Bestehende Dateien (lokal):** `~/dev/skylight-cli/Sources/skylight/CLI.swift` (Zeilen 244-269)

---

## 🎯 Ziel

skylight-cli erweitern um Chrome-spezifische AX-Attribute `AXDOMIdentifier` und `AXDOMClassList` zu lesen. Damit kann der AX-Tree direkt DOM `id`/`class` liefern — ohne CDP.

## 🔍 Warum

Chrome 148+ exponiert `AXDOMIdentifier` und `AXDOMClassList` im AX-Tree.  
Das sind der **heilige Gral**: stabile DOM-Identifikatoren direkt aus dem AX-Tree,  
auch in Popups/OAuth-Sheets wo CDP nicht rankommt.

## 🏗️ Implementation

### Datei: `AXChromeAttributes.swift` (neuer File in skylight-cli)

```swift
enum AXChromeAttr {
    static let domIdentifier  = "AXDOMIdentifier"
    static let domClassList   = "AXDOMClassList"
    static let url            = "AXURL"
}
```

### Änderungen in `list-elements`

- Nach `kAXIdentifierAttribute` auch `AXDOMIdentifier` + `AXDOMClassList` auslesen
- In der JSON-Ausgabe als `"dom_id"` und `"dom_classes"` ergänzen

## ✅ Sub-Tasks

- [x] AXElement um domId/domClasses erweitert ✅
- [x] `collect()` liest AXDOMIdentifier + AXDOMClassList ✅
- [x] `stringArrayAttr` Helper hinzugefügt ✅
- [x] `list-elements` JSON-Output: dom_id, dom_classes ✅
- [x] Commit: `fa5c558` auf SIN-CLIs/skylight-cli ✅
- [ ] Test mit Chrome: `skylight-cli list-elements --pid CHROME_PID` → dom_id sichtbar?
- [ ] Stealth-Runner-seitig: `cdp_click.py` kann dom_id aus AX nutzen

## 📂 Verwandte Dateien

| Datei | Rolle |
|-------|-------|
| `cli/modules/cdp_click.py` | Kann AXDOMIdentifier als Fallback nutzen |
| `docs/apple-tool-library.md` | AXDOMIdentifier dokumentieren |

## 🔗 Issue

[ISSUE-SR-12: skylight-cli DOM Patch](../issues/ISSUE-SR-12.md)
