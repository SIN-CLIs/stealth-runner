"""Panel-Provider-Erkennung anhand von URL- und Text-Mustern (8 Provider)."""
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Final

@dataclass(frozen=True, slots=True)
class PanelRules:
    name: str
    url_patterns: tuple[str, ...]
    text_patterns: tuple[str, ...] = ()
    dq_markers: tuple[str, ...] = ()
    quality_traps: tuple[str, ...] = ()
    continue_labels: tuple[str, ...] = ()
    min_seconds_per_question: float = 2.5
    min_free_text_chars: int = 12
    extra_hints: tuple[str, ...] = ()

PANELS: Final[tuple[PanelRules, ...]] = (
    PanelRules(name="PureSpectrum", url_patterns=("purespectrum.io","pspmarket.com","ps-route.com","pssurveys.io"), text_patterns=("pure spectrum","purespectrum"), dq_markers=("we're sorry","you did not qualify","quota full","leider passen sie nicht","thank you for your interest"), quality_traps=("please select","attention check","if you are reading this","aufmerksamkeitstest"), continue_labels=("continue","next","weiter","submit"), min_seconds_per_question=3.0, min_free_text_chars=15, extra_hints=("Device-Verification: 5-15s warten.","Attention-Check: wörtliche Anweisung.","Freitext: min 15 Zeichen.")),
    PanelRules(name="Dynata", url_patterns=("dynata.com","researchnow.com","samplicio.us"), text_patterns=("dynata","research now"), dq_markers=("we apologize","you do not qualify","survey is full","quota has been reached"), quality_traps=("straight-lining","speeder","please rate the following","data quality"), continue_labels=("continue","next","weiter","fortfahren"), min_seconds_per_question=3.5, min_free_text_chars=20, extra_hints=("Straight-Lining: Antworten variieren.","Speeder: >3.5s pro Frage.","Freitext: min 20 Zeichen.")),
    PanelRules(name="Sapio", url_patterns=("sapioresearch.com","sapio-research.com","sapio-survey.com"), text_patterns=("sapio research","sapio survey"), dq_markers=("unfortunately you do not qualify","survey quota filled","no further participation"), quality_traps=("red herring","trap question","consistency check","please ignore this"), continue_labels=("continue","next","submit","weiter"), min_seconds_per_question=3.0, min_free_text_chars=12, extra_hints=("Consistency-Checks: gleiche Frage Runde 1+3.","Brand-Trap: 'Nie gehört'.")),
    PanelRules(name="Cint", url_patterns=("cint.com","cint-survey.com","lifepointspanel.com","p.cint.link"), text_patterns=("cint","lifepoints"), dq_markers=("we couldn't find a survey","we're unable to complete","better luck next time","aktuell keine passende"), quality_traps=("please select all that apply","select the option"), continue_labels=("continue","next","submit"), min_seconds_per_question=2.5, min_free_text_chars=10, extra_hints=("Redirect: 'Redirecting…' 3-8s warten.","Multi-Select: nie 'Keine' mit anderen.")),
    PanelRules(name="Lucid", url_patterns=("lucidhq.com","lucidholdings.com","samplicio.us","fulcrum.rpanel.io"), text_patterns=("lucid marketplace","fulcrum"), dq_markers=("we couldn't match you","survey has been closed","please try again later"), quality_traps=("for quality control","please answer honestly"), continue_labels=("continue","next","weiter"), min_seconds_per_question=3.0, min_free_text_chars=15, extra_hints=("Fulcrum-Router: mehrfache Redirects.")),
    PanelRules(name="HeyPiggy", url_patterns=("heypiggy.com",), text_patterns=("heypiggy","deine verfuegbaren erhebungen"), dq_markers=("diese umfrage ist leider nicht mehr verfuegbar","du wurdest leider nicht qualifiziert","umfrage abgebrochen"), continue_labels=("weiter","start","teilnehmen"), min_seconds_per_question=2.0, min_free_text_chars=10, extra_hints=("Dashboard: höchster EUR/Min zuerst.","Nach Abschluss: 5 Sterne.")),
)

def _build_patterns(attr: str) -> dict[str, re.Pattern[str]]:
    return {p.name: re.compile("|".join(re.escape(f) for f in getattr(p, attr, ())), re.IGNORECASE) for p in PANELS if getattr(p, attr, ())}

_URL_PATTERNS: Final = _build_patterns("url_patterns")
_TEXT_PATTERNS: Final = _build_patterns("text_patterns")

def detect_panel(url: str = "", body_text: str = "") -> PanelRules | None:
    url, body_text = url or "", body_text or ""
    for panel in PANELS:
        pat = _URL_PATTERNS.get(panel.name)
        if pat and pat.search(url): return panel
    if body_text:
        snippet = body_text[:2000].lower()
        for panel in PANELS:
            pat = _TEXT_PATTERNS.get(panel.name)
            if pat and pat.search(snippet): return panel
    return None

def detect_quality_trap(panel: PanelRules | None, body_text: str) -> str | None:
    if not panel or not panel.quality_traps or not body_text: return None
    low = body_text.lower()
    for marker in panel.quality_traps:
        if marker.lower() in low: return marker
    return None

def detect_panel_dq(panel: PanelRules | None, body_text: str) -> str | None:
    if not panel or not panel.dq_markers or not body_text: return None
    low = body_text.lower()
    for marker in panel.dq_markers:
        if marker.lower() in low: return marker
    return None

def build_panel_prompt_block(panel: PanelRules | None, body_text: str = "") -> str:
    if panel is None: return ""
    lines = [f"===== PANEL: {panel.name} ====="]
    trap = detect_quality_trap(panel, body_text)
    if trap: lines.append(f"ATTENTION-CHECK: '{trap}' — wörtliche Anweisung befolgen.")
    dq = detect_panel_dq(panel, body_text)
    if dq: lines.append(f"DQ-SIGNAL: '{dq}' — disqualifiziert markieren.")
    lines.append(f"Regeln: min {panel.min_seconds_per_question:.1f}s, Freitext {panel.min_free_text_chars} Zeichen, Labels: {', '.join(panel.continue_labels)}")
    if panel.extra_hints:
        for hint in panel.extra_hints: lines.append(f" - {hint}")
    return "\n".join(lines)
