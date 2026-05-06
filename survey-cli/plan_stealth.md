# ✅ FIXED — 19 tests, LIVE-verified (navigator.webdriver === undefined confirmed)

**What was implemented**: 3-phase tab creation pipeline: `create_blank_tab()` (empty about:blank) → `inject_stealth_to_tab()` (12-module bundle via `Runtime.evaluate`) → `navigate_tab()` (navigate to survey URL AFTER stealth is active). Added `Page.addScriptToEvaluateOnNewDocument` for persistence across navigations. Stealth modules: navigator.webdriver, canvas fingerprint jitter, WebGL vendor/renderer spoof, navigator.plugins, audio context fingerprint, permissions API, chrome.runtime, hardwareConcurrency, userAgentData, screen.colorDepth, automation detection flags. 19 regression tests pass, LIVE-verified in production.

---

# Plan: P1 Fix — Zero Stealth Injection → 12-Module Stealth Bundle

## Problem
survey-cli creates NEW browser tabs for surveys via `Target.createTarget` but injects NO stealth overrides:
- `navigator.webdriver` = `true` (automation detected immediately)
- No canvas fingerprint randomization
- No WebGL vendor/renderer spoofing
- No plugin spoofing
- No automation flags removed

Manual survey works because Chrome profile already has stealth.

## Root Cause
`chrome.py` creates new tab, navigates to CPX URL — zero stealth injection between tab creation and navigation.

## Fix Strategy

### Source: stealth-captcha/stealth/injection.js

```javascript
// 12-module stealth bundle from stealth-captcha
// Modules: navigator.webdriver, navigator.plugins, navigator.languages,
//          canvas fingerprint, WebGL vendor/renderer, audio context,
//          permissions API, chrome.runtime, navigator.hardwareConcurrency,
//          userAgentData, screen.colorDepth, automation detection
```

### Injection Point

In `execute.py` — AFTER `Target.createTarget` but BEFORE page navigation:

```python
# execute.py:execute()
# 1. Create new tab via CDP
new_ws = self._create_survey_tab(target_ws_url)
# 2. Inject stealth BEFORE navigating to survey URL
self._inject_stealth(new_ws)
# 3. NOW navigate to survey URL
new_ws.send(json.dumps({
    "method": "Page.navigate",
    "params": {"url": survey_url}
}))
```

### Implementation: `_inject_stealth()`

```python
def _inject_stealth(self, ws: websocket.WebSocket) -> None:
    """Inject 12-module stealth bundle into new tab."""
    with open(PKG / "stealth" / "injection.js") as f:
        stealth_js = f.read()
    ws.send(json.dumps({
        "id": next(self._id_ctr),
        "method": "Runtime.evaluate",
        "params": {
            "expression": stealth_js,
            "returnByValue": False
        }
    }))
    resp = ws.recv()  # verify injection succeeded
```

### Fallback: Inline JS if file not found

```python
def _get_stealth_js(self) -> str:
    """Load stealth bundle or return inline fallback."""
    stealth_file = PKG / "stealth" / "injection.js"
    if stealth_file.exists():
        return stealth_file.read_text()
    # Inline minimal stealth (same as stealth-captcha fallback)
    return """
    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    window.navigator.chrome = {runtime: {}};
    """
```

## Files to Change

| File | Change | Risk |
|------|--------|------|
| `survey/execute.py` | Add `_inject_stealth()` method | Low |
| `survey/execute.py` | Call `_inject_stealth()` after tab creation, before navigation | Low |
| `survey/chrome.py` | Copy `stealth/injection.js` from stealth-captcha | Low |
| `survey/chrome.py` | Add `inject_stealth_tab()` helper | Low |
| `survey/execute.py` | Add `_create_survey_tab()` that returns WS with stealth | Medium — tab creation flow |

## Stealth Injection Order (Critical)

1. **Tab Created** (empty about:blank)
2. **Stealth JS injected** (sets overrides)
3. **Page.navigate to survey URL** (page loads with overrides ACTIVE)
4. **Page events fire** ( CDP `Page.loadEventFired`, etc. )

→ Stealth active BEFORE first byte of survey page loads.

## Tests to Add

```python
# tests/test_stealth.py (NEW)
class TestStealthInjection:
    def test_injects_navigator_webdriver_override()  # verify webdriver=false
    def test_injects_canvas_fingerprint_randomization()
    def test_injects_webgl_vendor_spoofing()
    def test_injects_plugins_spoofing()
    def test_injection_succeeds_before_navigation()
    def test_fallback_inline_js_when_file_missing()
    def test_stealth_persists_after_page_load()
```

## Verification

```bash
# Before: navigator.webdriver === true (detected immediately)
# After: navigator.webdriver === undefined (stealth active)
python3 -m survey run --mode loop --max 1 --debug
# Check CDP JS: window.navigator.webdriver
```

## Estimate

- **Effort**: 3-4h
- **Impact**: Prevents immediate detection by PureSpectrum, Cint, Samplicio
- **Risk**: Medium — stealth injection timing is critical (must be before page load)
