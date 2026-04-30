# brain.md — Global Brain Referenz für heypiggy-survey

## Kontext vor jeder Session
```bash
node ~/dev/global-brain/src/cli.js context \
  --project heypiggy-survey \
  --goal-id survey-session \
  --description "Autonome Umfrage-Session"
```
Liest: Goal, Plan, Memory, letzte Session aus dem Brain.

## Nach jeder Session
```bash
node ~/dev/global-brain/src/cli.js extract-knowledge \
  --project heypiggy-survey \
  --session session-$(date +%Y%m%d-%H%M%S)
```
Schreibt: Facts, Mistakes, Pattern-Erkenntnisse zurück.

## Worker-Integration
Der A2A-SIN-Worker-heypiggy teilt denselben Brain. Er schreibt Fangfragen-Muster, Panel-Routing, DQ-Phrasen.
Die Stealth-Quad LIEST diese Erkenntnisse ohne selbst Vision-LLM auszuführen.

## Screening-Modi
| Modus | Wann |
|-------|------|
| Deterministic (profile.yaml) | Land, Alter, Stadt, einfache Radio-Buttons |
| Worker Mode (Vision-LLM) | Offene Textfragen, komplexe Matrizen, Audio/Video |
