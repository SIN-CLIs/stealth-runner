"""Tests für sin_survey_core – Panel, EUR, Errors."""
from __future__ import annotations
import pytest
from sin_survey_core.panels import detect_panel, detect_panel_dq, detect_quality_trap, build_panel_prompt_block, PANELS
from sin_survey_core.rewards import extract_eur_from_text, extract_earnings_summary, EarningsSummary
from sin_survey_core.errors import classify_error, ErrorCategory, ErrorInfo

class TestDetectPanel:
    def test_heypiggy(self) -> None: assert detect_panel("https://heypiggy.com/?page=dashboard","").name == "HeyPiggy"
    def test_purespectrum(self) -> None: assert detect_panel("https://s.purespectrum.io/abc","").name == "PureSpectrum"
    def test_dynata(self) -> None: assert detect_panel("https://panel.dynata.com/survey","").name == "Dynata"
    def test_cint(self) -> None: assert detect_panel("https://p.cint.link/survey","").name == "Cint"
    def test_unknown(self) -> None: assert detect_panel("https://unknown.com","") is None
    def test_sapio_body(self) -> None: assert detect_panel("","Sapio Research survey").name == "Sapio"
    def test_lucid_body(self) -> None: assert detect_panel("","Lucid Marketplace").name == "Lucid"
    def test_panel_count(self) -> None: assert len(PANELS) == 8

class TestDetectPanelDQ:
    def test_dq_detected(self) -> None:
        p = detect_panel("https://heypiggy.com","")
        assert detect_panel_dq(p, "Diese Umfrage ist leider nicht mehr verfügbar.") is not None
    def test_no_dq(self) -> None:
        p = detect_panel("https://heypiggy.com","")
        assert detect_panel_dq(p, "Willkommen!") is None

class TestDetectQualityTrap:
    def test_trap_detected(self) -> None:
        p = detect_panel("https://s.purespectrum.io","")
        assert detect_quality_trap(p, "Attention check: please select blue") is not None
    def test_no_trap(self) -> None:
        p = detect_panel("https://panel.dynata.com","")
        assert detect_quality_trap(p, "What is your age?") is None

class TestBuildPanelPromptBlock:
    def test_valid_panel(self) -> None:
        p = detect_panel("https://heypiggy.com","")
        block = build_panel_prompt_block(p)
        assert "HeyPiggy" in block and "Regeln:" in block
    def test_none_panel(self) -> None: assert build_panel_prompt_block(None) == ""
    def test_dq_in_block(self) -> None:
        p = detect_panel("https://heypiggy.com","")
        assert "DQ-SIGNAL" in build_panel_prompt_block(p, "Du wurdest leider nicht qualifiziert")

class TestExtractEUR:
    def test_german(self) -> None: assert extract_eur_from_text("Verdienst: 1.71 €") == 1.71
    def test_english(self) -> None: assert extract_eur_from_text("EUR=0.50") == 0.50
    def test_suffix(self) -> None: assert extract_eur_from_text("124.00 EUR") == 124.00
    def test_none(self) -> None: assert extract_eur_from_text("No reward") == 0.0
    def test_empty(self) -> None: assert extract_eur_from_text("") == 0.0
    def test_summary(self) -> None:
        s = extract_earnings_summary("4,50 €")
        assert isinstance(s, EarningsSummary) and s.eur == 4.50

class TestClassifyError:
    def test_disqualified(self) -> None:
        r = classify_error("you did not qualify"); assert r is not None and r.category == ErrorCategory.DISQUALIFIED
    def test_quota_full(self) -> None:
        r = classify_error("quota full"); assert r is not None and r.category == ErrorCategory.QUOTA_FULL
    def test_attention(self) -> None:
        r = classify_error("attention check failed"); assert r is not None and r.category == ErrorCategory.ATTENTION_FAILED
    def test_not_found(self) -> None:
        r = classify_error("survey not found"); assert r is not None and r.category == ErrorCategory.NOT_FOUND
    def test_unknown(self) -> None: assert classify_error("random") is None
    def test_empty(self) -> None: assert classify_error("") is None
    def test_matched_marker(self) -> None:
        r = classify_error("did not qualify"); assert r is not None and "did not qualify" in r.matched_marker
    def test_frozen(self) -> None:
        r = classify_error("quota full"); assert r is not None
        with pytest.raises(Exception): r.category = ErrorCategory.NOT_FOUND
