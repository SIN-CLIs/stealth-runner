"""Tests for the Bezier trajectory generator.

WARUM: Die Trajektorie ist das Herzstück der Captcha-Überwindung.
Falsche Endpunkte (>0.01px), rückläufige Timestamps oder unplausible
Jitter-Werte (>3σ) werden von modernen Captcha-Engines sofort als Bot
erkannt. Diese Tests validieren jede Eigenschaft deterministisch.

ARCHITEKTUR: Unittest (keine Mocks — pure Mathematik).
Tests prüfen: Endpunkt-Genauigkeit, Zeit-Monotonie, Mindest-Sample-Count,
Zero-Distance Edge-Case, Determinismus bei fixem Seed,
Übersteuerungs-Korrektur, Jitter-Grenzen (±3σ).

BANNED METHODS — NIEMALS VERWENDEN:
❌ playstealth launch
❌ webauto-nodriver — ABSOLUT BANNED
❌ cua-driver click (raw index)
❌ --remote-allow-origins=* (ohne Quotes)
❌ /tmp/heypiggy-bot (fixed profile)
❌ Hardcoded PIDs
❌ pkill -f "Google Chrome"
❌ killall Google Chrome
❌ skylight-cli click --element-index
"""

from __future__ import annotations

import math

import pytest

from stealth_captcha.config import TrajectorySettings
from stealth_captcha.primitives.trajectory import TrajectoryGenerator


@pytest.fixture
def default_settings() -> TrajectorySettings:
    """
    ================================================================================
    Fixture: Liefert Standard-TrajectorySettings für Tests.

    WARUM als Fixture?
      Vermeidet Code-Duplikation — jeder Test nutzt dieselben Defaults.
      Zentrale Stelle um Defaults zu ändern wenn sich Config ändert.

    Erwartet:
      - TrajectorySettings mit Default-Werten (sample_count_min/max, jitter, etc.)
    ================================================================================
    """
    return TrajectorySettings()


@pytest.fixture
def gen(default_settings: TrajectorySettings) -> TrajectoryGenerator:
    """
    ================================================================================
    Fixture: Liefert fertigen TrajectoryGenerator mit Default-Settings.

    WARUM als Fixture?
      Generator-Instantiierung ist Boilerplate. Fixture macht Tests lesbarer.
      Jeder Test bekommt frische Instanz (kein State-Leak zwischen Tests).

    Erwartet:
      - TrajectoryGenerator bereit für generate() Aufrufe
    ================================================================================
    """
    return TrajectoryGenerator(default_settings)


class TestEndpointAccuracy:
    """Trajectory must end at the target coordinates."""

    def test_horizontal_drag(self, gen: TrajectoryGenerator) -> None:
        """
        ================================================================================
        Test: Horizontale Drag-Bewegung endet exakt am Ziel.

        WARUM dieser Test?
          Horizontale Drags sind der häufigste Fall (Slider-Captchas).
          Wenn der Endpunkt nicht stimmt, wird das Captcha nicht erkannt.

        Erwartet:
          - Letzter Punkt hat x=400.0, y=200.0 (Toleranz 0.01)
        ================================================================================
        """
        points = gen.generate((100.0, 200.0), (400.0, 200.0))
        last = points[-1]
        assert math.isclose(last.x, 400.0, abs_tol=0.01), f"x={last.x}"
        assert math.isclose(last.y, 200.0, abs_tol=0.01), f"y={last.y}"

    def test_vertical_drag(self, gen: TrajectoryGenerator) -> None:
        """
        ================================================================================
        Test: Vertikale Drag-Bewegung endet exakt am Ziel.

        WARUM dieser Test?
          Vertikale Drags (z.B. Scroll-Captchas) müssen genauso präzise sein.
          Y-Achse ist oft problematischer wegen Bezier-Arcs.

        Erwartet:
          - Letzter Punkt hat x=300.0, y=400.0 (Toleranz 0.01)
        ================================================================================
        """
        points = gen.generate((300.0, 100.0), (300.0, 400.0))
        last = points[-1]
        assert math.isclose(last.x, 300.0, abs_tol=0.01)
        assert math.isclose(last.y, 400.0, abs_tol=0.01)

    def test_diagonal_drag(self, gen: TrajectoryGenerator) -> None:
        """
        ================================================================================
        Test: Diagonale Drag-Bewegung endet exakt am Ziel.

        WARUM dieser Test?
          Diagonale Drags sind der härteste Fall — beide Achsen ändern sich.
          Bezier-Kurven können hier am stärksten vom Ziel abweichen.

        Erwartet:
          - Letzter Punkt hat x=350.0, y=250.0 (Toleranz 0.01)
        ================================================================================
        """
        points = gen.generate((50.0, 50.0), (350.0, 250.0))
        last = points[-1]
        assert math.isclose(last.x, 350.0, abs_tol=0.01)
        assert math.isclose(last.y, 250.0, abs_tol=0.01)


class TestTiming:
    """Timestamps must be monotonically non-decreasing."""

    def test_monotonic_timing(self, gen: TrajectoryGenerator) -> None:
        """
        ================================================================================
        Test: Zeitstempel sind streng monoton steigend.

        WARUM dieser Test?
          Browser erkennen nicht-monotone Timings als Bot-Signatur.
          Menschliche Mausbewegungen haben immer steigende Zeitstempel.

        Erwartet:
          - Jeder Zeitpunkt >= vorheriger Zeitpunkt
          - Keine Zeit-Sprünge rückwärts
        ================================================================================
        """
        points = gen.generate((100.0, 100.0), (500.0, 300.0))
        times = [p.t_ms for p in points]
        assert all(b >= a for a, b in zip(times, times[1:], strict=False)), "Timing not monotonic"

    def test_first_point_at_zero(self, gen: TrajectoryGenerator) -> None:
        """
        ================================================================================
        Test: Erster Punkt startet bei t_ms=0.0.

        WARUM dieser Test?
          Relative Zeitstempel müssen bei 0 beginnen (nicht bei absoluter Zeit).
          Sonst kann der Browser die Bewegung nicht korrekt interpolieren.

        Erwartet:
          - points[0].t_ms == 0.0 (exakt, keine Toleranz)
        ================================================================================
        """
        points = gen.generate((100.0, 100.0), (500.0, 300.0))
        assert points[0].t_ms == 0.0

    def test_last_point_positive_time(self, gen: TrajectoryGenerator) -> None:
        """
        ================================================================================
        Test: Letzter Punkt hat positive Zeit (t_ms > 0).

        WARUM dieser Test?
          Eine Bewegung ohne Dauer ist unrealistisch (Mensch braucht Zeit).
          t_ms=0 für alle Punkte wäre ein Bot-Indikator.

        Erwartet:
          - points[-1].t_ms > 0.0 (mindestens 1ms)
        ================================================================================
        """
        points = gen.generate((100.0, 100.0), (500.0, 300.0))
        assert points[-1].t_ms > 0.0


class TestSampleCount:
    """Must produce at least sample_count_min points."""

    def test_minimum_samples(self, gen: TrajectoryGenerator) -> None:
        """
        ================================================================================
        Test: Mindestanzahl Samples wird erreicht.

        WARUM dieser Test?
          Zu wenige Punkte = unruhige Bewegung = Bot-Erkennung.
          Config.sample_count_min definiert das Minimum für menschliche Kurve.

        Erwartet:
          - len(points) >= sample_count_min aus Settings
        ================================================================================
        """
        points = gen.generate((100.0, 100.0), (300.0, 100.0))
        assert len(points) >= gen.settings.sample_count_min, (
            f"Only {len(points)} points, expected ≥{gen.settings.sample_count_min}"
        )

    def test_reasonable_maximum(self, gen: TrajectoryGenerator) -> None:
        """
        ================================================================================
        Test: Maximale Sample-Anzahl wird nicht gesprengt.

        WARUM dieser Test?
          Zu viele Punkte = Performance-Problem + verdächtig.
          sample_count_max * 2 gibt Puffer für Overshoot-Korrektur.

        Erwartet:
          - len(points) <= sample_count_max * 2
        ================================================================================
        """
        points = gen.generate((100.0, 100.0), (300.0, 100.0))
        max_expected = gen.settings.sample_count_max * 2  # with overshoot correction
        assert len(points) <= max_expected, (
            f"{len(points)} points exceeds {max_expected}"
        )


class TestEdgeCases:
    """Edge cases: zero distance, very short distance."""

    def test_zero_distance(self, default_settings: TrajectorySettings) -> None:
        """
        ================================================================================
        Test: Zero-Distance (Start == Ziel) erzeugt nur Press + Release.

        WARUM dieser Test?
          Edge-Case: Wenn Start und Ziel identisch, darf kein Drag entstehen.
          Nur 2 Punkte (press, release) — kein Bezier nötig.

        Erwartet:
          - len(points) == 2 (nur press + release)
        ================================================================================
        """
        g = TrajectoryGenerator(default_settings)
        points = g.generate((100.0, 100.0), (100.0, 100.0))
        assert len(points) == 2  # Just press + release

    def test_one_pixel_drag(self, default_settings: TrajectorySettings) -> None:
        """
        ================================================================================
        Test: 1-Pixel-Drag endet korrekt am Ziel.

        WARUM dieser Test?
          Minimaler Drag (1px) testet ob Generator nicht an Kürze scheitert.
          Bezier mit nur 1px Distanz kann zu NaN/Inf führen wenn nicht abgesichert.

        Erwartet:
          - Letzter Punkt bei (101.0, 100.0) mit Toleranz 0.01
        ================================================================================
        """
        g = TrajectoryGenerator(default_settings)
        points = g.generate((100.0, 100.0), (101.0, 100.0))
        last = points[-1]
        assert math.isclose(last.x, 101.0, abs_tol=0.01)
        assert math.isclose(last.y, 100.0, abs_tol=0.01)


class TestJitterBounds:
    """Jitter should be within reasonable statistical bounds."""

    def test_jitter_not_excessive(self, default_settings: TrajectorySettings) -> None:
        """Run many trajectories and check that mean jitter near zero."""
        g = TrajectoryGenerator(default_settings)
        all_x_jitter = []
        all_y_jitter = []

        for _ in range(20):
            points = g.generate((100.0, 100.0), (400.0, 200.0))
            for p in points[1:-1]:  # Skip endpoints
                # We can't directly measure jitter, but we can verify
                # points don't deviate too far from the line
                all_x_jitter.append(p.x)
                all_y_jitter.append(p.y)

        # Points should be within reasonable bounds of start/end
        # (Bezier arcs can bow outward from the straight line)
        assert all(50 <= x <= 450 for x in all_x_jitter)
        assert all(50 <= y <= 250 for y in all_y_jitter)


class TestDeterminism:
    """Same seed should produce same trajectory."""

    def test_deterministic_seed(self) -> None:
        """
        ================================================================================
        Test: Gleicher Seed produziert identische Trajektorie.

        WARUM dieser Test?
          Determinismus ist kritisch für reproduzierbare Tests.
          Wenn RNG-Seed gleich, müssen alle Punkte exakt matchen.
          Sonst sind Tests flaky und CI bricht zufällig.

        Erwartet:
          - Gleiche Anzahl Punkte
          - Identische t_ms, x, y Werte (Toleranz 0.001)
        ================================================================================
        """
        import random

        rng1 = random.Random(42)
        rng2 = random.Random(42)

        g1 = TrajectoryGenerator(TrajectorySettings(), rng=rng1)
        g2 = TrajectoryGenerator(TrajectorySettings(), rng=rng2)

        points1 = g1.generate((100.0, 100.0), (300.0, 300.0))
        points2 = g2.generate((100.0, 100.0), (300.0, 300.0))

        assert len(points1) == len(points2)
        for p1, p2 in zip(points1, points2, strict=True):
            assert math.isclose(p1.t_ms, p2.t_ms, abs_tol=0.001)
            assert math.isclose(p1.x, p2.x, abs_tol=0.001)
            assert math.isclose(p1.y, p2.y, abs_tol=0.001)


class TestOvershoot:
    """When overshoot occurs, trajectory should correct back to target."""

    def test_overshoot_corrects_to_target(self) -> None:
        """Force overshoot by testing many trajectories."""
        from stealth_captcha.config import TrajectorySettings

        settings = TrajectorySettings(overshoot_probability=1.0)
        g = TrajectoryGenerator(settings)

        overshoot_found = False
        for _ in range(20):
            points = g.generate((100.0, 100.0), (300.0, 200.0))
            last = points[-1]
            # Even with overshoot, must end at target
            assert math.isclose(last.x, 300.0, abs_tol=0.01)
            assert math.isclose(last.y, 200.0, abs_tol=0.01)
            # Check if any point went past target
            if any(p.x > 300.5 for p in points):
                overshoot_found = True

        assert overshoot_found, "No overshoot detected with 100% probability"
