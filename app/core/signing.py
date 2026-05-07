"""================================================================================
FCTES FLOW SIGNING — Ed25519 Signatur für Gefrorene Flows
================================================================================

WAS IST DAS?
  Kryptographische Signatur für gefrorene (production) Flows.
  Jeder kompilierte Flow wird Ed25519-signiert. Vor Ausführung wird
  die Signatur geprüft. Verhindert Manipulation gefrorener Flows.

ARCHITEKTUR (Ring 1 — Sicherheit):
  ┌─────────────────────┐
  │  compile()          │
  └─────────────────────┘
         │
         ▼
  ┌─────────────────────┐
  │  sign_flow()        │
  │  (Ed25519)          │
  └─────────────────────┘
         │
         ▼
  ┌─────────────────────┐
  │  .sig Datei         │
  │  (neben .py)         │
  └─────────────────────┘
         │
         ▼
  ┌─────────────────────┐
  │  verify_signature() │
  │  (vor Execution)    │
  └─────────────────────┘

WARUM Ed25519?
  - Schnell: Signieren/Verifizieren in <1ms
  - Sicher: Elliptic Curve Cryptography (256-bit)
  - Kurze Signaturen: 64 Bytes (vs. RSA 2048+ Bytes)
  - Keine Dependencies: cryptography Library (optional)

WARUM Signatur?
  Gefrorene Flows sind immutable. Aber Filesystem ist mutable.
  → Ein Agent/Process könnte eine .py Datei modifizieren.
  → Signatur prüft Integrität vor Ausführung.
  → Falls Signatur ungültig: Execution abgebrochen.

WARUM Ring 1?
  Defense in Depth (Multi-Ring Security):
  - Ring 0: Registry (JSON, wer ist gefroren?)
  - Ring 1: Signatur (kryptographisch, wurde manipuliert?)
  - Ring 2: Dispatcher (nur versionierte Tools)
  - Ring 3: Gatekeeper (konkurrierende Zugriffe blockieren)
  → Mehrere Schutzschichten, jede unabhängig.

DEPENDENZEN:
  - cryptography (pip install cryptography) — OPTIONAL
    Wenn nicht verfügbar: Signatur wird übersprungen (Warnung).
  - ~/.stealth/flow_signing_key.pem (Private Key)
  - ~/.stealth/flow_public_key.pem (Public Key)

BANNED METHODS — NIEMALS VERWENDEN (siehe /banned.md):
  ❌ playstealth launch
  ❌ webauto-nodriver — ABSOLUT BANNED
  ❌ cua-driver click (raw index)
  ❌ --remote-allow-origins=* (ohne Quotes)
  ❌ /tmp/heypiggy-bot (fixed profile)
  ❌ Hardcoded PIDs
  ❌ pkill -f "Google Chrome"
  ❌ killall Google Chrome
  ❌ skylight-cli click --element-index
================================================================================"""
import json
import hashlib
from pathlib import Path
from typing import Optional, Tuple

try:
    from cryptography.hazmat.primitives.asymmetric import ed25519
    from cryptography.hazmat.primitives import serialization
    _CRYPTO_AVAILABLE = True
except ImportError:
    _CRYPTO_AVAILABLE = False

STEALTH_DIR = Path.home() / ".stealth"
SIGNING_KEY_PATH = STEALTH_DIR / "flow_signing_key.pem"
PUBLIC_KEY_PATH = STEALTH_DIR / "flow_public_key.pem"
FLOW_LOCK_PATH = STEALTH_DIR / "flow_lock.json"


def _ensure_keys() -> bool:
    """Generiert Ed25519-Schlüsselpaar falls nicht vorhanden."""
    if not _CRYPTO_AVAILABLE:
        return False
    if SIGNING_KEY_PATH.exists() and PUBLIC_KEY_PATH.exists():
        return True
    STEALTH_DIR.mkdir(parents=True, exist_ok=True)
    private_key = ed25519.Ed25519PrivateKey.generate()
    with open(SIGNING_KEY_PATH, "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ))
    with open(PUBLIC_KEY_PATH, "wb") as f:
        f.write(private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ))
    return True


def sign_flow(flow_path: Path) -> Optional[Path]:
    """Signiert einen Flow und speichert .sig + flow_hash + lock.json."""
    if not _ensure_keys():
        return None
    with open(SIGNING_KEY_PATH, "rb") as f:
        private_key = serialization.load_pem_private_key(f.read(), password=None)
    with open(flow_path, "rb") as f:
        flow_data = f.read()
    signature = private_key.sign(flow_data)
    flow_hash = hashlib.sha256(flow_data).hexdigest()

    sig_path = flow_path.with_suffix(flow_path.suffix + ".sig")
    with open(sig_path, "wb") as f:
        f.write(signature)

    STEALTH_DIR.mkdir(parents=True, exist_ok=True)
    lock = {}
    if FLOW_LOCK_PATH.exists():
        lock = json.loads(FLOW_LOCK_PATH.read_text())
    lock[str(flow_path)] = {
        "hash": flow_hash,
        "sig_file": str(sig_path),
        "signed_at": __import__("time").time()
    }
    FLOW_LOCK_PATH.write_text(json.dumps(lock, indent=2))
    return sig_path


def verify_flow(flow_path: Path) -> Tuple[bool, str]:
    """
    Prüft Signatur und Hash eines Flows.
    Returns: (is_valid, reason)
    """
    if not _CRYPTO_AVAILABLE:
        return False, "cryptography not installed"

    sig_path = flow_path.with_suffix(flow_path.suffix + ".sig")
    if not sig_path.exists():
        return False, f"signature file missing: {sig_path}"

    with open(PUBLIC_KEY_PATH, "rb") as f:
        public_key = serialization.load_pem_public_key(f.read())
    with open(flow_path, "rb") as f:
        flow_data = f.read()
    with open(sig_path, "rb") as f:
        signature = f.read()

    try:
        public_key.verify(signature, flow_data)
    except Exception as e:
        return False, f"signature invalid: {e}"

    if FLOW_LOCK_PATH.exists():
        lock = json.loads(FLOW_LOCK_PATH.read_text())
        entry = lock.get(str(flow_path), {})
        stored_hash = entry.get("hash", "")
        actual_hash = hashlib.sha256(flow_data).hexdigest()
        if stored_hash and stored_hash != actual_hash:
            return False, "hash mismatch — flow tampered"

    return True, "verified"


def verify_signature(flow_path: Path) -> bool:
    """Boolean wrapper für Vorbedingungs-Check (Semgrep-Regel)."""
    valid, _ = verify_flow(flow_path)
    return valid


def get_lock_entry(flow_path: Path) -> Optional[dict]:
    """Gibt den flow_lock-Eintrag zurück (für Registry)."""
    if not FLOW_LOCK_PATH.exists():
        return None
    lock = json.loads(FLOW_LOCK_PATH.read_text())
    return lock.get(str(flow_path))


if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "verify"
    path = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    if cmd == "generate-keys":
        ok = _ensure_keys()
        print("Keys generated" if ok else "cryptography not available")
    elif cmd == "sign" and path:
        sig = sign_flow(path)
        print(f"Signed: {sig}" if sig else "sign failed")
    elif cmd == "verify" and path:
        valid, reason = verify_flow(path)
        print(f"Valid={valid} reason={reason}")