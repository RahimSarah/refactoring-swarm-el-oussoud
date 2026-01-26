"""
Shared mixins for agent functionality.

These mixins provide common functionality used across multiple agents.
"""

import logging
import re
from typing import Dict, List, Optional

from src.tools.file_ops import read_file

logger = logging.getLogger(__name__)


class FileReadMixin:
    """
    Mixin providing file reading functionality for agents.

    This mixin extracts the common file reading pattern used by
    Auditor, Fixer, and Judge agents.
    """

    target_dir: str  # Type hint for mixin - must be set by the using class

    def _read_files(self, files: List[str]) -> Dict[str, str]:
        """
        Read contents of multiple files with error handling.

        Args:
            files: List of file paths to read

        Returns:
            Dictionary mapping file paths to their contents.
            On error, the value will be an error message string.
        """
        contents = {}
        for file_path in files:
            try:
                content = read_file(file_path, self.target_dir)
                contents[file_path] = content
            except FileNotFoundError:
                logger.warning(f"File not found: {file_path}")
                contents[file_path] = f"ERROR: File not found - {file_path}"
            except PermissionError:
                logger.error(f"Permission denied: {file_path}")
                contents[file_path] = f"ERROR: Permission denied - {file_path}"
            except OSError as e:
                logger.error(f"OS error reading {file_path}: {e}")
                contents[file_path] = f"ERROR: OS error - {e}"
        return contents


class ContentCleaningMixin:
    """
    Mixin providing content cleaning functionality.

    Used to clean LLM output that may contain line numbers
    or other artifacts from the input format.
    """

    def _clean_content(self, content: str) -> str:
        """
        Remove line numbers if LLM accidentally included them in output.

        Args:
            content: Content that may contain line number prefixes

        Returns:
            Cleaned content without line number prefixes
        """
        lines = content.split("\n")
        cleaned = []
        for line in lines:
            # Remove line number prefix like "   1 | " or "42 | "
            match = re.match(r"^\s*\d+\s*\|\s?(.*)$", line)
            if match:
                cleaned.append(match.group(1))
            else:
                cleaned.append(line)
        return "\n".join(cleaned)

    def _format_with_line_numbers(self, content: str) -> str:
        """
        Add line numbers to content for LLM input.

        Args:
            content: Content to add line numbers to

        Returns:
            Content with line numbers in format "   1 | line content"
        """
        lines = content.split("\n")
        numbered = [f"{i + 1:4d} | {line}" for i, line in enumerate(lines)]
        return "\n".join(numbered)
