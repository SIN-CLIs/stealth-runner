# AGENTS.md — Stealth Survey CLI

> **← [../AGENTS.md](../AGENTS.md) ist das MASTER Regelwerk.**
> **← [../sinrules.md](../sinrules.md) ist das zentrale Regelwerk.**

## 🚨 ARCHÄOLOGIE-TSUNAMI — PFLICHT VOR JEDER AKTION

**REGEL: Jeder Agent MUSS vor dem ersten Code-Edit einen vollständigen Archäologie-Tsunami starten.**

### Warum?
- Alter Code = extrem gefährlich (tötet User Chrome, leaked Credentials)
- Falscher Code = verwirrt Agents unnötig
- Lügen-Code = das Schlimmste was in einer Entwicklung geschehen kann
- Nicht ausreichend kommentierter Code = nächster Agent zerstört alles wieder

### Pflicht-Prozedur (IN DIESER REIHENFOLGE):
1. **Explore Subagent starten**: Scan ALLER Repos und Code-Dateien
2. **Kategorisieren**: 🔥 DELETE (alt/broken/banned) | ⚠️ LEGACY | ✅ ACTIVE
3. **BANNED-Patterns prüfen**: playstealth, webauto-nodriver, pkill -f Google Chrome, hardcoded PIDs, --remote-allow-origins=* ohne Quotes
4. **Löschen**: Alle 🔥 DELETE Dateien SOFORT entfernen
5. **Kommentieren**: Jede verbleibende Code-Datei mit extremen Kommentaren ausstatten:
   - Was macht diese Datei?
   - Warum existiert sie?
   - Was ist die Architektur?
   - Was sind die Abhängigkeiten?
   - BANNED-Methoden als Warnung
   - Jede Funktion dokumentieren
   - Jede Konstante erklären
   - Warum-Fragen beantworten
6. **Test-Dateien**: Kein Tool ohne Test-Dateien!

### Selbst wenn sich ein Agent "alles wissen" einbildet:
- **ER LÜGT**. Immer. Jeder Agent denkt er weiß es, aber er liegt.
- **Er MUSS trotzdem recherchieren**. Keine Ausnahmen.
- **Er MUSS die aktuellen Commits prüfen**. Gestern war alles anders.

### Bei Abweichung (Code entspricht nicht Schema):
1. SOFORT Deep-Recherche starten (alle Repos, Issues, Commits)
2. ALLE betroffenen Dateien identifizieren
3. Kommentare/Dokumentation in ALLEN betroffenen Dateien nachholen
4. BANNED-Patterns in Code UND Doku markieren

## 🚨 EXPLICITE VERBOTE (UNVERBRÜCHLICH)

### Chrome Startup
- ❌ `playstealth launch` — setzt NICHT --force-renderer-accessibility
- ❌ Chrome OHNE `--force-renderer-accessibility` — cua-driver AX-Tree LEER
- ❌ Chrome OHNE `--remote-allow-origins="*"` (MIT Quotes!) — CDP WebSocket 403
- ✅ Chrome MANUELL starten: `/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9999 --remote-allow-origins="*" --force-renderer-accessibility --no-first-run --user-data-dir=/tmp/heypiggy-new-$(date +%s) URL`

### User Chrome
- ❌ `pkill -f "Google Chrome"` — VERBOTEN (tötet User Chrome!)
- ❌ `killall Google Chrome` — VERBOTEN
- ❌ `kill <pid>` auf USER Chrome PIDs — VERBOTEN
- ✅ NUR Bot-Chrome beenden (profile=/tmp/heypiggy-new-*)

### Tools
- ❌ webauto-nodriver — ABSOLUT BANNED
- ❌ cua-driver click (raw index) — instabil, nutze tool_click.py
- ❌ skylight-cli click --element-index — Index instabil
- ❌ Hardcoded PIDs — dynamisch, niemals hardcodieren

## NEMO Architecture

```
Compact Snapshot (skylight/CDP) → Nemotron Decision (NIM) → Batch Execute (CDP) → Memory/Guardian
```

Vorteil: 1 LLM-Call PRO SEITE (nicht pro Element!) = 10× effizienter
