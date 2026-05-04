# PLANS-OVERVIEW — Alle offenen Arbeitspakete + Stealth Suite Status (2026-05-04 10:30:00 CET)

> **Master-Index** aller Pläne für stealth-runner.
> Jeder Plan hat eine korrespondierende Issue-Datei in `issues/`.

---

## 🔍 Stealth Suite — Vollständiger Repo Status (Recherchiert 2026-05-04)

Die gesamte Stealth Suite umfasst 12 Komponenten (10 existieren, 1 fehlt, 1 muss gepusht werden).

| Repo | Sprache | Status | GitHub | Lokal | Rolle im Stack |
|------|---------|--------|--------|-------|----------------|
| **stealth-runner** | Python | 🟢 Aktiv | ✅ SIN-CLIs | ✅ | Orchestrator (Login → Survey → EUR) |
| **cua-touch** | Python | 🟢 Aktiv | ✅ SIN-CLIs | ✅ | Python Client für AX-Popups |
| *(cua-driver Binary)* | Swift | ⚠️ Source verloren | ❌ Kein GitHub | ✅ Binary im .app | Swift Binary, Source nirgends gesichert |
| **skylight-cli** | Swift | 🟢 Aktiv | ✅ SIN-CLIs | ✅ | AXPress Klicks (Hauptfenster) |
| **playstealth-cli** | Python | 🟢 Aktiv | ✅ SIN-CLIs | ✅ | Isolierter Chrome-Launcher |
| **screen-follow** | Swift | 🟢 Aktiv | ✅ SIN-CLIs | ✅ | Screen Recording |
| **unmask-cli** | TypeScript | 🟢 Aktiv | ✅ SIN-CLIs | ✅ | DOM/Network/Console X-Ray |
| **stealth-skills** | TS/Python | 🔵 Privat | ✅ SIN-CLIs | ✅ | Plattform-spezifische Skills |
| **stealth-captcha** | Python | 🟢 Aktiv | ✅ SIN-CLIs | ✅ | Captcha-Solver (20 Typen) |
| **A2A-SIN-Worker-heypiggy** | Python | 🔴 Legacy | ✅ OpenSIN-AI | ✅ | Alter Worker (deprecated) |
| **computer-use-mcp** | TypeScript | 🔴 Legacy | ✅ SIN-CLIs | ✅ | Alter MCP Server (deprecated) |
| **macos-ax-cli** | Swift | 🔴 Nie gepusht | Remote gesetzt, Repo ⚠️ | ✅ `~/dev/macos-ax-cli/` | Systemweiter AX-Scan |
| **ax-graph** | Swift | 🟢 **AKTIV** | ✅ SIN-CLIs/ax-graph | ✅ `~/dev/ax-graph/` | Unified AX Indexer (Erstellt: 2026-05-04) |

### Datenfluss (aktuell)

```
playstealth-cli → Chrome PID → skylight-cli (Hauptfenster)
                              → cua-touch/cua-driver (Popups)
                              → unmask-cli (DOM/NET)
                              → screen-follow (Video)
                              → stealth-runner (Orchestrierung + Omni Vision)
```

### Lücken im Stack
1. ✅ **macos-ax-cli** → GEPUSHT (2026-05-04)
2. ⚠️ **cua-driver Swift Source** → Binary existiert, Source ist nirgends auf der Platte → **für immer verloren**
3. ✅ **ax-graph** → **ERSTELLT** unter `SIN-CLIs/ax-graph` (2026-05-04)
4. **A2A-SIN-Worker-heypiggy** + **computer-use-mcp** → Legacy, archivieren
5. ✅ **stealth-runner** liegt jetzt unter SIN-CLIs

---

## Prioritätsschlüssel

| Symbol | Bedeutung |
|--------|-----------|
| 🔴 | **Kritisch** — Blockiert Produktion |
| 🟡 | **Hoch** — Nächste Schritte |
| 🟢 | **Mittel** — Optimierung |
| 🔵 | **Niedrig** — Nice-to-Have |

---

## 🔴 KRITISCHE ARBEITSPAKETE

| # | Plan | Issue | Beschreibung | Aufwand |
|---|------|-------|-------------|---------|
| 1 | [plan-ax-graph.md](plan-ax-graph.md) | [ISSUE-SR-11](../issues/ISSUE-SR-11.md) | **ax-graph Swift CLI** — Unified AX Indexer (alle Apps + Fenster + Chrome DOM) | **Groß (neues Repo)** |
| 2 | [plan-survey-runner-complete.md](plan-survey-runner-complete.md) | [ISSUE-SR-14](../issues/ISSUE-SR-14.md) | **Survey Runner fertigstellen** — Multi-Survey, Balance-Prüfung, Captcha-Auto-Solve | **Groß** |
| 3 | [plan-daemon-production.md](plan-daemon-production.md) | [ISSUE-SR-17](../issues/ISSUE-SR-17.md) | **24/7 Daemon Production** — Cron-Job, Monitoring, Error-Recovery | **Mittel** |

## 🟡 HOHE ARBEITSPAKETE

| # | Plan | Issue | Beschreibung | Aufwand |
|---|------|-------|-------------|---------|
| 4 | [plan-skylight-dom-patch.md](plan-skylight-dom-patch.md) | [ISSUE-SR-12](../issues/ISSUE-SR-12.md) | **skylight-cli DOM Patch** — AXDOMIdentifier/AXDOMClassList lesen | **Klein** |
| 5 | [plan-atomacos-python-ax.md](plan-atomacos-python-ax.md) | [ISSUE-SR-13](../issues/ISSUE-SR-13.md) | **Python AX Integration** — atomacos/pyobjc für Orchestrator | **Klein** |
| 6 | [plan-audio-capture.md](plan-audio-capture.md) | [ISSUE-SR-15](../issues/ISSUE-SR-15.md) | **Audio-Capture Integration** — BlackHole + Omni in survey_runner | **Klein** |
| 7 | [plan-captcha-integration.md](plan-captcha-integration.md) | [ISSUE-SR-16](../issues/ISSUE-SR-16.md) | **Captcha Auto-Solve** — Captcha-Erkennung + Lösung automatisch | **Mittel** |

## 🔵 NIEDRIGE ARBEITSPAKETE

| # | Plan | Issue | Beschreibung | Aufwand |
|---|------|-------|-------------|---------|
| 8 | plan-web-ui.md | *(optional)* | Web-UI / Electron-App | **Groß** |
| 9 | plan-telegram-bot.md | *(optional)* | Telegram-Bot für Status | **Klein** |
| 10 | plan-docker.md | *(optional)* | Docker-Container | **Klein** |

---

## Abhängigkeiten (DAG)

```
ax-graph ──→ skylight-dom-patch (braucht ax-graph node_id Format)
       │
       └──→ atomacos-python-ax (kann parallel)
       
survey-runner-complete ──→ audio-capture (muss integriert sein)
       │
       ├──→ captcha-integration
       │
       └──→ daemon-production (braucht fertigen Survey Runner)
```

---

## Verwandte Dateien

| Datei | Zweck |
|-------|-------|
| `AGENTS.md` | Agenten-Anleitung (wird aktualisiert) |
| `brain.md` | Systemwissen (wird aktualisiert) |
| `issues.md` | Master Issue-Liste (wird aktualisiert) |
| `plan.md` | Aktueller Stand (Referenz) |
| `cli/modules/survey_runner.py` | Survey Automation (wird erweitert) |
| `cli/modules/audio_capture.py` | Audio Capture (vorhanden) |
| `cli/modules/audio_box.py` | Audio Analyse (vorhanden) |
| `cli/modules/captcha_crashtest.py` | Captcha Crash-Tests (vorhanden) |
