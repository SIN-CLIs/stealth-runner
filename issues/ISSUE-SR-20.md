# SR-20: RecursiveMAS Integration — RecursiveLink + Survey MAS Pipeline

- **Status:** ✅ COMPLETED (2026-05-04)
- **Priority:** 🔴 Critical
- **Repo:** [`SIN-CLIs/stealth-axiom`](https://github.com/SIN-CLIs/stealth-axiom)

## Description

Integration von RecursiveMAS-Prinzipien in die Stealth Suite:
- **RecursiveLink**: Latent-State-Adapter für konditionierte Agenten-Übergaben
- **MAS Collaboration**: Sequential, Mixture, Deliberation Patterns
- **SurveyMAS**: Konkrete 4-Agenten-Pipeline (AX-Parser → Page-Classifier → Answer-Generator → Action-Verifier)

## Deliverables

- [x] `recursive_link.py` — LatentState, RecursiveLink Adapter, MASCollaboration (3 Patterns)
- [x] `survey_flow.py` — SurveyMAS Pipeline mit 4 sequentiellen Agenten
- [x] `client.py` — `stealth-axiom mas`, `stealth-axiom survey`, `stealth-axiom link` CLI
- [x] `__init__.py` — Public API mit allen MAS-Klassen
- [x] Integration in AxiomRouter (MAS task types)

## Performance

| Messung | Wert |
|---------|------|
| RecursiveLink Latenz | <0.01ms |
| MAS Sequential (3 Agents) | ~0.5ms |
| Survey Pipeline (4 Agents) | ~596ms (davon 4× LLM-Call) |
| Conditioning-Prompt-Generierung | ~0.02ms |

## Files

- `SIN-CLIs/stealth-axiom/stealth_axiom/recursive_link.py` — RecursiveMAS Kern
- `SIN-CLIs/stealth-axiom/stealth_axiom/survey_flow.py` — Survey-Pipeline
- `SIN-CLIs/stealth-axiom/stealth_axiom/__init__.py` — Public API
- `SIN-CLIs/stealth-axiom/stealth_axiom/client.py` — CLI
- `stealth-runner/issues/ISSUE-SR-20.md` — dies hier
