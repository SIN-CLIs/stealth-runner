# tests/test_twocaptcha_solver.py
# ─────────────────────────────────────────────────────────────────────────────
# Tests fuer den 2Captcha-Generic-Fallback-Solver
# (stealth_captcha.solver.twocaptcha.TwoCaptchaFallbackSolver) und den
# survey-cli-Adapter (survey.captcha_adapters._twocaptcha_solve).
#
# STRATEGIE:
#   - KEIN echter 2Captcha-Call (das wuerde Kosten verursachen + Internet
#     in CI), wir mocken httpx.AsyncClient
#   - DOM-Inject testen wir gegen einen Fake-CDP der `Runtime.evaluate`
#     einfach in ein dict appended
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def test_twocaptcha_params_to_query_hcaptcha() -> None:
    from stealth_captcha.solver.twocaptcha import TwoCaptchaParams
    p = TwoCaptchaParams(captcha_type="hcaptcha",
                          sitekey="abc-def-123",
                          pageurl="https://example.com/survey")
    q = p.to_in_query("KEY")
    assert q["key"] == "KEY"
    assert q["method"] == "hcaptcha"
    assert q["sitekey"] == "abc-def-123"
    assert q["pageurl"] == "https://example.com/survey"
    assert q["json"] == 1


def test_twocaptcha_params_recaptcha_uses_userrecaptcha() -> None:
    from stealth_captcha.solver.twocaptcha import TwoCaptchaParams
    p = TwoCaptchaParams(captcha_type="recaptcha", sitekey="k", pageurl="u")
    q = p.to_in_query("K")
    # 2captcha API method-string fuer reCAPTCHA v2 ist "userrecaptcha"
    assert q["method"] == "userrecaptcha"


def test_twocaptcha_params_turnstile() -> None:
    from stealth_captcha.solver.twocaptcha import TwoCaptchaParams
    p = TwoCaptchaParams(captcha_type="turnstile", sitekey="k", pageurl="u")
    q = p.to_in_query("K")
    assert q["method"] == "turnstile"


def test_inject_token_via_cdp_hcaptcha_uses_correct_selector() -> None:
    """inject_token_via_cdp muss textarea[name=h-captcha-response] schreiben."""
    from stealth_captcha.solver.twocaptcha import inject_token_via_cdp

    calls = []

    class FakeCDP:
        def call_result(self, method, params):
            calls.append((method, params))
            return {"result": {"value": True}}

    ok = inject_token_via_cdp(FakeCDP(), "TOKEN_XYZ", "hcaptcha")
    assert ok is True
    assert any("h-captcha-response" in str(c[1]) for c in calls), \
        f"expected h-captcha-response selector in calls: {calls}"


def test_inject_token_via_cdp_recaptcha_uses_correct_selector() -> None:
    from stealth_captcha.solver.twocaptcha import inject_token_via_cdp

    calls = []

    class FakeCDP:
        def call_result(self, method, params):
            calls.append((method, params))
            return {"result": {"value": True}}

    ok = inject_token_via_cdp(FakeCDP(), "TOK", "recaptcha")
    assert ok is True
    assert any("g-recaptcha-response" in str(c[1]) for c in calls)


def test_inject_token_via_cdp_turnstile_uses_correct_selector() -> None:
    from stealth_captcha.solver.twocaptcha import inject_token_via_cdp

    calls = []

    class FakeCDP:
        def call_result(self, method, params):
            calls.append((method, params))
            return {"result": {"value": True}}

    ok = inject_token_via_cdp(FakeCDP(), "TOK", "turnstile")
    assert ok is True
    assert any("cf-turnstile-response" in str(c[1]) for c in calls)


def test_inject_token_handles_cdp_exception() -> None:
    """Wenn der Inject-JS-Code wirft, darf wir NICHT crashen — return False."""
    from stealth_captcha.solver.twocaptcha import inject_token_via_cdp

    class BadCDP:
        def call_result(self, method, params):
            raise RuntimeError("cdp dead")

    ok = inject_token_via_cdp(BadCDP(), "TOK", "hcaptcha")
    assert ok is False


def test_adapter_returns_api_key_missing_when_no_key(monkeypatch) -> None:
    """captcha_adapters.hcaptcha_solve liefert reason='2captcha:api_key_missing'
    wenn TWOCAPTCHA_API_KEY nicht gesetzt ist."""
    # Wir importieren spaeter, damit core_bootstrap fixture greift
    monkeypatch.delenv("TWOCAPTCHA_API_KEY", raising=False)
    from core import reset_singletons, get_config
    reset_singletons()
    cfg = get_config()
    assert not cfg.captcha.twocaptcha_api_key

    # captcha_adapters muss verfuegbar sein — wenn survey-cli nicht importierbar
    # ist (z.B. langgraph fehlt), skippen wir
    try:
        from survey.captcha_adapters import hcaptcha_solve
    except ImportError:
        pytest.skip("survey-cli not on PYTHONPATH (set in CI conftest)")

    class DummyCDP:
        def call_result(self, method, params):
            return {"result": {"value": "site-key-123"}}

    result = hcaptcha_solve(DummyCDP(), detection=None)
    assert result.solved is False
    assert "api_key_missing" in result.reason
