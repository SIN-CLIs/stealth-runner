"""================================================================================
CAPTCHA FALLBACK CHAIN — 5-Stufen Zero-Cost Defense in Depth (SR-138)
================================================================================

MODUL-KONZEPT (SR-138, 2026-05-12):
    Orchestriert die 5-stufige Captcha-Fallback-Chain. Wenn ein Solver
    fehlschlägt, wird der nächste versucht. Alle Solver sind KOSTENLOS
    (keine bezahlten Services wie 2Captcha, Anti-Captcha, etc.).

CHAIN-REIHENFOLGE:
    [1] NIM Primary (Nemotron-3-Nano-Omni) — existierender Solver
    [2] NIM Secondary (Qwen2.5-VL-72B) — nim_secondary_solver.py
    [3] Vercel AI Gateway (Gemini → Claude) — gateway_solver.py
    [4] Audio Solver (Parakeet ASR) — audio_solver.py
    [5] Human Handoff (JSONL Log) — logs/captcha-failures-*.jsonl

WARUM DIESE REIHENFOLGE?
    - [1+2] Zwei verschiedene NIM-Modelle reduzieren modellspezifische Fehler
    - [3] Gateway hat Gemini (schnell, native grounding) + Claude (reasoning)
    - [4] Audio als letzter algorithmischer Versuch (nur für reCAPTCHA/hCaptcha)
    - [5] Niemals bezahlter Service — wir loggen und eskalieren

STEP-TRACE:
    Jeder Schritt wird mit Ergebnis protokolliert für Debugging:
    [{solver: "nim_primary", outcome: "failed", error: "timeout"}, ...]

HUMAN HANDOFF:
    Bei finalem Fehler wird `logs/captcha-failures-YYYYMMDD.jsonl` geschrieben:
    {
        "timestamp": "2026-05-12T14:30:00Z",
        "detected_type": "angular_drag_drop",
        "page_url": "https://...",
        "step_trace": [...],
        "screenshot_b64": "iVBOR..."
    }

PUBLIC API:
    solve_with_fallback(cdp, detection, page_url) -> CaptchaResult | None

EXCEPTION:
    CaptchaUnsolvedError — raised wenn alle Schritte fehlschlagen

Module Status: NEW (SR-138, 2026-05-12)
================================================================================
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger("fallback_chain")

# ── EXCEPTION ──────────────────────────────────────────────────────────────

class CaptchaUnsolvedError(Exception):
    """Raised wenn alle Fallback-Schritte fehlgeschlagen sind.

    Attributes:
        captcha_type: Der Typ des ungelösten Captchas
        step_trace: Liste aller versuchten Schritte mit Ergebnissen
        page_url: URL der Seite mit dem Captcha
    """

    def __init__(self, captcha_type: str, step_trace: list, page_url: str = ""):
        self.captcha_type = captcha_type
        self.step_trace = step_trace
        self.page_url = page_url
        super().__init__(
            f"Captcha '{captcha_type}' unsolved after {len(step_trace)} attempts. "
            f"Last error: {step_trace[-1].get('error', 'unknown') if step_trace else 'none'}"
        )


# ── RESULT DATACLASS ───────────────────────────────────────────────────────

@dataclass
class CaptchaResult:
    """Ergebnis eines Captcha-Lösungsversuchs."""
    solved: bool
    captcha_type: str = ""
    token: str = ""
    elapsed_ms: float = 0.0
    reason: str = "ok"
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class StepResult:
    """Ergebnis eines einzelnen Chain-Schritts."""
    solver: str
    outcome: str  # "success", "failed", "skipped"
    error: str = ""
    elapsed_ms: float = 0.0


# ── SOLVER IMPORTS ─────────────────────────────────────────────────────────

def _get_nim_primary_solver():
    """Import existierender NIM Primary Solver (Nemotron-3-Nano-Omni)."""
    try:
        # Der existierende Solver in captcha_adapters oder drag_drop_solver
        from .drag_drop_solver import solve_puzzle
        return solve_puzzle
    except ImportError:
        pass

    # Fallback: Versuch über captcha_adapters
    try:
        from ..captcha_adapters import get_adapter
        return get_adapter("angular_drag_drop")
    except ImportError:
        pass

    return None


def _get_nim_secondary_solver():
    """Import NIM Secondary Solver (Qwen2.5-VL-72B)."""
    try:
        from .nim_secondary_solver import solve
        return solve
    except ImportError as e:
        logger.warning("nim_secondary_solver import failed: %s", e)
        return None


def _get_gateway_solver():
    """Import Vercel AI Gateway Solver."""
    try:
        from .gateway_solver import solve
        return solve
    except ImportError as e:
        logger.warning("gateway_solver import failed: %s", e)
        return None


def _get_audio_solver():
    """Import Audio Solver (Parakeet ASR)."""
    try:
        from .audio_solver import solve
        return solve
    except ImportError as e:
        logger.warning("audio_solver import failed: %s", e)
        return None


# ── LOGGING ────────────────────────────────────────────────────────────────

def _ensure_logs_dir() -> Path:
    """Stelle sicher dass logs/ Verzeichnis existiert."""
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    return logs_dir


def _capture_screenshot_b64(cdp) -> Optional[str]:
    """Capture Screenshot für Failure-Log."""
    try:
        resp = cdp.call_result("Page.captureScreenshot", {"format": "png", "quality": 60})
        return resp.get("data")
    except Exception:
        return None


def _log_human_handoff(
    cdp,
    detection,
    page_url: str,
    step_trace: list[dict],
) -> str:
    """Schreibe Failure-Log für Human Handoff.

    Args:
        cdp: CDPConnection instance
        detection: CaptchaDetection
        page_url: URL der Seite
        step_trace: Liste aller versuchten Schritte

    Returns:
        Pfad zur Log-Datei
    """
    logs_dir = _ensure_logs_dir()
    # SR-187: UTC-aware datetimes (naive utcnow() is deprecated in Py 3.12,
    # removed in 3.14; comparing naive against tz-aware silently mis-orders).
    now_utc = datetime.now(timezone.utc)
    date_str = now_utc.strftime("%Y%m%d")
    log_path = logs_dir / f"captcha-failures-{date_str}.jsonl"

    # Capture screenshot
    screenshot_b64 = _capture_screenshot_b64(cdp)

    # Build log entry
    entry = {
        # SR-187: isoformat() on tz-aware dt emits "+00:00"; we keep the
        # historical "Z" suffix for jsonl-consumer compatibility.
        "timestamp": now_utc.isoformat().replace("+00:00", "Z"),
        "detected_type": detection.captcha_type,
        "page_url": page_url,
        "frame_id": detection.frame_id,
        "dom_hint": detection.dom_hint,
        "step_trace": step_trace,
        "screenshot_b64": screenshot_b64 or "",
    }

    # Append to JSONL
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    logger.info("Human handoff logged to: %s", log_path)
    return str(log_path)


# ── FALLBACK CHAIN ─────────────────────────────────────────────────────────

class FallbackChain:
    """Orchestriert die 5-stufige Captcha-Fallback-Chain.

    Usage:
        chain = FallbackChain()
        result = chain.solve_with_fallback(cdp, detection, page_url)

    Die Chain short-circuits bei erstem Erfolg.
    Bei finalem Fehler wird CaptchaUnsolvedError geraised.
    """

    def __init__(self):
        """Initialisiere Chain mit allen verfügbaren Solvern."""
        self._solvers: list[tuple[str, Callable | None]] = [
            ("nim_primary", _get_nim_primary_solver()),
            ("nim_secondary", _get_nim_secondary_solver()),
            ("gateway", _get_gateway_solver()),
            ("audio", _get_audio_solver()),
        ]

    def _try_solver(
        self,
        name: str,
        solver: Callable | None,
        cdp,
        detection,
    ) -> tuple[Optional[CaptchaResult], StepResult]:
        """Versuche einen einzelnen Solver.

        Args:
            name: Name des Solvers für Logging
            solver: Solver-Funktion oder None
            cdp: CDPConnection
            detection: CaptchaDetection

        Returns:
            (CaptchaResult | None, StepResult)
        """
        t0 = time.time()

        # Skip if solver not available
        if solver is None:
            return None, StepResult(
                solver=name,
                outcome="skipped",
                error="solver_not_available",
                elapsed_ms=0,
            )

        try:
            # Rufe Solver auf
            result = solver(cdp, detection)

            elapsed = (time.time() - t0) * 1000

            # Prüfe ob gelöst
            if isinstance(result, dict):
                solved = result.get("solved", False)
            elif hasattr(result, "solved"):
                solved = result.solved
            else:
                solved = bool(result)

            if solved:
                logger.info("Chain step '%s' succeeded in %.0fms", name, elapsed)
                return result, StepResult(
                    solver=name,
                    outcome="success",
                    elapsed_ms=elapsed,
                )
            else:
                reason = getattr(result, "reason", "") if hasattr(result, "reason") else str(result)
                logger.info("Chain step '%s' failed: %s", name, reason)
                return None, StepResult(
                    solver=name,
                    outcome="failed",
                    error=reason[:100],
                    elapsed_ms=elapsed,
                )

        except Exception as e:
            elapsed = (time.time() - t0) * 1000
            logger.warning("Chain step '%s' exception: %s", name, e)
            return None, StepResult(
                solver=name,
                outcome="failed",
                error=f"exception: {str(e)[:80]}",
                elapsed_ms=elapsed,
            )

    def solve_with_fallback(
        self,
        cdp,
        detection,
        page_url: str = "",
    ) -> CaptchaResult:
        """Hauptmethode: Durchlaufe Fallback-Chain bis Erfolg oder Handoff.

        Args:
            cdp: CDPConnection instance
            detection: CaptchaDetection mit captcha_type und dom_hint
            page_url: URL der aktuellen Seite (für Logging)

        Returns:
            CaptchaResult bei Erfolg

        Raises:
            CaptchaUnsolvedError: Wenn alle Schritte fehlschlagen
        """
        t0 = time.time()
        step_trace: list[dict] = []
        ctype = detection.captcha_type

        logger.info(
            "Starting fallback chain for '%s' captcha (page: %s)",
            ctype, page_url[:60] if page_url else "unknown"
        )

        # Durchlaufe alle Solver
        for name, solver in self._solvers:
            # Spezialfall: Audio-Solver nur für reCAPTCHA/hCaptcha
            if name == "audio" and ctype not in ("recaptcha", "hcaptcha"):
                step_trace.append({
                    "solver": name,
                    "outcome": "skipped",
                    "error": "audio_not_applicable",
                    "elapsed_ms": 0,
                })
                continue

            result, step_result = self._try_solver(name, solver, cdp, detection)
            step_trace.append({
                "solver": step_result.solver,
                "outcome": step_result.outcome,
                "error": step_result.error,
                "elapsed_ms": step_result.elapsed_ms,
            })

            # Short-circuit on success
            if result is not None:
                # Ensure CaptchaResult type
                if isinstance(result, CaptchaResult):
                    result.extra["step_trace"] = step_trace
                    result.elapsed_ms = (time.time() - t0) * 1000
                    return result
                elif isinstance(result, dict):
                    return CaptchaResult(
                        solved=True,
                        captcha_type=ctype,
                        token=result.get("token", ""),
                        elapsed_ms=(time.time() - t0) * 1000,
                        reason="ok",
                        extra={"step_trace": step_trace, **result},
                    )

        # Step 5: Human Handoff
        logger.warning(
            "All %d solvers failed for '%s' captcha — logging for human handoff",
            len(self._solvers), ctype
        )
        log_path = _log_human_handoff(cdp, detection, page_url, step_trace)
        step_trace.append({
            "solver": "human_handoff",
            "outcome": "logged",
            "error": "",
            "elapsed_ms": 0,
            "log_path": log_path,
        })

        # Raise exception
        raise CaptchaUnsolvedError(
            captcha_type=ctype,
            step_trace=step_trace,
            page_url=page_url,
        )


# ── SINGLETON + PUBLIC API ─────────────────────────────────────────────────

_chain_instance: Optional[FallbackChain] = None


def get_chain() -> FallbackChain:
    """Singleton-Accessor für FallbackChain."""
    global _chain_instance
    if _chain_instance is None:
        _chain_instance = FallbackChain()
    return _chain_instance


def solve_with_fallback(cdp, detection, page_url: str = "") -> CaptchaResult:
    """Public API: Löst Captcha mit 5-stufiger Fallback-Chain.

    Chain-Reihenfolge:
    [1] NIM Primary (Nemotron-3-Nano-Omni)
    [2] NIM Secondary (Qwen2.5-VL-72B)
    [3] Vercel AI Gateway (Gemini → Claude)
    [4] Audio Solver (Parakeet ASR, nur für reCAPTCHA/hCaptcha)
    [5] Human Handoff (Log to JSONL)

    Args:
        cdp: CDPConnection instance
        detection: CaptchaDetection mit captcha_type und dom_hint
        page_url: URL der aktuellen Seite

    Returns:
        CaptchaResult bei Erfolg

    Raises:
        CaptchaUnsolvedError: Wenn alle Schritte fehlschlagen
    """
    return get_chain().solve_with_fallback(cdp, detection, page_url)
