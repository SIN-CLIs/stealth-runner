"""Dashboard scanner — survey ID extraction + provider detection.

Uses CDP JS to extract onclick handlers and CPX API to filter.
"""

import json
import time
import urllib.request
import websocket
from . import chrome
from .chrome import DETAILS_URL, CPX_CREDENTIALS

# ── Provider Detection ─────────────────────────────────

PROVIDER_PATTERNS = {
    "qualtrics": ["qualtrics.com"],
    "tolunastart": ["tolunastart.com", "toluna.com"],
    "purespectrum": ["purespectrum.com"],
    "strat7": ["strat7audiences.com"],
    "brand_ambassador": ["brand-ambassador.com"],
    "insights_today": ["insights-today.com"],
    "surveyrouter": ["surveyrouter.com"],
    "gfk": ["surveys.com"],
}


def detect_provider(url):
    """Detect survey provider from URL."""
    url_lower = url.lower()
    for provider, patterns in PROVIDER_PATTERNS.items():
        for pat in patterns:
            if pat in url_lower:
                return provider
    return "unknown"


# ── Survey ID Extraction ───────────────────────────────

def extract_ids_from_dashboard(ws_url):
    """Extract survey IDs from dashboard via CDP.

    Returns:
        List of survey IDs found in onclick handlers.
    """
    try:
        ws = websocket.create_connection(ws_url, timeout=15)
        ws.send(json.dumps({
            "id": 0, "method": "Runtime.evaluate",
            "params": {
                "expression": '''
(function() {
    var out = [];
    document.querySelectorAll("[onclick*=clickSurvey]").forEach(function(el) {
        var m = el.getAttribute("onclick").match(/\\d+/);
        if (m) out.push(m[0]);
    });
    return out.join("|");
})()
'''
            }
        }))
        r = json.loads(ws.recv())
        ws.close()
        ids_str = r.get("result", {}).get("result", {}).get("value", "")
        if ids_str:
            return [i for i in ids_str.split("|") if i]
        return []
    except Exception as e:
        print(f"[SCAN] Error extracting IDs: {e}")
        return []


# ── Survey Filtering ───────────────────────────────────

def filter_surveys(survey_ids, skip_providers=None, max_ids=15):
    """Filter surveys via CPX API.

    Args:
        survey_ids: List of IDs to check
        skip_providers: List of provider names to skip
        max_ids: Max IDs to process

    Returns:
        List of dicts: [{id, provider, href, type}, ...]
    """
    if skip_providers is None:
        skip_providers = ["purespectrum", "surveyrouter"]

    results = []
    for sid in survey_ids[:max_ids]:
        try:
            resp = json.loads(urllib.request.urlopen(
                DETAILS_URL + "&survey_id=" + sid, timeout=8
            ).read())

            entry = {
                "id": sid,
                "type": resp.get("type", "?"),
                "href": resp.get("href", ""),
                "provider": detect_provider(resp.get("href", "")),
            }

            # Check pre-qualifier
            if entry["type"] == "question":
                entry["provider"] = "pre_qualifier"
                entry["pre_q"] = resp.get("question", "")
                entry["answers"] = resp.get("answers", [])

            results.append(entry)

        except Exception as e:
            results.append({
                "id": sid, "type": "error", "error": str(e)[:60]
            })

    return results


def print_survey_table(results):
    """Pretty-print filtered survey results."""
    print(f"\n{'─'*70}")
    print(f"  {'ID':12s} {'Type':15s} {'Provider':18s} {'URL'}")
    print(f"{'─'*70}")

    okay_count = 0
    for r in results:
        icon = "✅" if r.get("type") == "okay" else "⚠️ " if r.get("type") == "question" else "❌"
        pid = r.get("id", "?")
        ptype = r.get("type", "?")
        prov = r.get("provider", "?")
        href = r.get("href", "")[:55]
        error = r.get("error", "")
        suffix = f" | {error}" if error else ""
        print(f"  {icon} {pid:12s} {ptype:15s} {prov:18s} {href}{suffix}")
        if r.get("type") == "okay":
            okay_count += 1

    print(f"{'─'*70}")
    print(f"  Total: {len(results)} | OK: {okay_count} | Filtered: {len(results) - okay_count}")
    print()

    return [r for r in results if r.get("type") == "okay"]


def scan_dashboard(port=9999, skip_providers=None):
    """Full scan: connect → extract IDs → filter → print.

    Returns:
        List of viable survey entries [{id, provider, href}]
    """
    ws_url = chrome.find_dashboard_ws(port)
    if not ws_url:
        print("[SCAN] No dashboard found. Is Chrome running?")
        return []

    # Extract IDs
    ids = extract_ids_from_dashboard(ws_url)
    if not ids:
        print("[SCAN] No survey IDs found on dashboard")
        return []

    print(f"[SCAN] Found {len(ids)} survey IDs. Checking via API...")

    # Filter via API
    results = filter_surveys(ids, skip_providers=skip_providers)
    viable = print_survey_table(results)

    return viable


# ── Page Content Extraction ────────────────────────────

def read_page_text(ws_url, max_len=500):
    """Read page innerText via CDP."""
    try:
        ws = websocket.create_connection(ws_url, timeout=10)
        ws.send(json.dumps({
            "id": 0, "method": "Runtime.evaluate",
            "params": {
                "expression": f"document.body.innerText.substring(0, {max_len})"
            }
        }))
        r = json.loads(ws.recv())
        ws.close()
        return r.get("result", {}).get("result", {}).get("value", "")
    except Exception:
        return ""


def read_balance(port=9999):
    """Read current balance from dashboard."""
    ws_url = chrome.find_dashboard_ws(port)
    if not ws_url:
        return 0.0

    try:
        ws = websocket.create_connection(ws_url, timeout=10)
        ws.send(json.dumps({
            "id": 0, "method": "Runtime.evaluate",
            "params": {
                "expression": '''
(function() {
    var t = document.body.innerText;
    var m = t.match(/\\d+\\.\\d+\\s*[€$]/g);
    return m ? m[m.length-1].replace("€","").replace("$","").trim() : "0";
})()
'''
            }
        }))
        r = json.loads(ws.recv())
        ws.close()
        return float(r.get("result", {}).get("result", {}).get("value", "0"))
    except Exception:
        return 0.0
