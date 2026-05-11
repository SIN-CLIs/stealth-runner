"""================================================================================
OPENCODE TOOL — Delegation an opencode CLI bei 3× Failures
================================================================================

WAS IST DAS?
  Wrapper für opencode CLI Delegation. Wenn der Survey-Graph 3×
  hintereinander fehlschlägt (consecutive_failures >= 3), wird die
  Survey-Automation an opencode CLI übergeben — ein Mensch kann das
  Problem analysieren und lösen.

ARCHITEKTUR:
  ┌─────────────────────────────────────────────────────────────────────────┐
  │                  DELEGATION WORKFLOW                                    │
  ├─────────────────────────────────────────────────────────────────────────┤
  │                                                                          │
  │  Graph: execute_node() returned total_fail > 0                          │
  │    │                                                                    │
  │    ▼                                                                    │
  │  consecutive_failures += 1                                              │
  │    │                                                                    │
  │    ▼                                                                    │
  │  consecutive_failures >= 3? ──── NO ──→ continue NEMO Loop             │
  │    │                                                                    │
  │    YES                                                                  │
  │    │                                                                    │
  │    ▼                                                                    │
  │  delegate_task() ──→ subprocess.run(opencode run ...)                  │
  │    │                                                                    │
  │    ▼                                                                    │
  │  Parse JSON output                                                      │
  │    │                                                                    │
  │    ▼                                                                    │
  │  Return result + Update state.errors                                    │
  │    │                                                                    │
  │    ▼                                                                    │
  │  END (Graph beendet)                                                    │
  │                                                                          │
  └─────────────────────────────────────────────────────────────────────────┘

TRIGGER-BEDINGUNGEN (in graph.nodes.human_delegate):
  - consecutive_failures >= 3 (3× failed execute in Folge)
  - Iteration > max_iterations (Safety-Net, aber delegate ist priorisiert)

WARUM DELEGIEREN?
  - Captchas (Angular CDK Drag-Drop Puzzle, GeeTest, Lemin)
  - Edge-Cases (seltene Survey-Provider, unerwartete DOM-Strukturen)
  - Browser-Probleme (Chrome crashed, Session verloren, etc.)
  - Neue Provider die noch nicht im Graph implementiert sind
  - Probleme die der Graph nicht "wissen" kann

DELEGATION PROMPT:
  Der Prompt enthält ALLE relevanten Informationen für den Agent:
    - Survey-ID und Provider
    - Letzten Error (Root Cause)
    - Tab-WS URL (für CDP-Zugriff)
    - Iteration (wo genau gescheitert)
    - Anweisung was zu tun ist

  Beispiel:
    "Fix survey 67064749 (provider=purespectrum):
     Root cause: Angular CDK Drag-Drop Puzzle bei 66% Fortschritt.
     Tab: ws://127.0.0.1:9999/devtools/page/...
     Iteration: 4 (4× execute versucht, 0× Erfolg)
     Letzter Error: dropzoneImg: EMPTY (CDP PointerEvent von Angular blockiert)
     Action: Implementiere PointerEvent-Lösung aus AGENTS.md §11.3,
     oder nutze NVIDIA Vision für OCR-Captcha als Workaround.
     Ziel: Survey komplettieren und balance erhöhen."

OPENCODE CLI COMMANDS:
  opencode run --format json --dir <repo_dir> --prompt <prompt>

  Flags:
    --format json       → JSON Output statt text (parsenbar)
    --dir               → Arbeitsverzeichnis (stealth-runner)
    --prompt            → Anweisung für den Agent

  Output-Format:
    {"status": "ok", "message": "...", "data": {...}}
    oder
    {"status": "error", "message": "...", "error": "..."}

TIMEOUT:
  - Default: 300 Sekunden (5 Minuten)
  - Warum so lange? Agent muss Chrome starten, Debuggen, Fixen, Testen
  - Override via OPENCODE_TIMEOUT env var

ERROR HANDLING:
  - Timeout: subprocess.TimeoutExpired → return error + timeout message
  - Non-JSON Output: json.JSONDecodeError → return raw output + parse warning
  - Empty output: return empty + warning
  - Exit code != 0: return error + stderr

BANNED METHODS — NIEMALS VERWENDEN:
  ❌ playstealth launch — setzt NICHT --force-renderer-accessibility
  ❌ webauto-nodriver — ABSOLUT BANNED
  ❌ cua-driver click (raw index) — instabil
  ❌ Hardcoded PIDs — dynamisch, niemals hardcodieren
  ❌ pkill -f "Google Chrome" — tötet USER Chrome

DEPENDENCIES:
  - subprocess.run (opencode CLI invocation)
  - json (JSON Output parsing)
  - os.environ (OPENCODE_TIMEOUT override)

================================================================================"""

from __future__ import annotations

import json
import os
import subprocess
import time
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    # Forward-ref-only: avoids runtime circular import
    # (state -> nodes -> opencode_tool -> state).
    # SurveyState is referenced as quoted annotation in
    # delegate_if_needed(); `from __future__ import annotations`
    # keeps it lazy at runtime. SR-61.
    from .state import SurveyState  # noqa: F401

# ── CONSTANTS ─────────────────────────────────────────────────────────────────

# Default-Timeout für opencode CLI Delegation.
# 300 Sekunden = 5 Minuten — lang genug für Chrome-Start + Debug + Fix.
# Override via OPENCODE_TIMEOUT env var.
DEFAULT_TIMEOUT_SECONDS = 300

# opencode CLI Arbeitsverzeichnis — stealth-runner Repo.
DEFAULT_WORKDIR = "/Users/jeremy/dev/stealth-runner"


# ── MAIN DELEGATION FUNCTION ───────────────────────────────────────────────────


def delegate_task(
    survey_id: str,
    provider: str,
    reason: str,
    tab_ws: Optional[str] = None,
    iteration: int = 0,
    workdir: str = DEFAULT_WORKDIR,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    """Delegiere Survey-Problem an opencode CLI.

    Diese Funktion wird aufgerufen wenn der Survey-Graph 3×
    hintereinander fehlschlägt. Sie startet opencode CLI mit einem
    detaillierten Prompt der alle Informationen enthält die der
    Agent braucht um das Problem zu lösen.

    DELEGATION PROMPT EXAMPLE:
      "Fix survey 67064749 (provider=purespectrum):
       Root cause: Angular CDK Drag-Drop Puzzle bei 66% Fortschritt.
       Tab: ws://127.0.0.1:9999/devtools/page/...
       Iteration: 4 (4× execute versucht, 0× Erfolg)
       Letzter Error: dropzoneImg: EMPTY (CDP PointerEvent von Angular blockiert)
       Action: Implementiere PointerEvent-Lösung aus AGENTS.md §11.3,
       oder nutze NVIDIA Vision für OCR-Captcha als Workaround.
       Ziel: Survey komplettieren und balance erhöhen."

    Args:
        survey_id: HeyPiggy Survey-ID (z.B. "67064749")
        provider: Survey-Provider Name (z.B. "purespectrum")
        reason: Warum delegiert wurde (z.B. "3 consecutive failures at iteration 4")
        tab_ws: CDP WebSocket URL des Survey-Tabs (optional, für Debugging)
        iteration: Aktuelle Iteration (z.B. 4)
        workdir: Arbeitsverzeichnis für opencode CLI (default: stealth-runner)
        timeout: Timeout in Sekunden (default: 300)

    Returns:
        Dict mit keys:
          - status: "ok" | "error"
          - stdout: opencode CLI output (JSON oder text)
          - stderr: Fehlermeldungen
          - exit_code: Exit-Code
          - timeout: True wenn Timeout erreicht

    Side-Effects:
        - subprocess.run: opencode CLI wird gestartet (blocking)
        - stdout/stderr werden geloggt für learn.md

    Example:
        >>> result = delegate_task(
        ...     survey_id="67064749",
        ...     provider="purespectrum",
        ...     reason="3 consecutive failures at iteration 4",
        ...     tab_ws="ws://127.0.0.1:9999/devtools/page/42",
        ...     iteration=4,
        ... )
        >>> result["status"]
        'ok'
    """
    # Timeout aus Environment überschreiben falls gesetzt
    timeout = int(os.environ.get("OPENCODE_TIMEOUT", str(timeout)))

    # Prompt bauen mit allen relevanten Informationen
    prompt = _build_delegation_prompt(
        survey_id=survey_id,
        provider=provider,
        reason=reason,
        tab_ws=tab_ws,
        iteration=iteration,
    )

    # opencode CLI Command bauen
    # Format: opencode run --format json --dir <workdir> --prompt "<prompt>"
    cmd = [
        "opencode",
        "run",
        "--format", "json",
        "--dir", workdir,
        "--prompt", prompt,
    ]

    # Logging für Debugging
    {
        "ts": time.time(),
        "survey_id": survey_id,
        "provider": provider,
        "reason": reason,
        "iteration": iteration,
        "cmd": f"opencode run --format json --dir {workdir} --prompt '...'",
    }

    # subprocess.run mit Timeout
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=workdir,
        )

        # Parse JSON Output wenn möglich
        parsed = None
        parse_error = None
        if result.stdout:
            try:
                parsed = json.loads(result.stdout)
            except json.JSONDecodeError as e:
                parse_error = str(e)

        return {
            "status": "ok" if result.returncode == 0 else "error",
            "exit_code": result.returncode,
            "stdout": result.stdout[:2000] if result.stdout else "",
            "stderr": result.stderr[:500] if result.stderr else "",
            "parsed": parsed,
            "parse_error": parse_error,
            "timeout": False,
        }

    except subprocess.TimeoutExpired:
        return {
            "status": "error",
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Timeout after {timeout}s",
            "parsed": None,
            "parse_error": f"Timeout: {timeout}s exceeded",
            "timeout": True,
        }

    except FileNotFoundError:
        return {
            "status": "error",
            "exit_code": -1,
            "stdout": "",
            "stderr": "opencode CLI not found — ensure opencode is in PATH",
            "parsed": None,
            "parse_error": "opencode not in PATH",
            "timeout": False,
        }

    except Exception as e:
        return {
            "status": "error",
            "exit_code": -1,
            "stdout": "",
            "stderr": str(e),
            "parsed": None,
            "parse_error": str(e),
            "timeout": False,
        }


# ── PROMPT BUILDER ────────────────────────────────────────────────────────────


def _build_delegation_prompt(
    survey_id: str,
    provider: str,
    reason: str,
    tab_ws: Optional[str],
    iteration: int,
) -> str:
    """Baue den Delegation-Prompt für opencode CLI.

    Der Prompt enthält alle Informationen die der Agent braucht
    um das Survey-Problem zu verstehen und zu lösen.

    Prompt-Struktur:
      1. Was ist das Problem? (Survey-ID, Provider, reason)
      2. Wo ist das Problem? (Tab-WS URL)
      3. Wie weit ist das Problem? (Iteration)
      4. Was soll der Agent tun? (Action + Ziel)
      5. Wie ist der Kontext? (AGENTS.md Referenzen)

    Args:
        survey_id: HeyPiggy Survey-ID
        provider: Provider Name
        reason: Warum delegiert (failure reason)
        tab_ws: CDP WS URL (optional)
        iteration: Aktuelle Iteration

    Returns:
        String: Der komplette Delegation-Prompt
    """
    lines = [
        f"Fix survey {survey_id} (provider={provider})",
        "",
        f"Root cause: {reason}",
        f"Iteration: {iteration} (NEMO Loop hat {iteration}× versucht)",
    ]

    if tab_ws:
        lines.append(f"Tab WebSocket: {tab_ws}")

    lines.extend([
        "",
        "Action required:",
        "1. Analysiere den aktuellen Tab-Zustand via CDP",
        "2. Identifiziere das Root-Cause-Problem (nicht die Symptome)",
        "3. Implementiere eine Lösung",
        "4. Teste die Lösung",
        "5. Verifiziere dass balance erhöht wurde",
        "",
        "Wichtige Kontext-Dokumente:",
        "  - AGENTS.md §11.3: Complete Drag-Drop Puzzle Problem",
        "  - AGENTS.md §DAEMON WAY: Learn-by-Doing System",
        "  - survey-cli/survey/providers/purespectrum.py: Provider-Implementierung",
        "",
        "BANNED methods (NIEMALS verwenden):",
        "  - pkill -f 'Google Chrome' (tötet USER Chrome!)",
        "  - webauto-nodriver (ABSOLUT BANNED)",
        "  - Hardcoded PIDs (PIDs sind dynamisch)",
        "",
        "Goal: Complete the survey and verify balance increased.",
    ])

    return "\n".join(lines)


# ── CONVENIENCE WRAPPER ────────────────────────────────────────────────────────


def delegate_if_needed(state: "SurveyState") -> Dict[str, Any]:
    """Convenience-Wrapper: delegiere NUR wenn should_delegate=True.

    Diese Funktion prüft state.should_delegate und ruft
    delegate_task() NUR wenn nötig. Nützlich für direkte Integration
    ohne den full Graph zu durchlaufen.

    Args:
        state: SurveyState mit should_delegate property

    Returns:
        Dict: delegate_task() Result, oder {"skipped": True} wenn nicht nötig
    """
    from .state import SurveyState

    if not isinstance(state, SurveyState):
        return {"skipped": True, "reason": "state is not SurveyState"}

    if not state.should_delegate:
        return {
            "skipped": True,
            "reason": f"consecutive_failures={state.consecutive_failures} < 3",
        }

    return delegate_task(
        survey_id=state.survey_id,
        provider=state.provider,
        reason=state.errors[-1].get("error", "unknown") if state.errors else "unknown",
        tab_ws=state.tab_ws,
        iteration=state.iteration,
    )
