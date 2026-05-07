# STATE OF THE ART — Aktueller Zustand Stealth-Runner & Stealth Suite

> **Stand**: 2026-05-08 01:30 UTC
> **Reporter**: SIN-Agent Automated Analysis
> **Scope**: stealth-runner + 23 Suite-Repos + ~/.stealth Session-Daten + OpenCode DB


---

## 0. UPDATE: SOLL-IST-ANALYSE (2026-05-08 01:30)

**Massive Dokumentation + Best Practices + Issues erstellt.**

| Kategorie | Dateien | Zeilen | Status |
|-----------|---------|--------|--------|
| **Best Practices Plan** | docs/best-practices/PLAN.md | 995 | ✅ Erweitert um §§11-15 |
| **State Management** | docs/best-practices/STATE-MANAGEMENT.md | 463 | ✅ NEU — explizite States, Transitions, Recovery |
| **Verify-Box Pattern** | docs/best-practices/VERIFY-BOX.md | 367 | ✅ NEU — Verify-Pattern für ALLE Aktionen |
| **Test Patterns** | docs/best-practices/TEST-PATTERNS.md | 393 | ✅ NEU — Test-Pyramid, Mocking, Naming |
| **Issue #5** | issues/005-code-completeness-verification.md | 120 | ✅ NEU — Automatische Code-Vollständigkeit |
| **Issue #6** | issues/006-nim-runtime-failures.md | 180 | ✅ NEU — NIM Fallback-Strategie |
| **survey.py Kommentare** | survey-cli/survey.py | 1388 (+62) | ✅ EXTREM — alle CLI-Args dokumentiert |
| **survey_agent.py Kommentare** | src/stealth_survey/survey_agent.py | 1105 (+213) | ✅ EXTREM — BatchExecutor, _simple_actions, _detect_completion, _rate_survey |
| **auto_google_login.py** | cli/modules/auto_google_login.py | 1651 | ✅ Bereits extrem dokumentiert |
| **TOTAL** | | **6662 Zeilen** | ✅ Alle Dateien kompilieren |

| Metrik | Wert | Status |
|--------|------|--------|
| **Surveys Completed (letzte Session)** | 0 | 🔴 KRITISCH |
| **Daemon Zustand** | `running: false` (seit 07. Mai 06:53) | 🔴 KRITISCH |
| **Login-Failure Rate** | ~100% (letzte 20 Intents identisch) | 🔴 KRITISCH |
| **Learn.md Failed-Einträge** | ~117.925 Zeilen (fast ausschließlich `failed ❌`) | 🔴 KRITISCH |
| **IndentationError** | Behoben in `a8ceca7` (survey.py:199) | 🟡 BEHOBEN |
| **Unit Tests** | 211 Tests in 15 Modulen | 🟢 OK |
| **Uncommitted Docs** | ~35 Dateien in skylight-cli, cua-touch, macos-ax-cli | 🟡 WARNUNG |
| **Session-Dateien** | 2965 Sessions (jeweils 2 Bytes → leer/placeholder) | 🟡 WARNUNG |

---

## 2. ROOT CAUSE ANALYSIS — Warum 0 Surveys?

### 2.1 Login-Loop Failure (KRITISCH)

**Symptom** (aus `~/.stealth/intents.jsonl`, letzte 20 Einträge):
```json
{"goal": "NEUE TAB! Aber NICHT eingeloggt! Login first:", "verdict": "failed", "success": false}
```

**Ursache**: Der `cmd_watch()` Loop in `survey-cli/survey.py` versucht:
1. Dashboard zu finden → `find_dashboard_ws(args.port)`
2. Login-State zu prüfen → `document.title.includes('Umfragen') || document.body.innerText.includes('Abmelden')`
3. Wenn nicht eingeloggt → `google_login()` aufrufen

**Problem**: `google_login()` schlägt fehl oder wird endlos wiederholt:
- Chrome startet, aber Accessibility nicht aktiv
- cua-driver Daemon nicht laufend
- Google OAuth Popup nicht erkannt
- Keychain Auto-Fill funktioniert nicht
- Dashboard-Tab wird nicht korrekt identifiziert

**Impact**: Endlosschleife → Keine Surveys werden jemals gescannt oder ausgeführt.

### 2.2 Daemon Not Running

`~/.stealth/daemon_state.json`:
```json
{"running": false, "stopped_at": "2026-05-07T06:53:14.807058", "surveys_completed": 0}
```

**Folgen**:
- cua-driver Daemon nicht aktiv → kein Session-Cache
- Keine Chrome-Interaktionen möglich
- Watch-Loop bricht ab oder wiederholt Fehler

### 2.3 Empty Session Files

2.965 Session-Dateien in `~/.local/share/opencode/sessions/` — **jeweils nur 2 Bytes**.

**Hypothese**: Sessions werden erstellt aber nie beschrieben, oder Cleanup-Mechanismus ist zu aggressiv.

---

## 3. CODE-QUALITÄTS-ANALYSE

### 3.1 IndentationError (BEHOBEN in a8ceca7)

**Datei**: `survey-cli/survey.py:199`
**Problem**: 6 Zeilen eingerückt mit 8 Spaces statt 4 nach einem `import` Statement.
**Fix**: Dedent von 8 auf 4 Spaces.
**Risk**: SyntaxError würde das gesamte `survey.py` Script blockieren.

### 3.2 Uncommitted Documentation Files

**Betroffene Repos**:
| Repo | Uncommitted Files |
|------|------------------|
| skylight-cli | ~35 Dateien (sinrules.md, brain.md, fix.md, learn.md, etc.) |
| cua-touch | ~35 Dateien |
| macos-ax-cli | ~35 Dateien |

**Ursache**: Auto-generierte Dokumentation bei `graphify` oder anderen Tools.
**Risk**: Verwirrung für zukünftige Agents (welche Version ist aktuell?).

---

## 4. REPO-STATUS ÜBERSICHT (Stealth Suite)

| Repo | Letzter Commit | Status | Uncommitted |
|------|---------------|--------|-------------|
| **stealth-runner** | a8ceca7 (Indentation Fix) | 🔴 Login-Failure | survey.py |
| **stealth-core** | 01b76ef (gitnexus) | 🟢 OK | .claude/ |
| **stealth-session** | 2ca4063 (gitnexus) | 🟢 OK | .claude/ |
| **stealth-guardian** | d9f8ef7 (gitnexus) | 🟢 OK | .claude/ |
| **stealth-memory** | f20b29f (gitnexus) | 🟢 OK | .claude/ |
| **stealth-captcha** | 23367b4 (gitnexus) | 🟢 OK | .claude/ |
| **stealth-skills** | 49736d9 (gitnexus) | 🟡 OK | AGENTS.md, .claude/ |
| **playstealth-cli** | 5605e96 (graphify) | 🟢 OK | Keine |
| **skylight-cli** | d7770ae (Update) | 🟡 Warnung | ~35 docs |
| **cua-touch** | 83927bc (Update) | 🟡 Warnung | ~35 docs |
| **macos-ax-cli** | 8bb9215 (Suite table) | 🟡 Warnung | ~35 docs |

---

## 5. API KEYS & CONFIGURATION

`~/.local/share/opencode/auth.json`:
- **mistral**: ✅ aktiv
- **groq**: ✅ aktiv
- **vercel**: ✅ aktiv
- **fireworks-ai**: ✅ aktiv

`~/.stealth/config.yaml`:
- **NVIDIA NIM**: Konfiguriert aber `NVIDIA_API_KEY` Umgebungsvariable nicht gesetzt?
- **Swarm**: Aktiviert (max 8 Workers, Byzantine consensus)
- **Graphify**: Aktiviert (auto-update nach LORA training)
- **Codeburn**: Budget $10, aktiviert

---

## 6. KNOWLEDGE GRAPH STATUS

`stealth-runner/graphify-out/`:
- `graph.json`: **5.1 MB** (aktuell bis 07. Mai 21:11)
- `graph.html`: **3.9 MB**
- `GRAPH_REPORT.md`: **199 KB**

**Letzter Rebuild**: `a8ceca7` (Indentation Fix) → graph.json wurde mit aktualisiert.

---

## 7. EMPFEHLUNGEN (Priorisiert)

### 🔴 P0 — Sofort
1. **Login-Failure beheben**: Root-Cause in `auto_google_login.py` oder `cmd_watch()` finden
2. **cua-driver Daemon starten**: `nohup cua-driver serve > /tmp/cua-daemon.log 2>&1 &`
3. **Chrome mit korrekten Flags starten**: `--force-renderer-accessibility --remote-allow-origins="*"`

### 🟡 P1 — Heute
4. **Session-Dateien analysieren**: Warum sind alle 2 Bytes?
5. **Uncommitted docs committen oder .gitignore updaten**: skylight-cli, cua-touch, macos-ax-cli
6. **NVIDIA_API_KEY prüfen**: Ist die Umgebungsvariable gesetzt?

### 🟢 P2 — Diese Woche
7. **Test-Suite erweitern**: Login-Flow als Integrationstest
8. **Health-Check Tool**: `./survey.py doctor` vollständig implementieren
9. **Monitoring**: Alert wenn `daemon_state.json` → `running: false`

---

## 8. ANHANG

### 8.1 Datei-Größen ~/.stealth/

```
brain.md        : 22.633  Zeilen
learn.md        : 117.925 Zeilen
intents.jsonl   : 33.805  Zeilen
sync_events.jsonl: 8.203  Zeilen
config.yaml     : ~4.5    KB
audit_chain.json: 2       Einträge (Genesis + 1 failed)
```

### 8.2 Commit-History stealth-runner (letzte 20)

```
a8ceca7 fix: IndentationError in survey.py line 199
eb5cbb0 feat(opencode): add custom commands + tools
59f887a test: add unit tests for all 15 tools/modules (211 tests)
1610719 Fix all AGENTS.md files: remove emojis, fix YAML parsing errors
c654be4 Fix AGENTS.md YAML parse errors
a1b4834 docs: mass documentation — 75 files
6085865 docs: document 6 critical core modules
b0cac3b docs: document NEMO runner.py + scanner.py
ed5bb3a docs: extensive module docstrings for 8 core modules
5ed71a7 docs+fix: archaeology-tsunami — complete codebase documentation
...
```

### 8.3 Opencode DB Schema

```sql
__drizzle_migrations
project, message, part, permission, session, todo
session_share, control_account, account, account_state
event_sequence, event, workspace, session_message
```

---

*Dieses Dokument wurde automatisch generiert am 2026-05-08 00:20 UTC.*
*Nächste Aktualisierung: Nach jedem erfolgreichen Survey-Run.*
