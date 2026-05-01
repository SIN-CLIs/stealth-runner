# Graph Report - stealth-runner  (2026-05-01)

## Corpus Check
- 73 files · ~33,094 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 475 nodes · 694 edges · 43 communities detected
- Extraction: 75% EXTRACTED · 25% INFERRED · 0% AMBIGUOUS · INFERRED: 176 edges (avg confidence: 0.68)
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
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]

## God Nodes (most connected - your core abstractions)
1. `StealthExecutor` - 28 edges
2. `SurveyRunner` - 24 edges
3. `LiveOmniMonitor` - 21 edges
4. `AuditLog` - 19 edges
5. `VisionClient` - 18 edges
6. `SkylightDriver` - 16 edges
7. `detect_panel()` - 14 edges
8. `HumanProfile` - 13 edges
9. `classify_element()` - 10 edges
10. `classify_error()` - 10 edges

## Surprising Connections (you probably didn't know these)
- `main()` --calls--> `SurveyRunner`  [INFERRED]
  main.py → runner/state_machine.py
- `StealthExecutor` --uses--> `TestVisionClient`  [INFERRED]
  runner/stealth_executor.py → tests/test_runner.py
- `HumanProfile` --uses--> `TestVisionClient`  [INFERRED]
  runner/human_profile.py → tests/test_runner.py
- `stealth-runner – Orchestrator der Stealth-Triade v0.3.1.` --uses--> `State`  [INFERRED]
  runner/__init__.py → src/stealth_runner/state_machine.py
- `SurveyRunner` --calls--> `test_state_machine_initializes()`  [INFERRED]
  runner/state_machine.py → tests/test_state_machine.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.07
Nodes (14): AuditLog, AuditLog – Thread-safe JSONL trace mit Batched Writes., HumanProfile, HumanProfile – SOTA Behavioral Biometrics via scipy.stats PDFs., stealth-runner – Orchestrator der Stealth-Triade v0.3.1., build_prompt(), prompt_kit – SYSTEM_PROMPT mit expliziten SoM-Referenzen., State Machine — JEDER Schritt VISION (Omni-first, Multi-Frame). (+6 more)

### Community 1 - "Community 1"
Cohesion: 0.08
Nodes (16): Exception, FatalCLIError, Async CLI-Executor mit Timeout, Exit-Code-Mapping & Zombie-Cleanup., RetryableCLIError, StealthDegradedError, ClickValidationError, Strict click contract enforcement — blocks raw coordinates., validate_click_command() (+8 more)

### Community 2 - "Community 2"
Cohesion: 0.11
Nodes (13): _extract_json(), LiveOmniMonitor, OmniObservation, Live Omni Screen Monitor – Rolling Video Buffer + Screenshot Hybrid.  ARCHITEKTU, Extrahiert die letzten N Sekunden als base64-mp4., Screenshot (schnell) oder Rolling-Video-Clip (temporal) an Omni., Hybrid Loop: Screenshot (schnell) + Video (alle 5 Schritte temporal)., Screenshot + Rolling Video Buffer → Omni → skylight-cli Execute. (+5 more)

### Community 3 - "Community 3"
Cohesion: 0.08
Nodes (11): ABC, BaseDriver, SkylightDriver, StealthExecutor – TLS-geprüft, Driver-basiert, Omni-integriert., StealthError, get_ja4_fingerprint(), TLS-Fingerprinting auf JA4-Basis., test_click_with_axpath() (+3 more)

### Community 4 - "Community 4"
Cohesion: 0.11
Nodes (12): build_panel_prompt_block(), detect_panel(), detect_panel_dq(), detect_quality_trap(), PanelRules, Panel-Provider-Erkennung anhand von URL- und Text-Mustern (8 Provider)., Panel-Provider-Erkennung für Umfrageplattformen.  Provider (8): PureSpectrum, Dy, Tests für sin_survey_core – Panel, EUR, Errors. (+4 more)

### Community 5 - "Community 5"
Cohesion: 0.14
Nodes (16): BaseSettings, AuditLogger, StealthConfig, SurveyConfig, FatalError, RetryableError, run_cli_atomic(), StealthRunnerError (+8 more)

### Community 6 - "Community 6"
Cohesion: 0.14
Nodes (17): get_omni(), OmniClient, OmniError, _parse_json(), Nemotron 3 Nano Omni – Unified Video+Audio+Image+Text Client.  Ersetzt separate, Single multimodal client for video, audio, image, text., load_state(), main() (+9 more)

### Community 7 - "Community 7"
Cohesion: 0.1
Nodes (11): Fehlerklassifikation für Umfrage-Abbrüche (4 Kategorien, mehrsprachig)., classify_error(), ErrorCategory, ErrorInfo, Fehlerklassifikation für Umfrage-Abbrüche — ErrorCategory Enum + ErrorInfo Datac, ExtendedState, Erweiterte State Machine mit Exit-Code-Routing & Stealth-Scoring., sin_survey_core – Aus dem A2A-SIN-Worker extrahierte Survey-Intelligenz. (+3 more)

### Community 8 - "Community 8"
Cohesion: 0.15
Nodes (7): classify_element(), _has_images(), prescan_dom(), dom_prescan – Vision-free Fast Path via unmask-cli DOM-Scan., Tests für dom_prescan – Vision-free Fast Path., TestClassifyElement, TestPrescanDom

### Community 9 - "Community 9"
Cohesion: 0.15
Nodes (7): Typer CLI mit Rich Progress für den stealth-runner., run(), SurveyRunner, main(), test_max_recoveries_stops(), test_state_machine_initializes(), test_state_transition_idle_to_launch()

### Community 10 - "Community 10"
Cohesion: 0.17
Nodes (9): EarningsSummary, extract_earnings_summary(), extract_eur_from_text(), EUR-Betrag-Extraktion aus Umfrage-Seitentexten.  Verwendet vorkompilierte Regex-, Extrahiert den ersten EUR-Betrag aus einem beliebigen Text., Strukturierte EUR-Auszahlung aus einem Survey-Chunk., Extrahiert EUR-Betrag und gibt eine Zusammenfassung zurück., EUR-Betrag-Extraktion aus Umfrage-Seitentexten.  Bietet zwei Funktionen:  * :fun (+1 more)

### Community 11 - "Community 11"
Cohesion: 0.18
Nodes (10): BaseModel, ClickAction, DoneAction, HoldAction, Pydantic V2-Modelle für strukturierte Vision-API-Antworten., ScrollAction, TypeAction, WaitAction (+2 more)

### Community 12 - "Community 12"
Cohesion: 0.24
Nodes (5): classify_error(), learn_from_error(), Anti-Learning Module — Error-to-Recovery Generator., store(), TestClassifyError

### Community 13 - "Community 13"
Cohesion: 0.25
Nodes (9): chrome_health_check(), is_chrome_running(), Chrome Health-Check und Recovery., Prüft, ob Chrome-Prozess noch läuft., Startet Chrome neu und gibt Haupt-PID zurück., Führt Health-Check durch und startet Chrome neu falls nötig., relaunch_chrome(), Tests für Chrome Recovery. (+1 more)

### Community 14 - "Community 14"
Cohesion: 0.31
Nodes (9): check_tools(), find_repos(), main(), phase1_deep_scan(), phase2_analyze(), phase3_generate(), Phase 2: Analysieren – Fehler finden, Qualität prüfen., Phase 3: Fehlende Dokumente generieren (nur bei genug Daten). (+1 more)

### Community 15 - "Community 15"
Cohesion: 0.27
Nodes (9): load_state(), State-File Management mit Backup & Recovery., Lädt State mit Backup-Recovery., Speichert State mit Backup., Versucht, State aus Backups wiederherzustellen., Validiert State-Struktur., _recover_state(), save_state() (+1 more)

### Community 16 - "Community 16"
Cohesion: 0.25
Nodes (2): Vision-Client Konfiguration (YAML-basiert)., VisionConfig

### Community 17 - "Community 17"
Cohesion: 0.25
Nodes (2): Thread-sichere Survey-Queue (SQLite + FileLock)., SurveyQueue

### Community 18 - "Community 18"
Cohesion: 0.29
Nodes (2): FrameOptimizer, Frame-Diffing & ROI-Cropping für Vision-Token-Optimierung.

### Community 19 - "Community 19"
Cohesion: 0.33
Nodes (2): AuditLoggerSync, Crash-sicheres JSONL Audit-Log mit O_SYNC + fcntl.

### Community 20 - "Community 20"
Cohesion: 0.33
Nodes (2): ScreenFollowDriver – Bildschirmaufnahme via screen-follow CLI., ScreenFollowDriver

### Community 21 - "Community 21"
Cohesion: 0.33
Nodes (2): UnmaskDriver – DOM-Scan via unmask-cli für Vision-free Fast Path., UnmaskDriver

### Community 22 - "Community 22"
Cohesion: 0.4
Nodes (1): Behavioral Biometrics via scipy.stats PDFs.

### Community 23 - "Community 23"
Cohesion: 0.4
Nodes (1): Resilienz-Patterns: Retry, Circuit Breaker, Graceful Shutdown.

### Community 24 - "Community 24"
Cohesion: 0.6
Nodes (4): learn_from_session(), push_to_global_brain(), Skill Capture Loop — parst screen-follow Audit-Log (type: mouse_down, etc.)., update_registry()

### Community 25 - "Community 25"
Cohesion: 0.5
Nodes (2): Stealth-Scoring nach 6 Prüfvektoren mit gewichteten Thresholds., StealthResult

### Community 26 - "Community 26"
Cohesion: 0.5
Nodes (1): Semantic Vision Cache via diskcache.

### Community 27 - "Community 27"
Cohesion: 0.67
Nodes (3): load_brain_rules(), Strategy Evolution Module — wählt optimale Skill-Sequenz aus Brain-Daten., select_best_strategy()

### Community 28 - "Community 28"
Cohesion: 0.67
Nodes (1): Structured Logging mit structlog.

### Community 29 - "Community 29"
Cohesion: 0.67
Nodes (1): OpenTelemetry APM – Traces über alle States.

### Community 31 - "Community 31"
Cohesion: 1.0
Nodes (1): Zentrale Konfiguration – lädt .env und validiert alle Secrets.

### Community 32 - "Community 32"
Cohesion: 1.0
Nodes (1): pytest-Konfiguration für den stealth-runner.

### Community 33 - "Community 33"
Cohesion: 1.0
Nodes (1): Test-Suite für den stealth-runner. Führe mit: pytest tests/ -v

### Community 34 - "Community 34"
Cohesion: 1.0
Nodes (1): stealth-runner: Vision-driven CLI orchestrator for stealth survey automation.

### Community 36 - "Community 36"
Cohesion: 1.0
Nodes (1): Der Doktor – scannt, findet, fixrt, committed.

### Community 37 - "Community 37"
Cohesion: 1.0
Nodes (1): Hauptlauf: Alle Repos → Alle Lenses → Fixen → Report.

### Community 38 - "Community 38"
Cohesion: 1.0
Nodes (1): Lens 1: Finde + fixe veraltete Claims in ALLEN .md Dateien.

### Community 39 - "Community 39"
Cohesion: 1.0
Nodes (1): Lens 6: Finde API-Keys + Passwoerter in Docs.

### Community 40 - "Community 40"
Cohesion: 1.0
Nodes (1): Lens 4: Prüfe welche SOTA Docs fehlen.

### Community 41 - "Community 41"
Cohesion: 1.0
Nodes (1): Lens 2: Finde defekte Links via md-dead-link-check (wenn installiert).

### Community 42 - "Community 42"
Cohesion: 1.0
Nodes (1): Commit + Push in ALLEN Repos.

### Community 43 - "Community 43"
Cohesion: 1.0
Nodes (1): Hybrid Loop: Screenshot (schnell) + Video (alle 5 Schritte temporal).

### Community 44 - "Community 44"
Cohesion: 1.0
Nodes (1): Hybrid Loop: Screenshot (schnell) + Video (alle 5 Schritte temporal).

## Knowledge Gaps
- **71 isolated node(s):** `FastAPI wrapper for stealth-runner – SaaS API (SOTA #14).`, `Phase 1: Repo bis auf letzten Millimeter scannen.`, `Phase 2: Analysieren – Fehler finden, Qualität prüfen.`, `Phase 3: Fehlende Dokumente generieren (nur bei genug Daten).`, `State-File Management mit Backup & Recovery.` (+66 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 16`** (9 nodes): `config.py`, `current_model()`, `fallback_models()`, `max_tokens()`, `Vision-Client Konfiguration (YAML-basiert).`, `timeout()`, `VisionConfig`, `.__init__()`, `._load_config()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 17`** (8 nodes): `survey_queue.py`, `Thread-sichere Survey-Queue (SQLite + FileLock).`, `SurveyQueue`, `.claim_task()`, `.enqueue()`, `.__init__()`, `.mark_done()`, `.mark_failed()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 18`** (7 nodes): `FrameOptimizer`, `.crop_roi()`, `.__init__()`, `.is_duplicate()`, `frame_optimizer.py`, `Frame-Diffing & ROI-Cropping für Vision-Token-Optimierung.`, `skipped_count()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 19`** (6 nodes): `AuditLoggerSync`, `.close()`, `.__init__()`, `.log()`, `audit_logger_sync.py`, `Crash-sicheres JSONL Audit-Log mit O_SYNC + fcntl.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 20`** (6 nodes): `ScreenFollowDriver – Bildschirmaufnahme via screen-follow CLI.`, `ScreenFollowDriver`, `.get_status()`, `.start_recording()`, `.stop_recording()`, `screen_follow.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 21`** (6 nodes): `UnmaskDriver – DOM-Scan via unmask-cli für Vision-free Fast Path.`, `UnmaskDriver`, `.dom_scan()`, `.inspect()`, `.network_capture()`, `unmask.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 22`** (5 nodes): `behavioral_biometrics.py`, `Behavioral Biometrics via scipy.stats PDFs.`, `sample_dwell_time()`, `sample_flight_time()`, `sample_typing_speed()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 23`** (5 nodes): `install_shutdown_handlers()`, `resilience.py`, `Resilienz-Patterns: Retry, Circuit Breaker, Graceful Shutdown.`, `register_shutdown_handler()`, `vision_retry()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 25`** (4 nodes): `calculate_stealth_score()`, `stealth_scorer.py`, `Stealth-Scoring nach 6 Prüfvektoren mit gewichteten Thresholds.`, `StealthResult`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 26`** (4 nodes): `get_cached_action()`, `semantic_cache.py`, `Semantic Vision Cache via diskcache.`, `set_cached_action()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 28`** (3 nodes): `get_logger()`, `logging_config.py`, `Structured Logging mit structlog.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 29`** (3 nodes): `apm.py`, `OpenTelemetry APM – Traces über alle States.`, `start_trace()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 31`** (2 nodes): `config.py`, `Zentrale Konfiguration – lädt .env und validiert alle Secrets.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 32`** (2 nodes): `conftest.py`, `pytest-Konfiguration für den stealth-runner.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 33`** (2 nodes): `__init__.py`, `Test-Suite für den stealth-runner. Führe mit: pytest tests/ -v`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 34`** (2 nodes): `__init__.py`, `stealth-runner: Vision-driven CLI orchestrator for stealth survey automation.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 36`** (1 nodes): `Der Doktor – scannt, findet, fixrt, committed.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 37`** (1 nodes): `Hauptlauf: Alle Repos → Alle Lenses → Fixen → Report.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 38`** (1 nodes): `Lens 1: Finde + fixe veraltete Claims in ALLEN .md Dateien.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 39`** (1 nodes): `Lens 6: Finde API-Keys + Passwoerter in Docs.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 40`** (1 nodes): `Lens 4: Prüfe welche SOTA Docs fehlen.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 41`** (1 nodes): `Lens 2: Finde defekte Links via md-dead-link-check (wenn installiert).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 42`** (1 nodes): `Commit + Push in ALLEN Repos.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 43`** (1 nodes): `Hybrid Loop: Screenshot (schnell) + Video (alle 5 Schritte temporal).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 44`** (1 nodes): `Hybrid Loop: Screenshot (schnell) + Video (alle 5 Schritte temporal).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `sin_survey_core – Aus dem A2A-SIN-Worker extrahierte Survey-Intelligenz.` connect `Community 7` to `Community 10`, `Community 4`?**
  _High betweenness centrality (0.136) - this node is a cross-community bridge._
- **Why does `StealthExecutor` connect `Community 0` to `Community 9`, `Community 3`, `Community 1`, `Community 6`?**
  _High betweenness centrality (0.128) - this node is a cross-community bridge._
- **Are the 18 inferred relationships involving `StealthExecutor` (e.g. with `BaseDriver` and `SkylightDriver`) actually correct?**
  _`StealthExecutor` has 18 INFERRED edges - model-reasoned connections that need verification._
- **Are the 10 inferred relationships involving `SurveyRunner` (e.g. with `stealth-runner – Orchestrator der Stealth-Triade v0.3.1.` and `StealthExecutor`) actually correct?**
  _`SurveyRunner` has 10 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `LiveOmniMonitor` (e.g. with `OmniSurveyRunner` and `Kompletter Survey-Durchlauf: Login → Loop → Abschluss.`) actually correct?**
  _`LiveOmniMonitor` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 12 inferred relationships involving `AuditLog` (e.g. with `stealth-runner – Orchestrator der Stealth-Triade v0.3.1.` and `State`) actually correct?**
  _`AuditLog` has 12 INFERRED edges - model-reasoned connections that need verification._
- **Are the 9 inferred relationships involving `VisionClient` (e.g. with `.__init__()` and `main()`) actually correct?**
  _`VisionClient` has 9 INFERRED edges - model-reasoned connections that need verification._