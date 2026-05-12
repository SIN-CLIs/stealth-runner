#!/usr/bin/env python3
"""Compatibility delegator for the canonical survey-cli entry point.

The active survey engine lives in `survey-cli/survey.py` and `survey-cli/survey/`.
This root script only maps the historical `--mode ...` interface to the canonical
subcommands so old invocations keep working without maintaining a second engine.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SURVEY_CLI_DIR = ROOT / "survey-cli"
SURVEY_ENTRY = SURVEY_CLI_DIR / "survey.py"


def _legacy_to_canonical(argv: list[str]) -> list[str]:
    """Map old root flags to canonical survey-cli subcommands."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--mode", choices=["legacy", "nim", "scan", "loop", "snapshot"], default="scan"
    )
    parser.add_argument("--survey-id")
    parser.add_argument("--url")
    parser.add_argument("--max", type=int, default=5)
    parser.add_argument("--tab-id")
    parser.add_argument("--debug", action="store_true")
    args, passthrough = parser.parse_known_args(argv)

    mapped = []
    if args.debug:
        mapped.append("--debug")

    if args.mode == "scan":
        mapped.append("scan")
    elif args.mode == "loop":
        mapped.extend(["loop", "--max", str(args.max)])
    elif args.mode == "nim":
        mapped.append("run")
        if args.survey_id:
            mapped.extend(["--id", args.survey_id])
        if args.url:
            mapped.extend(["--url", args.url])
    elif args.mode == "snapshot":
        mapped.append("status")
    elif args.mode == "legacy":
        raise SystemExit(
            "legacy mode was removed with the deleted app/ FCTES tree; use survey-cli login/scan/run/loop"
        )

    return mapped + passthrough


def _load_survey_entry():
    """Load `survey-cli/survey.py` without confusing it with the `survey` package."""
    if str(SURVEY_CLI_DIR) not in sys.path:
        sys.path.insert(0, str(SURVEY_CLI_DIR))
    spec = importlib.util.spec_from_file_location("survey_cli_entry", SURVEY_ENTRY)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load survey entry: {SURVEY_ENTRY}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _delegate_to_toolbox_api(argv: list[str]) -> int:
    """Try to delegate to the running Agent-Toolbox API on localhost:8000."""
    try:
        import json as _json
        import urllib.error
        import urllib.request

        # Map legacy --mode to API endpoints
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument(
            "--mode", choices=["legacy", "nim", "scan", "loop", "snapshot"], default="scan"
        )
        args, _ = parser.parse_known_args(argv)

        url = None
        payload = None
        if args.mode == "scan":
            url = "http://localhost:8000/survey/run"
            payload = _json.dumps({"profile_name": "default", "max_surveys": 1}).encode()
        elif args.mode == "loop":
            url = "http://localhost:8000/survey/run"
            payload = _json.dumps({"profile_name": "default", "max_surveys": 5}).encode()
        elif args.mode == "nim":
            url = "http://localhost:8000/services/heypiggy/login"
            payload = _json.dumps({"profile_name": "default"}).encode()
        elif args.mode == "snapshot":
            url = "http://localhost:8000/browser/health"
            payload = b""

        if url:
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST" if payload else "GET",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = _json.loads(resp.read().decode())
                print(_json.dumps(data, indent=2, ensure_ascii=False))
                return 0
    except urllib.error.URLError:
        # Toolbox API not running — fall through to direct execution
        pass
    except Exception:
        pass
    return -1


def main(argv: list[str] | None = None):
    """Delegate to the canonical survey-cli main() or Agent-Toolbox API."""
    argv = list(sys.argv[1:] if argv is None else argv)

    # Try Agent-Toolbox API first (if running)
    if not any(a.startswith("--mode=legacy") or a == "--mode" for a in argv):
        api_result = _delegate_to_toolbox_api(argv)
        if api_result == 0:
            return 0

    canonical_args = (
        _legacy_to_canonical(argv) if any(a == "--mode" for a in argv) or not argv else argv
    )
    module = _load_survey_entry()

    old_argv = sys.argv[:]
    try:
        sys.argv = [str(SURVEY_ENTRY), *canonical_args]
        return module.main()
    finally:
        sys.argv = old_argv


if __name__ == "__main__":
    main()
