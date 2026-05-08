"""SecretsClient — single source of truth for runtime credentials.

Resolution order: env var -> ~/.stealth/config.yaml -> explicit error.

WARUM: CPX credentials waren in mehreren Dateien hardgecoded. Ein zentraler
Client reicht aber nur, wenn er fail-closed ist: echte Defaults im Code sind
weiterhin Credential-Leaks und machen Rotation unzuverlaessig.
"""

import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


@dataclass
class CPXCredentials:
    app_id: str
    ext_user_id: str
    secure_hash: str
    email: str


class MissingSecretError(RuntimeError):
    """Raised when a required runtime secret is not configured."""


class SecretsClient:
    _instance = None
    _config_path = Path.home() / ".stealth" / "config.yaml"

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self):
        self._config = {}
        try:
            if self._config_path.exists():
                import yaml
                with open(self._config_path) as f:
                    self._config = yaml.safe_load(f) or {}
        except Exception:
            pass

    @staticmethod
    def get_nvidia_api_key() -> Optional[str]:
        return os.getenv("NVIDIA_API_KEY")

    @classmethod
    def require_nvidia_api_key(cls) -> str:
        """Return NVIDIA_API_KEY or raise a clear configuration error."""
        value = cls.get_nvidia_api_key()
        if not value:
            raise MissingSecretError("Missing required secret: NVIDIA_API_KEY")
        return value

    @classmethod
    def get_google_email(cls) -> str:
        """Return configured Google login email or raise MissingSecretError."""
        return cls._required("GOOGLE_EMAIL", "google.email")

    @classmethod
    def get_cpx_credentials(cls) -> CPXCredentials:
        """Return complete CPX credentials or raise MissingSecretError."""
        return CPXCredentials(
            app_id=cls._required("CPX_APP_ID", "cpx.app_id"),
            ext_user_id=cls._required("CPX_EXT_USER_ID", "cpx.ext_user_id"),
            secure_hash=cls._required("CPX_SECURE_HASH", "cpx.secure_hash"),
            email=cls._required("CPX_EMAIL", "cpx.email"),
        )

    @classmethod
    def _required(cls, env_name: str, config_key: str) -> str:
        """Resolve a required value from env or config, never from code defaults."""
        value = os.getenv(env_name) or cls._config_value(config_key)
        if value:
            return str(value)
        raise MissingSecretError(f"Missing required secret: {env_name} ({config_key})")

    @classmethod
    def _config_value(cls, dotted_key: str) -> Optional[str]:
        """Read dotted keys from ~/.stealth/config.yaml, if present."""
        config = cls()._config
        current = config
        for part in dotted_key.split("."):
            if not isinstance(current, dict) or part not in current:
                return None
            current = current[part]
        return current


_secrets = SecretsClient()


def get_secrets() -> SecretsClient:
    return _secrets
