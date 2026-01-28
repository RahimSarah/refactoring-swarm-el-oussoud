"""
Configuration management for The Refactoring Swarm.

This module provides centralized configuration with environment variable support.
Uses dependency injection pattern instead of global mutable state.
"""

import os
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.llm.base import LLMProvider


@dataclass
class Config:
    """Configuration settings for The Refactoring Swarm."""

    # LLM Configuration
    llm_provider: str = "mistral"
    llm_model: str = "mistral-large-latest"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 8192

    # Iteration limits
    max_iterations: int = 10

    # Timeouts (seconds)
    pylint_timeout: int = 30
    test_timeout: int = 60
    llm_timeout: int = 120

    # API Keys (loaded from environment)
    google_api_key: Optional[str] = field(default=None, repr=False)
    mistral_api_key: Optional[str] = field(default=None, repr=False)

    @classmethod
    def from_env(cls) -> "Config":
        """Create configuration from environment variables."""
        return cls(
            llm_provider=os.getenv("LLM_PROVIDER", "mistral"),
            llm_model=os.getenv("LLM_MODEL", "mistral-large-latest"),
            llm_temperature=float(os.getenv("LLM_TEMPERATURE", "0.7")),
            llm_max_tokens=int(os.getenv("LLM_MAX_TOKENS", "4096")),
            max_iterations=int(os.getenv("MAX_ITERATIONS", "10")),
            pylint_timeout=int(os.getenv("PYLINT_TIMEOUT", "30")),
            test_timeout=int(os.getenv("TEST_TIMEOUT", "60")),
            llm_timeout=int(os.getenv("LLM_TIMEOUT", "120")),
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            mistral_api_key=os.getenv("MISTRAL_API_KEY"),
        )

    def validate(self) -> None:
        """Validate configuration. Raises ValueError if invalid."""
        if self.llm_provider == "gemini" and not self.google_api_key:
            raise ValueError(
                "GOOGLE_API_KEY not set. Please set it in your .env file or environment."
            )
        if self.llm_provider == "mistral" and not self.mistral_api_key:
            raise ValueError(
                "MISTRAL_API_KEY not set. Please set it in your .env file or environment."
            )
        if self.max_iterations < 1:
            raise ValueError("max_iterations must be at least 1")
        if self.llm_temperature < 0 or self.llm_temperature > 1:
            raise ValueError("llm_temperature must be between 0 and 1")

    def get_llm_provider(self) -> "LLMProvider":
        """
        Create and return an LLM provider based on configuration.

        This method implements dependency injection - the Config object
        creates the LLM provider rather than using global state.

        Returns:
            Configured LLM provider instance
        """
        from src.llm import get_llm_provider

        api_key = (
            self.mistral_api_key
            if self.llm_provider == "mistral"
            else self.google_api_key
        )

        return get_llm_provider(
            provider=self.llm_provider,
            api_key=api_key or "",
            model=self.llm_model,
        )


# === DEPRECATED: Global state functions ===
# These are kept for backward compatibility but should be migrated to
# passing Config explicitly via dependency injection.

_config: Optional[Config] = None


def get_config() -> Config:
    """
    Get the global configuration instance, creating it if necessary.

    DEPRECATED: Prefer passing Config explicitly via dependency injection.
    This function is kept for backward compatibility during migration.
    """
    global _config
    if _config is None:
        _config = Config.from_env()
    return _config


def set_config(config: Config) -> None:
    """
    Set the global configuration instance.

    DEPRECATED: Prefer passing Config explicitly via dependency injection.
    This function is kept for backward compatibility during migration.
    """
    global _config
    _config = config
