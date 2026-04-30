"""TLS-Fingerprinting auf JA4-Basis."""
from __future__ import annotations
from curl_cffi import requests
CHROME_IMPERSONATE = "chrome120"

def get_ja4_fingerprint(url: str) -> dict:
    session = requests.Session()
    resp = session.get(url, impersonate=CHROME_IMPERSONATE)
    return {"ja4": resp.headers.get("ja4", "unknown"), "status": resp.status_code}
