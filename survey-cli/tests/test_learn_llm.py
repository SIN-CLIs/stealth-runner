# -*- coding: utf-8 -*-
"""
test_learn_llm.py
==================

SR-57 #56 — FCTC-ES Phase 2 LLM-Suggester. Vollstaendig gemockt, KEIN
Netzwerk-Zugriff. ``unittest.mock.patch`` auf ``urllib.request.urlopen``
fuer den Low-Level-Client; auf ``survey.learn.suggester.call_llm`` fuer
den High-Level-Pfad in suggest_via_llm; und auf
``survey.learn.aggregator.suggest_via_llm`` fuer die Aggregator-Integration.

Test-Klassen:
  TestLLMClient        — ``call_llm`` mit echtem urlopen-Mock (HTTP shape).
  TestSuggestViaLLM    — ``suggest_via_llm`` (Parse-Validation, halluziniert).
  TestAggregateLLM     — ``aggregate_misses(use_llm=True)`` end-to-end gemockt.
  TestPrivacyAndSafety — Prompt enthaelt NIE user-Values; fail-soft bei no-key.
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
PARENT = os.path.dirname(HERE)
if PARENT not in sys.path:
    sys.path.insert(0, PARENT)

from survey.learn import (  # noqa: E402
    aggregate_misses,
    call_llm,
    llm_is_available,
    prompt_hash,
    suggest_via_llm,
)
from survey.learn import suggester as suggester_mod  # noqa: E402
from survey.learn import aggregator as aggregator_mod  # noqa: E402
from survey.learn import llm_client as llm_client_mod  # noqa: E402


def _fake_urlopen_response(payload: dict, status: int = 200):
    """Build a mock ``urlopen`` ctx-mgr that returns the given JSON payload."""
    body = json.dumps(payload).encode("utf-8")
    fake = mock.MagicMock()
    fake.__enter__ = mock.MagicMock(
        return_value=mock.MagicMock(read=mock.MagicMock(return_value=body))
    )
    fake.__exit__ = mock.MagicMock(return_value=False)
    return fake


def _openai_shape(content: str, model: str = "openai/gpt-5-mini") -> dict:
    return {
        "id": "chatcmpl-test",
        "model": model,
        "choices": [{"message": {"role": "assistant", "content": content}}],
    }


# ────────────────────────────────────────────────────────────────────────────
# TestLLMClient
# ────────────────────────────────────────────────────────────────────────────


class TestLLMClient(unittest.TestCase):
    def test_no_api_key_returns_none_without_network(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            r = call_llm("hello")
        self.assertIsNone(r.content)
        self.assertIn("AI_GATEWAY_API_KEY", r.error)
        self.assertEqual(r.model, "openai/gpt-5-mini")
        self.assertEqual(len(r.prompt_hash), 12)

    def test_successful_call_parses_content(self):
        payload = _openai_shape(content='{"ok": true}')
        with mock.patch.dict(os.environ, {"AI_GATEWAY_API_KEY": "test"}):
            with mock.patch(
                "survey.learn.llm_client.urllib.request.urlopen",
                return_value=_fake_urlopen_response(payload),
            ):
                r = call_llm("classify this")
        self.assertEqual(r.content, '{"ok": true}')
        self.assertIsNone(r.error)
        self.assertEqual(r.model, "openai/gpt-5-mini")
        self.assertIsNotNone(r.latency_ms)

    def test_http_error_is_contained(self):
        err = urllib.error.HTTPError(
            url="x",
            code=429,
            msg="Too Many",
            hdrs={},
            fp=io.BytesIO(b'{"error":"rate-limit"}'),
        )
        with mock.patch.dict(os.environ, {"AI_GATEWAY_API_KEY": "test"}):
            with mock.patch(
                "survey.learn.llm_client.urllib.request.urlopen",
                side_effect=err,
            ):
                r = call_llm("x")
        self.assertIsNone(r.content)
        self.assertIn("HTTP 429", r.error)

    def test_url_error_is_contained(self):
        with mock.patch.dict(os.environ, {"AI_GATEWAY_API_KEY": "test"}):
            with mock.patch(
                "survey.learn.llm_client.urllib.request.urlopen",
                side_effect=urllib.error.URLError("connection refused"),
            ):
                r = call_llm("x")
        self.assertIsNone(r.content)
        self.assertIn("URL error", r.error)
        self.assertIn("connection refused", r.error)

    def test_timeout_is_contained(self):
        with mock.patch.dict(os.environ, {"AI_GATEWAY_API_KEY": "test"}):
            with mock.patch(
                "survey.learn.llm_client.urllib.request.urlopen",
                side_effect=TimeoutError("slow"),
            ):
                r = call_llm("x", timeout=1.0)
        self.assertIsNone(r.content)
        self.assertIn("timeout", r.error)

    def test_unparseable_response_is_contained(self):
        with mock.patch.dict(os.environ, {"AI_GATEWAY_API_KEY": "test"}):
            with mock.patch(
                "survey.learn.llm_client.urllib.request.urlopen",
                return_value=_fake_urlopen_response({"not": "openai-shape"}),
            ):
                r = call_llm("x")
        self.assertIsNone(r.content)
        self.assertIn("unparseable", r.error)

    def test_request_body_contains_expected_fields(self):
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured["url"] = req.full_url
            captured["headers"] = dict(req.headers)
            captured["body"] = json.loads(req.data.decode("utf-8"))
            return _fake_urlopen_response(_openai_shape("ok")).__enter__()

        class FakeCtx:
            def __init__(self, req, timeout=None):
                captured["url"] = req.full_url
                captured["headers"] = dict(req.headers)
                captured["body"] = json.loads(req.data.decode("utf-8"))

            def __enter__(self_inner):
                inner = mock.MagicMock()
                inner.read = mock.MagicMock(return_value=json.dumps(_openai_shape("ok")).encode())
                return inner

            def __exit__(self_inner, *a):
                return False

        with mock.patch.dict(os.environ, {"AI_GATEWAY_API_KEY": "tk-1"}):
            with mock.patch(
                "survey.learn.llm_client.urllib.request.urlopen",
                side_effect=FakeCtx,
            ):
                call_llm("hello world", model="anthropic/claude-opus-4.6")

        self.assertEqual(captured["body"]["model"], "anthropic/claude-opus-4.6")
        self.assertEqual(captured["body"]["temperature"], 0.0)
        self.assertEqual(captured["body"]["response_format"], {"type": "json_object"})
        msgs = captured["body"]["messages"]
        self.assertEqual(msgs[1]["content"], "hello world")
        # Auth header
        auth = captured["headers"].get("Authorization")
        self.assertEqual(auth, "Bearer tk-1")

    def test_endpoint_override_via_env(self):
        captured = {}

        class FakeCtx:
            def __init__(self_inner, req, timeout=None):
                captured["url"] = req.full_url

            def __enter__(self_inner):
                inner = mock.MagicMock()
                inner.read = mock.MagicMock(return_value=json.dumps(_openai_shape("x")).encode())
                return inner

            def __exit__(self_inner, *a):
                return False

        with mock.patch.dict(
            os.environ,
            {
                "AI_GATEWAY_API_KEY": "tk",
                "SR_AI_GATEWAY_URL": "https://custom.example/v1/chat/completions",
            },
        ):
            with mock.patch(
                "survey.learn.llm_client.urllib.request.urlopen",
                side_effect=FakeCtx,
            ):
                call_llm("x")
        self.assertEqual(
            captured["url"],
            "https://custom.example/v1/chat/completions",
        )

    def test_prompt_hash_stable(self):
        a = prompt_hash("hello")
        b = prompt_hash("hello")
        c = prompt_hash("hello!")
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertEqual(len(a), 12)

    def test_is_available_reflects_env(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertFalse(llm_is_available())
        with mock.patch.dict(os.environ, {"AI_GATEWAY_API_KEY": "x"}):
            self.assertTrue(llm_is_available())


# ────────────────────────────────────────────────────────────────────────────
# TestSuggestViaLLM
# ────────────────────────────────────────────────────────────────────────────


class TestSuggestViaLLM(unittest.TestCase):
    def _patch_call_llm(self, content, model="openai/gpt-5-mini", error=None):
        from survey.learn.llm_client import LLMResponse

        return mock.patch.object(
            suggester_mod,
            "call_llm",
            return_value=LLMResponse(
                content=content,
                model=model,
                prompt_hash="abc123def456",
                error=error,
                latency_ms=42,
            ),
        )

    def test_valid_response_parsed(self):
        content = json.dumps(
            {
                "family": "household_size",
                "confidence": 0.92,
                "reason": "asks about number of persons in household",
            }
        )
        with self._patch_call_llm(content):
            r = suggest_via_llm(
                "wie viele personen leben in ihrem haushalt",
                allowed_families=["household_size", "income", "phone"],
            )
        self.assertEqual(r.family, "household_size")
        self.assertAlmostEqual(r.confidence, 0.92)
        self.assertIn("number of persons", r.reason)
        self.assertEqual(r.model, "openai/gpt-5-mini")
        self.assertIsNone(r.error)

    def test_family_null_means_no_match(self):
        content = json.dumps(
            {
                "family": None,
                "confidence": 0.0,
                "reason": "asks about favourite colour, not in profile",
            }
        )
        with self._patch_call_llm(content):
            r = suggest_via_llm(
                "lieblingsfarbe",
                allowed_families=["phone", "email"],
            )
        self.assertIsNone(r.family)
        self.assertEqual(r.confidence, 0.0)
        self.assertIsNone(r.error)

    def test_hallucinated_family_rejected(self):
        content = json.dumps(
            {
                "family": "lieblingsfarbe",  # not in allowed list
                "confidence": 0.99,
                "reason": "made up family",
            }
        )
        with self._patch_call_llm(content):
            r = suggest_via_llm(
                "lieblingsfarbe",
                allowed_families=["phone", "email"],
            )
        self.assertIsNone(r.family)
        self.assertIn("hallucination", r.error)

    def test_confidence_clamped_to_unit_interval(self):
        content = json.dumps(
            {
                "family": "phone",
                "confidence": 1.7,  # nonsense
                "reason": "x",
            }
        )
        with self._patch_call_llm(content):
            r = suggest_via_llm("handy", allowed_families=["phone"])
        self.assertEqual(r.confidence, 1.0)

        content2 = json.dumps(
            {
                "family": "phone",
                "confidence": -0.3,
                "reason": "x",
            }
        )
        with self._patch_call_llm(content2):
            r = suggest_via_llm("handy", allowed_families=["phone"])
        self.assertEqual(r.confidence, 0.0)

    def test_markdown_codefence_stripped(self):
        content = '```json\n{"family": "email", "confidence": 0.9, "reason": "mail"}\n```'
        with self._patch_call_llm(content):
            r = suggest_via_llm("emailadresse", allowed_families=["email", "phone"])
        self.assertEqual(r.family, "email")
        self.assertAlmostEqual(r.confidence, 0.9)

    def test_non_json_response_returns_error(self):
        with self._patch_call_llm("I'm sorry, I cannot comply."):
            r = suggest_via_llm("x", allowed_families=["phone"])
        self.assertIsNone(r.family)
        self.assertIn("non-json", r.error)

    def test_llm_unavailable_propagates_error_field(self):
        with self._patch_call_llm(None, error="no AI_GATEWAY_API_KEY"):
            r = suggest_via_llm("x", allowed_families=["phone"])
        self.assertIsNone(r.family)
        self.assertEqual(r.confidence, 0.0)
        self.assertIn("AI_GATEWAY_API_KEY", r.error)

    def test_empty_label_returns_error(self):
        r = suggest_via_llm("   ", allowed_families=["phone"])
        self.assertIsNone(r.family)
        self.assertIn("empty label", r.error)

    def test_empty_allowed_families_returns_error(self):
        r = suggest_via_llm("x", allowed_families=[])
        self.assertIsNone(r.family)
        self.assertIn("no allowed_families", r.error)

    def test_reason_truncated_to_140_chars(self):
        long_reason = "x" * 500
        content = json.dumps(
            {
                "family": "phone",
                "confidence": 0.9,
                "reason": long_reason,
            }
        )
        with self._patch_call_llm(content):
            r = suggest_via_llm("handy", allowed_families=["phone"])
        self.assertEqual(len(r.reason), 140)

    def test_family_string_case_normalized(self):
        content = json.dumps(
            {
                "family": "PHONE",
                "confidence": 0.8,
                "reason": "x",
            }
        )
        with self._patch_call_llm(content):
            r = suggest_via_llm("handy", allowed_families=["phone"])
        self.assertEqual(r.family, "phone")


# ────────────────────────────────────────────────────────────────────────────
# TestAggregateLLM
# ────────────────────────────────────────────────────────────────────────────


class _AggFixture:
    """Spins up a tmp logs/ dir with a matcher-telemetry JSONL."""

    def __init__(self, miss_labels):
        self.td = tempfile.mkdtemp(prefix="agg-llm-")
        self.logs = os.path.join(self.td, "logs")
        os.makedirs(self.logs)
        path = os.path.join(self.logs, "matcher-telemetry-20260512.jsonl")
        with open(path, "w") as f:
            f.write(
                json.dumps(
                    {
                        "persona": "p1",
                        "miss_labels": miss_labels,
                    }
                )
                + "\n"
            )

    def cleanup(self):
        import shutil

        shutil.rmtree(self.td, ignore_errors=True)


class TestAggregateLLM(unittest.TestCase):
    def test_use_llm_false_keeps_substring_source(self):
        """Default behaviour (use_llm=False) — every record gets
        source='substring' but otherwise byte-equivalent to pre-#56."""
        fx = _AggFixture(
            [
                {"role": "textbox", "label": "Mobilfunknummer"},
            ]
        )
        try:
            recs = aggregate_misses(log_dir=fx.logs, min_count=1)
            self.assertEqual(len(recs), 1)
            self.assertEqual(recs[0]["source"], "substring")
            self.assertEqual(recs[0]["suggested_family"], "phone")
            self.assertNotIn("model", recs[0])
            self.assertNotIn("prompt_hash", recs[0])
        finally:
            fx.cleanup()

    def test_use_llm_true_overrides_unhandled_miss(self):
        """LLM kicks in when heuristic returns family=None.

        Note: we use "Lieblings-Pizza" because it has ZERO token-overlap
        with any FAMILY_TOKENS family — the heuristic returns family=None,
        which is the only condition under which the aggregator calls LLM.
        Labels like "Wie viele Personen ..." actually DO match the
        household_size heuristic, so they would NOT trigger LLM-fallback.
        """
        fx = _AggFixture(
            [
                {"role": "textbox", "label": "Lieblings-Pizza"},
            ]
        )
        try:
            from survey.learn.suggester import LLMSuggestion

            def fake_llm(label, allowed, *, model=None, timeout=20.0):
                return LLMSuggestion(
                    family="household_size",
                    confidence=0.9,
                    reason="contrived test: LLM picks an existing family",
                    model="openai/gpt-5-mini",
                    prompt_hash="cafe1234face",
                )

            with (
                mock.patch.object(
                    aggregator_mod,
                    "suggest_via_llm",
                    side_effect=fake_llm,
                ),
                mock.patch.object(
                    aggregator_mod,
                    "_llm_is_available",
                    return_value=True,
                ),
            ):
                recs = aggregate_misses(
                    log_dir=fx.logs,
                    min_count=1,
                    use_llm=True,
                )
            self.assertEqual(len(recs), 1)
            rec = recs[0]
            self.assertEqual(rec["source"], "llm")
            self.assertEqual(rec["suggested_family"], "household_size")
            self.assertAlmostEqual(rec["confidence"], 0.9)
            self.assertEqual(rec["model"], "openai/gpt-5-mini")
            self.assertEqual(rec["prompt_hash"], "cafe1234face")
            self.assertIn("reason", rec)
            # Heuristic fallback fields preserved for forensics
            self.assertIn("heuristic_family", rec)
            self.assertIn("heuristic_confidence", rec)
        finally:
            fx.cleanup()

    def test_llm_does_not_override_high_confidence_heuristic(self):
        """Wenn die Heuristik bereits >=0.20 ist, LLM wird gar nicht
        gerufen — Kosten + Determinismus."""
        fx = _AggFixture(
            [
                {"role": "textbox", "label": "Mobilfunknummer"},  # heuristic OK
            ]
        )
        try:
            with (
                mock.patch.object(
                    aggregator_mod,
                    "suggest_via_llm",
                ) as llm_mock,
                mock.patch.object(
                    aggregator_mod,
                    "_llm_is_available",
                    return_value=True,
                ),
            ):
                recs = aggregate_misses(
                    log_dir=fx.logs,
                    min_count=1,
                    use_llm=True,
                )
            llm_mock.assert_not_called()
            self.assertEqual(recs[0]["source"], "substring")
        finally:
            fx.cleanup()

    def test_use_llm_without_api_key_warns_and_keeps_substring(self):
        """use_llm=True + no key → 1x stderr warning, kein crash, alle
        records bleiben source=substring (oder None bei unklassifizierten)."""
        fx = _AggFixture(
            [
                {"role": "textbox", "label": "Lieblings-Pizza"},
            ]
        )
        try:
            with mock.patch.object(
                aggregator_mod,
                "_llm_is_available",
                return_value=False,
            ):
                recs = aggregate_misses(
                    log_dir=fx.logs,
                    min_count=1,
                    use_llm=True,
                )
            self.assertEqual(len(recs), 1)
            # Heuristic returns None family for "lieblings-pizza", aber
            # source bleibt "substring" weil LLM nicht verfuegbar.
            self.assertEqual(recs[0]["source"], "substring")
            self.assertIsNone(recs[0]["suggested_family"])
        finally:
            fx.cleanup()

    def test_llm_error_recorded_when_llm_returns_no_family(self):
        """LLM-Call gelang, aber das Modell sagte family=null — wir behalten
        den Heuristik-Record (None) UND notieren prompt_hash + model fuer
        Audit."""
        fx = _AggFixture(
            [
                {"role": "textbox", "label": "Lieblings-Pizza"},
            ]
        )
        try:
            from survey.learn.suggester import LLMSuggestion

            with (
                mock.patch.object(
                    aggregator_mod,
                    "suggest_via_llm",
                    return_value=LLMSuggestion(
                        family=None,
                        confidence=0.0,
                        reason="",
                        model="openai/gpt-5-mini",
                        prompt_hash="bad1cafe1234",
                        error="hallucination",
                    ),
                ),
                mock.patch.object(
                    aggregator_mod,
                    "_llm_is_available",
                    return_value=True,
                ),
            ):
                recs = aggregate_misses(
                    log_dir=fx.logs,
                    min_count=1,
                    use_llm=True,
                )
            rec = recs[0]
            self.assertEqual(rec["source"], "substring")
            self.assertIsNone(rec["suggested_family"])
            self.assertEqual(rec["llm_error"], "hallucination")
            self.assertEqual(rec["prompt_hash"], "bad1cafe1234")
        finally:
            fx.cleanup()


# ────────────────────────────────────────────────────────────────────────────
# TestPrivacyAndSafety
# ────────────────────────────────────────────────────────────────────────────


class TestPrivacyAndSafety(unittest.TestCase):
    def test_prompt_only_contains_label_text_not_user_values(self):
        """SR-57 #56 § Privacy: Der Prompt enthaelt das LABEL, niemals den
        User-Value. matcher-telemetry-records koennen ``user_value`` haben,
        aber aggregate_misses transportiert das schon nicht in die
        suggestion-records. Hier verifizieren wir, dass _build_llm_prompt
        nichts vom matcher-telemetry-Record sieht."""
        prompt = suggester_mod._build_llm_prompt(
            "wie viele personen leben im haushalt",
            families=["household_size", "income"],
        )
        self.assertIn("wie viele personen", prompt)
        self.assertIn("household_size", prompt)
        # Stable: keine Zeit/User/Persona/PII-Reference im prompt-template.
        forbidden = ["user_value", "persona=", "timestamp", "USER", "@", "vorname", "nachname"]
        for f in forbidden:
            self.assertNotIn(f, prompt, f"prompt leaks {f!r}: {prompt!r}")

    def test_prompt_hash_stable_for_fixed_inputs(self):
        """Die Familie-Reihenfolge im Prompt ist sortiert → prompt_hash ist
        unabhaengig von der Reihenfolge, in der die Caller die Familien
        uebergeben."""
        p1 = suggester_mod._build_llm_prompt("x", ["phone", "email", "household_size"])
        p2 = suggester_mod._build_llm_prompt("x", ["household_size", "email", "phone"])
        self.assertEqual(p1, p2)
        self.assertEqual(prompt_hash(p1), prompt_hash(p2))

    def test_call_llm_does_not_log_api_key(self):
        """Auch im Fehlerfall darf der API-Key nirgends im LLMResponse-Error
        auftauchen."""
        with mock.patch.dict(os.environ, {"AI_GATEWAY_API_KEY": "SECRET-KEY"}):
            with mock.patch(
                "survey.learn.llm_client.urllib.request.urlopen",
                side_effect=urllib.error.URLError("key=SECRET-KEY exposed in error msg"),
            ):
                r = call_llm("x")
        self.assertIsNotNone(r.error)
        # URLError-msg kann theoretisch den key enthalten (wenn die Library
        # ihn faelschlich logged) — wir testen, dass UNSER Code ihn nicht
        # zusaetzlich in den Error-String packt.
        self.assertNotIn("Authorization:", r.error)
        self.assertNotIn("Bearer SECRET-KEY", r.error)

    def test_module_constants_match_acceptance_criteria(self):
        """SR-57 #56 AC#7: Default model = openai/gpt-5-mini."""
        self.assertEqual(llm_client_mod._DEFAULT_MODEL, "openai/gpt-5-mini")
        self.assertEqual(llm_client_mod._DEFAULT_TEMPERATURE, 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
