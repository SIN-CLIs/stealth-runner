# PLAN: ax-graph Swift CLI — Unified AX Indexer

> **Quelle:** Plane Wiki `chat verlauf mit agent 2` (256966ad)
> **Repo:** 🔴 **NEU** `SIN-CLIs/ax-graph` — eigenes Repo wie skylight-cli, screen-follow
> **Abhängigkeiten:** Keine
> **Priorität:** 🔴 KRITISCH
> **Aufwand:** Groß (neues GitHub Repo SIN-CLIs/ax-graph + Swift CLI)

---

## 🔍 Stealth Suite Kontext

**ax-graph ist das FEHLENDE GLIED im Stack.** Die aktuelle Suite hat:
- ✅ `skylight-cli` — AXPress für Hauptfenster (Swift, GitHub: SIN-CLIs/skylight-cli)
- ✅ `cua-touch` — Popup-Interaktion (Python, GitHub: SIN-CLIs/cua-touch)
- ✅ `cua-driver` — Swift Binary der von cua-touch aufgerufen wird (`/Applications/CuaDriver.app`)
  ⚠️ Binary Source ist NICHT auf GitHub gesichert!
- ✅ `unmask-cli` — CDP für DOM (TypeScript, GitHub: SIN-CLIs/unmask-cli)
- ✅ `macos-ax-cli` — System-Scan (Swift, lokal-only `~/dev/macos-ax-cli/`, NICHT auf GitHub)

**Was fehlt:** Ein Tool, das ALLE drei AX-Quellen (System-AX + Chrome-AX + CDP) in EINEN Graphen merged → **ax-graph**.

> **⚠️ Wichtig:** Der `cua-driver` Swift Source Code ist nirgends auf GitHub gesichert.  
> Nur das kompilierte Binary existiert unter `/Applications/CuaDriver.app`.  
> **ax-graph** sollte daher in Swift geschrieben werden und den Source Code auf GitHub sichern.
> Auch `macos-ax-cli` existiert lokal (`~/dev/macos-ax-cli/`) aber wurde NIE auf GitHub gepushed.

---

## 🎯 Ziel

Ein neues Swift CLI `ax-graph`, das ALLE drei AX-Quellen (System-AX + Chrome-AX + CDP) in EINEN vereinheitlichten Graphen zusammenführt — mit stabilen SHA256-basierten `node_id`s und live Mutation Tracking via AXObserver.

## 📋 Architektur

```
ax-graph snapshot --all                  # alle Apps, alle Fenster, alle Elemente
ax-graph snapshot --pid 12345            # nur eine App (rekursiv inkl. Popups)
ax-graph snapshot --bundle com.google.Chrome --include-dom-id
ax-graph watch --pid 12345               # AXObserver-basiert, streamt Mutations als JSONL
ax-graph resolve --node-id <hash>        # gibt AXUIElement-Pointer zurück (für click)
```

### Output-Schema

```json
{
  "snapshot_id": "snap:a1b2c3d4",
  "timestamp": 1730000000.0,
  "apps": [{
    "pid": 12345,
    "bundle_id": "com.google.Chrome",
    "windows": [{
      "window_id": "W1",
      "title": "Heypiggy Dashboard",
      "elements": [{
        "node_id": "axg:a3f2...",
        "role": "AXButton",
        "title": "Continue with Google",
        "dom_id": "google-signin-btn",
        "dom_classes": ["btn", "primary"],
        "frame": [612, 410, 200, 44],
        "actions": ["AXPress"],
        "path": "AXWindow/AXGroup[0]/AXButton[2]"
      }]
    }]
  }]
}
```

## 🏗️ Modul-Struktur

```
ax-graph/
├── Package.swift                    # Swift 5.9, ArgumentParser + Crypto
├── Sources/ax-graph/
│   ├── main.swift                   # CLI Entry Point + CommandConfiguration
│   ├── AXAttributes.swift           # AXAttr Helper (string, bool, point, size, children)
│   ├── AXNode.swift                 # AXNode struct + NodeID (SHA256)
│   ├── AXTreeWalker.swift           # Rekursiver Tree-Walker (maxDepth, includeDOM)
│   ├── AppEnumerator.swift          # NSWorkspace + AXUIElementCreateApplication
│   ├── Snapshot.swift               # snapshot Subcommand
│   ├── Watch.swift                  # watch Subcommand (AXObserver)
│   └── Resolve.swift                # resolve Subcommand (node_id → AXPress)
```

## ✅ Sub-Tasks

### Phase 1: Swift CLI Scaffold
- [ ] `Package.swift` mit Dependencies (ArgumentParser, Crypto)
- [ ] `main.swift` mit CommandConfiguration + Subcommands
- [ ] `AXAttributes.swift` — Attribute Reader (string, bool, point, size, children, actionNames)
- [ ] `AXNode.swift` — Node Struct + `NodeID.make()` SHA256

### Phase 2: Snapshot Engine
- [ ] `AppEnumerator.swift` — Alle laufenden Apps + Fenster enumerieren
- [ ] `AXTreeWalker.swift` — Rekursiver Walk mit Depth-Limit
- [ ] `Snapshot.swift` — JSON Output (pretty + compact)
- [ ] Test: `ax-graph snapshot --pid $(pgrep -x Google Chrome)`

### Phase 3: AXObserver Live Tracking
- [ ] `Watch.swift` — AXObserverCreate + CFRunLoopAddSource
- [ ] Mutation Events: kAXUIElementDestroyedNotification, kAXFocusedWindowChangedNotification
- [ ] Streaming Output: JSONL pro Mutation

### Phase 4: Resolve + Click
- [ ] `Resolve.swift` — node_id → AXUIElement Pointer Lookup
- [ ] AXPress via resolved Pointer

## 📂 Verwandte Dateien

| Datei | Rolle |
|-------|-------|
| `cli/modules/cdp_click.py` | CDP+AX für Web-Content (Referenz für Resolve) |
| `cli/modules/cua_popup.py` | cua-driver Popup-Wrapper (Referenz für Popup-Handling) |
| `docs/apple-tool-library.md` | Apple Tool Library (wird um ax-graph ergänzt) |
| `SOTA.md` | State of the Art (wird aktualisiert) |
| `brain.md` | Systemwissen (wird aktualisiert) |

## 🔗 Issue

[ISSUE-SR-11: ax-graph Swift CLI](../issues/ISSUE-SR-11.md)
