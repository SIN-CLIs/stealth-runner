"""Provider registry for survey-specific adapters."""

from __future__ import annotations

from importlib import import_module
from typing import Dict

from .base import CompletionState, ProviderAdapter
from .generic import GenericAdapter


_ADAPTERS = {
    "qualtrics": ("survey.providers.qualtrics", "QualtricsAdapter"),
    "toluna": ("survey.providers.toluna", "TolunaAdapter"),
    "tolunastart": ("survey.providers.toluna", "TolunaAdapter"),
    "strat7": ("survey.providers.strat7", "Strat7Adapter"),
    "purespectrum": ("survey.providers.purespectrum", "PureSpectrumAdapter"),
}


def get_provider_adapter(provider: str) -> ProviderAdapter:
    """Return the adapter for provider, falling back to GenericAdapter."""
    key = (provider or "generic").lower()
    target = _ADAPTERS.get(key)
    if not target:
        return GenericAdapter()
    module_name, class_name = target
    module = import_module(module_name)
    return getattr(module, class_name)()


def get_provider_commands(provider: str) -> Dict[str, str]:
    """Return provider command templates for BatchExecutor."""
    return get_provider_adapter(provider).get_commands()


def detect_provider_completion(provider: str, text: str, url: str = "") -> CompletionState:
    """Classify completion state through the provider adapter."""
    return get_provider_adapter(provider).detect_completion(text, url)


__all__ = [
    "CompletionState",
    "ProviderAdapter",
    "get_provider_adapter",
    "get_provider_commands",
    "detect_provider_completion",
]
