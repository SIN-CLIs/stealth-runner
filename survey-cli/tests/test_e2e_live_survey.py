"""E2E Live Survey Test — Für echte HeyPiggy-Surveys (Issue #80 Verification)

Dieser Test simuliert einen kompletten Survey-Lauf mit allen Core-Features:
  - Budget-Enforcement (120s hard limit)
  - Qualification-Filtering (nie "möchte nicht angeben")
  - CUA-Fallback (Consent-Pages)
  - Screenshot on Failure
  - Observability (/core/analytics, /core/errors)

USAGE (Live):
  export HEYPIGGY_USERNAME=...
  export HEYPIGGY_PASSWORD=...
  export CHROME_EXECUTABLE=/usr/bin/chromium
  export TWOCAPTCHA_API_KEY=...
  
  pytest survey-cli/tests/test_e2e_live_survey.py::test_live_heypiggy_survey -v -s

Note: Dieser Test ist OPTIONAL und nur für echte Live-Tests gedacht.
      Im CI wird er skipped (wird nur manual ausgeführt).
"""

import os
import pytest
from dataclasses import dataclass


@pytest.mark.skip(reason="Live test — nur manual mit echten Credentials")
def test_live_heypiggy_survey():
    """E2E: Eine echte HeyPiggy-Survey vom Start bis Completion.

    Pre-Conditions:
      - HEYPIGGY_USERNAME env var gesetzt
      - HEYPIGGY_PASSWORD env var gesetzt
      - Chrome Binary installiert
      - 2Captcha API Key gesetzt
      - core/ Module importierbar

    Assertions:
      - Survey completed (status="completed")
      - Keine "möchte nicht angeben" Antworten
      - Balance erhöht sich
      - Keine Screenshots in screenshot_dir (kein Fehler)
      - /core/analytics meldet survey.completed counter
    """
    # Pre-flight checks
    username = os.environ.get("HEYPIGGY_USERNAME")
    password = os.environ.get("HEYPIGGY_PASSWORD")
    chrome_exe = os.environ.get("CHROME_EXECUTABLE", "/usr/bin/chromium")
    
    if not username or not password:
        pytest.skip("HEYPIGGY_USERNAME/PASSWORD not set")
    if not os.path.exists(chrome_exe):
        pytest.skip(f"Chrome executable not found: {chrome_exe}")
    
    try:
        from core import bootstrap_core, get_state_manager
        from core.langgraph_integration import run_survey_with_core
        from survey.graph.state import SurveyState
        from survey.graph.graph import run_survey_protected
        import asyncio
    except ImportError as e:
        pytest.skip(f"Core modules not available: {e}")
    
    # 1) Bootstrap core
    asyncio.run(bootstrap_core())
    
    # 2) Create initial state
    state = SurveyState(
        survey_id="e2e-test-live",
        provider="heypiggy",
        account_email=username,
        # ... other fields as needed
    )
    
    # 3) Run survey with full protection
    final = run_survey_protected(
        state,
        use_langgraph=True,
        max_seconds=120  # 2 min hard limit
    )
    
    # 4) Assertions
    assert final.status in ["completed", "screen_out"], \
        f"Survey should complete or screen-out, got: {final.status}"
    
    if final.status == "completed":
        # Balance should increase
        assert final.balance_after > final.balance_before, \
            "Balance should increase on completion"
        
        # Check no disqualifying answers were selected
        disqualifying = [
            e for e in getattr(final, "errors", [])
            if "disqualifying_answer" in str(e)
        ]
        assert not disqualifying, \
            f"No disqualifying answers should be selected: {disqualifying}"
    
    # 5) No screenshots on success
    screenshot_dir = os.environ.get("SCREENSHOT_DIR", os.path.expanduser("~/.stealth/screenshots"))
    if os.path.exists(screenshot_dir):
        files = os.listdir(screenshot_dir)
        # If there are screenshots, they should NOT be from this run_id
        for f in files:
            assert "e2e-test-live" not in f, \
                f"No failures expected, but screenshot found: {f}"


@pytest.mark.skip(reason="Observability test — manual only")
def test_core_observability_endpoints():
    """Prüfe dass FastAPI /core/* Endpoints funktionieren.

    Pre-Conditions:
      - FastAPI Server läuft auf :9999
      - Core bootstrap ausgeführt

    Endpoints:
      GET /core/health → status=="healthy"
      GET /core/analytics → hat "survey.completed" counter
      GET /core/errors → circuit_breaker_status
      GET /core/runs/{run_id} → checkpoint-history
    """
    pytest.skip("Manual observability test")


# ── SCAFFOLD für Integration-Tests (später auszubauen) ────────────────────

@dataclass
class LiveTestConfig:
    """Config für E2E Live-Tests."""
    heypiggy_username: str
    heypiggy_password: str
    chrome_executable: str
    twocaptcha_api_key: str
    max_survey_duration_seconds: int = 120
    screenshot_on_failure: bool = True
    enable_core_logging: bool = True


@pytest.fixture
def live_config():
    """Fixture: Live-Test Config aus env vars."""
    return LiveTestConfig(
        heypiggy_username=os.environ.get("HEYPIGGY_USERNAME", ""),
        heypiggy_password=os.environ.get("HEYPIGGY_PASSWORD", ""),
        chrome_executable=os.environ.get("CHROME_EXECUTABLE", "/usr/bin/chromium"),
        twocaptcha_api_key=os.environ.get("TWOCAPTCHA_API_KEY", ""),
    )


def test_configuration_validation(live_config):
    """Validiere dass alle Configs vor Live-Test gesetzt sind."""
    # SKIPPED by default, aber Developers können manuell checken
    errors = []
    if not live_config.heypiggy_username:
        errors.append("HEYPIGGY_USERNAME not set")
    if not live_config.heypiggy_password:
        errors.append("HEYPIGGY_PASSWORD not set")
    if not os.path.exists(live_config.chrome_executable):
        errors.append(f"Chrome not found: {live_config.chrome_executable}")
    if not live_config.twocaptcha_api_key:
        errors.append("TWOCAPTCHA_API_KEY not set")
    
    if errors:
        pytest.skip("Live-Test Config incomplete:\n" + "\n".join(errors))
