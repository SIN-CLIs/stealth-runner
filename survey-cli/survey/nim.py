"""================================================================================
NVIDIA NIM CLIENT v3 — Nemotron 3 Omni für die KANONISCHE v2-Pipeline
================================================================================

WAS HAT SICH GEAENDERT (2026-05-11):
- Prompt erhaelt eine FLACHE Liste von Elementen aus cdp_universal.scan(),
  jedes mit einem stabilen, frame-uebergreifenden Bezeichner `stable_id`.
- Das Modell antwortet mit `{actions: [{stable_id, action, value?}]}`.
  KEINE `@eN`-Indizes mehr, KEIN Y-Sort, KEINE Provider-Heuristik im Prompt.
- Backward-Compat: wenn der Aufrufer (alter Code) noch `refs={@e0:...}`
  übergibt, wird automatisch der LEGACY-Prompt benutzt, damit nichts bricht.

KONTRAKT MIT decide_node (siehe survey-cli/survey/graph/nodes.py):
  Input:
    snapshot = {
      "elements": [
        {"stable_id": "abc123", "role": "button", "name": "Weiter",
         "value": "", "checked": false},
        ...
      ],
      "avoid_stable_id": "previously_failed_id",  # leer wenn keiner
      "no_dom_change_count": 1,                   # 0 wenn letzter Klick wirkte
      "iteration": 7,
      "provider": "qualtrics" | "purespectrum" | ...
    }
    profile = ProfileLoader.load_profile()
  Output:
    {"actions": [
        {"stable_id": "xyz789", "action": "click"},
        # oder
        {"stable_id": "xyz789", "action": "fill", "value": "Berlin"},
        # oder
        {"action": "wait"},
        # oder
        {"action": "complete"},
     ],
     "model": "...",
     "elapsed_ms": int,
     "tokens": {"total": int}
    }

WARUM nur EINE Aktion pro Decide?
  Pflicht-Verify im Actuator macht Batch-Actions unmoeglich zuverlaessig:
  Aktion 1 koennte das DOM aendern und Aktion 2/3 ungueltig machen
  (stable_ids invalidiert). Stattdessen: 1 Aktion, dann re-scan, dann
  naechste Entscheidung. So sieht der Graph jede Halluzination sofort.

BANNED:
- KEIN `@eN`-Output in neuen Prompts.
- KEIN `action="select"` oder `action="submit"` mit Index.
  Das Modell muss `stable_id` + `action ∈ {click, fill, wait, complete}` liefern.
================================================================================
"""
# ruff: noqa: E501  (LLM prompts in f-strings - SR-62 #61)

import json
import os
import time
import re
import logging
from openai import OpenAI, APIConnectionError, APITimeoutError, RateLimitError, AuthenticationError

logger = logging.getLogger("nim_client")

DEFAULT_MODEL = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"
DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"
MAX_TOKENS = 600
RETRIES = 3
CIRCUIT_BREAKER_THRESHOLD = 3
CIRCUIT_BREAKER_RECOVERY_S = 300


# ── PROMPT-BUILDER ─────────────────────────────────────────────────────────


def build_v2_prompt(snapshot: dict, profile: dict) -> str:
    """Neuer Prompt fuer die kanonische v2-Pipeline (stable_id-Schema).

    Erwartet `snapshot.elements` als flache Liste. Liefert einen Chain-of-
    Thought-Prompt der das Modell zwingt:
      1) genau ein Element zu identifizieren
      2) genau eine action zu waehlen
      3) JSON in einem definierten Schema auszugeben

    Args:
        snapshot: {elements:[...], avoid_stable_id, no_dom_change_count,
                   iteration, provider}
        profile: User-Profil von ProfileLoader
    """
    raw_elements = snapshot.get("elements", []) or []

    # Truncate to max 30 Elemente — sonst sprengt der Prompt die Token-Limits.
    # Priorisierung: zuerst die wahrscheinlichsten Interaktions-Kandidaten.
    INTERACTIVE_ORDER = (
        "button",
        "link",
        "radio",
        "checkbox",
        "switch",
        "combobox",
        "textbox",
        "searchbox",
        "spinbutton",
        "slider",
        "menuitem",
        "tab",
        "option",
    )
    raw_elements.sort(
        key=lambda e: (
            INTERACTIVE_ORDER.index(e.get("role", ""))
            if e.get("role") in INTERACTIVE_ORDER
            else 99,  # noqa: E501
            0 if not e.get("checked") else 1,
        )
    )
    elements = raw_elements[:30]

    compact_elems = [
        {
            "id": e["stable_id"],
            "role": e.get("role", ""),
            "name": (e.get("name") or "")[:80],
            "value": (e.get("value") or "")[:40],
            "checked": bool(e.get("checked", False)),
        }
        for e in elements
    ]

    avoid = snapshot.get("avoid_stable_id", "")
    no_dom_change = int(snapshot.get("no_dom_change_count", 0))
    iteration = int(snapshot.get("iteration", 0))
    provider = snapshot.get("provider", "?")

    profile_fields = {
        "age": profile.get("age"),
        "gender": profile.get("gender_label"),
        "city": profile.get("city"),
        "education": profile.get("education"),
        "employment": profile.get("employment_label"),
        "income": profile.get("household_income"),
    }
    profile_fields = {k: v for k, v in profile_fields.items() if v}

    hints = []
    if avoid:
        hints.append(
            f"WICHTIG: das Element mit id={avoid!r} wurde gerade angeklickt "
            f"aber das DOM hat sich NICHT geaendert. WAEHLE EIN ANDERES."
        )
    if no_dom_change >= 2:
        hints.append(
            "ACHTUNG: mehrere Klicks in Folge ohne DOM-Aenderung. "
            "Pruefe ob ein Captcha geloest werden muss oder du auf der "
            "falschen Frage bist."
        )
    hint_block = "\n".join(hints) if hints else "(keine besonderen Hinweise)"

    prompt = f"""You drive a survey filling agent. ONE action per turn, then the page is rescanned.

Provider: {provider} | Iteration: {iteration}

Hints:
{hint_block}

Available elements (each has a stable id, role, accessible name, current value, and checked state):
{json.dumps(compact_elems, indent=2, ensure_ascii=False)}

User profile (the agent must answer surveys consistent with this persona):
{json.dumps(profile_fields, indent=2, ensure_ascii=False)}

Think step by step (silently):
1. What is the current question or screen asking?
2. Which single element advances the survey toward completion in a way that matches the profile?
3. If a radio/checkbox represents the correct answer → action=click on that element.
4. If a textbox needs the user's data (city, age, etc.) → action=fill with the appropriate value.
5. If everything on this page is already answered and a continue/next button exists → action=click on it.
6. If the page is loading or nothing is interactive yet → action=wait.
7. If the survey is finished (thank you page, completion text) → action=complete.

CRITICAL RULES:
- ALWAYS use the element "id" field as `stable_id` — never invent ids.
- NEVER pick the id that is mentioned in "WICHTIG" above as "kein DOM-Change".
- Output ONE action per turn. The graph will rescan after execution.
- Output VALID JSON exactly matching this schema:

{{"actions": [{{"stable_id": "<id from list>", "action": "click"|"fill", "value": "<for fill>"}}]}}

Or, when no element should be touched:
{{"actions": [{{"action": "wait"}}]}}      or      {{"actions": [{{"action": "complete"}}]}}

Output ONLY the JSON, no markdown, no commentary.

JSON:"""
    return prompt


def build_legacy_prompt(snapshot: dict, profile: dict) -> str:
    """LEGACY-Prompt (alte @eN-Indizes). Wird nur noch genutzt wenn der
    Aufrufer NICHT die v2-Felder uebergibt. Wird im naechsten Schritt
    entfernt sobald alle Tools auf v2 sind."""
    refs = snapshot.get("refs", {})
    elements = dict(list(refs.items())[:25])
    questions = snapshot.get("semantic", {}).get("questions", [])[:3]
    provider = snapshot.get("provider", "?")
    progress = snapshot.get("semantic", {}).get("progress", "?")

    profile_fields = {
        "age": profile.get("age"),
        "gender": profile.get("gender_label"),
        "city": profile.get("city"),
        "education": profile.get("education"),
        "employment": profile.get("employment_label"),
        "income": profile.get("household_income"),
    }
    profile_fields = {k: v for k, v in profile_fields.items() if v}

    return f"""Analyze this survey page and decide what to do next.

Provider: {provider} | Progress: {progress}

Available elements:
{json.dumps(elements, indent=2, ensure_ascii=False)}

Detected questions:
{json.dumps(questions, ensure_ascii=False)}

User profile:
{json.dumps(profile_fields, indent=2)}

Think step by step:
1. What question is being asked?
2. What answer matches the profile?
3. Which element(s) need to be clicked/selected/filled?
4. Is there a submit/next button?

Then output ONLY a JSON array of actions.
Example: [{{"ref": "@e0", "action": "select"}}, {{"action": "submit"}}]
If done (completion text visible): [{{"action": "complete"}}]

Your JSON:"""


def build_survey_prompt(snapshot, profile, learnings=None, history=None):
    """Dispatcher zwischen v2- und Legacy-Prompt.

    Erkennung anhand `snapshot["elements"]`: wenn vorhanden → v2.
    Sonst → Legacy.
    """
    if isinstance(snapshot, dict) and "elements" in snapshot:
        return build_v2_prompt(snapshot, profile)
    return build_legacy_prompt(snapshot, profile)


# ── RESPONSE-PARSER ─────────────────────────────────────────────────────────


def parse_response(raw: str) -> list:
    """Robuster Parser fuer Modell-Antwort. Liefert immer eine Liste
    von action-dicts.

    Akzeptierte Schemas:
      v2:     {"actions": [{"stable_id": "...", "action": "click"|"fill",
                            "value"?: "..."}]}
      v2:     [{"stable_id":"...", "action":"click"}]
      legacy: [{"ref": "@e0", "action": "select"}]
      legacy: {"actions":[...]}

    Ungueltige/leere Antworten → fallback [{"action": "wait"}].
    (NICHT mehr "submit" wie frueher — das hat blind Submit gedrueckt
     ohne Verify und war eine Halluzinations-Quelle.)
    """
    if not raw:
        return [{"action": "wait"}]

    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw = "\n".join(lines)

    parsed = None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        # Suche eingebettetes JSON
        match = re.search(r"\{.*\}|\[.*\]", raw, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

    if parsed is None:
        if "complete" in raw.lower():
            return [{"action": "complete"}]
        return [{"action": "wait"}]

    actions: list = []
    if isinstance(parsed, dict) and "actions" in parsed:
        actions = parsed["actions"] or []
    elif isinstance(parsed, list):
        actions = parsed
    elif isinstance(parsed, dict):
        actions = [parsed]

    # Normalisierung: alte "ref" → neuer Kontext bleibt fuer Backward-Compat,
    # aber wir loggen das. Der Aufrufer (decide_node) erwartet stable_id.
    cleaned: list = []
    for a in actions:
        if not isinstance(a, dict):
            continue
        # Falls Modell trotz Anweisung "ref" verwendet hat
        if "ref" in a and "stable_id" not in a:
            a["stable_id"] = a.pop("ref")
        cleaned.append(a)

    if not cleaned:
        return [{"action": "wait"}]
    return cleaned


# ── CLIENT ─────────────────────────────────────────────────────────────────


class NIMClient:
    """NVIDIA Nemotron 3 Omni Client mit Circuit-Breaker und Retry."""

    def __init__(self, api_key=None, model=None):
        self.api_key = api_key or os.getenv("NVIDIA_API_KEY")
        self.model = model or os.getenv("NVIDIA_MODEL", DEFAULT_MODEL)
        self.client = None
        if self.api_key:
            self.client = OpenAI(api_key=self.api_key, base_url=DEFAULT_BASE_URL)
        self.consecutive_failures = 0
        self.last_failure_time = 0.0
        self._available = self.client is not None

    @property
    def available(self):
        if self._available:
            return True
        if (
            self.consecutive_failures > 0
            and time.time() - self.last_failure_time > CIRCUIT_BREAKER_RECOVERY_S
        ):
            logger.info(
                "NIM auto-recovery: circuit breaker closed after %ds", CIRCUIT_BREAKER_RECOVERY_S
            )
            self._available = True
            self.consecutive_failures = 0
        return self._available

    def _record_failure(self, error_type, error_msg):
        self.consecutive_failures += 1
        self.last_failure_time = time.time()
        logger.warning(
            "NIM failure [%s]: %s (consecutive: %d/%d)",
            error_type,
            error_msg,
            self.consecutive_failures,
            CIRCUIT_BREAKER_THRESHOLD,
        )
        if self.consecutive_failures >= CIRCUIT_BREAKER_THRESHOLD:
            self._available = False
            logger.error(
                "NIM circuit breaker OPEN after %d consecutive failures", self.consecutive_failures
            )

    def _record_success(self):
        if self.consecutive_failures > 0:
            logger.info(
                "NIM success: resetting circuit breaker (was %d failures)",
                self.consecutive_failures,
            )
        self.consecutive_failures = 0
        self._available = True

    def _call_api(self, prompt, temperature):
        return self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=MAX_TOKENS,
        )

    def decide(self, snapshot, profile, learnings=None, history=None, temperature=0.0):
        """Hauptmethode: liefert {actions, model, elapsed_ms, tokens}.

        Fallback bei fehlendem API-Key / Circuit-Breaker / Fehler:
        ``{"actions": [{"action": "wait"}], "model": "fallback", ...}``.
        Heuristik im decide_node uebernimmt dann.
        """
        if not self.client:
            return {
                "actions": [{"action": "wait"}],
                "model": "auto_pilot",
                "elapsed_ms": 0,
                "tokens": {"total": 0},
            }

        if not self.available:
            logger.warning("NIM circuit breaker open — returning fallback")
            return {
                "actions": [{"action": "wait"}],
                "model": "fallback",
                "elapsed_ms": 0,
                "tokens": {"total": 0},
            }

        prompt = build_survey_prompt(snapshot, profile, learnings, history)

        for attempt in range(1, RETRIES + 1):
            start = time.monotonic()
            try:
                response = self._call_api(prompt, temperature)
                elapsed = time.monotonic() - start
                raw = response.choices[0].message.content or ""
                actions = parse_response(raw)
                self._record_success()
                return {
                    "actions": actions,
                    "raw_response": raw[:200],
                    "model": self.model,
                    "elapsed_ms": round(elapsed * 1000),
                    "tokens": {"total": response.usage.total_tokens if response.usage else 0},
                }
            except AuthenticationError as e:
                self._record_failure("auth", str(e))
                break
            except RateLimitError as e:
                self._record_failure("rate_limit", str(e))
                if attempt < RETRIES:
                    time.sleep(min(2**attempt, 10))
                    continue
                break
            except (APIConnectionError, APITimeoutError) as e:
                self._record_failure("network", str(e))
                if attempt < RETRIES:
                    time.sleep(min(2**attempt, 10))
                    continue
                break
            except Exception as e:
                self._record_failure("unknown", str(e))
                break

        return {
            "actions": [{"action": "wait"}],
            "model": "fallback",
            "elapsed_ms": round((time.monotonic() - start) * 1000),
            "tokens": {"total": 0},
        }


_default_client = None


def get_nim():
    """Singleton-Accessor fuer den Default-Client."""
    global _default_client
    if _default_client is None:
        _default_client = NIMClient()
    return _default_client
