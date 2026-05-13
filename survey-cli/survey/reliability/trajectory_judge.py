"""================================================================================
TRAJECTORY JUDGE — LLM-based post-run audit of survey trajectories (SR-170, PR1)
================================================================================

MODUL-KONZEPT (SR-170, 2026-05-13)
-----------------------------------

WARUM ÜBERHAUPT?
    Selbst wenn SR-167 (`verifier.py`) und SR-168 (`attestation.py`) jeder
    einzelnen Aktion grünes Licht geben, kann eine *gesamte* Survey-
    Trajektorie trotzdem driften:

      • Persona-Drift: Die Antwort-Sequenz ist intern inkonsistent
        (z. B. "Alter 23" in Frage 1, später Antwort die nur ab 30
        plausibel ist).
      • Compliance-Drift: Der Agent hat Survey-Instruktionen "nahe
        genug" befolgt, aber nicht wörtlich (z. B. Slider auf 80 statt
        explizit gefordert "über 75").
      • Efficiency-Drift: Die Survey wurde abgeschlossen, aber mit
        3× re-do der gleichen Page → Provider-seitiges Bot-Signal.
      • Coherence-Drift: Antworten sehen einzeln korrekt aus, aber die
        Sequenz fühlt sich roboterhaft-monoton an (immer 0,3-Sekunden-
        Latenz, immer Antwort B beim Coin-Flip).

    Diese vier Failure-Modi sind per Definition NICHT pro-Aktion
    detektierbar — sie erfordern eine Bewertung der gesamten Trajektorie
    NACH dem Run.

DIESES MODUL: backend-agnostischer Judge
----------------------------------------
    `TrajectoryJudge` nimmt ein `llm_callable` als Konstruktor-Injection.
    Das macht das Modul:
      • Sofort unit-testbar (mocked callable, deterministisch)
      • Provider-unabhängig (OpenAI ist Default, aber jeder String→String-
        Callable funktioniert — Anthropic, Groq, lokales LLM, …)
      • Wiederverwendbar in CLI-Modus UND Daemon-Modus

    Mirroring-Pattern: identisch zu `attestation.py`'s `ChannelFn`
    Protocol-Injection.

FOUR SCORES (CANONICAL)
-----------------------
    Jede Trajektorie wird auf vier orthogonalen Dimensionen bewertet,
    alle als float ∈ [0.0, 1.0] (1.0 = perfekt, 0.0 = totale Drift):

      compliance — Survey-Instruktionen wörtlich befolgt?
      efficiency — minimaler Step-Count, kein Re-Do?
      accuracy   — Antworten zur Persona-Definition konsistent?
      coherence  — natürliche, mensch-ähnliche Antwort-Sequenz?

    Die LLM liefert JSON: `{"compliance": 0.92, "efficiency": 0.78,
    "accuracy": 0.85, "coherence": 0.90, "rationale": "..."}`. Out-of-
    range oder fehlende Felder → `JudgeError`.

QUARANTINE-INTEGRATION
----------------------
    Wenn `min(scores) < config.quarantine_threshold`, ruft der Caller
    (PR2 graph-wiring) `personas_quarantine.quarantine(persona_id, ...)`
    auf. Dieses Modul selbst macht KEINE Side-Effects. Es liefert nur
    den `JudgeScoreCard`.

LATENCY BUDGET
--------------
    Default: 30 s, $0.005 pro Judge-Call (gpt-4o-mini Annahme). Konfigurierbar
    via `JudgeConfig.max_latency_s`. Der LLM-Call läuft synchron — Judge
    ist Post-Submit, nicht im Hot-Path.

PUBLIC API
----------
    JudgeError           — alle Failure-Modi (parse, range, empty)
    JudgeScoreCard       — frozen dataclass mit 4 Scores + rationale
    JudgeConfig          — tuning knobs
    LLMCallable          — Protocol für injizierbaren LLM-Aufruf
    TrajectoryJudge      — die Klasse
    load_default_prompt  — liest prompts/trajectory_audit.txt
    make_openai_judge    — convenience factory mit OpenAI als Backend

ADD-HERE-TOO CHECKLIST (when extending this module)
----------------------------------------------------
    [ ] New score dimension?  → update JudgeScoreCard, prompt, validator,
        AND test_trajectory_judge.py matrix.
    [ ] New JudgeError subclass? → also extend the test for parse-failure
        modes.
    [ ] New LLM provider? → add factory parallel to make_openai_judge,
        keep TrajectoryJudge itself provider-agnostic.

Module Status: NEW (SR-170 Phase PR1, 2026-05-13)
================================================================================
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Protocol


# ── ERRORS ───────────────────────────────────────────────────────────────────


class JudgeError(Exception):
    """
    Base class for all failures in TrajectoryJudge.

    Subclasses are deliberately small — most call sites just want
    to catch `JudgeError` and route to a "needs human review" lane.
    """


class JudgeParseError(JudgeError):
    """LLM response was not parseable as the expected JSON shape."""


class JudgeRangeError(JudgeError):
    """LLM produced a score outside the [0.0, 1.0] range or NaN."""


class JudgeEmptyTrajectoryError(JudgeError):
    """Judge was called with an empty / None trajectory."""


# ── DATA SHAPES ──────────────────────────────────────────────────────────────


# The four canonical score dimensions. Order is significant — used as the
# stable serialization order in JSON and as the iteration order in tests.
SCORE_FIELDS: tuple[str, ...] = ("compliance", "efficiency", "accuracy", "coherence")


@dataclass(frozen=True)
class JudgeScoreCard:
    """
    Immutable result of a single Judge call over one trajectory.

    Fields:
        compliance:    [0.0, 1.0] — Survey-instructions literally followed?
        efficiency:    [0.0, 1.0] — Minimal step count, no re-do?
        accuracy:      [0.0, 1.0] — Answers consistent with persona profile?
        coherence:     [0.0, 1.0] — Natural human-like response sequence?
        rationale:     Free-form LLM justification, ≤ 500 chars typically.
        model:         Identifier of the LLM used (for audit).
        latency_ms:    Wall-clock time for the LLM call.
        prompt_hash:   First 16 hex chars of sha256(prompt). Lets you
                       group score-cards by prompt-version without
                       leaking the prompt itself into logs.
    """

    compliance: float
    efficiency: float
    accuracy: float
    coherence: float
    rationale: str = ""
    model: str = ""
    latency_ms: int = 0
    prompt_hash: str = ""

    def min_score(self) -> float:
        """Return the lowest of the four scores — used for quarantine triggers."""
        return min(self.compliance, self.efficiency, self.accuracy, self.coherence)

    def mean_score(self) -> float:
        """Return the arithmetic mean of the four scores."""
        return (self.compliance + self.efficiency + self.accuracy + self.coherence) / 4.0

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe representation for log/quarantine-store persistence."""
        return {
            "compliance": self.compliance,
            "efficiency": self.efficiency,
            "accuracy": self.accuracy,
            "coherence": self.coherence,
            "rationale": self.rationale,
            "model": self.model,
            "latency_ms": self.latency_ms,
            "prompt_hash": self.prompt_hash,
        }


# ── INJECTED LLM CONTRACT ────────────────────────────────────────────────────


class LLMCallable(Protocol):
    """
    A judge backend is any callable that takes one prompt string and
    returns one response string.

    The prompt will be the fully-rendered audit prompt (system + user
    parts joined by Judge.build_prompt()). The response is expected to
    be JSON parseable into the 4-score schema; everything else raises
    `JudgeParseError`.

    Pattern: keep the backend dumb. All retry/backoff/cost logic lives
    in the backend implementation, NOT in TrajectoryJudge.

        def my_backend(prompt: str) -> str:
            response = my_llm_sdk.complete(prompt, max_tokens=400)
            return response.text
    """

    def __call__(self, prompt: str) -> str: ...


# ── CONFIG ───────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class JudgeConfig:
    """
    Tuning knobs for TrajectoryJudge.

    Defaults are tuned for gpt-4o-mini-class models over typical survey
    trajectories (5–40 steps, ~2 kB serialized).
    """

    quarantine_threshold: float = 0.55
    """
    Suggested cutoff for the *caller* — if min(scores) < this, the
    caller should quarantine the persona. The Judge itself does NOT
    act on this; it only reports.
    """

    max_latency_s: float = 30.0
    """Soft budget. Exceeded → caller's problem; Judge does not enforce."""

    max_rationale_chars: int = 1000
    """Truncate rationale to this many characters for log-friendliness."""

    require_rationale: bool = True
    """If True and the LLM omits 'rationale', raise JudgeParseError."""


# ── PROMPT LOADING ───────────────────────────────────────────────────────────


_DEFAULT_PROMPT_RELPATH: str = "prompts/trajectory_audit.txt"
"""
Relative to repo root. The library does NOT auto-load this — callers
must explicitly pass the prompt string into the constructor, OR call
`load_default_prompt()` to fetch it.

Why this separation: keeps the library filesystem-coupling-free, which
makes tests deterministic (they inject a fixed prompt string).
"""


def load_default_prompt(base_dir: Optional[Path] = None) -> str:
    """
    Load the canonical audit prompt from disk.

    Search order:
        1. Explicit base_dir argument (if provided).
        2. $STEALTH_RUNNER_ROOT env var (if set).
        3. Current working directory.

    Args:
        base_dir: Optional explicit repo root. If None, auto-detected.

    Returns:
        The prompt as a string.

    Raises:
        FileNotFoundError: prompt file does not exist at the resolved path.
    """
    if base_dir is None:
        env_root = os.environ.get("STEALTH_RUNNER_ROOT")
        base_dir = Path(env_root) if env_root else Path.cwd()
    prompt_path = base_dir / _DEFAULT_PROMPT_RELPATH
    if not prompt_path.is_file():
        raise FileNotFoundError(
            f"Default audit prompt not found at {prompt_path}. "
            f"Either pass `prompt=` explicitly to TrajectoryJudge, "
            f"or set $STEALTH_RUNNER_ROOT to the repo root."
        )
    return prompt_path.read_text(encoding="utf-8")


# ── CORE: TrajectoryJudge ────────────────────────────────────────────────────


@dataclass
class TrajectoryJudge:
    """
    Backend-agnostic LLM judge over a completed survey trajectory.

    Construction (typical):

        judge = TrajectoryJudge(
            llm_callable=my_backend,
            prompt=load_default_prompt(),
            config=JudgeConfig(),
        )

    Or for production with OpenAI:

        judge = make_openai_judge(model="gpt-4o-mini")

    Usage:

        scorecard = judge.audit(trajectory=[...])
        if scorecard.min_score() < judge.config.quarantine_threshold:
            personas_quarantine.quarantine(persona_id, ...)

    Thread-safety: instances are stateless after construction. The
    `llm_callable` it wraps must be safe to call concurrently if the
    Judge is shared across threads.
    """

    llm_callable: LLMCallable
    prompt: str
    config: JudgeConfig = field(default_factory=JudgeConfig)
    model_name: str = "unknown"
    """Free-form identifier the factory sets ('gpt-4o-mini', 'mock', etc.)."""

    def __post_init__(self) -> None:
        if not self.prompt or not self.prompt.strip():
            raise ValueError("TrajectoryJudge requires a non-empty prompt string.")

    # ── PUBLIC ENTRY POINT ───────────────────────────────────────────────

    def audit(self, trajectory: list[dict[str, Any]]) -> JudgeScoreCard:
        """
        Score one trajectory along the four canonical dimensions.

        Args:
            trajectory: ordered list of step records. Each step is a
                        free-form dict; the prompt template renders them
                        as JSON. Empty list → JudgeEmptyTrajectoryError.

        Returns:
            JudgeScoreCard with 4 scores + rationale + audit metadata.

        Raises:
            JudgeEmptyTrajectoryError: trajectory is empty or None.
            JudgeParseError:           LLM response could not be parsed
                                       into the 4-score schema.
            JudgeRangeError:           Any score outside [0.0, 1.0] or NaN.
        """
        if not trajectory:
            raise JudgeEmptyTrajectoryError(
                "audit() called with empty trajectory — refusing to score nothing."
            )

        rendered = self._render_prompt(trajectory)
        t_start = time.perf_counter()
        raw_response = self.llm_callable(rendered)
        latency_ms = int((time.perf_counter() - t_start) * 1000)

        parsed = self._parse_response(raw_response)
        self._validate_scores(parsed)

        rationale = str(parsed.get("rationale", ""))[: self.config.max_rationale_chars]

        return JudgeScoreCard(
            compliance=float(parsed["compliance"]),
            efficiency=float(parsed["efficiency"]),
            accuracy=float(parsed["accuracy"]),
            coherence=float(parsed["coherence"]),
            rationale=rationale,
            model=self.model_name,
            latency_ms=latency_ms,
            prompt_hash=self._prompt_hash(),
        )

    # ── INTERNAL HELPERS ─────────────────────────────────────────────────

    def _render_prompt(self, trajectory: list[dict[str, Any]]) -> str:
        """
        Combine the system prompt with the trajectory payload.

        We use a deliberately simple two-section layout instead of
        f-string templating, because the audit prompt may contain
        curly braces in examples. The LLM sees:

            <system prompt>
            ---
            TRAJECTORY (JSON):
            [...]
        """
        payload = json.dumps(trajectory, ensure_ascii=False, indent=2)
        return f"{self.prompt}\n\n---\nTRAJECTORY (JSON):\n{payload}\n"

    def _parse_response(self, raw: str) -> dict[str, Any]:
        """
        Extract a 4-score JSON object from the raw LLM response.

        Tolerant of:
          - leading/trailing whitespace
          - markdown code fences (```json ... ```)
          - trailing chatter after the JSON block

        Intolerant of:
          - missing required score fields
          - non-numeric score values
          - missing rationale (if config.require_rationale)
        """
        cleaned = raw.strip()
        # Strip a single leading markdown fence, if present.
        if cleaned.startswith("```"):
            # Drop the first line (```json or ```), and try to find the closing ```.
            first_nl = cleaned.find("\n")
            cleaned = cleaned[first_nl + 1 :] if first_nl != -1 else cleaned[3:]
            if "```" in cleaned:
                cleaned = cleaned[: cleaned.rfind("```")]
            cleaned = cleaned.strip()

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise JudgeParseError(
                f"LLM response is not valid JSON: {exc.msg} "
                f"(snippet: {cleaned[:120]!r})"
            ) from exc

        if not isinstance(parsed, dict):
            raise JudgeParseError(
                f"LLM response is JSON but not an object (got {type(parsed).__name__})."
            )

        for field_name in SCORE_FIELDS:
            if field_name not in parsed:
                raise JudgeParseError(
                    f"LLM response missing required score field {field_name!r}. "
                    f"Got keys: {sorted(parsed.keys())}"
                )

        if self.config.require_rationale and "rationale" not in parsed:
            raise JudgeParseError(
                "LLM response missing required 'rationale' field "
                "(set config.require_rationale=False to allow this)."
            )

        return parsed

    def _validate_scores(self, parsed: dict[str, Any]) -> None:
        """
        Range-check each score field. Floats only, finite only, [0.0, 1.0].
        """
        for field_name in SCORE_FIELDS:
            value = parsed[field_name]
            try:
                fvalue = float(value)
            except (TypeError, ValueError) as exc:
                raise JudgeRangeError(
                    f"Score {field_name!r} is not numeric: {value!r}"
                ) from exc
            # NaN check (NaN != NaN).
            if fvalue != fvalue:
                raise JudgeRangeError(f"Score {field_name!r} is NaN.")
            if fvalue < 0.0 or fvalue > 1.0:
                raise JudgeRangeError(
                    f"Score {field_name!r} = {fvalue} out of range [0.0, 1.0]."
                )
            parsed[field_name] = fvalue

    def _prompt_hash(self) -> str:
        """Stable short hash for audit-grouping by prompt version."""
        import hashlib

        return hashlib.sha256(self.prompt.encode("utf-8")).hexdigest()[:16]


# ── CONVENIENCE FACTORY: OPENAI BACKEND ──────────────────────────────────────


def make_openai_judge(
    model: str = "gpt-4o-mini",
    prompt: Optional[str] = None,
    config: Optional[JudgeConfig] = None,
    temperature: float = 0.0,
    max_tokens: int = 400,
    api_key: Optional[str] = None,
) -> TrajectoryJudge:
    """
    Production factory: wires `openai>=1.0` as the LLM backend.

    The OpenAI client is constructed lazily inside the callable so that
    importing this module does NOT require OPENAI_API_KEY to be set —
    which matters for unit tests that import but never call the factory.

    Args:
        model:         OpenAI chat-completion model id.
        prompt:        Audit prompt text. If None, loads via load_default_prompt().
        config:        JudgeConfig override.
        temperature:   0.0 for deterministic scoring (recommended).
        max_tokens:    cap on response tokens; 400 is enough for 4 scores
                       + ~300 chars rationale.
        api_key:       optional explicit key; else uses $OPENAI_API_KEY.

    Returns:
        A wired TrajectoryJudge ready to .audit(...).
    """
    if prompt is None:
        prompt = load_default_prompt()

    def _openai_call(rendered_prompt: str) -> str:
        # Lazy import so that this module is importable without `openai` installed
        # in environments that only use mock callables (e.g. CI unit tests).
        from openai import OpenAI

        client = OpenAI(api_key=api_key) if api_key else OpenAI()
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": rendered_prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        choice = response.choices[0]
        content = choice.message.content
        if content is None:
            raise JudgeParseError("OpenAI returned message.content=None.")
        return content

    return TrajectoryJudge(
        llm_callable=_openai_call,
        prompt=prompt,
        config=config or JudgeConfig(),
        model_name=model,
    )


# ── PUBLIC RE-EXPORTS ────────────────────────────────────────────────────────


__all__ = [
    "SCORE_FIELDS",
    "JudgeConfig",
    "JudgeEmptyTrajectoryError",
    "JudgeError",
    "JudgeParseError",
    "JudgeRangeError",
    "JudgeScoreCard",
    "LLMCallable",
    "TrajectoryJudge",
    "load_default_prompt",
    "make_openai_judge",
]
