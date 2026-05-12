"""================================================================================
stealth-runner / core / config.py  — Zentrale Konfiguration
================================================================================

HERKUNFT
--------
Dieses Modul stammt urspruenglich aus Delqhi/sin-hermes-agent
(.open-auth-rotator/openai/core/config.py) und wurde fuer das
HeyPiggy-Survey-Use-Case angepasst:

  - Default CDP Port: 9999 (HeyPiggy Bot-Profil — NICHT 9336)
  - Default Chrome user_data_dir: ~/.stealth/chrome-profile (nicht /tmp/...)
  - HEYPIGGY_COOKIE_BACKUP wird hier zentral aufgeloest
  - 2captcha API-Key wird hier als optional gefuehrt
  - SurveyBudgetConfig (NEU): 2-Minuten Wallclock-Budget pro Survey

ZWECK
-----
EINE Quelle der Wahrheit fuer ALLES was Environment-abhaengig ist:

  - Welcher Chrome-Port?            → ChromeConfig.port
  - Welche Supabase-Instanz?        → SupabaseConfig.url
  - Wo liegen die Cookies?          → ChromeConfig.heypiggy_cookie_backup
  - Wie viele Retries pro Step?    → RetryConfig.max_retries
  - Wie lang darf eine Survey sein? → SurveyBudgetConfig.max_seconds (120s!)
  - 2captcha API-Key?               → CaptchaConfig.twocaptcha_api_key

DESIGN-PRINZIPIEN
-----------------
1. IMMUTABILITY (frozen=True): Konfiguration wird einmal geladen und ist
   danach unveraenderlich. Verhindert "wer hat das geaendert?"-Bugs.
2. ENV-FIRST: Alle Secrets ausschliesslich aus Environment Variables —
   niemals in Code committen. .env.example dokumentiert ALLE Keys.
3. ENVIRONMENT-AWARE: development / staging / production / docker — jede
   Umgebung kann eigene Defaults haben (z. B. Chrome-Path differs auf Linux).
4. VALIDATION-FIRST: Config.validate() liefert eine Liste konkreter Fehler.
   Bei Production-Start fail-fast wenn Pflicht-Keys fehlen.

LIFECYCLE
---------
  Config.load()              ← Factory, auto-detected Environment
       │
       ▼
  validate()                 ← Pflicht vor Production-Use
       │
       ▼
  via get_config() (singleton im __init__.py) ueberall im Code abrufbar

BANNED
------
- Keine globalen MUTABLE Konfigurationen
- Keine hardcoded Secrets, Tokens, Passwoerter
- Keine direkten os.environ-Zugriffe in anderen Modulen
  (immer via Config.<sub>.from_env() Klasse)
================================================================================"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

# ── ENVIRONMENT-DETECTION ──────────────────────────────────────────────────────


class Environment(Enum):
    """Deployment-Umgebung. Steuert Defaults & feature flags.

    Detection-Reihenfolge (siehe detect()):
      1. IS_DOCKER=1     → DOCKER
      2. ENV=production  → PRODUCTION
      3. ENV=staging     → STAGING
      4. sonst           → DEVELOPMENT

    Warum nicht NODE_ENV? Wir sind in Python — ENV ist die etablierte
    Konvention fuer Python-Apps (12-factor).
    """

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    DOCKER = "docker"

    @classmethod
    def detect(cls) -> Environment:
        if os.environ.get("IS_DOCKER") == "1":
            return cls.DOCKER
        env_val = os.environ.get("ENV", "").lower()
        if env_val == "production":
            return cls.PRODUCTION
        if env_val == "staging":
            return cls.STAGING
        return cls.DEVELOPMENT


# ── CHROME-CONFIG ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ChromeConfig:
    """Chrome-Browser Konfiguration fuer den HeyPiggy-Bot-Profil.

    KRITISCHE FELDER:
      port:                 CDP Port — IMMER 9999 fuer HeyPiggy-Bot.
                            Ports 9336 / 9222 sind SIN-Hermes / Docker-Convention.
      heypiggy_cookie_backup: Pfad zur Session-Cookie-Datei. Wird beim
                            inject_cookies-Node geladen.
      force_renderer_accessibility:
                            MUSS True sein. Ohne dieses Flag liefert
                            Accessibility.getFullAXTree nur den Top-Frame.
                            Siehe AGENTS.md "KANONISCHE ARCHITEKTUR".

    NICHT VERAENDERN ohne AGENTS.md zu updaten.
    """

    port: int = 9999
    host: str = "127.0.0.1"
    user_data_dir: str = field(
        default_factory=lambda: os.path.expanduser("~/.stealth/chrome-profile")
    )
    profile_directory: str = "Default"
    pid_file: str = "/tmp/stealth_chrome.pid"
    executable: str = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    stabilization_delay: float = 4.0
    startup_timeout: int = 30
    force_renderer_accessibility: bool = True
    heypiggy_cookie_backup: str = field(
        default_factory=lambda: os.path.expanduser(
            "~/.stealth/heypiggy-backup/heypiggy-cookies.json"
        )
    )

    @property
    def cdp_url(self) -> str:
        """HTTP-Basis-URL fuer das DevTools-Protocol — z. B. fuer Tab-Discovery
        via /json. WebSocket-URL bekommt man PRO TAB aus dem /json-Response.
        """
        return f"http://{self.host}:{self.port}"

    @classmethod
    def from_env(cls) -> ChromeConfig:
        """Liest CHROME_* env vars. Production-ready: alle Defaults bleiben
        konstant, env vars sind reine Overrides.

        ENV-Vars:
          CHROME_PORT          — CDP-Debug-Port (default 9999)
          CHROME_HOST          — Bind-Host (default 127.0.0.1)
          CHROME_EXECUTABLE    — Pfad zum Chrome-Binary (system-spezifisch)
          CHROME_USER_DATA_DIR — Profile-Pfad (default ~/.stealth/profile)
        """
        return cls(
            port=int(os.environ.get("CHROME_PORT", "9999")),
            host=os.environ.get("CHROME_HOST", "127.0.0.1"),
            executable=os.environ.get(
                "CHROME_EXECUTABLE",
                cls.__dataclass_fields__["executable"].default,
            ),
            user_data_dir=os.environ.get(
                "CHROME_USER_DATA_DIR",
                cls.__dataclass_fields__["user_data_dir"].default_factory(),
            ),
        )

    @classmethod
    def for_docker(cls) -> ChromeConfig:
        """Docker-Defaults: anderer Pfad, kein macOS-Chrome."""
        return cls(
            port=9222,
            user_data_dir="/tmp/chrome_docker_profile",
            executable="/usr/bin/google-chrome",
            stabilization_delay=2.0,
        )


# ── SUPABASE-CONFIG ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SupabaseConfig:
    """Supabase fuer optional distributed state + audit-sync.

    Wird NICHT benoetigt fuer lokalen Single-Machine-Betrieb. Erst wenn
    mehrere Worker parallel laufen sollen oder Audit-Logs zentral
    persistiert werden, ist Supabase Pflicht.
    """

    url: str = ""
    anon_key: str = ""
    audit_table: str = "stealth_audit_log"
    metrics_table: str = "stealth_metrics"
    pipeline_state_table: str = "stealth_pipeline_state"

    @classmethod
    def from_env(cls) -> SupabaseConfig:
        return cls(
            url=os.environ.get("SUPABASE_URL", ""),
            anon_key=os.environ.get("SUPABASE_ANON_KEY", ""),
        )

    def validate(self) -> bool:
        return bool(self.url and self.anon_key)


# ── SECURITY-CONFIG ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SecurityConfig:
    """Encryption + Session-Management.

    encryption_key: Wird fuer Fernet (AES-128-CBC + HMAC-SHA256) genutzt.
                    Wenn leer → CredentialVault faellt auf XOR-Obfuskation
                    zurueck (NICHT production-tauglich!).
                    Generation: python -c "from cryptography.fernet import
                    Fernet; print(Fernet.generate_key().decode())"
    """

    encryption_key: str = ""
    max_login_attempts: int = 3
    session_timeout: int = 3600
    audit_retention_days: int = 90

    @classmethod
    def from_env(cls) -> SecurityConfig:
        return cls(encryption_key=os.environ.get("ENCRYPTION_KEY", ""))


# ── RETRY-CONFIG ───────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RetryConfig:
    """Retry-Verhalten fuer ErrorHandler.

    Defaults sind survey-tauglich:
      max_retries=3   : 1× normal + 3× retry = 4 attempts max
      base_delay=1.0  : Start bei 1s, exponentiell
      max_delay=15.0  : Hartes Cap — 15s ist viel fuer eine 120s-Survey!
      jitter=True     : Random 0.5–1.5× Multiplikator gegen Thundering Herd
    """

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 15.0
    exponential_base: float = 2.0
    jitter: bool = True


# ── CAPTCHA-CONFIG ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CaptchaConfig:
    """Captcha-Solver Konfiguration.

    twocaptcha_api_key: Wird als generischer Fallback genutzt wenn KEIN
                        nativer Solver fuer einen Captcha-Typ existiert.
                        Siehe stealth-captcha/.../twocaptcha_fallback.py.
                        Ohne Key → solve faellt fehl mit
                        reason='no_solver_for_type'.
    max_solve_seconds:  Hartes Timeout pro Solve-Versuch. 60s ist
                        2captcha-Realistic; laenger waere innerhalb des
                        120s Survey-Budgets nicht mehr leistbar.
    """

    twocaptcha_api_key: str = ""
    capsolver_api_key: str = ""
    max_solve_seconds: int = 60

    @classmethod
    def from_env(cls) -> CaptchaConfig:
        return cls(
            twocaptcha_api_key=os.environ.get("TWOCAPTCHA_API_KEY", ""),
            capsolver_api_key=os.environ.get("CAPSOLVER_API_KEY", ""),
            max_solve_seconds=int(os.environ.get("CAPTCHA_SOLVE_TIMEOUT_S", "60")),
        )

    @property
    def has_fallback_solver(self) -> bool:
        return bool(self.twocaptcha_api_key or self.capsolver_api_key)

    def __repr__(self) -> str:  # noqa: D401 — kurz und buendig
        """Custom repr — KEINE Klartext-API-Keys in Logs/Tracebacks leaken!

        Liefert nur das letzte 4-Zeichen-Suffix (z.B. "...xyz1") oder
        "<unset>" wenn leer. Wichtig fuer Production: Sentry/Logging-Tools
        recorden gern repr(config) bei Errors — ohne diese Redaction landet
        der Key dann im Sentry-Issue.
        """

        def _mask(s: str) -> str:
            return "<unset>" if not s else f"...{s[-4:]}"

        return (
            f"CaptchaConfig("
            f"twocaptcha_api_key={_mask(self.twocaptcha_api_key)}, "
            f"capsolver_api_key={_mask(self.capsolver_api_key)}, "
            f"max_solve_seconds={self.max_solve_seconds})"
        )


# ── SURVEY-BUDGET-CONFIG ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class SurveyBudgetConfig:
    """Production-Budget pro Survey-Run (CRITICAL fuer ROI).

    User-Vorgabe: "eine umfrage sollte nicht laenger als 2 min dauern".
    Wenn der Agent laenger braucht, ist die Umfrage entweder:
      - Disqualifiziert (screen_out aber nicht detected)
      - In einem Stuck-Loop (Captcha den wir nicht loesen koennen)
      - Eine 30-Minuten-Brand-Studie (selten und nicht profitabel)
    In ALLEN Faellen ist Abbruch besser als weiterlaufen.

    max_seconds=120         : Wallclock-Limit pro Survey-Run
    max_iterations=15       : LangGraph NEMO-Loop-Cap (entspricht ~30 Seiten)
    iteration_warn_after=10 : Log-Warnung, wahrscheinlich stuck
    soft_kill_at_pct=0.85   : Bei 85 % (102s) signalisieren — kein Captcha mehr
    hard_kill_at_pct=1.0    : Bei 100 % (120s) → state.status="error"
    """

    max_seconds: float = 120.0
    max_iterations: int = 15
    iteration_warn_after: int = 10
    soft_kill_at_pct: float = 0.85
    hard_kill_at_pct: float = 1.0

    @classmethod
    def from_env(cls) -> SurveyBudgetConfig:
        return cls(
            max_seconds=float(os.environ.get("SURVEY_MAX_SECONDS", "120")),
            max_iterations=int(os.environ.get("SURVEY_MAX_ITERATIONS", "15")),
        )

    @property
    def soft_kill_seconds(self) -> float:
        return self.max_seconds * self.soft_kill_at_pct

    @property
    def hard_kill_seconds(self) -> float:
        return self.max_seconds * self.hard_kill_at_pct


# ── HAUPT-CONFIG ───────────────────────────────────────────────────────────────


@dataclass
class Config:
    """Aggregat aller Sub-Configs. Single Source of Truth.

    Usage (typisch):
      from core import get_config
      cfg = get_config()
      port = cfg.chrome.port            # 9999
      budget = cfg.budget.max_seconds   # 120.0

    Validation in Production-Pfad:
      ok, errors = cfg.validate()
      if not ok:  raise SystemExit(f"Config invalid: {errors}")
    """

    environment: Environment = field(default_factory=Environment.detect)
    chrome: ChromeConfig = field(default_factory=ChromeConfig.from_env)
    supabase: SupabaseConfig = field(default_factory=SupabaseConfig.from_env)
    security: SecurityConfig = field(default_factory=SecurityConfig.from_env)
    retry: RetryConfig = field(default_factory=RetryConfig)
    captcha: CaptchaConfig = field(default_factory=CaptchaConfig.from_env)
    budget: SurveyBudgetConfig = field(default_factory=SurveyBudgetConfig.from_env)

    # ── Runtime-Pfade ────────────────────────────────────────────────────────
    # Werden NACH __post_init__ angelegt (mkdir) — kein Fehler wenn schon da.
    tmp_dir: Path = field(default_factory=lambda: Path("/tmp"))
    log_dir: Path = field(default_factory=lambda: Path(os.path.expanduser("~/.stealth/logs")))
    screenshot_dir: Path = field(
        default_factory=lambda: Path(os.path.expanduser("~/.stealth/screenshots"))
    )
    checkpoint_dir: Path = field(
        default_factory=lambda: Path(os.path.expanduser("~/.stealth/checkpoints"))
    )

    # ── Feature-Flags ────────────────────────────────────────────────────────
    enable_analytics: bool = True
    enable_audit_logging: bool = True
    enable_health_checks: bool = True
    enable_screenshots_on_error: bool = True
    enable_state_checkpoints: bool = True
    verbose_logging: bool = False

    def __post_init__(self) -> None:
        # Alle Run-Verzeichnisse anlegen (idempotent)
        for d in (self.log_dir, self.screenshot_dir, self.checkpoint_dir):
            try:
                d.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass  # Nicht fatal — z. B. Read-Only FS in CI

        # Docker-Overrides
        if self.environment == Environment.DOCKER:
            object.__setattr__(self, "chrome", ChromeConfig.for_docker())

    # ── Factory ──────────────────────────────────────────────────────────────

    @classmethod
    def load(cls, env: Environment | None = None) -> Config:
        return cls(environment=env or Environment.detect())

    # ── Serialisierung (OHNE Secrets!) ───────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "environment": self.environment.value,
            "chrome": {
                "port": self.chrome.port,
                "force_renderer_accessibility": self.chrome.force_renderer_accessibility,
                "user_data_dir": self.chrome.user_data_dir,
            },
            "supabase_configured": self.supabase.validate(),
            "security_configured": bool(self.security.encryption_key),
            "captcha_fallback_available": self.captcha.has_fallback_solver,
            "budget": {
                "max_seconds": self.budget.max_seconds,
                "max_iterations": self.budget.max_iterations,
            },
            "features": {
                "analytics": self.enable_analytics,
                "audit_logging": self.enable_audit_logging,
                "health_checks": self.enable_health_checks,
                "screenshots_on_error": self.enable_screenshots_on_error,
                "state_checkpoints": self.enable_state_checkpoints,
            },
        }

    # ── Validation ───────────────────────────────────────────────────────────

    def validate(self) -> tuple[bool, list[str]]:
        """Pre-flight check. Liefert (ok, errors).

        Errors sind WARN in development, FATAL in production.
        """
        errors: list[str] = []

        # Production-only: Supabase + Encryption-Key sind Pflicht
        if self.environment == Environment.PRODUCTION:
            if not self.supabase.validate():
                errors.append(
                    "Supabase config incomplete in PRODUCTION "
                    "(SUPABASE_URL, SUPABASE_ANON_KEY required)"
                )
            if not self.security.encryption_key:
                errors.append(
                    "ENCRYPTION_KEY not set in PRODUCTION — "
                    "credential vault will use weak XOR fallback"
                )

        # Audit-Logging benoetigt Encryption fuer Integritaets-Hash-Salting
        if self.enable_audit_logging and not self.security.encryption_key:
            errors.append(
                "Audit logging enabled but ENCRYPTION_KEY not set — "
                "audit integrity hashes are not salted"
            )

        # Chrome-Executable nur ausserhalb Docker pruefen
        if self.environment != Environment.DOCKER:
            chrome_path = Path(self.chrome.executable)
            if not chrome_path.exists():
                errors.append(
                    f"Chrome executable not found: {self.chrome.executable} "
                    "(set CHROME_EXECUTABLE env var)"
                )

        # 2-Minuten-Budget gegen Iterations-Cap plausibilisieren
        # 15 Iterations × ~8s avg = 120s — passt. Bei weniger Iterations
        # bleibt Reserve fuer langsame Seiten.
        if self.budget.max_seconds < 30:
            errors.append("budget.max_seconds < 30 — too tight, surveys won't complete")

        return len(errors) == 0, errors
