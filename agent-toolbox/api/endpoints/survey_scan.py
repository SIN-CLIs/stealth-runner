# ════════════════════════════════════════════════════════════════════════════════╗
# ║  DASHBOARD SCAN — scan dashboard, get next survey                             ║
# ║                                                                               ║
# ║  100% ELEMENT CAPTURE via survey-cli/survey/scanner.py                       ║
# ║  Provider Detection + Trust Scores (SR-53)                                   ║
# ╚═══════════════════════════════════════════════════════════════════════════════╝

from __future__ import annotations

from fastapi import APIRouter, Depends
from ._common import (
    ScanDashboardRequest, ScanDashboardResponse,
    require_survey_ready, update_command_registry,
)

router = APIRouter(tags=["dashboard"])

import json, asyncio, websockets, urllib.request

# ─── TOOL IMPORTS ──────────────────────────────────────────────────────────────
from tools.tool_scan_dashboard import scan as _scan_dashboard, get_next_survey as _get_next


def _read_balance_ws(ws_url: str) -> float:
    """Read balance from dashboard tab via WebSocket."""
    try:
        async def get():
            async with websockets.connect(ws_url) as ws:
                js = """
                (() => {
                    const txt = document.body.innerText || '';
                    const amts = [...txt.matchAll(/(\\d+[.,]\\d{2})/g)];
                    let max = 0;
                    for (const m of amts) {
                        const n = parseFloat(m[1].replace(',', '.'));
                        if (txt.substring(m.index, m.index + 50).includes('€') && n >= 1.0 && n > max)
                            max = n;
                    }
                    return max;
                })()
                """
                await ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                                         "params": {"expression": js}}))
                resp = await asyncio.wait_for(ws.recv(), timeout=5)
                val = json.loads(resp).get("result", {}).get("result", {}).get("value")
                return float(val) if isinstance(val, (int, float)) else 0.0
        return asyncio.run(get())
    except Exception:
        return 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# POST /survey/scan — Scan HeyPiggy dashboard for available surveys
# Tool: survey-cli/tools/tool_scan_dashboard.py (176 lines, standalone)
# Provider Detection: survey-cli/survey/scanner.py:detect_provider()
# Trust Scores: survey-cli/survey/scanner.py:PROVIDER_TRUST_SCORES
#
# Provider Trust Scores:
#   qualtrics 0.9 | toluna 0.8 | cint 0.7 | tivian 0.6 | nfield 0.5
#   samplicio 0.4 | purespectrum 0.3 | ipsos 0.3 | surveyrouter 0.2 | unknown 0.1
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/survey/scan", response_model=ScanDashboardResponse, dependencies=[Depends(require_survey_ready)])
async def api_scan_dashboard(req: ScanDashboardRequest):
    """
    Scans HeyPiggy dashboard for available surveys with 100% element capture.
    
    100% Element Capture:
      ✓ .survey-item cards (title, reward, duration, provider)
      ✓ Provider detection from card text and URL patterns
      ✓ Trust score calculation per provider
      ✓ Balance extraction from body text (max € >= 1.0)
      ✓ Survey count verification
    
    Provider Detection (survey-cli/survey/scanner.py):
      - qualtrics: eu.qualtrics.com, qualtrics.com
      - toluna: enter.ipsosinteractive.com, toluna.com
      - cint: sw.cint.com, cint.com
      - samplicio: rx.samplicio.us
      - purespectrum: screener.purespectrum.com, purespectrum.com
      - nfield: nfieldeu-interviewing.nfieldmr.com
      - ipsos: enter.ipsosinteractive.com
    
    Status: NO AUTO-RUN! Manual survey opening only until 100 verified.
    """
    try:
        result = _scan_dashboard(cdp_port=req.cdp_port)
        balance = result.get("balance", 0.0)
        if not balance:
            raw = urllib.request.urlopen(f"http://127.0.0.1:{req.cdp_port}/json/list", timeout=3).read()
            pages = json.loads(raw)
            for p in pages:
                if p.get("type") == "page" and "heypiggy" in p.get("url", ""):
                    balance = _read_balance_ws(p.get("webSocketDebuggerUrl", ""))
                    break
        
        update_command_registry("scan_dashboard", True, {
            "surveys": len(result.get("surveys", [])),
            "balance": balance,
        })
        return ScanDashboardResponse(
            status="ok",
            balance=balance,
            surveys=result.get("surveys", []),
            count=len(result.get("surveys", [])),
        )
    except Exception as e:
        update_command_registry("scan_dashboard", False, {"error": str(e)})
        return ScanDashboardResponse(status="error", reason=str(e))