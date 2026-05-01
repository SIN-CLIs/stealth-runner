# goal.md - Stealth Runner Hauptziel

## Primärziel
Heypiggy.com automatisieren: Google-Login → Surveys abschließen → EUR > 0 verdienen

## Meilensteine (erreicht)
| Datum | Meilenstein |
|-------|-------------|
| 2026-05-01 | ✅ **Google Login erfolgreich!** (5 Schritte: Klick → Email → Weiter → Passwort → Weiter) |
| 2026-05-01 | ✅ Omni reasoning-Feld fix (content=null bug) |
| 2026-05-01 | ✅ Nemotron Omni Integration (Model fix, SSE, Rolling Video) |
| 2026-05-01 | ✅ Graphify Knowledge Graph (6 Repos → 4820 Nodes) |
| 2026-05-01 | ✅ Semgrep Architecture Guard (11 Regeln, Pre-Commit) |
| 2026-05-01 | ✅ Live Omni Monitor (Rolling Video Buffer + SSE) |
| 2026-05-01 | ✅ screen-follow record --video (Daueraufnahme für Omni) |
| 2026-05-01 | ✅ playstealth launch (isolierte Chrome-Instanz) |
| 2026-05-01 | ✅ CLI heypiggy-login (nur skylight-cli, kein osascript) |

## Aktueller Status
- ✅ Google Login: Funktionierender Flow (playstealth → Google → Email → Passwort → Dashboard)
- ✅ Omni Vision: HTTP 200, SSE Streaming, reasoning-Parsing
- ✅ Rolling Video Buffer: screen-follow + ffmpeg + Omni Conv3D
- ⏳ Survey-Loop starten (Omni-gesteuert via LiveOmniMonitor)
- ⏳ EUR-Guthaben prüfen nach Survey

## Constraints (UNVERBRÜCHLICH – semgrep blockiert Verstöße)
1. Nur skylight-cli, NIE skylight-cli
2. Nur `--element-index`, NIE `--x`/`--y`
3. Nur `playstealth launch`, NIE `open -na Chrome` oder `pgrep`
4. Nur httpx an NVIDIA NIM, NIE openai-Client
5. JEDER Schritt durch Vision (kein DOM-Prescan)
6. Screenshots VOR/NACH jedem Schritt (SOTA-Konform)
7. Kein Recovery-Mode (Omni macht ALLE Entscheidungen)
8. **Videoaufzeichnung bei jedem Build/Debug** (`screen-follow record --video`)

## Nächste Schritte
1. Survey-Loop starten (Omni-gesteuert via LiveOmniMonitor)
2. EUR-Guthaben prüfen nach Survey
3. Täglicher EUR-Canary (cron-Job)
