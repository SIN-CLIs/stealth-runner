#!/usr/bin/env python3
"""
================================================================================
FIND SURVEY — Survey-ID aus Dashboard extrahieren

WAS DAS TUT:
  Scannt HeyPiggy Dashboard nach verfuegbaren Surveys.
  Extrahiert Survey-IDs aus clickSurvey() calls oder DOM-Elementen.

VERWENDUNG:
  result = find_surveys(dashboard_ws)
  # result = {"surveys": [{"id": "67064749", "text": "6 Min  |  0.15 €", "idx": 0}, ...]}

  # Oder: nur erste Survey
  result = find_first_survey(dashboard_ws)
  # result = {"id": "67064749", "ws": "ws://...", "url": "..."}

INTEGRATION:
  - preflight_check() gibt dashboard_ws zurueck
  - find_surveys() -> survey_cli/commands/open_survey.py
  - open_survey() -> CDP Runtime.evaluate clickSurvey()

=================================================================================="""

import json
import time
import urllib.request
import websocket

CHROME_PORT = 9999


def find_surveys(dashboard_ws: str, max_surveys: int = 20) -> dict:
    """
    Findet alle Survey-IDs auf dem HeyPiggy Dashboard.

    Returns:
        {
            "status": "ok" | "error",
            "surveys": [
                {"id": "67064749", "text": "6 Min  |  0.15 €", "reward": 0.15, "idx": 0},
                {"id": "67064750", "text": "8 Min  |  0.14 €", "reward": 0.14, "idx": 1},
                ...
            ],
            "count": int,
        }
    """
    try:
        ws = websocket.create_connection(dashboard_ws, timeout=15)
        ws.send(
            json.dumps(
                {
                    "id": 1,
                    "method": "Runtime.evaluate",
                    "params": {
                        "expression": """
(function() {
    var results = [];
    
    // Method 1: Find clickSurvey() calls in onclick attributes
    var clickables = document.querySelectorAll('[onclick*="clickSurvey"], [data-survey-id]');
    for (var i = 0; i < clickables.length && results.length < 20; i++) {
        var el = clickables[i];
        var onclick = el.getAttribute('onclick') || '';
        var dataId = el.getAttribute('data-survey-id') || '';
        var match = onclick.match(/clickSurvey\\(['\"]([^'\"]+)['\"]\\)/);
        if (match) {
            var text = (el.textContent || '').trim().replace(/\\s+/g, ' ').substring(0, 100);
            var priceMatch = text.match(/(\\d+\\.\\d+)\\s*€/);
            var price = priceMatch ? parseFloat(priceMatch[1]) : 0;
            results.push({
                id: match[1],
                text: text,
                reward: price,
                idx: results.length
            });
        } else if (dataId) {
            var text = (el.textContent || '').trim().replace(/\\s+/g, ' ').substring(0, 100);
            var priceMatch = text.match(/(\\d+\\.\\d+)\\s*€/);
            var price = priceMatch ? parseFloat(priceMatch[1]) : 0;
            results.push({
                id: dataId,
                text: text,
                reward: price,
                idx: results.length
            });
        }
    }
    
    // Method 2: Parse body text for survey cards
    if (results.length === 0) {
        var body = document.body.innerText;
        var lines = body.split('\\n');
        var lastId = '';
        for (var i = 0; i < lines.length; i++) {
            var line = lines[i].trim();
            // Price pattern: "0.15 €"
            var priceMatch = line.match(/^(\\d+\\.\\d+)\\s*€/);
            if (priceMatch && lastId) {
                var price = parseFloat(priceMatch[1]);
                results.push({
                    id: lastId,
                    text: line + ' | ' + (lines[i-1] || '').trim(),
                    reward: price,
                    idx: results.length
                });
                lastId = '';
            }
            // Survey ID pattern: 7-8 digits
            if (/\\d{7,8}/.test(line)) {
                lastId = line.trim();
            }
        }
    }
    
    return JSON.stringify({
        status: 'ok',
        surveys: results,
        count: results.length
    });
})()
"""
                    },
                }
            )
        )
        r = json.loads(ws.recv())
        ws.close()

        raw = r.get("result", {}).get("result", {}).get("value", "{}")
        data = json.loads(raw)

        return {
            "status": "ok",
            "surveys": data.get("surveys", []),
            "count": data.get("count", 0),
        }
    except Exception as e:
        return {"status": "error", "surveys": [], "count": 0, "error": str(e)}


def find_first_survey(dashboard_ws: str) -> dict:
    """Findet die erste/beste Survey auf dem Dashboard.

    Sortiert nach: hoechster Reward zuerst.
    """
    result = find_surveys(dashboard_ws)
    if result["status"] != "ok" or not result["surveys"]:
        return {"status": "error", "reason": "No surveys found"}

    # Sort by reward (highest first)
    surveys = sorted(result["surveys"], key=lambda s: s.get("reward", 0), reverse=True)
    first = surveys[0]

    return {
        "status": "ok",
        "id": first["id"],
        "text": first["text"],
        "reward": first["reward"],
        "idx": first["idx"],
    }


def click_survey(dashboard_ws: str, survey_id: str, timeout: float = 5.0) -> dict:
    """
    Klickt Survey-Card via clickSurvey() auf dem Dashboard.

    Returns:
        {
            "status": "ok" | "clicked" | "error",
            "new_tab_ws": str | None,  # Survey-Tab WS URL falls neuer Tab
            "new_tab_url": str | None,
            "modal_detected": bool,
            "body_text": str,           # Page text nach Klick
        }
    """
    # Get initial tab list
    pages_before = {}
    try:
        pages = json.loads(
            urllib.request.urlopen(f"http://127.0.0.1:{CHROME_PORT}/json", timeout=5).read()
        )
        pages_before = {p.get("id", ""): p.get("url", "") for p in pages}
    except Exception:
        pass

    # Click survey card
    try:
        ws = websocket.create_connection(dashboard_ws, timeout=15)
        ws.send(
            json.dumps(
                {
                    "id": 1,
                    "method": "Runtime.evaluate",
                    "params": {"expression": f'clickSurvey("{survey_id}")'},
                }
            )
        )
        json.loads(ws.recv())  # consume response
        ws.close()
        print(f"  [CLICK] clickSurvey('{survey_id}') executed")
    except Exception as e:
        return {"status": "error", "reason": str(e)}

    # Wait for page transition
    time.sleep(timeout)

    # Find new tab
    new_tab_ws = None
    new_tab_url = None
    try:
        pages = json.loads(
            urllib.request.urlopen(f"http://127.0.0.1:{CHROME_PORT}/json", timeout=5).read()
        )
        for p in pages:
            tab_id = p.get("id", "")
            url = p.get("url", "")
            if tab_id not in pages_before:
                # New tab detected
                if url and not url.startswith("chrome-extension") and not url.startswith("about:"):
                    new_tab_ws = p["webSocketDebuggerUrl"]
                    new_tab_url = url
                    print(f"  [NEW TAB] {url[:70]}")
                    break
    except Exception:
        pass

    # Get dashboard body text to check for modal
    modal_detected = False
    body_text = ""
    try:
        ws = websocket.create_connection(dashboard_ws, timeout=15)
        ws.send(
            json.dumps(
                {
                    "id": 2,
                    "method": "Runtime.evaluate",
                    "params": {"expression": "document.body.innerText.substring(0, 500)"},
                }
            )
        )
        r = json.loads(ws.recv())
        ws.close()
        body_text = r.get("result", {}).get("result", {}).get("value", "")

        # Modal detection: overlay, popup, oder survey-start button
        if any(
            w in body_text.lower()
            for w in ["umfrage starten", "survey start", "teilnehmen", "beginnen"]
        ):
            modal_detected = True
            print("  [MODAL] Detected on dashboard")
    except Exception:
        pass

    return {
        "status": "ok" if new_tab_ws or modal_detected else "error",
        "new_tab_ws": new_tab_ws,
        "new_tab_url": new_tab_url,
        "modal_detected": modal_detected,
        "body_text": body_text,
    }


if __name__ == "__main__":
    # Test with current dashboard
    import sys

    sys.path.insert(0, "/Users/jeremy/dev/stealth-runner/survey-cli")
    from commands.preflight_check import preflight_check

    check = preflight_check()
    if not check["ready"]:
        print("Session not ready. Run start_heypiggy first.")
        sys.exit(1)

    print(f"\n{'=' * 50}")
    print("  FIND SURVEY — Dashboard scan")
    print(f"{'=' * 50}")

    # Find surveys
    result = find_surveys(check["tab_ws"])
    print(f"  Surveys found: {result['count']}")

    for s in result.get("surveys", [])[:5]:
        print(f"  [{s['idx']}] ID={s['id']} | Reward=€{s['reward']:.2f} | {s['text'][:50]}")

    if result.get("surveys"):
        # Try to click first survey
        first = sorted(result["surveys"], key=lambda x: x["reward"], reverse=True)[0]
        print(f"\n  Clicking survey {first['id']} (€{first['reward']:.2f})...")
        click_result = click_survey(check["tab_ws"], first["id"])
        print(f"  Status: {click_result['status']}")
        print(
            f"  New tab WS: {click_result['new_tab_ws'][:50] if click_result['new_tab_ws'] else 'NONE'}"
        )
        print(f"  Modal: {'YES' if click_result['modal_detected'] else 'NO'}")

    print(f"{'=' * 50}")
