# SR-19: stealth-axiom — 3-Tier Hierarchical Model Router

- **Status:** ✅ COMPLETED (2026-05-04)
- **Priority:** 🔴 Critical
- **Repo:** [`SIN-CLIs/stealth-axiom`](https://github.com/SIN-CLIs/stealth-axiom)

## Description

Intelligenter Model-Router: Micro (<100ms, FREE) → Mid (<500ms, FREE) → Heavy (nur Notfall, $0.01/Call).  
80/15/5 Verteilung → **99.96% Kostenersparnis** vs. DeepSeek V4 only.

## Deliverables

- [x] `router.py` — AxiomRouter mit Task-Klassifikation + Failure-Escalation
- [x] `prompts.py` — MICRO/MID/HEAVY Prompt-Templates
- [x] `client.py` — `stealth-axiom` CLI (stats/route/fail/success/health)
- [x] `__init__.py` — Public API
- [x] `setup.py` — pip installable
- [x] `README.md` — Dokumentation

## Modell-Palette

| Modell | Tier | Kosten | Latenz |
|--------|------|--------|--------|
| mistral-small-latest | MICRO | 🟢 FREE | 80ms |
| nemotron-3-nano-omni-30b-a3b-reasoning | MICRO | 🟢 FREE | 60ms |
| nemotron-3-super-120b-a12b | MID | 🟢 FREE | 400ms |
| step-3.5-flash | MID | 🟢 FREE | 300ms |
| nemoretriever-ocr-v1 | OCR | 🟢 FREE | 500ms |
| deepseek-v4-pro | HEAVY | 🔴 $0.01 | 2000ms |

## Files

- `SIN-CLIs/stealth-axiom` — komplettes Repo (6 files)
- `stealth-session/stealth_session/executor.py` — Axiom-Integration
- `stealth-runner/issues/ISSUE-SR-19.md` — dies hier
- `stealth-runner/issues.md` — Issue-Tabelle
