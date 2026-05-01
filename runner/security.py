"""Security Hardening (SOTA #12)."""
from __future__ import annotations
import secrets, shutil, subprocess, tempfile
from pathlib import Path
from typing import Optional

class Security:
    @staticmethod
    def create_temp_profile() -> Path:
        return Path(tempfile.mkdtemp(prefix="stealth_"))
    @staticmethod
    def cleanup_temp_profile(path: Path) -> None:
        if path.exists(): shutil.rmtree(path, ignore_errors=True)
    @staticmethod
    def generate_token(length: int = 32) -> str:
        return secrets.token_hex(length)
    @staticmethod
    def store_keychain(account: str, password: str) -> bool:
        try: subprocess.run(["security", "add-generic-password", "-a", account, "-s", "stealth-runner", "-w", password], capture_output=True, check=True); return True
        except: return False
    @staticmethod
    def get_keychain(account: str) -> Optional[str]:
        try: return subprocess.run(["security", "find-generic-password", "-a", account, "-s", "stealth-runner", "-w"], capture_output=True, text=True, check=True).stdout.strip()
        except: return None
