#!/usr/bin/env bash
set -euo pipefail
PID=${1:-$(pgrep -f "Google Chrome" | head -1)}
echo "🔍 Debugging click for PID: $PID"
echo "1️⃣ Window state..."
skylight-cli get-window-state --pid "$PID" 2>&1 | head -1
echo "2️⃣ Primer..."
skylight-cli click --pid "$PID" --x -1 --y -1 2>&1 | head -1
echo "3️⃣ Finding web button..."
ELEMENTS=$(skylight-cli screenshot --pid "$PID" --mode som --include-tree 2>&1)
BUTTON=$(echo "$ELEMENTS" | python3 -c "
import json,sys
for e in json.load(sys.stdin).get('elements',[]):
    if 'AXWebArea' in e.get('path','') and e['role'] in ('AXButton','AXLink'):
        print(e['index']); break
")
echo "   Button index: $BUTTON"
echo "4️⃣ Click..."
skylight-cli click --pid "$PID" --element-index "$BUTTON" 2>&1 | head -1
echo "✅ Done"
