"""Regression test for tools/smoke_match_field.py — keeps hit-rate >= 70%.

WARUM:
- Issue SR-51 fordert einen Smoke-Korpus, der schon **vor** dem ersten
  echten Survey-Run zeigt, ob ProfileLoader.match_field() relevante
  Label-Phrasen trifft.
- Der Korpus ist nicht in echtem HTML, sondern als typed dict aus dem
  Tool importiert (CORPUS = list of (role, label, expected_key)).
- Threshold 70% — bewusst niedrig, weil das Tool fuer Erweiterung der
  Patterns gedacht ist (man entdeckt Misses und fuegt Patterns hinzu).
  Aktuell stehen wir bei 100% (alle pos. + neg. Faelle korrekt) →
  Regression kommt wenn jemand ein Pattern bricht.

NICHT als Unit-Test der Patterns gedacht — dafuer gibt es
``test_profile_match_field.py`` mit gezielten Einzelfaellen. Das hier
ist nur die Aggregations-Sicht.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import unittest

# Make sure survey-cli/ is on PYTHONPATH so we can import `survey.*`.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# WARUM importlib statt ``from tools import smoke_match_field``:
# ``tools/__init__.py`` aggregiert weitere Tools (tool_find_new_tab) die
# ``requests`` als Hard-Dependency haben. ``requests`` ist nicht in der
# survey-cli/requirements.txt (test-Umgebung) — wuerde den Test grundlos
# zerschiessen. Direkt-Import des einen Moduls umgeht das.
_SMOKE_PATH = os.path.join(_ROOT, "tools", "smoke_match_field.py")
_spec = importlib.util.spec_from_file_location("smoke_match_field", _SMOKE_PATH)
assert _spec and _spec.loader, "cannot load smoke_match_field.py"
smoke = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(smoke)


class SmokeMatchFieldRegressionTest(unittest.TestCase):
    """Run the smoke tool inline and assert hit-rate >= 70%."""

    HIT_RATE_THRESHOLD = 70.0
    FALSE_POSITIVE_THRESHOLD = 20.0  # max 20% der negativen Faelle duerfen falsch positiv matchen

    def test_jeremy_schulze_smoke(self) -> None:
        result = smoke.run_smoke("jeremy_schulze", write_jsonl=False)
        self.assertGreaterEqual(
            result.hit_rate,
            self.HIT_RATE_THRESHOLD,
            f"Smoke-Korpus hit-rate {result.hit_rate:.1f}% < "
            f"{self.HIT_RATE_THRESHOLD}%. Misses: {result.misses[:5]}",
        )
        self.assertLessEqual(
            result.false_positive_rate,
            self.FALSE_POSITIVE_THRESHOLD,
            f"False-positive-rate {result.false_positive_rate:.1f}% > "
            f"{self.FALSE_POSITIVE_THRESHOLD}%. FPs: {result.false_positives[:5]}",
        )

    def test_corpus_is_nonempty(self) -> None:
        self.assertGreater(len(smoke.CORPUS), 50,
                           "Korpus ist zu klein — bitte erweitern.")
        # Sanity: jedes Item hat exakt 4 Felder
        # (role, label, placeholder, expected_key).
        for item in smoke.CORPUS:
            self.assertEqual(len(item), 4, f"bad corpus item: {item!r}")
            role, label, placeholder, expected = item
            self.assertIsInstance(role, str)
            self.assertIsInstance(label, str)
            self.assertIsInstance(placeholder, str)
            # expected darf None sein (negativer Fall) oder str (logical key)
            self.assertTrue(expected is None or isinstance(expected, str))


if __name__ == "__main__":
    unittest.main(verbosity=2)
