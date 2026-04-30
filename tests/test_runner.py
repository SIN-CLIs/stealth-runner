"""Tests für die Kernmodule des stealth-runner."""
from __future__ import annotations
import json, os
from unittest.mock import patch
import pytest
from runner.stealth_executor import StealthExecutor, StealthError
from runner.vision_client import VisionClient
from runner.audit_log import AuditLog
from runner.human_profile import HumanProfile

class TestStealthExecutor:
    def test_init(self) -> None:
        e = StealthExecutor()
        assert e.pid is None
        assert e.backend == "skylight-cli"

    def test_init_rejects_missing_skylight(self) -> None:
        with patch("shutil.which", return_value=None):
            with pytest.raises(RuntimeError, match="skylight-cli"):
                StealthExecutor()

    def test_pid_settable(self) -> None:
        e = StealthExecutor(); e.pid = 54971
        assert e.pid == 54971

    def test_click_requires_element_or_coords(self) -> None:
        e = StealthExecutor(); e.pid = 99999
        result = e.click()
        assert result["status"] == "error"

    def test_type_text_builds_correct_command(self) -> None:
        e = StealthExecutor(); e.pid = 99999
        with patch.object(e, "_run", return_value={"status": "ok"}) as mock_run:
            e.type_text("Hello", element_index=5, clear_first=True)
            cmd = mock_run.call_args[0][0]
            assert "Hello" in cmd and "--element-index" in cmd and "--clear-first" in cmd

class TestVisionClient:
    @patch.dict(os.environ, {"CF_TOKEN": "test-token"}, clear=True)
    def test_init_with_cf_token(self) -> None:
        assert VisionClient() is not None

    @patch.dict(os.environ, {"NVIDIA_API_KEY": "test-key"}, clear=True)
    def test_init_with_nvidia_key(self) -> None:
        assert VisionClient() is not None

    def test_init_without_any_token_raises(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(EnvironmentError):
                VisionClient()

    def test_parse_json_plain(self) -> None:
        result = VisionClient()._parse_json('{"action":"click","element_id":7}')
        assert result["action"] == "click" and result["element_id"] == 7

    def test_parse_json_codeblock(self) -> None:
        result = VisionClient()._parse_json('```json\n{"action":"type","text":"hello"}\n```')
        assert result["action"] == "type"

    def test_parse_json_hard_fallback(self) -> None:
        result = VisionClient()._parse_json("Completely invalid")
        assert result["action"] == "click" and result["element_id"] == 0

class TestAuditLog:
    def test_log_and_summary(self, tmp_path) -> None:
        log_file = tmp_path / "test.jsonl"
        log = AuditLog(log_file)
        log.log("test_event", key="value"); log.flush()
        assert log.get_summary()["total_events"] == 1
        log.close()

    def test_multiple_events(self, tmp_path) -> None:
        log = AuditLog(tmp_path / "m.jsonl")
        for i in range(15): log.log("e", i=i)
        log.flush(); assert log.get_summary()["total_events"] == 15; log.close()

class TestHumanProfile:
    def test_random_generates_valid_profile(self) -> None:
        p = HumanProfile.random()
        assert 2.0 <= p.min_delay <= 4.0 and 5.0 <= p.max_delay <= 9.0

    @pytest.mark.anyio
    async def test_click_delay_is_async(self) -> None:
        await HumanProfile.random().click_delay()
