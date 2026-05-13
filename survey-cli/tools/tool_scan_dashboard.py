"""TOOL: scan_dashboard — HeyPiggy Survey Discovery + Provider Detection

ARCHITEKTUR:
  ┌─────────────────────────┐
  │  scan(port=9999)        │
  └─────────────────────────┘
           │
           ▼
  ┌─────────────────────────┐
  │  find_dashboard_ws()    │  → ws://127.0.0.1:9999/...
  │  (Chrome CDP scan)      │
  └─────────────────────────┘
           │
           ▼
  ┌─────────────────────────┐
  │  extract_ids_from_dom() │  → ["67064749", "67064991", ...]
  │  (onclick handlers)     │
  └─────────────────────────┘
           │
           ▼
  ┌─────────────────────────┐
  │  filter_surveys()       │  → [{id, provider, href, type, trust_score}]
  │  (CPX API + detection)  │
  └─────────────────────────┘
           │
           ▼
  ┌─────────────────────────┐
  │  Registry Update        │
  └─────────────────────────┘

STATUS: __frozen__=True | Version: 2026-05-11
NUTZT: survey/scanner.py (scan_dashboard, detect_provider, PROVIDER_TRUST_SCORES)

BANNED METHODS:
  ❌ playstealth launch
  ❌ webauto-nodriver — ABSOLUT BANNED
  ❌ hardcoded PIDs — dynamisch scannen
  ❌ pkill -f "Google Chrome"
  ❌ skylight-cli click --element-index
"""

from __future__ import annotations
import json
from typing import Dict, Optional

__frozen__ = True
__version__ = "2026-05-11"


# ── Pre-Flight: Chrome running check ─────────────────────────────────────────

def _preflight(port: int) -> bool:
    """Check if Chrome is running with CDP on specified port."""
    try:
        import urllib.request
        resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=5)
        return resp.status == 200
    except Exception:
        return False


def _update_registry(success: bool, details: dict):
    """Auto-Update: record scan result."""
    try:
        import survey.command_registry as cr_module
        reg = cr_module.CommandRegistry()
        reg.record_command("scan_dashboard", success, details)
    except Exception:
        pass


# ── Core: scan_dashboard ──────────────────────────────────────────────────────

def scan(port: int = 9999) -> dict:
    """Scan HeyPiggy dashboard for available surveys.

    Args:
        port: CDP port (default: 9999 for HeyPiggy bot chrome)

    Returns:
        dict: {
            "status": "ok"|"error",
            "count": N,           # total surveys found
            "viable": [...],      # type="okay" surveys
            "pre_qualifiers": [...],  # type="question" surveys
            "provider_counts": {...},  # {qualtrics: 3, cint: 2, ...}
        }

    Usage:
        from tools.tool_scan_dashboard import scan
        result = scan(9999)
        # → {"status": "ok", "count": 12, "viable": [...], "provider_counts": {...}}
    """
    # Pre-flight: Chrome running?
    if not _preflight(port):
        _update_registry(False, {"reason": "chrome_not_running", "port": port})
        return {"status": "error", "reason": "chrome_not_running", "port": port}

    try:
        from survey.scanner import (
            scan_dashboard,
            detect_provider,
            PROVIDER_TRUST_SCORES,
            get_trust_score,
        )

        # scan_dashboard returns list of survey entries
        # Each: {id, type, href, provider, trust_score, ...}
        surveys = scan_dashboard(port=port)

        if not surveys:
            _update_registry(False, {"reason": "no_surveys_found"})
            return {"status": "ok", "count": 0, "viable": [], "pre_qualifiers": [], "provider_counts": {}}

        # Categorize
        viable = [s for s in surveys if s.get("type") == "okay"]
        pre_qualifiers = [s for s in surveys if s.get("type") == "question"]

        # Provider counts
        provider_counts: Dict[str, int] = {}
        for s in surveys:
            p = s.get("provider", "unknown")
            provider_counts[p] = provider_counts.get(p, 0) + 1

        result = {
            "status": "ok",
            "count": len(surveys),
            "viable_count": len(viable),
            "viable": viable[:15],  # Top 15 viable
            "pre_qualifiers": pre_qualifiers[:10],  # Top 10 pre-qualifiers
            "provider_counts": provider_counts,
        }

        _update_registry(True, {
            "count": len(surveys),
            "viable": len(viable),
            "providers": list(provider_counts.keys()),
        })

        return result

    except ImportError as e:
        _update_registry(False, {"reason": f"import_error: {e}"})
        return {"status": "error", "reason": f"import_error: {e}"}
    except Exception as e:
        _update_registry(False, {"reason": str(e)[:200]})
        return {"status": "error", "reason": str(e)[:200]}


# ── Public API: get next viable survey ────────────────────────────────────────

def get_next_survey(port: int = 9999, min_trust: float = 0.5) -> Optional[dict]:
    """Get the next best survey to attempt.

    Args:
        port: CDP port
        min_trust: Minimum trust score (0.0-1.0)

    Returns:
        Survey dict or None if no viable surveys.
    """
    result = scan(port)
    if result["status"] != "ok":
        return None

    for s in result.get("viable", []):
        if s.get("trust_score", 0) >= min_trust:
            return s

    return None


if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9999
    result = scan(port)
    print(json.dumps(result, indent=2, ensure_ascii=False))