"""HeyPiggy provider adapter — first-class registry entry.

HeyPiggy is a German survey aggregator with a dashboard login, survey queue,
and cash-out flow. This adapter provides HeyPiggy-specific selectors and
completion detection instead of relying on GenericAdapter fallback heuristics.

ARCHITEKTUR:
- Login: username/password form, optional 2FA detection, MFA-skip
- Survey queue: card-based layout with survey items
- Completion markers: German + English phrases for completed/screen-out/quota
- Payout: balance display + cash-out button

BANNED METHODS — NIEMALS VERWENDEN:
x playstealth launch
x webauto-nodriver — ABSOLUT BANNED
x cua-driver click (raw index)
x --remote-allow-origins=* (ohne Quotes)
x /tmp/heypiggy-bot (fixed profile)
x Hardcoded PIDs
x pkill -f "Google Chrome"
x killall Google Chrome
x skylight-cli click --element-index
"""

from typing import Dict, List

from .base import CompletionState, ProviderAdapter

# HeyPiggy-specific completion markers (German + English)
COMPLETION_MARKERS = [
    "survey completed",
    "umfrage abgeschlossen",
    "thank you for your time",
    "vielen dank für ihre teilnahme",
    "gutgeschrieben",
    "punkte gutgeschrieben",
    "erfolgreich abgeschlossen",
    "ihre antworten wurden gespeichert",
]

# Screen-out / disqualification markers
SCREEN_OUT_MARKERS = [
    "you don't qualify",
    "you do not qualify",
    "sie qualifizieren sich nicht",
    "leider passen sie nicht",
    "quota full",
    "quote voll",
    "kontingent erschöpft",
    "this survey is no longer available",
    "diese umfrage ist nicht mehr verfügbar",
    "umfrage geschlossen",
    "survey closed",
    "disqualified",
    "disqualifiziert",
    "nicht für diese umfrage qualifiziert",
    "thank you for your interest",
]

# CDP/JS command templates for HeyPiggy dashboard and surveys
COMMANDS = {
    # Next button in surveys (multiple fallback selectors)
    "click_next": '''(function(){
        var btn = document.querySelector(
            'button[type="submit"], button.btn-next, button.next-btn, ' +
            '.survey-next-button, [data-action="next"], button:contains("Weiter"), ' +
            'button:contains("Next"), input[type="submit"]'
        );
        if(btn && !btn.disabled) { btn.click(); return "clicked"; }
        return "not found";
    })()''',

    # Radio/checkbox element click by index
    "click_element": '''(function(idx){
        var els = document.querySelectorAll('input[type="radio"], input[type="checkbox"]');
        if(els[idx]) { els[idx].click(); return "clicked:" + idx; }
        return "not found";
    })({idx})''',

    # Login form submit
    "login_submit": '''(function(){
        var form = document.querySelector('form[action*="login"], form.login-form, #login-form');
        if(form) { form.submit(); return "submitted"; }
        var btn = document.querySelector('button[type="submit"], input[type="submit"]');
        if(btn) { btn.click(); return "clicked"; }
        return "not found";
    })()''',

    # Survey card click (dashboard survey selection)
    "survey_card_click": '''(function(idx){
        var cards = document.querySelectorAll(
            '.survey-card, .survey-item, .available-survey, ' +
            '[data-survey-id], .survey-list-item, .dashboard-survey'
        );
        if(cards[idx]) { cards[idx].click(); return "clicked:" + idx; }
        return "not found";
    })({idx})''',

    # Cash-out button
    "cashout_click": '''(function(){
        var btn = document.querySelector(
            'button.cashout, button.payout, [data-action="cashout"], ' +
            'a[href*="cashout"], a[href*="payout"], .withdraw-btn, ' +
            'button:contains("Auszahlen"), button:contains("Cash Out")'
        );
        if(btn && !btn.disabled) { btn.click(); return "clicked"; }
        return "not found";
    })()''',

    # Fill text input (username, password, text fields)
    "fill_text": '''(function(selector, value){
        var el = document.querySelector(selector);
        if(el) {
            var proto = el.tagName === "TEXTAREA"
                ? window.HTMLTextAreaElement.prototype
                : window.HTMLInputElement.prototype;
            var nativeSetter = Object.getOwnPropertyDescriptor(proto, "value").set;
            if(nativeSetter) nativeSetter.call(el, value);
            else el.value = value;
            el.dispatchEvent(new Event("input", {bubbles: true}));
            el.dispatchEvent(new Event("change", {bubbles: true}));
            el.dispatchEvent(new Event("blur", {bubbles: true}));
            return "filled";
        }
        return "not found";
    })("{selector}", "{value}")''',
}


class HeyPiggyAdapter(ProviderAdapter):
    """HeyPiggy adapter for dashboard login, survey queue, and cash-out flows."""

    def __init__(self):
        super().__init__(
            name="heypiggy",
            url_patterns=[
                "heypiggy.com",
                "heypiggy.de",
                "app.heypiggy",
                "dashboard.heypiggy",
            ],
            commands=COMMANDS,
            completion_markers=COMPLETION_MARKERS,
            screen_out_markers=SCREEN_OUT_MARKERS,
        )

    def detect_completion(self, text: str, url: str = "") -> CompletionState:
        """Classify HeyPiggy page text into completion states.

        Priority order:
        1. Completed markers (success)
        2. Screen-out markers (disqualified/quota/closed)
        3. Blocked markers (captcha/bot detection)
        4. Running (still in survey)
        """
        haystack = f"{url} {text}".lower()

        # Check completion first
        for marker in self.completion_markers:
            if marker.lower() in haystack:
                return CompletionState("completed", marker)

        # Check screen-out/disqualification
        for marker in self.screen_out_markers:
            if marker.lower() in haystack:
                return CompletionState("screen_out", marker)

        # Check blocked (captcha, bot detection)
        for marker in self.blocked_markers:
            if marker.lower() in haystack:
                return CompletionState("blocked", marker)

        return CompletionState("running", "")

    def get_login_flow(self) -> List[Dict[str, str]]:
        """Return HeyPiggy dashboard login flow steps.

        Steps:
        1. Fill username field
        2. Fill password field
        3. Submit login form
        4. Detect 2FA prompt (if present)
        5. Skip MFA if possible
        """
        return [
            {
                "step": "fill_username",
                "selector": 'input[name="username"], input[name="email"], '
                           'input[type="email"], #username, #email',
                "action": "fill",
                "env_var": "HEYPIGGY_USERNAME",
            },
            {
                "step": "fill_password",
                "selector": 'input[name="password"], input[type="password"], #password',
                "action": "fill",
                "env_var": "HEYPIGGY_PASSWORD",
            },
            {
                "step": "submit_login",
                "selector": 'button[type="submit"], input[type="submit"], '
                           '.login-btn, #login-button',
                "action": "click",
            },
            {
                "step": "detect_2fa",
                "selector": 'input[name="otp"], input[name="2fa"], '
                           'input[name="totp"], .mfa-input, #otp-input',
                "action": "detect",
                "optional": True,
            },
            {
                "step": "skip_mfa",
                "selector": 'a[href*="skip"], button.skip-mfa, '
                           '.skip-2fa, [data-action="skip-mfa"]',
                "action": "click",
                "optional": True,
            },
        ]

    def get_survey_queue_selector(self) -> str:
        """Return CSS selector for HeyPiggy survey queue enumeration.

        Targets survey cards/items on the dashboard for iteration.
        """
        return (
            ".survey-card, .survey-item, .available-survey, "
            "[data-survey-id], .survey-list-item, .dashboard-survey, "
            ".survey-container .survey, ul.surveys li, .survey-row"
        )

    def get_payout_selector(self) -> str:
        """Return CSS selector for HeyPiggy cash-out and balance verification.

        Targets:
        - Balance display element
        - Cash-out/payout button
        """
        return (
            ".balance, .account-balance, .points-balance, .current-balance, "
            "[data-balance], #balance-display, "
            "button.cashout, button.payout, a[href*='cashout'], "
            "a[href*='payout'], .withdraw-btn, [data-action='cashout']"
        )
