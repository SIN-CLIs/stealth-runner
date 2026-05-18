"""Tests for survey.reliability.env_check (SR-254).

Pure unit tests, no real env-mutation outside the test scope.
unittest-only.
"""

from __future__ import annotations

import unittest
from typing import Any

from survey.reliability.env_check import (
    EnvCheckResult,
    EnvRequirement,
    EnvVarStatus,
    REQUIRED_FOR_DAEMON,
    REQUIRED_FOR_LIVE_RUN,
    Severity,
    check_env,
    format_human_report,
)


# ── Helpers ─────────────────────────────────────────────────────────────────


def _req(name: str, severity: Severity = "required", **kwargs: Any) -> EnvRequirement:
    """Builder with sensible defaults for tests."""
    return EnvRequirement(
        name=name,
        severity=severity,
        description=kwargs.get("description", f"test var {name}"),
        validator=kwargs.get("validator"),
        default_hint=kwargs.get("default_hint"),
    )


# ── Basic check_env behaviour ───────────────────────────────────────────────


class CheckEnvBasicTests(unittest.TestCase):
    def test_all_required_present_passes(self) -> None:
        env = {"FOO": "bar", "BAZ": "qux"}
        result = check_env([_req("FOO"), _req("BAZ")], env=env)
        self.assertTrue(result.is_ok)
        self.assertEqual(len(result.missing_required), 0)
        self.assertEqual(len(result.missing_optional), 0)

    def test_missing_required_fails(self) -> None:
        env = {"FOO": "bar"}
        result = check_env([_req("FOO"), _req("BAZ")], env=env)
        self.assertFalse(result.is_ok)
        self.assertEqual(len(result.missing_required), 1)
        self.assertEqual(result.missing_required[0].name, "BAZ")

    def test_missing_optional_does_not_fail(self) -> None:
        env = {"FOO": "bar"}
        result = check_env(
            [_req("FOO"), _req("BAZ", severity="optional")],
            env=env,
        )
        self.assertTrue(result.is_ok)
        self.assertEqual(len(result.missing_optional), 1)

    def test_warning_severity_appears_but_does_not_fail(self) -> None:
        env: dict[str, str] = {}
        result = check_env(
            [_req("FOO", severity="warning")],
            env=env,
        )
        self.assertTrue(result.is_ok)
        self.assertEqual(len(result.warnings), 1)

    def test_empty_string_treated_as_missing(self) -> None:
        env = {"FOO": ""}
        result = check_env([_req("FOO")], env=env)
        self.assertFalse(result.is_ok)
        self.assertEqual(result.missing_required[0].name, "FOO")

    def test_whitespace_only_treated_as_missing(self) -> None:
        env = {"FOO": "   \n\t"}
        result = check_env([_req("FOO")], env=env)
        self.assertFalse(result.is_ok)


# ── Validator hooks ─────────────────────────────────────────────────────────


class ValidatorTests(unittest.TestCase):
    def test_validator_failure_marks_invalid(self) -> None:
        def must_be_int(v: str) -> str:
            try:
                int(v)
                return ""  # ok
            except ValueError:
                return f"not an int: {v!r}"

        env = {"PORT": "abc"}
        result = check_env([_req("PORT", validator=must_be_int)], env=env)
        self.assertFalse(result.is_ok)
        self.assertEqual(len(result.invalid), 1)
        self.assertEqual(result.invalid[0].requirement.name, "PORT")
        self.assertIn("not an int", result.invalid[0].error_message)

    def test_validator_pass_keeps_ok(self) -> None:
        def must_be_int(v: str) -> str:
            try:
                int(v)
                return ""
            except ValueError:
                return "bad"

        env = {"PORT": "9999"}
        result = check_env([_req("PORT", validator=must_be_int)], env=env)
        self.assertTrue(result.is_ok)

    def test_validator_failure_for_optional_does_not_fail_overall(self) -> None:
        def reject_all(_v: str) -> str:
            return "always fails"

        env = {"OPTIONAL_VAR": "value"}
        result = check_env(
            [_req("OPTIONAL_VAR", severity="optional", validator=reject_all)],
            env=env,
        )
        self.assertTrue(result.is_ok)
        self.assertEqual(len(result.invalid_optional), 1)

    def test_validator_exception_is_reported_not_propagated(self) -> None:
        def bad_validator(_v: str) -> str:
            raise RuntimeError("validator buggy")

        env = {"FOO": "value"}
        # Must NOT raise.
        result = check_env([_req("FOO", validator=bad_validator)], env=env)
        self.assertFalse(result.is_ok)
        self.assertEqual(len(result.invalid), 1)
        self.assertIn("validator buggy", result.invalid[0].error_message)


# ── Status enumeration ──────────────────────────────────────────────────────


class StatusTests(unittest.TestCase):
    def test_per_var_statuses_present(self) -> None:
        env = {"FOO": "bar"}
        result = check_env(
            [
                _req("FOO"),
                _req("BAZ"),
                _req("OPT", severity="optional"),
            ],
            env=env,
        )
        statuses = {s.name: s for s in result.statuses}
        self.assertEqual(statuses["FOO"].state, "present")
        self.assertEqual(statuses["BAZ"].state, "missing")
        self.assertEqual(statuses["OPT"].state, "missing")
        self.assertFalse(result.is_ok)

    def test_invalid_state_set_when_validator_fails(self) -> None:
        env = {"FOO": "bad"}
        result = check_env(
            [_req("FOO", validator=lambda v: "bad value")], env=env
        )
        statuses = {s.name: s.state for s in result.statuses}
        self.assertEqual(statuses["FOO"], "invalid")


# ── Human report format ─────────────────────────────────────────────────────


class FormatReportTests(unittest.TestCase):
    def test_report_shows_missing_required_first(self) -> None:
        env = {"PRESENT": "x"}
        result = check_env(
            [
                _req("PRESENT"),
                _req("MISSING_REQ"),
                _req("MISSING_OPT", severity="optional"),
            ],
            env=env,
        )
        report = format_human_report(result)
        idx_req = report.find("MISSING_REQ")
        idx_opt = report.find("MISSING_OPT")
        self.assertGreater(idx_req, -1)
        self.assertGreater(idx_opt, -1)
        self.assertLess(idx_req, idx_opt)

    def test_report_includes_default_hint_when_present(self) -> None:
        env: dict[str, str] = {}
        result = check_env(
            [_req("FOO", default_hint="set to 'http://localhost:3000'")],
            env=env,
        )
        report = format_human_report(result)
        self.assertIn("http://localhost:3000", report)

    def test_report_redacts_present_values(self) -> None:
        """Don't echo secrets back to the operator."""
        env = {"AI_GATEWAY_API_KEY": "vc_proj_very_secret"}
        result = check_env(
            [_req("AI_GATEWAY_API_KEY", description="LLM key")],
            env=env,
        )
        report = format_human_report(result)
        self.assertNotIn("vc_proj_very_secret", report)
        self.assertIn("AI_GATEWAY_API_KEY", report)
        self.assertIn("present", report.lower())

    def test_ok_report_states_ok(self) -> None:
        env = {"FOO": "bar"}
        result = check_env([_req("FOO")], env=env)
        report = format_human_report(result)
        self.assertIn("OK", report.upper())


# ── Default required lists ──────────────────────────────────────────────────


class DefaultRequirementsTests(unittest.TestCase):
    def test_required_for_daemon_is_non_empty(self) -> None:
        self.assertGreater(len(REQUIRED_FOR_DAEMON), 0)

    def test_required_for_live_run_extends_daemon(self) -> None:
        """Live-run set should be a superset of daemon set names."""
        daemon_names = {r.name for r in REQUIRED_FOR_DAEMON}
        live_names = {r.name for r in REQUIRED_FOR_LIVE_RUN}
        self.assertTrue(daemon_names.issubset(live_names))
        self.assertGreater(len(live_names), len(daemon_names))

    def test_default_lists_are_evaluable(self) -> None:
        result_d = check_env(REQUIRED_FOR_DAEMON, env={})
        result_l = check_env(REQUIRED_FOR_LIVE_RUN, env={})
        self.assertFalse(result_d.is_ok)
        self.assertFalse(result_l.is_ok)
        # And nothing crashes during reporting.
        format_human_report(result_d)
        format_human_report(result_l)


# ── Real os.environ default fallback ────────────────────────────────────────


class OsEnvironFallbackTests(unittest.TestCase):
    def test_default_env_is_os_environ(self) -> None:
        """When no env arg given, check_env reads from os.environ."""
        import os

        marker = "STEALTH_TEST_MARKER_SR_254"
        os.environ[marker] = "x"
        try:
            result = check_env([_req(marker)])
            self.assertTrue(result.is_ok)
        finally:
            del os.environ[marker]


# ── to_dict serialization ───────────────────────────────────────────────────


class SerializationTests(unittest.TestCase):
    def test_to_dict_is_json_safe(self) -> None:
        import json

        env = {"PRESENT": "x"}
        result = check_env(
            [_req("PRESENT"), _req("MISSING")], env=env
        )
        d = result.to_dict()
        roundtrip = json.loads(json.dumps(d))
        self.assertFalse(roundtrip["is_ok"])
        self.assertEqual(len(roundtrip["statuses"]), 2)
        self.assertEqual(len(roundtrip["missing_required"]), 1)


if __name__ == "__main__":
    unittest.main()
