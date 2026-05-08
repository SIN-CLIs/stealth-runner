"""Generic ProviderAdapter fallback."""

from .base import ProviderAdapter


COMMANDS = {
    "click_next": "__CDP_CLICK_BUTTON__:Weiter",
    "click_element": "__CDP_CLICK_GENERIC__:{idx}",
    "fill_text": '''(function(v){
        var ta = document.querySelector(
            "textarea,input[type=text],input[type=number]");
        if(ta){
            var proto = ta.tagName === "TEXTAREA"
                ? window.HTMLTextAreaElement.prototype
                : window.HTMLInputElement.prototype;
            var nativeSetter = Object.getOwnPropertyDescriptor(proto,"value").set;
            if(nativeSetter) nativeSetter.call(ta, v); else ta.value = v;
            ta.dispatchEvent(new Event("input",{bubbles:true,cancelable:true}));
            ta.dispatchEvent(new Event("change",{bubbles:true,cancelable:true}));
        }
    })("{value}")''',
}

COMPLETION_MARKERS = [
    "vielen dank",
    "survey complete",
    "thank you for completing",
    "your response has been recorded",
    "zurück zur website",
    "gutgeschrieben",
]


class GenericAdapter(ProviderAdapter):
    """Fallback adapter for unknown providers."""

    def __init__(self):
        super().__init__(
            name="generic",
            url_patterns=[],
            commands=COMMANDS,
            completion_markers=COMPLETION_MARKERS,
        )
