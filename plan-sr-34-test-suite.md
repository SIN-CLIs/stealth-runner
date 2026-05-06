# Plan SR-34: Survey Flow Test Suite

## Overview
Build a comprehensive test suite for survey automation. Currently 0 tests exist for the survey flow.

## Test Structure

```
tests/
├── conftest.py                     # Shared fixtures
├── test_provider_detect.py         # 6 tests
├── test_answer_patterns.py         # 5 tests
├── test_persona.py                 # 6 tests
├── test_e2e_survey.py              # 1 E2E test
└── fixtures/
    ├── mock_qualtrics.html         # 3-question Qualtrics mock
    └── mock_tolunastart.html       # 3-question TolunaStart mock
```

## Mock HTML Fixture (Qualtrics)

```html
<!-- tests/fixtures/mock_qualtrics.html -->
<!DOCTYPE html>
<html>
<body>
<div class="QuestionText">Sind Sie...</div>
<label><input type="radio" name="gender" value="1"> Weiblich</label>
<label><input type="radio" name="gender" value="2"> Männlich</label>
<label><input type="radio" name="gender" value="3"> Divers</label>
<button class="NextButton Button">Weiter →</button>

<div class="QuestionText" style="display:none">Alter angeben</div>
<div style="display:none">
  <label><input type="radio" name="age" value="1"> 20-25</label>
  <label><input type="radio" name="age" value="4"> 31-35</label>
  <label><input type="radio" name="age" value="5"> 36-40</label>
  <button class="NextButton Button">Weiter →</button>
</div>

<div class="QuestionText" style="display:none">Bundesland</div>
<div style="display:none">
  <label><input type="radio" name="state" value="1"> Bayern</label>
  <label><input type="radio" name="state" value="2"> Berlin</label>
  <label><input type="radio" name="state" value="3"> Hamburg</label>
  <button class="NextButton Button">Weiter →</button>
</div>

<div id="complete" style="display:none">
  Zurück zur Website +0.38 EUR gutgeschrieben
</div>
</body>
</html>
```

## Test Cases

### test_provider_detect.py
```python
def test_qualtrics_url():
    assert detect_provider("https://eu.qualtrics.com/jfe/form/SV_xxx") == "qualtrics"

def test_tolunastart_url():
    assert detect_provider("https://survey.tolunastart.com/xxx") == "tolunastart"

def test_purespectrum_url():
    assert detect_provider("https://screener.purespectrum.com/xxx") == "purespectrum"

def test_cpx_redirect():
    assert detect_provider("https://click.cpx-research.com/?k=xxx") == "unknown"
    # Should wait for redirect

def test_unknown_url():
    assert detect_provider("https://example.com") == "unknown"
```

### test_persona.py
```python
def test_age_from_dob():
    p = Profile.load("jeremy_schulze")
    assert p.age == 32  # born 1993-11-13

def test_age_bracket():
    assert p._get_age_bracket() == "31 bis 35"

def test_gender_resolve():
    assert p.gender_label == "Männlich"

def test_education_resolve():
    assert "Abitur" in p.education_label  # NOT Universität

def test_state_resolve():
    assert p.resolve_answer("Bundesland", ["Bayern","Berlin","Hamburg"]) == 1
```

### test_e2e_survey.py
```python
def test_qualtrics_3_question_flow():
    """End-to-end: Serve mock HTML, open in Chrome CDP, answer 3 questions, verify completion."""
    # 1. Start local HTTP server with mock_qualtrics.html
    # 2. Chrome --headless → Target.createTarget("http://localhost:8765/mock_qualtrics.html")
    # 3. CDP Runtime.evaluate → answer 3 questions
    # 4. Verify "Zurück zur Website" appears
    # 5. Assert completion detected
```

## Implementation: ~3h
