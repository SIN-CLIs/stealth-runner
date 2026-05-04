# stealth-sync

> **Stealth Suite Module** — Automatic OpenCode session monitoring, semantic analysis, and documentation generation.

## Overview

`stealth-sync` is a Python daemon that monitors OpenCode sessions via the `opencode.db` SQLite database, performs semantic analysis on session messages using NVIDIA NIM APIs (aligning with the Stealth Suite's Nemotron 3 Nano Omni stack), and automatically generates structured documentation.

## Features

- **Database Polling**: Monitors `~/.local/share/opencode/opencode.db` for new sessions and messages
- **Semantic Analysis**: Classifies OpenCode sessions into categories (`fix`, `new`, `refactor`, `doc`) using NVIDIA NIM
- **Structured Output**: Generates YAML/JSON documentation units with session metadata, classifications, and code blocks
- **Integration**: Seamlessly integrates with the Stealth Suite toolchain (stealth-runner, macos-ax-cli, cua-touch, unmask-cli, ax-graph)

## Architecture

```
                         +-----------------------+
                         |    stealth-sync       |
                         |   (Python-Daemon)     |
                         +----------+------------+
                                    |
                                    v
         +--------------------------+--------------------------+
         |                             |                             |
+--------v--------+        +----------v--------+        +----------v--------+
| Datenbank-      |        | NLP / Semantic-   |        | Output-           |
| Poller          |        | Analyse-Engine    |        | Generatoren       |
+-----------------+        +-------------------+        +-------------------+
```

## Installation

```bash
# From the Stealth Suite monorepo or standalone
cd stealth-sync
pip install -e ".[dev]"
```

## Usage

```bash
# Start standard monitoring
stealth-sync monitor

# Auto-document from OpenCode sessions
stealth-sync auto-doc --source opencode --output docs/ai-sessions/

# Summarize a specific session (recursive with sub-agents)
stealth-sync summarize --session ses_XYZ --recursive --format yaml

# Validate AX documentation against skylight-cli
stealth-sync validate-ax-docs --cli skylight-cli
```

## Configuration

Create a `.env` file (or use Infisical):

```bash
# OpenCode DB path (default)
OPENCODE_DB_PATH=~/.local/share/opencode/opencode.db

# NVIDIA NIM API (aligned with Stealth Suite)
NVIDIA_API_KEY=nvapi-...
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1

# Polling interval (seconds)
POLL_INTERVAL=10

# Output directories
OUTPUT_DIR=docs/opencode-sessions/
LOGBOOK_PATH=logbook.stealth.yaml
```

## Integration with Stealth Suite

| Tool | Integration |
|------|-------------|
| **stealth-runner** | `stealth-sync detect` links running Runner sessions with OpenCode sessions |
| **macos-ax-cli** | Auto-updates AX element type documentation from OpenCode sessions |
| **skylight-cli & cua-touch** | Suggests new AX roles discovered in sessions |
| **unmask-cli** | Integrates Playwright fallback solutions as automated tests |
| **ax-graph** | Extends graph with OpenCode session results as nodes |

## Development

```bash
# Run tests
pytest

# Lint
ruff check .

# Type check
mypy src/
```

## License

MIT — see [LICENSE](LICENSE)
