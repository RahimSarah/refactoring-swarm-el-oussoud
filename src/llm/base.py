"""
LLM provider base classes and protocols.

This module defines the abstract interface for LLM providers.
"""

from dataclasses import dataclass, field
from typing import Protocol, List, Dict, Any, runtime_checkable


@dataclass
class Message:
    """A message in a conversation with an LLM."""

    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class LLMResponse:
    """Response from an LLM provider."""

    content: str
    model: str
    usage: Dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol for LLM providers (Gemini, OpenAI, etc.)."""

    @property
    def model_name(self) -> str:
        """Return the model identifier for logging."""
        ...

    def complete(
        self,
        messages: List[Message],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Generate completion from messages."""
        ...
