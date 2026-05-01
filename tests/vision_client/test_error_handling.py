"""Tests für Vision-Client Error Handling."""
import pytest
from unittest.mock import patch, MagicMock
from requests.exceptions import Timeout, RequestException
from runner.vision_client import VisionClient


def test_circuit_breaker_activation():
    client = VisionClient()
    client.circuit_breaker_threshold = 2

    with patch.object(client, "_nvidia_vision_call", side_effect=Exception("Test")):
        # 2 Fehler → Circuit Breaker aktiv
        with pytest.raises(Exception):
            client.analyze_screenshot("test.png", 1)
        with pytest.raises(Exception):
            client.analyze_screenshot("test.png", 1)

        # 3. Fehler → Circuit Breaker blockiert
        with pytest.raises(Exception) as exc_info:
            client.analyze_screenshot("test.png", 1)
        assert "Circuit Breaker aktiv" in str(exc_info.value)


def test_retry_logic():
    # Reset Circuit Breaker für Test
    from runner.vision_client.core import CIRCUIT_BROKEN, FAILURE_COUNT, LAST_FAILURE_TIME
    CIRCUIT_BROKEN = False
    FAILURE_COUNT = 0
    LAST_FAILURE_TIME = 0  # Zeitstempel auf 0 setzen, um sofortige Ausführung zu erlauben

    client = VisionClient()
    call_count = 0

    def mock_call(prompt, image):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise Timeout("Mock timeout")
        return {"action": "click", "element_id": 1}

    with patch.object(client, "_nvidia_vision_call", side_effect=mock_call):
        result = client.analyze_screenshot("test.png", 1)
        assert call_count == 3
        assert result["action"] == "click"


def test_handle_vision_error():
    client = VisionClient()
    state = {"eur": 5.0}
    error = Exception("Test Error")

    result = client.handle_vision_error(error, state)
    assert result["action"] == "wait"
    assert result["duration_seconds"] == 3600
    assert result["eur"] == 5.0
    assert "Vision-LLM failed" in result["reason"]
