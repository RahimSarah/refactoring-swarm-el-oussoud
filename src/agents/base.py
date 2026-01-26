"""
Base agent class for The Refactoring Swarm.

Provides common functionality for all agents including LLM calls and logging.
"""

import logging
from typing import Optional, Tuple

from src.llm.base import Message, LLMProvider, LLMResponse
from src.utils.logger import log_experiment, ActionType
from src.utils.logging_config import get_agent_logger, format_agent_message


class BaseAgent:
    """Base class for all agents in The Refactoring Swarm."""

    # Context management constants
    MAX_CONTEXT_CHARS = 100000  # ~25k tokens
    CHARS_PER_TOKEN = 4  # Rough estimate

    def __init__(
        self,
        llm: LLMProvider,
        name: str,
        target_dir: str,
    ):
        """
        Initialize the base agent.

        Args:
            llm: LLM provider for generating responses
            name: Agent name for logging (e.g., "Auditor", "Fixer", "Judge")
            target_dir: Target directory for file operations
        """
        self.llm = llm
        self.name = name
        self.target_dir = target_dir
        self._logger = get_agent_logger(name)

    def call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        action_type: ActionType,
        extra_details: Optional[dict] = None,
    ) -> str:
        """
        Call the LLM with automatic logging.

        Args:
            system_prompt: System instructions for the LLM
            user_prompt: User request/context
            action_type: Type of action for logging
            extra_details: Additional details to include in logs

        Returns:
            LLM response content as string
        """
        self._logger.info(
            format_agent_message(self.name, f"Calling LLM ({action_type.value})")
        )
        self._logger.debug(f"System prompt preview: {system_prompt[:150]}...")
        self._logger.debug(f"User prompt preview: {user_prompt[:150]}...")

        # Prepare messages
        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_prompt),
        ]

        full_prompt = f"[SYSTEM]\n{system_prompt}\n\n[USER]\n{user_prompt}"

        try:
            response: LLMResponse = self.llm.complete(messages)
            output = response.content

            self._logger.info(
                format_agent_message(
                    self.name, f"LLM response received ({len(output)} chars)"
                )
            )
            self._logger.debug(f"Response preview: {output[:150]}...")

            details = {
                "input_prompt": full_prompt,
                "output_response": output,
            }
            if extra_details:
                details.update(extra_details)

            log_experiment(
                agent_name=self.name,
                model_used=self.llm.model_name,
                action=action_type,
                details=details,
                status="SUCCESS",
            )

            return output

        except Exception as e:
            error_msg = str(e)
            self._logger.error(
                format_agent_message(self.name, f"LLM call failed: {error_msg}")
            )

            details = {
                "input_prompt": full_prompt,
                "output_response": f"ERROR: {error_msg}",
                "error": error_msg,
            }
            if extra_details:
                details.update(extra_details)

            log_experiment(
                agent_name=self.name,
                model_used=self.llm.model_name,
                action=action_type,
                details=details,
                status="FAILURE",
            )

            raise

    def log_tool_action(
        self,
        action_type: ActionType,
        command: str,
        output: str,
        status: str = "SUCCESS",
        extra_details: Optional[dict] = None,
    ) -> None:
        """
        Log a tool execution (non-LLM action).

        Args:
            action_type: Type of action for logging
            command: Command or tool that was executed
            output: Output from the tool
            status: "SUCCESS" or "FAILURE"
            extra_details: Additional details to include in logs
        """
        details = {
            "input_prompt": command,
            "output_response": output,
        }
        if extra_details:
            details.update(extra_details)

        log_experiment(
            agent_name=self.name,
            model_used="N/A",  # No LLM involved
            action=action_type,
            details=details,
            status=status,
        )

    def _truncate_context(self, content: str, max_chars: int) -> Tuple[str, bool]:
        """
        Truncate content if too long for context window.

        Args:
            content: Content to potentially truncate
            max_chars: Maximum allowed characters

        Returns:
            Tuple of (content, was_truncated)
        """
        if len(content) <= max_chars:
            return content, False

        # Keep first 60% and last 30%
        keep_start = int(max_chars * 0.6)
        keep_end = int(max_chars * 0.3)

        truncated = (
            content[:keep_start]
            + f"\n\n... [TRUNCATED {len(content) - max_chars} chars] ...\n\n"
            + content[-keep_end:]
        )

        self._logger.warning(
            f"Context truncated from {len(content)} to {len(truncated)} chars"
        )

        return truncated, True
