# survey-cli — Standalone Survey Automation CLI

**NOT a coding agent.** Only fills surveys at maximum speed.

Part of [SIN-CLIs](https://github.com/SIN-CLIs) Stealth Suite.

## Architecture

```
Chrome → Login → Scan → NEMO Loop → AutoDoc → Done

NEMO Loop (per page):
  1. Compact Snapshot (CDP WebSocket)
  2. NIM Decision (Nemotron 3 Omni)
  3. Batch Execute (CDP WebSocket)
  4. Auto-Document (append-only JSONL)
```

## Quick Start

```bash
# Install
pip install -r requirements.txt

# Login
./survey.py login

# Scan dashboard
./survey.py scan

# Run surveys (auto-loop)
./survey.py loop --max 10

# Or watch continuously
./survey.py watch --interval 60
```

## Commands

| Command | Description |
|---------|-------------|
| `login` | Login to heypiggy via Google OAuth |
| `scan` | Scan dashboard for available surveys |
| `run --id X` | Run a specific survey by ID |
| `run --url URL` | Run survey at direct URL |
| `loop --max 10` | Auto-loop with filtering |
| `watch ` | Continuous poller daemon |
| `balance` | Show current balance + summary |
| `status` | Check Chrome + login + NIM status |
| `doctor` | Full self-diagnostic |
| `kill` | Kill bot Chrome only (safe) |
| `summary` | Earnings summary |
| `opencode` | Delegate coding task to opencode cli |
| `profile` | Show current persona profile |

## Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `NVIDIA_API_KEY` | - | Required for Nemotron 3 Omni |
| `NVIDIA_MODEL` | `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` | NIM model |
| `SURVEY_PORT` | `9999` | CDP port |
| `SURVEY_WAIT` | `3.0` | Wait between actions (s) |
| `SURVEY_DEBUG` | `` | Enable debug output |

## Auto-Documentation

All errors, earnings, and decisions are captured automatically in `logs/` as append-only JSONL:

- `logs/earnings-{date}.jsonl` — Per-survey earnings
- `logs/errors-{date}.jsonl` — Errors with full traceback  
- `logs/sessions-{date}.jsonl` — Session events
- `logs/decisions-{date}.jsonl` — NEMO decisions

**NO LLM writes documentation.** The engine captures everything automatically.

## OpenCode Bridge

When coding tasks are needed (e.g., fixing a survey pattern):

```bash
./survey.py opencode "Add PureSpectrum CAPTCHA OCR solver to providers/purespectrum.py"
```

This dispatches the task to `opencode` CLI and returns the result.
