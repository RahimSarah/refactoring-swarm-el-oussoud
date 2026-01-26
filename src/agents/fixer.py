"""
Fixer Agent for The Refactoring Swarm.

The Fixer reads refactoring plans and applies fixes to code files.
"""

import hashlib
import logging
import re
from typing import Dict, Any, List, Optional

from src.agents.base import BaseAgent
from src.agents.mixins import FileReadMixin, ContentCleaningMixin
from src.llm.base import LLMProvider
from src.prompts.fixer_prompt import FIXER_SYSTEM_PROMPT
from src.tools.file_ops import read_file, write_file
from src.tools.pylint_tool import run_pylint, format_pylint_issues
from src.utils.logger import ActionType
from src.utils.logging_config import format_agent_message

logger = logging.getLogger(__name__)


class FixerAgent(BaseAgent, FileReadMixin, ContentCleaningMixin):
    """
    Fixer Agent that applies code fixes based on the refactoring plan.

    The Fixer:
    1. Reads the refactoring plan from the Auditor
    2. Reads error logs from the Judge (if any)
    3. Applies fixes to each file
    4. Runs Pylint to verify improvements
    """

    def __init__(self, llm: LLMProvider, target_dir: str):
        """
        Initialize the Fixer agent.

        Args:
            llm: LLM provider for code generation
            target_dir: Directory containing code to fix
        """
        super().__init__(llm=llm, name="Fixer", target_dir=target_dir)
        self._expected_files: List[str] = []

    def fix(
        self,
        plan: str,
        files: List[str],
        error_logs: Optional[List[str]] = None,
        previous_attempts: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Apply fixes based on the refactoring plan.

        Args:
            plan: Markdown refactoring plan from the Auditor
            files: List of files to potentially fix
            error_logs: Previous error logs from the Judge (if any)
            previous_attempts: Previous fix attempts to avoid repetition (SPEC 3.2)

        Returns:
            Dict with keys:
                - pylint_current: Current Pylint score after fixes
                - files_modified: List of modified files
                - fix_attempts: New fix attempts for tracking
        """
        error_logs = error_logs or []
        previous_attempts = previous_attempts or []
        self._expected_files = files

        # Read current file contents
        file_contents = self._read_files(files)

        # Build context for the LLM
        user_prompt = self._build_prompt(
            plan, file_contents, error_logs, previous_attempts
        )

        # Determine action type based on context
        if error_logs:
            action_type = ActionType.DEBUG
            self._logger.info(
                format_agent_message(
                    self.name, f"Analyzing {len(error_logs)} error logs"
                )
            )
        else:
            action_type = ActionType.FIX
            self._logger.info(
                format_agent_message(self.name, "Analyzing refactoring plan")
            )

        self._logger.info(f"Input: {len(files)} files to fix")

        # Call LLM to generate fixes
        response = self.call_llm(
            system_prompt=FIXER_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            action_type=action_type,
            extra_details={
                "files_to_fix": files,
                "has_error_logs": bool(error_logs),
            },
        )

        self._logger.info(f"Received fix response ({len(response)} chars)")

        # Parse LLM response and extract fixed files
        fixed_files = self._parse_response(response)

        if fixed_files:
            self._logger.info(f"Identified {len(fixed_files)} files to modify")
            for file_path in fixed_files.keys():
                self._logger.debug(f"  - {file_path}")
        else:
            self._logger.warning("No file modifications found in response")

        # Apply fixes
        files_modified = self._apply_fixes(fixed_files)

        # Record fix attempts for tracking (SPEC 3.2)
        new_attempts = self._record_fix_attempts(fixed_files)

        # Calculate new Pylint score
        pylint_current = self._calculate_current_score(files)

        return {
            "pylint_current": pylint_current,
            "files_modified": files_modified,
            "fix_attempts": new_attempts,
        }

    def _build_prompt(
        self,
        plan: str,
        file_contents: Dict[str, str],
        error_logs: List[str],
        previous_attempts: List[Dict[str, Any]],
    ) -> str:
        """Build the user prompt for the LLM with line numbers."""
        parts = [
            "# Refactoring Plan",
            plan,
            "",
            "# Current File Contents",
        ]

        for file_path, content in file_contents.items():
            parts.append(f"## File: {file_path}")
            parts.append("```python")
            # Add line numbers for consistency with Auditor/Judge
            parts.append(self._format_with_line_numbers(content))
            parts.append("```")
            parts.append("")

        if error_logs:
            parts.append("# Previous Error Logs (MUST FIX THESE)")
            for log in error_logs[-3:]:  # Only include last 3 errors
                parts.append(log)
            parts.append("")

        if previous_attempts:
            parts.append("# Previous Fix Attempts (DO NOT REPEAT)")
            for attempt in previous_attempts[-5:]:  # Last 5 attempts
                parts.append(
                    f"- Iteration {attempt.get('iteration', '?')}: {attempt.get('issue', 'unknown')}"
                )
            parts.append("")

        parts.append("# Instructions")
        parts.append("Fix all issues in the files above.")
        parts.append("Output COMPLETE fixed files using the format specified.")
        parts.append("Do NOT include line number prefixes in your output.")

        return "\n".join(parts)

    def _parse_response(self, response: str) -> Dict[str, str]:
        """Parse LLM response to extract fixed file contents with fallback."""
        fixed_files = {}

        # Multiple patterns to try (case-insensitive)
        patterns = [
            r"###\s*FILE:\s*([^\n]+)\n```python\n(.*?)```",
            r"##\s*FILE:\s*([^\n]+)\n```python\n(.*?)```",
            r"###\s*[Ff]ile:\s*([^\n]+)\n```python\n(.*?)```",
            r"##\s*[Ff]ile:\s*([^\n]+)\n```python\n(.*?)```",
            r"\*\*[Ff]ile:\*\*\s*`?([^\n`]+)`?\n```python\n(.*?)```",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, response, re.DOTALL | re.IGNORECASE)
            if matches:
                for file_path, content in matches:
                    file_path = file_path.strip()
                    # Clean content to remove any line number prefixes
                    content = self._clean_content(content.strip())
                    if content:
                        fixed_files[file_path] = content
                break

        # Fallback: Match code blocks to expected files
        if not fixed_files and self._expected_files:
            code_pattern = r"```python\n(.*?)```"
            code_matches = re.findall(code_pattern, response, re.DOTALL)

            if len(code_matches) == len(self._expected_files):
                self._logger.warning(
                    "Using fallback: matching code blocks to files by order"
                )
                for file_path, content in zip(self._expected_files, code_matches):
                    cleaned = self._clean_content(content.strip())
                    if cleaned:
                        fixed_files[file_path] = cleaned
            elif len(code_matches) == 1 and len(self._expected_files) == 1:
                # Single file case
                cleaned = self._clean_content(code_matches[0].strip())
                if cleaned:
                    fixed_files[self._expected_files[0]] = cleaned

        return fixed_files

    def _record_fix_attempts(self, fixed_files: Dict[str, str]) -> List[Dict[str, Any]]:
        """Record fix attempts for tracking (SPEC 3.2)."""
        attempts = []
        for file_path, content in fixed_files.items():
            fix_hash = hashlib.sha256(f"{file_path}:{content}".encode()).hexdigest()[
                :16
            ]
            attempts.append(
                {
                    "file": file_path,
                    "issue": "fix_applied",
                    "fix_hash": fix_hash,
                    "iteration": 0,  # Will be set by the node
                }
            )
        return attempts

    def _apply_fixes(self, fixed_files: Dict[str, str]) -> List[str]:
        """Apply fixes to files."""
        modified = []

        if not fixed_files:
            self._logger.warning("No files to modify")
            return modified

        self._logger.info(f"Applying fixes to {len(fixed_files)} files")

        for file_path, content in fixed_files.items():
            try:
                # CRITICAL: Never modify test files - only source files
                if (
                    "tests/" in file_path
                    or "tests\\" in file_path
                    or file_path.startswith("test_")
                ):
                    self._logger.warning(f"SKIPPED {file_path} (test file)")
                    continue

                write_file(file_path, content, self.target_dir)
                modified.append(file_path)
                self._logger.info(f"Updated {file_path} ({len(content)} bytes)")

                self.log_tool_action(
                    action_type=ActionType.FIX,
                    command=f"write_file('{file_path}', ...)",
                    output=f"File {file_path} updated ({len(content)} bytes)",
                    extra_details={"file_modified": file_path},
                )

            except FileNotFoundError as e:
                self._logger.error(f"File not found: {file_path}")
                self.log_tool_action(
                    action_type=ActionType.FIX,
                    command=f"write_file('{file_path}', ...)",
                    output=f"ERROR: File not found - {e}",
                    status="FAILURE",
                    extra_details={"file": file_path, "error": str(e)},
                )
            except PermissionError as e:
                self._logger.error(f"Permission denied: {file_path}")
                self.log_tool_action(
                    action_type=ActionType.FIX,
                    command=f"write_file('{file_path}', ...)",
                    output=f"ERROR: Permission denied - {e}",
                    status="FAILURE",
                    extra_details={"file": file_path, "error": str(e)},
                )
            except OSError as e:
                self._logger.error(f"OS error writing {file_path}: {e}")
                self.log_tool_action(
                    action_type=ActionType.FIX,
                    command=f"write_file('{file_path}', ...)",
                    output=f"ERROR: {e}",
                    status="FAILURE",
                    extra_details={"file": file_path, "error": str(e)},
                )

        return modified

    def _calculate_current_score(self, files: List[str]) -> float:
        """Calculate the current average Pylint score."""
        if not files:
            return 10.0

        scores = []
        for file_path in files:
            result = run_pylint(file_path)
            scores.append(result.score)

            # Log Pylint verification
            self.log_tool_action(
                action_type=ActionType.ANALYSIS,
                command=f"pylint {file_path} (verification)",
                output=format_pylint_issues(result),
                extra_details={
                    "file": file_path,
                    "score": result.score,
                },
            )

        return sum(scores) / len(scores)
