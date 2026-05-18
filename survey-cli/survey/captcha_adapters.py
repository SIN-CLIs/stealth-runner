"""================================================================================
CAPTCHA ADAPTERS — Bridge zwischen survey-cli und stealth-captcha
================================================================================

WAS IST DAS?
  Eine duenne sync-Schicht die fremde Solver in das Vertrags-Format
  `solve(cdp, detection) -> CaptchaResult` bringt das `captcha_router`
  erwartet. Survey-CLI ist der Konsument — Adapter gehoeren hierher,
  nicht ins stealth-captcha-Repo (single source of truth).

WARUM EXISTIERT DAS?
  - stealth-captcha-Solver sind teils asyncio + eigene CDPSession,
    teils sync + raw websockets. Beides muss unter dem gleichen
    Aufrufer-Vertrag laufen.
  - Aenderungen am stealth-captcha-Paket wuerden 30+ Repos beruehren.
    Adapter hier = ein File, ein Repo, klare Verantwortung.
  - Neue Captcha-Typen (hcaptcha, recaptcha, turnstile) bekommen hier
    einen sichtbaren Stub mit `reason="solver_not_yet_bridged"`. So weiss
    der Router was fehlt, und niemand muss erst tief im Code suchen.

VERTRAG:
  def <type>_solve(cdp, detection) -> CaptchaResult
    cdp:       survey.cdp_client.CDPConnection (sync, hat .ws_url)
    detection: survey.captcha_router.CaptchaDetection
    return:    survey.captcha_router.CaptchaResult

LOOKUP-REIHENFOLGE im captcha_router._solver_for():
  1) survey.captcha_adapters.<type>_solve  (HIER, hat Vorrang)
  2) stealth_captcha.solver.<type>.solve  (Fallback fuer Solver die
     bereits den richtigen Vertrag direkt erfuellen)

BANNED:
  - Kein Captcha-Code IN diesem Modul. Solver-Logik muss in
    stealth-captcha leben. Hier nur sync/async-Bruecken + Result-Mapping.
================================================================================
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from .captcha_router import CaptchaResult


# ── ANGULAR DRAG-DROP ──────────────────────────────────────────────────────


def angular_drag_drop_solve(cdp, detection) -> CaptchaResult:
    """Wraps stealth_captcha.solver.drag_drop_angular.solve_drag_puzzle_new.

    Der Angular-Drag-Drop-Solver ist sync und nutzt direkt
    websocket-client + Playwright subprocess. Er braucht nur einen
    ws_url — wir reichen `cdp.ws_url` durch.

    Mapping DragDropResult → CaptchaResult:
      status="solved"   → solved=True
      status="failed"   → solved=False, reason=error
      status="blocked"  → solved=False, reason=error
    """
    start = time.monotonic()
    try:
        from stealth_captcha.solver.drag_drop_angular import (
            solve_drag_puzzle_new,
        )
    except ImportError as e:
        return CaptchaResult(
            solved=False,
            captcha_type="angular_drag_drop",
            reason=f"import_failed:{e}"[:120],
            elapsed_ms=0,
        )

    try:
        result = solve_drag_puzzle_new(cdp.ws_url)
    except Exception as e:
        return CaptchaResult(
            solved=False,
            captcha_type="angular_drag_drop",
            reason=f"solver_exception:{type(e).__name__}:{e}"[:200],
            elapsed_ms=(time.monotonic() - start) * 1000,
        )

    elapsed_ms = (time.monotonic() - start) * 1000
    if getattr(result, "status", "") == "solved":
        return CaptchaResult(
            solved=True,
            captcha_type="angular_drag_drop",
            reason=f"solved:number={getattr(result, 'number', '?')}",
            elapsed_ms=elapsed_ms,
        )
    return CaptchaResult(
        solved=False,
        captcha_type="angular_drag_drop",
        reason=(getattr(result, "error", None) or
                f"status={getattr(result, 'status', '?')}")[:200],
        elapsed_ms=elapsed_ms,
    )


# ── VISUAL TEXT (OCR) ──────────────────────────────────────────────────────


def visual_text_solve(cdp, detection) -> CaptchaResult:
    """Wraps stealth_captcha.solver.text.TextCaptchaSolver (async) hinter
    einem sync-Adapter.

    Bridge-Strategie:
      a) Eine ad-hoc CDPSession-aehnliche Klasse die `await session.send`
         intern auf den sync CDPConnection delegiert (Threadsafe weil
         asyncio.run() einen eigenen Loop in diesem Thread aufmacht).
      b) `asyncio.run(TextCaptchaSolver().solve(session))` ruft die ganze
         OCR-Pipeline (Screenshot → Pixtral → Type → Submit).

    Wird derzeit NICHT von einem Detector im Router angesprochen — der
    Solver ist hier als "ready when needed" bereitgestellt, sobald der
    visual_text-Detector im captcha_router scharf geschaltet ist.
    """
    start = time.monotonic()

    try:
        from stealth_captcha.solver.text import (  # type: ignore
            TextCaptchaSolver,
            PixtralLargeOCR,
        )
    except ImportError as e:
        return CaptchaResult(
            solved=False,
            captcha_type="visual_text",
            reason=f"import_failed:{e}"[:120],
            elapsed_ms=0,
        )

    # Sync → Async Bruecke: minimaler "Session"-Stub der `await .send` auf
    # die sync CDPConnection delegiert. Wir leben ohne Multiplexing weil
    # ein einzelner Tab keine session_id braucht — der CDPConnection ist
    # bereits an genau einen Page-Target gebunden.
    class _SessionStub:
        def __init__(self, sync_cdp):
            self._cdp = sync_cdp

        async def send(self, method: str,
                       params: dict[str, Any] | None = None,
                       *, timeout: float | None = None) -> dict[str, Any]:
            # `cdp.send` blockiert; das ist in einem asyncio-Kontext
            # akzeptabel weil dieser Adapter selbst in einem dedizierten
            # asyncio.run() laeuft (sync Caller, eigener Event-Loop).
            return self._cdp.send(method, params or {})

    async def _run():
        backend = PixtralLargeOCR()
        solver = TextCaptchaSolver(backend=backend)
        session = _SessionStub(cdp)
        return await solver.solve(session)

    try:
        out = asyncio.run(_run())
    except Exception as e:
        return CaptchaResult(
            solved=False,
            captcha_type="visual_text",
            reason=f"solver_exception:{type(e).__name__}:{e}"[:200],
            elapsed_ms=(time.monotonic() - start) * 1000,
        )

    elapsed_ms = (time.monotonic() - start) * 1000
    solved = getattr(out, "outcome", None)
    is_solved = (str(solved).endswith("SUCCESS")
                 or getattr(solved, "value", "") == "success")
    return CaptchaResult(
        solved=bool(is_solved),
        captcha_type="visual_text",
        reason=f"ocr={getattr(out, 'detail', '')}"[:150],
        elapsed_ms=elapsed_ms,
    )


# ── NOCH NICHT GEBRIDGT ────────────────────────────────────────────────────
# Die folgenden Solver brauchen entweder noch ein Solver-Modul in
# stealth-captcha (hcaptcha/recaptcha/turnstile gibt es dort heute nicht)
# ODER eigene Loesungen via Open-Source-Repos.
#
# POLICY (SR-260): KEINE bezahlten Captcha-Services (2Captcha, Capsolver,
# anti-captcha etc.) duerfen jemals integriert werden. Wenn fuer einen
# Captcha-Typ kein nativer Solver existiert, liefern wir `solver_not_yet_bridged`
# — der Survey wird geskipt, NICHT gegen Geld geloest.
#
# ROADMAP fuer eigene Loesungen (siehe docs/CAPTCHA_STRATEGY.md):
#   hcaptcha    → eigener Solver basierend auf https://github.com/QIN2DIM/hcaptcha-challenger
#                 (open-source, lokales Vision-Modell)
#   recaptcha   → audio-challenge-route mit lokalem Whisper (OSS)
#   turnstile   → Browser-Trust-Score-Loesung via Patchright (kein Token-Solving noetig)
#   geetest     → eigener slide-Solver in stealth-captcha (auf Basis des bestehenden
#                 SlideCaptchaSolver)
#
# Bis diese Module implementiert sind, liefern die Adapter explizit
# `reason="solver_not_yet_bridged"` damit der Router das in state.errors
# sichtbar macht statt still zu scheitern.


def _not_bridged(captcha_type: str) -> CaptchaResult:
    """Einheitlicher 'kein-Solver'-Retval. Der Router behandelt das wie
    `no_solver_for_type` und der LangGraph-Loop skipt den Survey."""
    return CaptchaResult(
        solved=False,
        captcha_type=captcha_type,
        reason="solver_not_yet_bridged:see_docs/CAPTCHA_STRATEGY.md",
        elapsed_ms=0,
    )


def hcaptcha_solve(cdp, detection) -> CaptchaResult:
    """hCaptcha — kein nativer Solver in stealth-captcha (TBD).

    Roadmap: eigener Solver basierend auf hcaptcha-challenger (OSS),
    lokales Vision-Modell. KEIN bezahlter API-Service.
    """
    return _not_bridged("hcaptcha")


def recaptcha_solve(cdp, detection) -> CaptchaResult:
    """reCAPTCHA — kein nativer Solver in stealth-captcha (TBD).

    Roadmap: audio-challenge-route mit lokalem Whisper. KEIN bezahlter
    API-Service.
    """
    return _not_bridged("recaptcha")


def turnstile_solve(cdp, detection) -> CaptchaResult:
    """Cloudflare Turnstile — kein nativer Solver (TBD).

    Roadmap: Turnstile reagiert primaer auf Browser-Trust-Score, der durch
    Patchright + injection.js bereits hoch ist. Ein dezidiertes
    Token-Solving sollte in den meisten Faellen nicht noetig sein.
    """
    return _not_bridged("turnstile")


# ── REGISTRY ───────────────────────────────────────────────────────────────
# Wird vom captcha_router._solver_for() benutzt um den richtigen Adapter
# nachzuschlagen. Erweiterung: neuen Adapter oben definieren, hier
# eintragen, fertig.

ADAPTERS = {
    "angular_drag_drop": angular_drag_drop_solve,
    "visual_text":       visual_text_solve,
    "hcaptcha":          hcaptcha_solve,
    "recaptcha":         recaptcha_solve,
    "turnstile":         turnstile_solve,
}


def get_adapter(captcha_type: str):
    """Liefert den passenden Adapter-Callable oder None.

    Aufrufer (typischerweise captcha_router._solver_for()) muss None
    explizit als 'no_solver_for_type' behandeln.
    """
    return ADAPTERS.get(captcha_type)
