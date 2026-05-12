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
        reason=(getattr(result, "error", None) or f"status={getattr(result, 'status', '?')}")[:200],
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

        async def send(
            self, method: str, params: dict[str, Any] | None = None, *, timeout: float | None = None
        ) -> dict[str, Any]:
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
    is_solved = str(solved).endswith("SUCCESS") or getattr(solved, "value", "") == "success"
    return CaptchaResult(
        solved=bool(is_solved),
        captcha_type="visual_text",
        reason=f"ocr={getattr(out, 'detail', '')}"[:150],
        elapsed_ms=elapsed_ms,
    )


# ── NOCH NICHT GEBRIDGT ────────────────────────────────────────────────────
# Die folgenden Solver brauchen entweder noch ein Solver-Modul in
# stealth-captcha (hcaptcha/recaptcha/turnstile gibt es dort heute nicht)
# ODER einen zusaetzlichen Bridge-Layer (z.B. 2Captcha-API-Call).
#
# Vor dem Live-Einsatz MUSS hier ein passender Adapter rein. Bis dahin
# liefern wir explizit `solver_not_yet_bridged` damit der Router das in
# state.errors sichtbar macht statt still zu scheitern.


# ── 2CAPTCHA GENERIC FALLBACK ──────────────────────────────────────────────
# Brueckenkopf zum bezahlten 2Captcha-Service. Liefert echte Tokens fuer
# hCaptcha / reCAPTCHA / Cloudflare Turnstile / GeeTest / Lemin etc.
#
# Aktivierung: cfg.captcha.twocaptcha_api_key MUSS gesetzt sein (env
# TWOCAPTCHA_API_KEY). Ohne Key liefert der Adapter weiter
# `reason="2captcha:api_key_missing"` und das Survey skipped die Frage.
#
# KOSTEN-AWARENESS: jeder erfolgreiche Solve wird in core.analytics als
# `captcha.twocaptcha.cost` gezaehlt. ROI muss positiv bleiben (Survey-
# Reward > Token-Kosten). Surveys mit > 1 Captcha sind selten profitabel —
# der LangGraph-Loop sollte nach 2 Captchas in einer Survey abbrechen.


def _twocaptcha_extract_sitekey(cdp, detection, *, providers: tuple[str, ...]) -> str | None:
    """Holt sitekey aus dem DOM. Erst data-sitekey, dann iframe src ?k=...

    `providers` bestimmt welche CSS-Selektoren / iframe-Host-Patterns
    wir versuchen — z.B. ("hcaptcha", "recaptcha", "turnstile").
    """
    # 1) bekannte Marker-Selektoren via JS
    js = (
        "(function(){"
        "var sels=["
        "'[data-sitekey]','iframe[src*=\"hcaptcha\"]','iframe[src*=\"recaptcha\"]',"
        "'iframe[src*=\"challenges.cloudflare.com\"]'];"
        "for(var i=0;i<sels.length;i++){"
        "  var el=document.querySelector(sels[i]); if(!el)continue;"
        "  var v=el.getAttribute('data-sitekey');"
        "  if(v)return v;"
        "  var s=el.getAttribute('src')||'';"
        "  var m=s.match(/[?&](?:k|sitekey|render)=([A-Za-z0-9_\\-]+)/);"
        "  if(m)return m[1];"
        "}"
        "return null;"
        "})()"
    )
    try:
        r = cdp.call_result("Runtime.evaluate", {"expression": js, "returnByValue": True})
        v = ((r or {}).get("result") or {}).get("value")
        if v and isinstance(v, str):
            return v
    except Exception:
        pass
    return None


def _twocaptcha_current_url(cdp) -> str | None:
    """Holt die aktuelle Tab-URL — fuer 2captcha pageurl param Pflicht."""
    try:
        r = cdp.call_result(
            "Runtime.evaluate",
            {
                "expression": "location.href",
                "returnByValue": True,
            },
        )
        v = ((r or {}).get("result") or {}).get("value")
        if v and isinstance(v, str):
            return v
    except Exception:
        pass
    return None


def _twocaptcha_solve(
    cdp, detection, *, captcha_type: str, providers: tuple[str, ...]
) -> CaptchaResult:
    """Gemeinsame 2captcha-Solve-Logik. Wird von hcaptcha/recaptcha/
    turnstile-Adaptern mit captcha_type-spezifischem `providers` aufgerufen.
    """
    start = time.monotonic()

    # Config laden — fail-soft wenn core nicht installiert ist (z.B. Unit-Test)
    try:
        from core import get_config, get_analytics

        cfg = get_config()
        analytics = get_analytics()
    except Exception as e:
        return CaptchaResult(
            solved=False,
            captcha_type=captcha_type,
            reason=f"core_not_available:{e}"[:100],
            elapsed_ms=(time.monotonic() - start) * 1000,
        )

    api_key = cfg.captcha.twocaptcha_api_key
    if not api_key:
        return CaptchaResult(
            solved=False,
            captcha_type=captcha_type,
            reason="2captcha:api_key_missing",
            elapsed_ms=(time.monotonic() - start) * 1000,
        )

    sitekey = _twocaptcha_extract_sitekey(cdp, detection, providers=providers)
    if not sitekey:
        return CaptchaResult(
            solved=False,
            captcha_type=captcha_type,
            reason="2captcha:no_sitekey_found",
            elapsed_ms=(time.monotonic() - start) * 1000,
        )

    pageurl = _twocaptcha_current_url(cdp)
    if not pageurl:
        return CaptchaResult(
            solved=False,
            captcha_type=captcha_type,
            reason="2captcha:no_pageurl",
            elapsed_ms=(time.monotonic() - start) * 1000,
        )

    try:
        from stealth_captcha.solver.twocaptcha import (
            TwoCaptchaFallbackSolver,
            TwoCaptchaParams,
            inject_token_via_cdp,
        )
    except ImportError as e:
        return CaptchaResult(
            solved=False,
            captcha_type=captcha_type,
            reason=f"2captcha:import_failed:{e}"[:120],
            elapsed_ms=(time.monotonic() - start) * 1000,
        )

    solver = TwoCaptchaFallbackSolver(
        api_key=api_key,
        max_seconds=cfg.captcha.max_solve_seconds,
    )
    params = TwoCaptchaParams(
        captcha_type=captcha_type,
        sitekey=sitekey,
        pageurl=pageurl,
    )

    try:
        token = asyncio.run(solver.fetch_token(params))
    except Exception as e:
        analytics.increment(f"captcha.twocaptcha.failed.{captcha_type}")
        return CaptchaResult(
            solved=False,
            captcha_type=captcha_type,
            reason=f"2captcha:{type(e).__name__}:{e}"[:200],
            elapsed_ms=(time.monotonic() - start) * 1000,
        )

    # Token injizieren — wenn das Field nicht gefunden wird, gilt es als
    # nicht geloest (auch wenn 2captcha den Token geliefert hat — Kosten
    # fallen leider trotzdem an, das ist beim Provider so).
    injected = inject_token_via_cdp(cdp, token, captcha_type)
    elapsed_ms = (time.monotonic() - start) * 1000
    analytics.increment(f"captcha.twocaptcha.solved.{captcha_type}")
    # ROI-Tracking: gefuehrte Cost-Schaetzung pro Solve (in USD-Cents)
    cost_est_cents = 0.3 if captcha_type == "recaptcha" else 0.2
    analytics.record("captcha.twocaptcha.cost_cents", cost_est_cents, captcha_type=captcha_type)

    return CaptchaResult(
        solved=bool(injected),
        captcha_type=captcha_type,
        reason=(
            "2captcha:injected" if injected else "2captcha:token_received_but_dom_inject_failed"
        ),
        elapsed_ms=elapsed_ms,
    )


def hcaptcha_solve(cdp, detection) -> CaptchaResult:
    """hCaptcha via 2Captcha-Service. Schreibt den Token in
    textarea[name="h-captcha-response"] und triggert window.hcaptcha.execute().
    """
    return _twocaptcha_solve(cdp, detection, captcha_type="hcaptcha", providers=("hcaptcha",))


def recaptcha_solve(cdp, detection) -> CaptchaResult:
    """reCAPTCHA v2 via 2Captcha. Schreibt in textarea#g-recaptcha-response.
    Fuer v3 explizit captcha_type=recaptcha_v3 nutzen (eigener Adapter — TBD).
    """
    return _twocaptcha_solve(cdp, detection, captcha_type="recaptcha", providers=("recaptcha",))


def turnstile_solve(cdp, detection) -> CaptchaResult:
    """Cloudflare Turnstile via 2Captcha. Schreibt in
    input[name="cf-turnstile-response"] und ruft __turnstileCb(token) falls
    vorhanden.
    """
    return _twocaptcha_solve(cdp, detection, captcha_type="turnstile", providers=("turnstile",))


# ── REGISTRY ───────────────────────────────────────────────────────────────
# Wird vom captcha_router._solver_for() benutzt um den richtigen Adapter
# nachzuschlagen. Erweiterung: neuen Adapter oben definieren, hier
# eintragen, fertig.

ADAPTERS = {
    "angular_drag_drop": angular_drag_drop_solve,
    "visual_text": visual_text_solve,
    "hcaptcha": hcaptcha_solve,
    "recaptcha": recaptcha_solve,
    "turnstile": turnstile_solve,
}


def get_adapter(captcha_type: str):
    """Liefert den passenden Adapter-Callable oder None.

    Aufrufer (typischerweise captcha_router._solver_for()) muss None
    explizit als 'no_solver_for_type' behandeln.
    """
    return ADAPTERS.get(captcha_type)
