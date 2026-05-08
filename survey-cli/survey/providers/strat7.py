"""Strat7 Audiences provider patterns.

WARUM: Strat7 nutzt ein proprietäres Button-Grid (.bsbutton) für Consent
und Targeting. Ohne Provider-spezifische Commands würden generische
Selektoren fehlschlagen (z.B. button statt .bsbutton).
Dieses Modul liefert die NEMO-kompatiblen Actions für Strat7.

ARCHITEKTUR: Statische Command-Map (COMMANDS) + Detection-Heuristik.
Commands: click_next (bsbutton:not([disabled])), click_element (radio).
Completion-Marker: "umfrage beendet", "vielen dank", "gutgeschrieben".
Kein State, keine Klassen — reine Datenstruktur.

BANNED METHODS — NIEMALS VERWENDEN:
❌ playstealth launch
❌ webauto-nodriver — ABSOLUT BANNED
❌ cua-driver click (raw index)
❌ --remote-allow-origins=* (ohne Quotes)
❌ /tmp/heypiggy-bot (fixed profile)
❌ Hardcoded PIDs
❌ pkill -f "Google Chrome"
❌ killall Google Chrome
❌ skylight-cli click --element-index
"""

COMPLETION_MARKERS = [
    "umfrage beendet", "vielen dank", "gutgeschrieben",
]

COMMANDS = {
    "click_next": 'document.querySelector(".bsbutton:not([disabled])").click()',
    "click_element": 'document.querySelectorAll("input[type=radio]")[{idx}].click()',
}


from .base import ProviderAdapter


class Strat7Adapter(ProviderAdapter):
    """Strat7 adapter for .bsbutton and radio grids."""

    def __init__(self):
        super().__init__(
            name="strat7",
            url_patterns=["strat7", "strat7audiences.com", "bsbutton"],
            commands=COMMANDS,
            completion_markers=COMPLETION_MARKERS,
        )
