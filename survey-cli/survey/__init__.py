"""survey-cli — Standalone Survey Automation CLI (NVIDIA NIM + CDP).

WARUM: survey-cli ist KEIN Coding-Agent. Seine einzige Aufgabe ist:
Surveys so schnell und zuverlässig wie möglich ausfüllen.
NVIDIA Nemotron 3 Nano Omni für Entscheidungen, CDP WebSocket
für Browser-Interaktionen, Append-Only JSONL für Auto-Doku.

ARCHITEKTUR: Single-Entry-Point (survey.py). Commands: login, scan,
run, loop, watch, balance, doctor, opencode. Login → Dashboard-Scan
→ NEMO Loop (Compact Snapshot → NIM Decision → Batch Execute) →
AutoDoc (earnings.jsonl) → Done. Kein State zwischen Runs.
Nur CLI, kein Library-Import von außen.

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

# daemon submodule — auto-discovered by package loader

__all__ = ["daemon"]
