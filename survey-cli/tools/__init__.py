"""
================================================================================
SURVEY TOOLS — Atomare, eingefrorene Tools
================================================================================

REGEL: Diese Tools sind FROZEN. Nicht aendern wenn sie funktionieren!

Agent soll nur aufrufen:
    from tools import click, fill, snapshot, detect_completion, close_modals
    from tools import find_new_tab, get_tab_ids, select_language, AntiStuck

Agent soll NICHT:
    - Tools modifizieren
    - Neue Logik in Tools hinzufuegen
    - Flows neu implementieren
================================================================================
"""

from .tool_click_angular import click
from .tool_select_language import select_language
from .tool_fill_input import fill
from .tool_find_new_tab import find_new_tab, get_tab_ids, get_all_tabs, find_tab_by_url
from .tool_close_modals import close_modals
from .tool_detect_completion import detect as detect_completion
from .tool_snapshot import snapshot, find_submit, find_unfilled
from .tool_anti_stuck import AntiStuck, check_stuck
from .tool_solve_captcha import solve as solve_captcha
from .tool_solve_drag_puzzle import solve as solve_drag_puzzle
from .tool_scan_dashboard import scan as scan_dashboard, get_next_survey
from .tool_universal_answer import answer as universal_answer

__all__ = [
    "click",
    "select_language",
    "fill",
    "find_new_tab",
    "get_tab_ids",
    "get_all_tabs",
    "find_tab_by_url",
    "close_modals",
    "detect_completion",
    "snapshot",
    "find_submit",
    "find_unfilled",
    "AntiStuck",
    "check_stuck",
    "solve_captcha",
    "solve_drag_puzzle",
    "scan_dashboard",
    "get_next_survey",
    "universal_answer",
]
