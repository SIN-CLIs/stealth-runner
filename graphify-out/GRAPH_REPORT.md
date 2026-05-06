# Graph Report - stealth-runner  (2026-05-06)

## Corpus Check
- 65 files · ~189,868 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 865 nodes · 1756 edges · 58 communities detected
- Extraction: 54% EXTRACTED · 46% INFERRED · 0% AMBIGUOUS · INFERRED: 806 edges (avg confidence: 0.57)
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
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
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
- [[_COMMUNITY_Community 54|Community 54]]
- [[_COMMUNITY_Community 55|Community 55]]
- [[_COMMUNITY_Community 56|Community 56]]
- [[_COMMUNITY_Community 57|Community 57]]
- [[_COMMUNITY_Community 58|Community 58]]
- [[_COMMUNITY_Community 59|Community 59]]
- [[_COMMUNITY_Community 60|Community 60]]
- [[_COMMUNITY_Community 61|Community 61]]
- [[_COMMUNITY_Community 62|Community 62]]
- [[_COMMUNITY_Community 63|Community 63]]

## God Nodes (most connected - your core abstractions)
1. `OutputGenerator` - 119 edges
2. `SemanticAnalyzer` - 105 edges
3. `CDPSession` - 79 edges
4. `OpenCodeDBPoller` - 56 edges
5. `SlideCaptchaSolver` - 43 edges
6. `CDPConnectionError` - 41 edges
7. `StealthSyncDaemon` - 41 edges
8. `CDPClient` - 35 edges
9. `TrajectoryGenerator` - 33 edges
10. `TrajectorySettings` - 31 edges

## Surprising Connections (you probably didn't know these)
- `Test Infisical utilities.` --uses--> `StealthSyncDaemon`  [INFERRED]
  stealth-sync/test_infisical_integration.py → src/stealth_sync/daemon.py
- `Test that daemon can be imported with Infisical integration.` --uses--> `StealthSyncDaemon`  [INFERRED]
  stealth-sync/test_infisical_integration.py → src/stealth_sync/daemon.py
- `Test that CLI commands are available.` --uses--> `StealthSyncDaemon`  [INFERRED]
  stealth-sync/test_infisical_integration.py → src/stealth_sync/daemon.py
- `Test that all required files exist.` --uses--> `StealthSyncDaemon`  [INFERRED]
  stealth-sync/test_infisical_integration.py → src/stealth_sync/daemon.py
- `Start the stealth-sync daemon with optional Infisical integration.` --uses--> `StealthSyncDaemon`  [INFERRED]
  stealth-sync/cli/main.py → src/stealth_sync/daemon.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.02
Nodes (117): main(), Main daemon module for stealth-sync.  This module implements the core daemon tha, Initialize Infisical integration and validate setup., Stop the daemon gracefully.                  Shuts down the scheduler and perfor, Handle shutdown signals (SIGINT, SIGTERM).                  Args:             si, Load secrets from Infisical if available., Poll for new sessions and process them.                  This is the main work f, Start the daemon and begin polling.                  This method sets up signal (+109 more)

### Community 1 - "Community 1"
Cohesion: 0.04
Nodes (75): BaseSettings, _find_chrome(), Chrome launcher with hardened flags for stealth automation.  No --enable-automat, Launch Chrome with stealth flags.          Blocks until the CDP endpoint becomes, Open a URL in the default tab (creates one if none exist).          Requires tha, Kill the Chrome process gracefully (SIGTERM → SIGKILL after 5s)., Locate the Chrome/Chromium binary on the current platform., Manages a Chrome process with stealth flags and isolated profile.      Usage: (+67 more)

### Community 2 - "Community 2"
Cohesion: 0.06
Nodes (75): ABC, BaseSolver, CDPSession, Enum, GapDetector, GapGeometry, DOM-based gap detection — 100x more accurate than vision models.  Per the CAPTCH, The measured gap between drag block and target.      Attributes:         block_b (+67 more)

### Community 3 - "Community 3"
Cohesion: 0.04
Nodes (55): Exception, patch(), Semantic analysis engine using NVIDIA NIM API for OpenCode session classificatio, Parse the classification response from NVIDIA NIM API.                  The LLM, Generate structured summary of OpenCode session messages using NVIDIA NIM., Parse the classification response from NVIDIA NIM API.                  The LLM, Generate a structured documentation unit from session analysis., Build a prompt for NVIDIA NIM to summarize OpenCode session messages. (+47 more)

### Community 4 - "Community 4"
Cohesion: 0.09
Nodes (33): _bezier(), _ease_out_quint(), Human-like Bezier mouse trajectory generator.  Produces a sequence of (t_ms, x,, A single point in the mouse trajectory.      Attributes:         t_ms: Milliseco, Ease-out quintic: fast start, smooth stop.      This matches human motor control, Cubic Bezier interpolation at parameter t ∈ [0, 1]., Generates human-like drag trajectories.      Usage:         gen = TrajectoryGene, Generate a human-like drag trajectory from start to end.          Args: (+25 more)

### Community 5 - "Community 5"
Cohesion: 0.04
Nodes (3): generate_repo(), main(), Generate all missing files for one repo.

### Community 6 - "Community 6"
Cohesion: 0.07
Nodes (36): auto_doc(), check_infisical(), monitor(), Start the stealth-sync daemon with optional Infisical integration., Check Infisical integration status., Display Infisical setup guide., setup_infisical(), summarize() (+28 more)

### Community 7 - "Community 7"
Cohesion: 0.1
Nodes (18): compile(), FlowCompiler, FlowStatus, get_status(), record_run(), dispatch(), _dispatch_step(), _execute_yaml_flow() (+10 more)

### Community 8 - "Community 8"
Cohesion: 0.17
Nodes (8): get(), is_frozen(), _load(), save(), _main_chrome_pids(), _run(), SessionManager, _wid_from_pid()

### Community 9 - "Community 9"
Cohesion: 0.12
Nodes (13): ExperienceMemory, Episodic experience memory: caches successful trajectories per (host, captcha-ty, Store a trajectory in the experience database.          Args:             record, Find successful trajectories with similar gap distance.          Args:, Get memory statistics., Close the database connection., A stored trajectory from a solved captcha.      Attributes:         host: The do, Episodic memory backed by SQLite (WAL mode for concurrent access).      Usage: (+5 more)

### Community 10 - "Community 10"
Cohesion: 0.21
Nodes (14): Toggle individual stealth-patch modules.      All default to True (maximum steal, StealthSettings, Failed to inject one or more stealth patches into the page., StealthInjectionError, Stealth injection — patches browser fingerprints before page scripts run.  Loads, build_stealth_bundle(), _load_script(), StealthInjector: ships JS patches to the browser via CDP.  Uses Page.addScriptTo (+6 more)

### Community 11 - "Community 11"
Cohesion: 0.3
Nodes (11): _balance(), _click(), _cua(), execute(), _find_bot_wid(), _find_field(), _find_idx(), SURVEY_HEYPIGGY — CUA-ONLY Survey Flow      Args:       payload : dict   — optio (+3 more)

### Community 12 - "Community 12"
Cohesion: 0.24
Nodes (5): CaptchaSolver, Convert DOM (viewport) coordinates to window coordinates, Execute drag via cua-driver CGEvent, Solve slide captcha (gc-drag-block on gc-drag-slide-bar), Generic: drag element from drag_selector to drop_selector

### Community 13 - "Community 13"
Cohesion: 0.2
Nodes (11): _ensure_keys(), get_lock_entry(), Ring 1: Signierte & unveränderliche Flow-Artefakte. Jeder kompilierte Flow wird, Boolean wrapper für Vorbedingungs-Check (Semgrep-Regel)., Gibt den flow_lock-Eintrag zurück (für Registry)., Generiert Ed25519-Schlüsselpaar falls nicht vorhanden., Signiert einen Flow und speichert .sig + flow_hash + lock.json., Prüft Signatur und Hash eines Flows.     Returns: (is_valid, reason) (+3 more)

### Community 14 - "Community 14"
Cohesion: 0.38
Nodes (11): _click(), _cua(), execute(), _find_bot_wid(), _find_idx(), _find_logged_in_heypiggy(), AUTO-GOOGLE-LOGIN — CUA-ONLY 6-Step Flow (LIVE TESTED 2026-05-05)      Args:, _run() (+3 more)

### Community 15 - "Community 15"
Cohesion: 0.6
Nodes (5): is_registered(), list_tools(), _load(), register(), _save()

### Community 16 - "Community 16"
Cohesion: 0.4
Nodes (5): get_logger(), init_telemetry(), Structured logging with structlog + optional OpenTelemetry tracing.  We keep tel, Initialize structlog once. Idempotent., Get a structlog logger. Init telemetry first if needed.

### Community 17 - "Community 17"
Cohesion: 0.47
Nodes (5): check_repo(), find_repo(), main(), SOTA Audit: check ALL required files + UPPERCASE violations., Find repo dir by name in /Users/jeremy/dev.

### Community 18 - "Community 18"
Cohesion: 0.5
Nodes (2): jitter(), rng()

### Community 19 - "Community 19"
Cohesion: 0.5
Nodes (3): load(), Embedded JS payloads for reference — legacy dispatchEvent approach.  These paylo, Load a JS payload by filename.      Args:         name: Filename (e.g., "gocaptc

### Community 20 - "Community 20"
Cohesion: 0.67
Nodes (2): main(), Main Entry Point für Survey Flow

### Community 22 - "Community 22"
Cohesion: 1.0
Nodes (1): Tests for stealth-captcha.

### Community 23 - "Community 23"
Cohesion: 1.0
Nodes (1): Embedded JavaScript payloads loaded at import time via importlib.resources.

### Community 24 - "Community 24"
Cohesion: 1.0
Nodes (1): Structured logging and OpenTelemetry integration.

### Community 30 - "Community 30"
Cohesion: 1.0
Nodes (1): Dynamically get window position and toolbar height

### Community 31 - "Community 31"
Cohesion: 1.0
Nodes (1): Convert DOM (viewport) coordinates to window coordinates

### Community 32 - "Community 32"
Cohesion: 1.0
Nodes (1): Execute drag via cua-driver CGEvent

### Community 33 - "Community 33"
Cohesion: 1.0
Nodes (1): Solve slide captcha (gc-drag-block on gc-drag-slide-bar)

### Community 34 - "Community 34"
Cohesion: 1.0
Nodes (1): Generic: drag element from drag_selector to drop_selector

### Community 35 - "Community 35"
Cohesion: 1.0
Nodes (1): Command validator that detects failure patterns and logs fixes.

### Community 36 - "Community 36"
Cohesion: 1.0
Nodes (1): ax_python — Python AX tree traversal via atomacos.  Bietet schnellen Python-basi

### Community 37 - "Community 37"
Cohesion: 1.0
Nodes (1): Gibt kompletten AX-Tree einer App als Dict zurück.

### Community 38 - "Community 38"
Cohesion: 1.0
Nodes (1): Rekursiver Walk des AX-Trees.

### Community 39 - "Community 39"
Cohesion: 1.0
Nodes (1): Findet ersten Element-Index mit passendem Label (word-boundary).      Returns:

### Community 40 - "Community 40"
Cohesion: 1.0
Nodes (1): Rekursive Suche mit Index-Zählung.

### Community 41 - "Community 41"
Cohesion: 1.0
Nodes (1): Listet alle Fenster aller laufenden Apps.

### Community 42 - "Community 42"
Cohesion: 1.0
Nodes (1): Hilfsfunktion: Alle laufenden PIDs via NSWorkspace.

### Community 43 - "Community 43"
Cohesion: 1.0
Nodes (1): Prüft ob aktuelle Seite eine Audio-Frage hat.

### Community 44 - "Community 44"
Cohesion: 1.0
Nodes (1): Audio-Frage automatisch beantworten.     Nutzt BlackHole + ffmpeg + NVIDIA Omni.

### Community 45 - "Community 45"
Cohesion: 1.0
Nodes (1): Findet passende Antwort aus Persona für eine Frage.

### Community 46 - "Community 46"
Cohesion: 1.0
Nodes (1): Erkennt Fragen und Antwortmöglichkeiten im aktuellen AX-Tree.          Filtert B

### Community 47 - "Community 47"
Cohesion: 1.0
Nodes (1): Klickt eine Antwortmöglichkeit (RadioButton/CheckBox).

### Community 48 - "Community 48"
Cohesion: 1.0
Nodes (1): Tippt eine Antwort in ein Textfeld.

### Community 49 - "Community 49"
Cohesion: 1.0
Nodes (1): Klickt den Weiter/Nächst-Button.

### Community 50 - "Community 50"
Cohesion: 1.0
Nodes (1): Prüft ob ein Survey machbar ist — via vision_gate (NVIDIA + Pixtral).          E

### Community 51 - "Community 51"
Cohesion: 1.0
Nodes (1): Macht einen Screenshot und speichert ihn.

### Community 52 - "Community 52"
Cohesion: 1.0
Nodes (1): Beantwortet eine einzelne Frage basierend auf Persona und Fragetyp.          - r

### Community 53 - "Community 53"
Cohesion: 1.0
Nodes (1): Scannt verfügbare Surveys via CDP DOM.          Returns:         list[dict]: [{i

### Community 54 - "Community 54"
Cohesion: 1.0
Nodes (1): Startet einen Survey per CDP Click.          Returns:         dict: {"success":

### Community 55 - "Community 55"
Cohesion: 1.0
Nodes (1): Bearbeitet die Vorqualifizierung mit Vision-Gate Logik-Prüfung.          1. Cook

### Community 56 - "Community 56"
Cohesion: 1.0
Nodes (1): Bearbeitet einen Survey im neuen Tab.          1. Erkennt neuen Tab (Cint, PureS

### Community 57 - "Community 57"
Cohesion: 1.0
Nodes (1): Schließt den Survey-Tab und kehrt zum HeyPiggy Dashboard zurück.

### Community 58 - "Community 58"
Cohesion: 1.0
Nodes (1): Bearbeitet das Bewertungsfeld nach dem Survey.          Schreibt kurzen Text + r

### Community 59 - "Community 59"
Cohesion: 1.0
Nodes (1): Prüft ob sich das Guthaben erhöht hat.

### Community 60 - "Community 60"
Cohesion: 1.0
Nodes (1): PUBLIC BOX API: Komplette Survey Automation.          Führt Surveys nacheinander

### Community 61 - "Community 61"
Cohesion: 1.0
Nodes (1): Public API: Verfügbare Surveys scannen.

### Community 62 - "Community 62"
Cohesion: 1.0
Nodes (1): Public API: Besten oder bestimmten Survey starten.

### Community 63 - "Community 63"
Cohesion: 1.0
Nodes (1): Public API: Vorqualifizierung durchführen.

## Knowledge Gaps
- **147 isolated node(s):** `Main Entry Point für Survey Flow`, `Ring 1: Signierte & unveränderliche Flow-Artefakte. Jeder kompilierte Flow wird`, `Generiert Ed25519-Schlüsselpaar falls nicht vorhanden.`, `Signiert einen Flow und speichert .sig + flow_hash + lock.json.`, `Prüft Signatur und Hash eines Flows.     Returns: (is_valid, reason)` (+142 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 18`** (5 nodes): `get()`, `jitter()`, `rng()`, `safe()`, `stealth_main.js`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 20`** (3 nodes): `run_survey.py`, `main()`, `Main Entry Point für Survey Flow`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 22`** (2 nodes): `__init__.py`, `Tests for stealth-captcha.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 23`** (2 nodes): `Embedded JavaScript payloads loaded at import time via importlib.resources.`, `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 24`** (2 nodes): `__init__.py`, `Structured logging and OpenTelemetry integration.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 30`** (1 nodes): `Dynamically get window position and toolbar height`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 31`** (1 nodes): `Convert DOM (viewport) coordinates to window coordinates`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 32`** (1 nodes): `Execute drag via cua-driver CGEvent`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 33`** (1 nodes): `Solve slide captcha (gc-drag-block on gc-drag-slide-bar)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 34`** (1 nodes): `Generic: drag element from drag_selector to drop_selector`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 35`** (1 nodes): `Command validator that detects failure patterns and logs fixes.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 36`** (1 nodes): `ax_python — Python AX tree traversal via atomacos.  Bietet schnellen Python-basi`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 37`** (1 nodes): `Gibt kompletten AX-Tree einer App als Dict zurück.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 38`** (1 nodes): `Rekursiver Walk des AX-Trees.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 39`** (1 nodes): `Findet ersten Element-Index mit passendem Label (word-boundary).      Returns:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 40`** (1 nodes): `Rekursive Suche mit Index-Zählung.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 41`** (1 nodes): `Listet alle Fenster aller laufenden Apps.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 42`** (1 nodes): `Hilfsfunktion: Alle laufenden PIDs via NSWorkspace.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 43`** (1 nodes): `Prüft ob aktuelle Seite eine Audio-Frage hat.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 44`** (1 nodes): `Audio-Frage automatisch beantworten.     Nutzt BlackHole + ffmpeg + NVIDIA Omni.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 45`** (1 nodes): `Findet passende Antwort aus Persona für eine Frage.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 46`** (1 nodes): `Erkennt Fragen und Antwortmöglichkeiten im aktuellen AX-Tree.          Filtert B`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 47`** (1 nodes): `Klickt eine Antwortmöglichkeit (RadioButton/CheckBox).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 48`** (1 nodes): `Tippt eine Antwort in ein Textfeld.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 49`** (1 nodes): `Klickt den Weiter/Nächst-Button.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 50`** (1 nodes): `Prüft ob ein Survey machbar ist — via vision_gate (NVIDIA + Pixtral).          E`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 51`** (1 nodes): `Macht einen Screenshot und speichert ihn.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 52`** (1 nodes): `Beantwortet eine einzelne Frage basierend auf Persona und Fragetyp.          - r`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 53`** (1 nodes): `Scannt verfügbare Surveys via CDP DOM.          Returns:         list[dict]: [{i`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 54`** (1 nodes): `Startet einen Survey per CDP Click.          Returns:         dict: {"success":`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 55`** (1 nodes): `Bearbeitet die Vorqualifizierung mit Vision-Gate Logik-Prüfung.          1. Cook`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 56`** (1 nodes): `Bearbeitet einen Survey im neuen Tab.          1. Erkennt neuen Tab (Cint, PureS`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 57`** (1 nodes): `Schließt den Survey-Tab und kehrt zum HeyPiggy Dashboard zurück.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 58`** (1 nodes): `Bearbeitet das Bewertungsfeld nach dem Survey.          Schreibt kurzen Text + r`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 59`** (1 nodes): `Prüft ob sich das Guthaben erhöht hat.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 60`** (1 nodes): `PUBLIC BOX API: Komplette Survey Automation.          Führt Surveys nacheinander`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 61`** (1 nodes): `Public API: Verfügbare Surveys scannen.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 62`** (1 nodes): `Public API: Besten oder bestimmten Survey starten.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 63`** (1 nodes): `Public API: Vorqualifizierung durchführen.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `SemanticAnalyzer` connect `Community 3` to `Community 0`?**
  _High betweenness centrality (0.353) - this node is a cross-community bridge._
- **Why does `CaptchaError` connect `Community 2` to `Community 1`, `Community 10`, `Community 3`, `Community 4`?**
  _High betweenness centrality (0.348) - this node is a cross-community bridge._
- **Are the 110 inferred relationships involving `OutputGenerator` (e.g. with `TestOutputGenerator` and `TestOutputGeneratorLogbook`) actually correct?**
  _`OutputGenerator` has 110 INFERRED edges - model-reasoned connections that need verification._
- **Are the 92 inferred relationships involving `SemanticAnalyzer` (e.g. with `TestSemanticAnalyzer` and `TestSemanticAnalyzerCategories`) actually correct?**
  _`SemanticAnalyzer` has 92 INFERRED edges - model-reasoned connections that need verification._
- **Are the 73 inferred relationships involving `CDPSession` (e.g. with `GoCaptchaSolver` and `Bridge adapter: backward-compatible GoCaptchaSolver API → new CDP engine.  The o`) actually correct?**
  _`CDPSession` has 73 INFERRED edges - model-reasoned connections that need verification._
- **Are the 49 inferred relationships involving `OpenCodeDBPoller` (e.g. with `TestIntegrationPipeline` and `Integration test suite for stealth-sync full pipeline.  Tests the complete workf`) actually correct?**
  _`OpenCodeDBPoller` has 49 INFERRED edges - model-reasoned connections that need verification._
- **Are the 35 inferred relationships involving `SlideCaptchaSolver` (e.g. with `GoCaptchaSolver` and `Bridge adapter: backward-compatible GoCaptchaSolver API → new CDP engine.  The o`) actually correct?**
  _`SlideCaptchaSolver` has 35 INFERRED edges - model-reasoned connections that need verification._