# BANNED: webauto-nodriver

## Status: ❌ ABSOLUT BANNED

> Siehe: [sinrules.md §2](sinrules.md) — §BANNED | [AGENTS.md](AGENTS.md) — BAN REGELN

## Regel

```
❌ webauto-nodriver = ABSOLUT BANNED (keine CDP MCP Server nutzen!)
```

## Warum

- `webauto-nodriver` ist ein **CDP MCP Server** — in sinrules.md explizit verboten
- Browser-Automatisierung über MCP läuft AUSSERHALB der kontrollierten Tool-Chain
- Keine Verify-Box, keine Anti-Stuck, keine Memory-Integration
- Chrome-Instanz wird nicht über `playstealth launch` oder `survey/chrome.py` verwaltet → Session-Konflikte
- Origin-Check-Probleme bei CDP WebSocket (403 Forbidden)
- Alle Chrome-Instanzen die über MCP gestartet werden, sind NICHT in der Session-Registry

## Was stattdessen nutzen

| Use Case | Tool | Command |
|----------|------|---------|
| Chrome starten | `survey/chrome.py` | `launch_chrome()` mit ALLEN Flags |
| Survey ausführen | `survey.py` | `./survey.py loop --max 5` |
| Dashboard scannen | `survey.py` | `./survey.py scan` |
| Login | `survey.py` | `./survey.py login` |
| Status prüfen | `survey.py` | `./survey.py status` |
| CDP für JS execute | CDP WebSocket | `Runtime.evaluate()` — NUR für JS-Ausführung |
| Tab-Detection | `tools/tool_find_new_tab.py` | `find_new_tab(port, known)` |
| Modal cleanup | `tools/tool_close_modals.py` | `close_modals(ws_url)` |
| Snapshot | `tools/tool_snapshot.py` | `snapshot(ws_url)` |
| Completion | `tools/tool_detect_completion.py` | `detect(ws_url)` |
| Anti-Stuck | `tools/tool_anti_stuck.py` | `AntiStuck(threshold=3)` |

## Richtige Chrome-Flags

```bash
# RICHTIG:
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9999 \
  --remote-allow-origins=* \
  --force-renderer-accessibility \
  --no-first-run \
  --no-default-browser-check \
  --user-data-dir=/tmp/heypiggy-bot \
  URL

# FALSCH (fehlen Flags):
playstealth launch --url X    # ❌ setzt NICHT --force-renderer-accessibility
open new Chrome without flags # ❌ kein CDP-Zugriff möglich
```

## Verwandte Commands

- `/commands/banned-skylight-cli.md` — skylight-cli click verboten
- `/commands/banned-cdp-commands.md` — CDP nur für execute/evaluate, nicht Navigation
- `/commands/banned-pkill-heypiggy-bot.md` — killt alle Chrome-Instanzen
- `/commands/banned-killall-chrome.md` — killt ALLE Chrome (User + Bot)
- `/commands/banned-hardcoded-pids.md` — PIDs sind dynamisch

## Root-Cause (2026-05-07)

Agent nutzte `webauto-nodriver_webauto_health` als wäre es ein erlaubtes Tool.
Stattdessen: survey.py Commands nutzen, die alle korrekten Flags und CDP-Ports setzen.

## Test

```bash
# Verify webauto-nodriver is NOT in the allowed tools
grep -r "webauto-nodriver" /Users/jeremy/dev/stealth-runner/survey-cli/
# → sollte 0 Treffer haben (nur in banned.md DOKUMENTATION)
```