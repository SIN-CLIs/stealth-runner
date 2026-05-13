"""Test suite for drag_drop_solver (SR-68, 2026-05-11).

Deckt ab:
  - Puzzle detection (drag_count=0 → skip, drag_count>0 → process)
  - Target number extraction (Zahl X from DOM)
  - Position computation (source/target coords)
  - Mock CDP dispatch (keine echten Events)
  - Retry logic (position fails → error)
"""

import unittest
from unittest.mock import patch
import sys
from pathlib import Path

# Add survey-cli to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from survey.captcha.drag_drop_solver import (
    solve_puzzle
)


class TestDragDropSolver(unittest.TestCase):
    """Main test cases."""

    def test_puzzle_skipped_when_no_cdk_drag(self):
        """Test: status='skipped' wenn .cdk-drag nicht im DOM."""
        with patch('survey.captcha.drag_drop_solver._detect_puzzle_dom') as mock_detect:
            mock_detect.return_value = {"drag_count": 0, "drop_zone_exists": False}
            result = solve_puzzle("ws://fake/page/123")
            self.assertEqual(result["status"], "skipped")
            self.assertEqual(result["reason"], "no_puzzle")

    def test_error_when_number_not_found(self):
        """Test: status='error' wenn Zahl nicht extrahiert."""
        with patch('survey.captcha.drag_drop_solver._detect_puzzle_dom') as mock_detect:
            with patch('survey.captcha.drag_drop_solver._extract_target_number') as mock_extract:
                mock_detect.return_value = {"drag_count": 2, "drop_zone_exists": True}
                mock_extract.return_value = None
                result = solve_puzzle("ws://fake/page/123")
                self.assertEqual(result["status"], "error")
                self.assertEqual(result["reason"], "no_number")

    def test_error_when_positions_not_computed(self):
        """Test: status='error' wenn source/target nicht berechnet."""
        with patch('survey.captcha.drag_drop_solver._detect_puzzle_dom') as mock_detect:
            with patch('survey.captcha.drag_drop_solver._extract_target_number') as mock_extract:
                with patch('survey.captcha.drag_drop_solver._compute_bezier_path') as mock_path:
                    mock_detect.return_value = {"drag_count": 2}
                    mock_extract.return_value = "28"
                    mock_path.return_value = None
                    result = solve_puzzle("ws://fake/page/123")
                    self.assertEqual(result["status"], "error")
                    self.assertEqual(result["reason"], "no_positions")

    def test_success_when_puzzle_solved(self):
        """Test: status='ok' + button_clicked=True."""
        with patch('survey.captcha.drag_drop_solver._detect_puzzle_dom') as mock_detect:
            with patch('survey.captcha.drag_drop_solver._extract_target_number') as mock_extract:
                with patch('survey.captcha.drag_drop_solver._compute_bezier_path') as mock_path:
                    with patch('survey.captcha.drag_drop_solver._execute_drag_sequence') as mock_drag:
                        with patch('survey.captcha.drag_drop_solver._click_next_button') as mock_click:
                            mock_detect.return_value = {"drag_count": 2}
                            mock_extract.return_value = "28"
                            mock_path.return_value = {
                                "source_x": 100, "source_y": 100,
                                "target_x": 200, "target_y": 150
                            }
                            mock_drag.return_value = True
                            mock_click.return_value = True

                            result = solve_puzzle("ws://fake/page/123")
                            self.assertEqual(result["status"], "ok")
                            self.assertEqual(result["number"], "28")
                            self.assertTrue(result["button_clicked"])
                            self.assertEqual(result["source"], (100.0, 100.0))
                            self.assertEqual(result["target"], (200.0, 150.0))

    def test_ok_but_button_not_clicked(self):
        """Test: status='ok' aber button_clicked=False."""
        with patch('survey.captcha.drag_drop_solver._detect_puzzle_dom') as mock_detect:
            with patch('survey.captcha.drag_drop_solver._extract_target_number') as mock_extract:
                with patch('survey.captcha.drag_drop_solver._compute_bezier_path') as mock_path:
                    with patch('survey.captcha.drag_drop_solver._execute_drag_sequence') as mock_drag:
                        with patch('survey.captcha.drag_drop_solver._click_next_button') as mock_click:
                            mock_detect.return_value = {"drag_count": 1}
                            mock_extract.return_value = "15"
                            mock_path.return_value = {
                                "source_x": 50, "source_y": 50,
                                "target_x": 150, "target_y": 100
                            }
                            mock_drag.return_value = True
                            mock_click.return_value = False

                            result = solve_puzzle("ws://fake/page/123")
                            self.assertEqual(result["status"], "ok")
                            self.assertFalse(result["button_clicked"])

    def test_error_when_drag_execution_fails(self):
        """Test: status='error' wenn Mausbewegung fehlschlägt."""
        with patch('survey.captcha.drag_drop_solver._detect_puzzle_dom') as mock_detect:
            with patch('survey.captcha.drag_drop_solver._extract_target_number') as mock_extract:
                with patch('survey.captcha.drag_drop_solver._compute_bezier_path') as mock_path:
                    with patch('survey.captcha.drag_drop_solver._execute_drag_sequence') as mock_drag:
                        mock_detect.return_value = {"drag_count": 2}
                        mock_extract.return_value = "28"
                        mock_path.return_value = {
                            "source_x": 100, "source_y": 100,
                            "target_x": 200, "target_y": 150
                        }
                        mock_drag.return_value = False

                        result = solve_puzzle("ws://fake/page/123")
                        self.assertEqual(result["status"], "error")
                        self.assertEqual(result["reason"], "drag_execution_failed")

    def test_number_provided_directly(self):
        """Test: Mit number-Parameter (kein Auto-Detect)."""
        with patch('survey.captcha.drag_drop_solver._detect_puzzle_dom') as mock_detect:
            with patch('survey.captcha.drag_drop_solver._compute_bezier_path') as mock_path:
                with patch('survey.captcha.drag_drop_solver._execute_drag_sequence') as mock_drag:
                    with patch('survey.captcha.drag_drop_solver._click_next_button') as mock_click:
                        mock_detect.return_value = {"drag_count": 1}
                        mock_path.return_value = {
                            "source_x": 100, "source_y": 100,
                            "target_x": 200, "target_y": 150
                        }
                        mock_drag.return_value = True
                        mock_click.return_value = True

                        result = solve_puzzle("ws://fake/page/123", number="42")
                        self.assertEqual(result["status"], "ok")
                        self.assertEqual(result["number"], "42")


if __name__ == "__main__":
    unittest.main()
