"""
Logging configuration for The Refactoring Swarm.

This module provides centralized logging setup to replace print statements.
"""

import logging
import sys
from typing import Optional


def configure_logging(
    level: str = "INFO",
    format_string: Optional[str] = None,
    include_timestamp: bool = True,
) -> None:
    """
    Configure application-wide logging.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_string: Custom format string (optional)
        include_timestamp: Whether to include timestamps in log messages
    """
    if format_string is None:
        if include_timestamp:
            format_string = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
        else:
            format_string = "%(levelname)-8s | %(name)s | %(message)s"

    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format=format_string,
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
        force=True,  # Override any existing configuration
    )

    # Set specific log levels for noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def get_agent_logger(agent_name: str) -> logging.Logger:
    """
    Get a logger for a specific agent.

    Args:
        agent_name: Name of the agent (e.g., "Auditor", "Fixer", "Judge")

    Returns:
        Configured logger for the agent
    """
    return logging.getLogger(f"swarm.agent.{agent_name.lower()}")


def get_tool_logger(tool_name: str) -> logging.Logger:
    """
    Get a logger for a specific tool.

    Args:
        tool_name: Name of the tool (e.g., "pylint", "pytest")

    Returns:
        Configured logger for the tool
    """
    return logging.getLogger(f"swarm.tool.{tool_name.lower()}")


def get_llm_logger() -> logging.Logger:
    """
    Get a logger for LLM interactions.

    Returns:
        Configured logger for LLM calls
    """
    return logging.getLogger("swarm.llm")


# Agent-specific emoji for visual distinction in logs
AGENT_EMOJI = {
    "auditor": "🔍",
    "fixer": "🔧",
    "judge": "⚖️",
    "system": "🖥️",
}


def format_agent_message(agent_name: str, message: str) -> str:
    """
    Format a message with agent-specific emoji prefix.

    Args:
        agent_name: Name of the agent
        message: Message to format

    Returns:
        Formatted message with emoji prefix
    """
    emoji = AGENT_EMOJI.get(agent_name.lower(), "📋")
    return f"{emoji} [{agent_name}] {message}"
