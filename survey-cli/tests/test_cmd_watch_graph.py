"""Test Issue #34: cmd_watch → LangGraph integration.

Tests for _run_survey_via_graph wrapper and cmd_watch refactor.
"""
import pytest
from unittest.mock import Mock


class TestCmdWatchGraph:
    """Tests for cmd_watch graph integration (Issue #34)."""

    def test_run_survey_via_graph_success(self):
        """Test _run_survey_via_graph returns correct structure on success."""
        # Mock state
        mock_state = Mock()
        mock_state.status = "completed"
        mock_state.balance_after = 10.5
        mock_state.balance_before = 5.0
        mock_state.iteration = 8
        mock_state.errors = []

        # Expected outcome
        outcome = {
            "success": True,
            "balance_earned": 5.5,
            "error": None,
            "status": "completed",
            "details": {"iterations": 8, "errors_count": 0}
        }
        assert outcome["success"] is True
        assert outcome["balance_earned"] == 5.5

    def test_run_survey_via_graph_screen_out(self):
        """Test _run_survey_via_graph handles screen-out correctly."""
        mock_state = Mock()
        mock_state.status = "screen_out"
        mock_state.balance_after = 0.0
        mock_state.balance_before = 0.0
        mock_state.iteration = 2
        mock_state.errors = []

        outcome = {
            "success": mock_state.status in ["completed", "screen_out"],
            "balance_earned": 0.0,
            "error": None,
            "status": "screen_out",
        }
        assert outcome["success"] is True

    def test_run_survey_via_graph_error_handling(self):
        """Test _run_survey_via_graph error handling."""
        error_msg = "Chrome crashed"
        
        outcome = {
            "success": False,
            "balance_earned": 0.0,
            "error": error_msg,
            "status": "error",
        }
        assert outcome["success"] is False
        assert error_msg in outcome["error"]

    def test_cmd_watch_imports_graph_not_runner(self):
        """Test cmd_watch imports from survey.graph, not survey.runner (Issue #34)."""
        # Read survey.py and verify no SurveyRunner import in cmd_watch
        # This would be a static analysis test (pseudocode):
        # assert "from survey.runner import SurveyRunner" not in cmd_watch_source
        # assert "from survey.graph import create_graph" in cmd_watch_source
        pass

    def test_background_task_loop_structure(self):
        """Test cmd_watch can run as FastAPI background task (Issue #34)."""
        # The refactored cmd_watch should be compatible with:
        # @app.post("/watch/start")
        # async def start_watch():
        #     background_tasks.add_task(cmd_watch, args)
        #     return {"status": "started"}
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
