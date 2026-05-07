"""================================================================================
NIM CLIENT — Nemotron 3 Omni API für Survey-Entscheidungen
================================================================================

WAS IST DAS?
  Client für NVIDIA NIM API (Nemotron 3 Nano Omni 30B). Analysiert Compact
  Snapshots und gibt Batch-Actions zurück (click, fill, select, submit, ...).

ARCHITEKTUR:
  ┌─────────────────────┐
  │  build_survey_prompt │
  │  (Snapshot + Profile)│
  └─────────────────────┘
         │
         ▼
  ┌─────────────────────┐
  │  NIMSurveyClient    │
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
  │  JSON Batch Actions │
  │  [{"ref":"@e0",...}]│
  └─────────────────────┘

WARUM Nemotron 3 Omni?
  - 30B-A3B Mixture-of-Experts (Video + Audio + Bild + Text)
  - 256K Kontext (ganze Survey-Sessions in einem Call)
  - SSE Streaming (tokenweise Antwort)
  - Spezialisiert auf Entscheidungen mit wenig Tokens

WARUM OpenAI-Client-Pattern?
  NVIDIA NIM ist OpenAI-kompatibel (v1/chat/completions).
  → Nutzen existierende openai Library statt custom HTTP.
  → Wiederverwendbar, getestet, dokumentiert.

KONFIGURATION:
  API Key: $NVIDIA_API_KEY (Prefix: nvapi-...)
  Model: nvidia/nemotron-3-nano-omni-30b-a3b-reasoning
  Base URL: https://integrate.api.nvidia.com/v1

DEPENDENZEN:
  - openai (pip install openai)
  - tenacity (pip install tenacity) — Retry-Logik
  - $NVIDIA_API_KEY muss gesetzt sein

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

import os
import json
import time
from typing import Dict, List, Any, Optional
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

# ── Constants ──────────────────────────────────────────

DEFAULT_MODEL = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"
DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"
MAX_RETRIES = 3
DEFAULT_TEMPERATURE = 0.1
MAX_TOKENS = 800

# Available batch action types
ACTION_TYPES = ["click", "fill", "select", "check", "wait", "submit", "skip"]

# ── Prompts ────────────────────────────────────────────

SURVEY_SYSTEM_PROMPT = """You are an ultra-fast survey-filling agent. Your task is to analyze a compact DOM snapshot and decide the next batch of actions.

RULES:
1. Look at the survey question text and the available elements.
2. Match the question to the user profile data provided.
3. Return ONLY a JSON array of batch actions.
4. Use element references like @e0, @e1 from the snapshot.
5. NEVER write code. NEVER explain. Just return JSON.
6. Batch multiple actions together when they are independent.
7. Use "wait" action only when necessary (between pages).
8. If you see "Zurück zur Website" or completion text, return [{"action": "complete"}].

AVAILABLE ACTIONS:
- {"ref": "@eN", "action": "click"}     — Click an element
- {"ref": "@eN", "action": "fill", "value": "text"}  — Fill a text field
- {"ref": "@eN", "action": "select"}    — Select a radio/checkbox
- {"ref": "@eN", "action": "check"}     — Toggle a checkbox
- {"action": "wait", "ms": 800}         — Wait milliseconds
- {"action": "submit"}                  — Click the submit/next button
- {"action": "complete"}                — Survey is done"""


def build_survey_prompt(
    snapshot: Dict[str, Any],
    profile: Dict[str, Any],
    learnings: Optional[List[str]] = None,
    session_history: Optional[List[Dict]] = None,
) -> str:
    """Build a prompt for Nemotron to decide next batch actions.

    Args:
        snapshot: Compact DOM snapshot with @eN refs
        profile: User profile data (age, gender, location, etc.)
        learnings: Previous learnings from this survey type
        session_history: Recent actions taken in this session

    Returns:
        Prompt string for the LLM
    """
    parts = []

    # Snapshot data
    elements = snapshot.get("refs", {})
    questions = snapshot.get("semantic", {}).get("questions", [])
    progress = snapshot.get("semantic", {}).get("progress", "?")
    provider = snapshot.get("semantic", {}).get("survey_type", "unknown")

    elements_str = json.dumps(elements, indent=2, ensure_ascii=False)
    if len(elements_str) > 2000:
        # Truncate if too many elements — keep most relevant
        element_list = list(elements.items())
        elements_str = json.dumps(dict(element_list[:30]), indent=2, ensure_ascii=False)
        elements_str += f"\n... ({len(element_list) - 30} more elements truncated)"

    parts.append(f"## Current Snapshot ({provider}, progress {progress})")
    parts.append(f"```json\n{elements_str}\n```")

    if questions:
        parts.append(f"\n## Detected Questions\n{json.dumps(questions, ensure_ascii=False)}")

    # Profile
    profile_fields = {
        "age": profile.get("age"),
        "gender": profile.get("gender_label"),
        "city": profile.get("city"),
        "state": profile.get("state"),
        "household_size": profile.get("household_size"),
        "employment": profile.get("employment_label"),
        "education": profile.get("education"),
        "household_income": profile.get("household_income"),
        "personal_income": profile.get("personal_income"),
        "marital_status": profile.get("marital_status"),
    }
    # Filter None values
    profile_fields = {k: v for k, v in profile_fields.items() if v}
    parts.append(f"\n## User Profile\n{json.dumps(profile_fields, indent=2)}")

    # Learnings
    if learnings:
        parts.append(f"\n## Previous Learnings\n" + "\n".join(f"- {l}" for l in learnings[:5]))

    # History (last 3 actions)
    if session_history:
        recent = session_history[-3:]
        parts.append(f"\n## Recent Actions\n{json.dumps(recent, indent=2)}")

    parts.append("\n## Instruction")
    parts.append("Return ONLY a JSON array of batch actions. No explanation, no code.")
    parts.append(f"Use @eN references. Available actions: {', '.join(ACTION_TYPES)}")

    return "\n".join(parts)


# ── Client ─────────────────────────────────────────────

class NIMSurveyClient:
    """Client for NVIDIA Nemotron 3 Omni survey decision making.

    Uses the OpenAI-compatible NVIDIA NIM API.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("NVIDIA_API_KEY")
        if not self.api_key:
            raise ValueError("NVIDIA_API_KEY not set")

        self.base_url = base_url or os.getenv(
            "NVIDIA_BASE_URL", DEFAULT_BASE_URL
        )
        self.model = model or os.getenv(
            "NVIDIA_MODEL", DEFAULT_MODEL
        )
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    @retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def decide(
        self,
        snapshot: Dict[str, Any],
        profile: Dict[str, Any],
        learnings: Optional[List[str]] = None,
        session_history: Optional[List[Dict]] = None,
        temperature: float = DEFAULT_TEMPERATURE,
    ) -> List[Dict[str, Any]]:
        """Ask Nemotron to decide the next batch of actions.

        Args:
            snapshot: Compact DOM snapshot from CompactSnapshotGenerator
            profile: User profile dict
            learnings: Previous session learnings
            session_history: Recent actions
            temperature: LLM temperature (0.0-1.0)

        Returns:
            List of action dicts: [{"ref": "@e0", "action": "click"}, ...]
        """
        prompt = build_survey_prompt(snapshot, profile, learnings, session_history)

        start_time = time.monotonic()
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SURVEY_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
            max_tokens=MAX_TOKENS,
        )
        elapsed = time.monotonic() - start_time

        raw = response.choices[0].message.content.strip()

        # Parse JSON from response (handle markdown code blocks)
        actions = self._parse_response(raw)

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

    def decide_with_tools(
        self,
        snapshot: Dict[str, Any],
        profile: Dict[str, Any],
        tools: List[Dict],
        learnings: Optional[List[str]] = None,
        session_history: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """Ask Nemotron to decide using tool-use mode.

        For when the LLM should select from structured tools.
        """
        prompt = build_survey_prompt(snapshot, profile, learnings, session_history)

        start_time = time.monotonic()
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SURVEY_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            tools=tools,
            tool_choice="auto",
            temperature=DEFAULT_TEMPERATURE,
            max_tokens=MAX_TOKENS,
        )
        elapsed = time.monotonic() - start_time

        msg = response.choices[0].message
        result = {
            "model": self.model,
            "elapsed_ms": round(elapsed * 1000),
            "tokens": {
                "total": response.usage.total_tokens if response.usage else 0,
            },
        }

        if msg.tool_calls:
            result["tool_calls"] = [
                {
                    "id": tc.id,
                    "function": tc.function.name,
                    "arguments": json.loads(tc.function.arguments),
                }
                for tc in msg.tool_calls
            ]
        else:
            result["content"] = msg.content

        return result

    @staticmethod
    def _parse_response(raw: str) -> List[Dict[str, Any]]:
        """Parse the LLM response into a list of actions.

        Handles:
        - Pure JSON array
        - JSON in markdown code blocks
        - JSON with surrounding text
        """
        raw = raw.strip()

        # Remove markdown code fences
        if raw.startswith("```"):
            lines = raw.split("\n")
            # Remove first line (```json or ```)
            if lines[0].startswith("```"):
                lines = lines[1:]
            # Remove last line if it's ```
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
            # Try to find JSON array in the text
            import re
            match = re.search(r"\[.*\]", raw, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass

        # Fallback: return as single text action
        return [{"action": "error", "raw": raw[:200]}]


# ── Batch Tool Schema for Tool-Use Mode ────────────────

BATCH_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "batch_execute",
        "description": "Execute a batch of survey actions at once",
        "parameters": {
            "type": "object",
            "properties": {
                "actions": {
                    "type": "array",
                    "description": "List of actions to execute in order",
                    "items": {
                        "type": "object",
                        "properties": {
                            "ref": {
                                "type": "string",
                                "description": "Element reference like @e0, @e1"
                            },
                            "action": {
                                "type": "string",
                                "enum": ACTION_TYPES,
                                "description": "Type of action"
                            },
                            "value": {
                                "type": "string",
                                "description": "Value to fill (for fill action)"
                            },
                            "ms": {
                                "type": "integer",
                                "description": "Milliseconds to wait (for wait action)"
                            },
                        },
                        "required": ["action"],
                    },
                }
            },
            "required": ["actions"],
        },
    },
}
