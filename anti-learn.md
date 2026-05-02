# anti-learn.md – Anti-Patterns (was NIEMALS tun)

## ❌ skylight-cli in Popup-Fenstern

**NIEMALS** `skylight-cli click --pid X --element-index Y` wenn ein Popup offen ist.
`skylight-cli` sieht NUR das Hauptfenster. Die Element-Indices beziehen sich auf
Hauptfenster-Elemente, NICHT auf Popup-Buttons.

**Korrekt**: `cua-driver call click '{"pid":X,"window_id":W,"element_index":Y}'`

## ❌ bash mit `&` für Hintergrund-Prozesse

**NIEMALS** `bash("command &")` – blockiert trotzdem die Shell und der Agent hängt.

**Korrekt**: `interactive_bash(tmux_command="new-session -d ...")`

## ❌ playstealth launch --json am Ende

**NIEMALS** `playstealth launch --url X --json` – `--json` muss VOR `launch`.

**Korrekt**: `playstealth --json launch --url X`

## ❌ asyncio.get_event_loop() in Python 3.14+

**NIEMALS** `asyncio.get_event_loop()` – deprecated, wirft Errors.

**Korrekt**: `asyncio.new_event_loop()` + `asyncio.set_event_loop(loop)`

## ❌ OpenAI-Client für NVIDIA NIM

**NIEMALS** `import openai` oder `from openai import OpenAI`.

**Korrekt**: `import httpx; httpx.post('https://integrate.api.nvidia.com/v1/chat/completions', ...)`

## ❌ call_omo_agent (TOOL BROKEN)

**NIEMALS** `call_omo_agent` – Tool timed out auf ALLEN 9 Versuchen (30min timeout).

**Korrekt**: Direkte Tool-Nutzung (grep, ast-grep, lsp) oder Oh-My-OpenCode `task(run_in_background=true)`
