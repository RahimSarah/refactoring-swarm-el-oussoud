"""
Google Gemini LLM provider implementation.

This module provides integration with Google's Gemini models.

.. deprecated::
    The Gemini provider is deprecated in favor of MistralProvider.
    Gemini will be removed in a future version. Please migrate to:

    from src.llm.mistral import get_mistral_provider
    llm = get_mistral_provider(api_key="your-key")
"""

import warnings
from google import genai
from google.genai import types
from typing import List, Optional

from .base import Message, LLMResponse, LLMProvider


class GeminiProvider:
    """
    Google Gemini LLM provider.

    .. deprecated::
        Use MistralProvider instead. GeminiProvider will be removed in a future version.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.0-flash-lite",
    ):
        """
        Initialize Gemini provider.

        Args:
            api_key: Google API key
            model: Model name (default: gemini-2.0-flash-lite)

        .. deprecated::
            Use MistralProvider instead.
        """
        warnings.warn(
            "GeminiProvider is deprecated and will be removed in a future version. "
            "Please migrate to MistralProvider from src.llm.mistral.",
            DeprecationWarning,
            stacklevel=2,
        )
        self._client = genai.Client(api_key=api_key)
        self._model_name = model

    @property
    def model_name(self) -> str:
        """Return the model identifier for logging."""
        return self._model_name

    def complete(
        self,
        messages: List[Message],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """
        Generate completion from messages.

        Args:
            messages: List of conversation messages
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens to generate

        Returns:
            LLMResponse with generated content
        """
        prompt = self._format_messages(messages)

        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        response = self._client.models.generate_content(
            model=self._model_name,
            contents=prompt,
            config=config,
        )

        try:
            content = response.text if response.text else "[Empty response from model]"
        except (ValueError, AttributeError):
            content = "[Response blocked by safety filters]"

        return LLMResponse(
            content=content,
            model=self._model_name,
            usage={
                "prompt_tokens": 0,
                "completion_tokens": 0,
            },
        )

    def _format_messages(self, messages: List[Message]) -> str:
        """
        Convert message list to single prompt string.

        Gemini works best with a structured prompt format.
        """
        parts = []

        for msg in messages:
            if msg.role == "system":
                parts.append(f"### Instructions ###\n{msg.content}\n")
            elif msg.role == "user":
                parts.append(f"### User Request ###\n{msg.content}\n")
            elif msg.role == "assistant":
                parts.append(f"### Previous Response ###\n{msg.content}\n")

        return "\n".join(parts)


def get_llm_provider(
    api_key: Optional[str] = None, model: str = "gemini-2.0-flash-lite"
) -> LLMProvider:
    """
    Factory function to create an LLM provider.

    .. deprecated::
        Use get_mistral_provider from src.llm.mistral instead.

    Args:
        api_key: Google API key (if None, reads from environment)
        model: Model name to use

    Returns:
        Configured LLM provider
    """
    import os

    warnings.warn(
        "get_llm_provider from gemini.py is deprecated. "
        "Use get_mistral_provider from src.llm.mistral instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    if api_key is None:
        api_key = os.getenv("GOOGLE_API_KEY")

    if not api_key:
        raise ValueError(
            "GOOGLE_API_KEY not set. Please set it in your .env file or pass it directly."
        )

    return GeminiProvider(api_key=api_key, model=model)
