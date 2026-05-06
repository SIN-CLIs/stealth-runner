"""Centralized configuration via Pydantic Settings (12-factor, env-based).

All settings are camelCase in code but use UPPER_SNAKE_CASE env prefixes.
Override any value via STEALTH_CDP__PORT, STEALTH_TRAJ__DURATION_MAX_MS, etc.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class CDPSettings(BaseSettings):
    """Chrome DevTools Protocol connection.

    Point at an existing Chrome instance, or let StealthBrowser launch one.
    """

    host: str = "127.0.0.1"
    port: int = 9222
    connect_timeout_s: float = 10.0
    command_timeout_s: float = 15.0
    user_data_dir: Path = Field(
        default_factory=lambda: Path.home() / ".stealth-suite" / "chrome-profile"
    )

    model_config = SettingsConfigDict(env_prefix="STEALTH_CDP_")


class TrajectorySettings(BaseSettings):
    """Bezier trajectory generator — tunes the human-likeness of drags."""

    duration_min_ms: int = 800
    duration_max_ms: int = 1600
    sample_count_min: int = 60
    sample_count_max: int = 140
    jitter_y_px: float = 2.0
    jitter_x_px: float = 0.6
    overshoot_probability: float = 0.35
    overshoot_max_px: float = 8.0
    pause_before_release_min_ms: int = 40
    pause_before_release_max_ms: int = 180

    model_config = SettingsConfigDict(env_prefix="STEALTH_TRAJ_")


class SolverSettings(BaseSettings):
    """Retry, timeout, and diagnostics for the solver loop."""

    max_retries: int = 3
    retry_backoff_base_s: float = 1.5
    verify_timeout_s: float = 4.0
    verify_poll_interval_s: float = 0.1
    pre_drag_hit_test: bool = True
    post_drag_hit_test_recovery: bool = True

    model_config = SettingsConfigDict(env_prefix="STEALTH_SOLVER_")


class StealthSettings(BaseSettings):
    """Toggle individual stealth-patch modules.

    All default to True (maximum stealth). Disable any that conflict with
    the target site's behavior.
    """

    enable_navigator_patches: bool = True
    enable_chrome_runtime_patch: bool = True
    enable_webgl_patches: bool = True
    enable_canvas_patches: bool = True
    enable_audio_patches: bool = True
    enable_permissions_patch: bool = True
    enable_plugins_patch: bool = True
    enable_battery_patch: bool = True
    enable_iframe_contentwindow_patch: bool = True

    model_config = SettingsConfigDict(env_prefix="STEALTH_INJECT_")


class MemorySettings(BaseSettings):
    """Episodic experience memory — caches successful trajectories."""

    db_path: Path = Field(
        default_factory=lambda: Path.home() / ".stealth-suite" / "captcha-experience.db"
    )
    max_entries: int = 5000
    similarity_threshold_px: float = 6.0

    model_config = SettingsConfigDict(env_prefix="STEALTH_MEM_")


class ChromeSettings(BaseSettings):
    """Chrome launch flags (only used when StealthBrowser launches Chrome)."""

    binary: str | None = None
    headless: bool = False
    extra_flags: tuple[str, ...] = ()

    model_config = SettingsConfigDict(env_prefix="STEALTH_CHROME_")


class Settings(BaseSettings):
    """Root settings — nested via pydantic."""

    cdp: CDPSettings = Field(default_factory=CDPSettings)
    trajectory: TrajectorySettings = Field(default_factory=TrajectorySettings)
    solver: SolverSettings = Field(default_factory=SolverSettings)
    stealth: StealthSettings = Field(default_factory=StealthSettings)
    memory: MemorySettings = Field(default_factory=MemorySettings)
    chrome: ChromeSettings = Field(default_factory=ChromeSettings)

    log_level: str = "INFO"
    enable_telemetry: bool = True

    model_config = SettingsConfigDict(
        env_prefix="STEALTH_",
        env_nested_delimiter="__",
        env_file=".env",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a singleton Settings, loaded once from env."""
    return Settings()
