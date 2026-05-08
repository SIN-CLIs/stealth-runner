"""================================================================================
NVIDIA NIM CLIENT v2 — Nemotron 3 Omni mit Chain-of-Thought
================================================================================

WAS IST DAS?
  Client für NVIDIA NIM API (Nemotron 3 Nano Omni 30B-A3B).
  Optimiert für Survey-Entscheidungen mit Chain-of-Thought Prompts.

ARCHITEKTUR:
  ┌─────────────────────┐
  │  build_survey_      │
  │  prompt()           │
  └─────────────────────┘
         │
         ▼
  ┌─────────────────────┐
  │  NIMClient          │
  │  .decide()          │
  └─────────────────────┘
         │
         ▼
  ┌─────────────────────┐
  │  OpenAI API         │
  │  (NVIDIA NIM)       │
  └─────────────────────┘
         │
         ▼
  ┌─────────────────────┐
  │  Chain-of-Thought   │
  │  + JSON Batch Actions│
  └─────────────────────┘

KEY FINDINGS (2026-05-06):
  - Reasoning Models brauchen Chain-of-Thought (NICHT System-Prompts)
  - max_tokens muss ≥500 sein (Reasoning-Overhead!)
  - Das Modell muss "denken" bevor es JSON ausgibt
  - Kurze imperative Prompts ("Return ONLY JSON") verursachen leere Responses
  → Lösung: Detaillierte Chain-of-Thought Anweisungen

WARUM Chain-of-Thought?
  Nemotron 3 Omni ist ein Reasoning-Modell (30B-A3B).
  Es MUSS denken bevor es antwortet. Kurze Prompts blockieren das.
  → Chain-of-Thought = "Denkprozess" im Prompt, dann JSON-Output.

WARUM max_tokens=600?
  Reasoning-Overhead: 200-300 Tokens für Denkprozess.
  JSON-Output: 100-200 Tokens.
  → 600 = Puffer für komplexe Entscheidungen.

DEPENDENZEN:
  - openai (pip install openai)
  - NVIDIA_API_KEY (env var, Prefix: nvapi-...)

BANNED METHODS — NIEMALS VERWENDEN (siehe /banned.md):
  ❌ playstealth launch
  ❌ webauto-nodriver — ABSOLUT BANNED
  ❌ cua-driver click (raw index)
  ❌ --remote-allow-origins=* (ohne Quotes)
  ❌ /tmp/heypiggy-bot (fixed profile)
  ❌ Hardcoded PIDs
  ❌ pkill -f "Google Chrome"
  ❌ killall Google Chrome
  ❌ skylight-cli click --element-index
================================================================================"""

import json
import os
import time
import re
import logging
from openai import OpenAI, APIConnectionError, APITimeoutError, RateLimitError, AuthenticationError
from typing import Dict, List, Any, Optional

logger = logging.getLogger("nim_client")

DEFAULT_MODEL = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"
DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"
MAX_TOKENS = 600
RETRIES = 3
CIRCUIT_BREAKER_THRESHOLD = 3
CIRCUIT_BREAKER_RECOVERY_S = 300


def build_survey_prompt(snapshot, profile, learnings=None, history=None):
    """Build chain-of-thought prompt for Nemotron 3 Omni.
    
    The model needs to THINK before acting. Chain-of-thought format
    lets it analyze the question, match the profile, then output JSON.
    """
    refs = snapshot.get("refs", {})
    # Compact element list (max 25)
    elements = dict(list(refs.items())[:25])
    questions = snapshot.get("semantic", {}).get("questions", [])[:3]
    provider = snapshot.get("provider", "?")
    progress = snapshot.get("semantic", {}).get("progress", "?")

    # Minimal profile
    profile_fields = {
        "age": profile.get("age"),
        "gender": profile.get("gender_label"),
        "city": profile.get("city"),
        "education": profile.get("education"),
        "employment": profile.get("employment_label"),
        "income": profile.get("household_income"),
    }
    profile_fields = {k: v for k, v in profile_fields.items() if v}

    prompt = f"""Analyze this survey page and decide what to do next.

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

    return prompt


def parse_response(raw):
    """Parse LLM response into action list. Robust extraction."""
    if not raw:
        return [{"action": "submit"}]  # fallback
    
    raw = raw.strip()

    # Remove markdown code fences
    if raw.startswith("```"):
        lines = raw.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw = "\n".join(lines)

    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict) and "actions" in parsed:
            return parsed["actions"]
        return [parsed]
    except json.JSONDecodeError:
        match = re.search(r"\[.*?\]", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    
    # Last resort: check for "complete"
    if "complete" in raw.lower() or "done" in raw.lower():
        return [{"action": "complete"}]
    
    return [{"action": "submit"}]  # ultimate fallback


class NIMClient:
    """NVIDIA Nemotron 3 Omni client with circuit breaker and retry."""

    def __init__(self, api_key=None, model=None):
        self.api_key = api_key or os.getenv("NVIDIA_API_KEY")
        self.model = model or os.getenv("NVIDIA_MODEL", DEFAULT_MODEL)
        self.client = None
        if self.api_key:
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=DEFAULT_BASE_URL
            )
        self.consecutive_failures = 0
        self.last_failure_time = 0.0
        self._available = self.client is not None

    @property
    def available(self):
        if self._available:
            return True
        if self.consecutive_failures > 0 and time.time() - self.last_failure_time > CIRCUIT_BREAKER_RECOVERY_S:
            logger.info("NIM auto-recovery: circuit breaker closed after %ds",
                        CIRCUIT_BREAKER_RECOVERY_S)
            self._available = True
            self.consecutive_failures = 0
        return self._available

    def _record_failure(self, error_type, error_msg):
        self.consecutive_failures += 1
        self.last_failure_time = time.time()
        logger.warning("NIM failure [%s]: %s (consecutive: %d/%d)",
                       error_type, error_msg,
                       self.consecutive_failures, CIRCUIT_BREAKER_THRESHOLD)
        if self.consecutive_failures >= CIRCUIT_BREAKER_THRESHOLD:
            self._available = False
            logger.error("NIM circuit breaker OPEN after %d consecutive failures",
                         self.consecutive_failures)

    def _record_success(self):
        if self.consecutive_failures > 0:
            logger.info("NIM success: resetting circuit breaker (was %d failures)",
                        self.consecutive_failures)
        self.consecutive_failures = 0
        self._available = True

    def _call_api(self, prompt, temperature):
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=MAX_TOKENS,
        )
        return response

    def decide(self, snapshot, profile,
               learnings=None, history=None,
               temperature=0.0):
        if not self.client:
            return {"actions": [{"action": "submit"}],
                    "model": "auto_pilot", "elapsed_ms": 0,
                    "tokens": {"total": 0}}

        if not self.available:
            logger.warning("NIM circuit breaker open — returning fallback")
            return {"actions": [{"action": "submit"}],
                    "model": "fallback", "elapsed_ms": 0,
                    "tokens": {"total": 0}}

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
                    "tokens": {
                        "total": response.usage.total_tokens if response.usage else 0,
                    },
                }

            except AuthenticationError as e:
                self._record_failure("auth", str(e))
                return {"actions": [{"action": "submit"}],
                        "model": "fallback",
                        "elapsed_ms": round((time.monotonic() - start) * 1000),
                        "tokens": {"total": 0}}

            except RateLimitError as e:
                self._record_failure("rate_limit", str(e))
                if attempt < RETRIES:
                    wait = min(2 ** attempt, 10)
                    time.sleep(wait)
                    continue
                return {"actions": [{"action": "submit"}],
                        "model": "fallback",
                        "elapsed_ms": round((time.monotonic() - start) * 1000),
                        "tokens": {"total": 0}}

            except (APIConnectionError, APITimeoutError) as e:
                self._record_failure("network", str(e))
                if attempt < RETRIES:
                    wait = min(2 ** attempt, 10)
                    time.sleep(wait)
                    continue
                return {"actions": [{"action": "submit"}],
                        "model": "fallback",
                        "elapsed_ms": round((time.monotonic() - start) * 1000),
                        "tokens": {"total": 0}}

            except Exception as e:
                self._record_failure("unknown", str(e))
                return {"actions": [{"action": "submit"}],
                        "model": "fallback",
                        "elapsed_ms": round((time.monotonic() - start) * 1000),
                        "tokens": {"total": 0}}


_default_client = None


def get_nim():
    """Get or create default NIM client."""
    global _default_client
    if _default_client is None:
        _default_client = NIMClient()
    return _default_client
