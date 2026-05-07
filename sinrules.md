# sinrules.md — SIN-CLIs Stealth-Quad: Alle Regeln & Architektur

> **Letztes Update**: 2026-05-06 | **Gültig für**: Alle SIN-CLIs Repos
>
> **NEMO AKTIV**: Compact Snapshot + NVIDIA NIM + Batch Execute ist PRIMARY Architektur.
> - `skylight-cli` = RE-ACTIVATED für `snapshot-compact` + `batch` (nicht click!)
> - `webauto-nodriver` = ABSOLUT BANNED (keine CDP MCP Server nutzen!)
> - `cua-driver` = DEPRECATED (nur Legacy-Fallback, kein neuer Code)
> - CDP WebSocket = PRIMARY für direkten Zugriff (Runtime.evaluate, niemals Navigation)
>
> Diese Datei ist DAS zentrale Regelwerk. ALLE anderen md-Dateien verweisen hierher.

---

## 🔗 Cross-Reference Map (ALLE md-Dateien verlinkt)

| Datei | Zweck | Verlinkung |
|---|---|---|
| **[sinrules.md](sinrules.md)** | ← DU BIST HIER: Zentrales Regelwerk | Verweist auf ALLE anderen |
| [brain.md](brain.md) | NEMO Architektur + CDP+AX Trinity | ← sinrules.md ist die Quelle |
| [learn.md](learn.md) | Fusionierte Learnings | ← sinrules.md definiert Muster |
| [fix.md](fix.md) | Root Cause Fix (Index-Problem) | ← sinrules.md §BANNED |
| [issues.md](issues.md) | Kritisches Index-Problem | ← sinrules.md §ARCHITEKTUR |
| [AGENTS.md](AGENTS.md) | NEMO Tool-Befehle | ← sinrules.md §TOOLS |
| [plan.md](plan.md) | NEMO Implementierungsplan | ← sinrules.md §PLAN |
| [anti-learn.md](anti-learn.md) | Anti-Patterns | ← sinrules.md §BANNED |
| [successful.md](successful.md) | Erfolgreiche Flows | ← sinrules.md §FLOWS |
| [commands.md](commands.md) | CLI-Befehle | ← sinrules.md §TOOLS |
| [goal.md](goal.md) | Ziele & Meilensteine | ← sinrules.md §ZIELE |
| [README.md](README.md) | Projekt-README | ← sinrules.md ist die Referenz |

---

## §1 — GOLDEN RULES (UNVERBRÜCHLICH)

### R1: NEMO ist PRIMARY — Compact Snapshot + NIM + Batch Execute
```
❌ CDP queryAXTree → getContentQuads (CDP ist BANNED für Navigation!)
❌ skylight-cli click --element-index (Index instabil! Nutze batch!)
❌ cua-driver für neue Features (DEPRECATED, nur Legacy-Fallback!)
❌ webauto-nodriver (ABSOLUT BANNED)
✅ src/stealth_survey → NEMO Loop (SurveyAgent + NIMClient + BatchExecutor)
✅ skylight-cli snapshot-compact → kompakte @eN Snapshots
✅ skylight-cli batch → Batch-Aktionen ausführen
✅ CDP WebSocket Runtime.evaluate → direkte JS-Execution (Fallback)

JEDE Survey-Seite läuft über:
1. Compact Snapshot (skylight-cli / CDP) → @eN Element-Refs
2. Nemotron Decision (NVIDIA NIM) → Actions Array
3. Batch Execute (CDP WebSocket) → Alle Actions in EINEM Call
4. Memory + Guardian → Lernen aus jedem Schritt
```

### R2: NEMO Tool-Chain für ALLE Interaktionen
```
skylight-cli snapshot-compact  → Kompakte @eN Snapshot-Generierung
skylight-cli batch             → Batch-Aktionen ausführen (NEU, PRIMARY)
CDP WebSocket Runtime.evaluate → JS-Execution (Fallback)
cua-driver call get_window_state → AX-Tree lesen (Legacy-Fallback)
cua-driver call click           → AXPress (Legacy, nur wenn NEMO nicht verfügbar)
cua-driver call set_value       → Text eingeben (Legacy-Fallback)
cua-driver call press_key       → Tastendrücke (Legacy-Fallback)
```

### R3: NIEMALS Apple-Menüleiste anklicken
```
depth < 5 = Apple-Systemmenü (AXMenuBar, AXMenuBarItem, AXMenu)
depth > 5 = Browser-Content (AXButton, AXTextField, etc.)
IMMER depth > 5 FILTER setzen beim Suchen von Elementen!
```

### R4: Daemon mit nohup starten (NUR für cua-driver Legacy-Fallback)
```
nohup cua-driver serve > /tmp/cua-daemon.log 2>&1 &
Vor jeder Aktion prüfen: pgrep -f "cua-driver serve"
Ohne Daemon: kein Session-Cache → keine Clicks!
```

### R5: Fallback-Kette immer bereit
```
1. NEMO (PRIMARY) — Compact Snapshot + NIM + Batch (1 LLM-Call pro Seite!)
2. CDP WebSocket (Fallback) — Runtime.evaluate für direkte JS-Execution
3. cua-driver (Legacy) — window-id targetiert (NUR wenn NEMO + CDP versagen)
4. skylight-cli (Legacy) — label-basiert, Hauptfenster (DEPRECATED)
5. macos-ax-cli (Scan) — nur zum Finden, nie zum Klicken
```

### R6: Word-Boundary Label-Matching
```
"weiter" in "Weitere Informationen" → ❌ FALSCH
\bWeiter\b → ✅ RICHTIG (matcht NUR "Weiter", nicht "Weitere")
```
Jedes Label-Matching MUSS `\b` word-boundary nutzen!

### R7: Jeder Flow dynamisch — UI ändert sich jederzeit
```
Google kann Flows KÜRZEN (Cookies)
→ IMMER dynamische Erkennung + Fallback-Strategie
→ NIE fixe Indices hardcodieren!
```

### R8: NACH jedem Erfolg: 100% Dokumentation
```
Jeder erfolgreiche Command → commands.md
Jeder Bug-Fix → fix.md + issues.md
Jede neue Erkenntnis → learn.md + brain.md
```

---

## §2 — BANNED

| Pattern | Warum |
|---------|-------|
| `skylight-cli click --element-index` für Web-Content | Index instabil, nutze `skylight-cli batch` stattdessen |
| `cua-driver` für neuen Code | DEPRECATED — NEMO ist PRIMARY |
| `element_index=35` hardcodiert | UI ändert sich |
| Mausbewegung, Koordinaten raten | BANNED |
| `recovery_mode: true`, `omni_fallback: llama` | Legacy |
| OpenAI statt NVIDIA NIM | BANNED |
| Direkt Chrome statt playstealth | BANNED |
| `webauto-nodriver` | ABSOLUT BANNED |

---

## §3 — ARCHITEKTUR

### §3.1 — NEMO LOOP (PRIMARY, 2026-05-06)

```
Compact Snapshot (skylight/CDP) → Nemotron Decision (NIM) → Batch Execute (CDP) → Memory/Guardian

┌──────────────────────────────────────────────────────────────────────────┐
│                 NEMO LOOP — 1 LLM Call pro Frage-Batch                   │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  while not complete:                                                      │
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────┐     │
│  │ SCHRITT 1: COMPACT SNAPSHOT (skylight-cli / CDP)                │     │
│  │                                                                  │     │
│  │ skylight-cli snapshot-compact --pid X --semantic                 │     │
│  │ → {                                                              │     │
│  │     "refs": {"@e0": {role:"radio",text:"Männlich"},...},       │     │
│  │     "semantic": {"questions":[...], "progress":"3/10"},         │     │
│  │     "provider": "qualtrics",                                     │     │
│  │     "stealthScore": 0.92                                         │     │
│  │   }                                                              │     │
│  └──────────────────────────────────────────────────────────────────┘     │
│       │                                                                   │
│       ▼                                                                   │
│  ┌──────────────────────────────────────────────────────────────────┐     │
│  │ SCHRITT 2: NEMOTRON DECISION (NVIDIA NIM)                        │     │
│  │                                                                  │     │
│  │ NIMSurveyClient.decide(snapshot, profile, learnings)             │     │
│  │ → {"actions": [                                                  │     │
│  │     {"ref": "@e0", "action": "select"},                          │     │
│  │     {"ref": "@e12", "action": "fill", "value": "32"},            │     │
│  │     {"action": "submit"}                                         │     │
│  │   ]}                                                             │     │
│  │                                                                  │     │
│  │ Token-Effizient: ~500 tokens in, ~100 tokens raus                │     │
│  └──────────────────────────────────────────────────────────────────┘     │
│       │                                                                   │
│       ▼                                                                   │
│  ┌──────────────────────────────────────────────────────────────────┐     │
│  │ SCHRITT 3: BATCH EXECUTE (CDP WebSocket)                         │     │
│  │                                                                  │     │
│  │ BatchExecutor.execute(ws_url, actions, provider)                 │     │
│  │ → Alle Actions in EINEM WebSocket-Call:                          │     │
│  │ Runtime.evaluate("(function(){...alle actions...})()")           │     │
│  └──────────────────────────────────────────────────────────────────┘     │
│       │                                                                   │
│       ▼                                                                   │
│  ┌──────────────────────────────────────────────────────────────────┐     │
│  │ SCHRITT 4: MEMORY + GUARDIAN (auto)                              │     │
│  │                                                                  │     │
│  │ stealth_memory.log_step(snapshot, decision, result)              │     │
│  │ stealth_guardian.monitor_and_heal(session, result)               │     │
│  └──────────────────────────────────────────────────────────────────┘     │
│                                                                           │
│  Vorteil: 1 LLM-Call PRO SEITE (nicht pro Element!)                      │
│           90% Token-Ersparnis durch Compact Snapshot                      │
│           5× schneller als cua-driver Loop                               │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
```

### §3.2 — CDP+AX Trinity (LEGACY/DEPRECATED)

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
| **PRIMARY** | **NEMO (src/stealth_survey/)** | Survey-Loop: Compact Snapshot + NIM + Batch |
| **PRIMARY** | **skylight-cli snapshot-compact** | Kompakte @eN Snapshots |
| **PRIMARY** | **skylight-cli batch** | Batch-Aktionen ausführen |
| FALLBACK 1 | CDP WebSocket Runtime.evaluate | Direkte JS-Execution |
| LEGACY FALLBACK | cua-driver | Popups/Sheets (nur Bestand) |
| SCAN ONLY | macos-ax-cli | System-weite Erkennung |

---

## §5 — MODULSTRUKTUR

```
src/stealth_survey/           ← NEU: NEMO Compact Batch Survey Engine
├── __init__.py                → Public API
├── survey_agent.py            → SurveyAgent: run_survey(), run_loop()
├── nim_client.py              → NIMSurveyClient: decide(), decide_with_tools()
├── compact_snapshot.py        → CompactSnapshotGenerator: CDP → @eN snapshot
└── batch_executor.py          → BatchExecutor: actions → CDP JS execution

cli/modules/                   ← LEGACY (nur Fallback)
├── cdp_click.py                CDP+AX Trinity Klick-Engine (DEPRECATED)
├── cua_popup.py                cua-driver Popup-Wrapper (DEPRECATED)
├── skylight_main.py            skylight-cli Hauptfenster (DEPRECATED)
├── ax_scan.py                  macos-ax-cli System-Scan
├── google_email.py             Email-Eingabe
├── passkey_popup.py            Passkey-Erkennung
├── consent_screen.py           Consent-Screen
└── dashboard_verify.py         Balance-Verifikation

### OpenCode Skill
- **survey-runner** Skill: `infra-sin-opencode-stack/skills/survey-runner/SKILL.md`
- Installiert via `sync_dir_additive` in `infra-sin-opencode-stack/install.sh`
- Dokumentiert in `stealth-runner/AGENTS.md` §SURVEY-CLI
- Stealth Suite (23+ Repos): stealth-runner, stealth-core, stealth-session, stealth-guardian, stealth-memory, stealth-captcha, stealth-skills, playstealth-cli, skylight-cli, cua-touch, macos-ax-cli
```

---

## §6 — KRITISCHE REGELN

1. **NEMO ist PRIMARY** — Compact Snapshot → NIM Decision → Batch Execute pro Seite
2. **skylight-cli batch** für Batch-Aktionen, **niemals** `skylight-cli click --element-index`
3. **CDP WebSocket** als Fallback für Runtime.evaluate (niemals für Navigation!)
4. **cua-driver** = LEGACY ONLY (kein neuer Code, nur bestehende Flows)
5. **NIE Koordinaten-basiertes Klicken** (`--x --y`) → NUR element refs (@eN)
6. **NIE `label in el_label`** → `\b` word-boundary regex nutzen!
7. **CDP-Port kommt von playstealth launch** → `cdp_port` aus JSON-Output
8. **Jeder Klick = FIND + LOCATE + CLICK** → nie blind klicken

## §7 — stealth-session + Verify-Box (2026-05-04)

### R9: JEDER Befehl mit verify:true ausführen!
```
stealth-exec cua-touch --action click --label "Männlich" --verify
→ Nur success:true wenn AXRadioButton.selected == true
```

### R10: IdiotProofGuard blockiert automatisch
- Falsche PID/WID → Reparatur
- CDP-JS dispatchEvent → Block
- time.sleep(≥4) → Block
- MD überschreiben → Block
- 3 Fehler → STOP
- Verify fehlt → Einfügen

## §8 — Commands Verzeichnis (2026-05-05)

### R11: Jeder verifizierte Command → /commands/<name>.md
Alle funktionierenden, getesteten Commands kommen als separate MD-Datei in `/commands/`:
```
/commands/kill-bot-chrome.md    ✅ VERIFIED
/commands/find-bot-pids.md      ✅ VERIFIED
```

### R12: Jeder fehlgeschlagener Command → /commands/banned-<name>.md
Alle verbotenen, kaputten Commands kommen als `banned-*` Datei:
```
/commands/banned-pkill-heypiggy-bot.md   ❌ BANNED
/commands/banned-killall-chrome.md       ❌ BANNED
/commands/banned-hardcoded-pids.md       ❌ BANNED
```

### R13: Chrome Kill Regeln (UNVERBRÜCHLICH)
- ❌ `pkill -f "heypiggy-bot"` → killt ALLE Chrome-Instanzen (USER + BOT!)
- ❌ `killall Google Chrome` → killt ALLE Chrome (USER + BOT!)
- ❌ Hardcoded PIDs (71104, 70293, etc.) → PIDs sind dynamisch!
- ✅ NUR Main-Prozesse killen die `/Contents/MacOS/Google Chrome` + `/tmp/heypiggy-bot-` haben
- ✅ Registry leeren: `rm -f ~/.stealth/sessions.json`
- ✅ SessionManager.close_all() nutzen (SOTA Alternative)

## §9 — NEMO ARCHITECTURE (2026-05-06)

### Modulstruktur

```
src/stealth_survey/           ← NEMO Compact Batch Survey Engine
├── __init__.py                → Public API: SurveyAgent, NIMSurveyClient, BatchExecutor
├── survey_agent.py            → SurveyAgent.run_survey() — Haupt-Loop
├── nim_client.py              → NIMSurveyClient.decide() — NVIDIA NIM Inferenz
├── compact_snapshot.py        → CompactSnapshotGenerator — CDP → @eN Snapshot
└── batch_executor.py          → BatchExecutor.execute() — CDP JS Batch-Ausführung
```

### Flow: NEMO Loop (pro Survey-Seite)

```
run_survey(session, profile):
  while survey_active:
    snapshot = compact_snapshot.generate(pid, page)     # ~200 tokens
    actions  = nim_client.decide(snapshot, profile)     # ~100 tokens
    result   = batch_executor.execute(ws_url, actions)  # 1 WebSocket call
    memory.log(snapshot, actions, result)
    guardian.monitor_and_heal(session, result)
```

### Token-Effizienz

| Phase | In | Out | Round-Trips |
|-------|----|-----|-------------|
| Compact Snapshot | ~0 (CDP) | ~200 tokens | 1 |
| NIM Decision | ~500 tokens | ~100 tokens | 1 |
| Batch Execute | ~0 (CDP) | ~0 | 1 |
| **TOTAL pro Seite** | **~500 tokens** | **~100 tokens** | **3 calls** |

Vergleich:
- **cua-driver Loop**: ~5000+ tokens in, 20+ calls pro Seite
- **NEMO Loop**: ~500 tokens in, 3 calls pro Seite = **10× effizienter**

### skylight-cli Commands (NEU, SR-37)

| Command | Zweck | Beispiel |
|---------|-------|----------|
| `snapshot-compact` | Kompaktes @eN Snapshot | `skylight-cli snapshot-compact --pid X --semantic` |
| `find` | Element per role/text/label finden | `skylight-cli find --role button --text "Weiter"` |
| `batch` | Batch-Aktionen ausführen | `skylight-cli batch '[{"ref":"@e0","action":"click"}]'` |

### Verboten vs. Erlaubt (NEMO-Update)

| Tool | Status | Begründung |
|------|--------|------------|
| **skylight-cli** snapshot-compact | ✅ ERLAUBT | PRIMARY — Compact Snapshot |
| **skylight-cli** batch | ✅ ERLAUBT | Batch-Ausführung |
| **CDP WebSocket** Runtime.evaluate | ✅ ERLAUBT | Fallback wenn skylight nicht verfügbar |
| **src/stealth_survey/** | ✅ ERLAUBT | NEMO Survey Engine |
| **cua-driver** | ⚠️ DEPRECATED | Nur Fallback, NEMO ist PRIMARY |
| skylight-cli click (index) | ❌ BANNED | Nutze batch stattdessen |
| webauto-nodriver | ❌ BANNED | Absolut |
