#!/bin/bash
# build.sh – Kompiliert mac_eye.dylib mit privaten Frameworks
# Voraussetzung: SIP deaktiviert, Xcode CLT installiert

set -e
cd "$(dirname "$0")"

echo "🔨 Baue mac_eye.dylib..."
clang -dynamiclib \
    -F /System/Library/PrivateFrameworks \
    -framework Foundation \
    -framework CoreGraphics \
    -framework IOSurface \
    -framework SkyLight \
    -framework IOKit \
    -framework ApplicationServices \
    -o mac_eye.dylib \
    mac_eye.c 2>&1

echo "✅ mac_eye.dylib gebaut"

if [ -f "entitlements.plist" ]; then
    echo "🔐 Signiere mit privaten Entitlements..."
    codesign --force --sign - --entitlements entitlements.plist mac_eye.dylib 2>/dev/null || echo "⚠️  Signierung fehlgeschlagen (SIP=off ignoriert)"
fi

echo "📦 Fertig: $(pwd)/mac_eye.dylib"
