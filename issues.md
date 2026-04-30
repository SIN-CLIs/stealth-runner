# issues.md — stealth-runner (alle Repos der Stealth-Triade)

> Legend: ✅ Done | 🔴 Open | 🟡 Blocked | ⚫ Closed (obsolete)

---

## 🔴 Open Issues (stealth-runner)

| # | Title | Origin | Status | Assigned |
|---|-------|--------|--------|----------|
| [#1](https://github.com/OpenSIN-AI/stealth-runner/issues/1) | **Epic: Stealth Triad Greenfield Build** | A2A-Worker #167 | 🔴 Tracking | — |
| [#4](https://github.com/OpenSIN-AI/stealth-runner/issues/4) | Update CLI help text for `--dry-run` / `--one-shot` | A2A-Worker #164 | 🔴 Open | → `skylight-cli` |
| [#5](https://github.com/OpenSIN-AI/stealth-runner/issues/5) | SoM references in Vision prompts | A2A-Worker #160 | 🔴 Open | `vision_client.py` |
| [#8](https://github.com/OpenSIN-AI/stealth-runner/issues/8) | Error recovery for survey failures | A2A-Worker #148 | 🔴 Open | `state_machine.py` |

---

## 📋 Backlog (Roadmap — nicht als Issues angelegt)

| Prio | Feature | Abhängigkeit |
|------|---------|-------------|
| P0 | Human-Profile aktivieren (Jitter, Bézier, Hover-Delay, Typing-Rhythmus) | `human_profile.py` existiert → an `stealth_executor` anbinden |
| P0 | OCR-Fallback für Canvas-Elemente (Apple Vision `VNRecognizeTextRequest`) | `skylight-cli` muss OCR-Mode bereitstellen |
| P1 | `track`-Kommando Live-Test gegen Cloudflare Turnstile | `skylight-cli track` existiert, braucht Kalibrierung |
| P1 | Netzwerk-TLS-Profiling in `playstealth-cli` (JA4-Fingerprint) | `playstealth-cli` Repo |
| P2 | Parallelisierung mehrerer Survey-Instanzen (Multi-PID) | `state_machine.py` Refaktor |
| P2 | CI/CD: Automatisierter Regressionstest nach jedem macOS-Update | GitHub Actions |

---

## ✅ Resolved (in stealth-runner implementiert)

| # | Was | Commit |
|---|-----|--------|
| 1 | `cua-driver`-Referenzen entfernt — nur `skylight-cli` | `efd363f` |
| 2 | `open -na "Google Chrome"` ersetzt durch `playstealth-cli launch` | `efd363f` |
| 3 | AXStaticText-Klick im Prompt verboten — nur interaktive Rollen | `efd363f` |
| 4 | VisionClient.get_action() VOR jedem execute — kein blindes Raten | `efd363f` |
| 5 | `unmask-cli verify-stealth` in VERIFY-State integriert | `77581cf` |
| 6 | `ask_vision()`-Hänger gefixt — `ask_vision_text()` intern | `0b72d2e` |
| 7 | Lesezeichen-Klicks validiert — Chrome-UI-Klicks verhindert | `987e862` |
| 8 | AX-Tree-Kollaps bei verdeckten Fenstern: `_AXObserverAddNotificationAndCheckRemote` | `2ea1ee6` |
| 9 | Canvas-UI-Fallback: `VNRecognizeTextRequest` (OCR) | `f7b1f31` |
| 10 | `sin_survey_core` aus Alt-Worker extrahiert (8 Panel-Provider) | `fa79aa8` |
| 11 | `SYSTEM_PROMPT` vollständig (1742 chars, 10 Aktionen, Few-Shot) | `9691efb` |
| 12 | 10-State Machine: IDLE→LAUNCH→WAIT→CAPTURE→VISION→EXECUTE→VERIFY→DONE↘RECOVERY | `efd363f` |
| 13 | `.env`-Leak behoben → `.env.example` | `78c4672` |
| 14 | 8 md-Dokumentationsdateien (brain, banned, architecture, goal, fix, issues, AGENTS, CONTRIBUTING) | `78c4672` |
| 15 | 18/18 Tests PASS (12 sin_survey_core + 6 runner) | `f6f0531` |

---

## ⚫ Issues aus A2A-SIN-Worker-heypiggy (geschlossen)

| Worker # | Titel | Grund |
|----------|-------|-------|
| #167 | Stealth-Triade Integration | → Epic #1 |
| #166 | CLI flags usage examples | ✅ in AGENTS.md |
| #165 | CLI flags section | ✅ in AGENTS.md |
| #164 | Update CLI help text | → #4 offen |
| #163 | PID logging to audit trail | ✅ in AuditLog |
| #162 | Test find_bot_window() | ⚫ obsolete (kein CDP) |
| #161 | PID validation checks | ✅ in StealthExecutor |
| #160 | SoM references in Vision prompts | → #5 offen |
| #159 | SoM overlay rendering | ✅ in skylight-cli |
| #158 | OCR grid generation | ✅ in skylight-cli |
| #157 | Document merge workflow | ✅ in CONTRIBUTING.md |
| #156 | Pre-merge test check | ⚫ obsolete |
| #155 | PR template | ⚫ obsolete |
| #154 | Session cache documentation | ⚫ obsolete |
| #153 | Panel override logic | ✅ in detectors.py |
| #152 | cua-driver integration docs | ⚫ obsolete (cua-driver entfernt) |
| #151 | EUR deduplication | ✅ in extractor.py |
| #150 | Test extract_earnings() | ✅ Teil der 12 Tests |
| #149 | Test extract_earnings() banners | ✅ Teil der 12 Tests |
| #148 | Error recovery | → #8 offen |
| #147 | Form fill via cua-driver | ⚫ obsolete (→ skylight-cli type) |
| #146 | Page state transition | ✅ in StateMachine |
| #145 | 72h TTL sessions | ⚫ obsolete |
| #144 | Cookie replay | ✅ in playstealth-cli |
| #143 | Cookie serialization | ✅ in playstealth-cli |
| #142 | Browser rotation for bots | ✅ RECOVERY-State |
| #141 | Stealth verification after launch | ✅ VERIFY-State |
| #140 | interactor.py CDP → CLI | ⚫ obsolete (interactor entfernt) |
| #139 | vision_gate.py CDP screenshots | ⚫ obsolete (→ skylight-cli) |
| #138 | bridge.py remove CDP | ⚫ obsolete (bridge entfernt) |
| #137 | CLI docs parent | ⚫ obsolete |
| #136 | PID management parent | ⚫ obsolete |
| #135 | SoM parent | ⚫ obsolete |
| #134 | media_router unmask awareness | ⚫ obsolete |
| #133 | panel_detector stealth verification | ⚫ obsolete |
| #132 | interactor replace all CDP | ⚫ obsolete |
| #131 | bridge deprecate entirely | ⚫ obsolete |
| #130 | vision_gate use playstealth-cli | ⚫ obsolete |
| #129 | Bridge removal parent | ⚫ obsolete |
| #128 | Stealth verification loop parent | ⚫ obsolete |
| #127 | Continuous stealth verification | ✅ in VERIFY-State |

**Gesamt:** 29 Issues aus dem alten Worker geschlossen. 2 (#164, #160) als offene Issues #4/#5 migriert. 1 (#148) als offenes Issue #8 migriert. 1 (#167) als Epic #1 migriert.

---

## 🔗 Cross-Repo Dependencies (Issues in anderen SIN-CLIs Repos)

| Repo | Was fehlt | Issue |
|------|-----------|-------|
| `skylight-cli` | `--help`-Texte standardisieren (→ #4) | [anzulegen] |
| `skylight-cli` | OCR-Mode `--mode ocr` für Canvas-Fallback | [anzulegen] |
| `skylight-cli` | `track` gegen Live-Captchas kalibrieren | [anzulegen] |
| `playstealth-cli` | JA4 TLS-Fingerprint-Profiling | [anzulegen] |
| `unmask-cli` | Netzwerk-Timing-Analyse (zusätzlich zu Browser-Checks) | [anzulegen] |

---

## 📊 Quick Stats

```
Offen:           4  (stealth-runner)
Backlog:         6  (geplant)
Resolved:       15  (implementiert)
Alt-Worker:     29  (geschlossen)
Cross-Repo:      5  (abhängig)
────────────────────
Gesamt:         59
```

---

**Letztes Update:** 2026-04-30 · Smoke Test ALL GREEN · 18/18 Tests PASS
