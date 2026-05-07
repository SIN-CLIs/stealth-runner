"""================================================================================
BATCH EXECUTOR — Batch-Actions → CDP WebSocket Execution
================================================================================

WAS IST DAS?
  Führt vom Nemotron 3 Omni entschiedene Batch-Actions aus.
  Übersetzt high-level Actions ("click @e42", "fill @e15 'Berlin'")
  in CDP Runtime.evaluate Calls mit provider-spezifischem JavaScript.

ARCHITEKTUR:
  ┌─────────────────────┐
  │  Batch Actions      │
  │  [{"ref":"@e0",     │
  │   "action":"click"}]│
  └─────────────────────┘
         │
         ▼
  ┌─────────────────────┐
  │  BatchExecutor      │
  │  .execute()         │
  └─────────────────────┘
         │
         ▼
  ┌─────────────────────┐
  │  Provider-Routing   │
  │  (Qualtrics,        │
  │   Toluna, Strat7)   │
  └─────────────────────┘
         │
         ▼
  ┌─────────────────────┐
  │  CDP Runtime.       │
  │  evaluate(JS)         │
  └─────────────────────┘
         │
         ▼
  ┌─────────────────────┐
  │  ActionResult[]     │
  │  (Success/Error)    │
  └─────────────────────┘

WARUM Batch statt Einzel-Actions?
  Legacy: Agent ruft 20× get_window_state(), 20× click().
  NEMO: Eine Decision = 5 Actions → Ein WebSocket Call.
  → 5× schneller, weniger Round-Trips, stabiler.

PROVIDER-SPEZIFISCH:
  Jeder Survey-Provider hat unterschiedliche DOM-Strukturen:
  - Qualtrics: .NextButton, .LabelWrapper, input[type=radio]
  - TolunaStart: .cf-radio, button
  - Strat7: .bsbutton, input[type=radio]
  → BatchExecutor mappt Actions auf provider-spezifisches JS.

DEPENDENZEN:
  - CDP WebSocket Verbindung
  - websocket-client (pip install websocket-client)
  - Provider-Konfiguration (PROVIDER_COMMANDS dict)

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
import websocket
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field


@dataclass
class ActionResult:
    """Result of a single batch action."""
    action: str
    ref: str = ""
    success: bool = True
    error: Optional[str] = None
    elapsed_ms: float = 0.0
    screenshot_path: Optional[str] = None


@dataclass
class BatchResult:
    """Result of a complete batch execution."""
    actions: List[ActionResult] = field(default_factory=list)
    total_success: int = 0
    total_fail: int = 0
    total_elapsed_ms: float = 0.0
    page_changed: bool = False
    new_snapshot_needed: bool = True


# ── Provider-specific CDP commands ─────────────────────

PROVIDER_COMMANDS = {
    "qualtrics": {
        "click_next": 'document.querySelector(".NextButton").click()',
        "click_radio": 'document.querySelectorAll("input[type=radio]")[{idx}].click()',
        "click_checkbox": 'document.querySelectorAll("input[type=checkbox]")[{idx}].click()',
        "fill_text": '(function(v){{var t=document.querySelector("textarea:not(.g-recaptcha-response)");if(!t){{var i=document.querySelector("input[type=text]");if(i){{i.value=v;i.dispatchEvent(new Event("input",{{bubbles:true}}));i.dispatchEvent(new Event("change",{{bubbles:true}}));}}}}else{{t.value=v;t.dispatchEvent(new Event("input",{{bubbles:true}}));t.dispatchEvent(new Event("change",{{bubbles:true}}));}}}})("{value}")',
    },
    "tolunastart": {
        "click_next": 'document.querySelector("button").click()',
        "click_radio": '(function(){{var rs=document.querySelectorAll(".cf-radio");rs[{idx}].click();}})()',
        "click_checkbox": '(function(){{var cbs=document.querySelectorAll(".cf-checkbox");cbs[{idx}].click();}})()',
        "fill_text": '(function(v){{var i=document.querySelector("input[type=number],input[type=text]");if(i){{i.value=v;i.dispatchEvent(new Event("input",{{bubbles:true}}));i.dispatchEvent(new Event("change",{{bubbles:true}}));}}}})("{value}")',
    },
    "strat7": {
        "click_next": 'document.querySelector(".bsbutton:not([disabled])").click()',
        "click_radio": 'document.querySelectorAll("input[type=radio]")[{idx}].click()',
    },
    "brand_ambassador": {
        "click_next": 'document.querySelector(".submit-btn,button[type=submit]").click()',
        "click_radio": 'document.querySelectorAll("input[type=radio]")[{idx}].click()',
    },
    "purespectrum": {
        "click_next": 'document.querySelector("button[type=submit]").click()',
        "fill_text": '(function(v){{var t=document.querySelector("textarea");if(t){{t.value=v;t.dispatchEvent(new Event("input",{{bubbles:true}}));t.dispatchEvent(new Event("change",{{bubbles:true}}));}}}})("{value}")',
    },
}

GENERIC_COMMANDS = {
    "click_next": 'document.querySelector("button, .NextButton, .btn-primary, input[type=submit]").click()',
    "click_radio": 'document.querySelectorAll("input[type=radio]")[{idx}].click()',
    "click_checkbox": 'document.querySelectorAll("input[type=checkbox]")[{idx}].click()',
    "fill_text": '(function(v){{var el=document.querySelector("textarea,input[type=text],input[type=number]");if(el){{el.value=v;el.dispatchEvent(new Event("input",{{bubbles:true}}));el.dispatchEvent(new Event("change",{{bubbles:true}}));}}}})("{value}")',
}


class BatchExecutor:
    """Execute batch actions from NIM decisions via CDP WebSocket.

    Each action type is translated to provider-specific CDP JavaScript.
    """

    def __init__(self, ws_url: str, provider: str = "unknown"):
        self.ws_url = ws_url
        self.provider = provider
        self.commands = PROVIDER_COMMANDS.get(provider, GENERIC_COMMANDS)

    def execute(self, actions: List[Dict[str, Any]]) -> BatchResult:
        """Execute a list of batch actions.

        Args:
            actions: List of action dicts from NIM decision
                     [{"ref": "@e0", "action": "click"}, ...]

        Returns:
            BatchResult with per-action results
        """
        result = BatchResult()
        start = time.monotonic()

        ws = websocket.create_connection(self.ws_url, timeout=15)

        for action in actions:
            ar = self._execute_single(ws, action)
            result.actions.append(ar)
            if ar.success:
                result.total_success += 1
            else:
                result.total_fail += 1

        ws.close()
        result.total_elapsed_ms = round((time.monotonic() - start) * 1000)

        # If any action was a submit/next, page likely changed
        result.page_changed = any(
            a.get("action") in ("submit", "click") and
            a.get("ref", "").startswith("@e") is False
            for a in actions
        )

        return result

    def _execute_single(self, ws, action: Dict[str, Any]) -> ActionResult:
        """Execute a single action via CDP."""
        action_type = action.get("action", "")
        ref = action.get("ref", "")
        value = action.get("value", "")
        ms = action.get("ms", 0)

        a_start = time.monotonic()

        try:
            js = self._build_js(action_type, ref, value, ms)
            if js:
                ws.send(json.dumps({
                    "id": 0, "method": "Runtime.evaluate",
                    "params": {"expression": js}
                }))
                json.loads(ws.recv())  # consume response

            if action_type == "wait":
                time.sleep(ms / 1000)

            return ActionResult(
                action=action_type,
                ref=ref,
                success=True,
                elapsed_ms=(time.monotonic() - a_start) * 1000,
            )

        except Exception as e:
            return ActionResult(
                action=action_type,
                ref=ref,
                success=False,
                error=str(e)[:200],
                elapsed_ms=(time.monotonic() - a_start) * 1000,
            )

    def _build_js(self, action_type: str, ref: str, value: str, ms: int) -> Optional[str]:
        """Build the CDP JavaScript string for an action."""
        cmd = self.commands

        if action_type == "click":
            if ref and ref.startswith("@e"):
                # Click by element index (positional)
                idx = int(ref[2:])  # @e42 → 42
                js = cmd.get("click_radio", GENERIC_COMMANDS["click_radio"])
                return js.format(idx=idx)
            else:
                # Click next/submit button
                return cmd.get("click_next", GENERIC_COMMANDS["click_next"])

        elif action_type == "select":
            if ref and ref.startswith("@e"):
                idx = int(ref[2:])
                js = cmd.get("click_radio", GENERIC_COMMANDS["click_radio"])
                return js.format(idx=idx)

        elif action_type == "check":
            if ref and ref.startswith("@e"):
                idx = int(ref[2:])
                js = cmd.get("click_checkbox", GENERIC_COMMANDS["click_checkbox"])
                return js.format(idx=idx)

        elif action_type == "fill":
            js = cmd.get("fill_text", GENERIC_COMMANDS["fill_text"])
            if value:
                return js.format(value=value.replace('"', '\\"'))
            return None

        elif action_type == "submit":
            return cmd.get("click_next", GENERIC_COMMANDS["click_next"])

        elif action_type == "wait":
            time.sleep(ms / 1000)
            return None

        elif action_type == "complete":
            # Survey is done — no action needed
            return None

        elif action_type == "skip":
            return None

        return None

    @staticmethod
    def read_page_text(ws_url: str) -> str:
        """Read the current page text for completion detection."""
        ws = websocket.create_connection(ws_url, timeout=15)
        ws.send(json.dumps({
            "id": 0, "method": "Runtime.evaluate",
            "params": {"expression": "document.body.innerText.substring(0, 500)"}
        }))
        r = json.loads(ws.recv())
        ws.close()
        return r.get("result", {}).get("result", {}).get("value", "")

    @staticmethod
    def is_completed(ws_url: str) -> bool:
        """Check if survey is completed."""
        text = BatchExecutor.read_page_text(ws_url).lower()
        completion_markers = [
            "zurück zur website",
            "thank you",
            "vielen dank",
            "survey complete",
            "umfrage beendet",
            "gutgeschrieben",
        ]
        return any(marker in text for marker in completion_markers)
