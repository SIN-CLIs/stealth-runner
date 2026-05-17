"""================================================================================
ENV CHECK — Fail-fast environment validation at daemon/run startup (SR-254)
================================================================================

MODUL-KONZEPT (SR-254)
----------------------

Heutiger Stealth-Runner faellt typisch 5 Minuten in einen Run mit einem
NoneType-Error oder einem 401, weil ein erforderlicher Env-Var nicht
gesetzt war (TWOCAPTCHA_API_KEY, CHROME_EXECUTABLE, OPENAI_API_KEY etc).
Das ist Operator-Pain, der vermeidbar ist:

  - Im worst case startet die ganze Browser-/Daemon-Pipeline, registriert
    Personas, oeffnet Chrome — und scheitert dann beim ersten Captcha.
  - Recovery braucht: Daemon stoppen, .env editieren, Daemon neu starten.
    20-30 Minuten verloren.

Dieses Modul liefert ein **pure-Python**, **dependency-frei** Fail-Fast-
Werkzeug: eine Liste von EnvRequirement-Eintraegen mit optionalem
Validator-Hook, eine `check_env()`-Funktion die alle pruft, und ein
`format_human_report()` fuer "/doctor"-style Output.

DESIGN
------

  EnvRequirement(name, severity, description, validator?, default_hint?)
    - severity: "required" | "warning" | "optional"
        required  → fehlt → is_ok=False, daemon should refuse to start
        warning   → fehlt → is_ok=True, but report.warnings populated
        optional  → fehlt → is_ok=True, silent (kein Warning-Lift)
    - validator: optional function (str) -> str. Returns "" on OK,
      error message on invalid. Validator exceptions are caught and
      converted to invalid status (operator-bugs in validator should
      not crash the check).

  EnvCheckResult
    - is_ok: bool — daemon may proceed
    - missing_required, missing_optional, warnings, invalid, invalid_optional:
      lists for structured downstream consumption (eg. /doctor JSON).
    - statuses: complete per-var EnvVarStatus list for reporting.

DEFAULT REQUIREMENT LISTS
-------------------------

Two pre-curated lists for the typical entry points:

  REQUIRED_FOR_DAEMON  — the bare minimum to start the daemon at all.
                         CHROME_EXECUTABLE, STATE_DIR.

  REQUIRED_FOR_LIVE_RUN — daemon plus what's needed for an actual
                          earning live run: at least one CAPTCHA solver
                          key (TWOCAPTCHA or CAPSOLVER), and an LLM
                          key (OPENAI_API_KEY or NIM_API_KEY).

Callers can override or extend these lists trivially.

USAGE
-----

  >>> from survey.daemon.env_check import check_env, REQUIRED_FOR_LIVE_RUN
  >>> result = check_env(REQUIRED_FOR_LIVE_RUN)
  >>> if not result.is_ok:
  ...     print(format_human_report(result))
  ...     sys.exit(2)

  >>> # Or in a /doctor command JSON:
  >>> result.to_dict()
  {"is_ok": false, "missing_required": [...], ...}

NICHT-ZIELE
-----------
- Kein .env-Loading. dotenv/load_dotenv/etc. ist Caller-Verantwortung.
  Dieses Modul prueft nur das resultierende Environment.
- Kein Wireup in den Daemon-Startup. SR-254 liefert das Primitive,
  Wireup ist separater Folge-PR.
- Kein Logging des Werts (Secrets!) — nur des Status.

Module Status: NEW (SR-254)
================================================================================
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Literal, Optional

Severity = Literal["required", "warning", "optional"]
"""
- required:  missing/invalid → is_ok=False (daemon refuse to start)
- warning:   missing/invalid → is_ok=True, but reported (operator FYI)
- optional:  missing → silent. Invalid → reported (invalid_optional)
             but is_ok stays True.
"""

VarState = Literal["present", "missing", "invalid"]


# ── Data shapes ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class EnvRequirement:
    """One env-var the daemon expects to see.

    Fields:
        name:          The env-var name (e.g. "OPENAI_API_KEY").
        severity:      required / warning / optional.
        description:   One-liner shown in the human report.
        validator:     Optional ``(str) -> str`` callable. Return "" if the
                       value is OK; return a non-empty error message if
                       invalid. Exceptions are caught and converted to
                       'invalid' status with the exception message —
                       a buggy validator must NEVER crash startup.
        default_hint:  Optional advisory shown in the human report when
                       the var is missing. e.g. "/usr/bin/chromium".
    """

    name: str
    severity: Severity = "required"
    description: str = ""
    validator: Optional[Callable[[str], str]] = None
    default_hint: Optional[str] = None


@dataclass(frozen=True)
class EnvVarStatus:
    """Per-var outcome of a check_env run."""

    name: str
    state: VarState
    severity: Severity
    error_message: str = ""
    requirement: Optional[EnvRequirement] = None


@dataclass(frozen=True)
class EnvCheckResult:
    """Aggregate outcome of a check_env run.

    is_ok semantics:
        is_ok = (no missing_required) AND (no invalid required)
    Warnings and optional-missing/invalid never push is_ok to False.
    """

    is_ok: bool
    statuses: list[EnvVarStatus]
    missing_required: list[EnvVarStatus] = field(default_factory=list)
    missing_optional: list[EnvVarStatus] = field(default_factory=list)
    warnings: list[EnvVarStatus] = field(default_factory=list)
    invalid: list[EnvVarStatus] = field(default_factory=list)
    invalid_optional: list[EnvVarStatus] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe dict for /doctor or structlog."""
        def stat_d(s: EnvVarStatus) -> dict[str, Any]:
            return {
                "name": s.name,
                "state": s.state,
                "severity": s.severity,
                "error_message": s.error_message,
            }

        return {
            "is_ok": self.is_ok,
            "statuses": [stat_d(s) for s in self.statuses],
            "missing_required": [stat_d(s) for s in self.missing_required],
            "missing_optional": [stat_d(s) for s in self.missing_optional],
            "warnings": [stat_d(s) for s in self.warnings],
            "invalid": [stat_d(s) for s in self.invalid],
            "invalid_optional": [stat_d(s) for s in self.invalid_optional],
        }


# ── Internal helpers ────────────────────────────────────────────────────────


def _is_set(value: Optional[str]) -> bool:
    """Empty string and whitespace-only are treated as not-set."""
    if value is None:
        return False
    return bool(value.strip())


def _run_validator(
    validator: Callable[[str], str], value: str
) -> str:
    """Call validator; convert exceptions into error messages."""
    try:
        result = validator(value)
    except Exception as exc:  # noqa: BLE001 — defensive
        return f"validator raised: {exc!s}"
    return result if result else ""


# ── PUBLIC API ──────────────────────────────────────────────────────────────


def check_env(
    requirements: Iterable[EnvRequirement],
    *,
    env: Optional[dict[str, str]] = None,
) -> EnvCheckResult:
    """Run all requirements against ``env`` and return an EnvCheckResult.

    Args:
        requirements: Any iterable of EnvRequirement.
        env:          Optional explicit environment dict (test-friendly).
                      Default: os.environ.

    Returns:
        EnvCheckResult with full per-var statuses + bucketed lists.
    """
    if env is None:
        env_map: dict[str, str] = dict(os.environ)
    else:
        env_map = dict(env)

    statuses: list[EnvVarStatus] = []
    missing_required: list[EnvVarStatus] = []
    missing_optional: list[EnvVarStatus] = []
    warnings: list[EnvVarStatus] = []
    invalid: list[EnvVarStatus] = []
    invalid_optional: list[EnvVarStatus] = []
    is_ok = True

    for req in requirements:
        raw = env_map.get(req.name)
        if not _is_set(raw):
            # Missing.
            status = EnvVarStatus(
                name=req.name,
                state="missing",
                severity=req.severity,
                error_message="",
                requirement=req,
            )
            statuses.append(status)
            if req.severity == "required":
                missing_required.append(status)
                is_ok = False
            elif req.severity == "warning":
                warnings.append(status)
            else:  # optional
                missing_optional.append(status)
            continue

        # Present — run validator if any.
        assert raw is not None  # for type-checker; _is_set guarantees this
        if req.validator is not None:
            err = _run_validator(req.validator, raw)
            if err:
                status = EnvVarStatus(
                    name=req.name,
                    state="invalid",
                    severity=req.severity,
                    error_message=err,
                    requirement=req,
                )
                statuses.append(status)
                if req.severity == "required":
                    invalid.append(status)
                    is_ok = False
                elif req.severity == "warning":
                    warnings.append(status)
                else:  # optional
                    invalid_optional.append(status)
                continue

        # Present + valid (or no validator).
        statuses.append(
            EnvVarStatus(
                name=req.name,
                state="present",
                severity=req.severity,
                error_message="",
                requirement=req,
            )
        )

    return EnvCheckResult(
        is_ok=is_ok,
        statuses=statuses,
        missing_required=missing_required,
        missing_optional=missing_optional,
        warnings=warnings,
        invalid=invalid,
        invalid_optional=invalid_optional,
    )


def format_human_report(result: EnvCheckResult) -> str:
    """Human-readable multi-line report for stderr or /doctor output.

    Sections, in order:
      1. Header (OK or FAIL summary)
      2. Missing required
      3. Invalid required
      4. Warnings
      5. Missing optional / Invalid optional (compact)
      6. Present (var names only — never values)

    Values are NEVER echoed to avoid leaking secrets back to the
    operator's terminal/logs.
    """
    lines: list[str] = []
    if result.is_ok:
        lines.append("env check: OK")
    else:
        n_miss = len(result.missing_required)
        n_inv = len(result.invalid)
        lines.append(
            f"env check: FAIL ({n_miss} missing required, {n_inv} invalid required)"
        )

    if result.missing_required:
        lines.append("")
        lines.append("MISSING REQUIRED:")
        for s in result.missing_required:
            req = s.requirement
            desc = (req.description if req else "") or "(no description)"
            lines.append(f"  - {s.name}  — {desc}")
            if req and req.default_hint:
                lines.append(f"      hint: {req.default_hint}")

    if result.invalid:
        lines.append("")
        lines.append("INVALID REQUIRED:")
        for s in result.invalid:
            lines.append(f"  - {s.name}: {s.error_message}")

    if result.warnings:
        lines.append("")
        lines.append("WARNINGS:")
        for s in result.warnings:
            req = s.requirement
            desc = (req.description if req else "") or "(no description)"
            err = f" — {s.error_message}" if s.error_message else ""
            lines.append(f"  - {s.name}: {s.state}{err}  ({desc})")

    extras = list(result.missing_optional) + list(result.invalid_optional)
    if extras:
        lines.append("")
        lines.append("OPTIONAL (not required for startup):")
        for s in extras:
            lines.append(f"  - {s.name}: {s.state}")

    present = [s for s in result.statuses if s.state == "present"]
    if present:
        lines.append("")
        lines.append(f"PRESENT ({len(present)}): " + ", ".join(s.name for s in present))

    return "\n".join(lines)


# ── DEFAULT REQUIREMENT LISTS ───────────────────────────────────────────────


def _validate_path_exists(value: str) -> str:
    if not os.path.exists(os.path.expanduser(value)):
        return f"path does not exist: {value}"
    return ""


def _validate_writable_dir(value: str) -> str:
    expanded = os.path.expanduser(value)
    if os.path.exists(expanded) and not os.path.isdir(expanded):
        return f"exists but is not a directory: {expanded}"
    # If it doesn't exist, that's fine — caller is expected to mkdir -p.
    return ""


def _validate_int(value: str) -> str:
    try:
        int(value)
    except ValueError:
        return f"not an integer: {value!r}"
    return ""


REQUIRED_FOR_DAEMON: tuple[EnvRequirement, ...] = (
    EnvRequirement(
        name="STATE_DIR",
        severity="required",
        description="Directory for daemon state / checkpoints",
        validator=_validate_writable_dir,
        default_hint="~/.stealth/state",
    ),
    EnvRequirement(
        name="CHROME_EXECUTABLE",
        severity="required",
        description="Path to the Chrome/Chromium binary",
        validator=_validate_path_exists,
        default_hint="/usr/bin/chromium  (Linux)  or  /Applications/Google Chrome.app/Contents/MacOS/Google Chrome  (macOS)",
    ),
    EnvRequirement(
        name="CHROME_PORT",
        severity="warning",
        description="CDP port for Chrome (defaults to 9999 if missing)",
        validator=_validate_int,
        default_hint="9999",
    ),
    EnvRequirement(
        name="LOG_DIR",
        severity="warning",
        description="Directory for runtime logs",
        validator=_validate_writable_dir,
        default_hint="~/.stealth/logs",
    ),
)


REQUIRED_FOR_LIVE_RUN: tuple[EnvRequirement, ...] = REQUIRED_FOR_DAEMON + (
    EnvRequirement(
        name="TWOCAPTCHA_API_KEY",
        severity="warning",
        description=(
            "2Captcha API key. Without ANY captcha key, the captcha "
            "fallback chain is degraded — set at least one of "
            "TWOCAPTCHA_API_KEY / CAPSOLVER_API_KEY for live earning."
        ),
        default_hint="https://2captcha.com → Account → Settings → API Key",
    ),
    EnvRequirement(
        name="OPENAI_API_KEY",
        severity="warning",
        description=(
            "OpenAI API key for the answer engine and/or vision "
            "fallback (#239). Without it, NIM_API_KEY must cover the "
            "primary path."
        ),
        default_hint="https://platform.openai.com/api-keys",
    ),
)


__all__ = [
    "EnvCheckResult",
    "EnvRequirement",
    "EnvVarStatus",
    "REQUIRED_FOR_DAEMON",
    "REQUIRED_FOR_LIVE_RUN",
    "Severity",
    "VarState",
    "check_env",
    "format_human_report",
]
