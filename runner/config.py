"""Zentrale Konfiguration – lädt .env und validiert alle Secrets."""
from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
load_dotenv(Path.home() / ".stealth-runner.env")

CF_ACCOUNT_ID = os.getenv("CF_ACCT")
CF_GATEWAY_ID = os.getenv("CF_GATEWAY_ID", "")
CF_API_TOKEN = os.getenv("CF_TOKEN")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
HEYPIGGY_EMAIL = os.getenv("HEYPIGGY_EMAIL", "")
HEYPIGGY_PASSWORD = os.getenv("HEYPIGGY_PASSWORD", "")

MISSING: list[str] = []
if not CF_API_TOKEN:
    MISSING.append("CF_TOKEN")
if not NVIDIA_API_KEY:
    MISSING.append("NVIDIA_API_KEY (optional)")
if MISSING:
    raise EnvironmentError(
        "Fehlende Umgebungsvariablen:\n" + "\n".join(f"  - {m}" for m in MISSING)
        + "\n\nKopiere .env.example nach .env und fülle die Werte aus."
    )
