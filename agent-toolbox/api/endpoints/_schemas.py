# ════════════════════════════════════════════════════════════════════════════════╗
# ║  PYDANTIC SCHEMAS — Alle Request/Response Models                             ║
# ║                                                                               ║
# ║  Werden importiert von: alle endpoints/*.py + survey_tools.py               ║
# ║  Enthält NUR Pydantic models, keine Logik.                                   ║
# ║  WICHTIG: Keine Router hier!                                                 ║
# ╚═══════════════════════════════════════════════════════════════════════════════╝

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


# ── /open ──────────────────────────────────────────────────────────────────────
class OpenSurveyRequest(BaseModel):
    survey_id: str
    pid: int = 0
    wid: int = 0
    cdp_port: int = 9999
    wait_modal: float = 3.0
    wait_load: float = 5.0


class OpenSurveyResponse(BaseModel):
    status: str
    tab_id: str | None = None
    ws_url: str | None = None
    provider: str | None = None
    url: str | None = None
    modal_clicked: bool | None = None
    flow: str | None = None
    reason: str | None = None
    stage: str | None = None


# ── /close ─────────────────────────────────────────────────────────────────────
class CloseSurveyRequest(BaseModel):
    tab_id: str
    cdp_port: int = 9999


class CloseSurveyResponse(BaseModel):
    status: str
    closed: bool
    tab_id: str
    reason: str | None = None


# ── /fill ──────────────────────────────────────────────────────────────────────
class FillSurveyRequest(BaseModel):
    snapshot: dict[str, Any]
    profile_name: str = "sin_agent_heypiggy"
    use_nim: bool = False


class FillSurveyResponse(BaseModel):
    status: str
    answered: int = 0
    pages_processed: int = 0
    provider: str | None = None
    actions: list[dict[str, Any]] = []
    question_type: str | None = None
    confidence: float | None = None
    reason: str | None = None


# ── /rate ──────────────────────────────────────────────────────────────────────
class RateSurveyRequest(BaseModel):
    cdp_port: int = 9999
    verify: bool = True


class RateSurveyResponse(BaseModel):
    status: str
    bonus: float = 0.0
    tab_id: str | None = None
    verified: bool | None = None
    reason: str | None = None


# ── /purespectrum-preflight ────────────────────────────────────────────────────
class PurespectrumPreflightRequest(BaseModel):
    tab_id: str
    ws_url: str | None = None
    cdp_port: int = 9999
    debug: bool = False


class PurespectrumPreflightResponse(BaseModel):
    status: str
    success: bool
    steps: list[str] = []
    provider: str | None = "purespectrum"
    captcha_text: str | None = None
    tokens_used: int | None = None
    error: str | None = None


# ── /run-graph ─────────────────────────────────────────────────────────────────
class RunGraphRequest(BaseModel):
    survey_id: str
    provider: str = ""
    cdp_port: int = 9999
    max_iterations: int = 15


class RunGraphResponse(BaseModel):
    status: str
    earned: float = 0.0
    survey_id: str = ""
    provider: str = ""
    iterations: int = 0
    errors: int = 0
    screen_out: bool = False
    completion_detected: bool = False


# ── /universal (answer page) ───────────────────────────────────────────────────
class UniversalAnswerRequest(BaseModel):
    ws_url: str | None = None
    cdp_port: int = 9999
    profile_name: str = "sin_agent_heypiggy"
    provider: str | None = None
    max_select: int = 4


class UniversalAnswerResponse(BaseModel):
    status: str
    answered: int = 0
    provider: str = ""
    question_type: str = ""
    actions: list[dict[str, Any]] = []
    reason: str | None = None


# ── /scan ──────────────────────────────────────────────────────────────────────
class ScanDashboardRequest(BaseModel):
    cdp_port: int = 9999


class ScanDashboardResponse(BaseModel):
    status: str
    balance: float = 0.0
    surveys: list[dict[str, Any]] = []
    count: int = 0
    reason: str | None = None


# ── /snapshot ──────────────────────────────────────────────────────────────────
class SnapshotRequest(BaseModel):
    ws_url: str | None = None
    tab_id: str | None = None
    cdp_port: int = 9999


class SnapshotResponse(BaseModel):
    status: str
    url: str = ""
    title: str = ""
    body_preview: str = ""
    element_count: int = 0
    hash: str = ""
    elements: list[dict[str, Any]] = []


# ── /completion ────────────────────────────────────────────────────────────────
class CompletionRequest(BaseModel):
    ws_url: str | None = None
    cdp_port: int = 9999


class CompletionResponse(BaseModel):
    status: str
    completed: bool = False
    screen_out: bool = False
    url: str = ""
    balance: float = 0.0
    reason: str | None = None


# ── /click ─────────────────────────────────────────────────────────────────────
class ClickRequest(BaseModel):
    selector: str
    ws_url: str | None = None
    cdp_port: int = 9999
    timeout: float = 5.0


class ClickResponse(BaseModel):
    status: str
    clicked: bool = False
    element: str | None = None
    reason: str | None = None


# ── /find ──────────────────────────────────────────────────────────────────────
class FindRequest(BaseModel):
    selector: str
    ws_url: str | None = None
    cdp_port: int = 9999
    element_type: str | None = None


class FindResponse(BaseModel):
    status: str
    found: bool = False
    count: int = 0
    elements: list[dict[str, Any]] = []
    reason: str | None = None


# ── /verify ────────────────────────────────────────────────────────────────────
class VerifyRequest(BaseModel):
    selector: str
    ws_url: str | None = None
    cdp_port: int = 9999
    expected_state: str | None = None


class VerifyResponse(BaseModel):
    status: str
    verified: bool = False
    current_state: str | None = None
    reason: str | None = None


# ── /click-angular ─────────────────────────────────────────────────────────────
class ClickAngularRequest(BaseModel):
    selector: str
    ws_url: str | None = None
    cdp_port: int = 9999


class ClickAngularResponse(BaseModel):
    status: str
    clicked: bool = False
    reason: str | None = None


# ── /fill-input ────────────────────────────────────────────────────────────────
class FillInputRequest(BaseModel):
    selector: str
    value: str
    ws_url: str | None = None
    cdp_port: int = 9999


class FillInputResponse(BaseModel):
    status: str
    filled: bool = False
    reason: str | None = None


# ── /find-tab ──────────────────────────────────────────────────────────────────
class FindTabRequest(BaseModel):
    url_pattern: str | None = None
    cdp_port: int = 9999


class FindTabResponse(BaseModel):
    status: str
    tab_id: str | None = None
    ws_url: str | None = None
    url: str | None = None
    reason: str | None = None


# ── /close-modals ──────────────────────────────────────────────────────────────
class CloseModalsRequest(BaseModel):
    ws_url: str | None = None
    cdp_port: int = 9999


class CloseModalsResponse(BaseModel):
    status: str
    closed_count: int = 0
    reason: str | None = None


# ── /captcha/solve ─────────────────────────────────────────────────────────────
class CaptchaSolveRequest(BaseModel):
    ws_url: str | None = None
    cdp_port: int = 9999
    captcha_type: str | None = None


class CaptchaSolveResponse(BaseModel):
    status: str
    solved: bool = False
    captcha_type: str | None = None
    answer: str | None = None
    reason: str | None = None


# ── /solve-drag ────────────────────────────────────────────────────────────────
class SolveDragPuzzleRequest(BaseModel):
    ws_url: str | None = None
    cdp_port: int = 9999


class SolveDragPuzzleResponse(BaseModel):
    status: str
    solved: bool = False
    puzzle_number: str | None = None
    approach: str | None = None
    reason: str | None = None
