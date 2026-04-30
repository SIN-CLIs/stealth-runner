import sys
sys.path.insert(0, '/Users/jeremy/dev/stealth-runner')

from sin_survey_core import detect_panel, extract_eur_from_text, classify_error

def test_detect_panel_heypiggy():
    panel = detect_panel("https://heypiggy.com/?page=dashboard", "")
    assert panel is not None
    assert panel.name == "HeyPiggy"

def test_detect_panel_purespectrum():
    panel = detect_panel("https://s.purespectrum.io/abc", "")
    assert panel is not None
    assert panel.name == "PureSpectrum"

def test_detect_panel_dynata():
    panel = detect_panel("https://panel.dynata.com/survey", "")
    assert panel is not None
    assert panel.name == "Dynata"

def test_detect_panel_cint():
    panel = detect_panel("https://p.cint.link/survey", "")
    assert panel is not None
    assert panel.name == "Cint"

def test_detect_panel_unknown():
    panel = detect_panel("https://unknown.com", "")
    assert panel is None

def test_extract_eur_german():
    eur = extract_eur_from_text("Verdienst: 1.71 €")
    assert eur == 1.71

def test_extract_eur_english():
    eur = extract_eur_from_text("You earned EUR=0.50")
    assert eur == 0.50

def test_extract_eur_suffix():
    eur = extract_eur_from_text("Reward: 124.00 EUR")
    assert eur == 124.00

def test_extract_eur_none():
    eur = extract_eur_from_text("No reward available")
    assert eur == 0.0

def test_classify_error_disqualified():
    error = classify_error("We're sorry, you did not qualify for this survey")
    assert error == "disqualified"

def test_classify_error_quota_full():
    error = classify_error("This survey is full and has been closed")
    assert error == "quota_full"

def test_classify_error_unknown():
    error = classify_error("Something random happened")
    assert error == "unknown"

if __name__ == "__main__":
    test_detect_panel_heypiggy()
    test_detect_panel_purespectrum()
    test_detect_panel_dynata()
    test_detect_panel_cint()
    test_detect_panel_unknown()
    test_extract_eur_german()
    test_extract_eur_english()
    test_extract_eur_suffix()
    test_extract_eur_none()
    test_classify_error_disqualified()
    test_classify_error_quota_full()
    test_classify_error_unknown()
    print("✅ ALL 12 sin_survey_core tests PASSED")
