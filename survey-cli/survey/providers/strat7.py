"""Strat7 Audiences provider patterns.

Key patterns:
  - .bsbutton grid for consent/targeting
  - input[type=radio] for single choice
  - .bsbutton:not([disabled]) for page advance
"""

COMPLETION_MARKERS = [
    "umfrage beendet", "vielen dank", "gutgeschrieben",
]

COMMANDS = {
    "click_next": 'document.querySelector(".bsbutton:not([disabled])").click()',
    "click_element": 'document.querySelectorAll("input[type=radio]")[{idx}].click()',
}
