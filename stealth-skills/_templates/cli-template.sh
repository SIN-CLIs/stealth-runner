#!/bin/bash
# {{SKILL_NAME}} – {{SHORT_DESCRIPTION}}
# Generiert am {{DATE}} aus Session {{SESSION_ID}}

set -euo pipefail
PID="${1:?PID erforderlich}"

{{CAPTURED_COMMANDS}}

echo '{"status":"ok"}'
