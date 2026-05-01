import pytest
from unittest.mock import patch, MagicMock
from runner.drivers.skylight import SkylightDriver


def test_revalidation_after_type():
    driver = SkylightDriver(pid=91214)
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            stdout='{"status": "ok", "element": {"label": "E-Mail", "role": "AXTextField"}}',
            stderr="",
        )
        driver.type_text(element_index=38, text="test@test.com", post_delay=2000)

        mock_run.return_value = MagicMock(
            stdout='{"status": "ok", "file": "/tmp/after.png"}',
            stderr="",
        )
        screenshot = driver.screenshot(output="/tmp/after.png")
        assert screenshot["status"] == "ok"

        mock_run.return_value = MagicMock(
            stdout='{"status": "ok", "element": {"label": "Weiter", "role": "AXButton", "index": 41}}',
            stderr="",
        )
        weiter_element = driver.inspect(element_index=41)
        assert weiter_element["element"]["label"] == "Weiter"
        assert weiter_element["element"]["index"] == 41