#!/usr/bin/env python3
"""================================================================================
RUN_SURVEY — Single Entry Point for Heypiggy Survey Automation (NEMO v2.0)
================================================================================

WAS IST DAS?
  Haupt-Einstiegspunkt für Survey-Automation. Unterstützt mehrere Modi:
  - legacy: Alte cua-driver-basierte Flows (DEPRECATED)
  - nim: NEMO-Architektur (Compact Snapshot → Nemotron → Batch Execute)
  - scan: Dashboard nach verfügbaren Surveys scannen
  - loop: Automatisch Surveys ausführen (scan + nim wiederholt)
  - snapshot: Compact Snapshot einer Survey-Seite generieren

ARCHITEKTUR:
  ┌─────────────────────┐
  │   run_survey.py     │  ← DU BIST HIER (Entry Point)
  └─────────────────────┘
         │
    ┌────┴────────┬────────┬────────┐
    ▼             ▼        ▼        ▼
  legacy        nim      scan     snapshot
    │             │        │        │
    ▼             ▼        ▼        ▼
  cua-driver   NEMO     scanner   compact_snapshot
  (DEPRECATED)  Engine   (chrome)  (snapshot.py)

WARUM argparse statt Typer?
  Einfachheit. run_survey.py ist ein Standalone-Script,
  nicht ein komplexes CLI-Tool. argparse ist in der Standardlib.
  → Keine externe Dependency nötig.

WARUM sys.path.insert(0, os.path.dirname(__file__))?
  Ermöglicht relative Imports innerhalb des Repos.
  → Wichtig wenn Script aus anderem Verzeichnis aufgerufen wird.

WARUM Hardcoded Fallback-Profile?
  Wenn config/profiles/ fehlt (z.B. frische Installation),
  → Fallback-Profile garantiert Funktionalität.
  → Sollte später in Infisical oder Env-Vars ausgelagert werden.

BANNED METHODS — NIEMALS VERWENDEN (siehe /banned.md):
  ❌ playstealth launch — setzt NICHT --force-renderer-accessibility
  ❌ webauto-nodriver — ABSOLUT BANNED
  ❌ cua-driver click (raw index) — instabil
  ❌ --remote-allow-origins=* (ohne Quotes) — zsh glob expansion
  ❌ /tmp/heypiggy-bot (fixed profile) — korruptiert nach Neustart
  ❌ Hardcoded PIDs — dynamisch, niemals hardcodieren
  ❌ pkill -f "Google Chrome" — tötet USER Chrome
  ❌ killall Google Chrome — tötet ALLE Chrome
  ❌ skylight-cli click --element-index — Index instabil

USAGE:
  # Legacy survey flow (cua-driver, DEPRECATED — nutze NEMO!)
  python3 run_survey.py --mode legacy

  # NEMO: Einzelne Survey per ID
  python3 run_survey.py --mode nim --survey-id 66846193

  # NEMO: Automatisch Surveys ausführen (scan + nim Loop)
  python3 run_survey.py --mode loop --max 5

  # NEMO: Dashboard scannen
  python3 run_survey.py --mode scan

  # NEMO: Compact Snapshot generieren
  python3 run_survey.py --mode snapshot --tab-id <TAB_ID>
================================================================================"""

import sys
import os
import json
import time
import argparse

sys.path.insert(0, os.path.dirname(__file__))


def load_profile():
    """Load persona profile — hardcoded fallback if no profile file."""
    try:
        profile_path = os.path.join(os.path.dirname(__file__), "config", "profiles", "jeremy_schulze.json")
        if os.path.exists(profile_path):
            profile = json.loads(open(profile_path).read())
            print(f"[PROFILE] Loaded: {profile.get('name', 'unknown')}")
            return profile
    except Exception:
        pass

    # Hardcoded fallback
    return {
        "name": "Jeremy Schulze",
        "date_of_birth": "1993-11-13",
        "age": 32,
        "gender": "male",
        "gender_label": "Männlich",
        "city": "Berlin",
        "state": "Berlin",
        "zip": "10785",
        "street": "Kurfürstenstraße 124",
        "household_size": 3,
        "marital_status": "married",
        "education": "abitur",
        "employment": "employed_fulltime",
        "employment_label": "Angestellte",
        "household_income": "3000-4000",
        "personal_income": "1000-2000",
        "nationality": "Deutsch",
        "language": "Deutsch",
        "insurance_products": ["haftpflicht"],
        "contracts": ["mobilfunk", "strom"],
    }


def check_nvidia_api():
    """Verify NVIDIA API key is set."""
    if not os.getenv("NVIDIA_API_KEY"):
        print("⚠️  NVIDIA_API_KEY not set. NEMO mode will use simple auto-pilot (no AI)")
        return False
    return True


def cmd_legacy():
    """Run legacy survey flow (cua-driver based)."""
    from app.flows.learning import survey_heypiggy
    result = survey_heypiggy.execute()
    print("\n" + json.dumps(result, indent=2, ensure_ascii=False))
    return result


def cmd_scan(debug=False):
    """Scan dashboard for available survey IDs with provider info."""
    import urllib.request
    import websocket

    port = 9999
    pages = json.loads(urllib.request.urlopen(f'http://127.0.0.1:{port}/json').read())

    dashboard_ws = None
    for p in pages:
        if 'dashboard' in p.get('url', ''):
            dashboard_ws = p.get('webSocketDebuggerUrl')
            break

    if not dashboard_ws:
        print("❌ No dashboard tab found")
        return []

    # Extract IDs
    ws = websocket.create_connection(dashboard_ws, timeout=15)
    ws.send(json.dumps({
        "id": 0, "method": "Runtime.evaluate",
        "params": {
            "expression": '(function(){var out=[];document.querySelectorAll("[onclick*=clickSurvey]").forEach(function(c){var m=c.getAttribute("onclick").match(/\\\d+/);if(m)out.push(m[0]);});return out.join("|");})()'
        }
    }))
    r = json.loads(ws.recv())
    ws.close()

    ids = [i for i in r.get("result", {}).get("result", {}).get("value", "").split("|") if i]
    print(f"\n📋 Dashboard: {len(ids)} survey IDs found\n")

    if not ids:
        return []

    # Check each via API
    details_url = (
        "https://live-api.cpx-research.com/api/get-survey-details.php"
        "?output_method=jsscriptv1&app_id=11644"
        "&ext_user_id=2525530"
        "&secure_hash=ae75b0feca27c0f8eb356d7117d978ec"
        "&email=zukunftsorientierte.energie@gmail.com"
        "&extra_info_1=offerwall"
        "&main_info=true"
        "&extra_info_3=EUR"
        "&extra_info_4=nomobile"
    )

    for sid in ids[:15]:
        try:
            resp = json.loads(urllib.request.urlopen(
                details_url + "&survey_id=" + sid, timeout=8
            ).read())
            t = resp.get('type', '?')
            href = resp.get('href', '')[:60]

            # Detect provider from href
            provider = "?"
            if 'qualtrics.com' in href: provider = "Qualtrics"
            elif 'tolunastart.com' in href: provider = "TolunaStart"
            elif 'purespectrum.com' in href: provider = "PureSpectrum"
            elif 'strat7' in href: provider = "Strat7"
            elif 'brand' in href: provider = "BrandAmbassador"

            if t == 'okay':
                print(f"  ✅ {sid} | OK | {provider:15s} | {href}")
            elif t == 'question':
                print(f"  ⚠️  {sid} | PRE-QUALIFIER")
            else:
                print(f"  ❌ {sid} | {t}")
        except Exception as e:
            print(f"  ❌ {sid} | error: {e}")

    return ids


def cmd_nim_survey(survey_id=None, survey_url=None, debug=False):
    """Run a survey using the NEMO SurveyAgent."""
    from src.stealth_survey.survey_agent import SurveyAgent, AgentConfig

    profile = load_profile()
    has_nim = check_nvidia_api()

    config = AgentConfig(
        use_nim=has_nim,
        debug=debug,
        auto_rate=True,
        wait_between_actions=2.0,
    )

    agent = SurveyAgent(config=config)
    agent.load_profile()

    if survey_url:
        print(f"[NEMO] Running survey via URL: {survey_url[:60]}...")
        result = agent.run_survey(survey_id="direct", survey_url=survey_url)
    elif survey_id:
        print(f"[NEMO] Running survey: {survey_id}")
        result = agent.run_survey(survey_id=survey_id)
    else:
        print("❌ No survey ID or URL provided")
        return None

    print(f"\n{'='*50}")
    print(f"  Survey:     {result.survey_id}")
    print(f"  Status:     {result.status}")
    print(f"  Provider:   {result.provider}")
    print(f"  Earned:     +{result.earned}€")
    print(f"  Iterations: {result.iterations}")
    print(f"  Duration:   {result.elapsed_s}s")
    print(f"  NIM calls:  {result.nim_calls}")
    if result.error:
        print(f"  Error:      {result.error}")
    print(f"{'='*50}")

    return result


def cmd_loop(max_surveys=5, debug=False):
    """Auto-loop: scan dashboard → filter → run surveys."""
    from src.stealth_survey.survey_agent import SurveyAgent, AgentConfig

    profile = load_profile()
    has_nim = check_nvidia_api()

    config = AgentConfig(
        use_nim=has_nim,
        debug=debug,
        auto_rate=True,
        max_surveys=max_surveys,
        wait_between_actions=2.0,
    )

    agent = SurveyAgent(config=config)
    agent.load_profile()

    print(f"\n🔄 AUTO-LOOP starting (max {max_surveys} surveys)")
    print(f"   Profile: {profile.get('name', 'default')}")
    print(f"   LLM: {'Nemotron 3 Omni' if has_nim else 'Simple auto-pilot (no AI)'}")
    print()

    results = agent.run_loop()

    print(f"\n📊 LOOP COMPLETE")
    completed = sum(1 for r in results if r.status == 'completed')
    blocked = sum(1 for r in results if r.status == 'blocked')
    total_earned = sum(r.earned for r in results if r.earned > 0)
    print(f"   {completed} completed, {blocked} blocked")
    print(f"   +{total_earned}€ total earned")

    return results


def cmd_snapshot(tab_id=None):
    """Generate a compact snapshot of the current survey tab."""
    import urllib.request
    from src.stealth_survey.compact_snapshot import CompactSnapshotGenerator

    port = 9999
    pages = json.loads(urllib.request.urlopen(f'http://127.0.0.1:{port}/json').read())

    if tab_id:
        ws_url = None
        for p in pages:
            if p.get('id') == tab_id:
                ws_url = p.get('webSocketDebuggerUrl')
                break
        if not ws_url:
            print(f"❌ Tab {tab_id} not found")
            return
    else:
        # Find first non-dashboard tab
        for p in pages:
            url = p.get('url', '')
            if 'dashboard' not in url and 'rating.php' not in url:
                ws_url = p.get('webSocketDebuggerUrl')
                tab_id = p.get('id', '?')
                print(f"📄 Using tab: {p.get('url', '')[:60]}")
                break
        else:
            print("❌ No survey tab found")
            return

    gen = CompactSnapshotGenerator(port=port)
    snapshot = gen.generate(ws_url)

    print(f"\n📸 COMPACT SNAPSHOT — {snapshot.provider}")
    print(f"   URL: {snapshot.url[:60]}")
    print(f"   Title: {snapshot.title}")
    print(f"   Elements: {len(snapshot.refs)}")
    print(f"   Semantics: {json.dumps(snapshot.semantic, indent=2)}")
    print(f"\n--- Elements ---")
    for ref, info in snapshot.refs.items():
        text = info.get('text', '')[:30]
        role = info.get('role', '?')
        print(f"  {ref} | {role:15s} | {text}")

    return snapshot


def main():
    parser = argparse.ArgumentParser(description="Run surveys or scan dashboard")
    parser.add_argument("--mode", choices=["legacy", "nim", "scan", "loop", "snapshot"],
                        default="scan", help="Operation mode")
    parser.add_argument("--survey-id", type=str, default=None, help="Survey ID to run")
    parser.add_argument("--url", type=str, default=None, help="Direct survey URL")
    parser.add_argument("--max", type=int, default=5, help="Max surveys (loop mode)")
    parser.add_argument("--tab-id", type=str, default=None, help="Tab ID for snapshot")
    parser.add_argument("--debug", action="store_true", help="Verbose output")

    args = parser.parse_args()

    if args.mode == "legacy":
        return cmd_legacy()

    elif args.mode == "scan":
        return cmd_scan(debug=args.debug)

    elif args.mode == "nim":
        return cmd_nim_survey(
            survey_id=args.survey_id,
            survey_url=args.url,
            debug=args.debug,
        )

    elif args.mode == "loop":
        return cmd_loop(max_surveys=args.max, debug=args.debug)

    elif args.mode == "snapshot":
        return cmd_snapshot(tab_id=args.tab_id)

    return None


if __name__ == "__main__":
    main()
