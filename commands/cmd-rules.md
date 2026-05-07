# cmd-rules.md — /commands Verzeichnis Regeln & Governance

> **Status**: AKTIV seit 2026-05-05 | **Gültig für**: ALLE /commands Einträge
> **← sinrules.md** ist das zentrale Regelwerk. Diese Datei regelt NUR /commands.

---

## §1 — GRUNDREGELN

### R1: Jeder verifizierte Command → eigene .md Datei
Jeder erfolgreich getestete Shell-Command wird als separate `.md` Datei in `/commands/` dokumentiert.

Format: `<tool>-<aktion>.md` (z.B. `cua-driver-click.md`, `playstealth-launch.md`)

### R2: Banned Patterns → zentrale `banned.md`
Verbotene Patterns werden in der zentralen `banned.md` dokumentiert (nicht mehr einzeln).

### R3: SOFORT nach erfolgreichem Test dokumentieren
Nicht warten — direkt nach dem ersten erfolgreichen Test die .md Datei erstellen.
Shell-Output als Beweis inkludieren (Zeitstempel, PID, WID).

---

## §2 — PROVIDER VERZEICHNISSE (NEU 2026-05-05)

### R4: Provider-Subdirectory wenn >1 Command
**Sobald zu einem Provider mehr als 1 Command existiert, MUSS ein Unterverzeichnis in `/commands/` angelegt werden.**

Provider = Tool, Plattform, oder Service:
- `cua-driver` → `/commands/cua-driver/`
- `heypiggy` → `/commands/heypiggy/`
- `infisical` → `/commands/infisical/`
- `playstealth` → `/commands/playstealth/`
- `google` → [cli/modules/auto_google_login.py](cli/modules/auto_google_login.py) (VERIFIED 6-Step Flow)
- `bot-chrome` → `/commands/bot-chrome/`

### R5: Banned Patterns → zentrale `banned.md`
**Verbotene Patterns werden NICHT mehr einzeln in `/commands/` dokumentiert.**

→ Siehe zentrale Datei: [`banned.md`](/banned.md)

### R6: Veraltete Einzel-Banned-Files wurden gelöscht
Folgende Dateien wurden konsolidiert in `banned.md`:
- ~~`banned-pyautogui.md`~~
- ~~`banned-pynput.md`~~
- ~~`banned-coordinates-click.md`~~
- ~~`banned-skylight-cli.md`~~
- ~~`banned-webauto-nodriver.md`~~
- ~~`banned-cdp-commands.md`~~
- ~~`banned-applescript-chrome.md`~~
- ~~`banned-recovery-mode.md`~~

---

## §3 — DATEI-STRUKTUR

### R7: Jede Command-Datei MUSS enthalten
```markdown
# <command-name> — <kurze-beschreibung>

## Status
**VERIFIED** — YYYY-MM-DD, PID=<pid> WID=<wid>

## Command
```bash
# Exakter Shell-Befehl
```

## Live Example (Datum)
```bash
# Konkreter ausgeführter Befehl mit Output
```

## Wann verwenden?
- Kontext 1
- Kontext 2

## History
- YYYY-MM-DD: Erstellt / Grund
```

### R8: Banned Command-Datei MUSS enthalten
```markdown
# BANNED: <tool-name> ❌

## Status
**BANNED** — YYYY-MM-DD, Grund

## Warum BANNED?
- Grund 1
- Grund 2

## Verbote
```bash
# ❌ FALSCH - BANNED:
command1
command2
```

## RICHTIG: Alternative
```bash
# ✅ RICHTIG:
alternative-command
```

## History
- YYYY-MM-DD: Gebannt wegen X
```

---

## §4 — NAMENSKONVENTION

### R9: Dateinamen Muster
| Typ | Muster | Beispiel |
|-----|--------|---------|
| Verified | `<tool>-<aktion>.md` | `cua-driver-click.md` |
| Banned | → `banned.md` (zentral) | Alle verbotenen Patterns |
| Provider Config | `<provider>-credentials.md` | `heypiggy-credentials.md` |
| Flow | `<provider>-<flow>.md` | `auto_google_login.py` |

### R10: Keine Umlaute, keine Sonderzeichen
NUR: `a-z`, `0-9`, `-` (Bindestrich), `.md`

---

## §5 — AKTUELLE VERZEICHNIS-STRUKTUR

```
/commands/
├── cmd-rules.md                    ← DU BIST HIER
│
├── cua-driver/                     ← 8 Commands
│   ├── click.md
│   ├── click-survey-card.md        (heypiggy-spezifisch, aber cua-driver tool)
│   ├── set-value.md
│   ├── list-windows.md
│   ├── get-window-state.md
│   ├── find-element-index.md
│   ├── find-pid-wid.md
│   └── navigate-url.md
│
├── heypiggy/                       ← 2 Commands
│   └── credentials.md
│
├── infisical/                      ← 2 Commands
│   ├── login.md
│   └── secrets.md
│
├── playstealth/                    ← 1 Command
│   └── launch.md
│
├── session-manager/                ← 1 Command
│   └── launch.md
│
├── bot-chrome/                     ← 2 Commands (verified)
│   ├── kill-bot-chrome.md
│   └── find-bot-pids.md
│
├── macos-recovery-mode.md          ← 1 Command (Root)
│
└── [banned]                        ← Konsolidiert in `banned.md`
    → Siehe [`banned.md`](/banned.md) für alle verbotenen Patterns
```

---

## §6 — CRITICAL RULES (UNVERBRÜCHLICH)

### R11: PIDs sind IMMER dynamisch — NIE hardcoden
```bash
# ✅ RICHTIG: Vor jedem Command scannen
cua-driver call list_windows | python3 -c "..." 

# ❌ FALSCH: PID hartcodiert
echo '{"pid": 71104, ...}'
```

### R12: Jeder Command mit `verify: true` wenn möglich
```bash
echo '{"pid": X, "window_id": Y, "element_index": Z, "verify": true}' | cua-driver call click
```

### R13: Nach JEDER Aktion Status prüfen
1. `list_windows` → WID noch gültig?
2. `get_window_state` → neue Elemente?
3. Weiter mit nächstem Schritt

### R14: KEINE Duplikate
Wenn ein Command schon als .md existiert → KEIN zweites Mal erstellen.
Bestehende Datei aktualisieren (mit neuem Datum/Beispiel).

---

## §7 — WORKFLOW: Neuer Command

```
1. Command ausführen + testen
2. Output verifizieren (funktioniert es?)
3. Datei erstellen: /commands/<provider>/<name>.md (oder Root)
4. Live Example mit tatsächlichem Output einfügen
5. Bei Fehlschlag: banned-<name>.md im passenden Verzeichnis
```
