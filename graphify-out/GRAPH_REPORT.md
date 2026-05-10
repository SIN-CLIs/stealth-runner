# Graph Report - stealth-runner  (2026-05-10)

## Corpus Check
- 182 files · ~2,755,362 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 4127 nodes · 10240 edges · 108 communities detected
- Extraction: 46% EXTRACTED · 54% INFERRED · 0% AMBIGUOUS · INFERRED: 5481 edges (avg confidence: 0.57)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]
- [[_COMMUNITY_Community 45|Community 45]]
- [[_COMMUNITY_Community 46|Community 46]]
- [[_COMMUNITY_Community 47|Community 47]]
- [[_COMMUNITY_Community 48|Community 48]]
- [[_COMMUNITY_Community 49|Community 49]]
- [[_COMMUNITY_Community 50|Community 50]]
- [[_COMMUNITY_Community 51|Community 51]]
- [[_COMMUNITY_Community 52|Community 52]]
- [[_COMMUNITY_Community 53|Community 53]]
- [[_COMMUNITY_Community 55|Community 55]]
- [[_COMMUNITY_Community 56|Community 56]]
- [[_COMMUNITY_Community 57|Community 57]]
- [[_COMMUNITY_Community 58|Community 58]]
- [[_COMMUNITY_Community 59|Community 59]]
- [[_COMMUNITY_Community 60|Community 60]]
- [[_COMMUNITY_Community 61|Community 61]]
- [[_COMMUNITY_Community 62|Community 62]]
- [[_COMMUNITY_Community 63|Community 63]]
- [[_COMMUNITY_Community 64|Community 64]]
- [[_COMMUNITY_Community 67|Community 67]]
- [[_COMMUNITY_Community 68|Community 68]]
- [[_COMMUNITY_Community 69|Community 69]]
- [[_COMMUNITY_Community 70|Community 70]]
- [[_COMMUNITY_Community 71|Community 71]]
- [[_COMMUNITY_Community 72|Community 72]]
- [[_COMMUNITY_Community 73|Community 73]]
- [[_COMMUNITY_Community 74|Community 74]]
- [[_COMMUNITY_Community 75|Community 75]]
- [[_COMMUNITY_Community 76|Community 76]]
- [[_COMMUNITY_Community 77|Community 77]]
- [[_COMMUNITY_Community 78|Community 78]]
- [[_COMMUNITY_Community 79|Community 79]]
- [[_COMMUNITY_Community 80|Community 80]]
- [[_COMMUNITY_Community 81|Community 81]]
- [[_COMMUNITY_Community 82|Community 82]]
- [[_COMMUNITY_Community 83|Community 83]]
- [[_COMMUNITY_Community 84|Community 84]]
- [[_COMMUNITY_Community 85|Community 85]]
- [[_COMMUNITY_Community 86|Community 86]]
- [[_COMMUNITY_Community 87|Community 87]]
- [[_COMMUNITY_Community 88|Community 88]]
- [[_COMMUNITY_Community 89|Community 89]]
- [[_COMMUNITY_Community 90|Community 90]]
- [[_COMMUNITY_Community 91|Community 91]]
- [[_COMMUNITY_Community 92|Community 92]]
- [[_COMMUNITY_Community 93|Community 93]]
- [[_COMMUNITY_Community 94|Community 94]]
- [[_COMMUNITY_Community 95|Community 95]]
- [[_COMMUNITY_Community 96|Community 96]]
- [[_COMMUNITY_Community 97|Community 97]]
- [[_COMMUNITY_Community 98|Community 98]]
- [[_COMMUNITY_Community 99|Community 99]]
- [[_COMMUNITY_Community 100|Community 100]]
- [[_COMMUNITY_Community 101|Community 101]]
- [[_COMMUNITY_Community 102|Community 102]]
- [[_COMMUNITY_Community 103|Community 103]]
- [[_COMMUNITY_Community 104|Community 104]]
- [[_COMMUNITY_Community 105|Community 105]]
- [[_COMMUNITY_Community 106|Community 106]]
- [[_COMMUNITY_Community 107|Community 107]]
- [[_COMMUNITY_Community 108|Community 108]]
- [[_COMMUNITY_Community 109|Community 109]]
- [[_COMMUNITY_Community 110|Community 110]]

## God Nodes (most connected - your core abstractions)
1. `SurveyRunner` - 325 edges
2. `RunnerConfig` - 279 edges
3. `BatchExecutor` - 262 edges
4. `CompactSnapshot` - 190 edges
5. `SurveyFiller` - 185 edges
6. `SurveyResult` - 166 edges
7. `CommandRegistry` - 148 edges
8. `SurveyOpener` - 138 edges
9. `ChromeLauncher` - 132 edges
10. `CommandBannedError` - 132 edges

## Surprising Connections (you probably didn't know these)
- `main()` --calls--> `SurveyState`  [INFERRED]
  test_graph_invoke.py → survey-cli/survey/graph/state.py
- `BrowserManager` --uses--> `Kompletter End-to-End Test:     1. Chrome starten (Port 9224, Profil 902)     2.`  [INFERRED]
  agent-toolbox/core/browser_manager.py → agent_toolbox/tests/test_cookie_recovery.py
- `BrowserManager` --calls--> `test_full_recovery_flow()`  [INFERRED]
  agent-toolbox/core/browser_manager.py → agent_toolbox/tests/test_cookie_recovery.py
- `api_open_survey()` --calls--> `open_survey()`  [INFERRED]
  agent-toolbox/api/survey_tools.py → survey-cli/survey/graph/nodes.py
- `api_close_survey()` --calls--> `close_survey_tab()`  [INFERRED]
  agent-toolbox/api/survey_tools.py → survey-cli/tools/tool_open_survey.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.02
Nodes (266): Exception, Read current balance with exponential backoff.          Dashboard DOM updates as, _get_stealth_js(), Load stealth injection bundle, or fallback to inline minimal overrides., cmd_balance(), cmd_login(), cmd_loop(), cmd_profile() (+258 more)

### Community 1 - "Community 1"
Cohesion: 0.02
Nodes (265): Entscheide welche Node als nächstes ausgeführt wird.      Dies ist das zentrale, Entscheide welche Node als nächstes ausgeführt wird.      Dies ist das zentrale, Baue den Survey-StateGraph.      Graph-Struktur:       START → ensure_chrome → o, Baue den Survey-StateGraph.      Graph-Struktur:       START → ensure_chrome → r, Factory: Erstelle und kompiliere den Survey-Graph.      Convenience-Wrapper für:, Factory: Erstelle und kompiliere den Survey-Graph.      Convenience-Wrapper für:, Standalone Survey-Loop ohne LangGraph.      Fallback für Umgebungen wo LangGraph, Standalone Survey-Loop ohne LangGraph.      Fallback für Umgebungen wo LangGraph (+257 more)

### Community 2 - "Community 2"
Cohesion: 0.02
Nodes (264): api_click(), api_click_angular(), api_close_modals(), api_close_survey(), api_detect_completion(), api_fill_input(), api_fill_survey(), api_find() (+256 more)

### Community 3 - "Community 3"
Cohesion: 0.02
Nodes (216): ABC, BaseSettings, BaseSolver, _find_chrome(), Chrome launcher with hardened flags for stealth automation.  WARUM: Standard-Chr, Manages a Chrome process with stealth flags and isolated profile.      Usage:, Launch Chrome with stealth flags.          Blocks until the CDP endpoint becomes, Open a URL in the default tab (creates one if none exist).          Requires tha (+208 more)

### Community 4 - "Community 4"
Cohesion: 0.01
Nodes (158): decrypt_value(), extract_cookies(), get_key(), main(), Get Chrome Safe Storage key from macOS Keychain., Decrypt a single Chrome cookie value., Extract all cookies from Chrome profile., jitter() (+150 more)

### Community 5 - "Community 5"
Cohesion: 0.04
Nodes (169): extract_cookies(), inject_cookies(), ╔══════════════════════════════════════════════════════════════════════════════╗, Extrahiert Cookies aus dem aktuellen Browser (HeyPiggy-fokussiert).          ABL, Injiziert gespeicherte Cookies in den Browser.          ABLAUF:     1. Starte Ze, Prüft ob eine HeyPiggy-Session aktiv ist.          ABLAUF:     1. Hole BrowserMa, verify_session(), Agent-Toolbox API Package. (+161 more)

### Community 6 - "Community 6"
Cohesion: 0.02
Nodes (127): CDPConnection, CDPConnectionError, CDPError, create_cdp(), ================================================================================, Initialize CDP connection.          Args:             ws_url: WebSocket debugger, Connect to the CDP WebSocket with retry., Close the WebSocket connection. (+119 more)

### Community 7 - "Community 7"
Cohesion: 0.03
Nodes (96): ProviderAdapter, CompletionState, ProviderAdapter, ProviderAdapter interface for provider-specific survey behavior.  The engine sho, Provider completion classification., Base adapter with URL matching, commands, and completion detection., Return True if this adapter owns the URL or page text., Return CDP command templates for this provider. (+88 more)

### Community 8 - "Community 8"
Cohesion: 0.04
Nodes (79): CuaAdapter, CuaResult, CuaAdapter — Tiny seam over cua-driver CLI.  WARUM: auto_google_login.py war 170, Type text into AXTextField via cua-driver set_value., Find bot Chrome window by keywords.          Returns:             (pid, wid) tup, Ergebnis eines cua-driver Aufrufs.          WARUM eigene Klasse statt dict?, Initialisiere CuaResult.                  WARUM Defaults ("", "", 0)?, Parse stdout als JSON, gib {} zurück bei Fehler.                  ABLAUF: (+71 more)

### Community 9 - "Community 9"
Cohesion: 0.03
Nodes (65): _main_chrome_pids(), Findet ALLE Bot-Chrome Main-Prozesse.          RETURNS:         list: [(pid, pro, Findet Window-ID (WID) fuer gegebene Chrome-PID.          ARGS:         pid (int, ================================================================================, Initialisiert SessionManager und laedt existierende Sessions.                  W, Laedt Sessions aus JSON-Datei.                  RETURNS:             dict: {"nam, Speichert Sessions als JSON mit ATOMIC WRITE (verhindert Corruption).          W, Registriert neue Session.                  ARGS:             name (str): Eindeut (+57 more)

### Community 10 - "Community 10"
Cohesion: 0.04
Nodes (73): build_survey_prompt(), get_nim(), NIMClient, parse_response(), ================================================================================, Parse LLM response into action list. Robust extraction., NVIDIA Nemotron 3 Omni client with circuit breaker and retry., Get or create default NIM client. (+65 more)

### Community 11 - "Community 11"
Cohesion: 0.03
Nodes (57): Custom threshold works as expected., Always returns a bool., Test the AntiStuck class — DOM-hash repeat detection., After 3 identical hashes, is_stuck returns True., Different hashes never trigger stuck., reset() clears all hash history., count returns consecutive identical hash count., count resets to 1 when hash changes. (+49 more)

### Community 12 - "Community 12"
Cohesion: 0.02
Nodes (96): generate_repo(), main(), make_agents(), make_anti_learn(), make_api(), make_architecture(), make_banned(), make_benchmarks() (+88 more)

### Community 13 - "Community 13"
Cohesion: 0.09
Nodes (89): get_balance(), ╔══════════════════════════════════════════════════════════════════════════════╗, Implementation des Dashboard-Scans (wiederverwendbar für Endpoints + Background-, Scannt das HeyPiggy Dashboard nach verfügbaren Surveys mit Rewards.          ABL, Scannt das HeyPiggy Dashboard nach verfügbaren Surveys mit Rewards.          ABL, Scannt das HeyPiggy Dashboard nach verfügbaren Surveys mit Rewards.          ABL, Liest den aktuellen HeyPiggy Kontostand aus.          ABLAUF:     1. Finde Dashb, Liest den aktuellen HeyPiggy Kontostand aus.          ABLAUF:     1. Finde Dashb (+81 more)

### Community 14 - "Community 14"
Cohesion: 0.03
Nodes (50): Test CDP helper functions with mocked HTTP., Test close_survey_tab function., Placeholder: close_survey_tab exists and accepts tab_id., Test _detect_provider — provider detection from URL., Test _get_details_url and _get_survey_url., TestCdpHelpers, TestCloseSurveyTab, TestCpxApi (+42 more)

### Community 15 - "Community 15"
Cohesion: 0.04
Nodes (43): build_graph(), create_graph(), ================================================================================, Entscheide welche Node als nächstes ausgeführt wird.      Dies ist das zentrale, Baue den Survey-StateGraph.      Graph-Struktur:       START → ensure_chrome → r, Factory: Erstelle und kompiliere den Survey-Graph.      Convenience-Wrapper für:, Standalone Survey-Loop ohne LangGraph.      Fallback für Umgebungen wo LangGraph, route() (+35 more)

### Community 16 - "Community 16"
Cohesion: 0.04
Nodes (42): mail' in 'E-Mail oder Telefonnummer' matches via boundary (mail is word-bounded, Test find_element — main element finder., Weiter' finds [246] but not [247] 'Weitere Informationen'., Weitere' should match 'Weitere Informationen'., Test find_all — returning multiple matches., Test convenience finders: find_button, find_radio, etc., Test diagnose() helper for debugging failed searches., Test _parse_markdown — extracting element dictionaries. (+34 more)

### Community 17 - "Community 17"
Cohesion: 0.04
Nodes (68): _config_value(), CPXCredentials, get_cpx_credentials(), get_google_email(), get_nvidia_api_key(), get_secrets(), MissingSecretError, SecretsClient — single source of truth for all credentials.  Resolution order: e (+60 more)

### Community 18 - "Community 18"
Cohesion: 0.04
Nodes (41): Klicke auf ein Element via cua-driver AXPress.                  ABLAUF:, Click element via cua-driver AXPress., MockWebSocket, click returns error when element not in DOM., click handles WebSocket connection failure gracefully., Three CDP mouse events dispatched: move, press, release., Mock CDP WebSocket that returns shaped responses., Test CDP mouse event click via mocked WebSocket. (+33 more)

### Community 19 - "Community 19"
Cohesion: 0.05
Nodes (26): detect_provider(), Detect survey provider from URL., _detect_progress(), _detect_questions(), generate_snapshot(), Generate compact snapshot from CDP WebSocket URL.      Args:         ws_url: CDP, Extract question texts., Detect survey progress. (+18 more)

### Community 20 - "Community 20"
Cohesion: 0.06
Nodes (45): cmd_doctor(), cmd_status(), _cleanup(), DaemonManager, DaemonProcess, ensure_login(), get_balance(), is_chrome_alive() (+37 more)

### Community 21 - "Community 21"
Cohesion: 0.05
Nodes (59): inject_cookies_into_ws(), main(), Injiziere 7 HeyPiggy-Cookies in eine WebSocket-Verbindung., Find dashboard tab and verify logged in., Injiziere 7 HeyPiggy-Cookies in Dashboard-Tab., Find first available survey on dashboard., Click survey card to open modal., Find the survey tab WebSocket URL. (+51 more)

### Community 22 - "Community 22"
Cohesion: 0.04
Nodes (5): Test SOTA detection functions: detect_error_page, detect_progress, detect_comple, Test detect_progress() — SOTA progress state detection., Test BatchExecutor.detect_error_page() — comprehensive error detection., TestDetectErrorPage, TestDetectProgress

### Community 23 - "Community 23"
Cohesion: 0.05
Nodes (36): analyze_survey_page(), auto_survey_loop(), detect_question_type(), execute_survey_action(), generate_back_to_dashboard_js(), generate_consent_js(), generate_dropdown_js(), generate_matrix_rating_js() (+28 more)

### Community 24 - "Community 24"
Cohesion: 0.05
Nodes (9): Test survey/autodoc.py — append-only logging and summary generation.  WARUM: Aut, End-to-end: log + regenerate summary from same tmp dir., TestAutodocIntegration, TestGenerateSummary, TestLogDecision, TestLogEarnings, TestLogError, TestLogSession (+1 more)

### Community 25 - "Community 25"
Cohesion: 0.06
Nodes (24): New survey tab found after known_tab_ids diff., about:blank tabs are ignored., Returns None when all tabs were known., Custom ignore_urls parameter works., Waits wait_s seconds before scanning., Test find_tab_by_url() — finding tab by URL substring., Test get_all_tabs() — fetching Chrome tab list., get_all_tabs filters to type='page' only. (+16 more)

### Community 26 - "Community 26"
Cohesion: 0.08
Nodes (22): survey/observability/ — Structured logging, metrics, and health monitoring.  WAR, _Colors, _daily_file(), _ensure_logs(), StructuredLogger — JSONL file logging + optional console output.  WARUM: Alle Su, Reconfigure logger for current survey context., Write structured JSONL entry + optional console output., Print to console if verbose enabled. (+14 more)

### Community 27 - "Community 27"
Cohesion: 0.1
Nodes (19): CaptchaSolver, Convert DOM (viewport) coordinates to window coordinates, Execute drag via cua-driver CGEvent, Solve slide captcha (gc-drag-block on gc-drag-slide-bar), Generic: drag element from drag_selector to drop_selector, ================================================================================, ================================================================================, _make_run_side_effect() (+11 more)

### Community 28 - "Community 28"
Cohesion: 0.08
Nodes (18): Integration test: tool_select_language calls CDP with correct JS.      tool_sele, tool_select_language sends JS with selectedIndex + dispatchEvent., tool_select_language returns the CDP result dict., Default language is Deutsch., TestToolSelectLanguageIntegration, Empty CDP response returns error., WebSocket is closed after successful call., Default language is Deutsch. (+10 more)

### Community 29 - "Community 29"
Cohesion: 0.11
Nodes (15): Check if page text contains completion markers., _make_response(), URL containing 'complete' returns 'completed'., WebSocket failure conservative: returns 'running'., English 'thank you for completing' returns 'completed'., quota full' returns 'screen_out'., Unknown page with no markers returns 'running'., Always returns a str. (+7 more)

### Community 30 - "Community 30"
Cohesion: 0.08
Nodes (11): Tests for Agent-Toolbox API endpoints.  WARUM: Die API muss isoliert testbar sei, Test /tools/extract-cookies endpoint., POST /tools/extract-cookies returns cookies., Test /browser/* endpoints with mocked BrowserManager., POST /browser/start returns success., POST /browser/stop returns success., GET /browser/health when browser not running., Test /services/heypiggy/login endpoint. (+3 more)

### Community 31 - "Community 31"
Cohesion: 0.12
Nodes (14): ExperienceMemory, Episodic experience memory: caches successful trajectories per (host, captcha-ty, ================================================================================, Initialize the database and create tables if needed., Store a trajectory in the experience database.          Args:             record, Find successful trajectories with similar gap distance.          Args:, Get memory statistics., Close the database connection. (+6 more)

### Community 32 - "Community 32"
Cohesion: 0.09
Nodes (10): _daily_file(), _ensure_logs(), SurveyMetrics — in-memory counters + periodic JSONL persistence.  WARUM: Phase 5, Return current metrics snapshot., Write current snapshot to JSONL., Reset all counters (for testing)., Reset metrics singleton (for testing)., Thread-safe in-memory metrics singleton with JSONL persistence. (+2 more)

### Community 33 - "Community 33"
Cohesion: 0.14
Nodes (22): answer_page(), answer_survey(), capture_page(), cdp_eval(), cdp_execute_js(), click_submit(), detect_page_type(), get_body_text() (+14 more)

### Community 34 - "Community 34"
Cohesion: 0.1
Nodes (12): CookieManager, ╔══════════════════════════════════════════════════════════════════════════════╗, Verwaltet Browser-Cookies für Session-Persistenz.          Extrahiert, speichert, Initialisiert den Cookie-Manager.                  ABLAUF:         1. Speichere, Extrahiert alle Cookies der aktuellen Page.                  ABLAUF:         1., Speichert Cookies in eine JSON-Datei.                  ABLAUF:         1. Erstel, Lädt Cookies aus einer JSON-Datei.                  ABLAUF:         1. Erstelle, Injiziert Cookies in einen Browser-Context.                  ABLAUF:         1. (+4 more)

### Community 35 - "Community 35"
Cohesion: 0.15
Nodes (12): check_and_alert(), is_session_corrupted(), RuntimeHealth — Daemon/Chrome/Session health snapshot.  WARUM: Phase 5 — "Fehler, Check session registry for corruption., Generate full health snapshot., Return True if all subsystems are operational., Check health and return snapshot. Prints alerts for issues.      Returns:, Check if a session file is corrupted (< 100 bytes or invalid JSON).      Args: (+4 more)

### Community 36 - "Community 36"
Cohesion: 0.17
Nodes (16): check_banned_header(), check_banned_patterns(), check_docstrings(), check_hardcoded_credentials(), check_hardcoded_pids(), check_test_coverage(), get_python_files(), Findet alle Python-Dateien im Projekt (rekursiv).      Args:         root: Root- (+8 more)

### Community 37 - "Community 37"
Cohesion: 0.18
Nodes (16): click_start_button(), create_survey_tab(), _eval_js(), get_survey_url(), inject_cookies_and_navigate(), load_heypiggy_cookies(), open_survey(), Klicke 'Umfrage starten' Button im Modal (schliesst Modal). (+8 more)

### Community 38 - "Community 38"
Cohesion: 0.19
Nodes (14): create_tab_with_cookies(), kill_bot_chrome(), load_heypiggy_cookies(), main(), navigate_to_dashboard(), Start Chrome with Profile 901 copy on port 9999. Returns browser WS URL., Create about:blank tab, inject cookies, return (tab_ws, target_id)., Navigate tab to HeyPiggy dashboard. (+6 more)

### Community 39 - "Community 39"
Cohesion: 0.2
Nodes (14): check_login(), count_surveys(), find_heypiggy_tab(), is_chrome_alive(), preflight_check(), preflight_or_start(), Liest Balance aus Dashboard-Tab.          Filter: Nur Betraege >= 1.0€ (Rewards, Zaehlt verfügbare Surveys auf Dashboard.          Sucht nach survey-item cards, (+6 more)

### Community 40 - "Community 40"
Cohesion: 0.2
Nodes (13): generate_stealth_js(), get_current_identity(), get_identity_hash(), inject_stealth(), ╔═══════════════════════════════════════════════════════════════════════════════, Generiert JavaScript-Code der bei JEDEM Page-Load injected wird.          Args:, Generiert Hash der Identität (für Session-Validierung)., Injected Stealth-JS auf eine Seite via CDP.          Args:         ws_url: CDP W (+5 more)

### Community 41 - "Community 41"
Cohesion: 0.21
Nodes (13): _get_cdp_pages(), _get_state(), State Verification Tool — __frozen__=True  After jeder Aktion: verify dass Zusta, Verify page state by URL, text content, or element counts.      Args:         ur, Verify heypiggy dashboard shows logged-in state., Verify survey page loaded (has questions/radio buttons)., Verify survey completion page (Vielen Dank, etc.)., Verify an element exists with expected role/text.      Returns:         {"status (+5 more)

### Community 42 - "Community 42"
Cohesion: 0.27
Nodes (3): Tests for ActionSelector — fallback action generation without NIM.  WARUM: Jede, Test ActionSelector.select_actions() with various snapshot inputs., TestActionSelector

### Community 43 - "Community 43"
Cohesion: 0.31
Nodes (8): _delegate_to_toolbox_api(), _legacy_to_canonical(), _load_survey_entry(), main(), Delegate to the canonical survey-cli main() or Agent-Toolbox API., Map old root flags to canonical survey-cli subcommands., Load `survey-cli/survey.py` without confusing it with the `survey` package., Try to delegate to the running Agent-Toolbox API on localhost:8000.

### Community 44 - "Community 44"
Cohesion: 0.22
Nodes (8): auto_doc(), monitor(), Session-Monitoring Daemon (STUB).          WARUM STUB?       Die echte Monitor-L, Automatische Dokumentationsgenerierung (STUB).          WARUM STUB?       Die ec, Session-Zusammenfassung (STUB).          WARUM STUB?       Session-Zusammenfassu, AX-Dokumentation Validierung (STUB).          WARUM STUB?       AX-Doku ist in A, summarize(), validate_ax_docs()

### Community 45 - "Community 45"
Cohesion: 0.32
Nodes (7): _cleanup_old_entries(), _get_client_id(), rate_limit_dependency(), ╔══════════════════════════════════════════════════════════════════════════════╗, FastAPI Dependency für Rate Limiting.     Prüft ALLE Tier-Limits. Wenn EINES gre, Erzeugt eine Client-ID aus IP und User-Agent., Entfernt Einträge die älter als 24h sind.

### Community 46 - "Community 46"
Cohesion: 0.36
Nodes (7): eval_js(), Receive WebSocket message matching target ID (drains all event messages)., # IMPORTANT: DO NOT enable Page/Network events — they flood the buffer!, Evaluate JS and return result value., # IMPORTANT: Runtime.enable must be called for JS click handlers to work, recv_target(), test_open_survey()

### Community 47 - "Community 47"
Cohesion: 0.38
Nodes (6): check_repo(), find_repo(), main(), SOTA Audit: check ALL required files + UPPERCASE violations., ================================================================================, Find repo dir by name in /Users/jeremy/dev.

### Community 48 - "Community 48"
Cohesion: 0.29
Nodes (3): Tests for fail-closed secret resolution., SecretsClient must never return real code defaults., TestSecretsClient

### Community 49 - "Community 49"
Cohesion: 0.33
Nodes (6): click_survey(), find_first_survey(), find_surveys(), Findet die erste/beste Survey auf dem Dashboard.          Sortiert nach: hoechst, Klickt Survey-Card via clickSurvey() auf dem Dashboard.          Returns:, Findet alle Survey-IDs auf dem HeyPiggy Dashboard.          Returns:         {

### Community 50 - "Community 50"
Cohesion: 0.4
Nodes (2): jitter(), rng()

### Community 51 - "Community 51"
Cohesion: 0.53
Nodes (5): _fill_textarea(), _find_submit(), ActionSelector — generate survey actions from CompactSnapshot when NIM unavailab, select_actions(), _select_radio()

### Community 52 - "Community 52"
Cohesion: 0.5
Nodes (3): load(), Embedded JS payloads for reference — legacy dispatchEvent approach.  WARUM: Hist, Load a JS payload by filename.      Args:         name: Filename (e.g., "gocaptc

### Community 53 - "Community 53"
Cohesion: 0.67
Nodes (1): Survey CLI Test Suite.  WARUM: Jede Änderung am Survey-Loop (NEMO, CDP, Provider

### Community 55 - "Community 55"
Cohesion: 1.0
Nodes (1): Prüft ob Chrome aktiv ist.                  PRÜFUNG IN REIHENFOLGE:         1. W

### Community 56 - "Community 56"
Cohesion: 1.0
Nodes (1): POST /services/heypiggy/login returns success.

### Community 57 - "Community 57"
Cohesion: 1.0
Nodes (1): POST /services/heypiggy/login when already logged in.

### Community 58 - "Community 58"
Cohesion: 1.0
Nodes (1): POST /services/heypiggy/login with error.

### Community 59 - "Community 59"
Cohesion: 1.0
Nodes (1): Hole NVIDIA_API_KEY aus Umgebungsvariable.                  WARUM @staticmethod

### Community 60 - "Community 60"
Cohesion: 1.0
Nodes (1): Hole NVIDIA_API_KEY oder wirf MissingSecretError.                  WARUM @classm

### Community 61 - "Community 61"
Cohesion: 1.0
Nodes (1): Hole konfigurierte Google Login E-Mail.                  ABLAUF:           1. Ru

### Community 62 - "Community 62"
Cohesion: 1.0
Nodes (1): Hole komplette CPX Credentials als CPXCredentials Objekt.                  ABLAU

### Community 63 - "Community 63"
Cohesion: 1.0
Nodes (1): Löse ein required Secret auf (Resolution Order: env → config → error).

### Community 64 - "Community 64"
Cohesion: 1.0
Nodes (1): Löse dotted key in ~/.stealth/config.yaml auf.                  ABLAUF:

### Community 67 - "Community 67"
Cohesion: 1.0
Nodes (1): Zählt wie oft aktueller Hash wiederholt wurde.                  RETURNS:

### Community 68 - "Community 68"
Cohesion: 1.0
Nodes (1): execute() creates GoogleOAuthFlow and returns result.

### Community 69 - "Community 69"
Cohesion: 1.0
Nodes (1): execute() returns error dict on failure.

### Community 70 - "Community 70"
Cohesion: 1.0
Nodes (1): execute() returns ok for already_logged_in status.

### Community 71 - "Community 71"
Cohesion: 1.0
Nodes (1): Generate action list from snapshot (fallback when NIM unavailable).          Arg

### Community 72 - "Community 72"
Cohesion: 1.0
Nodes (1): Return select action for best radio/checkbox match.

### Community 73 - "Community 73"
Cohesion: 1.0
Nodes (1): Return submit action for first enabled submit button.

### Community 74 - "Community 74"
Cohesion: 1.0
Nodes (1): Return fill action for first textarea with plausible answer.

### Community 75 - "Community 75"
Cohesion: 1.0
Nodes (1): Load profile from JSON or return default with calculated age.          Args:

### Community 76 - "Community 76"
Cohesion: 1.0
Nodes (1): Calculate earnings from before/after balance.          Returns max(0, after - be

### Community 77 - "Community 77"
Cohesion: 1.0
Nodes (1): True wenn Graph noch aktiv ist (nicht completed/error/delegated).

### Community 78 - "Community 78"
Cohesion: 1.0
Nodes (1): True wenn Graph in einem Endzustand ist.

### Community 79 - "Community 79"
Cohesion: 1.0
Nodes (1): True wenn 3+ consecutive failures erreicht wurden.

### Community 80 - "Community 80"
Cohesion: 1.0
Nodes (1): Berechneter Verdienst: balance_after minus balance_before.

### Community 81 - "Community 81"
Cohesion: 1.0
Nodes (1): Extract survey IDs from dashboard via CDP.      Returns:         List of survey

### Community 82 - "Community 82"
Cohesion: 1.0
Nodes (1): Filter surveys via CPX API.      Args:         survey_ids: List of IDs to check

### Community 83 - "Community 83"
Cohesion: 1.0
Nodes (1): Pretty-print filtered survey results.

### Community 84 - "Community 84"
Cohesion: 1.0
Nodes (1): Scan dashboard DOM for survey cards with rewards.      heypiggy renders survey c

### Community 85 - "Community 85"
Cohesion: 1.0
Nodes (1): Full scan: connect → extract IDs → filter → print.      Returns:         List of

### Community 86 - "Community 86"
Cohesion: 1.0
Nodes (1): Read page innerText via CDP.

### Community 87 - "Community 87"
Cohesion: 1.0
Nodes (1): Read current balance from dashboard.      The heypiggy dashboard shows balance i

### Community 88 - "Community 88"
Cohesion: 1.0
Nodes (1): Read balance with exponential backoff — avoids false 0.00€ reads.      Dashboard

### Community 89 - "Community 89"
Cohesion: 1.0
Nodes (1): Close a survey tab and return to dashboard.

### Community 90 - "Community 90"
Cohesion: 1.0
Nodes (1): Read balance with exponential backoff — avoids false 0.00€ reads.      Dashboard

### Community 91 - "Community 91"
Cohesion: 1.0
Nodes (1): Angular CDK drag-drop puzzle solver (sync wrapper).      Tries in order:     1.

### Community 92 - "Community 92"
Cohesion: 1.0
Nodes (1): Get live details_url from dashboard page.

### Community 93 - "Community 93"
Cohesion: 1.0
Nodes (1): Fetch actual survey URL from CPX API.

### Community 94 - "Community 94"
Cohesion: 1.0
Nodes (1): Create new browser tab via CDP Target.createTarget.

### Community 95 - "Community 95"
Cohesion: 1.0
Nodes (1): Find a tab that wasn't in old_tab_ids.

### Community 96 - "Community 96"
Cohesion: 1.0
Nodes (1): Click 'Umfrage starten' in modal via window.open interception + Target.createTar

### Community 97 - "Community 97"
Cohesion: 1.0
Nodes (1): Handle modal via CDP JS (pre-qualifier or "Umfrage starten").          Handles t

### Community 98 - "Community 98"
Cohesion: 1.0
Nodes (1): Handle pre-qualifier modal: click submit, then handle resulting modal.

### Community 99 - "Community 99"
Cohesion: 1.0
Nodes (1): Open a survey — handle CPX redirect + modals + new-tab detection.      Args:

### Community 100 - "Community 100"
Cohesion: 1.0
Nodes (1): Close a survey tab and return to dashboard.

### Community 101 - "Community 101"
Cohesion: 1.0
Nodes (1): Read balance with exponential backoff — avoids false 0.00€ reads.      Dashboard

### Community 102 - "Community 102"
Cohesion: 1.0
Nodes (1): True wenn Graph noch aktiv ist (nicht completed/error/delegated).

### Community 103 - "Community 103"
Cohesion: 1.0
Nodes (1): True wenn Graph in einem Endzustand ist.

### Community 104 - "Community 104"
Cohesion: 1.0
Nodes (1): True wenn 3+ consecutive failures erreicht wurden.

### Community 105 - "Community 105"
Cohesion: 1.0
Nodes (1): Berechneter Verdienst: balance_after minus balance_before.

### Community 106 - "Community 106"
Cohesion: 1.0
Nodes (1): Füge einen Fehler zur errors-Liste hinzu.          Args:             node: Name

### Community 107 - "Community 107"
Cohesion: 1.0
Nodes (1): Reset consecutive_failures auf 0 nach erfolgreichem execute.

### Community 108 - "Community 108"
Cohesion: 1.0
Nodes (1): Inkrementiere consecutive_failures nach failed execute.

### Community 109 - "Community 109"
Cohesion: 1.0
Nodes (1): Inkrementiere iteration nach NEMO-Loop-Durchlauf.

### Community 110 - "Community 110"
Cohesion: 1.0
Nodes (1): Kompakte String-Repräsentation für Debugging.

## Knowledge Gaps
- **804 isolated node(s):** `Find Dashboard tab WebSocket URL.`, `Check if session is valid (body contains 'abmelden').`, `Scan dashboard for available surveys.`, `Select best survey based on reward * provider_trust.`, `Map old root flags to canonical survey-cli subcommands.` (+799 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 50`** (6 nodes): `get()`, `jitter()`, `patch()`, `rng()`, `safe()`, `stealth_main.js`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 53`** (3 nodes): `__init__.py`, `__init__.py`, `Survey CLI Test Suite.  WARUM: Jede Änderung am Survey-Loop (NEMO, CDP, Provider`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 55`** (1 nodes): `Prüft ob Chrome aktiv ist.                  PRÜFUNG IN REIHENFOLGE:         1. W`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 56`** (1 nodes): `POST /services/heypiggy/login returns success.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 57`** (1 nodes): `POST /services/heypiggy/login when already logged in.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 58`** (1 nodes): `POST /services/heypiggy/login with error.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 59`** (1 nodes): `Hole NVIDIA_API_KEY aus Umgebungsvariable.                  WARUM @staticmethod`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 60`** (1 nodes): `Hole NVIDIA_API_KEY oder wirf MissingSecretError.                  WARUM @classm`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 61`** (1 nodes): `Hole konfigurierte Google Login E-Mail.                  ABLAUF:           1. Ru`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 62`** (1 nodes): `Hole komplette CPX Credentials als CPXCredentials Objekt.                  ABLAU`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 63`** (1 nodes): `Löse ein required Secret auf (Resolution Order: env → config → error).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 64`** (1 nodes): `Löse dotted key in ~/.stealth/config.yaml auf.                  ABLAUF:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 67`** (1 nodes): `Zählt wie oft aktueller Hash wiederholt wurde.                  RETURNS:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 68`** (1 nodes): `execute() creates GoogleOAuthFlow and returns result.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 69`** (1 nodes): `execute() returns error dict on failure.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 70`** (1 nodes): `execute() returns ok for already_logged_in status.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 71`** (1 nodes): `Generate action list from snapshot (fallback when NIM unavailable).          Arg`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 72`** (1 nodes): `Return select action for best radio/checkbox match.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 73`** (1 nodes): `Return submit action for first enabled submit button.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 74`** (1 nodes): `Return fill action for first textarea with plausible answer.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 75`** (1 nodes): `Load profile from JSON or return default with calculated age.          Args:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 76`** (1 nodes): `Calculate earnings from before/after balance.          Returns max(0, after - be`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 77`** (1 nodes): `True wenn Graph noch aktiv ist (nicht completed/error/delegated).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 78`** (1 nodes): `True wenn Graph in einem Endzustand ist.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 79`** (1 nodes): `True wenn 3+ consecutive failures erreicht wurden.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 80`** (1 nodes): `Berechneter Verdienst: balance_after minus balance_before.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 81`** (1 nodes): `Extract survey IDs from dashboard via CDP.      Returns:         List of survey`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 82`** (1 nodes): `Filter surveys via CPX API.      Args:         survey_ids: List of IDs to check`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 83`** (1 nodes): `Pretty-print filtered survey results.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 84`** (1 nodes): `Scan dashboard DOM for survey cards with rewards.      heypiggy renders survey c`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 85`** (1 nodes): `Full scan: connect → extract IDs → filter → print.      Returns:         List of`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 86`** (1 nodes): `Read page innerText via CDP.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 87`** (1 nodes): `Read current balance from dashboard.      The heypiggy dashboard shows balance i`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 88`** (1 nodes): `Read balance with exponential backoff — avoids false 0.00€ reads.      Dashboard`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 89`** (1 nodes): `Close a survey tab and return to dashboard.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 90`** (1 nodes): `Read balance with exponential backoff — avoids false 0.00€ reads.      Dashboard`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 91`** (1 nodes): `Angular CDK drag-drop puzzle solver (sync wrapper).      Tries in order:     1.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 92`** (1 nodes): `Get live details_url from dashboard page.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 93`** (1 nodes): `Fetch actual survey URL from CPX API.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 94`** (1 nodes): `Create new browser tab via CDP Target.createTarget.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 95`** (1 nodes): `Find a tab that wasn't in old_tab_ids.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 96`** (1 nodes): `Click 'Umfrage starten' in modal via window.open interception + Target.createTar`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 97`** (1 nodes): `Handle modal via CDP JS (pre-qualifier or "Umfrage starten").          Handles t`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 98`** (1 nodes): `Handle pre-qualifier modal: click submit, then handle resulting modal.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 99`** (1 nodes): `Open a survey — handle CPX redirect + modals + new-tab detection.      Args:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 100`** (1 nodes): `Close a survey tab and return to dashboard.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 101`** (1 nodes): `Read balance with exponential backoff — avoids false 0.00€ reads.      Dashboard`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 102`** (1 nodes): `True wenn Graph noch aktiv ist (nicht completed/error/delegated).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 103`** (1 nodes): `True wenn Graph in einem Endzustand ist.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 104`** (1 nodes): `True wenn 3+ consecutive failures erreicht wurden.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 105`** (1 nodes): `Berechneter Verdienst: balance_after minus balance_before.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 106`** (1 nodes): `Füge einen Fehler zur errors-Liste hinzu.          Args:             node: Name`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 107`** (1 nodes): `Reset consecutive_failures auf 0 nach erfolgreichem execute.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 108`** (1 nodes): `Inkrementiere consecutive_failures nach failed execute.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 109`** (1 nodes): `Inkrementiere iteration nach NEMO-Loop-Durchlauf.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 110`** (1 nodes): `Kompakte String-Repräsentation für Debugging.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `SurveyRunner` connect `Community 0` to `Community 1`, `Community 5`, `Community 10`, `Community 14`, `Community 28`?**
  _High betweenness centrality (0.125) - this node is a cross-community bridge._
- **Why does `patch()` connect `Community 4` to `Community 0`, `Community 1`, `Community 6`, `Community 7`, `Community 9`, `Community 11`, `Community 14`, `Community 18`, `Community 19`, `Community 20`, `Community 25`, `Community 27`, `Community 28`, `Community 29`, `Community 30`?**
  _High betweenness centrality (0.121) - this node is a cross-community bridge._
- **Why does `BatchExecutor` connect `Community 1` to `Community 0`, `Community 4`, `Community 6`, `Community 7`, `Community 15`, `Community 22`, `Community 28`, `Community 29`?**
  _High betweenness centrality (0.120) - this node is a cross-community bridge._
- **Are the 304 inferred relationships involving `SurveyRunner` (e.g. with `╔══════════════════════════════════════════════════════════════════════════════╗` and `Lazy-Load BrowserManager — erstellt eine neue Instanz bei jedem Aufruf.`) actually correct?**
  _`SurveyRunner` has 304 INFERRED edges - model-reasoned connections that need verification._
- **Are the 277 inferred relationships involving `RunnerConfig` (e.g. with `╔══════════════════════════════════════════════════════════════════════════════╗` and `Lazy-Load BrowserManager — erstellt eine neue Instanz bei jedem Aufruf.`) actually correct?**
  _`RunnerConfig` has 277 INFERRED edges - model-reasoned connections that need verification._
- **Are the 252 inferred relationships involving `BatchExecutor` (e.g. with `TestSimpleActions` and `TestRunSurveyLoopDetection`) actually correct?**
  _`BatchExecutor` has 252 INFERRED edges - model-reasoned connections that need verification._
- **Are the 186 inferred relationships involving `CompactSnapshot` (e.g. with `TestCompleteImmediately` and `TestCircuitBreaker`) actually correct?**
  _`CompactSnapshot` has 186 INFERRED edges - model-reasoned connections that need verification._