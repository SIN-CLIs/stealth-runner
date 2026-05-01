#!/bin/bash
# inject_and_run.sh – Startet Chrome mit injiziertem mac_eye.dylib
# Voraussetzung: SIP deaktiviert (Recovery Mode: csrutil disable)
set -e
MAC_EYE_DYLIB="$(cd "$(dirname "$0")" && pwd)/mac_eye/mac_eye.dylib"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

if [ ! -f "$MAC_EYE_DYLIB" ]; then
    echo "❌ $MAC_EYE_DYLIB fehlt"
    echo "   cd mac_eye && ./build.sh"
    exit 1
fi

if csrutil status | grep -q "enabled"; then
    echo "⚠️  SIP ist AKTIV"
    exit 1
fi

echo "🚀 Chrome mit mac_eye.dylib..."
DYLD_INSERT_LIBRARIES="$MAC_EYE_DYLIB" MAC_EYE_ENABLE=1 "$CHROME" \
    --no-first-run --remote-debugging-port=9222 \
    "https://heypiggy.com/?page=dashboard" &
CHROME_PID=$!

echo "⏳ Warte auf Shared Memory..."
for i in $(seq 1 30); do
    python3 -c "from runner.mac_eye_reader import MacEyeReader; e=MacEyeReader(); print(e.connect())" 2>/dev/null | grep -q "True" && echo "✅ Bereit" && break
    sleep 1
done

echo "👁️ LiveOmniAgent..."
python3 runner/live_agent.py
kill $CHROME_PID 2>/dev/null || true
