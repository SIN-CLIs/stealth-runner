"""survey-cli — Standalone Survey Automation CLI (NVIDIA NIM + CDP).

Not a coding agent. Only fills surveys at maximum speed.
Architecture:
  Chrome → Login → Scan → NEMO Loop → AutoDoc → Done

Usage:
  python3 survey.py login         # Login to heypiggy
  python3 survey.py scan          # Scan dashboard for surveys
  python3 survey.py run --id X    # Run one survey
  python3 survey.py loop --max 10 # Auto-loop
  python3 survey.py watch         # Continuous poller
  python3 survey.py balance       # Show current balance
  python3 survey.py doctor        # Self-diagnostic
  python3 survey.py opencode      # Delegate coding task
"""
