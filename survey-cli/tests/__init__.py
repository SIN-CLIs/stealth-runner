"""Survey CLI Test Suite.

WARUM: Jede Änderung am Survey-Loop (NEMO, CDP, Provider-Patterns)
kann Regressionen verursachen. Dieses Test-Paket sichert die SOTA
Patterns: detection, execution, runner, snapshot, autodoc.
Alle Tests sind mock-basiert (kein echter Chrome, kein echter NIM).

ARCHITEKTUR: pytest-basiert. Import-Root via sys.path.insert.
Jeder Test isoliert eine Komponente. Ausführung:
  python3 -m pytest tests/ -v
  python3 -m pytest tests/test_detection.py -v
Kein globaler State, keine shared Fixtures.

BANNED METHODS — NIEMALS VERWENDEN:
❌ playstealth launch
❌ webauto-nodriver — ABSOLUT BANNED
❌ cua-driver click (raw index)
❌ --remote-allow-origins=* (ohne Quotes)
❌ /tmp/heypiggy-bot (fixed profile)
❌ Hardcoded PIDs
❌ pkill -f "Google Chrome"
❌ killall Google Chrome
❌ skylight-cli click --element-index
"""

# Survey CLI Test Suite
# Tests for SOTA patterns: detection, execution, runner, snapshot

# Run all tests: python3 -m pytest tests/ -v
# Run specific:  python3 -m pytest tests/test_detection.py -v
