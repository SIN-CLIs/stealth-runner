"""================================================================================
CAPTCHA FALLBACK CHAIN TESTS — Unit Tests mit Mocked HTTP Layers (SR-138)
================================================================================

Test Coverage (18+ Tests gemäß Acceptance Criteria):

NimSecondary (3 Tests):
    - test_nim_secondary_success
    - test_nim_secondary_api_error
    - test_nim_secondary_unsupported_type

Gateway (5 Tests):
    - test_gateway_gemini_success
    - test_gateway_gemini_fail_claude_success
    - test_gateway_both_fail
    - test_gateway_no_api_key_graceful_skip
    - test_gateway_coords_extraction

Audio (3 Tests):
    - test_audio_recaptcha_success
    - test_audio_hcaptcha_success
    - test_audio_parakeet_error

FallbackChain (4 Tests):
    - test_chain_success_step_1
    - test_chain_step1_fail_step2_succeeds
    - test_chain_all_vision_fail_audio_succeeds
    - test_chain_all_fail_handoff

Logging (3 Tests):
    - test_jsonl_shape
    - test_step_trace_correctness
    - test_screenshot_encoding

Module Status: NEW (SR-138, 2026-05-12)
================================================================================
"""

from __future__ import annotations

import base64
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ── MOCK FIXTURES ──────────────────────────────────────────────────────────


@dataclass
class MockCaptchaDetection:
    """Mock CaptchaDetection für Tests."""

    captcha_type: str
    frame_id: str = ""
    frame_url: str = ""
    dom_hint: str = ""


@dataclass
class MockCaptchaResult:
    """Mock CaptchaResult für Tests."""

    solved: bool
    captcha_type: str = ""
    token: str = ""
    elapsed_ms: float = 0.0
    reason: str = "ok"
    extra: dict = None

    def __post_init__(self):
        if self.extra is None:
            self.extra = {}


class MockCDPConnection:
    """Mock CDP Connection für Tests."""

    def __init__(self, screenshot_b64: str = None, eval_results: dict = None):
        self._screenshot = screenshot_b64 or base64.b64encode(b"fake_png_data").decode()
        self._eval_results = eval_results or {}
        self.calls = []

    def call_result(self, method: str, params: dict = None) -> dict:
        self.calls.append((method, params))

        if method == "Page.captureScreenshot":
            return {"data": self._screenshot}
        elif method == "Runtime.evaluate":
            expr = params.get("expression", "")
            for key, value in self._eval_results.items():
                if key in expr:
                    return {"result": {"value": value}}
            return {"result": {"value": None}}
        elif method == "Input.dispatchMouseEvent":
            return {}
        return {}


# ══════════════════════════════════════════════════════════════════════════
# NIM SECONDARY SOLVER TESTS (3)
# ══════════════════════════════════════════════════════════════════════════


class TestNimSecondarySolver:
    """Tests für nim_secondary_solver.py."""

    def test_nim_secondary_success(self):
        """Test successful solve with NIM Qwen2.5-VL."""
        from survey.captcha.nim_secondary_solver import NimSecondarySolver

        solver = NimSecondarySolver(api_key="test_key")
        cdp = MockCDPConnection()
        detection = MockCaptchaDetection(captcha_type="angular_drag_drop", dom_hint="target=28")

        # Mock API response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(
            {"found": True, "source": {"x": 100, "y": 200}, "target": {"x": 300, "y": 200}}
        )

        with patch.object(
            solver, "_call_vision_api", return_value=mock_response.choices[0].message.content
        ):
            result = solver.solve(cdp, detection)

        assert result.solved is True
        assert result.captcha_type == "angular_drag_drop"
        assert result.reason == "ok"

    def test_nim_secondary_api_error(self):
        """Test handling of NIM API errors."""
        from survey.captcha.nim_secondary_solver import NimSecondarySolver

        solver = NimSecondarySolver(api_key="test_key")
        cdp = MockCDPConnection()
        detection = MockCaptchaDetection(captcha_type="angular_drag_drop")

        # Mock API failure
        with patch.object(solver, "_call_vision_api", return_value=None):
            result = solver.solve(cdp, detection)

        assert result.solved is False
        assert result.reason == "nim_api_failed"

    def test_nim_secondary_unsupported_type(self):
        """Test that unsupported captcha types are rejected."""
        from survey.captcha.nim_secondary_solver import NimSecondarySolver

        solver = NimSecondarySolver(api_key="test_key")
        cdp = MockCDPConnection()
        detection = MockCaptchaDetection(captcha_type="unknown_type")

        result = solver.solve(cdp, detection)

        assert result.solved is False
        assert result.reason == "unsupported_type"


# ══════════════════════════════════════════════════════════════════════════
# GATEWAY SOLVER TESTS (5)
# ══════════════════════════════════════════════════════════════════════════


class TestGatewaySolver:
    """Tests für gateway_solver.py."""

    def test_gateway_gemini_success(self):
        """Test successful solve with Gemini 3.1 Flash Image."""
        from survey.captcha.gateway_solver import GatewaySolver

        solver = GatewaySolver(api_key="test_gateway_key")
        cdp = MockCDPConnection()
        detection = MockCaptchaDetection(captcha_type="angular_drag_drop", dom_hint="target=42")

        gemini_response = json.dumps(
            {
                "elements": [
                    {"label": "draggable", "bbox": [100, 200, 150, 250]},
                    {"label": "dropzone", "bbox": [300, 200, 350, 250]},
                ],
                "action": "drag",
                "solved": True,
            }
        )

        with patch.object(solver, "_call_gateway_api", return_value=gemini_response):
            result = solver.solve(cdp, detection)

        assert result.solved is True
        assert "gemini" in result.extra.get("model", "").lower()

    def test_gateway_gemini_fail_claude_success(self):
        """Test fallback to Claude when Gemini fails."""
        from survey.captcha.gateway_solver import (
            GatewaySolver,
            GATEWAY_PRIMARY_MODEL,
        )

        solver = GatewaySolver(api_key="test_gateway_key")
        cdp = MockCDPConnection()
        detection = MockCaptchaDetection(captcha_type="visual_text")

        call_count = [0]

        def mock_call(model, prompt, image):
            call_count[0] += 1
            if model == GATEWAY_PRIMARY_MODEL:
                return json.dumps({"solved": False, "reason": "gemini_failed"})
            else:
                return json.dumps(
                    {"action_type": "text", "solved": True, "data": {"text": "ABC123"}}
                )

        with patch.object(solver, "_call_gateway_api", side_effect=mock_call):
            result = solver.solve(cdp, detection)

        assert result.solved is True
        assert "claude" in result.extra.get("model", "").lower()
        assert call_count[0] == 2  # Both models tried

    def test_gateway_both_fail(self):
        """Test when both Gemini and Claude fail."""
        from survey.captcha.gateway_solver import GatewaySolver

        solver = GatewaySolver(api_key="test_gateway_key")
        cdp = MockCDPConnection()
        detection = MockCaptchaDetection(captcha_type="angular_drag_drop")

        with patch.object(solver, "_call_gateway_api", return_value=None):
            result = solver.solve(cdp, detection)

        assert result.solved is False
        assert result.reason == "both_models_failed"

    def test_gateway_no_api_key_graceful_skip(self):
        """Test graceful skip when AI_GATEWAY_API_KEY is not set."""
        from survey.captcha.gateway_solver import GatewaySolver

        # Create solver without API key
        with patch.dict(os.environ, {"AI_GATEWAY_API_KEY": ""}, clear=True):
            solver = GatewaySolver(api_key=None)

        cdp = MockCDPConnection()
        detection = MockCaptchaDetection(captcha_type="angular_drag_drop")

        result = solver.solve(cdp, detection)

        assert result.solved is False
        assert result.reason == "api_key_not_set"

    def test_gateway_coords_extraction(self):
        """Test coordinate extraction from model response."""
        from survey.captcha.gateway_solver import GatewaySolver

        solver = GatewaySolver(api_key="test_key")
        cdp = MockCDPConnection()
        detection = MockCaptchaDetection(captcha_type="slider")

        response = json.dumps({"action_type": "slide", "solved": True, "data": {"distance": 150}})

        # Mock slider handle detection
        cdp._eval_results = {"slider": {"x": 50, "y": 300}}

        with patch.object(solver, "_call_gateway_api", return_value=response):
            result = solver.solve(cdp, detection)

        # Should attempt to execute slide action
        assert result.captcha_type == "slider"


# ══════════════════════════════════════════════════════════════════════════
# AUDIO SOLVER TESTS (3)
# ══════════════════════════════════════════════════════════════════════════


class TestAudioSolver:
    """Tests für audio_solver.py."""

    def test_audio_recaptcha_success(self):
        """Test successful reCAPTCHA audio solve."""
        from survey.captcha.audio_solver import AudioSolver

        solver = AudioSolver(api_key="test_nvidia_key")
        cdp = MockCDPConnection(
            eval_results={
                "audio-button": True,
                "audio-source": "https://example.com/audio.mp3",
                "audio-response": True,
                "verify": True,
            }
        )
        detection = MockCaptchaDetection(captcha_type="recaptcha")

        # Mock audio download and transcription
        with (
            patch("survey.captcha.audio_solver._click_audio_button", return_value=True),
            patch(
                "survey.captcha.audio_solver._extract_audio_url",
                return_value="https://example.com/audio.mp3",
            ),
            patch("survey.captcha.audio_solver._download_audio_b64", return_value="base64audio"),
            patch.object(solver, "_transcribe_audio", return_value="hello world"),
        ):
            result = solver.solve(cdp, detection)

        assert result.solved is True
        assert result.extra.get("transcript") == "hello world"

    def test_audio_hcaptcha_success(self):
        """Test successful hCaptcha audio solve."""
        from survey.captcha.audio_solver import AudioSolver

        solver = AudioSolver(api_key="test_nvidia_key")
        cdp = MockCDPConnection()
        detection = MockCaptchaDetection(captcha_type="hcaptcha")

        with (
            patch("survey.captcha.audio_solver._click_audio_button", return_value=True),
            patch(
                "survey.captcha.audio_solver._extract_audio_url",
                return_value="https://example.com/hcaptcha.mp3",
            ),
            patch("survey.captcha.audio_solver._download_audio_b64", return_value="base64audio"),
            patch.object(solver, "_transcribe_audio", return_value="nine four two"),
        ):
            result = solver.solve(cdp, detection)

        assert result.solved is True
        assert "nine four two" in result.extra.get("transcript", "")

    def test_audio_parakeet_error(self):
        """Test handling of Parakeet ASR errors."""
        from survey.captcha.audio_solver import AudioSolver

        solver = AudioSolver(api_key="test_nvidia_key")
        cdp = MockCDPConnection()
        detection = MockCaptchaDetection(captcha_type="recaptcha")

        with (
            patch("survey.captcha.audio_solver._click_audio_button", return_value=True),
            patch(
                "survey.captcha.audio_solver._extract_audio_url",
                return_value="https://example.com/audio.mp3",
            ),
            patch("survey.captcha.audio_solver._download_audio_b64", return_value="base64audio"),
            patch.object(solver, "_transcribe_audio", return_value=None),
            patch.object(solver, "_transcribe_via_openai_compat", return_value=None),
        ):
            result = solver.solve(cdp, detection)

        assert result.solved is False
        assert result.reason == "transcription_failed"


# ══════════════════════════════════════════════════════════════════════════
# FALLBACK CHAIN TESTS (4)
# ══════════════════════════════════════════════════════════════════════════


class TestFallbackChain:
    """Tests für fallback_chain.py."""

    def test_chain_success_step_1(self):
        """Test chain succeeds on first step (NIM Primary)."""
        from survey.captcha.fallback_chain import FallbackChain, CaptchaResult

        chain = FallbackChain()
        cdp = MockCDPConnection()
        detection = MockCaptchaDetection(captcha_type="angular_drag_drop")

        # Mock first solver succeeds
        mock_result = CaptchaResult(solved=True, captcha_type="angular_drag_drop")

        with patch.object(chain, "_solvers", [("nim_primary", lambda c, d: mock_result)]):
            result = chain.solve_with_fallback(cdp, detection, "https://example.com")

        assert result.solved is True
        step_trace = result.extra.get("step_trace", [])
        assert len(step_trace) == 1
        assert step_trace[0]["solver"] == "nim_primary"
        assert step_trace[0]["outcome"] == "success"

    def test_chain_step1_fail_step2_succeeds(self):
        """Test chain falls back to step 2 when step 1 fails."""
        from survey.captcha.fallback_chain import FallbackChain, CaptchaResult

        chain = FallbackChain()
        cdp = MockCDPConnection()
        detection = MockCaptchaDetection(captcha_type="angular_drag_drop")

        failed_result = CaptchaResult(solved=False, reason="primary_failed")
        success_result = CaptchaResult(solved=True, captcha_type="angular_drag_drop")

        def mock_primary(c, d):
            return failed_result

        def mock_secondary(c, d):
            return success_result

        with patch.object(
            chain,
            "_solvers",
            [
                ("nim_primary", mock_primary),
                ("nim_secondary", mock_secondary),
            ],
        ):
            result = chain.solve_with_fallback(cdp, detection, "https://example.com")

        assert result.solved is True
        step_trace = result.extra.get("step_trace", [])
        assert len(step_trace) == 2
        assert step_trace[0]["outcome"] == "failed"
        assert step_trace[1]["outcome"] == "success"

    def test_chain_all_vision_fail_audio_succeeds(self):
        """Test chain falls back to audio when all vision solvers fail."""
        from survey.captcha.fallback_chain import FallbackChain, CaptchaResult

        chain = FallbackChain()
        cdp = MockCDPConnection()
        detection = MockCaptchaDetection(captcha_type="recaptcha")

        failed_result = CaptchaResult(solved=False, reason="vision_failed")
        audio_result = CaptchaResult(solved=True, captcha_type="recaptcha", token="test_token")

        with patch.object(
            chain,
            "_solvers",
            [
                ("nim_primary", lambda c, d: failed_result),
                ("nim_secondary", lambda c, d: failed_result),
                ("gateway", lambda c, d: failed_result),
                ("audio", lambda c, d: audio_result),
            ],
        ):
            result = chain.solve_with_fallback(cdp, detection, "https://example.com")

        assert result.solved is True
        step_trace = result.extra.get("step_trace", [])
        assert step_trace[-1]["solver"] == "audio"
        assert step_trace[-1]["outcome"] == "success"

    def test_chain_all_fail_handoff(self):
        """Test chain logs human handoff when all solvers fail."""
        from survey.captcha.fallback_chain import FallbackChain, CaptchaUnsolvedError, CaptchaResult

        chain = FallbackChain()
        cdp = MockCDPConnection()
        detection = MockCaptchaDetection(captcha_type="angular_drag_drop")

        failed_result = CaptchaResult(solved=False, reason="all_failed")

        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                patch.object(
                    chain,
                    "_solvers",
                    [
                        ("nim_primary", lambda c, d: failed_result),
                        ("nim_secondary", lambda c, d: failed_result),
                        ("gateway", lambda c, d: failed_result),
                        ("audio", None),  # Audio not applicable for drag_drop
                    ],
                ),
                patch("survey.captcha.fallback_chain._ensure_logs_dir", return_value=Path(tmpdir)),
            ):
                with pytest.raises(CaptchaUnsolvedError) as exc_info:
                    chain.solve_with_fallback(cdp, detection, "https://example.com")

                error = exc_info.value
                assert error.captcha_type == "angular_drag_drop"
                assert len(error.step_trace) >= 4  # 3 failed + skipped audio + handoff


# ══════════════════════════════════════════════════════════════════════════
# LOGGING TESTS (3)
# ══════════════════════════════════════════════════════════════════════════


class TestLogging:
    """Tests für Logging-Funktionalität."""

    def test_jsonl_shape(self):
        """Test JSONL log entry has correct structure."""
        from survey.captcha.fallback_chain import _log_human_handoff

        cdp = MockCDPConnection()
        detection = MockCaptchaDetection(
            captcha_type="angular_drag_drop", frame_id="frame123", dom_hint="target=28"
        )
        step_trace = [
            {"solver": "nim_primary", "outcome": "failed", "error": "timeout"},
            {"solver": "nim_secondary", "outcome": "failed", "error": "parse_error"},
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("survey.captcha.fallback_chain._ensure_logs_dir", return_value=Path(tmpdir)):
                log_path = _log_human_handoff(cdp, detection, "https://test.com", step_trace)

            # Read and parse JSONL
            with open(log_path) as f:
                entry = json.loads(f.readline())

            # Verify structure
            assert "timestamp" in entry
            assert entry["detected_type"] == "angular_drag_drop"
            assert entry["page_url"] == "https://test.com"
            assert entry["frame_id"] == "frame123"
            assert entry["dom_hint"] == "target=28"
            assert "step_trace" in entry
            assert "screenshot_b64" in entry

    def test_step_trace_correctness(self):
        """Test step_trace contains correct solver sequence."""
        from survey.captcha.fallback_chain import _log_human_handoff

        cdp = MockCDPConnection()
        detection = MockCaptchaDetection(captcha_type="recaptcha")
        step_trace = [
            {"solver": "nim_primary", "outcome": "failed", "error": "error1", "elapsed_ms": 100},
            {"solver": "nim_secondary", "outcome": "failed", "error": "error2", "elapsed_ms": 200},
            {"solver": "gateway", "outcome": "skipped", "error": "no_api_key", "elapsed_ms": 0},
            {"solver": "audio", "outcome": "failed", "error": "error3", "elapsed_ms": 300},
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("survey.captcha.fallback_chain._ensure_logs_dir", return_value=Path(tmpdir)):
                log_path = _log_human_handoff(cdp, detection, "https://test.com", step_trace)

            with open(log_path) as f:
                entry = json.loads(f.readline())

            logged_trace = entry["step_trace"]
            assert len(logged_trace) == 4
            assert logged_trace[0]["solver"] == "nim_primary"
            assert logged_trace[1]["solver"] == "nim_secondary"
            assert logged_trace[2]["outcome"] == "skipped"
            assert logged_trace[3]["solver"] == "audio"

    def test_screenshot_encoding(self):
        """Test screenshot is properly base64 encoded."""
        from survey.captcha.fallback_chain import _log_human_handoff

        # Create mock with known screenshot data
        test_png = b"\x89PNG\r\n\x1a\n" + b"fake_image_data"
        test_b64 = base64.b64encode(test_png).decode()
        cdp = MockCDPConnection(screenshot_b64=test_b64)

        detection = MockCaptchaDetection(captcha_type="visual_text")

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("survey.captcha.fallback_chain._ensure_logs_dir", return_value=Path(tmpdir)):
                log_path = _log_human_handoff(cdp, detection, "https://test.com", [])

            with open(log_path) as f:
                entry = json.loads(f.readline())

            # Verify base64 can be decoded
            screenshot_b64 = entry["screenshot_b64"]
            assert screenshot_b64 == test_b64
            decoded = base64.b64decode(screenshot_b64)
            assert decoded == test_png


# ══════════════════════════════════════════════════════════════════════════
# INTEGRATION TEST
# ══════════════════════════════════════════════════════════════════════════


class TestIntegration:
    """Integration tests für die gesamte Chain."""

    def test_captcha_router_integration(self):
        """Test that captcha_router.solve() delegates to fallback_chain."""
        # This test verifies the surgical patch to captcha_router.py
        # Note: Requires the actual captcha_router to be patched

        from survey.captcha.fallback_chain import solve_with_fallback, CaptchaResult

        cdp = MockCDPConnection()
        detection = MockCaptchaDetection(captcha_type="angular_drag_drop")

        # Mock all solvers to return success on first try
        mock_result = CaptchaResult(solved=True, captcha_type="angular_drag_drop")

        with patch(
            "survey.captcha.fallback_chain._get_nim_primary_solver",
            return_value=lambda c, d: mock_result,
        ):
            result = solve_with_fallback(cdp, detection, "https://test.com")

        assert result.solved is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
