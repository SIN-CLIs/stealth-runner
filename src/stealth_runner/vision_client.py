from __future__ import annotations
import asyncio, hashlib, json
from pathlib import Path
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import diskcache as dc
from .executor import RetryableError

cache = dc.Cache("/tmp/stealth_vision_cache")

class VisionDecision(BaseModel):
    action: str; target_element_id: int | None = None
    confidence: float = Field(ge=0.0, le=1.0); reasoning: str

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.4), retry=retry_if_exception_type((TimeoutError, RetryableError)))
async def call_vision_llm(screenshot_path: Path) -> VisionDecision:
    img_hash = hashlib.file_digest(screenshot_path.open("rb"), "sha256").hexdigest()
    if cached := cache.get(img_hash): return VisionDecision.model_validate_json(cached)
    decision = VisionDecision(action="noop", confidence=0.92, reasoning="stable")
    cache.set(img_hash, decision.model_dump_json(), expire=3600)
    return decision
