#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
# START FASTAPI — 24/7 Survey Automation API
# ═══════════════════════════════════════════════════════════════════════════════
# 
# WARUM dieses Skript?
# → FastAPI muss mit dem .venv Python gestartet werden (nicht System-Python!).
# → .venv hat langgraph, websocket-client, und andere Dependencies installiert.
# → System-Python (3.14) hat diese Packages NICHT → ImportError.
# → Dieses Skript stellt sicher dass der richtige Python-Interpreter verwendet wird.
#
# VERWENDUNG:
#   ./start-api.sh        # Startet API im Vordergrund (mit Logs)
#   ./start-api.sh &      # Startet API im Hintergrund (Daemon)
#   ./start-api.sh --bg   # Startet API als Background-Job mit nohup
#
# BANNED:
#   ❌ NIE System-Python verwenden (python3, /opt/homebrew/bin/python3).
#   ❌ NIE pip ohne venv verwenden.
#   ❌ NIE den .venv Ordner verschieben (Pfade sind hardcoded in venv).
# ═══════════════════════════════════════════════════════════════════════════════

set -euo pipefail

# Pfade
PROJECT_DIR="/Users/jeremy/dev/stealth-runner"
VENV_DIR="$PROJECT_DIR/.venv"
PYTHON="$VENV_DIR/bin/python"
APP="api.main:app"
HOST="0.0.0.0"
PORT="8889"

# Prüfe ob .venv existiert
if [ ! -d "$VENV_DIR" ]; then
    echo "[ERROR] Virtual environment not found at $VENV_DIR"
    echo "[INFO] Run: uv venv $VENV_DIR"
    exit 1
fi

# Prüfe ob Python-Interpreter existiert
if [ ! -f "$PYTHON" ]; then
    echo "[ERROR] Python interpreter not found at $PYTHON"
    echo "[INFO] Virtual environment may be corrupted. Recreate it."
    exit 1
fi

# Prüfe ob uvicorn im venv installiert ist
if ! "$PYTHON" -c "import uvicorn" 2>/dev/null; then
    echo "[ERROR] uvicorn not installed in virtual environment"
    echo "[INFO] Run: uv pip install --python $PYTHON uvicorn fastapi"
    exit 1
fi

echo "[STARTUP] Using Python: $PYTHON ($($PYTHON --version))"
echo "[STARTUP] Starting FastAPI on $HOST:$PORT"
echo "[STARTUP] Background survey loop will start automatically"
echo "[STARTUP] Swagger UI: http://$HOST:$PORT/docs"
echo "[STARTUP] Press Ctrl+C to stop"

# Setze PYTHONPATH damit survey-cli gefunden wird
export PYTHONPATH="$PROJECT_DIR:$PROJECT_DIR/survey-cli:$PYTHONPATH"

# Starte Uvicorn mit venv Python
# --reload: Auto-reload bei Code-Änderungen (nur für Development!).
# --workers 1: Einzelner Worker (Survey-Loop ist single-threaded).
# --loop uvloop: Schnellerer Event-Loop (Performance).
# --log-level info: Normale Logs (debug = zu viel Output).
if [ "${1:-}" == "--bg" ]; then
    # Background-Modus: nohup + disown
    nohup "$PYTHON" -m uvicorn "$APP" \
        --host "$HOST" \
        --port "$PORT" \
        --workers 1 \
        --log-level info \
        > "$PROJECT_DIR/api.log" 2>&1 &
    echo $! > "$PROJECT_DIR/api.pid"
    echo "[STARTUP] API started in background (PID: $!)"
    echo "[STARTUP] Logs: $PROJECT_DIR/api.log"
else
    # Vordergrund-Modus: Ctrl+C stoppt
    "$PYTHON" -m uvicorn "$APP" \
        --host "$HOST" \
        --port "$PORT" \
        --workers 1 \
        --log-level info \
        "$@"
fi
