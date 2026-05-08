"""================================================================================
DASHBOARD SCANNER — Survey ID Extraction + Provider Detection
================================================================================

WAS IST DAS?
  Scannt das Heypiggy Dashboard nach verfügbaren Surveys.
  Extrahiert Survey-IDs aus onclick-Handlern und erkennt den Provider
  (Qualtrics, Toluna, Strat7, PureSpectrum, etc.).

ARCHITEKTUR:
  ┌─────────────────────┐
  │  scan_dashboard()   │
  └─────────────────────┘
         │
         ▼
  ┌─────────────────────┐
  │  CDP JS Extractor   │
  │  (onclick handlers) │
  └─────────────────────┘
         │
         ▼
  ┌─────────────────────┐
  │  Provider Detection │
  │  (URL Patterns)     │
  └─────────────────────┘
         │
         ▼
  ┌─────────────────────┐
  │  [{id, title,      │
  │   payout, provider}]│
  └─────────────────────┘

WARUM onclick-Handler?
  Heypiggy Survey-Cards haben onclick="clickSurvey('12345')".
  → Wir extrahieren die ID aus dem Handler-String.
  → Zuverlässiger als Text-Matching (Titel ändern sich).

WARUM Provider Detection?
  Verschiedene Provider = verschiedene DOM-Strukturen.
  → BatchExecutor braucht provider-spezifisches JavaScript.
  → Erkennung via URL-Patterns (qualtrics.com, tolunastart.com, etc.).

BANNED METHODS — NIEMALS VERWENDEN (siehe /banned.md):
  ❌ playstealth launch
  ❌ webauto-nodriver — ABSOLUT BANNED
  ❌ cua-driver click (raw index)
  ❌ --remote-allow-origins=* (ohne Quotes)
  ❌ /tmp/heypiggy-bot (fixed profile)
  ❌ Hardcoded PIDs
  ❌ pkill -f "Google Chrome"
  ❌ killall Google Chrome
  ❌ skylight-cli click --element-index
================================================================================"""

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

def filter_surveys(survey_ids, skip_providers=None, max_ids=15, port=9223):
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


# ── DOM Survey Card Scanner (IN-PAGE MODAL) ─────────────


def scan_dashboard_dom(port=9223):
    """Scan dashboard DOM for survey cards with rewards.

    heypiggy renders survey cards with onclick=\"clickSurvey('ID')\".
    These show reward/duration that CPX API doesn't expose.
    """
    try:
        ws_url = chrome.find_dashboard_ws(port)
        if not ws_url:
            return []
        ws = websocket.create_connection(ws_url, timeout=10)
        ws.send(json.dumps({
            "id": 1, "method": "Runtime.evaluate",
            "params": {"expression": '''
JSON.stringify(
    Array.from(document.querySelectorAll("[onclick*=clickSurvey]")).map(el => {
        var onclick = el.getAttribute("onclick");
        var id = (onclick.match(/clickSurvey\\('(\\d+)'\\)/) || [])[1] || "";
        var text = (el.textContent || "").trim();
        var reward = (text.match(/(\\d+\\.?\\d*)\\s*€/) || [])[1] || "0";
        var duration = (text.match(/(\\d+)\\s*Min/) || [])[1] || "0";
        return {id: id, reward: parseFloat(reward), duration: parseInt(duration)};
    })
)
''', "returnByValue": True}
        }))
        r = json.loads(ws.recv())
        ws.close()
        cards = json.loads(r.get("result", {}).get("result", {}).get("value", "[]"))
        for c in cards:
            c["provider"] = "in_page_modal"
            c["type"] = "okay"
        return cards
    except Exception:
        return []


def scan_dashboard(port=9223, skip_providers=None):
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


def read_balance(port=9223):
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
    // Fallback: find number next to € that is NOT a survey reward (reward lines have "Min" nearby)
    var t = document.body.innerText;
    var lines = t.split("\\n");
    for (var i = 0; i < lines.length; i++) {
        var line = lines[i].trim();
        var m = line.match(/^(\\d+[.,]\\d+)\\s*€?$/);
        // Skip lines that are survey rewards (have "Min" in adjacent lines or are small)
        if (m && !/Min|Level|Umfragen/.test(lines[Math.max(0,i-1)] || "")) {
            var val = parseFloat(m[1].replace(",", "."));
            // Balance is typically > 1.0 and not a round number like survey rewards
            if (val > 1.0 && val < 1000) return val.toString();
        }
    }
    return "0";
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


def read_balance_with_backoff(port=9223, max_retries=5, base_delay=2.0):
    """Read balance with exponential backoff — avoids false 0.00€ reads.

    Dashboard DOM updates async after page load. Without backoff, first
    read returns 0.00€ → false negative on payout detection.

    Args:
        port: CDP port
        max_retries: Max retry attempts (default 5)
        base_delay: Initial delay in seconds (doubles each retry)

    Returns:
        float balance value
    """
    for attempt in range(1, max_retries + 1):
        balance = read_balance(port)
        if balance > 0:
            return balance
        if attempt < max_retries:
            delay = min(base_delay * (2 ** (attempt - 1)), 30.0)
            time.sleep(delay)
    return read_balance(port)
