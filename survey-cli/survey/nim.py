"""NVIDIA NIM Client — Nemotron 3 Omni survey decisions.

Reuses OpenAI-compatible API pattern. Returns batch actions.
Falls back to simple auto-pilot when NIM is unavailable.
"""

import json
import os
import time
import re
from openai import OpenAI
from typing import Dict, List, Any, Optional

# ── Constants ──────────────────────────────────────────

DEFAULT_MODEL = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"
DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"
MAX_TOKENS = 800
RETRIES = 3

ACTION_TYPES = ["click", "fill", "select", "check", "wait", "submit", "skip"]

SYSTEM_PROMPT = """You are an ultra-fast survey-filling agent. Analyze a compact DOM snapshot and decide the next batch of actions.

RULES:
1. Match question text to user profile data.
2. Return ONLY a JSON array of batch actions.
3. Use @eN element references from snapshot.
4. NEVER write code or explanations. Just JSON.
5. Batch independent actions together.
6. On completion text, return [{"action": "complete"}].

ACTIONS:
- {"ref": "@eN", "action": "click"}     — Click element
- {"ref": "@eN", "action": "fill", "value": "text"}  — Fill text field
- {"ref": "@eN", "action": "select"}    — Select radio/checkbox
- {"ref": "@eN", "action": "check"}     — Toggle checkbox
- {"action": "wait", "ms": 800}         — Wait
- {"action": "submit"}                  — Click next/submit
- {"action": "complete"}                — Survey done"""


# ── Prompt Builder ─────────────────────────────────────

def build_survey_prompt(
    snapshot: Dict[str, Any],
    profile: Dict[str, Any],
    learnings: Optional[List[str]] = None,
    history: Optional[List[Dict]] = None,
) -> str:
    """Build token-efficient prompt for Nemotron."""
    parts = []

    # Compact element list (truncated to 30)
    refs = snapshot.get("refs", {})
    elements_str = json.dumps(dict(list(refs.items())[:30]), indent=2, ensure_ascii=False)
    if len(refs) > 30:
        elements_str += f"\n... ({len(refs) - 30} more truncated)"

    questions = snapshot.get("semantic", {}).get("questions", [])
    progress = snapshot.get("semantic", {}).get("progress", "?")

    parts.append(f"## Snapshot ({snapshot.get('provider', '?')}, progress {progress})")
    parts.append(f"```json\n{elements_str}\n```")

    if questions:
        parts.append(f"\n## Questions\n{json.dumps(questions, ensure_ascii=False)}")

    # Profile (key fields only)
    profile_fields = {
        "age": profile.get("age"),
        "gender": profile.get("gender_label"),
        "city": profile.get("city"),
        "state": profile.get("state"),
        "education": profile.get("education"),
        "employment": profile.get("employment_label"),
        "income": profile.get("household_income"),
    }
    profile_fields = {k: v for k, v in profile_fields.items() if v}
    parts.append(f"\n## Profile\n{json.dumps(profile_fields, indent=2)}")

    # Learnings
    if learnings:
        parts.append("\n## Learnings\n" + "\n".join(f"- {l}" for l in learnings[:5]))

    # Recent actions
    if history:
        recent = history[-3:]
        parts.append(f"\n## Recent\n{json.dumps(recent, indent=2)}")

    parts.append("\nReturn ONLY JSON array of actions.")
    return "\n".join(parts)


# ── Response Parser ────────────────────────────────────

def parse_response(raw: str) -> List[Dict[str, Any]]:
    """Parse LLM response into action list."""
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
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    return [{"action": "error", "raw": raw[:200]}]


# ── NIM Client ─────────────────────────────────────────

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
               temperature=0.1):
        """Decide next batch actions.

        Args:
            snapshot: Dict from snapshot generator
            profile: User profile dict
            learnings: Optional list of learnings
            history: Optional recent action history
            temperature: LLM temperature

        Returns:
            Dict with actions, raw_response, tokens, elapsed_ms
        """
        if not self.client:
            return {"actions": self._simple_actions(snapshot),
                    "model": "auto_pilot", "elapsed_ms": 0,
                    "tokens": {"total": 0}}

        prompt = build_survey_prompt(snapshot, profile, learnings, history)

        start = time.monotonic()
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=temperature,
                max_tokens=MAX_TOKENS,
            )
            elapsed = time.monotonic() - start
            raw = response.choices[0].message.content.strip()
            actions = parse_response(raw)

            return {
                "actions": actions,
                "raw_response": raw,
                "model": self.model,
                "elapsed_ms": round(elapsed * 1000),
                "tokens": {
                    "prompt": response.usage.prompt_tokens if response.usage else 0,
                    "completion": response.usage.completion_tokens if response.usage else 0,
                    "total": response.usage.total_tokens if response.usage else 0,
                },
            }
        except Exception as e:
            elapsed = time.monotonic() - start
            return {"actions": self._simple_actions(snapshot),
                    "model": f"fallback_{e}",
                    "elapsed_ms": round(elapsed * 1000),
                    "tokens": {"total": 0}}

    def _simple_actions(self, snapshot):
        """Simple auto-pilot fallback."""
        actions = []

        # Select first radio/checkbox
        for ref, info in snapshot.get("refs", {}).items():
            if info.get("role") in ("radio", "checkbox") and info.get("enabled", True):
                actions.append({"ref": ref, "action": "select"})
                break

        # Find submit/next button
        for ref, info in snapshot.get("refs", {}).items():
            if info.get("role") == "button":
                text = info.get("text", "").lower()
                if any(kw in text for kw in ["weiter", "next", "submit", "nächste"]):
                    actions.append({"action": "submit"})
                    break
        else:
            # Fallback: first button
            for ref, info in snapshot.get("refs", {}).items():
                if info.get("role") == "button":
                    actions.append({"ref": ref, "action": "click"})
                    break

        if not actions:
            actions.append({"action": "submit"})

        return actions


# ── Singleton ──────────────────────────────────────────

_default_client = None


def get_nim():
    """Get or create default NIM client."""
    global _default_client
    if _default_client is None:
        _default_client = NIMClient()
    return _default_client
