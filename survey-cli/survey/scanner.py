"""Dashboard scanner — survey ID extraction + provider detection.

Uses CDP JS to extract onclick handlers and CPX API to filter.
"""

import json
import time
import urllib.request
import websocket
from . import chrome
from . import chrome

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
    # NEW PROVIDERS (2026-05-06) — discovered from live surveys
    "cloudresearch": ["cloudresearch.com", "sentry.cloudresearch.com"],
    "edgesurvey": ["edgesurvey.innovatemr.net", "innovatemr.net"],
    "reach3insights": ["reach3insights.com", "surveys.reach3insights.com"],
    "samplicio": ["samplicio.us", "rx.samplicio.us"],
    "cint": ["s.cint.com"],
    "nfield": ["nfieldeu-interviewing.nfieldmr.com"],
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

def filter_surveys(survey_ids, skip_providers=None, max_ids=15, port=9999):
    """Filter surveys via CPX API.

    Args:
        survey_ids: List of IDs to check
        skip_providers: List of provider names to skip
        max_ids: Max IDs to process
        port: CDP port

    Returns:
        List of dicts: [{id, provider, href, type}, ...]
    """
    if skip_providers is None:
        skip_providers = ["surveyrouter"]

    from .chrome import get_details_url
    details_url = get_details_url(port)

    results = []
    for sid in survey_ids[:max_ids]:
        try:
            resp = json.loads(urllib.request.urlopen(
                details_url + "&survey_id=" + sid, timeout=8
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
                entry["question_text"] = resp.get("question_text", resp.get("question", ""))
                # answers is a dict: {key: {text, key}} — keep as-is
                entry["answers"] = resp.get("answers", {})
                entry["question_key"] = resp.get("question_key", "")
                entry["message_button"] = resp.get("message_button", "einreichen")

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

    # Return ALL surveys — including pre-qualifiers and unknown types.
    # The runner's handle_pre_qualifier() will answer pre-qualifier questions.
    # NEVER filter out surveys before they reach the execution engine.
    return results


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
    """Read current balance from dashboard.

    The heypiggy dashboard shows balance in a .balance or .credit element.
    Falls back to regex on innerText.
    """
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
    // Try specific balance elements first
    var el = document.querySelector('.balance, .my-balance, .credit, [class*=balance], [class*=credit]');
    if (el) {
        var t = el.innerText || el.textContent;
        var m = t.match(/(\\d+[.,]\\d+)/);
        if (m) return m[1].replace(",", ".");
    }
    // Fallback: find the largest number near € in the full text
    var t = document.body.innerText;
    var re = /(\\d+[.,]\\d+)\\s*\\n?\\s*[€$]/g;
    var matches = [];
    var match;
    while ((match = re.exec(t)) !== null) {
        matches.push(parseFloat(match[1].replace(",", ".")));
    }
    // Filter out very small values (< 0.01) and return the largest
    var valid = matches.filter(function(v) { return v > 0.01; });
    return valid.length > 0 ? Math.max.apply(null, valid).toString() : "0";
})()
'''
            }
        }))
        r = json.loads(ws.recv())
        ws.close()
        val = r.get("result", {}).get("result", {}).get("value", "0")
        return float(val)
    except Exception as e:
        return 0.0
