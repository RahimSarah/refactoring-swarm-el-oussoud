"""LLM provider abstraction for The Refactoring Swarm."""

from typing import Optional
from .base import Message, LLMResponse, LLMProvider
from .gemini import GeminiProvider, get_llm_provider as get_gemini_provider
from .mistral import MistralProvider, get_mistral_provider


def get_llm_provider(
    provider: str,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> LLMProvider:
    """
    Factory to create LLM provider based on configuration.

    Args:
        provider: Provider name ("gemini" or "mistral")
        api_key: API key for the provider
        model: Model name to use

    Returns:
        Configured LLM provider

    Raises:
        ValueError: If provider is not supported
    """
    if provider == "gemini":
        return get_gemini_provider(
            api_key=api_key, model=model or "gemini-2.0-flash-lite"
        )
    elif provider == "mistral":
        return get_mistral_provider(
            api_key=api_key, model=model or "mistral-large-latest"
        )
    else:
        raise ValueError(
            f"Unsupported LLM provider: {provider}. Supported: 'gemini', 'mistral'"
        )


__all__ = [
    "Message",
    "LLMResponse",
    "LLMProvider",
    "GeminiProvider",
    "MistralProvider",
    "get_llm_provider",
]
