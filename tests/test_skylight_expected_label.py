import pytest
from unittest.mock import patch, MagicMock
from runner.drivers.skylight import SkylightDriver


def test_click_with_expected_label_success():
    driver = SkylightDriver(pid=91214)
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            stdout='{"status": "ok", "element": {"label": "Weiter", "role": "AXButton"}}',
            stderr="",
        )
        result = driver.click(
            element_index=39,
            expected_label="Weiter",
            expected_role="AXButton",
        )
        assert result["status"] == "ok"
        assert "Weiter" in result["element"]["label"]


def test_click_with_expected_label_mismatch():
    driver = SkylightDriver(pid=91214)
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            stdout='{"status": "error", "message": "expected_label_mismatch"}',
            stderr="",
        )
        result = driver.click(
                element_index=39,
                expected_label="Weiter",
                expected_role="AXButton",
            )
        assert result["status"] == "error"
        assert "expected_label_mismatch" in result.get("message", "")