"""Stealth injection — patches browser fingerprints before page scripts run.

Loads JS bundles from embedded scripts/ and injects them via
Page.addScriptToEvaluateOnNewDocument so they execute on every frame
prior to any page-owned JavaScript.
"""

from stealth_captcha.stealth.patches import StealthInjector, build_stealth_bundle

__all__ = ["StealthInjector", "build_stealth_bundle"]
