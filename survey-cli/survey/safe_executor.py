"""
Survey Flow Executor — Safe command execution with registry validation.

Uses command_registry.json to:
1. Pre-flight check every command before execution
2. Execute only safe sequences
3. Auto-record success/failure
4. Prevent known crash patterns (e.g., submit after radio without sleep)

CRITICAL: This module uses SYNCHRONOUS websocket (not async websockets)
to match LangGraph node execution which runs in sync context.
"""

import json
import time
import websocket
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path

from survey.command_registry import (
    CommandRegistry,
    CommandBannedError,
    CommandNotVerifiedError,
    can_execute,
)

# CDP WebSocket URL template
CDP_BASE = "ws://127.0.0.1:9999/devtools/page/"

# Commands that require enforced sleep before click_continue
INPUT_COMMANDS = {"select_radio", "fill_number", "select_dropdown", "fill_textarea"}

# Minimum sleep seconds after input commands (prevents Chrome tab crash)
MIN_SLEEP_AFTER_INPUT = 2


class SurveyFlowExecutor:
    """Executes survey commands with safety validation."""

    def __init__(self, tab_id: str, registry_path: Optional[Path] = None):
        self.tab_id = tab_id
        self.ws_url = f"{CDP_BASE}{tab_id}"
        self.registry = CommandRegistry(registry_path)
        self._ws: Optional[websocket.WebSocket] = None
        self._last_command: Optional[str] = None
        self._last_command_time: float = 0

    def connect(self) -> bool:
        """Connect to CDP WebSocket."""
        try:
            self._ws = websocket.create_connection(self.ws_url, timeout=15)
            return True
        except ConnectionRefusedError:
            print(f"Chrome nicht erreichbar auf Port 9999. Tab-ID: {self.tab_id}")
            return False
        except Exception as e:
            print(f"WebSocket connection failed: {e}")
            return False

    def disconnect(self):
        """Close WebSocket connection."""
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass
            self._ws = None

    def _ensure_connected(self) -> bool:
        """Ensure WebSocket is connected, reconnect if needed."""
        if not self._ws or self._ws.status != websocket.STATUS_CONNECTED:
            return self.connect()
        return True

    def _send_cdp(self, method: str, params: Dict = None) -> Dict:
        """Send CDP command and return result."""
        if not self._ensure_connected():
            raise ConnectionError("WebSocket nicht verbunden. connect() zuerst aufrufen.")

        msg_id = int(time.time() * 1000)
        payload = {"id": msg_id, "method": method}
        if params:
            payload["params"] = params

        self._ws.send(json.dumps(payload))
        response = json.loads(self._ws.recv())

        if "error" in response:
            raise RuntimeError(f"CDP Error: {response['error']}")

        return response.get("result", {})

    def _enforce_sleep_if_needed(self, command_id: str):
        """
        Enforce mandatory sleep after input commands to prevent Chrome crash.
        
        ROOT CAUSE (2026-05-10): click_continue immediately after select_radio
        causes ConnectionClosedError (Chrome tab crash). Minimum 2s sleep required.
        """
        if self._last_command in INPUT_COMMANDS and command_id == "click_continue":
            elapsed = time.time() - self._last_command_time
            if elapsed < MIN_SLEEP_AFTER_INPUT:
                sleep_time = MIN_SLEEP_AFTER_INPUT - elapsed
                print(f"[SAFETY] Enforcing {sleep_time:.1f}s sleep after {self._last_command} before {command_id}")
                time.sleep(sleep_time)

        self._last_command = command_id
        self._last_command_time = time.time()

    def capture_page_text(self) -> str:
        """Get page text content."""
        result = self._send_cdp(
            "Runtime.evaluate",
            {"expression": "document.body.innerText.substring(0, 2000)"}
        )
        return result.get("result", {}).get("value", "")

    def capture_interactive_elements(self) -> List[Dict]:
        """Get all interactive elements on page."""
        result = self._send_cdp(
            "Runtime.evaluate",
            {"expression": '''
                JSON.stringify(Array.from(document.querySelectorAll(
                    "input, select, textarea, button, [role=button]"
                )).map(i => ({
                    tag: i.tagName,
                    type: i.type || "",
                    id: i.id || "",
                    name: i.name || "",
                    text: (i.innerText || "").substring(0, 50),
                    disabled: i.disabled,
                    class: (i.className || "").substring(0, 100)
                })))
            '''}
        )
        return json.loads(result.get("result", {}).get("value", "[]"))

    def capture_radio_mapping(self) -> List[Dict]:
        """Map radio buttons to their labels."""
        result = self._send_cdp(
            "Runtime.evaluate",
            {"expression": '''
                JSON.stringify(Array.from(document.querySelectorAll("input[type=radio]")).map(r => ({
                    id: r.id,
                    label: document.querySelector("label[for='" + r.id + "']")?.innerText.trim() || "no label",
                    name: r.name,
                    checked: r.checked
                })))
            '''}
        )
        return json.loads(result.get("result", {}).get("value", "[]"))

    def select_radio(self, radio_id: str) -> bool:
        """Select a radio button safely."""
        can_execute("select_radio")

        expression = f'''
            (function() {{
                var radio = document.getElementById("{radio_id}");
                if (!radio) return "ELEMENT_NOT_FOUND";
                radio.checked = true;
                radio.dispatchEvent(new Event("change", {{bubbles: true}}));
                return "SELECTED: {radio_id}";
            }})()
        '''
        result = self._send_cdp("Runtime.evaluate", {"expression": expression})
        value = result.get("result", {}).get("value", "")

        if "SELECTED" in value:
            self.registry.record_success("select_radio", f"Radio {radio_id} selected")
            return True

        self.registry.record_failure("select_radio", value, f"Failed to select {radio_id}")
        return False

    def fill_number(self, input_id: str, value: str) -> bool:
        """Fill a number input safely."""
        can_execute("fill_number")

        expression = f'''
            (function() {{
                var input = document.getElementById("{input_id}");
                if (!input) return "ELEMENT_NOT_FOUND";
                input.value = "{value}";
                input.dispatchEvent(new Event("input", {{bubbles: true}}));
                input.dispatchEvent(new Event("change", {{bubbles: true}}));
                return "FILLED: {input_id} = {value}";
            }})()
        '''
        result = self._send_cdp("Runtime.evaluate", {"expression": expression})
        value = result.get("result", {}).get("value", "")

        if "FILLED" in value:
            self.registry.record_success("fill_number", f"Number {input_id} = {value}")
            return True

        self.registry.record_failure("fill_number", value, f"Failed to fill {input_id}")
        return False

    def select_dropdown(self, select_id: str, option_index: int) -> bool:
        """Select dropdown option safely."""
        can_execute("select_dropdown")

        expression = f'''
            (function() {{
                var select = document.getElementById("{select_id}");
                if (!select) return "ELEMENT_NOT_FOUND";
                if (option_index < 0 || option_index >= select.options.length) return "INDEX_OUT_OF_RANGE";
                select.selectedIndex = {option_index};
                select.dispatchEvent(new Event("change", {{bubbles: true}}));
                return "SELECTED: {select_id}[{option_index}]";
            }})()
        '''
        result = self._send_cdp("Runtime.evaluate", {"expression": expression})
        value = result.get("result", {}).get("value", "")

        if "SELECTED" in value:
            self.registry.record_success("select_dropdown", f"Dropdown {select_id}[{option_index}]")
            return True

        self.registry.record_failure("select_dropdown", value, f"Failed to select {select_id}[{option_index}]")
        return False

    def click_continue(self, with_sleep: bool = True, sleep_seconds: int = 2) -> bool:
        """
        Click continue button SAFELY.
        
        CRITICAL: This command is BANNED if called immediately after select_radio
        without sleep. The with_sleep parameter enforces the safety delay.
        """
        if not with_sleep or sleep_seconds < 1:
            try:
                can_execute("click_continue_immediately_after_radio")
            except CommandBannedError as e:
                print(f"BLOCKED: {e}")
                print("FIX: Verwende click_continue(with_sleep=True, sleep_seconds=2)")
                return False

        can_execute("click_continue")

        expression = '''
            (function() {
                var btn = document.getElementById("btn_continue");
                if (!btn) return "BUTTON_NOT_FOUND";
                if (btn.disabled) return "BUTTON_DISABLED";
                btn.click();
                return "CLICKED_CONTINUE";
            })()
        '''
        result = self._send_cdp("Runtime.evaluate", {"expression": expression})
        value = result.get("result", {}).get("value", "")

        if "CLICKED" in value:
            self.registry.record_success("click_continue", "Continue button clicked")
            return True

        self.registry.record_failure("click_continue", value, "Failed to click continue")
        return False

    def execute_actions(self, actions: List[Dict]) -> Dict[str, Any]:
        """
        Execute a list of actions with registry validation and safe sequence enforcement.
        
        Each action dict should have:
          - "command": command ID (e.g., "select_radio", "click_continue")
          - "params": optional dict of parameters for the command
        
        Safe sequences are enforced:
          - After any input command (select_radio, fill_number, etc.), 
            a minimum 2s sleep is enforced before click_continue
          - Banned commands are blocked with CommandBannedError
          - Unverified commands generate warnings but still execute
        
        Returns:
            {
                "success": bool,
                "results": [{"command": str, "success": bool, "error": str or None}],
                "total_success": int,
                "total_fail": int,
                "elapsed_ms": int
            }
        """
        start_time = time.time()
        results = []
        total_success = 0
        total_fail = 0

        for action in actions:
            command_id = action.get("command", "")
            params = action.get("params", {})

            if not command_id:
                results.append({"command": "", "success": False, "error": "No command specified"})
                total_fail += 1
                continue

            # Pre-flight validation
            try:
                can_execute(command_id)
            except CommandBannedError as e:
                print(f"[BLOCKED] {e}")
                results.append({"command": command_id, "success": False, "error": str(e)})
                total_fail += 1
                continue
            except CommandNotVerifiedError as e:
                print(f"[WARNING] {e}")
                # Allow execution but log warning

            # Enforce safe sequence (sleep after input commands before click_continue)
            self._enforce_sleep_if_needed(command_id)

            # Execute command
            try:
                method = getattr(self, command_id, None)
                if method and callable(method):
                    success = method(**params)
                else:
                    # Generic CDP execution for unknown commands
                    success = self._execute_generic_cdp(command_id, params)

                if success:
                    total_success += 1
                    results.append({"command": command_id, "success": True, "error": None})
                else:
                    total_fail += 1
                    results.append({"command": command_id, "success": False, "error": "Command returned False"})

            except Exception as e:
                total_fail += 1
                error_msg = f"{type(e).__name__}: {str(e)[:200]}"
                print(f"[ERROR] {command_id}: {error_msg}")
                results.append({"command": command_id, "success": False, "error": error_msg})
                self.registry.record_failure(command_id, error_msg)

        elapsed_ms = int((time.time() - start_time) * 1000)

        return {
            "success": total_fail == 0,
            "results": results,
            "total_success": total_success,
            "total_fail": total_fail,
            "elapsed_ms": elapsed_ms,
        }

    def _execute_generic_cdp(self, command_id: str, params: Dict) -> bool:
        """
        Execute a generic CDP command not in the method registry.
        
        Used for commands that are not explicitly defined as methods
        but are still safe to execute (e.g., capture_*, custom JS).
        """
        # Map common command patterns to CDP calls
        if command_id.startswith("capture_"):
            # Capture commands don't modify state, always safe
            method = getattr(self, command_id, None)
            if method:
                method()
                return True
            return False

        # Unknown command — log warning and return False
        print(f"[UNKNOWN] Command '{command_id}' not recognized")
        return False

    def execute_safe_sequence(self, sequence_id: str, **kwargs) -> bool:
        """
        Execute a pre-verified safe sequence of commands.
        
        Example:
            executor.execute_safe_sequence("radio_then_continue", 
                radio_id="ans25853.0.2")
        """
        steps = self.registry.get_safe_sequence(sequence_id)
        if not steps:
            print(f"Safe sequence '{sequence_id}' not found in registry")
            return False

        print(f"Executing safe sequence: {sequence_id}")
        print(f"Steps: {' -> '.join(steps)}")

        for step in steps:
            if step.startswith("sleep("):
                seconds = int(step.split("(")[1].split(")")[0].split("-")[0])
                time.sleep(seconds)
            elif step == "capture_page_text":
                text = self.capture_page_text()
                print(f"Page: {text[:100]}...")
            elif step == "capture_radio_mapping":
                mapping = self.capture_radio_mapping()
                print(f"Radios: {len(mapping)} found")
            elif step == "capture_interactive_elements":
                elements = self.capture_interactive_elements()
                print(f"Elements: {len(elements)} found")
            elif step.startswith("select_radio("):
                radio_id = kwargs.get("radio_id")
                if radio_id:
                    self.select_radio(radio_id)
            elif step == "click_continue":
                self.click_continue(with_sleep=True, sleep_seconds=2)

        return True

    def run_with_validation(self, command_id: str, func: Callable, *args, **kwargs):
        """
        Run any function with pre-flight validation and post-flight recording.
        
        Example:
            executor.run_with_validation(
                "select_radio",
                self.select_radio,
                "ans25853.0.2"
            )
        """
        # Pre-flight
        try:
            can_execute(command_id)
        except CommandBannedError as e:
            print(f"BLOCKED: {e}")
            return None
        except CommandNotVerifiedError as e:
            print(f"WARNING: {e}")
            # Allow execution but log warning

        # Execute
        try:
            result = func(*args, **kwargs)
            self.registry.record_success(command_id)
            return result
        except Exception as e:
            self.registry.record_failure(command_id, str(e))
            raise
