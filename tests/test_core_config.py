"""Tests fuer core.config — Singleton, ENV-Overrides, cdp_url Property."""

from __future__ import annotations

import os

import pytest


def test_get_config_returns_singleton(tmp_config):
    """Zweiter get_config()-Aufruf MUSS dasselbe Objekt liefern."""
    from core import get_config
    a = get_config()
    b = get_config()
    assert a is b, "get_config() must return same instance"


def test_chrome_cdp_url_property(tmp_config):
    """cdp_url MUSS f'http://{host}:{port}' liefern."""
    from core import get_config
    cfg = get_config()
    assert cfg.chrome.cdp_url == f"http://{cfg.chrome.host}:{cfg.chrome.port}"
    assert cfg.chrome.cdp_url.startswith("http://")
    assert ":9999" in cfg.chrome.cdp_url


def test_budget_max_seconds_default(tmp_config):
    """Default Survey-Budget == 120s (Ziel: < 2 Min pro Survey)."""
    from core import get_config
    cfg = get_config()
    assert cfg.budget.max_seconds == 120.0, (
        "Default budget MUST be 120s — siehe AGENTS.md Ziel: "
        "'eine umfrage sollte nicht laenger als 2 min dauern'"
    )


def test_env_override_chrome_port(monkeypatch, tmp_path):
    """CHROME_PORT env var MUSS Default ueberschreiben."""
    monkeypatch.setenv("CHROME_PORT", "12345")
    monkeypatch.setenv("STATE_DIR", str(tmp_path / "s"))
    monkeypatch.setenv("SCREENSHOT_DIR", str(tmp_path / "sc"))
    monkeypatch.setenv("AUDIT_LOG_DIR", str(tmp_path / "a"))
    monkeypatch.setenv("CHROME_EXECUTABLE", "/usr/bin/echo")
    from core import reset_singletons, get_config
    reset_singletons()
    cfg = get_config()
    assert cfg.chrome.port == 12345


def test_twocaptcha_api_key_redaction_safe(tmp_config, monkeypatch):
    """twocaptcha_api_key NICHT im __repr__ ausgegeben."""
    monkeypatch.setenv("TWOCAPTCHA_API_KEY", "supersecret_key_xyz")
    from core import reset_singletons, get_config
    reset_singletons()
    cfg = get_config()
    # API key MUSS gesetzt sein, aber __repr__ darf ihn nicht leaken
    if hasattr(cfg.captcha, "twocaptcha_api_key"):
        assert cfg.captcha.twocaptcha_api_key == "supersecret_key_xyz"
    repr_str = repr(cfg)
    assert "supersecret_key_xyz" not in repr_str, (
        "API key MUST NOT leak in __repr__ — Risk: leaks in logs/tracebacks"
    )


def test_paths_created_on_bootstrap(tmp_config):
    """bootstrap_core() MUSS checkpoint_dir + screenshot_dir + log_dir anlegen.

    Wenn diese Verzeichnisse fehlen, crasht state_manager.save_checkpoint()
    und Screenshots-on-Failure landen nirgendwo.
    """
    import asyncio
    from core import bootstrap_core, get_config
    asyncio.run(bootstrap_core())
    cfg = get_config()
    assert cfg.checkpoint_dir.exists(), f"checkpoint_dir missing: {cfg.checkpoint_dir}"
    assert cfg.screenshot_dir.exists(), f"screenshot_dir missing: {cfg.screenshot_dir}"
    assert cfg.log_dir.exists(), f"log_dir missing: {cfg.log_dir}"
