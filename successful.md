# successful.md – Was funktioniert (SOTA)

## Core-Loop
1. Browser starten → `playstealth-cli launch` ✅
2. Screenshot mit SoM → `skylight-cli screenshot --mode som` ✅
3. Vision-Entscheidung → Llama 4 Scout / NVIDIA Mistral ✅
4. Unsichtbarer Klick → AXPress via `skylight-cli click` ✅
5. Stealth-Verifikation → `unmask-cli verify-stealth` ✅
6. Recovery bei Detektion → erneuter Versuch ✅

## Architektur
- State Machine mit 10 Zuständen ✅
- Checkpoint-Resume nach Crash ✅
- Human-Profile (scipy.stats PDFs) ✅
- Temp-Profile pro Session ✅

## NICHT funktionierend
- DOM-Prescan (ENTFERNT – klickte blind Element 1)
- `CGEventPostToPid` (TOT auf Chrome 148)
