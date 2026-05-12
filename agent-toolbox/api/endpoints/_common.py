# ════════════════════════════════════════════════════════════════════════════════╗
# ║  _common.py — Re-exports from _schemas.py + _utils.py (backward compat)      ║
# ║                                                                               ║
# ║  SPLIT (2026-05-11): _common.py war 497 Zeilen → aufgeteilt in:             ║
# ║    _schemas.py → Alle Pydantic Models (268 lines)                           ║
# ║    _utils.py  → preflight_check + require_survey_ready + update_registry    ║
# ║                                                                               ║
# ║  Keine Logik hier — nur Re-Export für Backward Compatibility.               ║
# ╚═══════════════════════════════════════════════════════════════════════════════╝

# Re-export ALL schemas (backward compat for endpoints that import from _common)
from ._schemas import (
    CaptchaSolveRequest,
    CaptchaSolveResponse,
    ClickAngularRequest,
    ClickAngularResponse,
    ClickRequest,
    ClickResponse,
    CloseModalsRequest,
    CloseModalsResponse,
    CloseSurveyRequest,
    CloseSurveyResponse,
    CompletionRequest,
    CompletionResponse,
    FillInputRequest,
    FillInputResponse,
    FillSurveyRequest,
    FillSurveyResponse,
    FindRequest,
    FindResponse,
    FindTabRequest,
    FindTabResponse,
    OpenSurveyRequest,
    OpenSurveyResponse,
    PurespectrumPreflightRequest,
    PurespectrumPreflightResponse,
    RateSurveyRequest,
    RateSurveyResponse,
    RunGraphRequest,
    RunGraphResponse,
    ScanDashboardRequest,
    ScanDashboardResponse,
    SnapshotRequest,
    SnapshotResponse,
    SolveDragPuzzleRequest,
    SolveDragPuzzleResponse,
    UniversalAnswerRequest,
    UniversalAnswerResponse,
    VerifyRequest,
    VerifyResponse,
)

# Re-export utilities
from ._utils import (
    PreflightError,
    _read_balance,
    preflight_check,
    require_survey_ready,
    update_command_registry,
)

__all__ = [
    # Schemas
    "OpenSurveyRequest",
    "OpenSurveyResponse",
    "CloseSurveyRequest",
    "CloseSurveyResponse",
    "FillSurveyRequest",
    "FillSurveyResponse",
    "RateSurveyRequest",
    "RateSurveyResponse",
    "PurespectrumPreflightRequest",
    "PurespectrumPreflightResponse",
    "RunGraphRequest",
    "RunGraphResponse",
    "UniversalAnswerRequest",
    "UniversalAnswerResponse",
    "ScanDashboardRequest",
    "ScanDashboardResponse",
    "SnapshotRequest",
    "SnapshotResponse",
    "CompletionRequest",
    "CompletionResponse",
    "ClickRequest",
    "ClickResponse",
    "FindRequest",
    "FindResponse",
    "VerifyRequest",
    "VerifyResponse",
    "ClickAngularRequest",
    "ClickAngularResponse",
    "FillInputRequest",
    "FillInputResponse",
    "FindTabRequest",
    "FindTabResponse",
    "CloseModalsRequest",
    "CloseModalsResponse",
    "CaptchaSolveRequest",
    "CaptchaSolveResponse",
    "SolveDragPuzzleRequest",
    "SolveDragPuzzleResponse",
    # Utilities
    "preflight_check",
    "require_survey_ready",
    "update_command_registry",
    "PreflightError",
    "_read_balance",
]
