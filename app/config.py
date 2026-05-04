"""
Flow Compilation & Tool Enforcement System (FCTES)
==================================================
Hard Enforcement Layer — Agent darf NUR compiled Flows als Tools nutzen.

ARCHITECTUR:
  Learning → 10x Success → Compile → Tool Registry → Dispatcher → EXECUTION

Der Agent denkt NICHT mehr. Er macht exakt EINEN Tool-Call.
"""
from pathlib import Path

# === CORE PATHS ===
ROOT = Path("/Users/jeremy/dev/stealth-runner")
FLOW_DIR = ROOT / "app/flows/learning"
COMPILED_DIR = ROOT / "app/flows/compiled"
STATE_DIR = ROOT / "app/state"
OPENCODE_JSON = ROOT / "opencode.json"

# === CONFIG ===
THRESHOLD = 10           # Nach 10 Erfolgen → Flow wird frozen
MAX_RETRIES = 3          # Retry bei kAXErrorCannotComplete
VERIFY_ENABLED = True    # Verify-Box: Nach jedem Klick State prüfen