import pytest
from unittest.mock import patch, MagicMock
from runner.drivers.skylight import SkylightDriver


def test_click_with_axpath():
    driver = SkylightDriver(pid=91214)
    axpath = "//AXButton[@label='Weiter']"
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            stdout='{"status": "ok", "element": {"label": "Weiter", "role": "AXButton"}}',
            stderr="",
        )
        result = driver.click(axpath=axpath)
        assert result["status"] == "ok"
        assert "//AXButton[@label='Weiter']" in mock_run.call_args[0][0]