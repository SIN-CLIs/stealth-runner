# issues.md - Aktuelle Issues (2026-05-01)

## 2026-05-02: Doctor Scan

**Gefixt:** 86 veraltete Muster/Kredentials

**Fehlende Docs (2):**

- [ ] `ROADMAP.md`
- [ ] `Dockerfile`

**Offene Findings:** 86

## P0 (Blocker)

1. **Google Login abschließen**: Passwort-Seite nach Weiter erreichen
   - playstealth launch → Google Login → E-Mail → Weiter → **Passwort**
   - cli/heypiggy-login bereit, muss getestet werden
   - PID über playstealth launch (nie pgrep!)

2. **NVIDIA API Key Doku**
   - Key Prefix: `nvapi-...`
   - Endpoint: `https://integrate.api.nvidia.com/v1/chat/completions`
   - Model: `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`
   - Nicht verwechseln mit `nvidia/nvidia/...` (gibt 404!)

## P1 (Wichtig)

3. **Survey-Loop nach Login**
   - LiveOmniMonitor bereit (Rolling Video + SSE)
   - Muss getestet werden: capture → Omni → execute → loop

4. **EUR-Guthaben prüfen**
   - Nach Survey-Teilnahme EUR-Stand auslesen
   - unmask-cli oder skylight-cli für Texterkennung

5. **Graphify merged graph regenerieren**
   - Nach Code-Änderungen `graphify update .` in jedem Repo
   - Dann `graphify merge-graphs` für alle 6 Repos

## P2 (Später)

6. **Täglicher EUR-Canary**
   - Cron-Job via launchd
   - Automatischer Login → Survey → EUR-Check
   - Bei 3 konsekutiven Erfolgen: KR1 erreicht

7. **Mehrere Survey-Profile parallel**
   - Unterschiedliche Profile für verschiedene Plattformen
   - Profile in `profiles/` ablegen

8. **Proxy-Rotation**
   - Für IP-Verschleierung
   - playstealth launch mit Proxy-Support
