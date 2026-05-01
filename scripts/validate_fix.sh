#!/bin/bash
set -euo pipefail

echo "🔍 Validierung der Fixes für FM-003..."

echo "📝 Test 1: --expected-label"
python3 -m pytest tests/test_skylight_expected_label.py -v

echo "📝 Test 2: AXPath"
python3 -m pytest tests/test_axpath.py -v

echo "📝 Test 3: Revalidierung nach type"
python3 -m pytest tests/test_revalidation.py -v

echo "✅ Alle Tests erfolgreich!"