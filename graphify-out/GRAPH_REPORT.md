# Graph Report - stealth-runner  (2026-05-05)

## Corpus Check
- 34 files · ~104,635 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 533 nodes · 888 edges · 45 communities detected
- Extraction: 66% EXTRACTED · 34% INFERRED · 0% AMBIGUOUS · INFERRED: 299 edges (avg confidence: 0.6)
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

## God Nodes (most connected - your core abstractions)
1. `OutputGenerator` - 119 edges
2. `SemanticAnalyzer` - 105 edges
3. `OpenCodeDBPoller` - 56 edges
4. `StealthSyncDaemon` - 41 edges
5. `FlowCompiler` - 19 edges
6. `SessionManager` - 19 edges
7. `TestOutputGenerator` - 17 edges
8. `TestSemanticAnalyzer` - 16 edges
9. `TestSemanticAnalyzerCategories` - 15 edges
10. `TestOutputGeneratorLogbook` - 14 edges

## Surprising Connections (you probably didn't know these)
- `Test Infisical utilities.` --uses--> `StealthSyncDaemon`  [INFERRED]
  stealth-sync/test_infisical_integration.py → src/stealth_sync/daemon.py
- `Test suite for OutputGenerator module.  Tests the output generation functionalit` --uses--> `OutputGenerator`  [INFERRED]
  tests/test_output_generator.py → src/stealth_sync/output_generator.py
- `Test suite for OutputGenerator class.` --uses--> `OutputGenerator`  [INFERRED]
  tests/test_output_generator.py → src/stealth_sync/output_generator.py
- `Test initialization with default output directory.` --uses--> `OutputGenerator`  [INFERRED]
  tests/test_output_generator.py → src/stealth_sync/output_generator.py
- `Test initialization with custom output directory.` --uses--> `OutputGenerator`  [INFERRED]
  tests/test_output_generator.py → src/stealth_sync/output_generator.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.04
Nodes (50): OutputGenerator, Output generators for documentation units.  This module handles generating struc, Update changelog with a new entry for this session.                  Creates a M, Build a Markdown changelog entry.                  Creates a formatted Markdown, Update the central logbook with a session reference.                  Appends a, Generates structured documentation from session analysis.          This class cr, Initialize the output generator.                  Args:             output_dir:, Generate a YAML documentation file for a session.                  Creates a YAM (+42 more)

### Community 1 - "Community 1"
Cohesion: 0.04
Nodes (49): dispatch(), Exception, Semantic analysis engine using NVIDIA NIM API for OpenCode session classificatio, Generate structured summary of OpenCode session messages using NVIDIA NIM., Generate a structured documentation unit from session analysis., Build a prompt for NVIDIA NIM to summarize OpenCode session messages., Analyzes OpenCode session messages and classifies them using NVIDIA NIM API., Create a brief summary of the session messages.                  In a production (+41 more)

### Community 2 - "Community 2"
Cohesion: 0.05
Nodes (38): Handle shutdown signals (SIGINT, SIGTERM).                  Args:             si, Load secrets from Infisical if available., Poll for new sessions and process them.                  This is the main work f, Process a single OpenCode session.                  Fetches messages, classifies, Handle shutdown signals (SIGINT, SIGTERM).                  Args:             si, Poll for new sessions and process them.                  This is the main work f, Process a single OpenCode session.                  Fetches messages, classifies, Initialize the stealth-sync daemon.                  Args:             db_path: (+30 more)

### Community 3 - "Community 3"
Cohesion: 0.05
Nodes (43): auto_doc(), check_infisical(), monitor(), Start the stealth-sync daemon with optional Infisical integration., Check Infisical integration status., Display Infisical setup guide., setup_infisical(), summarize() (+35 more)

### Community 4 - "Community 4"
Cohesion: 0.04
Nodes (3): generate_repo(), main(), Generate all missing files for one repo.

### Community 5 - "Community 5"
Cohesion: 0.09
Nodes (21): compile(), FlowCompiler, FlowStatus, get_status(), record_run(), _dispatch_step(), _execute_yaml_flow(), _gatekeeper_check() (+13 more)

### Community 6 - "Community 6"
Cohesion: 0.13
Nodes (22): Initialize Infisical integration and validate setup., check_infisical_integration(), find_infisical_project_file(), InfisicalNotInstalledError, InfisicalProjectNotFoundError, InfisicalValidationError, is_infisical_cli_installed(), load_infisical_secrets() (+14 more)

### Community 7 - "Community 7"
Cohesion: 0.22
Nodes (4): _main_chrome_pids(), _run(), SessionManager, _wid_from_pid()

### Community 8 - "Community 8"
Cohesion: 0.3
Nodes (11): _balance(), _click(), _cua(), execute(), _find_bot_wid(), _find_field(), _find_idx(), SURVEY_HEYPIGGY — CUA-ONLY Survey Flow      Args:       payload : dict   — optio (+3 more)

### Community 9 - "Community 9"
Cohesion: 0.22
Nodes (6): CaptchaSolver, Dynamically get window position and toolbar height, Convert DOM (viewport) coordinates to window coordinates, Execute drag via cua-driver CGEvent, Solve slide captcha (gc-drag-block on gc-drag-slide-bar), Generic: drag element from drag_selector to drop_selector

### Community 10 - "Community 10"
Cohesion: 0.2
Nodes (11): _ensure_keys(), get_lock_entry(), Ring 1: Signierte & unveränderliche Flow-Artefakte. Jeder kompilierte Flow wird, Boolean wrapper für Vorbedingungs-Check (Semgrep-Regel)., Gibt den flow_lock-Eintrag zurück (für Registry)., Generiert Ed25519-Schlüsselpaar falls nicht vorhanden., Signiert einen Flow und speichert .sig + flow_hash + lock.json., Prüft Signatur und Hash eines Flows.     Returns: (is_valid, reason) (+3 more)

### Community 11 - "Community 11"
Cohesion: 0.38
Nodes (11): _click(), _cua(), execute(), _find_bot_wid(), _find_idx(), _find_logged_in_heypiggy(), AUTO-GOOGLE-LOGIN — CUA-ONLY 6-Step Flow (LIVE TESTED 2026-05-05)      Args:, _run() (+3 more)

### Community 12 - "Community 12"
Cohesion: 0.22
Nodes (6): Parse the classification response from NVIDIA NIM API.                  The LLM, Parse the classification response from NVIDIA NIM API.                  The LLM, Classify an OpenCode session based on its messages.                  Uses NVIDIA, Classify an OpenCode session based on its messages.                  Uses NVIDIA, Build a prompt for NVIDIA NIM to classify the OpenCode session., Build a prompt for NVIDIA NIM to classify the OpenCode session.

### Community 13 - "Community 13"
Cohesion: 0.6
Nodes (5): is_registered(), list_tools(), _load(), register(), _save()

### Community 14 - "Community 14"
Cohesion: 0.47
Nodes (5): check_repo(), find_repo(), main(), SOTA Audit: check ALL required files + UPPERCASE violations., Find repo dir by name in /Users/jeremy/dev.

### Community 15 - "Community 15"
Cohesion: 0.67
Nodes (2): main(), Main Entry Point für Survey Flow

### Community 21 - "Community 21"
Cohesion: 1.0
Nodes (1): Command validator that detects failure patterns and logs fixes.

### Community 22 - "Community 22"
Cohesion: 1.0
Nodes (1): ax_python — Python AX tree traversal via atomacos.  Bietet schnellen Python-basi

### Community 23 - "Community 23"
Cohesion: 1.0
Nodes (1): Gibt kompletten AX-Tree einer App als Dict zurück.

### Community 24 - "Community 24"
Cohesion: 1.0
Nodes (1): Rekursiver Walk des AX-Trees.

### Community 25 - "Community 25"
Cohesion: 1.0
Nodes (1): Findet ersten Element-Index mit passendem Label (word-boundary).      Returns:

### Community 26 - "Community 26"
Cohesion: 1.0
Nodes (1): Rekursive Suche mit Index-Zählung.

### Community 27 - "Community 27"
Cohesion: 1.0
Nodes (1): Listet alle Fenster aller laufenden Apps.

### Community 28 - "Community 28"
Cohesion: 1.0
Nodes (1): Hilfsfunktion: Alle laufenden PIDs via NSWorkspace.

### Community 29 - "Community 29"
Cohesion: 1.0
Nodes (1): Prüft ob aktuelle Seite eine Audio-Frage hat.

### Community 30 - "Community 30"
Cohesion: 1.0
Nodes (1): Audio-Frage automatisch beantworten.     Nutzt BlackHole + ffmpeg + NVIDIA Omni.

### Community 31 - "Community 31"
Cohesion: 1.0
Nodes (1): Findet passende Antwort aus Persona für eine Frage.

### Community 32 - "Community 32"
Cohesion: 1.0
Nodes (1): Erkennt Fragen und Antwortmöglichkeiten im aktuellen AX-Tree.          Filtert B

### Community 33 - "Community 33"
Cohesion: 1.0
Nodes (1): Klickt eine Antwortmöglichkeit (RadioButton/CheckBox).

### Community 34 - "Community 34"
Cohesion: 1.0
Nodes (1): Tippt eine Antwort in ein Textfeld.

### Community 35 - "Community 35"
Cohesion: 1.0
Nodes (1): Klickt den Weiter/Nächst-Button.

### Community 36 - "Community 36"
Cohesion: 1.0
Nodes (1): Prüft ob ein Survey machbar ist — via vision_gate (NVIDIA + Pixtral).          E

### Community 37 - "Community 37"
Cohesion: 1.0
Nodes (1): Macht einen Screenshot und speichert ihn.

### Community 38 - "Community 38"
Cohesion: 1.0
Nodes (1): Beantwortet eine einzelne Frage basierend auf Persona und Fragetyp.          - r

### Community 39 - "Community 39"
Cohesion: 1.0
Nodes (1): Scannt verfügbare Surveys via CDP DOM.          Returns:         list[dict]: [{i

### Community 40 - "Community 40"
Cohesion: 1.0
Nodes (1): Startet einen Survey per CDP Click.          Returns:         dict: {"success":

### Community 41 - "Community 41"
Cohesion: 1.0
Nodes (1): Bearbeitet die Vorqualifizierung mit Vision-Gate Logik-Prüfung.          1. Cook

### Community 42 - "Community 42"
Cohesion: 1.0
Nodes (1): Bearbeitet einen Survey im neuen Tab.          1. Erkennt neuen Tab (Cint, PureS

### Community 43 - "Community 43"
Cohesion: 1.0
Nodes (1): Schließt den Survey-Tab und kehrt zum HeyPiggy Dashboard zurück.

### Community 44 - "Community 44"
Cohesion: 1.0
Nodes (1): Bearbeitet das Bewertungsfeld nach dem Survey.          Schreibt kurzen Text + r

### Community 45 - "Community 45"
Cohesion: 1.0
Nodes (1): Prüft ob sich das Guthaben erhöht hat.

### Community 46 - "Community 46"
Cohesion: 1.0
Nodes (1): PUBLIC BOX API: Komplette Survey Automation.          Führt Surveys nacheinander

### Community 47 - "Community 47"
Cohesion: 1.0
Nodes (1): Public API: Verfügbare Surveys scannen.

### Community 48 - "Community 48"
Cohesion: 1.0
Nodes (1): Public API: Besten oder bestimmten Survey starten.

### Community 49 - "Community 49"
Cohesion: 1.0
Nodes (1): Public API: Vorqualifizierung durchführen.

## Knowledge Gaps
- **115 isolated node(s):** `Main Entry Point für Survey Flow`, `Ring 1: Signierte & unveränderliche Flow-Artefakte. Jeder kompilierte Flow wird`, `Generiert Ed25519-Schlüsselpaar falls nicht vorhanden.`, `Signiert einen Flow und speichert .sig + flow_hash + lock.json.`, `Prüft Signatur und Hash eines Flows.     Returns: (is_valid, reason)` (+110 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 15`** (3 nodes): `run_survey.py`, `main()`, `Main Entry Point für Survey Flow`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 21`** (1 nodes): `Command validator that detects failure patterns and logs fixes.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 22`** (1 nodes): `ax_python — Python AX tree traversal via atomacos.  Bietet schnellen Python-basi`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 23`** (1 nodes): `Gibt kompletten AX-Tree einer App als Dict zurück.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 24`** (1 nodes): `Rekursiver Walk des AX-Trees.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 25`** (1 nodes): `Findet ersten Element-Index mit passendem Label (word-boundary).      Returns:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 26`** (1 nodes): `Rekursive Suche mit Index-Zählung.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 27`** (1 nodes): `Listet alle Fenster aller laufenden Apps.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 28`** (1 nodes): `Hilfsfunktion: Alle laufenden PIDs via NSWorkspace.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 29`** (1 nodes): `Prüft ob aktuelle Seite eine Audio-Frage hat.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 30`** (1 nodes): `Audio-Frage automatisch beantworten.     Nutzt BlackHole + ffmpeg + NVIDIA Omni.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 31`** (1 nodes): `Findet passende Antwort aus Persona für eine Frage.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 32`** (1 nodes): `Erkennt Fragen und Antwortmöglichkeiten im aktuellen AX-Tree.          Filtert B`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 33`** (1 nodes): `Klickt eine Antwortmöglichkeit (RadioButton/CheckBox).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 34`** (1 nodes): `Tippt eine Antwort in ein Textfeld.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 35`** (1 nodes): `Klickt den Weiter/Nächst-Button.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 36`** (1 nodes): `Prüft ob ein Survey machbar ist — via vision_gate (NVIDIA + Pixtral).          E`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 37`** (1 nodes): `Macht einen Screenshot und speichert ihn.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 38`** (1 nodes): `Beantwortet eine einzelne Frage basierend auf Persona und Fragetyp.          - r`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 39`** (1 nodes): `Scannt verfügbare Surveys via CDP DOM.          Returns:         list[dict]: [{i`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 40`** (1 nodes): `Startet einen Survey per CDP Click.          Returns:         dict: {"success":`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 41`** (1 nodes): `Bearbeitet die Vorqualifizierung mit Vision-Gate Logik-Prüfung.          1. Cook`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 42`** (1 nodes): `Bearbeitet einen Survey im neuen Tab.          1. Erkennt neuen Tab (Cint, PureS`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 43`** (1 nodes): `Schließt den Survey-Tab und kehrt zum HeyPiggy Dashboard zurück.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 44`** (1 nodes): `Bearbeitet das Bewertungsfeld nach dem Survey.          Schreibt kurzen Text + r`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 45`** (1 nodes): `Prüft ob sich das Guthaben erhöht hat.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 46`** (1 nodes): `PUBLIC BOX API: Komplette Survey Automation.          Führt Surveys nacheinander`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 47`** (1 nodes): `Public API: Verfügbare Surveys scannen.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 48`** (1 nodes): `Public API: Besten oder bestimmten Survey starten.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 49`** (1 nodes): `Public API: Vorqualifizierung durchführen.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `SemanticAnalyzer` connect `Community 1` to `Community 2`, `Community 3`, `Community 12`, `Community 6`?**
  _High betweenness centrality (0.348) - this node is a cross-community bridge._
- **Why does `OutputGenerator` connect `Community 0` to `Community 2`, `Community 3`, `Community 6`?**
  _High betweenness centrality (0.235) - this node is a cross-community bridge._
- **Why does `dispatch()` connect `Community 1` to `Community 5`?**
  _High betweenness centrality (0.201) - this node is a cross-community bridge._
- **Are the 110 inferred relationships involving `OutputGenerator` (e.g. with `TestOutputGenerator` and `TestOutputGeneratorLogbook`) actually correct?**
  _`OutputGenerator` has 110 INFERRED edges - model-reasoned connections that need verification._
- **Are the 92 inferred relationships involving `SemanticAnalyzer` (e.g. with `TestSemanticAnalyzer` and `TestSemanticAnalyzerCategories`) actually correct?**
  _`SemanticAnalyzer` has 92 INFERRED edges - model-reasoned connections that need verification._
- **Are the 49 inferred relationships involving `OpenCodeDBPoller` (e.g. with `TestIntegrationPipeline` and `Integration test suite for stealth-sync full pipeline.  Tests the complete workf`) actually correct?**
  _`OpenCodeDBPoller` has 49 INFERRED edges - model-reasoned connections that need verification._
- **Are the 28 inferred relationships involving `StealthSyncDaemon` (e.g. with `Test Infisical utilities.` and `Test that daemon can be imported with Infisical integration.`) actually correct?**
  _`StealthSyncDaemon` has 28 INFERRED edges - model-reasoned connections that need verification._