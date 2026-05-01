# goal.md - Stealth Runner Hauptziel

## Primärziel
Heypiggy.com automatisieren: Google-Login → Surveys abschließen → EUR > 0 verdienen

## Meilensteine (erreicht)
| Datum | Meilenstein |
|-------|-------------|
| 2026-05-01 | ✅ Nemotron Omni Integration (Model fix, SSE, Rolling Video) |
| 2026-05-01 | ✅ Graphify Knowledge Graph (6 Repos → 4820 Nodes) |
| 2026-05-01 | ✅ Semgrep Architecture Guard (11 Regeln, Pre-Commit) |
| 2026-05-01 | ✅ Live Omni Monitor (Rolling Video Buffer + SSE) |
| 2026-05-01 | ✅ playstealth launch (isolierte Chrome-Instanz) |
| 2026-05-01 | ✅ CLI heypiggy-login (nur skylight-cli, kein osascript) |

## Aktueller Status
- ✅ playstealth launch funktioniert (isoliertes Chrome, eigene PID)
- ✅ skylight-cli mit element-index funktioniert
- ✅ Google-Login Popup öffnet korrekt
- ✅ Nemotron Omni API: HTTP 200, SSE Streaming
- ✅ Rolling Video Buffer: temporal analysis
- ⏳ Google-Login abschließen (Passwort-Seite)
- ⏳ Survey-Loop starten (Omni-gesteuert)

## Constraints (UNVERBRÜCHLICH – semgrep blockiert Verstöße)
1. Nur skylight-cli, NIE webauto-nodriver
2. Nur `--element-index`, NIE `--x`/`--y`
3. Nur `playstealth launch`, NIE `open -na Chrome` oder `pgrep`
4. Nur httpx an NVIDIA NIM, NIE openai-Client
5. JEDER Schritt durch Vision (kein DOM-Prescan)
6. Screenshots VOR/NACH jedem Schritt (SOTA-Konform)
7. Kein Recovery-Mode (Omni macht ALLE Entscheidungen)
8. Alle Fehler dokumentieren in BANNED.md

## Nächste Schritte
1. Google Login Popup: Passwort eingeben + Weiter klicken
2. Survey-Loop starten (Omni-gesteuert via LiveOmniMonitor)
3. EUR-Guthaben prüfen nach Survey
4. Täglicher EUR-Canary (cron-Job)
