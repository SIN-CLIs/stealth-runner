#!/usr/bin/env python3
"""
LangGraph E2E Test — create_graph().invoke() mit echtem Survey

Dieses Script:
1. Scannt das HeyPiggy Dashboard nach verfügbaren Surveys
2. Wählt die beste Survey (basierend auf Provider-Trust)
3. Erstellt und kompiliert den LangGraph StateGraph
4. Führt graph.invoke() aus
5. Loggt das Ergebnis

Usage:
    PYTHONPATH=/Users/jeremy/dev/stealth-runner:/Users/jeremy/dev/stealth-runner/survey-cli \
        /Users/jeremy/dev/stealth-runner/.venv/bin/python test_graph_invoke.py
"""

import sys
import json
import time
import os

sys.path.insert(0, '/Users/jeremy/dev/stealth-runner')
sys.path.insert(0, '/Users/jeremy/dev/stealth-runner/survey-cli')

import websocket
import urllib.request

# LangGraph
from survey.graph import create_graph, SurveyState

CDP_PORT = 9999


def get_dashboard_ws():
    """Find Dashboard tab WebSocket URL."""
    try:
        pages = json.loads(urllib.request.urlopen(
            f'http://127.0.0.1:{CDP_PORT}/json/list', timeout=5).read())
        for p in pages:
            if p.get('type') == 'page' and 'heypiggy' in p.get('url', ''):
                return p.get('webSocketDebuggerUrl')
    except Exception as e:
        print(f"[ERROR] Could not find dashboard: {e}")
    return None


def validate_session(ws_url):
    """Check if session is valid (body contains 'abmelden')."""
    try:
        ws = websocket.create_connection(ws_url, timeout=10)
        ws.send(json.dumps({
            "id": 1,
            "method": "Runtime.evaluate",
            "params": {"expression": "document.body.innerText.substring(0, 500)"}
        }))
        r = json.loads(ws.recv())
        ws.close()
        text = r.get("result", {}).get("result", {}).get("value", "").lower()
        return "abmelden" in text or "umfragen" in text, text[:100]
    except Exception as e:
        print(f"[ERROR] Session validation failed: {e}")
        return False, ""


def scan_dashboard(ws_url):
    """Scan dashboard for available surveys."""
    scan_js = """
(function() {
    var results = {balance: "", surveys: []};
    
    // Balance
    var balanceElements = document.querySelectorAll(
        '.balance, .points, [class*="balance"], [class*="points"], [class*="guthaben"]'
    );
    for (var el of balanceElements) {
        var text = el.textContent.trim();
        if (text.includes('€') || text.includes('EUR') || /\\d+\\.\\d+/.test(text)) {
            results.balance = text;
            break;
        }
    }
    if (!results.balance) {
        var bodyText = document.body.innerText;
        var balanceMatch = bodyText.match(/(Guthaben|Balance|Points)[:\\s]*([€\\$]?\\s*[\\d,.]+)/i);
        if (balanceMatch) results.balance = balanceMatch[2];
    }
    
    // Surveys
    var cards = document.querySelectorAll('[onclick*="clickSurvey"]');
    for (var i = 0; i < cards.length; i++) {
        var card = cards[i];
        var onclick = card.getAttribute("onclick") || '';
        var idMatch = onclick.match(/clickSurvey\\('?(\\d+)'?\\)/);
        var surveyId = idMatch ? idMatch[1] : '';
        
        var parent = card.closest('div, li, tr, article') || card;
        var cardText = parent.textContent || '';
        
        var rewardMatch = cardText.match(/(\\d+[.,]?\\d*)\\s*€/);
        var reward = rewardMatch ? parseFloat(rewardMatch[1].replace(',', '.')) : 0;
        
        var durationMatch = cardText.match(/(\\d+)\\s*min/i);
        var duration = durationMatch ? parseInt(durationMatch[1]) : null;
        
        var titleMatch = cardText.match(/([^€\\n]+)(?=\\d+[.,]?\\d*\\s*€)/);
        var title = titleMatch ? titleMatch[1].trim().substring(0, 100) : '';
        
        var provider = '';
        if (cardText.toLowerCase().includes('qualtrics')) provider = 'qualtrics';
        else if (cardText.toLowerCase().includes('toluna')) provider = 'tolunastart';
        else if (cardText.toLowerCase().includes('cint')) provider = 'cint';
        else if (cardText.toLowerCase().includes('tivian')) provider = 'tivian';
        else if (cardText.toLowerCase().includes('nfield')) provider = 'nfield';
        else if (cardText.toLowerCase().includes('samplicio')) provider = 'samplicio';
        else if (cardText.toLowerCase().includes('purespectrum') || cardText.toLowerCase().includes('pure')) provider = 'purespectrum';
        else if (cardText.toLowerCase().includes('ipsos')) provider = 'ipsos';
        else provider = 'unknown';
        
        if (surveyId && reward > 0) {
            results.surveys.push({
                id: surveyId, reward: reward, duration: duration,
                title: title, provider: provider
            });
        }
    }
    return JSON.stringify(results);
})()
"""
    try:
        ws = websocket.create_connection(ws_url, timeout=15)
        ws.send(json.dumps({
            "id": 1,
            "method": "Runtime.evaluate",
            "params": {"expression": scan_js}
        }))
        r = json.loads(ws.recv())
        ws.close()
        result_text = r.get("result", {}).get("result", {}).get("value", "{}")
        return json.loads(result_text)
    except Exception as e:
        print(f"[ERROR] Dashboard scan failed: {e}")
        return {"balance": "", "surveys": []}


def select_best_survey(surveys):
    """Select best survey based on reward * provider_trust."""
    provider_trust = {
        "qualtrics": 0.9, "tolunastart": 0.8, "cint": 0.7,
        "tivian": 0.7, "nfield": 0.6, "samplicio": 0.4,
        "purespectrum": 0.3, "ipsos": 0.5, "unknown": 0.5,
    }
    
    best = None
    best_score = -1
    
    for s in surveys:
        reward = s.get("reward", 0)
        provider = s.get("provider", "unknown")
        trust = provider_trust.get(provider, 0.5)
        score = reward * trust
        
        if score > best_score:
            best_score = score
            best = s
    
    return best


def main():
    print("=" * 70)
    print("LANGGRAPH E2E TEST — create_graph().invoke()")
    print("=" * 70)
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Step 1: Find Dashboard
    print("[1/6] Finding Dashboard tab...")
    ws_url = get_dashboard_ws()
    if not ws_url:
        print("[ERROR] No dashboard found. Is Chrome running?")
        sys.exit(1)
    print(f"  ✓ Dashboard found: {ws_url[:50]}...")
    
    # Step 2: Validate Session
    print("[2/6] Validating session...")
    valid, text_preview = validate_session(ws_url)
    if not valid:
        print(f"[ERROR] Session invalid! Text preview: {text_preview}")
        print("[INFO] Try: Chrome restart + cookie injection (AGENTS.md Regel 1-4)")
        sys.exit(1)
    print(f"  ✓ Session valid (found 'abmelden/umfragen')")
    print(f"  Preview: {text_preview[:80]}...")
    
    # Step 3: Scan Dashboard
    print("[3/6] Scanning dashboard...")
    scan = scan_dashboard(ws_url)
    balance_str = scan.get("balance", "")
    surveys = scan.get("surveys", [])
    
    print(f"  Balance: {balance_str or 'N/A'}")
    print(f"  Surveys found: {len(surveys)}")
    
    if not surveys:
        print("[INFO] No surveys available. Try again later.")
        sys.exit(0)
    
    for s in surveys[:5]:
        print(f"    - ID:{s['id'][:12]}... {s['provider']:12s} +{s['reward']:.2f}€ {s['title'][:40]}")
    
    # Step 4: Select Best Survey
    print("[4/6] Selecting best survey...")
    best = select_best_survey(surveys)
    if not best:
        print("[ERROR] Could not select survey")
        sys.exit(1)
    
    print(f"  ✓ Selected: ID={best['id']}, Provider={best['provider']}, Reward=+{best['reward']:.2f}€")
    
    # Step 5: Create Graph
    print("[5/6] Creating LangGraph StateGraph...")
    try:
        graph = create_graph()
        print(f"  ✓ Graph compiled successfully")
    except Exception as e:
        print(f"[ERROR] Graph compilation failed: {e}")
        sys.exit(1)
    
    # Step 6: Invoke Graph
    print("[6/6] Invoking graph (this may take 1-3 minutes)...")
    print()
    
    initial_state = SurveyState(
        survey_id=best["id"],
        provider=best["provider"],
        cdp_port=CDP_PORT,
        max_iterations=15,
    )
    
    start_time = time.time()
    try:
        final_state = graph.invoke(initial_state)
        elapsed = time.time() - start_time
        
        # LangGraph returns dict when using dataclass state_schema
        if isinstance(final_state, dict):
            state_dict = final_state
        else:
            state_dict = final_state.__dict__ if hasattr(final_state, '__dict__') else {}
        
        # DEBUG: Print full state dict for analysis
        print("\n--- FULL STATE DUMP ---")
        for key, value in sorted(state_dict.items()):
            if key == 'errors' and value:
                print(f"  {key}: {len(value)} errors")
                for i, err in enumerate(value[:10]):
                    print(f"    [{i}] {err}")
            elif key == 'nim_actions' and value:
                print(f"  {key}: {value}")
            elif key == 'snapshot_refs' and value:
                print(f"  {key}: {len(value)} refs")
            elif key in ['dashboard_ws', 'tab_ws'] and value:
                print(f"  {key}: {str(value)[:50]}...")
            else:
                print(f"  {key}: {value}")
        print("--- END STATE DUMP ---\n")
        
        print()
        print("=" * 70)
        print("RESULT")
        print("=" * 70)
        print(f"Survey ID:     {state_dict.get('survey_id', 'N/A')}")
        print(f"Provider:      {state_dict.get('provider', 'N/A')}")
        print(f"Status:        {state_dict.get('status', 'N/A')}")
        print(f"Iterations:    {state_dict.get('iteration', 0)}/{state_dict.get('max_iterations', 15)}")
        earned = state_dict.get('balance_earned', 0.0)
        before = state_dict.get('balance_before', 0.0)
        after = state_dict.get('balance_after', 0.0)
        print(f"Earned:        €{earned:.2f}")
        print(f"Balance Before: €{before:.2f}")
        print(f"Balance After:  €{after:.2f}")
        print(f"Screen Out:    {state_dict.get('screen_out', False)}")
        print(f"Completion:    {state_dict.get('completion_detected', False)}")
        errors = state_dict.get('errors', [])
        print(f"Errors:        {len(errors)}")
        print(f"Elapsed:       {elapsed:.1f}s")
        print()
        
        if errors:
            print("Errors:")
            for err in errors[:5]:
                if isinstance(err, dict):
                    print(f"  - [{err.get('node', '?')}] {err.get('error', 'unknown')[:100]}")
                else:
                    print(f"  - {str(err)[:100]}")
        
        print()
        if earned > 0:
            print("🎉 SUCCESS: Balance increased!")
        elif state_dict.get('screen_out', False):
            print("⚠️  SCREEN-OUT: Disqualified (0.02€ compensation)")
        elif state_dict.get('status') == "error":
            print("❌ ERROR: Survey failed")
        else:
            print("ℹ️  COMPLETED: No earnings (may need verification)")
        
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"\n[ERROR] Graph invocation failed after {elapsed:.1f}s: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print("=" * 70)
    print(f"Log saved to: /tmp/langgraph_e2e_{time.strftime('%Y%m%d_%H%M%S')}.log")


if __name__ == "__main__":
    # Redirect stdout to both console and file
    log_file = f"/tmp/langgraph_e2e_{time.strftime('%Y%m%d_%H%M%S')}.log"
    
    class Tee:
        def __init__(self, *files):
            self.files = files
        def write(self, obj):
            for f in self.files:
                f.write(obj)
                f.flush()
        def flush(self):
            for f in self.files:
                f.flush()
    
    with open(log_file, 'w') as f:
        original_stdout = sys.stdout
        sys.stdout = Tee(sys.stdout, f)
        try:
            main()
        finally:
            sys.stdout = original_stdout
    
    print(f"\nFull log: {log_file}")
