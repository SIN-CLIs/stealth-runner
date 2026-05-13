"""
Tests for survey/network/beacon_filter.py (SR-174).

Coverage matrix:
    - Real-world beacon URL samples must match (10+).
    - Real-world non-beacon survey URLs must NOT match (10+).
    - Regression: "survey-analytics-provider.com" must NOT match (greedy-regex bug).
    - Custom patterns + extras compose correctly.
    - Empty/None URL handling.
    - Module-level singleton identity.
"""

from __future__ import annotations

import unittest

from survey.network.beacon_filter import (
    BeaconFilter,
    DEFAULT_BEACON_PATTERNS,
    get_default_filter,
    is_beacon,
)


# Real-world URL samples — must match (sampled from production logs).
BEACON_SAMPLES_POSITIVE = [
    "https://www.google-analytics.com/g/collect?v=2&tid=G-XYZ",
    "https://region1.google-analytics.com/g/collect?v=2",
    "https://www.googletagmanager.com/gtag/js?id=G-ABC123",
    "https://stats.g.doubleclick.net/g/collect?v=2",
    "https://ad.doubleclick.net/ddm/trackclk/N12345.123456;dc_trk_aid=1",
    "https://www.facebook.com/tr/?id=1234567890&ev=PageView",
    "https://script.hotjar.com/modules.html",
    "https://api.mixpanel.com/track/?data=eyJldmVudCI6...",
    "https://api.segment.io/v1/track",
    "https://cdn.segment.com/v1/projects/xyz/integrations",
    "https://api2.amplitude.com/2/httpapi",
    "https://o123456.ingest.sentry.io/api/9876/envelope/",
    "https://sessions.bugsnag.com/",
    "https://js-agent.newrelic.com/nr-1234.min.js",
    "https://pollfish.example.com/beacon/ping",
    "https://cint.example.com/telemetry/event",
    "https://lucid.example.com/_/log/exposure",
    "https://www.google-analytics.com/collect?v=1&tid=UA-X",
    "https://stats.example.com/track/click.gif?utm_source=ad&utm_medium=banner",
    "https://www.googletagmanager.com/gtag/js?id=GTM-XYZ",
]

# Real-world URL samples — must NOT match (these are legitimate survey/API calls).
BEACON_SAMPLES_NEGATIVE = [
    # The classic regression: greedy `analytics` would break this.
    "https://survey-analytics-provider.com/api/v1/responses",
    "https://analytics.example-survey.com/progress",  # provider's own progress endpoint
    # Survey-engine endpoints.
    "https://api.pollfish.com/v1/surveys/abc/answer",
    "https://respondent.cint.com/Survey/Select",
    "https://samplicio.us/respondent/qualifier",
    "https://www.qualtrics.com/jfe/preview/SV_abc/api/answer",
    "https://prolific.co/api/v1/submissions/xyz",
    # Heypiggy survey payload.
    "https://heypiggy.example/api/answer",
    # Non-beacon GET on an unrelated GIF (no utm/track/click query keys).
    "https://cdn.example.com/images/logo.gif",
    # NOT a beacon: a survey response that happens to live under /collect-data/.
    "https://survey.example.com/collect-data-from-user",
    # NOT a beacon: well-known asset paths.
    "https://cdn.example.com/main.js",
    "https://fonts.gstatic.com/s/roboto/v30/font.woff2",
    # NOT a beacon: similar-looking-but-not-matching path.
    "https://example.com/telemetry-config-export",  # contains "telemetry-" not segment "telemetry"
]


class TestBeaconFilterDefaults(unittest.TestCase):
    def test_default_patterns_non_empty(self):
        self.assertGreater(len(DEFAULT_BEACON_PATTERNS), 10)

    def test_positive_samples_match(self):
        f = BeaconFilter()
        misses = [u for u in BEACON_SAMPLES_POSITIVE if not f.is_beacon(u)]
        self.assertEqual(misses, [], f"Expected matches but missed: {misses}")

    def test_negative_samples_do_not_match(self):
        f = BeaconFilter()
        hits = [u for u in BEACON_SAMPLES_NEGATIVE if f.is_beacon(u)]
        self.assertEqual(hits, [], f"Unexpected matches (greedy regex?): {hits}")

    def test_greedy_regex_regression_survey_analytics(self):
        """Regression: greedy `analytics` substring must not match.

        This was the example called out in the issue body. If someone changes
        the default patterns to a greedy `analytics` substring, this test
        will catch it.
        """
        url = "https://survey-analytics-provider.com/api/v1/responses"
        self.assertFalse(BeaconFilter().is_beacon(url))

    def test_empty_url_not_beacon(self):
        self.assertFalse(BeaconFilter().is_beacon(""))

    def test_none_url_not_beacon(self):
        # is_beacon must accept anything falsy and return False without raising.
        self.assertFalse(BeaconFilter().is_beacon(None))  # type: ignore[arg-type]


class TestBeaconFilterCustom(unittest.TestCase):
    def test_custom_patterns_replace_defaults(self):
        # Custom: ONLY match URLs containing /custom-ping
        f = BeaconFilter(patterns=[r"/custom-ping"])
        self.assertTrue(f.is_beacon("https://x.com/custom-ping?u=1"))
        # Default GA URL no longer matches because we replaced defaults.
        self.assertFalse(f.is_beacon("https://www.google-analytics.com/collect"))

    def test_extras_extend_defaults(self):
        f = BeaconFilter(extra=[r"^https?://custom-tracker\.example\.com/"])
        self.assertTrue(f.is_beacon("https://custom-tracker.example.com/event"))
        # Defaults still apply.
        self.assertTrue(f.is_beacon("https://www.google-analytics.com/collect"))

    def test_case_insensitive_matching(self):
        f = BeaconFilter()
        self.assertTrue(f.is_beacon("https://WWW.GOOGLE-ANALYTICS.COM/collect"))


class TestModuleLevelHelpers(unittest.TestCase):
    def test_get_default_filter_returns_singleton(self):
        a = get_default_filter()
        b = get_default_filter()
        self.assertIs(a, b)

    def test_module_is_beacon_delegates_to_default(self):
        self.assertTrue(is_beacon("https://www.google-analytics.com/collect"))
        self.assertFalse(is_beacon("https://api.pollfish.com/v1/surveys"))


if __name__ == "__main__":
    unittest.main()
