"""================================================================================
stealth-captcha / solver / twocaptcha.py  — Generic 2Captcha API Fallback
================================================================================

ZWECK
-----
ANSCHEINEND-unloesbare Captchas (hCaptcha, reCAPTCHA v2/v3, Cloudflare
Turnstile, GeeTest v4, Lemin) bekommen wir ueber das 2Captcha-Service
gegen Bezahlung als Token zurueck — wir injizieren dann den Token in
das richtige DOM-Feld und lassen die Survey weiterlaufen.

Dies ist ein BEZAHLTER FALLBACK (~0.001-0.003 USD pro Solve). Wir
schalten ihn NUR scharf wenn:
  - kein lokaler Solver greift (`_solver_for() == None`), oder
  - der lokale Solver mehrfach failed (recovery in captcha_node)

ARCHITEKTUR
-----------
2Captcha hat zwei API-Stile:
  a) "in.php / res.php" (klassisch, REST, polling-basiert)
  b) async createTask / getTaskResult (neuer, JSON)

Wir nutzen (a) weil es seit 10+ Jahren stabil ist und alle Captcha-Typen
abdeckt (taskType-Whitelist von b ist enger).

LIFECYCLE pro solve():
  1. POST in.php {key, method, sitekey, pageurl, ...}            → captcha_id
  2. Loop:    GET  res.php?key=...&action=get&id=<captcha_id>    → "CAPCHA_NOT_READY" | "OK|token"
     mit exponential backoff, max max_seconds Sekunden
  3. token zurueck → Caller injiziert ins DOM-Field & dispatcht callback

KOSTEN-AWARENESS
----------------
Wir loggen jede Solve-Spendierung als 2captcha.solve.cost mit Captcha-Type
in core.analytics — Survey-ROI muss positiv bleiben (Survey-Reward >
Captcha-Kosten).

CONFIG
------
Der API-Key kommt aus core.config.CaptchaConfig.twocaptcha_api_key. Wenn
leer → SolveResult(outcome=FAILURE, detail="no_api_key").

KEINE WEITEREN DEPS
-------------------
Wir nutzen urllib.request statt requests/httpx — der Solver soll auch in
minimalen Containern laufen wo httpx fehlt.
================================================================================"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Optional

from stealth_captcha.solver.base import BaseSolver, SolveOutcome, SolveResult

log = logging.getLogger("solver.twocaptcha")

_TWOCAPTCHA_HOST = "https://2captcha.com"


# ── Mapping: unsere internen Typen → 2Captcha method-Parameter ────────────────
#
# Quelle: https://2captcha.com/2captcha-api (Captcha types section, 2026-05).
# Erweiterung: einen Eintrag hier dazu = neuen Captcha-Typ unterstuetzt.

_METHOD_MAP = {
    "hcaptcha":        "hcaptcha",        # benoetigt sitekey + pageurl
    "recaptcha":       "userrecaptcha",   # v2 — googlekey + pageurl
    "recaptcha_v3":    "userrecaptcha",   # zusaetzlich: version=v3, min_score
    "turnstile":       "turnstile",       # sitekey + pageurl
    "geetest":         "geetest",         # gt + challenge + api_server
    "lemin":           "lemin",           # captcha_id + api_server + pageurl
    "datadome":        "datadome",        # captcha_url + pageurl + userAgent
    "image":           "base64",          # OCR-only, body=base64 image
}


@dataclass(slots=True)
class TwoCaptchaParams:
    """Parameter-Bundle fuer einen 2Captcha-Solve.

    Pflicht-Felder pro captcha_type:
      hcaptcha:        sitekey, pageurl
      recaptcha:       sitekey, pageurl   (sitekey heisst dort 'googlekey')
      turnstile:       sitekey, pageurl
      geetest:         gt, challenge, pageurl
      lemin:           captcha_id, pageurl, api_server
      image:           image_base64
    """
    captcha_type: str
    sitekey: Optional[str] = None
    pageurl: Optional[str] = None
    gt: Optional[str] = None
    challenge: Optional[str] = None
    api_server: Optional[str] = None
    captcha_id: Optional[str] = None
    image_base64: Optional[str] = None
    user_agent: Optional[str] = None
    invisible: bool = False
    is_v3: bool = False
    min_score: float = 0.3
    action: Optional[str] = None  # reCAPTCHA v3
    extra: dict = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.extra is None:
            self.extra = {}


class TwoCaptchaError(RuntimeError):
    """Service liefert ERROR_<code> oder Netzwerk-Fehler."""


# ── Hauptklasse ──────────────────────────────────────────────────────────────


class TwoCaptchaFallbackSolver(BaseSolver):
    """Generischer Bezahl-Fallback fuer Captchas die kein lokaler Solver loest.

    Beispiel:
        solver = TwoCaptchaFallbackSolver(
            api_key=cfg.captcha.twocaptcha_api_key,
            max_seconds=cfg.captcha.max_solve_seconds,
        )
        params = TwoCaptchaParams(
            captcha_type="hcaptcha",
            sitekey="abc-123",
            pageurl="https://example.com/survey/42",
        )
        token = await solver.fetch_token(params)
        # → token-String wird ins richtige DOM-Field injiziert
        #   z. B. textarea[name="h-captcha-response"]

    Die solve()-Methode aus BaseSolver liefert ein SolveResult; fuer die
    primaere Use-Case-API empfehlen wir fetch_token() direkt — der Caller
    bekommt den Token-String zurueck und entscheidet wann/wo er injiziert.
    """

    def __init__(self, api_key: str, *, max_seconds: float = 60.0,
                 poll_interval: float = 5.0, soft_id: Optional[str] = None):
        self.api_key = (api_key or "").strip()
        self.max_seconds = float(max_seconds)
        self.poll_interval = float(poll_interval)
        self.soft_id = soft_id  # 2captcha affiliate ID (optional, kein Pflicht)

    # ── BaseSolver-Contract ──────────────────────────────────────────────────
    # Wir akzeptieren entweder session.captcha_params als TwoCaptchaParams oder
    # erwarten dass der Caller fetch_token() direkt verwendet. Die solve()-API
    # ist hier nur fuer Bridge-Adapter (z.B. captcha_adapters.twocaptcha_solve).

    async def solve(self, session) -> SolveResult:  # type: ignore[override]
        start = time.monotonic()
        params: Optional[TwoCaptchaParams] = getattr(session, "captcha_params", None)
        if params is None:
            return SolveResult(
                outcome=SolveOutcome.FAILURE,
                attempts=0,
                duration_s=0.0,
                detail="no_params_attached_to_session",
            )
        try:
            token = await self.fetch_token(params)
            return SolveResult(
                outcome=SolveOutcome.SUCCESS,
                attempts=1,
                duration_s=time.monotonic() - start,
                detail=token,
            )
        except TwoCaptchaError as e:
            return SolveResult(
                outcome=SolveOutcome.FAILURE,
                attempts=1,
                duration_s=time.monotonic() - start,
                detail=str(e)[:200],
            )
        except Exception as e:
            return SolveResult(
                outcome=SolveOutcome.UNKNOWN,
                attempts=1,
                duration_s=time.monotonic() - start,
                detail=f"{type(e).__name__}:{e}"[:200],
            )

    # ── Public API ───────────────────────────────────────────────────────────

    async def fetch_token(self, params: TwoCaptchaParams) -> str:
        """Submit + Poll, returns token-String oder wirft TwoCaptchaError."""
        if not self.api_key:
            raise TwoCaptchaError("api_key_missing")
        method = _METHOD_MAP.get(params.captcha_type)
        if not method:
            raise TwoCaptchaError(f"unsupported_type:{params.captcha_type}")

        captcha_id = await self._submit(method, params)
        token = await self._poll(captcha_id)
        return token

    # ── HTTP intern ──────────────────────────────────────────────────────────

    async def _submit(self, method: str, params: TwoCaptchaParams) -> str:
        body = self._build_submit_body(method, params)
        url = f"{_TWOCAPTCHA_HOST}/in.php"
        log.info(
            "twocaptcha.submit type=%s method=%s sitekey=%s pageurl=%s",
            params.captcha_type, method,
            (params.sitekey or "")[:12], (params.pageurl or "")[:60],
        )
        resp = await asyncio.to_thread(self._http_post, url, body)
        if not resp.startswith("OK|"):
            raise TwoCaptchaError(f"submit_failed:{resp}")
        return resp.split("|", 1)[1]

    async def _poll(self, captcha_id: str) -> str:
        deadline = time.monotonic() + self.max_seconds
        # 2Captcha empfiehlt 20s warten bevor erste poll-Anfrage
        await asyncio.sleep(min(self.poll_interval, self.max_seconds * 0.2))
        url = (
            f"{_TWOCAPTCHA_HOST}/res.php?key={urllib.parse.quote(self.api_key)}"
            f"&action=get&id={urllib.parse.quote(captcha_id)}"
        )
        attempts = 0
        while time.monotonic() < deadline:
            attempts += 1
            resp = await asyncio.to_thread(self._http_get, url)
            if resp == "CAPCHA_NOT_READY":
                await asyncio.sleep(self.poll_interval)
                continue
            if resp.startswith("OK|"):
                token = resp.split("|", 1)[1]
                log.info(
                    "twocaptcha.solved captcha_id=%s attempts=%d", captcha_id, attempts,
                )
                return token
            raise TwoCaptchaError(f"poll_error:{resp}")
        raise TwoCaptchaError(f"timeout_after_{self.max_seconds:.0f}s")

    # ── Body-Builder ─────────────────────────────────────────────────────────

    def _build_submit_body(self, method: str, p: TwoCaptchaParams) -> bytes:
        data: dict[str, str] = {
            "key": self.api_key,
            "method": method,
            "json": "1",  # spaeter ggf. auf JSON umsteigen
        }
        # JSON ist gerade nicht aktiv — wir kapseln das fuer kuenftige Migration
        data.pop("json", None)

        if p.pageurl:
            data["pageurl"] = p.pageurl
        if p.sitekey:
            # 2Captcha nennt das Feld unterschiedlich je Method:
            if method == "userrecaptcha":
                data["googlekey"] = p.sitekey
            elif method in ("hcaptcha", "turnstile"):
                data["sitekey"] = p.sitekey
        if method == "userrecaptcha":
            if p.is_v3:
                data["version"] = "v3"
                data["min_score"] = str(p.min_score)
                if p.action:
                    data["action"] = p.action
            if p.invisible:
                data["invisible"] = "1"
        if method == "geetest":
            if p.gt:        data["gt"] = p.gt
            if p.challenge: data["challenge"] = p.challenge
            if p.api_server: data["api_server"] = p.api_server
        if method == "lemin":
            if p.captcha_id: data["captcha_id"] = p.captcha_id
            if p.api_server: data["api_server"] = p.api_server
        if method == "datadome":
            if p.user_agent: data["userAgent"] = p.user_agent
        if method == "base64":
            if not p.image_base64:
                raise TwoCaptchaError("image_base64_required")
            data["body"] = p.image_base64
        if self.soft_id:
            data["soft_id"] = self.soft_id
        for k, v in (p.extra or {}).items():
            data[k] = str(v)
        return urllib.parse.urlencode(data).encode("utf-8")

    # ── Sync HTTP via stdlib (keine externe Dep) ─────────────────────────────

    @staticmethod
    def _http_post(url: str, body: bytes) -> str:
        req = urllib.request.Request(
            url, data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded",
                     "User-Agent": "stealth-runner/twocaptcha/1.0"},
        )
        with urllib.request.urlopen(req, timeout=15) as r:  # noqa: S310
            return r.read().decode("utf-8", errors="replace").strip()

    @staticmethod
    def _http_get(url: str) -> str:
        req = urllib.request.Request(
            url, headers={"User-Agent": "stealth-runner/twocaptcha/1.0"},
        )
        with urllib.request.urlopen(req, timeout=15) as r:  # noqa: S310
            return r.read().decode("utf-8", errors="replace").strip()


# ── Helper: DOM-Injection des Tokens via CDP ──────────────────────────────────


def inject_token_via_cdp(cdp, token: str, captcha_type: str) -> bool:
    """Schreibt den Token in das jeweilige Standard-Feld und triggert das
    Callback, das das Captcha-iframe beim Solve aufruft.

    Standard-Felder je Captcha:
      hcaptcha:  textarea[name="h-captcha-response"]
                 + global window.hcaptcha._callbacks[*](token)
      recaptcha: textarea#g-recaptcha-response
                 + global ___grecaptcha_cfg.clients[0][...] callback(token)
      turnstile: input[name="cf-turnstile-response"]
                 + window.turnstile.executeCallback(token)

    Returns True wenn das Field gefunden + gesetzt — der Submit-Button-Klick
    bleibt Aufgabe des Survey-Flows (jeder Provider hat eigene Buttons).
    """
    if captcha_type == "hcaptcha":
        expr = (
            "(function(t){"
            "var el=document.querySelector('textarea[name=\"h-captcha-response\"]')"
            "||document.querySelector('textarea#h-captcha-response');"
            "if(!el)return false;"
            "el.value=t;el.dispatchEvent(new Event('input'));"
            "el.dispatchEvent(new Event('change'));"
            "try{if(window.hcaptcha&&window.hcaptcha.execute)"
            "window.hcaptcha.execute();}catch(e){}"
            "return true;"
            "})(" + json.dumps(token) + ")"
        )
    elif captcha_type in ("recaptcha", "recaptcha_v3"):
        expr = (
            "(function(t){"
            "var el=document.querySelector('textarea#g-recaptcha-response')"
            "||document.querySelector('textarea[name=\"g-recaptcha-response\"]');"
            "if(!el)return false;"
            "el.value=t;el.style.display='block';"
            "el.dispatchEvent(new Event('input'));"
            "el.dispatchEvent(new Event('change'));"
            "return true;"
            "})(" + json.dumps(token) + ")"
        )
    elif captcha_type == "turnstile":
        expr = (
            "(function(t){"
            "var el=document.querySelector('input[name=\"cf-turnstile-response\"]')"
            "||document.querySelector('input#cf-turnstile-response');"
            "if(!el)return false;"
            "el.value=t;"
            "el.dispatchEvent(new Event('input'));"
            "el.dispatchEvent(new Event('change'));"
            "try{var cb=window.__turnstileCb;if(typeof cb==='function')cb(t);}catch(e){}"
            "return true;"
            "})(" + json.dumps(token) + ")"
        )
    else:
        return False

    try:
        result = cdp.call_result("Runtime.evaluate", {
            "expression": expr,
            "returnByValue": True,
        })
        return bool(((result or {}).get("result") or {}).get("value"))
    except Exception as e:
        log.warning("inject_token.cdp_failed type=%s err=%s", captcha_type, e)
        return False
