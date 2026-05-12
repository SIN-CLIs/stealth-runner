"""SR-57 #56 — Stdlib-only LLM-Client fuer Pattern-Suggester Phase 2.

================================================================================
ZWECK
================================================================================

Phase 1 des FCTC-ES-Suggesters (token-overlap heuristic in
``suggester.suggest_family``) klassifiziert Misses wie "Mobilfunknummer" →
``phone`` korrekt, scheitert aber an Phrasing-Varianten ohne Token-Ueberlapp:

  "Wie viele Personen wohnen in Ihrem Haushalt?"  →  household_size  (FAIL)
  "Was ist Ihre PLZ und Ihr Wohnort?"            →  postal_code+city (FAIL)

Phase 2 (dieses Modul) ruft die Vercel-AI-Gateway-API (OpenAI-kompatibel) auf,
wenn die Heuristik unentschieden ist (``family is None`` oder
``confidence < 0.20``). Output landet in der gleichen pattern-suggestions JSONL,
aber mit ``source: "llm"`` + ``model`` + ``prompt_hash`` — der downstream
``apply``-Pfad (SR-58 #57) hat einen strengeren Confidence-Gate (0.85) fuer
LLM-Quellen.

================================================================================
ARCHITEKTUR-ENTSCHEIDUNGEN
================================================================================

A) **Stdlib-only.** Wir benutzen ``urllib.request``, kein ``httpx``/``openai``
   SDK. Begruendung:
     - Die Lernschleife laeuft offline-batch (CI-tauglich), wir wollen KEINE
       neue Production-Dependency fuer einen Pfad, der hinter einem env-flag
       gated ist.
     - Mocking via ``unittest.mock.patch`` auf ``urllib.request.urlopen``
       ist trivialer als das mocken eines SDK-Clients.
     - AI Gateway exposes OpenAI-shape `POST /v1/chat/completions` — keine
       SDK-Magie noetig.

B) **Fail-soft.** Fehlende API-Key, Timeout, 5xx, JSON-Parse-Error werden
   alle als ``LLMResponse(content=None, error="...")`` zurueckgegeben — NIE
   als Exception. Begruendung: ein Aggregator-Lauf darf NICHT crashen, wenn
   die LLM kurz weg ist. Lieber 5 Heuristik-only Vorschlaege als 0 Vorschlaege
   plus Stacktrace.

C) **Strict timeouts.** Default 20s per request. Lernschleife laeuft batch,
   aber wir wollen NICHT, dass ein haengender API-Endpunkt CI blockiert.

D) **Stabile prompt_hash.** ``sha256(prompt)[:12]`` — gibt forensische
   Reproduzierbarkeit (welcher prompt hat diesen Vorschlag erzeugt?) ohne
   den vollen Prompt im Audit-Log zu duplizieren. Die Liste der erlaubten
   Familien fliesst in den Prompt ein, also aendert sich der Hash, wenn
   ``FAMILY_TOKENS`` waechst — bewusst, damit alter LLM-Output bei spaeterem
   Review nicht falsch zugeordnet wird.

E) **Sichtbare Provider-Wahl.** Default-Modell ``openai/gpt-5-mini`` ist ein
   AI-Gateway-Zero-Config-Provider; ``AI_GATEWAY_API_KEY`` ist die einzige
   noetige env. Override via ``model=`` Argument oder ``SR_LLM_MODEL`` env.
   Endpoint via ``SR_AI_GATEWAY_URL`` env (Default: Production-Gateway).
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional


# ── Konstanten ──────────────────────────────────────────────────────────────
_DEFAULT_ENDPOINT = "https://ai-gateway.vercel.sh/v1/chat/completions"
_DEFAULT_MODEL = "openai/gpt-5-mini"
_DEFAULT_TIMEOUT_S = 20.0
_DEFAULT_TEMPERATURE = 0.0  # deterministisch, wir klassifizieren keine Lyrik


@dataclass(frozen=True)
class LLMResponse:
    """Ergebnis eines LLM-Calls — content=None bedeutet 'kein Vorschlag'.

    Fields:
        content:      Roh-Text der Antwort, oder None bei Fehler/no-key.
        model:        Tatsaechlich verwendetes Model-ID (fuer Audit-Log).
        prompt_hash:  sha256(prompt)[:12], fuer forensische Lookup.
        error:        Kurzbeschreibung im Fehlerfall (None bei Success).
        latency_ms:   Round-trip latency, zur Telemetrie.
    """

    content: Optional[str]
    model: str
    prompt_hash: str
    error: Optional[str] = None
    latency_ms: Optional[int] = None


def prompt_hash(prompt: str) -> str:
    """Stabile 12-char hex-id fuer einen gegebenen Prompt-Text."""
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]


def _resolve_config() -> tuple[Optional[str], str, str]:
    """Returns ``(api_key, endpoint, model)``.

    Liest env-vars: AI_GATEWAY_API_KEY (required), SR_AI_GATEWAY_URL (opt),
    SR_LLM_MODEL (opt). ``api_key`` ist None, wenn die env-var fehlt — die
    Caller-Funktion ``call_llm`` returnt dann LLMResponse(content=None,
    error="no AI_GATEWAY_API_KEY"). Bewusst KEIN Crash."""
    api_key = os.environ.get("AI_GATEWAY_API_KEY")
    endpoint = os.environ.get("SR_AI_GATEWAY_URL", _DEFAULT_ENDPOINT)
    model = os.environ.get("SR_LLM_MODEL", _DEFAULT_MODEL)
    return api_key, endpoint, model


def call_llm(
    prompt: str,
    *,
    system: Optional[str] = None,
    model: Optional[str] = None,
    endpoint: Optional[str] = None,
    timeout: float = _DEFAULT_TIMEOUT_S,
    temperature: float = _DEFAULT_TEMPERATURE,
    response_format_json: bool = True,
) -> LLMResponse:
    """Ein POST gegen AI-Gateway, OpenAI-chat-completions-shape.

    Args:
        prompt:    User-Message-Text.
        system:    Optional system-Message (default: minimal classification system).
        model:     Override gegen env/default.
        endpoint:  Override gegen env/default.
        timeout:   Socket-timeout in Sekunden.
        temperature: Default 0.0 (deterministische Klassifikation).
        response_format_json: Setzt response_format={"type":"json_object"} —
                              AI-Gateway propagated das an die Provider.

    Returns:
        LLMResponse — niemals exception. ``content=None`` bei Fehler.

    Examples:
        >>> r = call_llm("Sag 'hallo'.")        # doctest: +SKIP
        >>> r.content                            # doctest: +SKIP
        'hallo'
    """
    api_key, default_endpoint, default_model = _resolve_config()
    used_model = model or default_model
    used_endpoint = endpoint or default_endpoint
    ph = prompt_hash(prompt)

    if not api_key:
        return LLMResponse(
            content=None, model=used_model, prompt_hash=ph,
            error="no AI_GATEWAY_API_KEY in env — LLM path disabled",
        )

    sys_msg = system or (
        "You are a strict classifier. "
        "Return ONLY valid JSON matching the requested schema. "
        "No prose, no markdown fences."
    )
    payload = {
        "model": used_model,
        "messages": [
            {"role": "system", "content": sys_msg},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
    }
    if response_format_json:
        payload["response_format"] = {"type": "json_object"}

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        used_endpoint,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            latency = int((time.monotonic() - t0) * 1000)
    except urllib.error.HTTPError as e:
        # Read body for diagnostic — but trimmed, weil API-Provider gern
        # mehrere KB stack-traces zurueckgeben.
        try:
            err_body = e.read().decode("utf-8", errors="replace")[:500]
        except Exception:  # noqa: BLE001
            err_body = "?"
        return LLMResponse(
            content=None, model=used_model, prompt_hash=ph,
            error=f"HTTP {e.code}: {err_body}",
            latency_ms=int((time.monotonic() - t0) * 1000),
        )
    except urllib.error.URLError as e:
        return LLMResponse(
            content=None, model=used_model, prompt_hash=ph,
            error=f"URL error: {e.reason}",
            latency_ms=int((time.monotonic() - t0) * 1000),
        )
    except TimeoutError:
        return LLMResponse(
            content=None, model=used_model, prompt_hash=ph,
            error=f"timeout after {timeout}s",
            latency_ms=int((time.monotonic() - t0) * 1000),
        )
    except Exception as e:  # noqa: BLE001 — fail-soft per architecture
        return LLMResponse(
            content=None, model=used_model, prompt_hash=ph,
            error=f"{type(e).__name__}: {e}",
            latency_ms=int((time.monotonic() - t0) * 1000),
        )

    # Parse OpenAI-shape response.
    try:
        obj = json.loads(raw)
        content = obj["choices"][0]["message"]["content"]
        # Provider can echo back a different model-id (e.g. with version).
        actual_model = obj.get("model", used_model)
    except (json.JSONDecodeError, KeyError, IndexError, TypeError) as e:
        return LLMResponse(
            content=None, model=used_model, prompt_hash=ph,
            error=f"unparseable response: {type(e).__name__}: "
                  f"{str(e)[:120]} (raw[:200]={raw[:200]!r})",
            latency_ms=latency,
        )

    return LLMResponse(
        content=content, model=actual_model, prompt_hash=ph,
        error=None, latency_ms=latency,
    )


def is_available() -> bool:
    """Quick check: does ``AI_GATEWAY_API_KEY`` exist? Used by CLI to decide
    whether to log 'LLM path skipped' or actually try."""
    return bool(os.environ.get("AI_GATEWAY_API_KEY"))


def warn_if_unavailable(stream=sys.stderr) -> None:
    """Schreibt eine einmal-Warnung auf stderr, wenn LLM gewuenscht aber
    nicht verfuegbar — der Caller wird das oft an mehreren Stellen pruefen,
    aber wir wollen die Warnung nicht spammen. Idempotent via Modul-Flag."""
    global _WARNED_NO_KEY  # noqa: PLW0603
    if _WARNED_NO_KEY:
        return
    _WARNED_NO_KEY = True
    if not is_available():
        stream.write(
            "[llm_client] AI_GATEWAY_API_KEY not set — LLM suggester "
            "path is disabled. Heuristic suggester (Phase 1) still runs.\n",
        )


_WARNED_NO_KEY: bool = False
