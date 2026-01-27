"""
Mistral AI LLM provider implementation.

This module provides integration with Mistral's AI models via their official API.
Includes retry logic with exponential backoff for resilience.
"""

import logging
import time
from functools import wraps
from typing import List, Optional, Callable, TypeVar

from mistralai import Mistral

from .base import Message, LLMResponse, LLMProvider

logger = logging.getLogger(__name__)

T = TypeVar("T")


def with_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exceptions: tuple = (Exception,),
) -> Callable:
    """
    Retry decorator with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries (seconds)
        max_delay: Maximum delay between retries (seconds)
        exceptions: Tuple of exception types to catch and retry

    Returns:
        Decorated function with retry logic
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        delay = min(base_delay * (2**attempt), max_delay)
                        logger.warning(
                            f"LLM call failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                            f"Retrying in {delay:.1f}s..."
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            f"LLM call failed after {max_retries + 1} attempts: {e}"
                        )
            raise last_exception  # type: ignore

        return wrapper

    return decorator


class MistralProvider:
    """Mistral AI LLM provider with retry logic."""

    def __init__(
        self,
        api_key: str,
        model: str = "mistral-large-latest",
    ):
        """
        Initialize Mistral provider.

        Args:
            api_key: Mistral API key
            model: Model name (default: mistral-large-latest)
        """
        self._client = Mistral(api_key=api_key)
        self._model_name = model

    @property
    def model_name(self) -> str:
        """Return the model identifier for logging."""
        return self._model_name

    @with_retry(max_retries=3, base_delay=1.0, max_delay=30.0)
    def complete(
        self,
        messages: List[Message],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """
        Generate completion from messages with automatic retry.

        Args:
            messages: List of conversation messages
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens to generate

        Returns:
            LLMResponse with generated content
        """
        # Convert Message objects to Mistral's expected format
        mistral_messages = [
            {"role": msg.role, "content": msg.content} for msg in messages
        ]

        response = self._client.chat.complete(
            model=self._model_name,
            messages=mistral_messages,  # type: ignore
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # Extract content safely
        content = "[Empty response from model]"
        if response and response.choices and len(response.choices) > 0:
            choice = response.choices[0]
            if choice.message and choice.message.content:
                msg_content = choice.message.content
                # Handle both str and List[ContentChunk]
                if isinstance(msg_content, str):
                    content = msg_content
                else:
                    # ContentChunk list - extract text
                    content = "".join(
                        chunk.text if hasattr(chunk, "text") else str(chunk)
                        for chunk in msg_content
                    )

        # Extract usage info
        usage = {}
        if hasattr(response, "usage") and response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        return LLMResponse(
            content=content,
            model=self._model_name,
            usage=usage,
        )


def get_mistral_provider(
    api_key: Optional[str] = None, model: str = "mistral-large-latest"
) -> LLMProvider:
    """
    Factory function to create a Mistral LLM provider.

    Args:
        api_key: Mistral API key (if None, reads from environment)
        model: Model name to use

    Returns:
        Configured Mistral LLM provider
    """
    import os

    if api_key is None:
        api_key = os.getenv("MISTRAL_API_KEY")

    if not api_key:
        raise ValueError(
            "MISTRAL_API_KEY not set. Please set it in your .env file or pass it directly."
        )

    return MistralProvider(api_key=api_key, model=model)
