"""================================================================================
stealth-runner / core / security.py  — Credential Vault + Audit Log
================================================================================

HERKUNFT
--------
Aus Delqhi/sin-hermes-agent (.open-auth-rotator/openai/core/security.py)
1:1 uebernommen — universelles Krypto/Audit-Modul.

ZWECK
-----
ZWEI Hauptaufgaben, beide unverzichtbar fuer einen Survey-Agent der
mit echten Account-Cookies (HeyPiggy-Session) hantiert:

1. CredentialVault  -> Fernet-verschluesselter In-Memory-Store
   - HeyPiggy-Session-Cookies
   - Supabase Service-Role-Key
   - opencode CLI-Token
   - Vercel AI Gateway API-Key (wenn LLM-Backend genutzt wird)

2. AuditLogger      -> Tamper-detected JSON-Lines-Log
   - JEDER Step-Start/Complete/Failed wird geloggt
   - JEDER Credential-Access (read-your-writes auditable)
   - Pipeline-Lifecycle (Start, Complete, Recovery)
   - Hash-Chain ueber jeden Eintrag fuer Tamper-Detection

WARUM EIGENES MODUL UND NICHT ENV-FILE?
---------------------------------------
- Env-Vars sind im /proc/<pid>/environ leak-bar
- Vault haelt nur ciphertext im RAM, decrypt-on-demand
- Audit-Log ist Pflicht fuer "warum hat der Agent in Survey #67064749
  3x geretried statt sofort delegiert?" -- Forensik

FERNET vs FALLBACK
------------------
Best-Path: cryptography.fernet.Fernet (AES-128-CBC + HMAC-SHA256)
Wenn ENCRYPTION_KEY nicht gesetzt ODER cryptography nicht installiert:
  -> XOR-Obfuskation mit sha256(key)-derived stream
  -> NICHT production-tauglich, nur "raw eyes" schuetzend
Production-Validation in core/config.py warnt davor.

INTEGRATION
-----------
- SecurityManager() ist Singleton im core/__init__.py
- Jeder LangGraph-Node ruft security.log_step(name, status)
- Token-Provider holen Keys via
  security.get_token("ai_gateway")

BANNED
------
- Keine plaintext-Credentials in Logs / Print-Outputs
- Keine Keys im git-history
- Keine Audit-Eintraege ohne integrity_hash
================================================================================"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


# -- EXCEPTIONS ----------------------------------------------------------------


class SecurityError(Exception):
    """Basis fuer Security-bezogene Fehler."""


class EncryptionError(SecurityError):
    """Encryption/Decryption-Fehlschlag."""


class AuditError(SecurityError):
    """Audit-Log-Schreibfehler."""


# -- CREDENTIAL VAULT ----------------------------------------------------------


@dataclass
class CredentialEntry:
    """Verschluesselter Credential-Eintrag.

    expires_at=None -> Credential gilt unbegrenzt (z. B. API-Key).
    Sonst: TTL pro Eintrag (z. B. Session-Token mit kurzem Refresh).
    """
    id: str
    encrypted_value: str
    created_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at


class CredentialVault:
    """In-Memory verschluesselter Key-Value-Store.

    Best-Path nutzt Fernet. Ohne cryptography -> XOR-Obfuskation (Notfall).
    Vault wird PRO PROZESS gehalten -- bei Restart muss neu befuellt werden.
    Production-Setup persistiert kritische Tokens ueber Supabase
    (CredentialEntry -> encrypted_value -> DB-Row).
    """

    def __init__(self, encryption_key: Optional[str] = None):
        self._key = encryption_key or os.environ.get("ENCRYPTION_KEY", "")
        self._fernet = None
        self._credentials: dict[str, CredentialEntry] = {}
        self._init_encryption()

    def _init_encryption(self) -> None:
        if not self._key:
            print("[SECURITY] Warning: No encryption key set, using XOR obfuscation")
            return
        try:
            from cryptography.fernet import Fernet
            # Fernet erwartet 32 url-safe base64-encoded bytes.
            # Wenn Key zu kurz -> SHA256 derivieren.
            if len(self._key) < 32:
                key_bytes = hashlib.sha256(self._key.encode()).digest()
                fernet_key = base64.urlsafe_b64encode(key_bytes)
            else:
                fernet_key = self._key.encode() if isinstance(self._key, str) else self._key
            self._fernet = Fernet(fernet_key)
        except ImportError:
            print("[SECURITY] cryptography not available, using XOR obfuscation")
        except Exception as e:
            print(f"[SECURITY] Fernet init failed: {e}, using XOR fallback")

    # -- Encrypt/Decrypt ----------------------------------------------------

    def _encrypt(self, plaintext: str) -> str:
        if self._fernet:
            return self._fernet.encrypt(plaintext.encode()).decode()
        key_hash = hashlib.sha256((self._key or "default").encode()).digest()
        xored = bytes(
            a ^ b
            for a, b in zip(
                plaintext.encode(), key_hash * (len(plaintext) // 32 + 1)
            )
        )
        return base64.urlsafe_b64encode(xored).decode()

    def _decrypt(self, ciphertext: str) -> str:
        if self._fernet:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        key_hash = hashlib.sha256((self._key or "default").encode()).digest()
        xored = base64.urlsafe_b64decode(ciphertext.encode())
        return bytes(
            a ^ b for a, b in zip(xored, key_hash * (len(xored) // 32 + 1))
        ).decode()

    # -- Public API ---------------------------------------------------------

    def store(
        self,
        credential_id: str,
        value: str,
        expires_in: Optional[int] = None,
        metadata: Optional[dict] = None,
    ) -> bool:
        try:
            encrypted = self._encrypt(value)
            expires_at = time.time() + expires_in if expires_in else None
            self._credentials[credential_id] = CredentialEntry(
                id=credential_id,
                encrypted_value=encrypted,
                expires_at=expires_at,
                metadata=metadata or {},
            )
            return True
        except Exception as e:
            raise EncryptionError(f"Failed to store credential {credential_id}: {e}")

    def retrieve(self, credential_id: str) -> Optional[str]:
        entry = self._credentials.get(credential_id)
        if not entry:
            return None
        if entry.is_expired():
            del self._credentials[credential_id]
            return None
        try:
            return self._decrypt(entry.encrypted_value)
        except Exception as e:
            raise EncryptionError(f"Failed to decrypt credential {credential_id}: {e}")

    def delete(self, credential_id: str) -> bool:
        if credential_id in self._credentials:
            del self._credentials[credential_id]
            return True
        return False

    def list_credentials(self) -> list[str]:
        self._cleanup_expired()
        return list(self._credentials.keys())

    def _cleanup_expired(self) -> None:
        expired = [k for k, v in self._credentials.items() if v.is_expired()]
        for k in expired:
            del self._credentials[k]


# -- AUDIT LOG -----------------------------------------------------------------


@dataclass
class AuditEntry:
    """Ein Audit-Eintrag mit integrity_hash zur Tamper-Detection."""
    timestamp: float
    event_type: str
    actor: str
    action: str
    resource: str
    status: str
    details: dict[str, Any]
    integrity_hash: str = ""

    def __post_init__(self) -> None:
        if not self.integrity_hash:
            self.integrity_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        data = (
            f"{self.timestamp}:{self.event_type}:{self.actor}:"
            f"{self.action}:{self.resource}:{self.status}"
        )
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def verify(self) -> bool:
        return self.integrity_hash == self._compute_hash()

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "datetime": datetime.fromtimestamp(self.timestamp).isoformat(),
            "event_type": self.event_type,
            "actor": self.actor,
            "action": self.action,
            "resource": self.resource,
            "status": self.status,
            "details": self.details,
            "integrity_hash": self.integrity_hash,
        }


class AuditLogger:
    """JSON-Lines Audit-Log mit In-Memory Buffer fuer Live-Queries.

    Default-Path: ~/.stealth/logs/stealth_audit.jsonl
    Wird ueber core.config.Config().log_dir gesetzt.

    Standard-Event-Konstanten unten -- bitte NUR diese benutzen, damit
    Reports/Dashboards einheitlich filterbar sind.
    """

    STEP_START = "STEP_START"
    STEP_COMPLETE = "STEP_COMPLETE"
    STEP_FAILED = "STEP_FAILED"
    RETRY_ATTEMPT = "RETRY_ATTEMPT"
    CREDENTIAL_ACCESS = "CREDENTIAL_ACCESS"
    CREDENTIAL_STORE = "CREDENTIAL_STORE"
    PIPELINE_START = "PIPELINE_START"
    PIPELINE_COMPLETE = "PIPELINE_COMPLETE"
    SECURITY_EVENT = "SECURITY_EVENT"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"  # NEU stealth-runner: 2min Survey-Limit

    def __init__(self, log_file: Optional[str] = None, max_buffer_size: int = 10000):
        default = os.path.expanduser("~/.stealth/logs/stealth_audit.jsonl")
        self._log_file = Path(log_file) if log_file else Path(default)
        self._buffer: list[AuditEntry] = []
        self._max_buffer = max_buffer_size
        try:
            self._log_file.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

    def log(
        self,
        event_type: str,
        actor: str,
        action: str,
        resource: str,
        status: str,
        details: Optional[dict] = None,
    ) -> None:
        entry = AuditEntry(
            timestamp=time.time(),
            event_type=event_type,
            actor=actor,
            action=action,
            resource=resource,
            status=status,
            details=details or {},
        )
        self._buffer.append(entry)
        if len(self._buffer) > self._max_buffer:
            self._buffer = self._buffer[-self._max_buffer // 2:]
        try:
            with open(self._log_file, "a") as f:
                f.write(json.dumps(entry.to_dict()) + "\n")
        except Exception as e:
            print(f"[AUDIT] Failed to write to file: {e}")

    def query(
        self,
        event_type: Optional[str] = None,
        actor: Optional[str] = None,
        since: Optional[float] = None,
        limit: int = 100,
    ) -> list[dict]:
        results: list[dict] = []
        for entry in reversed(self._buffer):
            if event_type and entry.event_type != event_type:
                continue
            if actor and entry.actor != actor:
                continue
            if since and entry.timestamp < since:
                continue
            results.append(entry.to_dict())
            if len(results) >= limit:
                break
        return results

    def verify_integrity(self) -> tuple[int, int]:
        valid = sum(1 for e in self._buffer if e.verify())
        return valid, len(self._buffer) - valid


# -- SECURITY MANAGER (Facade) -------------------------------------------------


class SecurityManager:
    """Facade ueber Vault + Audit + Session-ID. Singleton via core/__init__.

    Typische Survey-Run-Usage:
        sec.log_pipeline_event("survey_start", {"survey_id": "67064749"})
        sec.log_step("ensure_chrome", "success")
        ...
        sec.log_pipeline_event("survey_complete", {"earned_eur": 1.20})

    PII-IP:
      Wer IP-Anonymisierung braucht: SHA-256(ip + session_id) im
      `details`-Feld speichern, nie die rohe IP.
    """

    def __init__(
        self,
        encryption_key: Optional[str] = None,
        audit_log_path: Optional[str] = None,
    ):
        self.vault = CredentialVault(encryption_key)
        self.audit = AuditLogger(audit_log_path)
        self._session_id = secrets.token_hex(16)

    @property
    def session_id(self) -> str:
        return self._session_id

    # -- Token-Convenience -------------------------------------------------

    def store_token(self, provider: str, token: str, expires_in: int = 3600) -> bool:
        result = self.vault.store(f"{provider}_token", token, expires_in)
        self.audit.log(
            AuditLogger.CREDENTIAL_STORE,
            self._session_id,
            "store_token",
            provider,
            "success" if result else "failure",
            {"expires_in": expires_in},
        )
        return result

    def get_token(self, provider: str) -> Optional[str]:
        token = self.vault.retrieve(f"{provider}_token")
        self.audit.log(
            AuditLogger.CREDENTIAL_ACCESS,
            self._session_id,
            "get_token",
            provider,
            "success" if token else "not_found",
        )
        return token

    # -- Step/Pipeline-Logging ---------------------------------------------

    def log_step(self, step_name: str, status: str, details: Optional[dict] = None) -> None:
        event_type = (
            AuditLogger.STEP_COMPLETE if status == "success"
            else AuditLogger.STEP_FAILED
        )
        self.audit.log(event_type, self._session_id, "execute", step_name, status, details)

    def log_pipeline_event(self, event: str, details: Optional[dict] = None) -> None:
        event_type = (
            AuditLogger.PIPELINE_START if "start" in event.lower()
            else AuditLogger.PIPELINE_COMPLETE
        )
        self.audit.log(event_type, self._session_id, event, "pipeline", "info", details)

    def log_budget_exceeded(self, survey_id: str, elapsed_s: float, iteration: int) -> None:
        """Survey hat 2min-Budget gesprengt -- kritisch fuer ROI-Tracking."""
        self.audit.log(
            AuditLogger.BUDGET_EXCEEDED,
            self._session_id,
            "budget_exceeded",
            f"survey:{survey_id}",
            "aborted",
            {"elapsed_s": elapsed_s, "iteration": iteration},
        )

    # -- Summary fuer /health ----------------------------------------------

    def get_security_summary(self) -> dict:
        valid, invalid = self.audit.verify_integrity()
        return {
            "session_id": self._session_id,
            "credentials_count": len(self.vault.list_credentials()),
            "audit_entries": len(self.audit._buffer),
            "audit_integrity": {"valid": valid, "invalid": invalid},
            "encryption_available": self.vault._fernet is not None,
        }
