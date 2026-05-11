"""================================================================================
stealth-runner / core / __init__.py  — Public API + Singleton Wiring
================================================================================

ZWECK
-----
Eine kuratierte Re-Export-Schicht und das einzige zulaessige Bezugs-Tor fuer
Config, ErrorHandler, Vault, AuditLogger, AnalyticsCollector, StateManager.

Andere Module IMPORTIEREN NIE direkt aus core.config/core.security/usw. —
sondern ueber:

    from core import get_config, get_error_handler, get_state_manager
    from core import get_audit_log, get_vault, get_analytics

So bleibt das Wiring an EINER Stelle und Tests koennen die Singletons
mit reset_singletons() saubern.

LIFECYCLE
---------
  1. App-Start (FastAPI lifespan / CLI bootstrap):
        from core import bootstrap_core
        await bootstrap_core()              # Config laden + validieren
  2. Runtime:
        cfg = get_config()                   # idempotent Singleton
  3. Tests:
        from core import reset_singletons
        reset_singletons()                   # vor jedem Test rufen

WARUM SINGLETONS?
-----------------
- Config: einmal laden, ueberall lesen — sonst diverging Env-States
- ErrorHandler: ein zentraler Circuit-Breaker-Store
- AuditLogger: ein zusammenhaengender HMAC-Chain (sonst broken integrity)
- Analytics: Counters/Gauges duerfen nicht zerlegt sein

KONSTRUKTOREN
-------------
Die Modul-Klassen wurden direkt aus sin-hermes-agent uebernommen und nehmen
KEIN `config=` Argument — wir injizieren statt dessen die einzelnen Werte
hier in den Singleton-Gettern. So bleiben die Klassen self-contained und
unabhaengig von Config-Imports (testbar in Isolation).
================================================================================"""

from __future__ import annotations

import logging
import threading
from typing import Optional

from .analytics import AnalyticsCollector
from .config import Config, Environment
from .error_handler import ErrorContext, ErrorHandler, ErrorSeverity, RetryStrategy
from .security import AuditLogger, CredentialVault, SecurityManager
from .state_manager import StateManager
from .survey_budget import BudgetExceededError, SurveyBudget

__all__ = [
    # Klassen (fuer Type-Hints + erweiterte Use-Cases)
    "Config",
    "Environment",
    "ErrorHandler",
    "ErrorContext",
    "ErrorSeverity",
    "RetryStrategy",
    "CredentialVault",
    "AuditLogger",
    "SecurityManager",
    "AnalyticsCollector",
    "StateManager",
    "SurveyBudget",
    "BudgetExceededError",
    # Singleton-Getter (DER empfohlene Weg)
    "get_config",
    "get_error_handler",
    "get_vault",
    "get_audit_log",
    "get_security_manager",
    "get_analytics",
    "get_state_manager",
    # Lifecycle
    "bootstrap_core",
    "reset_singletons",
]

log = logging.getLogger("core")

# ── SINGLETON-STATE ──────────────────────────────────────────────────────────
# Thread-safe lazy initialization — kein eager Side-Effect beim Import,
# damit Tests reset_singletons() rufen koennen ohne Modul-Reload.

_lock = threading.Lock()
_config: Optional[Config] = None
_error_handler: Optional[ErrorHandler] = None
_vault: Optional[CredentialVault] = None
_audit_log: Optional[AuditLogger] = None
_security_manager: Optional[SecurityManager] = None
_analytics: Optional[AnalyticsCollector] = None
_state_manager: Optional[StateManager] = None


def get_config() -> Config:
    """Liefert das geladene Config-Singleton (laed beim ersten Aufruf)."""
    global _config
    if _config is None:
        with _lock:
            if _config is None:
                _config = Config.load()
    return _config


def get_error_handler() -> ErrorHandler:
    """ErrorHandler mit Config-abgeleiteten Retry-Parametern."""
    global _error_handler
    if _error_handler is None:
        with _lock:
            if _error_handler is None:
                cfg = get_config()
                _error_handler = ErrorHandler(
                    max_retries=cfg.retry.max_retries,
                    base_delay=cfg.retry.base_delay,
                    max_delay=cfg.retry.max_delay,
                )
    return _error_handler


def get_vault() -> CredentialVault:
    """Credential Vault mit Encryption-Key aus Config (Env)."""
    global _vault
    if _vault is None:
        with _lock:
            if _vault is None:
                cfg = get_config()
                _vault = CredentialVault(encryption_key=cfg.security.encryption_key or None)
    return _vault


def get_audit_log() -> AuditLogger:
    """Audit-Logger mit Pfad aus Config (log_dir/audit.jsonl)."""
    global _audit_log
    if _audit_log is None:
        with _lock:
            if _audit_log is None:
                cfg = get_config()
                _audit_log = AuditLogger(
                    log_file=str(cfg.log_dir / "stealth_audit.jsonl"),
                )
    return _audit_log


def get_security_manager() -> SecurityManager:
    """Facade ueber Vault + Audit — teilt sich KEINE Instanzen mit den
    Solo-Gettern get_vault()/get_audit_log() (Design des SecurityManager
    erzeugt eigene). Bei Bedarf koennen wir spaeter einen Facade-Re-Use bauen.
    """
    global _security_manager
    if _security_manager is None:
        with _lock:
            if _security_manager is None:
                cfg = get_config()
                _security_manager = SecurityManager(
                    encryption_key=cfg.security.encryption_key or None,
                    audit_log_path=str(cfg.log_dir / "stealth_audit.jsonl"),
                )
    return _security_manager


def get_analytics() -> AnalyticsCollector:
    """Analytics-Collector (in-memory). Prometheus via MetricsExporter
    in analytics.py — separate Lifecycle, nicht hier instanziiert.
    """
    global _analytics
    if _analytics is None:
        with _lock:
            if _analytics is None:
                _analytics = AnalyticsCollector()
    return _analytics


def get_state_manager() -> StateManager:
    """StateManager mit Checkpoint-Dir + Supabase-Sync (wenn konfiguriert)."""
    global _state_manager
    if _state_manager is None:
        with _lock:
            if _state_manager is None:
                cfg = get_config()
                _state_manager = StateManager(
                    checkpoint_dir=str(cfg.checkpoint_dir),
                    supabase_url=cfg.supabase.url or None,
                    supabase_key=cfg.supabase.anon_key or None,
                )
    return _state_manager


async def bootstrap_core() -> Config:
    """Eager-init aller Singletons + fail-fast Validation.

    Im FastAPI lifespan vor `yield` aufrufen — wenn Config invalide ist,
    crasht der Service beim Start (gewollt: lieber fail-fast als verstecktes
    Runtime-Failure mitten in einer Survey).
    """
    cfg = get_config()
    ok, errors = cfg.validate()
    if not ok:
        for err in errors:
            log.error("core.config.invalid: %s", err)
        if cfg.environment in (Environment.PRODUCTION, Environment.STAGING):
            raise RuntimeError(
                f"core.config.validation_failed ({len(errors)} errors): "
                + "; ".join(errors)
            )
        log.warning(
            "core.config.dev_mode: %d config warnings ignored (non-prod)",
            len(errors),
        )

    # Eager-init laesst Probleme (z. B. fehlendes Crypto-Modul) sofort auffallen
    get_error_handler()
    get_security_manager()
    get_analytics()
    sm = get_state_manager()
    await sm.bootstrap()  # legt runs/-Folder an, idempotent
    log.info(
        "core.bootstrap.ok env=%s budget_max=%ds",
        cfg.environment.value,
        cfg.budget.max_seconds,
    )
    return cfg


def reset_singletons() -> None:
    """NUR fuer Tests. Setzt alle Singletons zurueck.

    Achtung: aktive DB-Connections / Tasks werden NICHT geschlossen —
    Verantwortung des Test-Setups (pytest-Fixture mit yield + close).
    """
    global _config, _error_handler, _vault, _audit_log
    global _security_manager, _analytics, _state_manager
    with _lock:
        _config = None
        _error_handler = None
        _vault = None
        _audit_log = None
        _security_manager = None
        _analytics = None
        _state_manager = None
