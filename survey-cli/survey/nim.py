"""NVIDIA NIM Client v2 — Nemotron 3 Omni with Chain-of-Thought.

Key findings (2026-05-06):
- Reasoning models need chain-of-thought prompts (NOT system prompts)
- max_tokens must be ≥500 for reasoning overhead
- The model needs to "think" before outputting JSON
- Short imperative prompts ("Return ONLY JSON") cause empty responses
"""

import json
import os
import time
import re
from openai import OpenAI
from typing import Dict, List, Any, Optional

DEFAULT_MODEL = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"
DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"
MAX_TOKENS = 600
RETRIES = 3


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
    """NVIDIA Nemotron 3 Omni client for survey decisions."""

    def __init__(self, api_key=None, model=None):
        self.api_key = api_key or os.getenv("NVIDIA_API_KEY")
        self.model = model or os.getenv("NVIDIA_MODEL", DEFAULT_MODEL)
        self.client = None
        if self.api_key:
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=DEFAULT_BASE_URL
            )

    @property
    def available(self):
        return self.client is not None

    def decide(self, snapshot, profile,
               learnings=None, history=None,
               temperature=0.0):
        """Decide next batch actions with chain-of-thought.

        Returns:
            Dict with actions, tokens, elapsed_ms
        """
        if not self.client:
            return {"actions": [{"action": "submit"}],
                    "model": "auto_pilot", "elapsed_ms": 0,
                    "tokens": {"total": 0}}

        prompt = build_survey_prompt(snapshot, profile, learnings, history)

        start = time.monotonic()
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=MAX_TOKENS,
            )
            elapsed = time.monotonic() - start
            raw = response.choices[0].message.content or ""
            actions = parse_response(raw)

            return {
                "actions": actions,
                "raw_response": raw[:200],
                "model": self.model,
                "elapsed_ms": round(elapsed * 1000),
                "tokens": {
                    "total": response.usage.total_tokens if response.usage else 0,
                },
            }
        except Exception as e:
            elapsed = time.monotonic() - start
            return {"actions": [{"action": "submit"}],
                    "model": f"fallback",
                    "elapsed_ms": round(elapsed * 1000),
                    "tokens": {"total": 0}}


_default_client = None


def get_nim():
    """Get or create default NIM client."""
    global _default_client
    if _default_client is None:
        _default_client = NIMClient()
    return _default_client
