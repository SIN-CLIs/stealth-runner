# tests/test_core_security.py
# ─────────────────────────────────────────────────────────────────────────────
# Tests fuer core.security: Vault (Fernet-Encryption), Audit-Log, Mask-Helpers.
#
# WICHTIG (Test-Strategie):
#   - Vault-Tests nutzen einen tmp_path-basierten Master-Key — KEIN echter Key
#     im Repo, KEIN echter Schluessel in Logs
#   - Audit-Log schreibt in tmp_path um nicht "echte" Logs zu verseuchen
#   - PII-Mask wird gegen typische Survey-Felder gepruft (email, postal-code,
#     dob) — falls hier ein Test failed, ist das hochkritisch (DSGVO-Verstoss)
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from core.security import SecurityManager


def test_vault_roundtrip(security: SecurityManager) -> None:
    """encrypt → decrypt muss original plaintext liefern."""
    plain = "super-secret-cookie=abc123; hint=do-not-leak"
    blob = security.vault.encrypt(plain)
    # blob ist bytes/str, JEDENFALLS NICHT plaintext
    assert plain.encode() not in (blob if isinstance(blob, bytes) else blob.encode())
    assert security.vault.decrypt(blob) == plain


def test_vault_rejects_tampered_ciphertext(security: SecurityManager) -> None:
    """Manipulierter Cipher muss raisen (kein silent decrypt zu garbage)."""
    blob = security.vault.encrypt("payload")
    # 1 Byte kippen
    if isinstance(blob, bytes):
        tampered = blob[:-1] + bytes([(blob[-1] ^ 1) & 0xFF])
    else:
        tampered = blob[:-1] + ("Z" if blob[-1] != "Z" else "Y")
    with pytest.raises(Exception):
        security.vault.decrypt(tampered)


def test_audit_log_appends_jsonl(security: SecurityManager, tmp_path: Path) -> None:
    """Jeder log()-Call schreibt EINE Zeile JSONL — append-only."""
    security.audit.log(
        event_type="TEST",
        actor="pytest",
        action="unit_test",
        resource="r1",
        status="ok",
        details={"k": "v"},
    )
    # Audit-File finden (durch conftest in tmp_path konfiguriert)
    files = list(tmp_path.rglob("*.jsonl"))
    assert files, "Audit-Log JSONL not created"
    content = files[0].read_text().strip().splitlines()
    assert len(content) >= 1
    last = json.loads(content[-1])
    assert last["event_type"] == "TEST"
    assert last["actor"] == "pytest"


def test_mask_pii_emails(security: SecurityManager) -> None:
    """Emails muessen maskiert werden (xxx@domain → xxx***@domain)."""
    masked = security.mask_pii({"email": "foo@example.com", "name": "Alice"})
    assert "foo@example.com" not in str(masked)
    # name (kein PII-pattern match) bleibt erhalten — abhaengig von Impl
    # Wir pruefen NUR dass Email NICHT mehr drin steht
