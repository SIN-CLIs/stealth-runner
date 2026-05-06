# Graph Report - stealth-runner  (2026-05-06)

## Corpus Check
- 88 files · ~172,422 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1324 nodes · 2682 edges · 111 communities detected
- Extraction: 52% EXTRACTED · 48% INFERRED · 0% AMBIGUOUS · INFERRED: 1294 edges (avg confidence: 0.56)
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
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
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
- [[_COMMUNITY_Community 64|Community 64]]
- [[_COMMUNITY_Community 65|Community 65]]
- [[_COMMUNITY_Community 66|Community 66]]
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
- [[_COMMUNITY_Community 111|Community 111]]
- [[_COMMUNITY_Community 112|Community 112]]
- [[_COMMUNITY_Community 113|Community 113]]
- [[_COMMUNITY_Community 114|Community 114]]
- [[_COMMUNITY_Community 115|Community 115]]
- [[_COMMUNITY_Community 116|Community 116]]

## God Nodes (most connected - your core abstractions)
1. `OutputGenerator` - 119 edges
2. `SemanticAnalyzer` - 105 edges
3. `CDPSession` - 79 edges
4. `BatchExecutor` - 79 edges
5. `NIMClient` - 78 edges
6. `CompactSnapshot` - 77 edges
7. `SurveyRunner` - 59 edges
8. `OpenCodeDBPoller` - 56 edges
9. `RunnerConfig` - 44 edges
10. `SlideCaptchaSolver` - 43 edges

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
Nodes (157): patch(), main(), Main daemon module for stealth-sync.  This module implements the core daemon tha, Initialize Infisical integration and validate setup., Stop the daemon gracefully.                  Shuts down the scheduler and perfor, Handle shutdown signals (SIGINT, SIGTERM).                  Args:             si, Load secrets from Infisical if available., Poll for new sessions and process them.                  This is the main work f (+149 more)

### Community 1 - "Community 1"
Cohesion: 0.03
Nodes (121): _daily_file(), _ensure_logs(), generate_summary(), log_decision(), log_earnings(), log_error(), log_session(), print_summary() (+113 more)

### Community 2 - "Community 2"
Cohesion: 0.04
Nodes (74): _find_chrome(), Chrome launcher with hardened flags for stealth automation.  No --enable-automat, Launch Chrome with stealth flags.          Blocks until the CDP endpoint becomes, Open a URL in the default tab (creates one if none exist).          Requires tha, Kill the Chrome process gracefully (SIGTERM → SIGKILL after 5s)., Locate the Chrome/Chromium binary on the current platform., Manages a Chrome process with stealth flags and isolated profile.      Usage:, StealthBrowser (+66 more)

### Community 3 - "Community 3"
Cohesion: 0.05
Nodes (72): check_nvidia_api(), cmd_legacy(), cmd_loop(), cmd_nim_survey(), cmd_scan(), cmd_snapshot(), load_profile(), main() (+64 more)

### Community 4 - "Community 4"
Cohesion: 0.06
Nodes (75): ABC, BaseSolver, CDPSession, Enum, GapDetector, GapGeometry, DOM-based gap detection — 100x more accurate than vision models.  Per the CAPTCH, The measured gap between drag block and target.      Attributes:         block_b (+67 more)

### Community 5 - "Community 5"
Cohesion: 0.05
Nodes (87): BatchExecutor, BatchResult, CDP Batch Executor — Execute survey actions via WebSocket.  Translates high-leve, Execute batch of actions.          Args:             actions: List of action dic, Execute single action., Build CDP JS string for action., Execute batched survey actions via CDP WebSocket., build_survey_prompt() (+79 more)

### Community 6 - "Community 6"
Cohesion: 0.07
Nodes (32): compile(), FlowCompiler, FlowStatus, get_status(), record_run(), _dispatch_step(), _execute_yaml_flow(), _gatekeeper_check() (+24 more)

### Community 7 - "Community 7"
Cohesion: 0.09
Nodes (33): _bezier(), _ease_out_quint(), Human-like Bezier mouse trajectory generator.  Produces a sequence of (t_ms, x,, A single point in the mouse trajectory.      Attributes:         t_ms: Milliseco, Ease-out quintic: fast start, smooth stop.      This matches human motor control, Cubic Bezier interpolation at parameter t ∈ [0, 1]., Generates human-like drag trajectories.      Usage:         gen = TrajectoryGene, Generate a human-like drag trajectory from start to end.          Args: (+25 more)

### Community 8 - "Community 8"
Cohesion: 0.04
Nodes (3): generate_repo(), main(), Generate all missing files for one repo.

### Community 9 - "Community 9"
Cohesion: 0.07
Nodes (33): BaseSettings, ExperienceMemory, Episodic experience memory: caches successful trajectories per (host, captcha-ty, Store a trajectory in the experience database.          Args:             record, Find successful trajectories with similar gap distance.          Args:, Get memory statistics., Close the database connection., A stored trajectory from a solved captcha.      Attributes:         host: The do (+25 more)

### Community 10 - "Community 10"
Cohesion: 0.06
Nodes (36): auto_doc(), check_infisical(), monitor(), Start the stealth-sync daemon with optional Infisical integration., Check Infisical integration status., Display Infisical setup guide., setup_infisical(), summarize() (+28 more)

### Community 11 - "Community 11"
Cohesion: 0.11
Nodes (25): cdp_login(), _click(), _find_google_tab(), _js(), CDP Google Login — Fallback when cua-driver AX-Tree is empty.  Uses CDP Runtime., CDP mouse click at coordinates., Execute JS via Runtime.evaluate., Find Google OAuth tab URL. (+17 more)

### Community 12 - "Community 12"
Cohesion: 0.22
Nodes (4): _main_chrome_pids(), _run(), SessionManager, _wid_from_pid()

### Community 13 - "Community 13"
Cohesion: 0.12
Nodes (10): Semantic analysis engine using NVIDIA NIM API for OpenCode session classificatio, Generate structured summary of OpenCode session messages using NVIDIA NIM., Generate a structured documentation unit from session analysis., Build a prompt for NVIDIA NIM to summarize OpenCode session messages., Create a brief summary of the session messages.                  In a production, # TODO: Replace with actual NVIDIA NIM summarization, Parse the summary response from NVIDIA NIM API.                  The LLM should, Fallback summary parser when JSON parsing fails.                  Args: (+2 more)

### Community 14 - "Community 14"
Cohesion: 0.21
Nodes (14): cdp_click(), cdp_click_button(), fill_opinion_textarea(), handle_cookie_consent(), PureSpectrum provider patterns — CAPTCHA blocked.  All current PureSpectrum surv, Recursive __ngContext__ search → dropListRef.drop()., Run full PureSpectrum preflight: cookie → ROBOT → captcha → puzzle., CDP Input.dispatchMouseEvent — real OS event (isTrusted=true). (+6 more)

### Community 15 - "Community 15"
Cohesion: 0.3
Nodes (11): _balance(), _click(), _cua(), execute(), _find_bot_wid(), _find_field(), _find_idx(), SURVEY_HEYPIGGY — CUA-ONLY Survey Flow      Args:       payload : dict   — optio (+3 more)

### Community 16 - "Community 16"
Cohesion: 0.24
Nodes (5): CaptchaSolver, Convert DOM (viewport) coordinates to window coordinates, Execute drag via cua-driver CGEvent, Solve slide captcha (gc-drag-block on gc-drag-slide-bar), Generic: drag element from drag_selector to drop_selector

### Community 17 - "Community 17"
Cohesion: 0.38
Nodes (11): _click(), _cua(), execute(), _find_bot_wid(), _find_idx(), _find_logged_in_heypiggy(), AUTO-GOOGLE-LOGIN — CUA-ONLY 6-Step Flow (LIVE TESTED 2026-05-05)      Args:, _run() (+3 more)

### Community 18 - "Community 18"
Cohesion: 0.22
Nodes (6): Parse the classification response from NVIDIA NIM API.                  The LLM, Parse the classification response from NVIDIA NIM API.                  The LLM, Classify an OpenCode session based on its messages.                  Uses NVIDIA, Classify an OpenCode session based on its messages.                  Uses NVIDIA, Build a prompt for NVIDIA NIM to classify the OpenCode session., Build a prompt for NVIDIA NIM to classify the OpenCode session.

### Community 19 - "Community 19"
Cohesion: 0.25
Nodes (7): check_pending_tasks(), delegate_task(), OpenCode CLI Bridge — delegate coding tasks to opencode.  Survey-cli is NOT a co, Delegate a coding task to opencode cli.      Creates a temporary task file and i, Check for pending tasks that were dispatched., Submit a GitHub issue via gh CLI.      Used to report bugs or request features d, submit_issue()

### Community 20 - "Community 20"
Cohesion: 0.32
Nodes (7): _check_logged_in(), execute(), _navigate_and_wait(), Google OAuth login via CDP WebSocket.  Uses Keychain auto-fill. No passwords sto, Check if logged in to heypiggy dashboard., Execute full Google OAuth login flow.      Returns:         {"status": "ok", "pi, Navigate to URL and wait for page load.

### Community 21 - "Community 21"
Cohesion: 0.6
Nodes (5): is_registered(), list_tools(), _load(), register(), _save()

### Community 22 - "Community 22"
Cohesion: 0.47
Nodes (5): check_repo(), find_repo(), main(), SOTA Audit: check ALL required files + UPPERCASE violations., Find repo dir by name in /Users/jeremy/dev.

### Community 23 - "Community 23"
Cohesion: 0.5
Nodes (2): jitter(), rng()

### Community 24 - "Community 24"
Cohesion: 0.5
Nodes (3): load(), Embedded JS payloads for reference — legacy dispatchEvent approach.  These paylo, Load a JS payload by filename.      Args:         name: Filename (e.g., "gocaptc

### Community 25 - "Community 25"
Cohesion: 0.5
Nodes (3): get_action_for_question(), Qualtrics provider patterns.  Key differences from other providers:   - .NextBut, Match a question to profile data.      Returns:         {"index": int, "value":

### Community 27 - "Community 27"
Cohesion: 1.0
Nodes (1): Tests for stealth-captcha.

### Community 28 - "Community 28"
Cohesion: 1.0
Nodes (1): Embedded JavaScript payloads loaded at import time via importlib.resources.

### Community 29 - "Community 29"
Cohesion: 1.0
Nodes (1): Structured logging and OpenTelemetry integration.

### Community 30 - "Community 30"
Cohesion: 1.0
Nodes (1): Strat7 Audiences provider patterns.  Key patterns:   - .bsbutton grid for consen

### Community 31 - "Community 31"
Cohesion: 1.0
Nodes (1): Provider-specific survey patterns.  Each provider module exports:   - detect(pag

### Community 32 - "Community 32"
Cohesion: 1.0
Nodes (1): TolunaStart provider patterns.  Key patterns:   - .cf-radio for single select (u

### Community 38 - "Community 38"
Cohesion: 1.0
Nodes (1): Read page text for completion check.

### Community 39 - "Community 39"
Cohesion: 1.0
Nodes (1): Read the current page text for completion detection.

### Community 40 - "Community 40"
Cohesion: 1.0
Nodes (1): Check if survey is completed.

### Community 41 - "Community 41"
Cohesion: 1.0
Nodes (1): Ask Nemotron to decide the next batch of actions.          Args:             sna

### Community 42 - "Community 42"
Cohesion: 1.0
Nodes (1): Parse the LLM response into a list of actions.          Handles:         - Pure

### Community 43 - "Community 43"
Cohesion: 1.0
Nodes (1): Extract question texts from elements.

### Community 44 - "Community 44"
Cohesion: 1.0
Nodes (1): Detect survey progress if visible.

### Community 45 - "Community 45"
Cohesion: 1.0
Nodes (1): Detect survey provider from URL.

### Community 46 - "Community 46"
Cohesion: 1.0
Nodes (1): Navigate to URL and wait for page load.

### Community 47 - "Community 47"
Cohesion: 1.0
Nodes (1): Extract base64 captcha image from PureSpectrum page via CDP.      Returns:

### Community 48 - "Community 48"
Cohesion: 1.0
Nodes (1): Build token-efficient prompt for Nemotron.

### Community 49 - "Community 49"
Cohesion: 1.0
Nodes (1): Parse LLM response into action list.

### Community 50 - "Community 50"
Cohesion: 1.0
Nodes (1): NVIDIA Nemotron 3 Omni client for survey decisions.

### Community 51 - "Community 51"
Cohesion: 1.0
Nodes (1): Decide next batch actions.          Args:             snapshot: Dict from snapsh

### Community 52 - "Community 52"
Cohesion: 1.0
Nodes (1): Simple auto-pilot fallback.

### Community 53 - "Community 53"
Cohesion: 1.0
Nodes (1): Get or create default NIM client.

### Community 54 - "Community 54"
Cohesion: 1.0
Nodes (1): Safely kill ONLY bot Chrome processes.

### Community 55 - "Community 55"
Cohesion: 1.0
Nodes (1): Get survey URL from CPX API using live details_url.

### Community 56 - "Community 56"
Cohesion: 1.0
Nodes (1): Send captcha image to NVIDIA NIM Vision API for OCR.      Args:         data_url

### Community 57 - "Community 57"
Cohesion: 1.0
Nodes (1): Find the captcha input field on the page.

### Community 58 - "Community 58"
Cohesion: 1.0
Nodes (1): Fill captcha answer and click submit.

### Community 59 - "Community 59"
Cohesion: 1.0
Nodes (1): Full PureSpectrum captcha solving pipeline.      1. Extract captcha image     2.

### Community 60 - "Community 60"
Cohesion: 1.0
Nodes (1): Click 'Alle akzeptieren' or similar consent button.

### Community 61 - "Community 61"
Cohesion: 1.0
Nodes (1): Fill the opinion textarea with ROBOT keyword.      PureSpectrum requires the wor

### Community 62 - "Community 62"
Cohesion: 1.0
Nodes (1): Solve PureSpectrum drag-drop puzzle via Angular __ngContext__.      Recursively

### Community 63 - "Community 63"
Cohesion: 1.0
Nodes (1): Extract base64 captcha image from PureSpectrum page via CDP.      Returns:

### Community 64 - "Community 64"
Cohesion: 1.0
Nodes (1): Send captcha image to NVIDIA NIM Vision API for OCR.      Args:         data_url

### Community 65 - "Community 65"
Cohesion: 1.0
Nodes (1): Find the captcha input field on the page.

### Community 66 - "Community 66"
Cohesion: 1.0
Nodes (1): Fill captcha answer and click submit.

### Community 67 - "Community 67"
Cohesion: 1.0
Nodes (1): Full PureSpectrum captcha solving pipeline.      1. Extract captcha image     2.

### Community 68 - "Community 68"
Cohesion: 1.0
Nodes (1): Click 'Alle akzeptieren' or similar consent button.

### Community 69 - "Community 69"
Cohesion: 1.0
Nodes (1): Fill the opinion textarea with ROBOT keyword.      PureSpectrum requires the wor

### Community 70 - "Community 70"
Cohesion: 1.0
Nodes (1): Pretty-print filtered survey results.

### Community 71 - "Community 71"
Cohesion: 1.0
Nodes (1): Full scan: connect → extract IDs → filter → print.      Returns:         List of

### Community 72 - "Community 72"
Cohesion: 1.0
Nodes (1): Read page innerText via CDP.

### Community 73 - "Community 73"
Cohesion: 1.0
Nodes (1): Read current balance from dashboard.

### Community 74 - "Community 74"
Cohesion: 1.0
Nodes (1): Find all tabs in bot Chrome.

### Community 75 - "Community 75"
Cohesion: 1.0
Nodes (1): Find WebSocket URL for a heypiggy dashboard tab.

### Community 76 - "Community 76"
Cohesion: 1.0
Nodes (1): Find first non-dashboard survey tab.

### Community 77 - "Community 77"
Cohesion: 1.0
Nodes (1): Get WebSocket URL for a specific tab ID.

### Community 78 - "Community 78"
Cohesion: 1.0
Nodes (1): Check if bot Chrome is running with CDP enabled.

### Community 79 - "Community 79"
Cohesion: 1.0
Nodes (1): Launch Chrome via playstealth or raw subprocess.

### Community 80 - "Community 80"
Cohesion: 1.0
Nodes (1): Safely kill ONLY bot Chrome processes.

### Community 81 - "Community 81"
Cohesion: 1.0
Nodes (1): Get survey URL from CPX API.

### Community 82 - "Community 82"
Cohesion: 1.0
Nodes (1): Get full survey details from CPX API.

### Community 83 - "Community 83"
Cohesion: 1.0
Nodes (1): Dynamically get window position and toolbar height

### Community 84 - "Community 84"
Cohesion: 1.0
Nodes (1): Convert DOM (viewport) coordinates to window coordinates

### Community 85 - "Community 85"
Cohesion: 1.0
Nodes (1): Execute drag via cua-driver CGEvent

### Community 86 - "Community 86"
Cohesion: 1.0
Nodes (1): Solve slide captcha (gc-drag-block on gc-drag-slide-bar)

### Community 87 - "Community 87"
Cohesion: 1.0
Nodes (1): Generic: drag element from drag_selector to drop_selector

### Community 88 - "Community 88"
Cohesion: 1.0
Nodes (1): Command validator that detects failure patterns and logs fixes.

### Community 89 - "Community 89"
Cohesion: 1.0
Nodes (1): ax_python — Python AX tree traversal via atomacos.  Bietet schnellen Python-basi

### Community 90 - "Community 90"
Cohesion: 1.0
Nodes (1): Gibt kompletten AX-Tree einer App als Dict zurück.

### Community 91 - "Community 91"
Cohesion: 1.0
Nodes (1): Rekursiver Walk des AX-Trees.

### Community 92 - "Community 92"
Cohesion: 1.0
Nodes (1): Findet ersten Element-Index mit passendem Label (word-boundary).      Returns:

### Community 93 - "Community 93"
Cohesion: 1.0
Nodes (1): Rekursive Suche mit Index-Zählung.

### Community 94 - "Community 94"
Cohesion: 1.0
Nodes (1): Listet alle Fenster aller laufenden Apps.

### Community 95 - "Community 95"
Cohesion: 1.0
Nodes (1): Hilfsfunktion: Alle laufenden PIDs via NSWorkspace.

### Community 96 - "Community 96"
Cohesion: 1.0
Nodes (1): Prüft ob aktuelle Seite eine Audio-Frage hat.

### Community 97 - "Community 97"
Cohesion: 1.0
Nodes (1): Audio-Frage automatisch beantworten.     Nutzt BlackHole + ffmpeg + NVIDIA Omni.

### Community 98 - "Community 98"
Cohesion: 1.0
Nodes (1): Findet passende Antwort aus Persona für eine Frage.

### Community 99 - "Community 99"
Cohesion: 1.0
Nodes (1): Erkennt Fragen und Antwortmöglichkeiten im aktuellen AX-Tree.          Filtert B

### Community 100 - "Community 100"
Cohesion: 1.0
Nodes (1): Klickt eine Antwortmöglichkeit (RadioButton/CheckBox).

### Community 101 - "Community 101"
Cohesion: 1.0
Nodes (1): Tippt eine Antwort in ein Textfeld.

### Community 102 - "Community 102"
Cohesion: 1.0
Nodes (1): Klickt den Weiter/Nächst-Button.

### Community 103 - "Community 103"
Cohesion: 1.0
Nodes (1): Prüft ob ein Survey machbar ist — via vision_gate (NVIDIA + Pixtral).          E

### Community 104 - "Community 104"
Cohesion: 1.0
Nodes (1): Macht einen Screenshot und speichert ihn.

### Community 105 - "Community 105"
Cohesion: 1.0
Nodes (1): Beantwortet eine einzelne Frage basierend auf Persona und Fragetyp.          - r

### Community 106 - "Community 106"
Cohesion: 1.0
Nodes (1): Scannt verfügbare Surveys via CDP DOM.          Returns:         list[dict]: [{i

### Community 107 - "Community 107"
Cohesion: 1.0
Nodes (1): Startet einen Survey per CDP Click.          Returns:         dict: {"success":

### Community 108 - "Community 108"
Cohesion: 1.0
Nodes (1): Bearbeitet die Vorqualifizierung mit Vision-Gate Logik-Prüfung.          1. Cook

### Community 109 - "Community 109"
Cohesion: 1.0
Nodes (1): Bearbeitet einen Survey im neuen Tab.          1. Erkennt neuen Tab (Cint, PureS

### Community 110 - "Community 110"
Cohesion: 1.0
Nodes (1): Schließt den Survey-Tab und kehrt zum HeyPiggy Dashboard zurück.

### Community 111 - "Community 111"
Cohesion: 1.0
Nodes (1): Bearbeitet das Bewertungsfeld nach dem Survey.          Schreibt kurzen Text + r

### Community 112 - "Community 112"
Cohesion: 1.0
Nodes (1): Prüft ob sich das Guthaben erhöht hat.

### Community 113 - "Community 113"
Cohesion: 1.0
Nodes (1): PUBLIC BOX API: Komplette Survey Automation.          Führt Surveys nacheinander

### Community 114 - "Community 114"
Cohesion: 1.0
Nodes (1): Public API: Verfügbare Surveys scannen.

### Community 115 - "Community 115"
Cohesion: 1.0
Nodes (1): Public API: Besten oder bestimmten Survey starten.

### Community 116 - "Community 116"
Cohesion: 1.0
Nodes (1): Public API: Vorqualifizierung durchführen.

## Knowledge Gaps
- **290 isolated node(s):** `Ring 1: Signierte & unveränderliche Flow-Artefakte. Jeder kompilierte Flow wird`, `Generiert Ed25519-Schlüsselpaar falls nicht vorhanden.`, `Signiert einen Flow und speichert .sig + flow_hash + lock.json.`, `Prüft Signatur und Hash eines Flows.     Returns: (is_valid, reason)`, `Boolean wrapper für Vorbedingungs-Check (Semgrep-Regel).` (+285 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 23`** (5 nodes): `get()`, `jitter()`, `rng()`, `safe()`, `stealth_main.js`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 27`** (2 nodes): `__init__.py`, `Tests for stealth-captcha.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 28`** (2 nodes): `Embedded JavaScript payloads loaded at import time via importlib.resources.`, `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 29`** (2 nodes): `__init__.py`, `Structured logging and OpenTelemetry integration.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 30`** (2 nodes): `Strat7 Audiences provider patterns.  Key patterns:   - .bsbutton grid for consen`, `strat7.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 31`** (2 nodes): `Provider-specific survey patterns.  Each provider module exports:   - detect(pag`, `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 32`** (2 nodes): `TolunaStart provider patterns.  Key patterns:   - .cf-radio for single select (u`, `toluna.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 38`** (1 nodes): `Read page text for completion check.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 39`** (1 nodes): `Read the current page text for completion detection.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 40`** (1 nodes): `Check if survey is completed.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 41`** (1 nodes): `Ask Nemotron to decide the next batch of actions.          Args:             sna`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 42`** (1 nodes): `Parse the LLM response into a list of actions.          Handles:         - Pure`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 43`** (1 nodes): `Extract question texts from elements.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 44`** (1 nodes): `Detect survey progress if visible.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 45`** (1 nodes): `Detect survey provider from URL.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 46`** (1 nodes): `Navigate to URL and wait for page load.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 47`** (1 nodes): `Extract base64 captcha image from PureSpectrum page via CDP.      Returns:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 48`** (1 nodes): `Build token-efficient prompt for Nemotron.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 49`** (1 nodes): `Parse LLM response into action list.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 50`** (1 nodes): `NVIDIA Nemotron 3 Omni client for survey decisions.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 51`** (1 nodes): `Decide next batch actions.          Args:             snapshot: Dict from snapsh`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 52`** (1 nodes): `Simple auto-pilot fallback.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 53`** (1 nodes): `Get or create default NIM client.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 54`** (1 nodes): `Safely kill ONLY bot Chrome processes.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 55`** (1 nodes): `Get survey URL from CPX API using live details_url.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 56`** (1 nodes): `Send captcha image to NVIDIA NIM Vision API for OCR.      Args:         data_url`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 57`** (1 nodes): `Find the captcha input field on the page.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 58`** (1 nodes): `Fill captcha answer and click submit.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 59`** (1 nodes): `Full PureSpectrum captcha solving pipeline.      1. Extract captcha image     2.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 60`** (1 nodes): `Click 'Alle akzeptieren' or similar consent button.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 61`** (1 nodes): `Fill the opinion textarea with ROBOT keyword.      PureSpectrum requires the wor`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 62`** (1 nodes): `Solve PureSpectrum drag-drop puzzle via Angular __ngContext__.      Recursively`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 63`** (1 nodes): `Extract base64 captcha image from PureSpectrum page via CDP.      Returns:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 64`** (1 nodes): `Send captcha image to NVIDIA NIM Vision API for OCR.      Args:         data_url`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 65`** (1 nodes): `Find the captcha input field on the page.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 66`** (1 nodes): `Fill captcha answer and click submit.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 67`** (1 nodes): `Full PureSpectrum captcha solving pipeline.      1. Extract captcha image     2.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 68`** (1 nodes): `Click 'Alle akzeptieren' or similar consent button.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 69`** (1 nodes): `Fill the opinion textarea with ROBOT keyword.      PureSpectrum requires the wor`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 70`** (1 nodes): `Pretty-print filtered survey results.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 71`** (1 nodes): `Full scan: connect → extract IDs → filter → print.      Returns:         List of`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 72`** (1 nodes): `Read page innerText via CDP.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 73`** (1 nodes): `Read current balance from dashboard.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 74`** (1 nodes): `Find all tabs in bot Chrome.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 75`** (1 nodes): `Find WebSocket URL for a heypiggy dashboard tab.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 76`** (1 nodes): `Find first non-dashboard survey tab.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 77`** (1 nodes): `Get WebSocket URL for a specific tab ID.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 78`** (1 nodes): `Check if bot Chrome is running with CDP enabled.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 79`** (1 nodes): `Launch Chrome via playstealth or raw subprocess.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 80`** (1 nodes): `Safely kill ONLY bot Chrome processes.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 81`** (1 nodes): `Get survey URL from CPX API.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 82`** (1 nodes): `Get full survey details from CPX API.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 83`** (1 nodes): `Dynamically get window position and toolbar height`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 84`** (1 nodes): `Convert DOM (viewport) coordinates to window coordinates`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 85`** (1 nodes): `Execute drag via cua-driver CGEvent`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 86`** (1 nodes): `Solve slide captcha (gc-drag-block on gc-drag-slide-bar)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 87`** (1 nodes): `Generic: drag element from drag_selector to drop_selector`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 88`** (1 nodes): `Command validator that detects failure patterns and logs fixes.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 89`** (1 nodes): `ax_python — Python AX tree traversal via atomacos.  Bietet schnellen Python-basi`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 90`** (1 nodes): `Gibt kompletten AX-Tree einer App als Dict zurück.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 91`** (1 nodes): `Rekursiver Walk des AX-Trees.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 92`** (1 nodes): `Findet ersten Element-Index mit passendem Label (word-boundary).      Returns:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 93`** (1 nodes): `Rekursive Suche mit Index-Zählung.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 94`** (1 nodes): `Listet alle Fenster aller laufenden Apps.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 95`** (1 nodes): `Hilfsfunktion: Alle laufenden PIDs via NSWorkspace.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 96`** (1 nodes): `Prüft ob aktuelle Seite eine Audio-Frage hat.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 97`** (1 nodes): `Audio-Frage automatisch beantworten.     Nutzt BlackHole + ffmpeg + NVIDIA Omni.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 98`** (1 nodes): `Findet passende Antwort aus Persona für eine Frage.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 99`** (1 nodes): `Erkennt Fragen und Antwortmöglichkeiten im aktuellen AX-Tree.          Filtert B`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 100`** (1 nodes): `Klickt eine Antwortmöglichkeit (RadioButton/CheckBox).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 101`** (1 nodes): `Tippt eine Antwort in ein Textfeld.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 102`** (1 nodes): `Klickt den Weiter/Nächst-Button.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 103`** (1 nodes): `Prüft ob ein Survey machbar ist — via vision_gate (NVIDIA + Pixtral).          E`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 104`** (1 nodes): `Macht einen Screenshot und speichert ihn.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 105`** (1 nodes): `Beantwortet eine einzelne Frage basierend auf Persona und Fragetyp.          - r`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 106`** (1 nodes): `Scannt verfügbare Surveys via CDP DOM.          Returns:         list[dict]: [{i`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 107`** (1 nodes): `Startet einen Survey per CDP Click.          Returns:         dict: {"success":`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 108`** (1 nodes): `Bearbeitet die Vorqualifizierung mit Vision-Gate Logik-Prüfung.          1. Cook`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 109`** (1 nodes): `Bearbeitet einen Survey im neuen Tab.          1. Erkennt neuen Tab (Cint, PureS`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 110`** (1 nodes): `Schließt den Survey-Tab und kehrt zum HeyPiggy Dashboard zurück.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 111`** (1 nodes): `Bearbeitet das Bewertungsfeld nach dem Survey.          Schreibt kurzen Text + r`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 112`** (1 nodes): `Prüft ob sich das Guthaben erhöht hat.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 113`** (1 nodes): `PUBLIC BOX API: Komplette Survey Automation.          Führt Surveys nacheinander`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 114`** (1 nodes): `Public API: Verfügbare Surveys scannen.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 115`** (1 nodes): `Public API: Besten oder bestimmten Survey starten.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 116`** (1 nodes): `Public API: Vorqualifizierung durchführen.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `CaptchaError` connect `Community 4` to `Community 9`, `Community 10`, `Community 2`, `Community 7`?**
  _High betweenness centrality (0.331) - this node is a cross-community bridge._
- **Why does `SemanticAnalyzer` connect `Community 0` to `Community 18`, `Community 13`?**
  _High betweenness centrality (0.314) - this node is a cross-community bridge._
- **Why does `create_tab()` connect `Community 1` to `Community 2`?**
  _High betweenness centrality (0.296) - this node is a cross-community bridge._
- **Are the 110 inferred relationships involving `OutputGenerator` (e.g. with `TestOutputGenerator` and `TestOutputGeneratorLogbook`) actually correct?**
  _`OutputGenerator` has 110 INFERRED edges - model-reasoned connections that need verification._
- **Are the 92 inferred relationships involving `SemanticAnalyzer` (e.g. with `TestSemanticAnalyzer` and `TestSemanticAnalyzerCategories`) actually correct?**
  _`SemanticAnalyzer` has 92 INFERRED edges - model-reasoned connections that need verification._
- **Are the 73 inferred relationships involving `CDPSession` (e.g. with `GoCaptchaSolver` and `Bridge adapter: backward-compatible GoCaptchaSolver API → new CDP engine.  The o`) actually correct?**
  _`CDPSession` has 73 INFERRED edges - model-reasoned connections that need verification._
- **Are the 73 inferred relationships involving `BatchExecutor` (e.g. with `SurveyResult` and `RunnerConfig`) actually correct?**
  _`BatchExecutor` has 73 INFERRED edges - model-reasoned connections that need verification._