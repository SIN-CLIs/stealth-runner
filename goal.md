# goal.md - Stealth Runner Hauptziel

## Primärziel
Heypiggy.com automatisieren: Google-Login → Surveys abschließen → EUR > 0 verdienen

## Live-Trio-Architektur (erreicht)
- ✅ **EYES**: cua-driver list_windows (250ms Polling, Popup-Erkennung)
- ✅ **BRAIN**: cua-driver get_window_state --window-id (NUR Popup-Elemente)
- ✅ **HANDS**: cua-driver click --pid --window-id --element-index (Garantiert richtiges Fenster)
- ✅ **Popup-Bug gefixt**: skylight-cli klickte "Weiter" auf Heypiggy-Seite statt im Google Popup

## Meilensteine (erreicht)
| Datum | Meilenstein |
|-------|-------------|
| 2026-05-01 | ✅ **TRIO LAYER v2** – cua-driver mit window-id + element-index |
| 2026-05-01 | ✅ **Popup-Bug verstanden + gefixt** – Fenster-Isolation |
| 2026-05-01 | ✅ **Google Login erfolgreich** (5 Schritte) |
| 2026-05-01 | ✅ Nemotron Omni Integration (Model fix, SSE, reasoning) |
| 2026-05-01 | ✅ Graphify Knowledge Graph (6 Repos → 4820 Nodes) |
| 2026-05-01 | ✅ Semgrep Architecture Guard (11 Regeln) |
| 2026-05-01 | ✅ Doctor CLI v6 (28 Tools, 143 Repos) |

## Nächste Schritte
1. Trio Layer Live-Test: Google Login komplett mit Popup-Schutz
2. Survey-Loop mit Trio Layer + window-id
3. EUR-Guthaben prüfen nach Survey
4. Täglicher EUR-Canary (cron-Job)
