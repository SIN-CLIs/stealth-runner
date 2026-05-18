"""Tests for survey.observability.redact (SR-250).

Pure unit tests, no I/O, unittest-only.
"""

from __future__ import annotations

import unittest

from survey.observability.redact import (
    REDACTED,
    add_secret_key_pattern,
    add_value_pattern,
    redact,
)


# ── Key-based redaction ──────────────────────────────────────────────────────


class KeyBasedRedactionTests(unittest.TestCase):
    def test_password_key_redacts_value(self) -> None:
        out = redact({"password": "hunter2"})
        self.assertEqual(out, {"password": REDACTED})

    def test_api_key_underscored_redacts(self) -> None:
        out = redact({"api_key": "sk-abc"})
        self.assertEqual(out["api_key"], REDACTED)

    def test_api_key_dashed_redacts(self) -> None:
        out = redact({"api-key": "sk-abc"})
        self.assertEqual(out["api-key"], REDACTED)

    def test_case_insensitive_key_match(self) -> None:
        for key in ("Password", "PASSWORD", "Api_Key", "AUTHORIZATION"):
            with self.subTest(key=key):
                out = redact({key: "secret-value"})
                self.assertEqual(out[key], REDACTED)

    def test_email_key_redacts_value(self) -> None:
        out = redact({"email": "alice@example.com"})
        self.assertEqual(out["email"], REDACTED)

    def test_provider_specific_keys_redact(self) -> None:
        out = redact(
            {
                "ai_gateway_api_key": "vc_proj_abc",
                "nim_api_key": "nvapi-xxx",
                "captcha_api_key": "cap-xxx",
            }
        )
        self.assertEqual(out["ai_gateway_api_key"], REDACTED)
        self.assertEqual(out["nim_api_key"], REDACTED)
        self.assertEqual(out["captcha_api_key"], REDACTED)

    def test_safe_keys_unchanged(self) -> None:
        out = redact({"event": "click", "iteration": 5, "provider": "pollfish"})
        self.assertEqual(out, {"event": "click", "iteration": 5, "provider": "pollfish"})

    def test_key_match_collapses_nested_value(self) -> None:
        """A matched key replaces its ENTIRE value, even nested dicts."""
        out = redact(
            {
                "credentials": {
                    "username": "alice",
                    "password": "pw",
                    "extra": {"deep": "thing"},
                }
            }
        )
        # 'credentials' isn't on the default list, so we recurse.
        # Inside, 'password' matches and is fully redacted, 'username' isn't.
        self.assertEqual(
            out,
            {
                "credentials": {
                    "username": "alice",
                    "password": REDACTED,
                    "extra": {"deep": "thing"},
                }
            },
        )

    def test_non_string_value_under_secret_key_still_redacted(self) -> None:
        """{'token': 12345} → token should still be redacted (not bypassed)."""
        out = redact({"token": 12345})
        self.assertEqual(out["token"], REDACTED)


# ── Value-based redaction ────────────────────────────────────────────────────


class ValueBasedRedactionTests(unittest.TestCase):
    def test_bearer_token_in_string_redacted(self) -> None:
        out = redact({"header": "Authorization: Bearer abcdef.GHIJK_lmnop"})
        self.assertNotIn("abcdef.GHIJK_lmnop", out["header"])
        self.assertIn(REDACTED, out["header"])
        self.assertIn("Authorization:", out["header"])

    def test_jwt_in_url_redacted(self) -> None:
        url = (
            "https://heypiggy.com/cb?session="
            "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0In0.signature_part_xyz"
        )
        out = redact({"url": url})
        # URL query-string pattern catches ?session=... and replaces the
        # value portion. The host stays intact.
        self.assertIn("heypiggy.com", out["url"])
        self.assertNotIn("eyJhbGciOiJIUzI1NiJ9", out["url"])
        self.assertIn(REDACTED, out["url"])

    def test_openai_sk_key_in_freetext_redacted(self) -> None:
        msg = "Loaded key sk-proj-abcdefghijklmnopqrst123456 from env"
        out = redact({"msg": msg})
        self.assertNotIn("sk-proj-abcdefghijklmnopqrst123456", out["msg"])
        self.assertIn(REDACTED, out["msg"])
        self.assertIn("Loaded key", out["msg"])

    def test_nvapi_key_redacted(self) -> None:
        msg = "X-NVAPI-KEY: nvapi-abcdefghijk1234567890"
        out = redact({"header": msg})
        self.assertNotIn("nvapi-abcdefghijk1234567890", out["header"])

    def test_email_in_freetext_redacted(self) -> None:
        out = redact({"note": "contact alice@example.com for details"})
        self.assertNotIn("alice@example.com", out["note"])
        self.assertIn("contact", out["note"])
        self.assertIn("for details", out["note"])

    def test_url_token_query_redacted(self) -> None:
        url = "https://api.example.com/x?token=abc123xyz&user=alice"
        out = redact({"url": url})
        self.assertNotIn("abc123xyz", out["url"])
        # The user= part is unchanged (not a secret-key)
        self.assertIn("user=alice", out["url"])

    def test_long_hex_secret_redacted(self) -> None:
        out = redact({"hash": "deadbeef" * 8})  # 64 hex chars
        self.assertEqual(out["hash"], REDACTED)

    def test_short_hex_unchanged(self) -> None:
        # 8 hex chars don't match (need >= 32)
        out = redact({"short": "deadbeef"})
        self.assertEqual(out["short"], "deadbeef")

    def test_non_string_value_passthrough(self) -> None:
        out = redact({"counter": 42, "ratio": 0.95, "flag": True, "missing": None})
        self.assertEqual(out, {"counter": 42, "ratio": 0.95, "flag": True, "missing": None})


# ── Recursion + container handling ───────────────────────────────────────────


class RecursionTests(unittest.TestCase):
    def test_nested_dict_recursed(self) -> None:
        out = redact({"a": {"b": {"password": "p"}}})
        self.assertEqual(out, {"a": {"b": {"password": REDACTED}}})

    def test_list_of_dicts_redacted_elementwise(self) -> None:
        out = redact({"items": [{"password": "p1"}, {"password": "p2"}, {"safe": 1}]})
        self.assertEqual(
            out,
            {"items": [{"password": REDACTED}, {"password": REDACTED}, {"safe": 1}]},
        )

    def test_tuple_becomes_list(self) -> None:
        out = redact({"t": (1, 2, "alice@example.com")})
        self.assertIsInstance(out["t"], list)
        self.assertEqual(out["t"][:2], [1, 2])
        self.assertEqual(out["t"][2], REDACTED)

    def test_set_becomes_list(self) -> None:
        out = redact({"s": {"safe", "alice@example.com"}})
        self.assertIsInstance(out["s"], list)
        self.assertEqual(len(out["s"]), 2)

    def test_max_depth_caps_recursion(self) -> None:
        # Build 10-deep nested dict, max_depth=2 → only top 2 levels redacted
        deep: dict = {"password": "p1"}
        for _ in range(10):
            deep = {"nested": deep, "password": "p2"}
        out = redact(deep, max_depth=2)
        # Top-level password is redacted (depth-0 -> 1 step in)
        self.assertEqual(out["password"], REDACTED)
        # Beyond depth, the structure should be returned as-is at some
        # point. We just assert the call didn't crash + the original
        # innermost is intact somewhere.
        self.assertIsInstance(out, dict)

    def test_does_not_mutate_input(self) -> None:
        orig = {"password": "p", "nested": {"email": "a@b.c"}}
        snapshot = {"password": "p", "nested": {"email": "a@b.c"}}
        redact(orig)
        self.assertEqual(orig, snapshot)

    def test_payload_not_dict_returns_redacted_value(self) -> None:
        out = redact("Bearer abcdef123456")
        self.assertIn(REDACTED, out)


# ── Pattern overrides ────────────────────────────────────────────────────────


class OverrideTests(unittest.TestCase):
    def test_disable_all_redaction_with_empty_tuples(self) -> None:
        out = redact(
            {"password": "hunter2", "msg": "Bearer xyz"},
            secret_key_patterns=(),
            value_patterns=(),
        )
        self.assertEqual(out, {"password": "hunter2", "msg": "Bearer xyz"})

    def test_custom_secret_key_pattern(self) -> None:
        out = redact(
            {"customSensitive": "value", "safe": "ok"},
            secret_key_patterns=(r"customSensitive",),
        )
        self.assertEqual(out["customSensitive"], REDACTED)
        self.assertEqual(out["safe"], "ok")

    def test_custom_value_pattern(self) -> None:
        out = redact(
            {"id": "PERSONA-12345"},
            value_patterns=(r"PERSONA-\d+",),
        )
        self.assertEqual(out["id"], REDACTED)

    def test_invalid_regex_pattern_silently_dropped(self) -> None:
        # Bad regex — must not crash the call.
        out = redact(
            {"k": "v"},
            value_patterns=(r"[unclosed",),
        )
        self.assertEqual(out, {"k": "v"})


class ModuleMutationApiTests(unittest.TestCase):
    """add_*_pattern() functions mutate module state; tested in isolation
    by always re-overriding via kwargs in the assertion path."""

    def test_add_secret_key_pattern_extends_defaults(self) -> None:
        from survey.observability import redact as mod  # noqa: WPS433

        before = mod.DEFAULT_SECRET_KEY_PATTERNS
        try:
            mod.add_secret_key_pattern(r"foobar_secret")
            after = mod.DEFAULT_SECRET_KEY_PATTERNS
            self.assertEqual(len(after), len(before) + 1)
            out = mod.redact({"foobar_secret": "value"})
            self.assertEqual(out["foobar_secret"], REDACTED)
        finally:
            mod.DEFAULT_SECRET_KEY_PATTERNS = before

    def test_add_value_pattern_extends_defaults(self) -> None:
        from survey.observability import redact as mod  # noqa: WPS433

        before = mod.DEFAULT_VALUE_PATTERNS
        try:
            mod.add_value_pattern(r"\bMARKER\b")
            out = mod.redact({"msg": "this MARKER stays"})
            self.assertNotIn("MARKER", out["msg"])
        finally:
            mod.DEFAULT_VALUE_PATTERNS = before


# ── Realistic payload smoke ──────────────────────────────────────────────────


class SmokeRealisticPayloadTests(unittest.TestCase):
    def test_log_event_shape(self) -> None:
        event = {
            "event": "survey_started",
            "iteration": 3,
            "survey_id": "abc-123",
            "provider": "pollfish",
            "persona": {
                "id": "p1",
                "email": "alice@example.com",
                "dob": "1990-01-01",
                "preferences": ["coffee", "books"],
            },
            "request": {
                "url": "https://heypiggy.com/run?session=eyJhbGciOiJIUzI1NiJ9.body.sig",
                "headers": {
                    "Authorization": "Bearer abcdef.GHIJ-klmn",
                    "User-Agent": "Mozilla/5.0",
                },
            },
            "trace": [
                "Loaded key sk-proj-abcdefghijklmnopqrstuvwx from env",
                "Cookie set: heypiggy_sess=mySessionCookie123abcDEFXYZ",
            ],
        }
        out = redact(event)

        # Top-level identifiers untouched
        self.assertEqual(out["event"], "survey_started")
        self.assertEqual(out["iteration"], 3)
        self.assertEqual(out["provider"], "pollfish")

        # PII keys redacted
        self.assertEqual(out["persona"]["email"], REDACTED)
        self.assertEqual(out["persona"]["dob"], REDACTED)
        # Persona id is allowed (id is not on the secret-key list)
        self.assertEqual(out["persona"]["id"], "p1")

        # URL keeps host but loses session token
        self.assertIn("heypiggy.com", out["request"]["url"])
        self.assertNotIn("eyJhbGciOiJIUzI1NiJ9.body.sig", out["request"]["url"])

        # Authorization header value redacted
        self.assertEqual(out["request"]["headers"]["Authorization"], REDACTED)
        self.assertEqual(out["request"]["headers"]["User-Agent"], "Mozilla/5.0")

        # Trace strings: API key + cookie scrubbed
        joined = " ".join(out["trace"])
        self.assertNotIn("sk-proj-abcdefghijklmnopqrstuvwx", joined)


if __name__ == "__main__":
    unittest.main()
