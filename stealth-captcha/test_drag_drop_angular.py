#!/usr/bin/env python3
"""
Test script for Angular CDK drag-drop puzzle solver.

Usage:
  # Self-test (verify imports, structure, simulate with mocks):
  python3 test_drag_drop_angular.py --self-test

  # Live test against running Chrome (needs purespectrum survey at 66%):
  python3 test_drag_drop_angular.py --live --ws-url ws://127.0.0.1:9999/devtools/page/XXX

  # Auto-discover purespectrum tab and test:
  python3 test_drag_drop_angular.py --live --auto-discover
"""

import argparse
import json
import sys
import time
import unittest
from unittest.mock import MagicMock, patch

# Add paths — import solver module DIRECTLY to bypass broken package __init__.py
sys.path.insert(0, '/Users/jeremy/dev/stealth-runner/stealth-captcha/src')
sys.path.insert(0, '/Users/jeremy/dev/stealth-runner/stealth-captcha/src/stealth_captcha/solver')


class TestDragDropAngularSelf(unittest.TestCase):
    """Self-tests that don't require live Chrome or survey."""

    def test_import(self):
        """Verify solver module imports correctly."""
        import drag_drop_angular
        self.assertTrue(callable(drag_drop_angular.solve_drag_puzzle_new))

    def test_drag_drop_result_dataclass(self):
        """Verify DragDropResult dataclass works."""
        from drag_drop_angular import DragDropResult
        
        r = DragDropResult(status="solved", number="42", details={"method": "test"})
        self.assertEqual(r.status, "solved")
        self.assertEqual(r.number, "42")
        self.assertEqual(r.details["method"], "test")
        self.assertIsNone(r.error)

    def test_extract_number_with_mock(self):
        """Test _extract_number with mocked websocket."""
        from drag_drop_angular import _extract_number
        
        with patch('websocket.create_connection') as mock_ws:
            mock_conn = MagicMock()
            mock_ws.return_value = mock_conn
            
            # Simulate CDP response with number 20
            mock_conn.recv.return_value = json.dumps({
                "result": {
                    "result": {"value": "20"}
                }
            })
            
            result = _extract_number("ws://fake")
            self.assertEqual(result, "20")
            
            # Verify the CDP call
            call_args = mock_conn.send.call_args[0][0]
            call_json = json.loads(call_args)
            self.assertEqual(call_json["method"], "Runtime.evaluate")
            self.assertIn("Bitte legen", call_json["params"]["expression"])

    def test_get_page_info_with_mock(self):
        """Test _get_page_info with mocked websocket."""
        from drag_drop_angular import _get_page_info
        
        with patch('websocket.create_connection') as mock_ws:
            mock_conn = MagicMock()
            mock_ws.return_value = mock_conn
            
            mock_conn.recv.return_value = json.dumps({
                "result": {
                    "result": {"value": json.dumps({
                        "dropZoneCount": 2,
                        "dragCount": 3,
                        "numbers": ["06", "10", "52"],
                        "buttonText": "Nächste",
                        "buttonDisabled": True,
                        "targetZoneFound": True,
                        "targetHasImg": False
                    })}
                }
            })
            
            result = _get_page_info("ws://fake")
            self.assertEqual(result["dropZoneCount"], 2)
            self.assertEqual(result["dragCount"], 3)
            self.assertIn("52", result["numbers"])
            self.assertFalse(result["targetHasImg"])

    def test_verify_solution_with_mock(self):
        """Test _verify_solution with mocked websocket."""
        from drag_drop_angular import _verify_solution
        
        with patch('websocket.create_connection') as mock_ws:
            mock_conn = MagicMock()
            mock_ws.return_value = mock_conn
            
            mock_conn.recv.return_value = json.dumps({
                "result": {
                    "result": {"value": json.dumps({
                        "dropzoneHasImg": True,
                        "imgAlt": "52",
                        "buttonDisabled": False,
                        "buttonVisible": True,
                        "buttonText": "Nächste"
                    })}
                }
            })
            
            result = _verify_solution("ws://fake")
            self.assertTrue(result["dropzoneHasImg"])
            self.assertEqual(result["imgAlt"], "52")
            self.assertFalse(result["buttonDisabled"])

    def test_code_structure_approach_a(self):
        """Verify Approach A code contains Playwright mouse API."""
        import inspect
        from drag_drop_angular import _try_approach_a_playwright_mouse
        
        source = inspect.getsource(_try_approach_a_playwright_mouse)
        self.assertIn("mouse.move", source)
        self.assertIn("mouse.down", source)
        self.assertIn("mouse.up", source)
        self.assertIn("10 intermediate points", source.lower())
        self.assertIn("arc_offset", source)

    def test_code_structure_approach_b(self):
        """Verify Approach B code contains CDP dispatchMouseEvent."""
        import inspect
        from drag_drop_angular import _try_approach_b_cdp_mouse
        
        source = inspect.getsource(_try_approach_b_cdp_mouse)
        self.assertIn("Input.dispatchMouseEvent", source)
        self.assertIn("mousePressed", source)
        self.assertIn("mouseMoved", source)
        self.assertIn("mouseReleased", source)

    def test_code_structure_approach_c(self):
        """Verify Approach C code contains PointerEvent with realistic properties."""
        import inspect
        from drag_drop_angular import _try_approach_c_synthetic_pointer_with_delays
        
        source = inspect.getsource(_try_approach_c_synthetic_pointer_with_delays)
        self.assertIn("PointerEvent", source)
        self.assertIn("pointerType", source)
        self.assertIn("pressure", source)
        self.assertIn("buttons: 1", source)
        self.assertIn("10 intermediate", source.lower())

    def test_code_structure_approach_d(self):
        """Verify Approach D code contains HTML5 drag and DOM manipulation."""
        import inspect
        from drag_drop_angular import _try_approach_d_html5_drag_and_dom
        
        source = inspect.getsource(_try_approach_d_html5_drag_and_dom)
        self.assertIn("DragEvent", source)
        self.assertIn("dragstart", source)
        self.assertIn("dropZone.appendChild", source)
        self.assertIn("btn.disabled = false", source)

    def test_debug_logging_enabled(self):
        """Verify DEBUG flag is set for verbose logging."""
        from drag_drop_angular import DEBUG
        self.assertTrue(DEBUG, "DEBUG should be True for E2E troubleshooting")


def run_live_test(ws_url: str):
    """Run a live test against a real purespectrum survey tab.
    
    This requires:
    - Chrome running on port 9999 with purespectrum survey at 66% drag-drop puzzle
    - websocket-client and playwright installed
    """
    print("=" * 70)
    print("LIVE E2E TEST: Angular CDK Drag-Drop Puzzle Solver")
    print("=" * 70)
    print(f"Target WebSocket: {ws_url}")
    print()
    
    from drag_drop_angular import solve_drag_puzzle_new, DEBUG
    
    if not DEBUG:
        print("WARNING: DEBUG is False — set DEBUG=True in drag_drop_angular.py for verbose output")
    
    print("Starting solver...")
    print("-" * 70)
    
    start_time = time.time()
    result = solve_drag_puzzle_new(ws_url)
    elapsed = time.time() - start_time
    
    print()
    print("=" * 70)
    print("RESULT")
    print("=" * 70)
    print(f"Status:        {result.status}")
    print(f"Number:        {result.number}")
    print(f"Error:         {result.error}")
    print(f"Details:       {json.dumps(result.details, indent=2, default=str)}")
    print(f"Elapsed:       {elapsed:.2f}s")
    print()
    
    print("DEBUG LOG:")
    print("-" * 70)
    for i, log in enumerate(result.debug_log, 1):
        print(f"  {i:3d}. {log}")
    
    print()
    if result.status == "solved":
        print("✅ SUCCESS: Puzzle solved!")
        return 0
    elif result.status == "blocked":
        print("⚠️  BLOCKED: All approaches failed — Angular CDK is blocking automation")
        return 1
    else:
        print(f"❌ FAILED: {result.error}")
        return 2


def auto_discover_purespectrum_tab():
    """Auto-discover the purespectrum survey tab from Chrome on port 9999."""
    import urllib.request
    import json
    
    try:
        req = urllib.request.urlopen('http://127.0.0.1:9999/json/list', timeout=5)
        pages = json.loads(req.read())
        
        for page in pages:
            url = page.get('url', '')
            if 'purespectrum' in url and 'survey_id' in url:
                ws_url = page.get('webSocketDebuggerUrl')
                print(f"Found purespectrum tab: {url}")
                print(f"WebSocket URL: {ws_url}")
                return ws_url
        
        print("No purespectrum tab found. Available tabs:")
        for page in pages:
            print(f"  - {page.get('type', '?')}: {page.get('url', '?')[:80]}")
        return None
        
    except Exception as e:
        print(f"Failed to connect to Chrome: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Test Angular CDK drag-drop puzzle solver")
    parser.add_argument("--self-test", action="store_true", help="Run self-tests without live Chrome")
    parser.add_argument("--live", action="store_true", help="Run live test against Chrome")
    parser.add_argument("--ws-url", type=str, help="CDP WebSocket URL for purespectrum tab")
    parser.add_argument("--auto-discover", action="store_true", help="Auto-discover purespectrum tab")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose unittest output")
    
    args = parser.parse_args()
    
    if args.self_test or (not args.live and not args.ws_url and not args.auto_discover):
        print("Running self-tests (no live Chrome required)...")
        print()
        
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromTestCase(TestDragDropAngularSelf)
        
        runner = unittest.TextTestRunner(verbosity=2 if args.verbose else 1)
        result = runner.run(suite)
        
        if result.wasSuccessful():
            print()
            print("✅ All self-tests passed!")
            print()
            print("To run a live test:")
            print("  1. Start Chrome with purespectrum survey at 66% drag-drop puzzle")
            print("  2. Run: python3 test_drag_drop_angular.py --live --auto-discover")
            print("  3. Or specify ws-url: python3 test_drag_drop_angular.py --live --ws-url ws://...")
            return 0
        else:
            print()
            print("❌ Some tests failed!")
            return 1
    
    if args.live or args.ws_url or args.auto_discover:
        ws_url = args.ws_url
        
        if args.auto_discover and not ws_url:
            print("Auto-discovering purespectrum tab...")
            ws_url = auto_discover_purespectrum_tab()
            if not ws_url:
                print()
                print("❌ Could not find purespectrum tab. Is Chrome running on port 9999?")
                return 1
            print()
        
        if not ws_url:
            print("Error: --live requires --ws-url or --auto-discover")
            return 1
        
        return run_live_test(ws_url)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
