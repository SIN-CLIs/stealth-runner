#!/usr/bin/env python3
"""Entry point for Agent-Toolbox API.

Startet Uvicorn mit der FastAPI App.
  python start_toolbox.py

Umgebungsvariablen:
  API_HOST (default: 0.0.0.0)
  API_PORT (default: 8000)
  API_RELOAD (default: false)
"""

import os
import sys
from pathlib import Path

# Ensure agent-toolbox is importable
sys.path.insert(0, str(Path(__file__).parent / "agent-toolbox"))

import uvicorn

if __name__ == "__main__":
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    reload = os.getenv("API_RELOAD", "false").lower() == "true"

    print(f"🚀 Starting Agent-Toolbox API at http://{host}:{port}")
    print(f"📚 Swagger UI: http://{host}:{port}/docs")
    print(f"🔧 Reload: {reload}")

    uvicorn.run(
        "api.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )
