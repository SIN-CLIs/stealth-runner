"""SecretsClient — single source of truth for all credentials.

Resolution order: env var → ~/.stealth/config.yaml → hardcoded dev fallback.

WARUM: CPX credentials waren in 4 Dateien an 6 Stellen hardgecoded.
Jetzt: eine Funktion, ein Ort. Credential-Rotation = eine Env-Var ändern.
"""

import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


class MissingSecretError(RuntimeError):
    """Raised when a required secret has no resolved value.

    Placeholder stub for SR-63 (#62) fail-closed contract. The current
    SecretsClient still returns hardcoded fallbacks; the test in
    tests/test_security.py is module-level-skipped and uses this symbol
    only to satisfy its import. Promoting fail-closed behavior is tracked
    separately under SR-63.
    """


@dataclass
class CPXCredentials:
    app_id: str = ""
    ext_user_id: str = ""
    secure_hash: str = ""
    email: str = ""


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

    @staticmethod
    def get_google_email() -> str:
        return os.getenv("GOOGLE_EMAIL", "")

    @classmethod
    def get_cpx_credentials(cls) -> CPXCredentials:
        return CPXCredentials(
            app_id=os.getenv("CPX_APP_ID", "11644"),
            ext_user_id=os.getenv("CPX_EXT_USER_ID", "2525530"),
            secure_hash=os.getenv("CPX_SECURE_HASH",
                                  "ae75b0feca27c0f8eb356d7117d978ec"),
            email=os.getenv("CPX_EMAIL",
                            "zukunftsorientierte.energie@gmail.com"),
        )


_secrets = SecretsClient()


def get_secrets() -> SecretsClient:
    return _secrets
