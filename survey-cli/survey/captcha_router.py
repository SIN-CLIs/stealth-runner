"""================================================================================
CAPTCHA ROUTER — Erkennung + Solver-Routing als eigene Pipeline-Stufe
================================================================================

ZWECK
-----
Captchas sind KEIN normales Scan-Problem. Sie sind absichtlich obfuskiert:
eigene iframes, fremde Origins, randomisierte Klassen, Token-basierte
Verifikation. Wer Captcha-Detection in den allgemeinen Element-Scanner stopft
(``isCaptcha = cls.includes('captcha')``), verliert. Beweis: ``snapshot.py``
findet PureSpectrum-Captchas nur, wenn deren Klasse zufällig "NxtBtn" heißt.

Stattdessen ist Captcha-Erkennung eine eigene Stufe VOR oder PARALLEL zum
regulären Scan:

  scan_universal()  ──┐
                      ├──► captcha_router.detect()  ──► (type | None)
                      │           │
                      │           ▼
                      │     captcha_router.solve(type)
                      │           │
                      ▼           ▼
                  elements   captcha_state
                      │           │
                      └────► continue


DETECTION-PRIORITÄT
-------------------
1. iframe-URL-Patterns (höchste Sicherheit, keine False Positives):
     - hCaptcha          ``hcaptcha.com/captcha/``
     - reCAPTCHA v2/v3   ``google.com/recaptcha/`` / ``recaptcha.net``
     - Cloudflare Turnstile  ``challenges.cloudflare.com/turnstile``
     - GeeTest v4        ``api.geetest.com/`` / ``static.geetest.com``
     - Lemin             ``lemin.io``
     - DataDome          ``geo.captcha-delivery.com``
     - PerimeterX        ``captcha.px-cdn.net``

2. DOM-Signaturen NUR als Fallback wenn iframe-Detection nichts liefert:
     - Angular CDK drag-drop puzzle: ``.cdk-drop-list .cdk-drag`` + Text
       "Bitte legen Sie die Zahl X" (PureSpectrum, Strat7)
     - Visual-Text-Captcha: ``<img alt="Q3333S">`` mit 4–6-stelligem
       Zeichen-Alt (PureSpectrum eigenbau)

3. Network-Heuristik (optional, nur wenn 1+2 negativ und Loop steht):
     - Subrequest auf ``/captcha/`` oder ``/challenge/`` via
       ``Network.requestWillBeSent``-Event in den letzten N Sekunden.


SOLVER-INTERFACE
----------------
Jeder Solver implementiert ``solve(cdp, frame_info) -> CaptchaResult``.

  CaptchaResult:
    solved:        bool
    captcha_type:  str
    token:         str          (für API-basierte Captchas)
    elapsed_ms:    float
    reason:        str

Solver SIND HIER NICHT IMPLEMENTIERT. Sie leben in ``stealth-captcha/``
(separates Package). Der Router IMPORTIERT sie nur und delegiert. Wenn ein
Solver fehlt → ``CaptchaResult(solved=False, reason="no_solver_for_type")``.


WARUM EIGENES MODUL?
--------------------
- LangGraph hat einen ``captcha_node``, der GENAU diesen Router ruft.
- ``ScanResult.captcha_frames`` (aus cdp_universal) ist nur eine Hint-Liste —
  Routing-Entscheidung bleibt hier.
- Wenn ein Solver fehlschlägt → klare Eskalation (z. B. 2captcha-Fallback
  oder Manual-Mode).


PUBLIC API
----------
::

    router = CaptchaRouter(cdp)

    router.detect(scan_result)         -> CaptchaDetection | None
    router.solve(detection)            -> CaptchaResult
    router.detect_and_solve(scan_result) -> CaptchaResult | None


BANNED
------
- KEIN Captcha-Sniffing im allgemeinen Element-Scanner
- KEINE Provider-spezifischen "isCaptcha = cls.includes('captcha')" Heuristiken
================================================================================
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from .cdp_client import CDPConnection
from .cdp_universal import ScanResult


# Mapping iframe-URL-Substring → Captcha-Typ. Erweiterung NUR hier — niemals
# in ``cdp_universal``.
IFRAME_URL_TO_TYPE: tuple[tuple[str, str], ...] = (
    ("hcaptcha.com", "hcaptcha"),
    ("google.com/recaptcha", "recaptcha"),
    ("recaptcha.net", "recaptcha"),
    ("challenges.cloudflare.com/turnstile", "turnstile"),
    ("challenges.cloudflare.com", "turnstile"),
    ("api.geetest.com", "geetest_v4"),
    ("static.geetest.com", "geetest_v4"),
    ("lemin.io", "lemin"),
    ("geo.captcha-delivery.com", "datadome"),
    ("captcha.px-cdn.net", "perimeterx"),
)


@dataclass
class CaptchaDetection:
    captcha_type: str
    frame_id: str = ""
    frame_url: str = ""
    dom_hint: str = ""
    """Bei DOM-basierter Detection: kurzer Beschreibungs-String."""


@dataclass
class CaptchaResult:
    solved: bool
    captcha_type: str = ""
    token: str = ""
    elapsed_ms: float = 0.0
    reason: str = "ok"
    extra: dict[str, Any] = field(default_factory=dict)


# ── DOM-Signatur-Checks (Fallback wenn keine iframe-URL passt) ─────────────


def _check_angular_drag_puzzle(cdp: CDPConnection) -> CaptchaDetection | None:
    """PureSpectrum/Strat7: ``.cdk-drop-list`` mit Text "Bitte legen Sie ..."."""
    expr = (
        "(function(){"
        "var drop=document.querySelector('.cdk-drop-list,.drop-zone');"
        "if(!drop) return JSON.stringify({found:false});"
        "var text=(document.body.innerText||'').toLowerCase();"
        "var match=text.match(/zahl\\s*(\\d+)|number\\s*(\\d+)/);"
        "if(!match) return JSON.stringify({found:false});"
        "return JSON.stringify({found:true,target:match[1]||match[2]});"
        "})()"
    )
    resp = cdp.call_result("Runtime.evaluate", {"expression": expr})
    raw = resp.get("result", {}).get("value", "{}")
    try:
        d = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if d.get("found"):
        return CaptchaDetection(
            captcha_type="angular_drag_drop",
            dom_hint=f"target={d.get('target', '?')}",
        )
    return None


def _check_visual_text_captcha(cdp: CDPConnection) -> CaptchaDetection | None:
    """PureSpectrum eigenbau: ``<img alt="Q3333S">`` 4–6 Char Alt + textbox."""
    expr = (
        "(function(){"
        "var imgs=document.querySelectorAll('img[alt]');"
        "for(var i=0;i<imgs.length;i++){"
        "var alt=imgs[i].getAttribute('alt')||'';"
        "if(/^[A-Z0-9]{4,6}$/.test(alt)){"
        "var rect=imgs[i].getBoundingClientRect();"
        "if(rect.width>40&&rect.height>15){"
        "return JSON.stringify({found:true,alt:alt});"
        "}}}"
        "return JSON.stringify({found:false});"
        "})()"
    )
    resp = cdp.call_result("Runtime.evaluate", {"expression": expr})
    raw = resp.get("result", {}).get("value", "{}")
    try:
        d = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if d.get("found"):
        return CaptchaDetection(
            captcha_type="visual_text",
            dom_hint=f"alt={d.get('alt', '')}",
        )
    return None


# ── Solver-Imports — lazy, damit fehlende Solver nicht den Import killen ──


def _solver_for(captcha_type: str):
    """Importiert den passenden Solver lazy. Returns callable or None.

    Solver-Convention: ``def solve(cdp, detection) -> CaptchaResult``.

    Die echten Solver leben in ``stealth-captcha/``. Wer einen neuen
    Captcha-Typ unterstützen will, fügt:

      1) Einen Eintrag in ``IFRAME_URL_TO_TYPE`` oder einen DOM-Check oben.
      2) Ein Solver-Modul in ``stealth_captcha/solver/<type>.py`` mit der
         Signatur ``def solve(cdp, detection) -> CaptchaResult``.
      3) Einen Mapping-Eintrag hier unten.
    """
    if captcha_type == "angular_drag_drop":
        try:
            from stealth_captcha.solver.drag_drop_angular import solve  # noqa
            return solve
        except Exception:
            return None
    if captcha_type == "hcaptcha":
        try:
            from stealth_captcha.solver.hcaptcha import solve  # noqa
            return solve
        except Exception:
            return None
    if captcha_type == "recaptcha":
        try:
            from stealth_captcha.solver.recaptcha import solve  # noqa
            return solve
        except Exception:
            return None
    if captcha_type == "turnstile":
        try:
            from stealth_captcha.solver.turnstile import solve  # noqa
            return solve
        except Exception:
            return None
    if captcha_type == "visual_text":
        try:
            from stealth_captcha.solver.visual_text import solve  # noqa
            return solve
        except Exception:
            return None
    return None


class CaptchaRouter:
    """Erkennt und löst Captchas — Single Entry Point für LangGraph-Nodes."""

    def __init__(self, cdp: CDPConnection):
        self.cdp = cdp

    def detect(self, scan_result: ScanResult) -> CaptchaDetection | None:
        """Versucht Detection in folgender Reihenfolge:

          1) iframe-URL aus ``scan_result.captcha_frames``
          2) Angular drag-drop puzzle DOM-Signatur
          3) Visual-Text-Captcha DOM-Signatur

        Returns None wenn nichts gefunden.
        """
        # 1) iframe-URL Mapping
        for fr in scan_result.captcha_frames:
            url_low = fr["url"].lower()
            for hint, ctype in IFRAME_URL_TO_TYPE:
                if hint in url_low:
                    return CaptchaDetection(
                        captcha_type=ctype,
                        frame_id=fr["frame_id"],
                        frame_url=fr["url"],
                    )

        # 2) Angular CDK drag-drop
        drag = _check_angular_drag_puzzle(self.cdp)
        if drag:
            return drag

        # 3) Visual-Text-Captcha
        visual = _check_visual_text_captcha(self.cdp)
        if visual:
            return visual

        return None

    def solve(self, detection: CaptchaDetection) -> CaptchaResult:
        t0 = time.time()
        solver = _solver_for(detection.captcha_type)
        if solver is None:
            return CaptchaResult(
                solved=False,
                captcha_type=detection.captcha_type,
                reason="no_solver_for_type",
                elapsed_ms=(time.time() - t0) * 1000.0,
            )
        try:
            result: CaptchaResult = solver(self.cdp, detection)
        except Exception as e:
            return CaptchaResult(
                solved=False,
                captcha_type=detection.captcha_type,
                reason=f"solver_exception: {e}",
                elapsed_ms=(time.time() - t0) * 1000.0,
            )
        result.elapsed_ms = (time.time() - t0) * 1000.0
        return result

    def detect_and_solve(
        self, scan_result: ScanResult
    ) -> CaptchaResult | None:
        det = self.detect(scan_result)
        if det is None:
            return None
        return self.solve(det)
