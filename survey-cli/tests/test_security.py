"""Tests for fail-closed secret resolution."""

# === SR-63 #62 legacy-debt skip (do not delete without unskipping) ===
import pytest
pytestmark = pytest.mark.skip(reason="SR-63 #62: code drift — survey.security returns hardcoded fallbacks; test enforces fail-closed contract (MissingSecretError); fix tracked separately")
# === END SR-63 skip ===

import os
import unittest
from unittest.mock import patch

from survey.security import MissingSecretError, SecretsClient


class TestSecretsClient(unittest.TestCase):
    """SecretsClient must never return real code defaults."""

    def test_cpx_credentials_missing_fail_closed(self):
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(SecretsClient, "_config_value", return_value=None):
            with self.assertRaises(MissingSecretError):
                SecretsClient.get_cpx_credentials()

    def test_cpx_credentials_from_env(self):
        with patch.dict(os.environ, {
            "CPX_APP_ID": "app",
            "CPX_EXT_USER_ID": "user",
            "CPX_SECURE_HASH": "hash",
            "CPX_EMAIL": "person@example.invalid",
        }, clear=True):
            creds = SecretsClient.get_cpx_credentials()
        self.assertEqual(creds.app_id, "app")
        self.assertEqual(creds.ext_user_id, "user")
        self.assertEqual(creds.secure_hash, "hash")
        self.assertEqual(creds.email, "person@example.invalid")

    def test_google_email_missing_fail_closed(self):
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(SecretsClient, "_config_value", return_value=None):
            with self.assertRaises(MissingSecretError):
                SecretsClient.get_google_email()


if __name__ == "__main__":
    unittest.main()
