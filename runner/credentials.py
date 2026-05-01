"""
Credentials – lädt aus keyring ODER profiles/jeremy.yaml als Fallback.
"""
import os
from pathlib import Path
from typing import Dict, Optional

SERVICE_NAME = "heypiggy_com"


def _from_profile() -> Dict[str, Optional[str]]:
    profile = Path(__file__).resolve().parent.parent / "profiles" / "jeremy.yaml"
    if profile.exists():
        try:
            import yaml
            data = yaml.safe_load(profile.read_text())
            return {
                "email": data.get("google_email"),
                "password": data.get("google_password"),
            }
        except Exception:
            pass
    return {"email": os.environ.get("GOOGLE_EMAIL"), "password": os.environ.get("GOOGLE_PASSWORD")}


def load_credentials() -> Dict[str, Optional[str]]:
    try:
        import keyring
        email = keyring.get_password(SERVICE_NAME, "email")
        password = keyring.get_password(SERVICE_NAME, "password")
        if email and password:
            return {"email": email, "password": password}
    except Exception:
        pass
    return _from_profile()
