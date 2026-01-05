"""System prompts for The Refactoring Swarm agents."""

from .auditor_prompt import AUDITOR_SYSTEM_PROMPT
from .fixer_prompt import FIXER_SYSTEM_PROMPT
from .judge_prompt import JUDGE_GENERATE_PROMPT, JUDGE_VALIDATE_PROMPT

__all__ = [
    "AUDITOR_SYSTEM_PROMPT",
    "FIXER_SYSTEM_PROMPT",
    "JUDGE_GENERATE_PROMPT",
    "JUDGE_VALIDATE_PROMPT",
]
