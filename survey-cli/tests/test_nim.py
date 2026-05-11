"""Tests fuer NIMClient — decide(), build_survey_prompt(), get_nim().

WARUM:
    Die NIM-API liefert Actions fuer den Survey-Loop. Parsing-Fehler oder
    falsche Prompt-Konstruktion disqualifizieren den Agent sofort. Diese
    Suite deckt das Verhalten des CLIENT und des PROMPT-DISPATCHERS ab —
    NICHT das Verhalten des Parsers. Parser-Regressionen leben jetzt in
    ``tests/test_nim_parse_response.py`` (SR-50 Dedupe).

ARCHITEKTUR:
    - unittest + unittest.mock (MagicMock, patch).
    - ``survey.nim.OpenAI`` wird patched: keine echten HTTP-Calls.
    - Asserts gegen den NEUEN Contract:
        * Fallback bei Fehlern / fehlendem Key / leerem Content ist
          ``[{"action": "wait"}]`` (NICHT mehr ``submit``).
        * v2-Schema verwendet ``stable_id`` statt ``ref``.
        * Prompt-Dispatcher wechselt anhand ``snapshot["elements"]``
          zwischen v2- und Legacy-Prompt.

KONTRAKT (mirror von survey/nim.py):
    decide(snapshot, profile) -> {
        "actions": [...], "model": str, "elapsed_ms": int,
        "tokens": {"total": int}, "raw_response"?: str
    }

BANNED:
    - Tests die parse_response erneut abdecken (das macht test_nim_parse_response.py).
    - Asserts auf ``submit``-Fallback (alter Contract, killt den Loop).
    - Echte HTTP-Requests (OpenAI patchen!).
"""

import os
import sys
import time
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import survey.nim as nim_module
from survey.nim import (
    NIMClient,
    DEFAULT_MODEL,
    MAX_TOKENS,
    build_survey_prompt,
    build_v2_prompt,
    build_legacy_prompt,
    get_nim,
)


# =============================================================================
# Sample inputs — v2 (stable_id) und legacy (refs) Snapshots
# =============================================================================

V2_SNAPSHOT = {
    "elements": [
        {"stable_id": "el_001", "role": "radio", "name": "Maennlich",
         "value": "", "checked": False},
        {"stable_id": "el_002", "role": "radio", "name": "Weiblich",
         "value": "", "checked": False},
        {"stable_id": "btn_next", "role": "button", "name": "Weiter",
         "value": "", "checked": False},
    ],
    "avoid_stable_id": "",
    "no_dom_change_count": 0,
    "iteration": 1,
    "provider": "qualtrics",
}

LEGACY_SNAPSHOT = {
    "refs": {"@e0": {"role": "radio", "text": "Maennlich"}},
    "semantic": {"questions": ["Wie alt sind Sie?"], "progress": "1/5"},
    "provider": "qualtrics",
}

SAMPLE_PROFILE = {
    "age": 32,
    "gender_label": "Maennlich",
    "city": "Berlin",
}


def _make_chat_response(content, total_tokens=150):
    """Baut ein Mock-OpenAI-ChatCompletion-Result."""
    mock_choice = MagicMock()
    mock_choice.message.content = content
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage.total_tokens = total_tokens
    return mock_response


# =============================================================================
# decide() — Happy Path mit gemocktem OpenAI
# =============================================================================

class TestDecideReturnsActionsFromApi(unittest.TestCase):
    """API liefert v2-JSON → decide() reicht die Actions durch."""

    @patch("survey.nim.OpenAI")
    def test_returns_parsed_actions(self, MockOpenAI):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_chat_response(
            '{"actions":[{"stable_id":"el_001","action":"click"}]}',
        )
        MockOpenAI.return_value = mock_client

        client = NIMClient(api_key="nvapi-test-key")
        result = client.decide(snapshot=V2_SNAPSHOT, profile=SAMPLE_PROFILE)

        self.assertEqual(result["actions"], [
            {"stable_id": "el_001", "action": "click"},
        ])


class TestDecideRefNormalisedToStableId(unittest.TestCase):
    """Wenn das Modell Legacy ``ref`` liefert, normalisiert der Parser
    nach ``stable_id`` — decide() muss das transparent durchreichen."""

    @patch("survey.nim.OpenAI")
    def test_legacy_ref_becomes_stable_id(self, MockOpenAI):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_chat_response(
            '[{"ref":"@e0","action":"click"}]',
        )
        MockOpenAI.return_value = mock_client

        client = NIMClient(api_key="nvapi-test-key")
        result = client.decide(snapshot=V2_SNAPSHOT, profile=SAMPLE_PROFILE)

        self.assertEqual(result["actions"], [
            {"stable_id": "@e0", "action": "click"},
        ])


class TestDecideFillWithValue(unittest.TestCase):
    """fill-Action mit value muss als ein Action-Dict durchgereicht werden."""

    @patch("survey.nim.OpenAI")
    def test_fill_action_preserves_value(self, MockOpenAI):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_chat_response(
            '{"actions":[{"stable_id":"el_007","action":"fill","value":"Berlin"}]}',
        )
        MockOpenAI.return_value = mock_client

        client = NIMClient(api_key="nvapi-test-key")
        result = client.decide(snapshot=V2_SNAPSHOT, profile=SAMPLE_PROFILE)

        self.assertEqual(result["actions"], [
            {"stable_id": "el_007", "action": "fill", "value": "Berlin"},
        ])


class TestDecideRecordsTokens(unittest.TestCase):
    """``tokens.total`` muss aus der API-usage uebernommen werden."""

    @patch("survey.nim.OpenAI")
    def test_token_total_from_usage(self, MockOpenAI):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_chat_response(
            '{"actions":[{"action":"wait"}]}',
            total_tokens=311,
        )
        MockOpenAI.return_value = mock_client

        client = NIMClient(api_key="nvapi-test-key")
        result = client.decide(snapshot=V2_SNAPSHOT, profile={})

        self.assertEqual(result["tokens"]["total"], 311)


class TestDecideRecordsModelLabel(unittest.TestCase):
    """``model`` im Result muss exakt dem konfigurierten Model entsprechen."""

    @patch("survey.nim.OpenAI")
    def test_model_label_matches_config(self, MockOpenAI):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_chat_response(
            '{"actions":[{"action":"wait"}]}',
        )
        MockOpenAI.return_value = mock_client

        client = NIMClient(api_key="nvapi-test-key", model="custom/model-v1")
        result = client.decide(snapshot=V2_SNAPSHOT, profile={})

        self.assertEqual(result["model"], "custom/model-v1")


class TestDecideRecordsRawResponseAbbreviated(unittest.TestCase):
    """``raw_response`` wird auf maximal 200 Zeichen gekuerzt."""

    @patch("survey.nim.OpenAI")
    def test_raw_response_truncated_to_200_chars(self, MockOpenAI):
        long_content = "x" * 500
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_chat_response(
            long_content,
        )
        MockOpenAI.return_value = mock_client

        client = NIMClient(api_key="nvapi-test-key")
        result = client.decide(snapshot=V2_SNAPSHOT, profile={})

        self.assertEqual(len(result["raw_response"]), 200)


class TestDecideRecordsElapsedMs(unittest.TestCase):
    """``elapsed_ms`` muss eine nicht-negative Zahl sein."""

    @patch("survey.nim.OpenAI")
    def test_elapsed_ms_is_non_negative(self, MockOpenAI):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_chat_response(
            '{"actions":[{"action":"wait"}]}',
        )
        MockOpenAI.return_value = mock_client

        client = NIMClient(api_key="nvapi-test-key")
        result = client.decide(snapshot=V2_SNAPSHOT, profile={})

        self.assertGreaterEqual(result["elapsed_ms"], 0)


# =============================================================================
# decide() — API-Parameter
# =============================================================================

class TestDecidePassesMaxTokens(unittest.TestCase):
    """Der Client muss MAX_TOKENS an die API durchreichen."""

    @patch("survey.nim.OpenAI")
    def test_max_tokens_argument(self, MockOpenAI):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_chat_response(
            '{"actions":[{"action":"wait"}]}',
        )
        MockOpenAI.return_value = mock_client

        client = NIMClient(api_key="nvapi-test-key")
        client.decide(snapshot=V2_SNAPSHOT, profile={})

        kwargs = mock_client.chat.completions.create.call_args.kwargs
        self.assertEqual(kwargs["max_tokens"], MAX_TOKENS)


class TestDecidePassesDefaultTemperature(unittest.TestCase):
    """Default-Temperatur ist 0.0 fuer deterministische Outputs."""

    @patch("survey.nim.OpenAI")
    def test_default_temperature_is_zero(self, MockOpenAI):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_chat_response(
            '{"actions":[{"action":"wait"}]}',
        )
        MockOpenAI.return_value = mock_client

        client = NIMClient(api_key="nvapi-test-key")
        client.decide(snapshot=V2_SNAPSHOT, profile={})

        kwargs = mock_client.chat.completions.create.call_args.kwargs
        self.assertEqual(kwargs["temperature"], 0.0)


class TestDecidePassesCustomTemperature(unittest.TestCase):
    """Custom-Temperatur muss durchgereicht werden."""

    @patch("survey.nim.OpenAI")
    def test_custom_temperature_argument(self, MockOpenAI):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_chat_response(
            '{"actions":[{"action":"wait"}]}',
        )
        MockOpenAI.return_value = mock_client

        client = NIMClient(api_key="nvapi-test-key")
        client.decide(snapshot=V2_SNAPSHOT, profile={}, temperature=0.7)

        kwargs = mock_client.chat.completions.create.call_args.kwargs
        self.assertEqual(kwargs["temperature"], 0.7)


class TestDecidePassesDefaultModel(unittest.TestCase):
    """Ohne explizites Model muss DEFAULT_MODEL benutzt werden."""

    @patch.dict(os.environ, {}, clear=True)
    @patch("survey.nim.OpenAI")
    def test_default_model_is_nemotron(self, MockOpenAI):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_chat_response(
            '{"actions":[{"action":"wait"}]}',
        )
        MockOpenAI.return_value = mock_client

        client = NIMClient(api_key="nvapi-test-key")
        client.decide(snapshot=V2_SNAPSHOT, profile={})

        kwargs = mock_client.chat.completions.create.call_args.kwargs
        self.assertEqual(kwargs["model"], DEFAULT_MODEL)


# =============================================================================
# decide() — Fallback-Kontrakte
# =============================================================================

class TestDecideNoApiKeyAutoPilotModel(unittest.TestCase):
    """Ohne API-Key liefert decide() ``model="auto_pilot"``."""

    @patch.dict(os.environ, {}, clear=True)
    def test_returns_auto_pilot_model(self):
        client = NIMClient(api_key=None)
        result = client.decide(snapshot=V2_SNAPSHOT, profile={})

        self.assertEqual(result["model"], "auto_pilot")


class TestDecideNoApiKeyReturnsWait(unittest.TestCase):
    """Ohne API-Key liefert decide() ``[{"action": "wait"}]``
    (NICHT mehr ``submit`` — siehe Modul-Docstring)."""

    @patch.dict(os.environ, {}, clear=True)
    def test_returns_wait_fallback(self):
        client = NIMClient(api_key=None)
        result = client.decide(snapshot=V2_SNAPSHOT, profile={})

        self.assertEqual(result["actions"], [{"action": "wait"}])


class TestDecideNoApiKeyZeroTokens(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_zero_tokens(self):
        client = NIMClient(api_key=None)
        result = client.decide(snapshot=V2_SNAPSHOT, profile={})

        self.assertEqual(result["tokens"]["total"], 0)


class TestDecideNoApiKeyZeroElapsed(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_zero_elapsed_ms(self):
        client = NIMClient(api_key=None)
        result = client.decide(snapshot=V2_SNAPSHOT, profile={})

        self.assertEqual(result["elapsed_ms"], 0)


class TestDecideApiErrorReturnsWait(unittest.TestCase):
    """Unbekannte Exception → ``[{"action": "wait"}]`` (kein Loop-Crash)."""

    @patch("survey.nim.OpenAI")
    def test_wait_action_on_exception(self, MockOpenAI):
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception(
            "503 Service Unavailable",
        )
        MockOpenAI.return_value = mock_client

        client = NIMClient(api_key="nvapi-test-key")
        result = client.decide(snapshot=V2_SNAPSHOT, profile={})

        self.assertEqual(result["actions"], [{"action": "wait"}])


class TestDecideApiErrorFallbackModelLabel(unittest.TestCase):
    @patch("survey.nim.OpenAI")
    def test_model_label_is_fallback_on_error(self, MockOpenAI):
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("timeout")
        MockOpenAI.return_value = mock_client

        client = NIMClient(api_key="nvapi-test-key")
        result = client.decide(snapshot=V2_SNAPSHOT, profile={})

        self.assertEqual(result["model"], "fallback")


class TestDecideApiErrorZeroTokens(unittest.TestCase):
    @patch("survey.nim.OpenAI")
    def test_zero_tokens_on_error(self, MockOpenAI):
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("timeout")
        MockOpenAI.return_value = mock_client

        client = NIMClient(api_key="nvapi-test-key")
        result = client.decide(snapshot=V2_SNAPSHOT, profile={})

        self.assertEqual(result["tokens"]["total"], 0)


class TestDecideEmptyContentReturnsWait(unittest.TestCase):
    """API antwortet mit leerem Content → ``[{"action": "wait"}]``."""

    @patch("survey.nim.OpenAI")
    def test_wait_action_when_content_empty(self, MockOpenAI):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_chat_response(
            "", total_tokens=10,
        )
        MockOpenAI.return_value = mock_client

        client = NIMClient(api_key="nvapi-test-key")
        result = client.decide(snapshot=V2_SNAPSHOT, profile={})

        self.assertEqual(result["actions"], [{"action": "wait"}])


# =============================================================================
# Circuit-Breaker
# =============================================================================

class TestCircuitBreakerOpensAfterThreshold(unittest.TestCase):
    """Drei Folgefehler oeffnen den Breaker → naechster decide() ist
    sofort Fallback (ohne API-Call)."""

    @patch("survey.nim.OpenAI")
    def test_breaker_opens_after_three_failures(self, MockOpenAI):
        mock_client = MagicMock()
        # Wir patchen den Authentication-Pfad: ein einziger AuthError
        # triggert _record_failure einmal pro decide(), kein Retry.
        from openai import AuthenticationError
        mock_client.chat.completions.create.side_effect = AuthenticationError(
            "bad key", response=MagicMock(), body=None,
        )
        MockOpenAI.return_value = mock_client

        client = NIMClient(api_key="nvapi-test-key")
        for _ in range(3):
            client.decide(snapshot=V2_SNAPSHOT, profile={})

        self.assertFalse(client.available)


class TestCircuitBreakerOpenSkipsApi(unittest.TestCase):
    """Wenn Breaker offen ist, darf KEIN API-Call mehr passieren."""

    @patch("survey.nim.OpenAI")
    def test_open_breaker_does_not_call_api(self, MockOpenAI):
        mock_client = MagicMock()
        MockOpenAI.return_value = mock_client

        client = NIMClient(api_key="nvapi-test-key")
        client._available = False
        client.consecutive_failures = 5
        client.last_failure_time = time.time()

        result = client.decide(snapshot=V2_SNAPSHOT, profile={})

        self.assertEqual(result["model"], "fallback")
        mock_client.chat.completions.create.assert_not_called()


class TestCircuitBreakerSuccessResetsCounter(unittest.TestCase):
    """Ein erfolgreicher Call setzt den failure-counter auf 0 zurueck."""

    @patch("survey.nim.OpenAI")
    def test_success_resets_failures(self, MockOpenAI):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_chat_response(
            '{"actions":[{"action":"wait"}]}',
        )
        MockOpenAI.return_value = mock_client

        client = NIMClient(api_key="nvapi-test-key")
        client.consecutive_failures = 2
        client.decide(snapshot=V2_SNAPSHOT, profile={})

        self.assertEqual(client.consecutive_failures, 0)


# =============================================================================
# NIMClient.available property
# =============================================================================

class TestAvailableTrueWithKey(unittest.TestCase):
    def test_available_when_api_key_set(self):
        client = NIMClient(api_key="nvapi-test-key")
        self.assertTrue(client.available)


class TestAvailableFalseWithoutKey(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_not_available_without_api_key(self):
        client = NIMClient(api_key=None)
        self.assertFalse(client.available)


# =============================================================================
# get_nim() Singleton
# =============================================================================

class TestGetNimSingleton(unittest.TestCase):

    def setUp(self):
        nim_module._default_client = None

    def test_returns_same_instance(self):
        client1 = get_nim()
        client2 = get_nim()
        self.assertIs(client1, client2)


# =============================================================================
# build_survey_prompt — Dispatcher zwischen v2 und Legacy
# =============================================================================

class TestPromptDispatcherV2WhenElements(unittest.TestCase):
    """Snapshot enthaelt ``elements`` → v2-Prompt (mit stable_id-Hinweis)."""

    def test_dispatches_to_v2_prompt(self):
        prompt = build_survey_prompt(V2_SNAPSHOT, SAMPLE_PROFILE)
        # v2-Prompt enthaelt die wörtliche Schema-Beschreibung
        self.assertIn("stable_id", prompt)


class TestPromptDispatcherLegacyWhenRefs(unittest.TestCase):
    """Snapshot hat NUR ``refs`` (kein ``elements``) → Legacy-Prompt."""

    def test_dispatches_to_legacy_prompt(self):
        prompt = build_survey_prompt(LEGACY_SNAPSHOT, SAMPLE_PROFILE)
        # Legacy-Prompt-Beispiel-Schema verwendet @eN
        self.assertIn("@e0", prompt)


# =============================================================================
# build_v2_prompt — Inhalt
# =============================================================================

class TestV2PromptIncludesStableIds(unittest.TestCase):
    def test_includes_stable_id_values(self):
        prompt = build_v2_prompt(V2_SNAPSHOT, SAMPLE_PROFILE)
        self.assertIn("el_001", prompt)
        self.assertIn("btn_next", prompt)


class TestV2PromptIncludesElementNames(unittest.TestCase):
    def test_includes_accessible_names(self):
        prompt = build_v2_prompt(V2_SNAPSHOT, SAMPLE_PROFILE)
        self.assertIn("Maennlich", prompt)
        self.assertIn("Weiter", prompt)


class TestV2PromptIncludesProvider(unittest.TestCase):
    def test_includes_provider_name(self):
        prompt = build_v2_prompt(V2_SNAPSHOT, SAMPLE_PROFILE)
        self.assertIn("qualtrics", prompt)


class TestV2PromptIncludesProfile(unittest.TestCase):
    def test_includes_profile_city(self):
        prompt = build_v2_prompt(V2_SNAPSHOT, SAMPLE_PROFILE)
        self.assertIn("Berlin", prompt)


class TestV2PromptFiltersNoneProfileValues(unittest.TestCase):
    def test_none_profile_fields_not_serialised(self):
        profile = {"age": None, "gender_label": None, "city": "Berlin"}
        prompt = build_v2_prompt(V2_SNAPSHOT, profile)
        self.assertIn("Berlin", prompt)
        self.assertNotIn('"age": null', prompt)


class TestV2PromptAvoidHintEmittedWhenSet(unittest.TestCase):
    """Wenn ``avoid_stable_id`` gesetzt ist, MUSS der Prompt das Modell
    explizit warnen, diese id zu meiden (sonst Endlos-Loop)."""

    def test_emits_avoid_hint(self):
        snapshot = dict(V2_SNAPSHOT, avoid_stable_id="el_001")
        prompt = build_v2_prompt(snapshot, SAMPLE_PROFILE)
        self.assertIn("el_001", prompt)
        self.assertIn("WICHTIG", prompt)


class TestV2PromptNoDomChangeHintAfterThreshold(unittest.TestCase):
    """Bei ``no_dom_change_count >= 2`` muss ein Captcha-Hinweis im
    Prompt stehen (sonst klickt das Modell weiter ins Leere)."""

    def test_emits_no_dom_change_hint(self):
        snapshot = dict(V2_SNAPSHOT, no_dom_change_count=3)
        prompt = build_v2_prompt(snapshot, SAMPLE_PROFILE)
        self.assertIn("ACHTUNG", prompt)


class TestV2PromptTruncatesElementsTo30(unittest.TestCase):
    """Mehr als 30 Elemente → Prompt schneidet bei 30 ab (Token-Budget)."""

    def test_at_most_30_elements_in_prompt(self):
        elements = [
            {"stable_id": f"el_{i:03d}", "role": "radio",
             "name": f"Option {i}", "value": "", "checked": False}
            for i in range(50)
        ]
        snapshot = dict(V2_SNAPSHOT, elements=elements)
        prompt = build_v2_prompt(snapshot, {})
        # Erste 30 muessen drin sein, ab 30 nicht mehr
        self.assertIn("el_000", prompt)
        self.assertIn("el_029", prompt)
        self.assertNotIn("el_049", prompt)


# =============================================================================
# build_legacy_prompt — Backward-Compat
# =============================================================================

class TestLegacyPromptIncludesRefs(unittest.TestCase):
    def test_includes_refs(self):
        prompt = build_legacy_prompt(LEGACY_SNAPSHOT, SAMPLE_PROFILE)
        self.assertIn("@e0", prompt)
        self.assertIn("Maennlich", prompt)


class TestLegacyPromptIncludesProgress(unittest.TestCase):
    def test_includes_progress(self):
        prompt = build_legacy_prompt(LEGACY_SNAPSHOT, SAMPLE_PROFILE)
        self.assertIn("1/5", prompt)


class TestLegacyPromptIncludesQuestions(unittest.TestCase):
    def test_includes_detected_questions(self):
        prompt = build_legacy_prompt(LEGACY_SNAPSHOT, SAMPLE_PROFILE)
        self.assertIn("Wie alt sind Sie?", prompt)


# =============================================================================
# build_survey_prompt — Optional-Args (learnings/history)
# =============================================================================

class TestBuildSurveyPromptAcceptsLearnings(unittest.TestCase):
    def test_does_not_crash_with_learnings(self):
        learnings = {"avoid": ["skip_button"]}
        prompt = build_survey_prompt(V2_SNAPSHOT, SAMPLE_PROFILE, learnings=learnings)
        self.assertIsInstance(prompt, str)


class TestBuildSurveyPromptAcceptsHistory(unittest.TestCase):
    def test_does_not_crash_with_history(self):
        history = [{"actions": ["click"]}]
        prompt = build_survey_prompt(V2_SNAPSHOT, SAMPLE_PROFILE, history=history)
        self.assertIsInstance(prompt, str)


if __name__ == "__main__":
    unittest.main(verbosity=2)
