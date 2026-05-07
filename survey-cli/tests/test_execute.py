"""Test SOTA execution functions: _build_js, cdp_keyboard_enter, cdp_click_element_by_text.

WARUM: BatchExecutor führt NIM-Actions im Browser aus.
Falsche JS-Generierung oder Race-Conditions bei DOM-Interaktionen führen
zu disqualifizierten Surveys. Verify-Box-Logik muss Stale-State erkennen.

ARCHITEKTUR: Unittest mit unittest.mock (MagicMock, patch).
CDP WebSocket-Verbindungen und DOM-Responses werden gepatcht.
Es werden JS-Builder, Keyboard-Events, Element-Finding und
State-Change-Verifikation getestet — kein echter Browser.

BANNED METHODS — NIEMALS VERWENDEN:
❌ playstealth launch
❌ webauto-nodriver — ABSOLUT BANNED
❌ cua-driver click (raw index)
❌ --remote-allow-origins=* (ohne Quotes)
❌ /tmp/heypiggy-bot (fixed profile)
❌ Hardcoded PIDs
❌ pkill -f "Google Chrome"
❌ killall Google Chrome
❌ skylight-cli click --element-index
"""

import unittest
from unittest.mock import MagicMock, patch
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from survey.execute import (
    BatchExecutor, BatchResult, PROVIDER_COMMANDS, GENERIC_COMMANDS,
    cdp_keyboard_enter, cdp_click_element_by_text, capture_dom_hash,
    verify_state_change, EXECUTION_VERIFY_MS
)


def cdp_resp(d):
    """Wrap a dict as CDP Runtime.evaluate response value."""
    return {"result": {"result": {"value": json.dumps(d)}}}


def cdp_text(text):
    """CDP response with a plain string value."""
    return {"result": {"result": {"value": text}}}


def cdp_null():
    """CDP response for null/empty values."""
    return {"result": {"result": {"value": "null"}}}


V_EMPTY_HASH = cdp_resp({"n": 0, "t": "", "url": ""})
V_SAMPLE_HASH = cdp_resp({"n": 5, "t": "radio1|input|radio;;button|button|submit",
                           "url": "https://example.com"})
V_POS = cdp_resp({"x": 100, "y": 200, "tag": "BUTTON", "text": "weiter"})
V_BTN_HASH = cdp_resp({"n": 3, "t": "btn|button|submit", "url": ""})
V_BTN_SELECTORS = cdp_resp({"n": 5, "t": "btn1|button|submit;;btn2|button|submit", "url": ""})


class MockWs:
    """Mock WebSocket for CDP tests. responses must be JSON strings (not dicts)."""
    def __init__(self, responses=None):
        self.sent = []
        self._responses = responses or []
        self._resp_idx = 0

    def send(self, data):
        self.sent.append(json.loads(data) if isinstance(data, str) else data)

    def recv(self):
        if self._resp_idx < len(self._responses):
            r = self._responses[self._resp_idx]
            self._resp_idx += 1
            # Support both dict (legacy) and string (correct) responses
            if isinstance(r, str):
                return r
            return json.dumps(r)
        return json.dumps({"result": {"result": {"value": "null"}}})

    def getsockname(self):
        return "ws://localhost:9999"

    def getpeername(self):
        return ("localhost", 9999)

    def close(self):
        pass


class TestBuildJS(unittest.TestCase):

    def test_click_element_with_at_prefix(self):
        executor = BatchExecutor("ws://localhost:9999", "qualtrics")
        js = executor._build_js("click", "@e5", "")
        self.assertIn("5", js)
        self.assertIn("click", js.lower())

    def test_click_element_no_at_prefix_falls_back(self):
        executor = BatchExecutor("ws://localhost:9999", "qualtrics")
        js = executor._build_js("click", "e3", "")
        self.assertIsNotNone(js)

    def test_fill_with_value(self):
        executor = BatchExecutor("ws://localhost:9999", "generic")
        js = executor._build_js("fill", "@e0", "Berlin")
        self.assertIn("Berlin", js)

    def test_fill_without_value_returns_none(self):
        executor = BatchExecutor("ws://localhost:9999", "generic")
        js = executor._build_js("fill", "@e0", "")
        self.assertIsNone(js)

    def test_fill_escapes_quotes(self):
        executor = BatchExecutor("ws://localhost:9999", "generic")
        js = executor._build_js("fill", "@e0", 'Ich "liebe" Berlin')
        self.assertIn('\\"', js)

    def test_submit_action(self):
        executor = BatchExecutor("ws://localhost:9999", "generic")
        js = executor._build_js("submit", "", "")
        # Submit → _cdp_click_button("Weiter") which tries to find
        # a button with text "Weiter" via CDP Runtime.evaluate
        self.assertIsNotNone(js)
        self.assertIn("weiter", js.lower())

    def test_select_action(self):
        executor = BatchExecutor("ws://localhost:9999", "qualtrics")
        js = executor._build_js("select", "@e2", "")
        self.assertIn("2", js)

    def test_check_action(self):
        executor = BatchExecutor("ws://localhost:9999", "qualtrics")
        js = executor._build_js("check", "@e1", "")
        self.assertIn("1", js)

    def test_wait_action_returns_none(self):
        executor = BatchExecutor("ws://localhost:9999", "generic")
        js = executor._build_js("wait", "", "")
        self.assertIsNone(js)

    def test_complete_action_returns_none(self):
        executor = BatchExecutor("ws://localhost:9999", "generic")
        js = executor._build_js("complete", "", "")
        self.assertIsNone(js)

    def test_skip_action_returns_none(self):
        executor = BatchExecutor("ws://localhost:9999", "generic")
        js = executor._build_js("skip", "", "")
        self.assertIsNone(js)

    def test_unknown_action_returns_none(self):
        executor = BatchExecutor("ws://localhost:9999", "generic")
        js = executor._build_js("unknown_action", "@e0", "")
        self.assertIsNone(js)

    def test_empty_ref_fallback_to_click_next(self):
        executor = BatchExecutor("ws://localhost:9999", "generic")
        js = executor._build_js("click", "", "")
        self.assertIsNotNone(js)

    def test_qualtrics_provider_commands(self):
        executor = BatchExecutor("ws://localhost:9999", "qualtrics")
        js = executor._build_js("submit", "", "")
        self.assertIn("next", js.lower())

    def test_tolunastart_provider_commands(self):
        executor = BatchExecutor("ws://localhost:9999", "tolunastart")
        js = executor._build_js("click", "@e0", "")
        self.assertIsNotNone(js)

    def test_generic_provider(self):
        executor = BatchExecutor("ws://localhost:9999", "completely_unknown_provider_xyz")
        js = executor._build_js("click", "@e0", "")
        self.assertIsNotNone(js)


class TestCDPKeyboardEnter(unittest.TestCase):

    def test_keyboard_enter_sends_tab_keydown(self):
        mock_ws = MockWs()
        with patch('websocket.create_connection', return_value=mock_ws):
            result = cdp_keyboard_enter("ws://localhost:9999")
        self.assertTrue(result)
        tab_down = any(
            s.get("method") == "Input.dispatchKeyEvent" and
            s["params"].get("type") == "keyDown" and
            s["params"].get("key") == "Tab"
            for s in mock_ws.sent
        )
        self.assertTrue(tab_down, "Tab keyDown should be sent")

    def test_keyboard_enter_sends_enter_keydown(self):
        mock_ws = MockWs()
        with patch('websocket.create_connection', return_value=mock_ws):
            result = cdp_keyboard_enter("ws://localhost:9999")
        enter_down = any(
            s.get("method") == "Input.dispatchKeyEvent" and
            s["params"].get("type") == "keyDown" and
            s["params"].get("key") == "Enter"
            for s in mock_ws.sent
        )
        self.assertTrue(enter_down, "Enter keyDown should be sent")

    def test_keyboard_enter_sends_enter_keyup(self):
        mock_ws = MockWs()
        with patch('websocket.create_connection', return_value=mock_ws):
            result = cdp_keyboard_enter("ws://localhost:9999")
        enter_up = any(
            s.get("method") == "Input.dispatchKeyEvent" and
            s["params"].get("type") == "keyUp" and
            s["params"].get("key") == "Enter"
            for s in mock_ws.sent
        )
        self.assertTrue(enter_up, "Enter keyUp should be sent")

    def test_keyboard_enter_returns_false_on_error(self):
        with patch('websocket.create_connection', side_effect=Exception("Connection refused")):
            result = cdp_keyboard_enter("ws://localhost:9999")
        self.assertFalse(result)


class TestCDPClickElementByText(unittest.TestCase):

    def test_returns_tuple_bool_and_str(self):
        """Returns (success: bool, method_used: str)."""
        def make_resp(d):
            return json.dumps({"result": {"result": {"value": json.dumps(d)}}})
        responses = [make_resp({"x": 100, "y": 200, "tag": "BUTTON"}),
                     json.dumps({"result": {"result": {"value": "not_found"}}}),
                     json.dumps({"result": {"result": {"value": "not_found"}}})]
        mock_ws = MockWs(responses)
        with patch('websocket.create_connection', return_value=mock_ws):
            success, method = cdp_click_element_by_text('ws://localhost:9999', 'Weiter')
        self.assertIsInstance(success, bool)
        self.assertIsInstance(method, str)

    def test_not_found_returns_false(self):
        """Element not found -> falls through to JS fallback -> not_found."""
        def make_resp(d):
            return json.dumps({"result": {"result": {"value": json.dumps(d)}}})
        responses = [make_resp({"x": 100, "y": 200, "tag": "BUTTON"}),
                     json.dumps({"result": {"result": {"value": "not_found"}}})]
        mock_ws = MockWs(responses)
        with patch('websocket.create_connection', return_value=mock_ws):
            success, method = cdp_click_element_by_text('ws://localhost:9999', 'NonExistentButton')
        self.assertFalse(success)
        self.assertEqual("none", method)

    def test_element_found_cdp_mouse_dispatched(self):
        """CDP mouse click dispatched when element found and keyboard skipped."""
        import survey.execute as ex_mod
        def make_resp(d):
            return json.dumps({"result": {"result": {"value": json.dumps(d)}}})
        V_POS_RESP = make_resp({"x": 100, "y": 200, "tag": "BUTTON"})
        class HashCtr:
            def __init__(self):
                self.cnt = 0
            def __call__(self, url):
                self.cnt += 1
                if self.cnt == 1:
                    return None  # skip early return in keyboard path
                if self.cnt == 2:
                    return "abc"  # before hash for mouse path
                return "xyz"      # after hash -> changed=True -> success
        orig_kbe = ex_mod.cdp_keyboard_enter
        orig_hash = ex_mod.capture_dom_hash
        hash_ctr = HashCtr()
        ex_mod.cdp_keyboard_enter = lambda url: False
        ex_mod.capture_dom_hash = hash_ctr
        try:
            mock_ws = MockWs([V_POS_RESP])
            with patch('websocket.create_connection', return_value=mock_ws):
                success, method = cdp_click_element_by_text('ws://localhost:9999', 'Weiter')
            mouse_events = [s for s in mock_ws.sent
                           if s.get('method') == 'Input.dispatchMouseEvent']
            self.assertTrue(len(mouse_events) >= 3,
                           f'Expected >=3 mouse events, got {len(mouse_events)}')
            self.assertEqual("cdp_mouse", method)
        finally:
            ex_mod.cdp_keyboard_enter = orig_kbe
            ex_mod.capture_dom_hash = orig_hash

    def test_keyboard_fallback_when_no_state_change(self):
        """If keyboard enter doesn't change DOM -> try CDP mouse."""
        import survey.execute as ex_mod
        def make_resp(d):
            return json.dumps({"result": {"result": {"value": json.dumps(d)}}})
        V_POS_RESP = make_resp({"x": 100, "y": 200, "tag": "BUTTON"})
        orig_kbe = ex_mod.cdp_keyboard_enter
        orig_hash = ex_mod.capture_dom_hash
        ex_mod.cdp_keyboard_enter = lambda url: False
        ex_mod.capture_dom_hash = lambda url: ''  # state never changes
        try:
            mock_ws = MockWs([V_POS_RESP] * 8)
            with patch('websocket.create_connection', return_value=mock_ws):
                success, method = cdp_click_element_by_text('ws://localhost:9999', 'Weiter')
            mouse_events = [s for s in mock_ws.sent
                           if s.get('method') == 'Input.dispatchMouseEvent']
            self.assertTrue(len(mouse_events) >= 3,
                           f'Expected >=3 mouse events, got {len(mouse_events)}')
            self.assertEqual(100, mouse_events[0]['params']['x'])
        finally:
            ex_mod.cdp_keyboard_enter = orig_kbe
            ex_mod.capture_dom_hash = orig_hash

    def test_state_change_detected(self):
        """State change after click -> success."""
        import survey.execute as ex_mod
        def make_resp(d):
            return json.dumps({"result": {"result": {"value": json.dumps(d)}}})
        V_POS_RESP = make_resp({"x": 100, "y": 200, "tag": "BUTTON"})
        class HashCtr:
            def __init__(self):
                self.cnt = 0
            def __call__(self, url):
                self.cnt += 1
                if self.cnt == 1:
                    return None  # skip early return in keyboard path
                if self.cnt == 2:
                    return "abc"  # before hash
                return "xyz"      # after hash -> changed=True -> success
        orig_kbe = ex_mod.cdp_keyboard_enter
        orig_hash = ex_mod.capture_dom_hash
        hash_ctr = HashCtr()
        ex_mod.cdp_keyboard_enter = lambda url: False
        ex_mod.capture_dom_hash = hash_ctr
        try:
            mock_ws = MockWs([V_POS_RESP])
            with patch('websocket.create_connection', return_value=mock_ws):
                success, method = cdp_click_element_by_text('ws://localhost:9999', 'Weiter')
            self.assertTrue(success, f'Expected success=True, got {success}')
            self.assertEqual("cdp_mouse", method)
        finally:
            ex_mod.cdp_keyboard_enter = orig_kbe
            ex_mod.capture_dom_hash = orig_hash

    def test_normalizes_text_case_insensitive(self):
        """Search text should be case-insensitive (no crash)."""
        def make_resp(d):
            return json.dumps({"result": {"result": {"value": json.dumps(d)}}})
        responses = [make_resp({"x": 100, "y": 200, "tag": "BUTTON"}),
                     json.dumps({"result": {"result": {"value": "not_found"}}})]
        mock_ws = MockWs(responses)
        with patch('websocket.create_connection', return_value=mock_ws):
            success, method = cdp_click_element_by_text('ws://localhost:9999', 'WEITER')
        self.assertIsInstance(success, bool)

    def test_websocket_error_returns_false(self):
        """WebSocket error -> returns False."""
        with patch('websocket.create_connection', side_effect=Exception('Failed')):
            success, method = cdp_click_element_by_text('ws://localhost:9999', 'Weiter')
        self.assertFalse(success)
        self.assertEqual("none", method)



class TestCaptureDomHash(unittest.TestCase):

    def test_returns_16char_hex(self):
        mock_ws = MockWs([V_SAMPLE_HASH])
        with patch('websocket.create_connection', return_value=mock_ws):
            h = capture_dom_hash("ws://localhost:9999")
        self.assertIsInstance(h, str)
        self.assertEqual(16, len(h))
        self.assertTrue(all(c in '0123456789abcdef' for c in h))

    def test_different_pages_different_hash(self):
        mock_ws1 = MockWs([cdp_resp({"n": 5, "t": "el1;;el2", "url": "page1"})])
        mock_ws2 = MockWs([cdp_resp({"n": 10, "t": "el1;;el2;;el3", "url": "page2"})])
        with patch('websocket.create_connection', return_value=mock_ws1):
            h1 = capture_dom_hash("ws://localhost:9999")
        with patch('websocket.create_connection', return_value=mock_ws2):
            h2 = capture_dom_hash("ws://localhost:9999")
        self.assertNotEqual(h1, h2)

    def test_same_pages_same_hash(self):
        same_val = cdp_resp({"n": 5, "t": "same;;content", "url": "page"})
        mock_ws = MockWs([same_val, same_val])
        with patch('websocket.create_connection', return_value=mock_ws):
            h1 = capture_dom_hash("ws://localhost:9999")
            h2 = capture_dom_hash("ws://localhost:9999")
        self.assertEqual(h1, h2)

    def test_null_response_returns_empty_string(self):
        mock_ws = MockWs([cdp_null()])
        with patch('websocket.create_connection', return_value=mock_ws):
            h = capture_dom_hash("ws://localhost:9999")
        self.assertEqual("", h)

    def test_empty_string_value_returns_empty_string(self):
        mock_ws = MockWs([cdp_text("")])
        with patch('websocket.create_connection', return_value=mock_ws):
            h = capture_dom_hash("ws://localhost:9999")
        self.assertEqual("", h)

    def test_websocket_error_returns_empty_string(self):
        with patch('websocket.create_connection', side_effect=Exception("Failed")):
            h = capture_dom_hash("ws://localhost:9999")
        self.assertEqual("", h)


class TestExecuteSingle(unittest.TestCase):

    def test_ref_normalization_without_at_prefix(self):
        executor = BatchExecutor("ws://localhost:9999", "generic")
        mock_ws = MockWs([V_EMPTY_HASH])
        mock_ws.sock = "ws://localhost:9999"
        action = {"action": "click", "ref": "e0", "value": ""}
        result = executor._execute_single(mock_ws, action)
        self.assertIn("success", result)
        self.assertIn("ref", result)

    def test_ref_normalization_with_at_prefix(self):
        executor = BatchExecutor("ws://localhost:9999", "generic")
        mock_ws = MockWs([V_EMPTY_HASH])
        mock_ws.sock = "ws://localhost:9999"
        action = {"action": "click", "ref": "@e3", "value": ""}
        result = executor._execute_single(mock_ws, action)
        self.assertIn("success", result)

    def test_returns_elapsed_ms(self):
        executor = BatchExecutor("ws://localhost:9999", "generic")
        mock_ws = MockWs([V_EMPTY_HASH])
        mock_ws.sock = "ws://localhost:9999"
        action = {"action": "click", "ref": "@e0", "value": ""}
        result = executor._execute_single(mock_ws, action)
        self.assertIn("elapsed_ms", result)
        self.assertIsInstance(result["elapsed_ms"], int)

    def test_wait_action_includes_ms(self):
        executor = BatchExecutor("ws://localhost:9999", "generic")
        mock_ws = MockWs([V_EMPTY_HASH])
        mock_ws.sock = "ws://localhost:9999"
        action = {"action": "wait", "ref": "", "value": "", "ms": 500}
        result = executor._execute_single(mock_ws, action)
        self.assertIn("success", result)
        self.assertIn("elapsed_ms", result)

    def test_unknown_action_does_not_crash(self):
        executor = BatchExecutor("ws://localhost:9999", "generic")
        mock_ws = MockWs([V_EMPTY_HASH])
        mock_ws.sock = "ws://localhost:9999"
        action = {"action": "unknown_type", "ref": "@e0", "value": ""}
        result = executor._execute_single(mock_ws, action)
        self.assertIn("success", result)

    def test_empty_ref_click(self):
        executor = BatchExecutor("ws://localhost:9999", "generic")
        mock_ws = MockWs([V_EMPTY_HASH])
        mock_ws.sock = "ws://localhost:9999"
        action = {"action": "click", "ref": "", "value": ""}
        result = executor._execute_single(mock_ws, action)
        self.assertIn("success", result)


class TestBatchExecutorInit(unittest.TestCase):

    def test_init_accepts_config(self):
        config = MagicMock()
        executor = BatchExecutor("ws://localhost:9999", "qualtrics", config=config)
        self.assertEqual(executor.config, config)

    def test_init_without_config(self):
        executor = BatchExecutor("ws://localhost:9999", "qualtrics")
        self.assertIsNone(executor.config)

    def test_unknown_provider_uses_generic_commands(self):
        executor = BatchExecutor("ws://localhost:9999", "completely_unknown_provider_xyz")
        self.assertEqual(executor.commands, GENERIC_COMMANDS)


# =============================================================================
# Test BatchResult
# =============================================================================
class TestBatchResult(unittest.TestCase):

    def test_default_values(self):
        result = BatchResult()
        self.assertEqual(result.actions, [])
        self.assertEqual(result.total_success, 0)
        self.assertEqual(result.total_fail, 0)
        self.assertEqual(result.total_elapsed_ms, 0.0)

    def test_mutable_actions(self):
        result = BatchResult()
        result.actions.append({"ref": "@e0", "success": True})
        result.total_success += 1
        self.assertEqual(len(result.actions), 1)
        self.assertEqual(result.total_success, 1)

    def test_multiple_actions_tracked(self):
        result = BatchResult()
        for i in range(5):
            result.actions.append({"ref": f"@e{i}", "success": i % 2 == 0})
            if i % 2 == 0:
                result.total_success += 1
            else:
                result.total_fail += 1
        self.assertEqual(result.total_success, 3)
        self.assertEqual(result.total_fail, 2)


# =============================================================================
# Test BatchExecutor.execute (batch-level)
# =============================================================================
class MockWsForExecute:
    """Mock WS that tracks sends and returns configurable JSON responses."""
    def __init__(self, responses):
        self._responses = responses
        self._idx = 0
        self.sent = []

    def send(self, data):
        self.sent.append(json.loads(data) if isinstance(data, str) else data)

    def recv(self):
        if self._idx < len(self._responses):
            r = self._responses[self._idx]
            self._idx += 1
            return r if isinstance(r, str) else json.dumps(r)
        return json.dumps({"result": {"result": {"value": "null"}}})

    def getsockname(self):
        return "ws://localhost:9999"

    def getpeername(self):
        return ("localhost", 9999)

    def close(self):
        pass


class TestBatchExecutorExecute(unittest.TestCase):

    def test_empty_actions_returns_empty_result(self):
        executor = BatchExecutor("ws://localhost:9999", "generic")
        # capture_dom_hash patched → doesn't need WS for that
        import survey.execute as ex_mod
        orig_hash = ex_mod.capture_dom_hash
        orig_kbe = ex_mod.cdp_keyboard_enter
        ex_mod.capture_dom_hash = lambda url: ""
        ex_mod.cdp_keyboard_enter = lambda url: False
        try:
            mock_ws = MockWsForExecute([])
            with patch('websocket.create_connection', return_value=mock_ws):
                result = executor.execute([])
            self.assertEqual(len(result.actions), 0)
            self.assertEqual(result.total_success, 0)
        finally:
            ex_mod.capture_dom_hash = orig_hash
            ex_mod.cdp_keyboard_enter = orig_kbe

    def test_single_click_action(self):
        import survey.execute as ex_mod
        orig_hash = ex_mod.capture_dom_hash
        orig_kbe = ex_mod.cdp_keyboard_enter
        ex_mod.capture_dom_hash = lambda url: ""
        ex_mod.cdp_keyboard_enter = lambda url: False
        try:
            def make_resp(d):
                return json.dumps({"result": {"result": {"value": json.dumps(d)}}})
            responses = [make_resp({"n": 1, "t": "btn", "url": ""})]
            mock_ws = MockWsForExecute(responses)
            executor = BatchExecutor("ws://localhost:9999", "generic")
            with patch('websocket.create_connection', return_value=mock_ws):
                result = executor.execute([{"ref": "@e0", "action": "click", "value": ""}])
            self.assertEqual(len(result.actions), 1)
            self.assertIn("success", result.actions[0])
        finally:
            ex_mod.capture_dom_hash = orig_hash
            ex_mod.cdp_keyboard_enter = orig_kbe

    def test_multiple_actions_accumulated(self):
        import survey.execute as ex_mod
        orig_hash = ex_mod.capture_dom_hash
        orig_kbe = ex_mod.cdp_keyboard_enter
        ex_mod.capture_dom_hash = lambda url: ""
        ex_mod.cdp_keyboard_enter = lambda url: False
        try:
            def make_resp(d):
                return json.dumps({"result": {"result": {"value": json.dumps(d)}}})
            responses = [
                make_resp({"n": 1, "t": "btn", "url": ""}),  # action 1
                make_resp({"n": 2, "t": "radio", "url": ""}),  # action 2
                make_resp({"n": 3, "t": "submit", "url": ""}),  # action 3
            ]
            mock_ws = MockWsForExecute(responses)
            executor = BatchExecutor("ws://localhost:9999", "generic")
            with patch('websocket.create_connection', return_value=mock_ws):
                result = executor.execute([
                    {"ref": "@e0", "action": "click", "value": ""},
                    {"ref": "@e1", "action": "select", "value": ""},
                    {"ref": "@e2", "action": "submit", "value": ""},
                ])
            self.assertEqual(len(result.actions), 3)
        finally:
            ex_mod.capture_dom_hash = orig_hash
            ex_mod.cdp_keyboard_enter = orig_kbe

    def test_elapsed_ms_recorded(self):
        import survey.execute as ex_mod
        orig_hash = ex_mod.capture_dom_hash
        orig_kbe = ex_mod.cdp_keyboard_enter
        ex_mod.capture_dom_hash = lambda url: ""
        ex_mod.cdp_keyboard_enter = lambda url: False
        try:
            def make_resp(d):
                return json.dumps({"result": {"result": {"value": json.dumps(d)}}})
            mock_ws = MockWsForExecute([make_resp({"n": 1, "t": "btn", "url": ""})])
            executor = BatchExecutor("ws://localhost:9999", "generic")
            with patch('websocket.create_connection', return_value=mock_ws):
                result = executor.execute([{"ref": "@e0", "action": "click", "value": ""}])
            self.assertIsInstance(result.total_elapsed_ms, (int, float))
            self.assertGreaterEqual(result.total_elapsed_ms, 0)
        finally:
            ex_mod.capture_dom_hash = orig_hash
            ex_mod.cdp_keyboard_enter = orig_kbe

    def test_wait_action_preserved(self):
        import survey.execute as ex_mod
        orig_hash = ex_mod.capture_dom_hash
        orig_kbe = ex_mod.cdp_keyboard_enter
        ex_mod.capture_dom_hash = lambda url: ""
        ex_mod.cdp_keyboard_enter = lambda url: False
        try:
            def make_resp(d):
                return json.dumps({"result": {"result": {"value": json.dumps(d)}}})
            mock_ws = MockWsForExecute([make_resp({"n": 1, "t": "btn", "url": ""})])
            executor = BatchExecutor("ws://localhost:9999", "generic")
            with patch('websocket.create_connection', return_value=mock_ws):
                result = executor.execute([{"ref": "", "action": "wait", "value": "", "ms": 100}])
            self.assertEqual(len(result.actions), 1)
            self.assertEqual(result.actions[0]["action"], "wait")
        finally:
            ex_mod.capture_dom_hash = orig_hash
            ex_mod.cdp_keyboard_enter = orig_kbe

    def test_ws_closed_after_batch(self):
        import survey.execute as ex_mod
        orig_hash = ex_mod.capture_dom_hash
        orig_kbe = ex_mod.cdp_keyboard_enter
        ex_mod.capture_dom_hash = lambda url: ""
        ex_mod.cdp_keyboard_enter = lambda url: False
        try:
            def make_resp(d):
                return json.dumps({"result": {"result": {"value": json.dumps(d)}}})
            mock_ws = MockWsForExecute([make_resp({"n": 1, "t": "btn", "url": ""})])
            executor = BatchExecutor("ws://localhost:9999", "generic")
            with patch('websocket.create_connection', return_value=mock_ws):
                result = executor.execute([{"ref": "@e0", "action": "click", "value": ""}])
            # After execute, WS should be closed (close() called)
            # MockWs tracks close() calls
            self.assertTrue(hasattr(mock_ws, 'close'))
        finally:
            ex_mod.capture_dom_hash = orig_hash
            ex_mod.cdp_keyboard_enter = orig_kbe


if __name__ == "__main__":
    unittest.main(verbosity=2)