"""================================================================================
OBSERVABILITY ROUTER — FastAPI Routes fuer core/* Inspektion
================================================================================

WAS IST DAS?
  REST-Endpoints die Production-Ready Observability fuer den LangGraph
  Survey-Agent liefern. Alle Daten kommen aus core.{config,analytics,
  error_handler,security,state_manager}.

WARUM SEPARATE DATEI?
  main.py ist bereits 1800+ Zeilen lang. Issue #83 verlangt explizit eine
  saubere Trennung der Concerns — Observability ist eine eigene Schicht.

ENDPOINTS:
  GET  /core/health           → core_health() — modul-status, version
  GET  /core/config           → redacted_config() — config OHNE secrets
  GET  /core/analytics        → analytics_snapshot() — counters + p95
  GET  /core/errors           → recent_errors(limit=50)
  GET  /core/runs             → list_runs(limit=20) — letzte Surveys
  GET  /core/runs/{run_id}    → run_detail(run_id) — Steps + checkpoint
  POST /core/analytics/flush  → manuell analytics in state/ persistieren
  POST /core/reset            → singletons + counters reset (NUR fuer Tests)

SECURITY:
  - Audit-Endpoints loggen via security.audit (event_type="OBSERVABILITY_ACCESS")
  - Config-Endpoint REDACTED secrets (twocaptcha_api_key, encryption_key, ...)
  - In Production hinter Auth-Middleware mounten (z. B. Header X-Internal-Token)

MOUNTING in main.py:
  from .observability import router as observability_router
  app.include_router(observability_router, prefix="/core", tags=["observability"])

================================================================================"""

from __future__ import annotations

import logging
import os
import sys
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

# Repo-Root suchen damit `import core` funktioniert (gleiche Logik wie graph.py)
_THIS = os.path.abspath(__file__)
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_THIS)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

try:
    from core import (
        bootstrap_core,
        get_analytics,
        get_config,
        get_error_handler,
        get_security_manager,
        get_state_manager,
        reset_singletons,
    )

    CORE_AVAILABLE = True
except ImportError as e:
    CORE_AVAILABLE = False
    _core_import_error = str(e)

log = logging.getLogger("api.observability")

router = APIRouter()


# ── RESPONSE MODELS ──────────────────────────────────────────────────────────


class CoreHealthResponse(BaseModel):
    """Core health-check — alle Module geladen + bootstrapped."""

    available: bool
    bootstrapped: bool
    modules: dict[str, str]  # module name → status (loaded / error)
    error: str | None = None


class AnalyticsResponse(BaseModel):
    """Snapshot aus AnalyticsCollector."""

    counters: dict[str, int]
    histograms: dict[str, dict[str, float]]  # name → {p50, p95, p99, count}
    started_at: float
    uptime_seconds: float


class ErrorEntry(BaseModel):
    step_name: str
    error_type: str
    error_msg: str
    timestamp: float
    severity: str
    retry_attempt: int = 0


class ErrorsResponse(BaseModel):
    errors: list[ErrorEntry]
    total: int


class RunSummary(BaseModel):
    """Eine vergangene Survey-Run."""

    run_id: str
    saved_at: float
    status: str
    duration_seconds: float | None = None
    balance_delta: float | None = None


class RunsResponse(BaseModel):
    runs: list[RunSummary]


class RunDetailResponse(BaseModel):
    run_id: str
    checkpoint: dict[str, Any]
    metadata: dict[str, Any]
    saved_at: float


class ConfigResponse(BaseModel):
    """Config OHNE Secrets — sichere Variante fuer /core/config."""

    chrome: dict[str, Any]
    captcha: dict[str, Any]
    budget: dict[str, Any]
    paths: dict[str, str]
    feature_flags: dict[str, bool]
    redacted_keys: list[str]


# ── HELPER ────────────────────────────────────────────────────────────────────


def _require_core() -> None:
    """Werfen 503 wenn core nicht installiert ist."""
    if not CORE_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "core_not_available",
                "message": _core_import_error if not CORE_AVAILABLE else "",
                "hint": "Stellt sicher dass repo_root in PYTHONPATH liegt "
                "und core/__init__.py existiert.",
            },
        )


def _redact_config(cfg: Any) -> ConfigResponse:
    """Convertiert Config zu Dict OHNE Secrets.

    REDACTED: twocaptcha_api_key, encryption_key, basic_auth_credentials,
    ANY field mit 'key', 'secret', 'token' im Namen.
    """
    redacted = []

    def _to_dict(obj: Any, *, prefix: str = "") -> dict[str, Any]:
        from dataclasses import fields, is_dataclass

        out: dict[str, Any] = {}
        if not is_dataclass(obj):
            return out
        for f in fields(obj):
            name = f.name
            val = getattr(obj, name, None)
            # Redaction-Regeln
            lower = name.lower()
            if any(k in lower for k in ("key", "secret", "token", "password", "credential")):
                if val:
                    redacted.append(f"{prefix}{name}")
                    out[name] = "***REDACTED***"
                else:
                    out[name] = None
                continue
            # Verschachtelte dataclasses (nicht erwartet auf 2. Ebene, aber safe)
            if is_dataclass(val):
                out[name] = _to_dict(val, prefix=f"{prefix}{name}.")
            else:
                out[name] = val
        return out

    return ConfigResponse(
        chrome=_to_dict(cfg.chrome, prefix="chrome."),
        captcha=_to_dict(cfg.captcha, prefix="captcha."),
        budget=_to_dict(cfg.budget, prefix="budget."),
        paths={
            "state_dir": str(getattr(cfg, "state_dir", "")),
            "screenshot_dir": str(getattr(cfg, "screenshot_dir", "")),
            "audit_log_dir": str(getattr(cfg, "audit_log_dir", "")),
        },
        feature_flags={
            "enable_screenshots_on_error": bool(getattr(cfg, "enable_screenshots_on_error", False)),
            "enable_audit_logging": bool(getattr(cfg, "enable_audit_logging", False)),
            "enable_analytics_export": bool(getattr(cfg, "enable_analytics_export", False)),
        },
        redacted_keys=redacted,
    )


# ── ENDPOINTS ────────────────────────────────────────────────────────────────


@router.get("/health", response_model=CoreHealthResponse)
async def core_health() -> CoreHealthResponse:
    """Liefere Status der core-Module + ob bootstrap_core() jemals lief.

    UseCase: Liveness/Readiness-Probe fuer K8s — wenn core nicht available,
    sollte der Pod NICHT als ready markiert werden.
    """
    if not CORE_AVAILABLE:
        return CoreHealthResponse(
            available=False,
            bootstrapped=False,
            modules={},
            error=_core_import_error,
        )

    modules: dict[str, str] = {}
    for name in ("config", "error_handler", "security", "analytics", "state_manager"):
        try:
            __import__(f"core.{name}")
            modules[name] = "loaded"
        except Exception as e:
            modules[name] = f"error:{e}"

    # Bootstrap-Check: existiert state_dir?
    bootstrapped = False
    try:
        cfg = get_config()
        bootstrapped = cfg.state_dir.exists()
    except Exception as e:
        log.warning("core.health.bootstrap_check_failed err=%s", e)

    return CoreHealthResponse(
        available=True,
        bootstrapped=bootstrapped,
        modules=modules,
    )


@router.get("/config", response_model=ConfigResponse)
async def get_redacted_config() -> ConfigResponse:
    """Liefere Config OHNE Secrets.

    Wichtig: NIEMALS get_config() direkt serialisieren — das wuerde
    twocaptcha_api_key und encryption_key leaken. Diese Funktion redacted
    alle Felder mit 'key'/'secret'/'token'/'password' im Namen.
    """
    _require_core()
    cfg = get_config()
    return _redact_config(cfg)


@router.get("/analytics", response_model=AnalyticsResponse)
async def get_analytics_snapshot() -> AnalyticsResponse:
    """Liefere aktuelle Analytics-Counter und Histogramme.

    Verwendung in Grafana: Scrape diesen Endpoint alle 30s, plotte
    counter-deltas + histogram-p95 als Time-Series.

    Counters die wir definitiv ausstrahlen (siehe core/langgraph_integration.py):
      - node.{name}.started / .succeeded / .failed / .budget_exceeded
      - survey.completed / .not_completed / .budget_exceeded / .unhandled_exception
      - captcha.twocaptcha.solved.{type} / .failed.{type}
    """
    _require_core()
    a = get_analytics()
    snap = a.snapshot()
    return AnalyticsResponse(
        counters=snap.get("counters", {}),
        histograms=snap.get("histograms", {}),
        started_at=snap.get("started_at", 0.0),
        uptime_seconds=time.time() - snap.get("started_at", time.time()),
    )


@router.post("/analytics/flush")
async def flush_analytics() -> dict[str, Any]:
    """Persistiere Analytics-Snapshot in state/analytics_<timestamp>.json."""
    _require_core()
    a = get_analytics()
    try:
        path = a.flush_to_disk()
        return {"status": "ok", "path": str(path) if path else None}
    except Exception as e:
        log.exception("analytics.flush.failed err=%s", e)
        raise HTTPException(status_code=500, detail={"error": str(e)}) from e


@router.get("/errors", response_model=ErrorsResponse)
async def get_recent_errors(
    limit: int = Query(50, ge=1, le=500),
) -> ErrorsResponse:
    """Liefere die letzten N Errors aus error_handler.failure_log.

    Verwendung: Schnell-Debug nach einem Survey-Run der nicht completed.
    Schaut auf /core/errors und sieht z.B. dass `decide` 3x gefailed ist
    mit `TimeoutError`.
    """
    _require_core()
    eh = get_error_handler()
    # ErrorHandler hat ein failures-Dict (step_name → list[ErrorContext])
    out: list[ErrorEntry] = []
    failures = getattr(eh, "failures", {}) or {}
    flat: list[tuple[str, Any]] = []
    for step_name, ctx_list in failures.items():
        for c in ctx_list or []:
            flat.append((step_name, c))
    # Sort by timestamp desc
    flat.sort(
        key=lambda t: float(getattr(t[1], "timestamp", 0) or 0),
        reverse=True,
    )
    for step_name, c in flat[:limit]:
        out.append(
            ErrorEntry(
                step_name=step_name,
                error_type=getattr(c, "error_type", "unknown"),
                error_msg=str(getattr(c, "error_message", ""))[:500],
                timestamp=float(getattr(c, "timestamp", 0) or 0),
                severity=str(getattr(c, "severity", "ERROR")),
                retry_attempt=int(getattr(c, "retry_attempt", 0) or 0),
            )
        )
    return ErrorsResponse(errors=out, total=len(flat))


@router.get("/runs", response_model=RunsResponse)
async def list_runs(
    limit: int = Query(20, ge=1, le=200),
) -> RunsResponse:
    """Liefere die letzten N Survey-Runs (sortiert nach saved_at desc).

    UseCase: Dashboard "letzte 20 Surveys mit Status + Reward". Klick auf
    eine Row → /core/runs/{run_id} fuer Details.
    """
    _require_core()
    sm = get_state_manager()
    cps = await sm.list_checkpoints(limit=limit)
    out: list[RunSummary] = []
    for cp in cps:
        meta = cp.get("metadata", {}) or {}
        bal_before = meta.get("balance_before", 0.0) or 0.0
        bal_after = meta.get("balance_after", 0.0) or 0.0
        out.append(
            RunSummary(
                run_id=cp.get("run_id", "?"),
                saved_at=cp.get("saved_at", 0.0),
                status=meta.get("status", "?"),
                duration_seconds=meta.get("duration_seconds"),
                balance_delta=(bal_after - bal_before) if bal_after else None,
            )
        )
    return RunsResponse(runs=out)


@router.get("/runs/{run_id}", response_model=RunDetailResponse)
async def get_run_detail(run_id: str) -> RunDetailResponse:
    """Liefere kompletten Checkpoint + Metadata fuer einen Run.

    UseCase: Debug eines fehlgeschlagenen Surveys — zeigt alle Steps,
    Budget-Snapshot (Zeit-pro-Node), Final-State.
    """
    _require_core()
    sm = get_state_manager()
    cp = await sm.load_checkpoint(run_id)
    if cp is None:
        raise HTTPException(status_code=404, detail={"error": "run_not_found", "run_id": run_id})
    return RunDetailResponse(
        run_id=run_id,
        checkpoint=cp.get("checkpoint", {}) or {},
        metadata=cp.get("metadata", {}) or {},
        saved_at=cp.get("saved_at", 0.0),
    )


@router.post("/reset")
async def reset_core() -> dict[str, str]:
    """ACHTUNG: TEST-ONLY. Reset alle Singletons (config, analytics, error_handler).

    In Production NIEMALS aufrufen — bricht laufende Surveys ab. Sollte
    hinter einer Auth-Middleware mit `internal=true` Tag mounten.
    """
    _require_core()
    log.warning("core.reset.requested — alle Singletons werden zurueckgesetzt")
    reset_singletons()
    await bootstrap_core()
    return {"status": "ok", "message": "singletons reset + bootstrap_core() done"}


@router.post("/bootstrap")
async def bootstrap_endpoint() -> dict[str, str]:
    """Erzwinge bootstrap_core() — legt state_dir, screenshot_dir, etc. an.

    Idempotent. Normalerweise laeuft das auto beim ersten LangGraph-Run,
    aber hier fuer Setup-Skripte / CI exposed.
    """
    _require_core()
    await bootstrap_core()
    cfg = get_config()
    return {
        "status": "ok",
        "state_dir": str(cfg.state_dir),
        "screenshot_dir": str(cfg.screenshot_dir),
        "audit_log_dir": str(cfg.audit_log_dir),
    }
