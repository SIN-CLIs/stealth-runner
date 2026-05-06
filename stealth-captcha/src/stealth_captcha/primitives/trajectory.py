"""Human-like Bezier mouse trajectory generator.

Produces a sequence of (t_ms, x, y) samples that mimic a real human drag:
  - Bezier curve with two perpendicular control points → natural arc
  - Ease-out-quint velocity curve → fast start, slow finish (human-like)
  - Micro-jitter on both axes → defeats jerk/acceleration heuristics
  - Optional overshoot + correction → mimics natural imprecision
  - Pre-release micro-pause → human hesitation before release

This is the single most important component for defeating modern captcha
velocity analysis (GoCaptcha, hCaptcha, DataDome).
"""

from __future__ import annotations

import math
import random
import secrets
from dataclasses import dataclass

import numpy as np

from stealth_captcha.config import TrajectorySettings
from stealth_captcha.exceptions import TrajectoryError


@dataclass(slots=True, frozen=True)
class TrajectoryPoint:
    """A single point in the mouse trajectory.

    Attributes:
        t_ms: Milliseconds from the start of the trajectory.
        x: Absolute X coordinate on the page.
        y: Absolute Y coordinate on the page.
    """

    t_ms: float
    x: float
    y: float


def _ease_out_quint(t: float) -> float:
    """Ease-out quintic: fast start, smooth stop.

    This matches human motor control better than linear or ease-in-out.
    """
    return 1.0 - (1.0 - t) ** 5


def _bezier(
    p0: np.ndarray,
    p1: np.ndarray,
    p2: np.ndarray,
    p3: np.ndarray,
    t: float,
) -> np.ndarray:
    """Cubic Bezier interpolation at parameter t ∈ [0, 1]."""
    u = 1 - t
    return (u**3) * p0 + 3 * (u**2) * t * p1 + 3 * u * (t**2) * p2 + (t**3) * p3


@dataclass(slots=True)
class TrajectoryGenerator:
    """Generates human-like drag trajectories.

    Usage:
        gen = TrajectoryGenerator(settings.trajectory)
        points = gen.generate(start=(100, 200), end=(350, 200))
    """

    settings: TrajectorySettings
    rng: random.Random | None = None

    def __post_init__(self) -> None:
        if self.rng is None:
            self.rng = random.Random(secrets.randbits(64))

    def generate(
        self,
        start: tuple[float, float],
        end: tuple[float, float],
    ) -> list[TrajectoryPoint]:
        """Generate a human-like drag trajectory from start to end.

        Args:
            start: (x, y) starting coordinates.
            end: (x, y) target coordinates.

        Returns:
            A list of TrajectoryPoint in chronological order.

        Raises:
            TrajectoryError: if trajectory generation fails.
        """
        rng = self.rng
        if rng is None:
            raise TrajectoryError("RNG not initialized")

        s = self.settings
        sx, sy = start
        ex, ey = end
        dx, dy = ex - sx, ey - sy
        distance = math.hypot(dx, dy)

        # Edge case: near-zero distance → just a click
        if distance < 1.0:
            return [
                TrajectoryPoint(0.0, sx, sy),
                TrajectoryPoint(50.0, ex, ey),
            ]

        duration_ms = rng.uniform(s.duration_min_ms, s.duration_max_ms)
        sample_count = rng.randint(s.sample_count_min, s.sample_count_max)

        # ── Bezier control points ──────────────────────────────────────
        # Perpendicular offset creates a natural arc (humans don't drag
        # in mathematically straight lines).
        nx, ny = -dy / distance, dx / distance
        bow1 = rng.uniform(0.15, 0.45) * distance * rng.choice([-1, 1])
        bow2 = rng.uniform(0.10, 0.35) * distance * rng.choice([-1, 1])

        c1 = np.array([sx + dx * 0.33 + nx * bow1, sy + dy * 0.33 + ny * bow1])
        c2 = np.array([sx + dx * 0.66 + nx * bow2, sy + dy * 0.66 + ny * bow2])
        p0, p3 = np.array([sx, sy]), np.array([ex, ey])

        # ── Optional overshoot ─────────────────────────────────────────
        # Humans often drag a bit past the target and correct.
        overshoot = rng.random() < s.overshoot_probability
        if overshoot:
            ox = rng.uniform(2.0, s.overshoot_max_px)
            ux, uy = dx / distance, dy / distance
            p3 = np.array([ex + ux * ox, ey + uy * ox])

        # ── Generate samples along the Bezier curve ────────────────────
        points: list[TrajectoryPoint] = []
        for i in range(sample_count):
            raw_t = i / (sample_count - 1)
            t = _ease_out_quint(raw_t)
            pos = _bezier(p0, c1, c2, p3, t)
            jitter_x = rng.gauss(0.0, s.jitter_x_px)
            jitter_y = rng.gauss(0.0, s.jitter_y_px)
            time_ms = duration_ms * raw_t
            points.append(
                TrajectoryPoint(
                    time_ms,
                    float(pos[0] + jitter_x),
                    float(pos[1] + jitter_y),
                )
            )

        # ── Overshoot correction ───────────────────────────────────────
        if overshoot:
            correction_samples = rng.randint(8, 18)
            correction_ms = rng.uniform(60.0, 160.0)
            last = points[-1]
            for j in range(1, correction_samples + 1):
                ct = j / correction_samples
                eased = _ease_out_quint(ct)
                px_c = last.x + (ex - last.x) * eased
                py_c = last.y + (ey - last.y) * eased
                points.append(
                    TrajectoryPoint(
                        last.t_ms + correction_ms * ct,
                        px_c + rng.gauss(0.0, 0.3),
                        py_c + rng.gauss(0.0, 0.3),
                    )
                )

        # ── Pre-release pause ──────────────────────────────────────────
        # Humans briefly pause on target before releasing.
        pause_ms = rng.uniform(
            s.pause_before_release_min_ms,
            s.pause_before_release_max_ms,
        )
        last = points[-1]
        points.append(TrajectoryPoint(last.t_ms + pause_ms, ex, ey))

        return points
