"""E2E Smoketest Suite — 3-Tier Architecture (SR-139).

Tier 1: Mocked CI tests (fast, no network, no browser, runs on every PR)
Tier 2: Nightly replay tests (HAR fixtures, runs on schedule)
Tier 3: Manual real tests (live heypiggy.com, on-demand)

Usage:
    # Tier 1 (CI)
    pytest survey-cli/tests/e2e/test_tier1_mocked.py -v

    # Tier 2 (nightly via workflow)
    pytest survey-cli/tests/e2e/ -m tier2 -v

    # Tier 3 (manual)
    python -m survey.tests.e2e_runner --tier 3
"""

__all__ = ["TIER_MARKERS"]

TIER_MARKERS = {
    "tier1": "Fast mocked CI tests (<15 sec)",
    "tier2": "Nightly HAR replay tests (~2 min)",
    "tier3": "Manual real heypiggy tests (~5 min)",
}
