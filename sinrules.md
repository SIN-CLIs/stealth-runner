# sinrules.md — SIN-CLIs Stealth-Quad: Alle Regeln & Architektur

> **Letztes Update**: 2026-05-03 | **Gültig für**: Alle SIN-CLIs Repos
>
> **CUA-ONLY AKTIV**: cua-driver ist DAS EINZIGE Tool für Browser-Interaktion.
> - `webauto-nodriver` = ABSOLUT BANNED (keine CDP MCP Server nutzen!)
> - `skylight-cli` = DEPRECATED (nur noch für macOS-Menü wenn cua-driver komplett versagt)
> - CDP = BANNED für Navigation, NUR erlaubt für JS execute/evaluate (nicht click/navigate)
>
> Diese Datei ist DAS zentrale Regelwerk. ALLE anderen md-Dateien verweisen hierher.

---

## 🔗 Cross-Reference Map (ALLE md-Dateien verlinkt)

| Datei | Zweck | Verlinkung |
|---|---|---|
| **[sinrules.md](sinrules.md)** | ← DU BIST HIER: Zentrales Regelwerk | Verweist auf ALLE anderen |
| [brain.md](brain.md) | CDP+AX Trinity Architektur | ← sinrules.md ist die Quelle |
| [learn.md](learn.md) | Fusionierte Learnings | ← sinrules.md definiert Muster |
| [fix.md](fix.md) | Root Cause Fix (Index-Problem) | ← sinrules.md §BANNED |
| [issues.md](issues.md) | Kritisches Index-Problem | ← sinrules.md §ARCHITEKTUR |
| [AGENTS.md](AGENTS.md) | CDP+AX Tool-Befehle | ← sinrules.md §TOOLS |
| [plan.md](plan.md) | CDP+AX Implementierungsplan | ← sinrules.md §PLAN |
| [anti-learn.md](anti-learn.md) | Anti-Patterns | ← sinrules.md §BANNED |
| [successful.md](successful.md) | Erfolgreiche Flows | ← sinrules.md §FLOWS |
| [commands.md](commands.md) | CLI-Befehle | ← sinrules.md §TOOLS |
| [goal.md](goal.md) | Ziele & Meilensteine | ← sinrules.md §ZIELE |
| [README.md](README.md) | Projekt-README | ← sinrules.md ist die Referenz |

---

## §1 — GOLDEN RULES (UNVERBRÜCHLICH)

### R1: CUA-ONLY ist PRIMARY — KEIN CDP, KEIN skylight, KEIN webauto
```
❌ CDP queryAXTree → getContentQuads (CDP ist BANNED für Navigation!)
❌ skylight-cli click --element-index (Index instabil!)
❌ webauto-nodriver (ABSOLUT BANNED)
✅ cua-driver call get_window_state → find elements
✅ cua-driver call click → click buttons (mit Timeout+Retry)
✅ cua-driver call set_value → type text
✅ cua-driver call press_key → keyboard shortcuts

JEDER Klick auf Web-Content läuft über:
1. cua-driver serve (Daemon, mit nohup)
2. cua-driver call get_window_state → find element index
3. cua-driver call click → AXPress (mit 30s Timeout, 3x Retry)
4. Navigation via CUA Address-Bar: click + set_value + press_key(return)
```

### R2: NUR CUA für ALLE Interaktionen
```
cua-driver call click       → ALLE Klicks (Buttons, Checkboxen, RadioButtons)
cua-driver call set_value   → ALLE Textfelder
cua-driver call press_key   → Alle Tastendrücke (Enter, Tab, Cmd+T)
cua-driver call list_windows → Fenster finden
cua-driver call get_window_state → Elemente lesen (mit depth > 5 Filter!)
```

### R3: NIEMALS Apple-Menüleiste anklicken
```
depth < 5 = Apple-Systemmenü (AXMenuBar, AXMenuBarItem, AXMenu)
depth > 5 = Browser-Content (AXButton, AXTextField, etc.)
IMMER depth > 5 FILTER setzen beim Suchen von Elementen!
```

### R4: Daemon mit nohup starten
```
nohup cua-driver serve > /tmp/cua-daemon.log 2>&1 &
Vor jeder Aktion prüfen: pgrep -f "cua-driver serve"
Ohne Daemon: kein Session-Cache → keine Clicks!
```

### R3: Fallback-Kette immer bereit
```
1. CDP+AX (PRIMARY) — stabil, kein Index
2. skylight-cli (Fallback) — label-basiert, Hauptfenster
3. cua-driver (Popup) — window-id targetiert
4. macos-ax-cli (Scan) — nur zum Finden, nie zum Klicken
```

### R4: Word-Boundary Label-Matching
```
"weiter" in "Weitere Informationen" → ❌ FALSCH
\bWeiter\b → ✅ RICHTIG (matcht NUR "Weiter", nicht "Weitere")
```
Jedes Label-Matching MUSS `\b` word-boundary nutzen!

### R5: Jeder Flow dynamisch — UI ändert sich jederzeit
```
Google kann Flows KÜRZEN (Cookies)
→ IMMER dynamische Erkennung + Fallback-Strategie
→ NIE fixe Indices hardcodieren!
```

### R6: NACH jedem Erfolg: 100% Dokumentation
```
Jeder erfolgreiche Command → commands.md
Jeder Bug-Fix → fix.md + issues.md
Jede neue Erkenntnis → learn.md + brain.md
```

---

## §2 — BANNED

| Pattern | Warum |
|---------|-------|
| `skylight-cli click --element-index` für Web-Content | Index instabil, Browser-Chrome gemischt |
| `element_index=35` hardcodiert | UI ändert sich |
| Mausbewegung, Koordinaten raten | BANNED |
| `recovery_mode: true`, `omni_fallback: llama` | Legacy |
| OpenAI statt NVIDIA NIM | BANNED |
| Direkt Chrome statt playstealth | BANNED |

---

## §3 — ARCHITEKTUR: CDP+AX Trinity

```
┌──────────────────────────────────────────────────────────────────┐
│                     CDP+AX TRINITY                                │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  playstealth launch → cdp_port                                    │
│       │                                                           │
│       ▼                                                           │
│  CDP Accessibility.queryAXTree(label, role)                       │
│  → backendDOMNodeId + bounds (NUR Web-Content!)                   │
│       │                                                           │
│       ▼                                                           │
│  CDP DOM.getContentQuads(backendNodeId)                           │
│  → bounding box (x, y, w, h)                                      │
│       │                                                           │
│       ▼                                                           │
│  AXUIElementCopyElementAtPosition(app, cx, cy)                    │
│  → AXUIElement (position-stabil, kein Index!)                     │
│       │                                                           │
│       ▼                                                           │
│  AXUIElementPerformAction(element, kAXPressAction)                │
│  → Echter Klick (keine Maus, kein JS, kein Focus-Steal)          │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

---

## §4 — TOOLS PRIORITÄT

| Priority | Tool | Use Case |
|----------|------|----------|
| **PRIMARY** | **cdp_click (CDP+AX)** | Web-Content finden+klicken |
| FALLBACK 1 | skylight-cli | Hauptfenster |
| FALLBACK 2 | cua-driver | Popups/Sheets |
| SCAN ONLY | macos-ax-cli | System-weite Erkennung |

---

## §5 — MODULSTRUKTUR

```
cli/modules/
├── cdp_click.py         (NEU)  CDP+AX Trinity Klick-Engine
├── cua_popup.py                cua-driver Popup-Wrapper
├── skylight_main.py            skylight-cli Hauptfenster (Fallback)
├── ax_scan.py                  macos-ax-cli System-Scan
├── google_email.py             Email-Eingabe
├── passkey_popup.py            Passkey-Erkennung
├── consent_screen.py           Consent-Screen
└── dashboard_verify.py         Balance-Verifikation
```

---

## §6 — KRITISCHE REGELN

1. **NUR `cua-driver`** für Web-Content Interaktion (click, set_value, press_key)
2. **NIE Koordinaten-basiertes Klicken** (`--x --y`) → NUR element_index
3. **NIE `label in el_label`** → `\b` word-boundary regex nutzen!
3. **CDP-Port kommt von playstealth launch** → `cdp_port` aus JSON-Output
4. **Jeder Klick = FIND + LOCATE + CLICK** → nie blind klicken
5. **Fallback-Kette immer bereit** → AXPress → Koordinaten-Click → CDP (nur Navigation!)

## §7 — stealth-session + Verify-Box (2026-05-04)

### R7: JEDER Befehl mit verify:true ausführen!
```
stealth-exec cua-touch --action click --label "Männlich" --verify
→ Nur success:true wenn AXRadioButton.selected == true
```

### R8: IdiotProofGuard blockiert automatisch
- Falsche PID/WID → Reparatur
- CDP-JS dispatchEvent → Block
- time.sleep(≥4) → Block
- MD überschreiben → Block
- 3 Fehler → STOP
- Verify fehlt → Einfügen

## §8 — Commands Verzeichnis (2026-05-05)

### R9: Jeder verifizierte Command → /commands/<name>.md
Alle funktionierenden, getesteten Commands kommen als separate MD-Datei in `/commands/`:
```
/commands/kill-bot-chrome.md    ✅ VERIFIED
/commands/find-bot-pids.md      ✅ VERIFIED
```

### R10: Jeder fehlgeschlagener Command → /commands/banned-<name>.md
Alle verbotenen, kaputten Commands kommen als `banned-*` Datei:
```
/commands/banned-pkill-heypiggy-bot.md   ❌ BANNED
/commands/banned-killall-chrome.md       ❌ BANNED
/commands/banned-hardcoded-pids.md       ❌ BANNED
```

### R11: Chrome Kill Regeln (UNVERBRÜCHLICH)
- ❌ `pkill -f "heypiggy-bot"` → killt ALLE Chrome-Instanzen (USER + BOT!)
- ❌ `killall Google Chrome` → killt ALLE Chrome (USER + BOT!)
- ❌ Hardcoded PIDs (71104, 70293, etc.) → PIDs sind dynamisch!
- ✅ NUR Main-Prozesse killen die `/Contents/MacOS/Google Chrome` + `/tmp/heypiggy-bot-` haben
- ✅ Registry leeren: `rm -f ~/.stealth/sessions.json`
- ✅ SessionManager.close_all() nutzen (SOTA Alternative)
