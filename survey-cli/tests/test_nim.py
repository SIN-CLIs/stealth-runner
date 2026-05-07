"""Test NIMClient — decide(), parse_response(), build_survey_prompt(), get_nim().

WARUM: Sicherstellung der NVIDIA NIM Integration.
Die NIM-API liefert Actions für den Survey-Loop; Parsing-Fehler oder
falsche Prompt-Konstruktion disqualifizieren den Agent sofort.

ARCHITEKTUR: Unittest mit unittest.mock (MagicMock, patch).
HTTP-Requests an die NVIDIA NIM API werden gepatcht.
Es werden JSON-Parsing, Regex-Extraktion, Keyword-Fallbacks,
Token-Counting und Singleton-Verhalten getestet.

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

import survey.nim as nim_module
from survey.nim import (
    parse_response, build_survey_prompt, get_nim, NIMClient,
    DEFAULT_MODEL, DEFAULT_BASE_URL, MAX_TOKENS
)


# =============================================================================
# parse_response tests
# =============================================================================
class TestParseResponseJsonList(unittest.TestCase):
    def test_parses_json_array_of_actions(self):
        raw = '[{"ref":"@e0","action":"click"}]'
        result = parse_response(raw)
        self.assertEqual(result, [{"ref": "@e0", "action": "click"}])


class TestParseResponseJsonListMultiple(unittest.TestCase):
    def test_parses_json_array_multiple_actions(self):
        raw = '[{"ref":"@e0","action":"select"},{"action":"submit"}]'
        result = parse_response(raw)
        self.assertEqual(result, [
            {"ref": "@e0", "action": "select"},
            {"action": "submit"},
        ])


class TestParseResponseJsonDict(unittest.TestCase):
    def test_extracts_actions_key_from_dict(self):
        raw = '{"actions":[{"ref":"@e0","action":"click"}]}'
        result = parse_response(raw)
        self.assertEqual(result, [{"ref": "@e0", "action": "click"}])


class TestParseResponseJsonDictNoActions(unittest.TestCase):
    def test_wraps_plain_dict_in_list(self):
        raw = '{"ref":"@e5","action":"fill","value":"Berlin"}'
        result = parse_response(raw)
        self.assertEqual(result, [{"ref": "@e5", "action": "fill", "value": "Berlin"}])


class TestParseResponseMarkdownFenced(unittest.TestCase):
    def test_strips_triple_backtick_fence_with_lang(self):
        raw = '```json\n[{"ref":"@e0","action":"click"}]\n```'
        result = parse_response(raw)
        self.assertEqual(result, [{"ref": "@e0", "action": "click"}])


class TestParseResponseMarkdownFencedNoLang(unittest.TestCase):
    def test_strips_triple_backtick_fence_without_lang(self):
        raw = '```\n[{"ref":"@e0","action":"click"}]\n```'
        result = parse_response(raw)
        self.assertEqual(result, [{"ref": "@e0", "action": "click"}])


class TestParseResponseRegexExtraction(unittest.TestCase):
    def test_extracts_json_array_from_surrounding_text(self):
        raw = 'I think we need to do this: [{"ref":"@e0","action":"select"}]. That should work.'
        result = parse_response(raw)
        self.assertEqual(result, [{"ref": "@e0", "action": "select"}])


class TestParseResponseRegexWithNewlines(unittest.TestCase):
    def test_extracts_json_array_across_lines(self):
        raw = 'Analysis:\nHere is the plan:\n[\n  {"ref":"@e0","action":"click"}\n]\nDone.'
        result = parse_response(raw)
        self.assertEqual(result, [{"ref": "@e0", "action": "click"}])


class TestParseResponseCompleteKeyword(unittest.TestCase):
    def test_returns_complete_action_on_complete_keyword(self):
        raw = "The survey is now complete."
        result = parse_response(raw)
        self.assertEqual(result, [{"action": "complete"}])


class TestParseResponseDoneKeyword(unittest.TestCase):
    def test_returns_complete_action_on_done_keyword(self):
        raw = "All done here."
        result = parse_response(raw)
        self.assertEqual(result, [{"action": "complete"}])


class TestParseResponseNoneInput(unittest.TestCase):
    def test_falls_back_to_submit_on_none(self):
        result = parse_response(None)
        self.assertEqual(result, [{"action": "submit"}])


class TestParseResponseEmptyString(unittest.TestCase):
    def test_falls_back_to_submit_on_empty(self):
        result = parse_response("")
        self.assertEqual(result, [{"action": "submit"}])


class TestParseResponseGarbled(unittest.TestCase):
    def test_falls_back_to_submit_on_garbled_text(self):
        result = parse_response("asdfghjkl 12345 !@#$%")
        self.assertEqual(result, [{"action": "submit"}])


class TestParseResponseWhitespaceOnly(unittest.TestCase):
    def test_falls_back_to_submit_on_whitespace_only(self):
        result = parse_response("   \n  \t  ")
        self.assertEqual(result, [{"action": "submit"}])


# =============================================================================
# decide() tests with mocked OpenAI
# =============================================================================

SAMPLE_SNAPSHOT = {
    "refs": {"@e0": {"role": "radio", "text": "Männlich"}},
    "semantic": {"questions": [], "progress": "1/5"},
    "provider": "test",
}
SAMPLE_PROFILE = {"age": 32, "gender_label": "Männlich"}


def _make_mock_chat_response(content, total_tokens=150):
    """Build a mock OpenAI chat completion response."""
    mock_choice = MagicMock()
    mock_choice.message.content = content
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage.total_tokens = total_tokens
    return mock_response


class TestDecideMockedApiValidJson(unittest.TestCase):
    @patch("survey.nim.OpenAI")
    def test_returns_parsed_actions_from_api_response(self, MockOpenAI):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_mock_chat_response(
            '[{"ref":"@e0","action":"select"},{"action":"submit"}]',
        )
        MockOpenAI.return_value = mock_client

        client = NIMClient(api_key="nvapi-test-key")
        result = client.decide(snapshot=SAMPLE_SNAPSHOT, profile=SAMPLE_PROFILE)

        self.assertEqual(result["actions"], [
            {"ref": "@e0", "action": "select"},
            {"action": "submit"},
        ])


class TestDecideMockedApiDictResponse(unittest.TestCase):
    @patch("survey.nim.OpenAI")
    def test_parses_dict_response_with_actions_key(self, MockOpenAI):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_mock_chat_response(
            '{"actions":[{"ref":"@e1","action":"fill","value":"Berlin"}]}',
        )
        MockOpenAI.return_value = mock_client

        client = NIMClient(api_key="nvapi-test-key")
        result = client.decide(snapshot=SAMPLE_SNAPSHOT, profile=SAMPLE_PROFILE)

        self.assertEqual(result["actions"], [
            {"ref": "@e1", "action": "fill", "value": "Berlin"},
        ])


class TestDecideApiErrorFallback(unittest.TestCase):
    @patch("survey.nim.OpenAI")
    def test_falls_back_to_submit_on_api_exception(self, MockOpenAI):
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("503 Service Unavailable")
        MockOpenAI.return_value = mock_client

        client = NIMClient(api_key="nvapi-test-key")
        result = client.decide(snapshot=SAMPLE_SNAPSHOT, profile={})

        self.assertEqual(result["actions"], [{"action": "submit"}])


class TestDecideApiErrorModelLabel(unittest.TestCase):
    @patch("survey.nim.OpenAI")
    def test_labels_fallback_on_api_error(self, MockOpenAI):
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("timeout")
        MockOpenAI.return_value = mock_client

        client = NIMClient(api_key="nvapi-test-key")
        result = client.decide(snapshot=SAMPLE_SNAPSHOT, profile={})

        self.assertEqual(result["model"], "fallback")


class TestDecideApiErrorZeroTokens(unittest.TestCase):
    @patch("survey.nim.OpenAI")
    def test_reports_zero_tokens_on_api_error(self, MockOpenAI):
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("timeout")
        MockOpenAI.return_value = mock_client

        client = NIMClient(api_key="nvapi-test-key")
        result = client.decide(snapshot=SAMPLE_SNAPSHOT, profile={})

        self.assertEqual(result["tokens"]["total"], 0)


class TestDecideCountsTokens(unittest.TestCase):
    @patch("survey.nim.OpenAI")
    def test_records_token_count_from_api_usage(self, MockOpenAI):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_mock_chat_response(
            '[{"ref":"@e0","action":"click"}]', total_tokens=311,
        )
        MockOpenAI.return_value = mock_client

        client = NIMClient(api_key="nvapi-test-key")
        result = client.decide(snapshot=SAMPLE_SNAPSHOT, profile={})

        self.assertEqual(result["tokens"]["total"], 311)


class TestDecideRecordsModel(unittest.TestCase):
    @patch("survey.nim.OpenAI")
    def test_records_model_from_client_config(self, MockOpenAI):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_mock_chat_response(
            '[{"action":"submit"}]',
        )
        MockOpenAI.return_value = mock_client

        client = NIMClient(api_key="nvapi-test-key", model="custom/model-v1")
        result = client.decide(snapshot=SAMPLE_SNAPSHOT, profile={})

        self.assertEqual(result["model"], "custom/model-v1")


class TestDecideRecordsRawResponse(unittest.TestCase):
    @patch("survey.nim.OpenAI")
    def test_stores_abbreviated_raw_response(self, MockOpenAI):
        long_content = "x" * 300
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_mock_chat_response(
            long_content,
        )
        MockOpenAI.return_value = mock_client

        client = NIMClient(api_key="nvapi-test-key")
        result = client.decide(snapshot=SAMPLE_SNAPSHOT, profile={})

        self.assertEqual(len(result["raw_response"]), 200)


class TestDecideRecordsElapsedMs(unittest.TestCase):
    @patch("survey.nim.OpenAI")
    def test_records_positive_elapsed_milliseconds(self, MockOpenAI):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_mock_chat_response(
            '[{"action":"submit"}]',
        )
        MockOpenAI.return_value = mock_client

        client = NIMClient(api_key="nvapi-test-key")
        result = client.decide(snapshot=SAMPLE_SNAPSHOT, profile={})

        self.assertGreaterEqual(result["elapsed_ms"], 0)


class TestDecideNoApiKeyAutoPilot(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_returns_auto_pilot_when_no_api_key_set(self):
        client = NIMClient(api_key=None)
        result = client.decide(snapshot=SAMPLE_SNAPSHOT, profile={})

        self.assertEqual(result["model"], "auto_pilot")


class TestDecideNoApiKeySubmitFallback(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_returns_submit_action_when_no_api_key(self):
        client = NIMClient(api_key=None)
        result = client.decide(snapshot=SAMPLE_SNAPSHOT, profile={})

        self.assertEqual(result["actions"], [{"action": "submit"}])


class TestDecideNoApiKeyZeroTokens(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_returns_zero_tokens_when_no_api_key(self):
        client = NIMClient(api_key=None)
        result = client.decide(snapshot=SAMPLE_SNAPSHOT, profile={})

        self.assertEqual(result["tokens"]["total"], 0)


class TestDecideNoApiKeyZeroElapsed(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_returns_zero_elapsed_when_no_api_key(self):
        client = NIMClient(api_key=None)
        result = client.decide(snapshot=SAMPLE_SNAPSHOT, profile={})

        self.assertEqual(result["elapsed_ms"], 0)


class TestDecideEmptyContentFallback(unittest.TestCase):
    @patch("survey.nim.OpenAI")
    def test_falls_back_when_api_returns_empty_content(self, MockOpenAI):
        mock_response = _make_mock_chat_response("", total_tokens=10)
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        MockOpenAI.return_value = mock_client

        client = NIMClient(api_key="nvapi-test-key")
        result = client.decide(snapshot=SAMPLE_SNAPSHOT, profile={})

        self.assertEqual(result["actions"], [{"action": "submit"}])


class TestDecideUsesCorrectMaxTokens(unittest.TestCase):
    @patch("survey.nim.OpenAI")
    def test_passes_max_tokens_to_api_call(self, MockOpenAI):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_mock_chat_response(
            '[{"action":"submit"}]',
        )
        MockOpenAI.return_value = mock_client

        client = NIMClient(api_key="nvapi-test-key")
        client.decide(snapshot=SAMPLE_SNAPSHOT, profile={})

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        self.assertEqual(call_kwargs["max_tokens"], MAX_TOKENS)


class TestDecideUsesZeroTemperature(unittest.TestCase):
    @patch("survey.nim.OpenAI")
    def test_passes_zero_temperature_by_default(self, MockOpenAI):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_mock_chat_response(
            '[{"action":"submit"}]',
        )
        MockOpenAI.return_value = mock_client

        client = NIMClient(api_key="nvapi-test-key")
        client.decide(snapshot=SAMPLE_SNAPSHOT, profile={})

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        self.assertEqual(call_kwargs["temperature"], 0.0)


class TestDecideCustomTemperature(unittest.TestCase):
    @patch("survey.nim.OpenAI")
    def test_passes_custom_temperature_when_specified(self, MockOpenAI):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_mock_chat_response(
            '[{"action":"submit"}]',
        )
        MockOpenAI.return_value = mock_client

        client = NIMClient(api_key="nvapi-test-key")
        client.decide(snapshot=SAMPLE_SNAPSHOT, profile={}, temperature=0.7)

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        self.assertEqual(call_kwargs["temperature"], 0.7)


# =============================================================================
# NIMClient.available property
# =============================================================================
class TestNimClientAvailableTrue(unittest.TestCase):
    def test_available_is_true_when_api_key_provided(self):
        client = NIMClient(api_key="nvapi-test-key")
        self.assertTrue(client.available)


class TestNimClientAvailableFalse(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_available_is_false_when_no_api_key(self):
        client = NIMClient(api_key=None)
        self.assertFalse(client.available)


# =============================================================================
# get_nim() singleton
# =============================================================================
class TestGetNimSingleton(unittest.TestCase):

    def setUp(self):
        nim_module._default_client = None

    def test_returns_same_instance_on_repeated_calls(self):
        client1 = get_nim()
        client2 = get_nim()
        self.assertIs(client1, client2)


# =============================================================================
# build_survey_prompt tests
# =============================================================================
class TestBuildSurveyPromptIncludesProfile(unittest.TestCase):
    def test_includes_profile_gender_label(self):
        snapshot = {
            "refs": {"@e0": {"role": "radio", "text": "Männlich"}},
            "semantic": {"questions": [], "progress": "1/5"},
            "provider": "qualtrics",
        }
        profile = {"age": 32, "gender_label": "Männlich", "city": "Berlin"}

        prompt = build_survey_prompt(snapshot, profile)
        self.assertIn("Männlich", prompt)


class TestBuildSurveyPromptIncludesProvider(unittest.TestCase):
    def test_includes_provider_name(self):
        snapshot = {
            "refs": {},
            "semantic": {"questions": [], "progress": "1/5"},
            "provider": "qualtrics",
        }
        profile = {}

        prompt = build_survey_prompt(snapshot, profile)
        self.assertIn("qualtrics", prompt)


class TestBuildSurveyPromptIncludesProgress(unittest.TestCase):
    def test_includes_progress_field(self):
        snapshot = {
            "refs": {},
            "semantic": {"questions": [], "progress": "3/10"},
            "provider": "test",
        }
        profile = {}

        prompt = build_survey_prompt(snapshot, profile)
        self.assertIn("3/10", prompt)


class TestBuildSurveyPromptIncludesSnapshotRefs(unittest.TestCase):
    def test_includes_snapshot_element_refs(self):
        snapshot = {
            "refs": {"@e0": {"role": "radio", "text": "Option A"}},
            "semantic": {"questions": [], "progress": "1/5"},
            "provider": "test",
        }
        profile = {}

        prompt = build_survey_prompt(snapshot, profile)
        self.assertIn("@e0", prompt)
        self.assertIn("Option A", prompt)


class TestBuildSurveyPromptIncludesQuestions(unittest.TestCase):
    def test_includes_detected_questions(self):
        snapshot = {
            "refs": {},
            "semantic": {"questions": ["What is your age?"], "progress": "1/5"},
            "provider": "test",
        }
        profile = {}

        prompt = build_survey_prompt(snapshot, profile)
        self.assertIn("What is your age?", prompt)


class TestBuildSurveyPromptTruncatesRefs(unittest.TestCase):
    def test_limits_elements_to_max_25(self):
        refs = {}
        for i in range(50):
            refs[f"@e{i}"] = {"role": "radio", "text": f"Option {i}"}
        snapshot = {
            "refs": refs,
            "semantic": {"questions": [], "progress": "1/5"},
            "provider": "test",
        }
        profile = {}

        prompt = build_survey_prompt(snapshot, profile)
        self.assertIn("@e0", prompt)
        self.assertIn("@e24", prompt)
        self.assertNotIn("@e25", prompt)


class TestBuildSurveyPromptFiltersNones(unittest.TestCase):
    def test_excludes_none_profile_values(self):
        snapshot = {
            "refs": {},
            "semantic": {"questions": [], "progress": "1/5"},
            "provider": "test",
        }
        profile = {"age": None, "gender_label": None, "city": "Berlin"}

        prompt = build_survey_prompt(snapshot, profile)
        self.assertIn("Berlin", prompt)
        self.assertNotIn('"age": null', prompt)


class TestBuildSurveyPromptWithLearnings(unittest.TestCase):
    def test_accepts_learnings_parameter(self):
        snapshot = {
            "refs": {},
            "semantic": {"questions": [], "progress": "1/5"},
            "provider": "test",
        }
        profile = {}
        learnings = {"avoid": ["skip_button"]}

        # Should not crash with learnings
        prompt = build_survey_prompt(snapshot, profile, learnings=learnings)
        self.assertIsInstance(prompt, str)


class TestBuildSurveyPromptWithHistory(unittest.TestCase):
    def test_accepts_history_parameter(self):
        snapshot = {
            "refs": {},
            "semantic": {"questions": [], "progress": "1/5"},
            "provider": "test",
        }
        profile = {}
        history = [{"actions": ["click"]}]

        # Should not crash with history
        prompt = build_survey_prompt(snapshot, profile, history=history)
        self.assertIsInstance(prompt, str)


if __name__ == "__main__":
    unittest.main(verbosity=2)
