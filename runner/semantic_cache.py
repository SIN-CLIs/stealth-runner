"""Semantic Vision Cache via diskcache."""
from __future__ import annotations
from diskcache import Cache
cache = Cache("/tmp/stealth_cache")

def get_cached_action(image_hash: str) -> dict | None: return cache.get(image_hash)
def set_cached_action(image_hash: str, action: dict) -> None: cache.set(image_hash, action, expire=3600)
