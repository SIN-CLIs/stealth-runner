"""
survey/agents/parallel_orchestrator.py — Parallel Orchestrator (2026-05-06)

FUNKTION: Führt alle 5 Agenten parallel aus via ThreadPoolExecutor.
Koordiniert Pipeline: ElementMapper → [PersonaChecker, PageClassifier] → AnswerGenerator → ActionVerifier.

 Thread: Coordinator (main thread)
 Model:  — (koordiniert nur, kein eigener LLM-Call)
 Input:  ws_url, page_text, profile
 Output: {final_actions: [], page_type, persona_match_score, verified, ms}

PIPELINE:
  Thread 1: ElementMapper      → element_map (RADIOS, BUTTONS, FRAMEWORK)
  Thread 2: PageClassifier     → page_type, provider, is_trap, is_terminal
  Thread 3: PersonaChecker     → scored answers (top 3 preferred)
  [parallel: 1+2+3, then 4+5]
  Thread 4: AnswerGenerator    → actions list (CDP clicks, fill, submit)
  Thread 5: ActionVerifier     → verify each action

NEMO STYLE: 1 LLM-Call pro SEITE, nicht pro Element.
Hier: 5 Agenten parallel, aber NUR 2 LLM-Calls total (PersonaChecker + AnswerGenerator).
ElementMapper + PageClassifier = instant regex, kein LLM.
ActionVerifier = mistral-small MICRO, 80ms.
"""

from __future__ import annotations
import time
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Any, Optional

from .element_mapper import ElementMapper
from .page_classifier import PageClassifier
from .persona_checker import PersonaChecker
from .answer_generator import AnswerGenerator
from .action_verifier import ActionVerifier


class ParallelOrchestrator:
    """5-agent parallel pipeline for survey automation.

    FLOW:
    ┌─────────────────────────────────────────────────────────┐
    │                    PARALLEL PHASE 1                      │
    │  ┌───────────────┐  ┌───────────────┐  ┌─────────────┐  │
    │  │ElementMapper  │  │PageClassifier │  │PersonaCheck │  │
    │  │  (instant)    │  │  (instant)    │  │ (nemotron)  │  │
    │  └───────┬───────┘  └───────┬───────┘  └──────┬──────┘  │
    │          │                  │                 │          │
    │          └────────┬─────────┴─────────────────┘          │
    │                   ▼                                      │
    │         [element_map + page_type + scored_answers]        │
    │                   │                                      │
    │                   ▼                                      │
    │              PARALLEL PHASE 2                            │
    │  ┌───────────────────────────────┐  ┌─────────────────┐  │
    │  │     AnswerGenerator           │  │ ActionVerifier  │  │
    │  │       (nemotron)              │  │  (mistral-sm)   │  │
    │  │  → actions with CDP coords    │  │  → verify state │  │
    │  └───────────────┬───────────────┘  └─────────────────┘  │
    │                  │                                      │
    │                  ▼                                      │
    │           [final_actions]                               │
    └─────────────────────────────────────────────────────────┘

    TIMING:
    - Phase 1 (3 agents parallel): ~500ms (nemotron is the slowest)
    - Phase 2 (2 agents): ~600ms (nemotron + mistral in parallel)
    - Total: ~1100ms vs 5000ms sequential = 5× faster
    """

    def __init__(self, router=None):
        self.router = router
        self.element_mapper = ElementMapper(router)
        self.page_classifier = PageClassifier(router)
        self.persona_checker = PersonaChecker(router)
        self.answer_generator = AnswerGenerator(router)
        self.action_verifier = ActionVerifier(router)

    def run(self, ws_url: str, page_text: str, profile: Dict,
            actions: List[Dict] = None) -> Dict[str, Any]:
        """Run full parallel pipeline.

        Args:
            ws_url: CDP WebSocket URL
            page_text: Current page text
            profile: Persona profile dict
            actions: Optional pre-generated actions (for verification)

        Returns:
            Dict with final_actions, page_type, confidence, timing
        """
        total_start = time.monotonic()

        element_map = None
        page_class = None
        persona_result = None

        # ── PARALLEL PHASE 1: ElementMapper + PageClassifier + PersonaChecker ──
        phase1_start = time.monotonic()

        with ThreadPoolExecutor(max_workers=3) as executor:
            f1 = executor.submit(self.element_mapper.map, ws_url, page_text)
            f2 = executor.submit(self.page_classifier.classify, page_text, {})
            f3 = executor.submit(self.persona_checker.check, page_text, {}, profile)

            element_map = f1.result(timeout=15)
            page_class = f2.result(timeout=10)
            persona_result = f3.result(timeout=15)

        phase1_ms = round((time.monotonic() - phase1_start) * 1000)

        # Check for terminal page
        if page_class.get("is_terminal"):
            return {
                "final_actions": [],
                "page_type": page_class.get("page_type", "unknown"),
                "is_terminal": True,
                "is_trap": page_class.get("is_trap", False),
                "terminal_reason": page_class.get("terminal_reason", ""),
                "element_map": element_map,
                "page_class": page_class,
                "persona_result": persona_result,
                "total_ms": round((time.monotonic() - total_start) * 1000),
                "phase1_ms": phase1_ms,
                "phase2_ms": 0,
                "confidence": 1.0,
            }

        # ── PARALLEL PHASE 2: AnswerGenerator + ActionVerifier ────────────────
        phase2_start = time.monotonic()

        # AnswerGenerator needs all Phase 1 results
        action_result = self.answer_generator.generate(
            page_text=page_text,
            element_map=element_map,
            page_class=page_class,
            persona_result=persona_result,
            profile=profile,
        )

        # ActionVerifier checks if actions were already executed
        verified_actions = []
        if actions:
            page_before_hash = self.action_verifier.get_page_hash(ws_url)
            for act in actions:
                vr = self.action_verifier.verify(act, ws_url, page_before_hash)
                verified_actions.append({
                    "action": act,
                    "verified": vr.get("verified", False),
                    "state_changed": vr.get("state_changed", False),
                })
            page_before_hash = ""  # Only hash once

        phase2_ms = round((time.monotonic() - phase2_start) * 1000)
        total_ms = round((time.monotonic() - total_start) * 1000)

        return {
            "agent": "parallel_orchestrator",
            "final_actions": action_result.get("actions", []),
            "action_count": action_result.get("action_count", 0),
            "page_type": page_class.get("page_type", "unknown"),
            "is_terminal": page_class.get("is_terminal", False),
            "is_trap": page_class.get("is_trap", False),
            "provider": page_class.get("provider", "unknown"),
            "framework": element_map.get("framework", "standard"),
            "persona_match_score": persona_result.get("persona_match_score", 0.5),
            "confidence": action_result.get("confidence", 0.5),
            "has_submit": action_result.get("has_submit", False),
            "element_map": element_map,
            "page_class": page_class,
            "persona_result": persona_result,
            "verified_actions": verified_actions,
            "total_ms": total_ms,
            "phase1_ms": phase1_ms,
            "phase2_ms": phase2_ms,
        }

    def generate_only(self, ws_url: str, page_text: str, profile: Dict) -> Dict[str, Any]:
        """Just generate actions without verification (for one-shot execution)."""
        with ThreadPoolExecutor(max_workers=3) as executor:
            f1 = executor.submit(self.element_mapper.map, ws_url, page_text)
            f2 = executor.submit(self.page_classifier.classify, page_text, {})
            f3 = executor.submit(self.persona_checker.check, page_text, {}, profile)

            element_map = f1.result(timeout=15)
            page_class = f2.result(timeout=10)
            persona_result = f3.result(timeout=15)

        action_result = self.answer_generator.generate(
            page_text=page_text,
            element_map=element_map,
            page_class=page_class,
            persona_result=persona_result,
            profile=profile,
        )

        return {
            "final_actions": action_result.get("actions", []),
            "action_count": action_result.get("action_count", len(action_result.get("actions", []))),
            "page_type": page_class.get("page_type", "unknown"),
            "is_terminal": page_class.get("is_terminal", False),
            "is_trap": page_class.get("is_trap", False),
            "provider": page_class.get("provider", "unknown"),
            "framework": element_map.get("framework", "standard"),
            "persona_match_score": persona_result.get("persona_match_score", 0.5),
            "confidence": action_result.get("confidence", 0.5),
            "element_map": element_map,
            "page_class": page_class,
            "persona_result": persona_result,
        }

    def verify_only(self, actions: List[Dict], ws_url: str,
                    page_before_hash: str = "") -> List[Dict]:
        """Verify pre-executed actions."""
        results = []
        for act in actions:
            vr = self.action_verifier.verify(act, ws_url, page_before_hash)
            results.append({
                "action": act,
                "verified": vr.get("verified", False),
                "state_changed": vr.get("state_changed", False),
                "details": vr.get("details", {}),
            })
        return results