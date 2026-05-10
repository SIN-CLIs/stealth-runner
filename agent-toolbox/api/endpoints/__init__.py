# ════════════════════════════════════════════════════════════════════════════════╗
# ║  ENDPOINTS PACKAGE — Modular FastAPI routers                                 ║
# ║                                                                               ║
# ║  REGEL (AGENTS.md REGEL 1c): Keine Datei >300 Zeilen.                        ║
# ║  Split in 5 Dateien:                                                         ║
# ║    _common.py    → Schemas + preflight + registry (shared)                   ║
# ║    survey_core.py → /open, /close, /rate, /purespectrum-preflight, /run-graph║
# ║    survey_answer.py → /snapshot, /completion, /answer                        ║
# ║    survey_actions.py → /click, /find, /verify, /click-angular, /fill-input,  ║
# ║                        /find-tab, /close-modals                               ║
# ║    survey_captchas.py → /captcha/solve, /solve-drag                          ║
# ║    survey_scan.py   → /survey/scan                                           ║
# ╚═══════════════════════════════════════════════════════════════════════════════╝

from ._common import (
    require_survey_ready, preflight_check, update_command_registry,
    PreflightError, _read_balance,
    # ALL schemas
    OpenSurveyRequest, OpenSurveyResponse,
    CloseSurveyRequest, CloseSurveyResponse,
    FillSurveyRequest, FillSurveyResponse,
    RateSurveyRequest, RateSurveyResponse,
    PurespectrumPreflightRequest, PurespectrumPreflightResponse,
    RunGraphRequest, RunGraphResponse,
    UniversalAnswerRequest, UniversalAnswerResponse,
    ScanDashboardRequest, ScanDashboardResponse,
    SnapshotRequest, SnapshotResponse,
    CompletionRequest, CompletionResponse,
    ClickRequest, ClickResponse,
    FindRequest, FindResponse,
    VerifyRequest, VerifyResponse,
    ClickAngularRequest, ClickAngularResponse,
    FillInputRequest, FillInputResponse,
    FindTabRequest, FindTabResponse,
    CloseModalsRequest, CloseModalsResponse,
    CaptchaSolveRequest, CaptchaSolveResponse,
    SolveDragPuzzleRequest, SolveDragPuzzleResponse,
)

# Re-export all routers for import in survey_tools.py
from .survey_core import router as survey_core_router
from .survey_answer import router as survey_answer_router
from .survey_actions import router as survey_actions_router
from .survey_captchas import router as survey_captchas_router
from .survey_scan import router as survey_scan_router

__all__ = [
    "require_survey_ready", "preflight_check", "update_command_registry",
    "PreflightError", "_read_balance",
    # Schemas
    "OpenSurveyRequest", "OpenSurveyResponse",
    "CloseSurveyRequest", "CloseSurveyResponse",
    "FillSurveyRequest", "FillSurveyResponse",
    "RateSurveyRequest", "RateSurveyResponse",
    "PurespectrumPreflightRequest", "PurespectrumPreflightResponse",
    "RunGraphRequest", "RunGraphResponse",
    "UniversalAnswerRequest", "UniversalAnswerResponse",
    "ScanDashboardRequest", "ScanDashboardResponse",
    "SnapshotRequest", "SnapshotResponse",
    "CompletionRequest", "CompletionResponse",
    "ClickRequest", "ClickResponse",
    "FindRequest", "FindResponse",
    "VerifyRequest", "VerifyResponse",
    "ClickAngularRequest", "ClickAngularResponse",
    "FillInputRequest", "FillInputResponse",
    "FindTabRequest", "FindTabResponse",
    "CloseModalsRequest", "CloseModalsResponse",
    "CaptchaSolveRequest", "CaptchaSolveResponse",
    "SolveDragPuzzleRequest", "SolveDragPuzzleResponse",
    # Routers
    "survey_core_router",
    "survey_answer_router",
    "survey_actions_router",
    "survey_captchas_router",
    "survey_scan_router",
]