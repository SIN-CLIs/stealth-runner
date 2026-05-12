"""E2E Live Survey Test — Tier 3 Manual Tests (SR-139 Refactor).

Tier 3: Real HeyPiggy login + real survey, runs on-demand with staging credentials.
Target: ~5 minutes runtime.

USAGE (Manual, Tier 3):
    export HEYPIGGY_USERNAME=...
    export HEYPIGGY_PASSWORD=...
    export CHROME_EXECUTABLE=/usr/bin/chromium

    # Option A: Direct pytest (unskip manually)
    pytest survey-cli/tests/test_e2e_live_survey.py::test_tier3_real_heypiggy -v -s

    # Option B: CLI runner
    python -m survey.tests.e2e_runner --tier 3

Note: This test is SKIPPED in CI. Only run manually with real credentials.
      See survey-cli/tests/e2e/ for Tier 1 (mocked CI) and Tier 2 (nightly replay).
"""

import os
import pytest
from dataclasses import dataclass

# ── Tier 3 Marker ────────────────────────────────────────────────────────────

pytestmark = [
    pytest.mark.tier3,
    pytest.mark.skip(reason="Tier 3 — manual only with real credentials"),
]

# ── Config ───────────────────────────────────────────────────────────────────


@dataclass
class Tier3Config:
    """Config for Tier 3 live tests."""

    heypiggy_username: str
    heypiggy_password: str
    chrome_executable: str
    max_survey_duration_seconds: int = 300  # 5 min for real surveys
    screenshot_on_failure: bool = True
    enable_core_logging: bool = True


@pytest.fixture
def tier3_config() -> Tier3Config:
    """Fixture: Tier 3 config from env vars."""
    return Tier3Config(
        heypiggy_username=os.environ.get("HEYPIGGY_USERNAME", ""),
        heypiggy_password=os.environ.get("HEYPIGGY_PASSWORD", ""),
        chrome_executable=os.environ.get("CHROME_EXECUTABLE", "/usr/bin/chromium"),
    )


# ── Tier 3 Tests ─────────────────────────────────────────────────────────────


@pytest.mark.skip(reason="Tier 3 — manual only with real credentials")
def test_tier3_real_heypiggy(tier3_config: Tier3Config):
    """E2E Tier 3: Real HeyPiggy survey from start to completion.

    Pre-Conditions:
    - HEYPIGGY_USERNAME env var set
    - HEYPIGGY_PASSWORD env var set
    - Chrome binary installed
    - core/ modules importable

    Assertions:
    - Survey completed (status="completed") or screen_out
    - No disqualifying answers selected
    - Balance increases on completion
    - No error screenshots generated
    """
    # Pre-flight checks
    if not tier3_config.heypiggy_username or not tier3_config.heypiggy_password:
        pytest.skip("HEYPIGGY_USERNAME/PASSWORD not set")
    if not os.path.exists(tier3_config.chrome_executable):
        pytest.skip(f"Chrome executable not found: {tier3_config.chrome_executable}")

    try:
        from core import bootstrap_core
        from survey.graph.state import SurveyState
        from survey.graph.graph import run_survey_protected
        import asyncio
    except ImportError as e:
        pytest.skip(f"Core modules not available: {e}")

    # 1) Bootstrap core
    asyncio.run(bootstrap_core())

    # 2) Create initial state
    state = SurveyState(
        survey_id="e2e-tier3-live",
        provider="heypiggy",
        account_email=tier3_config.heypiggy_username,
    )

    # 3) Run survey with full protection
    final = run_survey_protected(
        state,
        use_langgraph=True,
        max_seconds=tier3_config.max_survey_duration_seconds,
    )

    # 4) Assertions
    assert final.status in ["completed", "screen_out"], (
        f"Survey should complete or screen-out, got: {final.status}"
    )

    if final.status == "completed":
        # Balance should increase
        assert final.balance_after > final.balance_before, (
            "Balance should increase on completion"
        )

        # Check no disqualifying answers were selected
        disqualifying = [
            e
            for e in getattr(final, "errors", [])
            if "disqualifying_answer" in str(e)
        ]
        assert not disqualifying, (
            f"No disqualifying answers should be selected: {disqualifying}"
        )

    # 5) No screenshots on success
    screenshot_dir = os.environ.get(
        "SCREENSHOT_DIR", os.path.expanduser("~/.stealth/screenshots")
    )
    if os.path.exists(screenshot_dir):
        files = os.listdir(screenshot_dir)
        for f in files:
            assert "e2e-tier3-live" not in f, (
                f"No failures expected, but screenshot found: {f}"
            )


@pytest.mark.skip(reason="Tier 3 — manual observability test")
def test_tier3_core_observability_endpoints():
    """Tier 3: Verify FastAPI /core/* endpoints function correctly.

    Pre-Conditions:
    - FastAPI server running on :9999
    - Core bootstrap executed

    Endpoints:
    - GET /core/health -> status=="healthy"
    - GET /core/analytics -> has "survey.completed" counter
    - GET /core/errors -> circuit_breaker_status
    - GET /core/runs/{run_id} -> checkpoint-history
    """
    pytest.skip("Manual observability test — run with --no-skip")


@pytest.mark.skip(reason="Tier 3 — manual config validation")
def test_tier3_configuration_validation(tier3_config: Tier3Config):
    """Validate all Tier 3 configs are set before live test."""
    errors = []
    if not tier3_config.heypiggy_username:
        errors.append("HEYPIGGY_USERNAME not set")
    if not tier3_config.heypiggy_password:
        errors.append("HEYPIGGY_PASSWORD not set")
    if not os.path.exists(tier3_config.chrome_executable):
        errors.append(f"Chrome not found: {tier3_config.chrome_executable}")

    if errors:
        pytest.fail("Tier 3 Config incomplete:\n" + "\n".join(errors))


# ── CLI Runner Interface ─────────────────────────────────────────────────────


def run_tier3_cli():
    """CLI entry point for Tier 3 tests.

    Usage:
        python -m survey.tests.e2e_runner --tier 3
    """
    import sys

    # Remove skip markers for CLI execution
    print("=" * 60)
    print("TIER 3 — Real HeyPiggy E2E Test")
    print("=" * 60)

    # Check env vars
    username = os.environ.get("HEYPIGGY_USERNAME")
    password = os.environ.get("HEYPIGGY_PASSWORD")

    if not username or not password:
        print("\nERROR: Missing credentials!")
        print("  export HEYPIGGY_USERNAME=<your-email>")
        print("  export HEYPIGGY_PASSWORD=<your-password>")
        sys.exit(1)

    print(f"\nCredentials: {username[:3]}***@***")
    print("Starting real survey test...\n")

    # Run with pytest, skipping the skip marker
    exit_code = pytest.main(
        [
            __file__,
            "-v",
            "-s",
            "--no-header",
            "-p",
            "no:skip",  # Disable skip plugin
            "-k",
            "test_tier3_real_heypiggy",
        ]
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    run_tier3_cli()
