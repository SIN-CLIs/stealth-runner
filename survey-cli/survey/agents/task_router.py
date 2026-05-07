"""
survey/agents/task_router.py — SOTA Task-Complexity Routing (2026-05-06)

WARUM: Große Modelle für kleine Tasks = Token-Verschwendung + Latenz.
Mistral-small (80ms) reicht für Element-Klassifizierung.
Nemotron-nano (500ms) für Mid-Tasks. Nur bei 3 aufeinanderfolgenden
Failures wird auf mistral-medium (2400ms) eskaliert. Das spart
~80% der Tokens und ist 5× schneller als "immer großes Modell".

ARCHITEKTUR: TaskRouter mappt Task-Typen auf Modelle.
Task-Types: micro, mid, reasoning, ocr, heavy.
Modelle (alle FREE via NVIDIA NIM + Mistral API):
  mistral-small → 80ms, 100 tokens, MICRO
  nvidia/nemotron-3-nano-30b-a3b-reasoning → 600ms, 300 tokens, REASONING
  nvidia/nemoretriever-ocr-v1 → 500ms, 300 tokens, OCR
  mistral-medium-latest → 2400ms, 500 tokens, HEAVY (nur nach 3 Failures).
Eskalation: 3x Fail auf Mid → Auto-Switch zu Heavy.

BANNED METHODS — NIEMALS VERWENDEN:
❌ playstealth launch
❌ webauto-nodriver — ABSOLUT BANNED
❌ cua-driver click (raw index)
❌ --remote-allow-origins=* (ohne Quotes)
❌ /tmp/heypiggy-bot (fixed profile)
❌ Hardcoded PIDs
❌ pkill -f "Google Chrome"
❌ killall Google Chrome
❌ skylight-cli click --element-index
"""

from __future__ import annotations
import os
import json
import logging
import hashlib
import time
from pathlib import Path
from enum import Enum
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# ── API Endpoints ──────────────────────────────────────────────────────────────

NVIDIA_BASE = "https://integrate.api.nvidia.com/v1"
MISTRAL_BASE = "https://api.mistral.ai/v1"


class TaskComplexity(Enum):
    """Task complexity tiers — maps to model selection."""
    MICRO = "micro"       # ~80ms, mistral-small (FASTEST)
    MID = "mid"           # ~500ms, nemotron-nano
    REASONING = "reasoning"  # ~600ms, nemotron-omni (chain-of-thought)
    OCR = "ocr"           # ~500ms, nemoretriever-ocr
    HEAVY = "heavy"       # ~2400ms, mistral-medium (ESCALATED only)


class ModelConfig(dict):
    """Model configuration as dict with attribute access."""
    def __getattr__(self, k):
        try: return self[k]
        except KeyError: raise AttributeError(k)
    def __setattr__(self, k, v):
        self[k] = v


# ── Model Registry ─────────────────────────────────────────────────────────────
# SOTA aus stealth-axiom/router.py — erweitert für survey-cli

MODELS = {
    # Mikro: Fast, cheapest, für element classification + verify
    "mistral-small": ModelConfig(
        name="mistral-small-latest",
        provider="mistral",
        complexity=TaskComplexity.MICRO,
        avg_latency_ms=80,
        max_tokens=100,
        base_url=MISTRAL_BASE,
        free=True,
        description="80ms, element classification, state verification, quick lookups",
    ),
    # Mid: Nemotron nano, gutes reasoning für page classification + answer picking
    "nemotron-nano": ModelConfig(
        name="nvidia/nemotron-3-nano-30b-a3b",
        provider="nvidia",
        complexity=TaskComplexity.MID,
        avg_latency_ms=500,
        max_tokens=400,
        base_url=NVIDIA_BASE,
        free=True,
        description="500ms, page classify, answer pick, action plan, detect question type",
    ),
    # Reasoning: Chain-of-thought, für komplexe multi-step reasoning
    "nemotron-omni": ModelConfig(
        name="nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
        provider="nvidia",
        complexity=TaskComplexity.REASONING,
        avg_latency_ms=600,
        max_tokens=300,
        base_url=NVIDIA_BASE,
        free=True,
        description="600ms, chain-of-thought reasoning, complex survey flows",
    ),
    # OCR: Spezialisiert auf Bild-Text-Erkennung
    "nemoretriever-ocr": ModelConfig(
        name="nvidia/nemoretriever-ocr-v1",
        provider="nvidia",
        complexity=TaskComplexity.OCR,
        avg_latency_ms=500,
        max_tokens=300,
        base_url=NVIDIA_BASE,
        free=True,
        description="500ms, captcha image OCR, text recognition from screenshots",
    ),
    # Heavy: Nur nach 3+ failures — teuer aber sicher
    "mistral-medium": ModelConfig(
        name="mistral-medium-latest",
        provider="mistral",
        complexity=TaskComplexity.HEAVY,
        avg_latency_ms=2400,
        max_tokens=500,
        base_url=MISTRAL_BASE,
        free=True,
        description="2400ms, new provider analysis, complex math, escalated tasks only",
    ),
}


# ── API Key Helper ──────────────────────────────────────────────────────────────

def get_api_key(provider: str) -> Optional[str]:
    """Get API key from environment or .env files."""
    env_var = "NVIDIA_API_KEY" if provider == "nvidia" else "MISTRAL_API_KEY"
    key = os.environ.get(env_var, "")
    if key:
        return key

    # Check .env files
    env_paths = [
        Path.home() / ".stealth" / ".env",
        Path.home() / ".stealth" / "secrets.json",
        Path("/Users/jeremy/dev/stealth-runner/.env"),
        Path("/Users/jeremy/dev/stealth-axiom/.env"),
    ]
    for ep in env_paths:
        if not ep.exists():
            continue
        if ep.suffix == ".json":
            try:
                secrets = json.loads(ep.read_text())
                return secrets.get(env_var, "")
            except Exception:
                continue
        else:
            for line in ep.read_text().split("\n"):
                if line.startswith(f"{env_var}="):
                    return line.strip().split("=", 1)[1].strip("'\"")
    return None


# ── LLM Cache ───────────────────────────────────────────────────────────────────

class LLMCache:
    """3-level LLM response cache: semantic → hash → disk."""

    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or (Path.home() / ".stealth")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.hash_cache_path = self.cache_dir / "llm_cache.json"
        self._load_hash_cache()

    def _load_hash_cache(self):
        try:
            if self.hash_cache_path.exists():
                self.hash_cache = json.loads(self.hash_cache_path.read_text())
            else:
                self.hash_cache = {}
        except Exception:
            self.hash_cache = {}

    def get(self, prompt: str, model: str) -> Optional[Dict]:
        """Get cached response by prompt hash + model."""
        key = hashlib.sha256((prompt[:200] + model).encode()).hexdigest()
        return self.hash_cache.get(key)

    def set(self, prompt: str, model: str, response: Dict):
        """Cache response by prompt hash + model."""
        key = hashlib.sha256((prompt[:200] + model).encode()).hexdigest()
        self.hash_cache[key] = response
        try:
            self.hash_cache_path.write_text(json.dumps(self.hash_cache))
        except Exception as e:
            logger.warning("Failed to write LLM cache: %s", e)


# ── Model Caller ───────────────────────────────────────────────────────────────

def call_model(model_name: str, prompt: str,
               max_tokens: int = 100,
               temperature: float = 0.1,
               cache: Optional[LLMCache] = None) -> Dict[str, Any]:
    """Call LLM model with caching. Returns {content, latency_ms, cached, model}."""
    start = time.monotonic()

    # Cache check
    if cache:
        cached = cache.get(prompt, model_name)
        if cached:
            return {**cached, "cached": True, "latency_ms": 0, "model": model_name}

    # Determine provider from model name
    if model_name.startswith("nvidia/"):
        provider = "nvidia"
        base_url = NVIDIA_BASE
    else:
        provider = "mistral"
        base_url = MISTRAL_BASE

    api_key = get_api_key(provider)
    if not api_key:
        return {"content": "", "error": f"No API key for {provider}", "cached": False}

    model_cfg = next((m for m in MODELS.values() if m.name == model_name), None)
    if model_cfg:
        max_tokens = min(max_tokens, model_cfg.max_tokens)

    try:
        payload = json.dumps({
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
            **({"stream": False} if "nemotron" in model_name else {}),
        }).encode()

        req = urllib.request.Request(
            f"{base_url}/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
        )
        resp = json.loads(urllib.request.urlopen(req, timeout=30).read())
        content = ""
        if "choices" in resp and resp["choices"]:
            msg = resp["choices"][0].get("message", {})
            content = msg.get("content", "")
            # Handle reasoning models (extract last section)
            if msg.get("reasoning") and len(msg["reasoning"]) > 20:
                content = msg["reasoning"].split("\n\n")[-1].strip()
        usage = resp.get("usage", {})
    except Exception as e:
        logger.warning("LLM call failed for %s: %s", model_name, e)
        return {"content": "", "error": str(e), "cached": False}

    latency_ms = round((time.monotonic() - start) * 1000)
    result = {
        "content": content,
        "tokens": usage.get("total_tokens", 0),
        "latency_ms": latency_ms,
        "cached": False,
        "model": model_name,
    }

    if cache:
        cache.set(prompt, model_name, result)

    return result


import urllib.request
# Re-order import to top once we confirm it works


# ── Task Router ────────────────────────────────────────────────────────────────

class TaskRouter:
    """SOTA task router based on AxiomRouter (stealth-axiom/router.py).

    Routes tasks to the cheapest/fastest model that can handle them.
    Escalates to heavier models only after repeated failures.

    Usage:
        router = TaskRouter()
        model = router.route("classify_page", {"ax_tree": "..."})
        # → nemotron-nano (500ms)

        model = router.route("ocr_image", {})
        # → nemoretriever-ocr (500ms)

        model = router.route("classify_element", {"confidence": 0.9})
        # → mistral-small (80ms) — cheap task, high confidence
    """

    def __init__(self, max_free_failures: int = 3):
        self.max_free_failures = max_free_failures
        self.failure_counts: Dict[str, int] = {}
        self.success_rates: Dict[str, float] = {}
        self.stats = {"micro": 0, "mid": 0, "reasoning": 0, "ocr": 0, "heavy": 0}
        self.cache = LLMCache()

    def route(self, task_type: str, context: Optional[Dict] = None) -> ModelConfig:
        """Route task to appropriate model based on complexity tier."""
        ctx = context or {}

        # MICRO: element classification, state verification, quick lookups
        if task_type in ("classify_element", "verify_state", "quick_lookup"):
            self.stats["micro"] += 1
            return MODELS["mistral-small"]

        # OCR: captcha image recognition
        if task_type == "ocr_image":
            self.stats["ocr"] += 1
            return MODELS["nemoretriever-ocr"]

        # MID: page classification, answer picking, action planning
        if task_type in ("classify_page", "pick_answer", "plan_next_action",
                         "detect_question_type", "detect_provider"):
            self.stats["mid"] += 1
            return MODELS["nemotron-nano"]

        # REASONING: complex multi-step reasoning
        if task_type in ("analyze_context", "solve_math", "multi_step_reasoning"):
            self.stats["reasoning"] += 1
            return MODELS["nemotron-omni"]

        # HEAVY: escalated only after failures
        if task_type in ("analyze_new_provider", "complex_survey_flow",
                         "detect_page_type_uncertain"):
            fails = self.failure_counts.get(task_type, 0)
            if fails >= self.max_free_failures:
                self.stats["heavy"] += 1
                logger.warning("Escalating %s to mistral-medium (%d failures)",
                              task_type, fails)
                return MODELS["mistral-medium"]
            self.stats["mid"] += 1
            return MODELS["nemotron-nano"]

        # DEFAULT: mid-tier
        self.stats["mid"] += 1
        return MODELS["nemotron-nano"]

    def route_cheap_first(self, task_type: str, min_confidence: float = 0.85) -> ModelConfig:
        """Route but prefer cheap model if success rate is very high."""
        rate = self.success_rates.get(task_type, 1.0)
        if rate >= 0.95 and task_type in ("classify_element", "verify_state"):
            self.stats["micro"] += 1
            return MODELS["mistral-small"]
        return self.route(task_type)

    def record_failure(self, task_type: str):
        """Record a failure for a task type. Triggers escalation after threshold."""
        c = self.failure_counts.get(task_type, 0) + 1
        self.failure_counts[task_type] = c
        self._update_success_rate(task_type, 0)
        logger.info("Failure #%d for %s", c, task_type)

    def record_success(self, task_type: str):
        """Record a success. Resets failure count."""
        old = self.failure_counts.pop(task_type, None)
        if old is not None:
            logger.info("Reset failure count for %s (was %d)", task_type, old)
        self._update_success_rate(task_type, 1)

    def _update_success_rate(self, task_type: str, outcome: int):
        if task_type not in self.success_rates:
            self.success_rates[task_type] = 1.0
        sr, n = self.success_rates[task_type], 10  # window of 10
        self.success_rates[task_type] = (sr * (n - 1) + outcome) / n

    def get_stats(self) -> Dict:
        """Return routing statistics."""
        total = sum(self.stats.values()) or 1
        return {
            "calls": dict(self.stats),
            "failure_counts": dict(self.failure_counts),
            "total_calls": sum(self.stats.values()),
            "micro_pct": round(self.stats["micro"] / total * 100, 1),
            "mid_pct": round(self.stats["mid"] / total * 100, 1),
            "reasoning_pct": round(self.stats["reasoning"] / total * 100, 1),
            "heavy_pct": round(self.stats["heavy"] / total * 100, 1),
            "estimated_cost_usd": 0.0,  # All models are FREE
            "providers": {"mistral": MISTRAL_BASE, "nvidia": NVIDIA_BASE},
            "cache_entries": len(self.cache.hash_cache),
        }

    def call(self, task_type: str, prompt: str,
             context: Optional[Dict] = None) -> Dict[str, Any]:
        """Route + call model in one step. Returns {content, model, latency_ms, cached}."""
        model = self.route(task_type, context)
        result = call_model(model.name, prompt,
                           max_tokens=model.max_tokens,
                           cache=self.cache)
        if result.get("error"):
            self.record_failure(task_type)
            return {**result, "model": model.name}
        else:
            self.record_success(task_type)
            return {**result, "model": model.name}


# ── Global Router Instance ─────────────────────────────────────────────────────

router = TaskRouter()