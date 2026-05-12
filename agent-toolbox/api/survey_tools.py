# ════════════════════════════════════════════════════════════════════════════════╗
# ║  SURVEY TOOLS FASTAPI — Router Kombination (STUB, NICHT MONOLITH!)           ║
# ║                                                                               ║
# ║  ❌ ALT (1339 Zeilen MONOLITH): survey_tools.py war eine einzelne Datei.      ║
# ║  ✅ NEU: Modular endpoints/ — 5 Dateien, jede <300 Zeilen.                   ║
# ║                                                                               ║
# ║  Diese Datei kombiniert nur noch die Router aus endpoints/                   ║
# ║  Keine Schemas, keine Logik, keine preflight — das ist in endpoints/.        ║
# ║                                                                               ║
# ║  MODULAR STRUKTUR (endpoints/):                                              ║
# ║    _common.py          → Schemas + preflight + registry (SHARED)             ║
# ║    survey_core.py      → /open, /close, /rate, /purespectrum-preflight, /run-graph  ~175 lines
# ║    survey_answer.py    → /snapshot, /completion, /answer                     ~200 lines
# ║    survey_actions.py   → /click, /find, /verify, /click-angular, /fill-input, /find-tab, /close-modals ~200 lines
# ║    survey_captchas.py  → /captcha/solve, /solve-drag                         ~145 lines
# ║    survey_scan.py      → /survey/scan                                        ~85 lines
# ║    __init__.py         → Re-exports all routers + schemas                    ║
# ╚═══════════════════════════════════════════════════════════════════════════════╝

from __future__ import annotations

import os
import sys

from fastapi import APIRouter

# ═══════════════════════════════════════════════════════════════════════════════
# PYTHONPATH — survey-cli/ muss im path sein für tool imports
# ═══════════════════════════════════════════════════════════════════════════════
_workspace_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
_survey_cli_path = os.path.join(_workspace_root, "survey-cli")
if _survey_cli_path not in sys.path:
    sys.path.insert(0, _survey_cli_path)

# ═══════════════════════════════════════════════════════════════════════════════
# ROUTER — Kombination aller modularen Routers
# ═══════════════════════════════════════════════════════════════════════════════

from endpoints import (
    survey_actions_router,
    survey_answer_router,
    survey_captchas_router,
    survey_core_router,
    survey_scan_router,
    universal_router,
)

router = APIRouter(prefix="/survey", tags=["survey-tools"])

router.include_router(survey_core_router)
router.include_router(survey_answer_router)
router.include_router(survey_actions_router)
router.include_router(survey_captchas_router)
router.include_router(survey_scan_router)

# Universal v2 router — direkter Top-Level-Mount auf /v2/*
# Wird in main.py via app.include_router(universal_router) eingehängt.
# Hier wird er als Export bereitgestellt.
universal_router_export = universal_router

# ─── /fill endpoint (kommt aus dem alten monolith — NUR dieser!) ───────────────
# NACHTRÄGLICH: /fill ist ein spezieller Endpoint der SurveyFiller nutzt
# Er kam aus dem alten monolith — hier als einziger grosser Endpoint behalten
# (survey-cli/tools/tool_fill_survey.py hat den kompletten Fill-Logic)
from endpoints._common import (
    FillSurveyRequest,
    FillSurveyResponse,
    require_survey_ready,
    update_command_registry,
)
from tools.tool_fill_survey import SurveyFiller


@router.post(
    "/fill", response_model=FillSurveyResponse, dependencies=[Depends(require_survey_ready)]
)
async def api_fill(req: FillSurveyRequest):
    """
    Füllt eine Survey-Seite basierend auf Compact Snapshot.

    Tool: tools.tool_fill_survey.SurveyFiller
    Nutzt: ELEMENT_EXTRACTOR_JS (100% element capture)

    NO AUTO-RUN: Dieser Endpoint ist nur für MANUAL TESTING.
    """
    try:
        filler = SurveyFiller(profile_name=req.profile_name)
        result = filler.fill(snapshot=req.snapshot, use_nim=req.use_nim)
        update_command_registry("fill_survey", result.get("answered", 0) > 0, result)
        return FillSurveyResponse(
            status="ok" if result.get("answered", 0) > 0 else "no_action",
            answered=result.get("answered", 0),
            pages_processed=result.get("pages_processed", 0),
            provider=result.get("provider"),
            actions=result.get("actions", []),
            question_type=result.get("question_type"),
            confidence=result.get("confidence"),
            reason=result.get("reason"),
        )
    except Exception as e:
        update_command_registry("fill_survey", False, {"error": str(e)})
        return FillSurveyResponse(status="error", reason=str(e))
