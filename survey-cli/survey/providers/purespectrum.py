"""PureSpectrum provider patterns — CAPTCHA blocked.

All current PureSpectrum surveys show a base64 PNG text CAPTCHA.
This module is a placeholder until OCR solver is implemented.
"""

COMPLETION_MARKERS = [
    "zurück zur website", "vielen dank",
]

COMMANDS = {
    "click_next": 'document.querySelector("button[type=submit]").click()',
}

# Captcha patterns
CAPTCHA_SELECTORS = [
    "#captcha img", ".captcha-image img",
    "img[src*=captcha]", "img[src*=base64]",
]

CAPTCHA_INPUT_SELECTORS = [
    "#captcha input", ".captcha-input input",
    "input[name=captcha]", "input[placeholder*=Code]",
]
