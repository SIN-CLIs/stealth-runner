"""Semantic analysis engine using NVIDIA NIM API for OpenCode session classification."""

# BANNED METHODS — NIEMALS VERWENDEN (siehe /banned.md):
#   ❌ playstealth launch — setzt NICHT --force-renderer-accessibility
#   ❌ webauto-nodriver — ABSOLUT BANNED
#   ❌ cua-driver click (raw index) — instabil
#   ❌ --remote-allow-origins=* (ohne Quotes) — zsh glob expansion
#   ❌ /tmp/heypiggy-bot (fixed profile) — korruptiert nach Neustart
#   ❌ Hardcoded PIDs — dynamisch, niemals hardcodieren
#   ❌ pkill -f "Google Chrome" — tötet USER Chrome
#   ❌ killall Google Chrome — tötet ALLE Chrome

import os
import time
from typing import Any

import structlog
from openai import OpenAI

logger = structlog.get_logger(__name__)

# Classification categories for OpenCode sessions
# These match conventional commit types for consistency with Stealth Suite
CATEGORIES = ["fix", "new", "refactor", "doc", "test", "chore", "feat"]
import structlog

logger = structlog.get_logger(__name__)

# Classification categories for OpenCode sessions
CATEGORIES = ["fix", "new", "refactor", "doc", "test", "chore", "feat"]


class SemanticAnalyzer:
    """Analyzes OpenCode session messages and classifies them using NVIDIA NIM API.

    This class connects to the NVIDIA Nemotron 3 Nano Omni model (30B-A3B MoE)
    which is already used by the Stealth Suite for vision tasks, ensuring consistency
    across the entire toolchain.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ):
        """Initialize the semantic analyzer with NVIDIA NIM credentials.

        Args:
            api_key: NVIDIA API key (or set NVIDIA_API_KEY env var)
            base_url: NVIDIA NIM base URL (default: integrate.api.nvidia.com/v1)
            model: Model to use (default: nvidia/nemotron-3-nano-omni-30b-a3b-reasoning)
        """
        self.api_key = api_key or os.getenv("NVIDIA_API_KEY")
        self.base_url = base_url or os.getenv(
            "NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"
        )
        self.model = model or os.getenv(
            "NVIDIA_MODEL", "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"
        )
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        logger.info("Initialized SemanticAnalyzer", model=self.model)

    def classify_session(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        """Classify an OpenCode session based on its messages.

        Uses NVIDIA NIM API to analyze the session content and categorize it
        into one of the predefined CATEGORIES.

        Args:
            messages: List of message dictionaries from the OpenCode database

        Returns:
            Dictionary with 'category' and 'confidence' keys
        """
        prompt = self._build_classification_prompt(messages)
        try:
            # Call NVIDIA NIM API with low temperature for consistent classification
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=200,
            )
            classification = response.choices[0].message.content.strip()
            return self._parse_classification(classification)
        except Exception as e:
            logger.error("Classification failed", error=str(e))
            return {"category": "unknown", "confidence": 0.0}

    def _build_classification_prompt(self, messages: list[dict[str, Any]]) -> str:
        """Build a prompt for NVIDIA NIM to classify the OpenCode session.

        This method extracts the role and content from the first 10 messages
        to create a compact prompt. The prompt asks the LLM to categorize
        into exactly one of the predefined CATEGORIES.

        Args:
            messages: List of message dictionaries from OpenCode DB

        Returns:
            A formatted prompt string ready for the NVIDIA NIM API
        """
        # Extract text from first 10 messages to keep prompt compact
        msg_text = "\n".join(
            [f"{m.get('role', 'unknown')}: {m.get('content', '')}" for m in messages[:10]]
        )
        # Build classification prompt with clear category definitions
        return f"""
Classify the following OpenCode session into ONE of these categories:
- fix: Bug fixes, error corrections
- new: New features, new functions
- refactor: Code restructuring, cleanup
- doc: Documentation updates
- test: Adding or updating tests
- chore: Maintenance tasks
- feat: Major feature implementations

Session messages:
{msg_text}

Return ONLY the category name, nothing else.
"""
        msg_text = "\n".join(
            [f"{m.get('role', 'unknown')}: {m.get('content', '')}" for m in messages[:10]]
        )
        return f"""
Classify the following OpenCode session into ONE of these categories:
- fix: Bug fixes, error corrections
- new: New features, new functions
- refactor: Code restructuring, cleanup
- doc: Documentation updates
- test: Adding or updating tests
- chore: Maintenance tasks
- feat: Major feature implementations

Session messages:
{msg_text}

Return ONLY the category name, nothing else.
"""

    def _parse_classification(self, text: str) -> dict[str, Any]:
        """Parse the classification response from NVIDIA NIM API.

        The LLM should return just the category name, but we handle
        cases where it might return additional text by checking if any
        known category appears in the response.

        Args:
            text: Raw text response from the NVIDIA NIM API

        Returns:
            Dictionary with 'category' and 'confidence' keys
        """
        # Normalize and check for known categories
        text = text.lower().strip()
        for cat in CATEGORIES:
            if cat in text:
                return {"category": cat, "confidence": 0.9}
        # Fallback for unrecognized responses
        return {"category": "unknown", "confidence": 0.0}
        text = text.lower().strip()
        for cat in CATEGORIES:
            if cat in text:
                return {"category": cat, "confidence": 0.9}
        return {"category": "unknown", "confidence": 0.0}

    def generate_doc_unit(
        self, session_id: str, messages: list[dict[str, Any]], classification: dict[str, Any]
    ) -> dict[str, Any]:
        """Generate a structured documentation unit from session analysis.

        This method creates a comprehensive documentation unit that includes
        session metadata, classification results, message statistics, and
        a summary. This unit can be serialized to YAML or JSON.

        Args:
            session_id: The OpenCode session ID (e.g., ses_XYZ)
            messages: List of message dictionaries from the session
            classification: Classification result from classify_session()

        Returns:
            A dictionary representing the documentation unit
        """
        return {
            "session_id": session_id,
            "timestamp": time.time(),  # Current time as fallback
            "classification": classification,
            "message_count": len(messages),
            "summary": self._summarize_messages(messages),
        }
        """Generate a structured documentation unit."""
        return {
            "session_id": session_id,
            "timestamp": time.time() if False else None,
            "classification": classification,
            "message_count": len(messages),
            "summary": self._summarize_messages(messages),
        }

    def _summarize_messages(self, messages: list[dict[str, Any]]) -> str:
        """Create a brief summary of the session messages.

        In a production system, this would call NVIDIA NIM to generate
        a proper summary. For now, it returns a simple message count.

        Args:
            messages: List of message dictionaries

        Returns:
            A human-readable summary string
        """
        # TODO: Replace with actual NVIDIA NIM summarization
        return f"Session with {len(messages)} messages"
        """Summarize session messages."""
        return f"Session with {len(messages)} messages"
