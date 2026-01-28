"""
Unified file formatting utilities for consistent LLM prompt generation.

Provides standardized formatting for code files in prompts across all agents.
This ensures consistent line number formats, code block styling, and context
structure that the LLM can reliably parse.
"""

import os
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class FormattedFile:
    """A file formatted for LLM consumption."""

    path: str
    content: str
    numbered_content: str
    line_count: int

    @property
    def module_name(self) -> str:
        """Extract module name from file path."""
        basename = os.path.basename(self.path)
        return os.path.splitext(basename)[0]


class FileFormatter:
    """
    Unified file formatter for LLM prompts.

    Provides consistent formatting across all agents:
    - Auditor: Formats files for code analysis
    - Judge: Formats files for test generation
    - Fixer: Formats files for code fixes

    The format uses:
    - 4-digit right-aligned line numbers
    - Pipe separator with space
    - Example: "   1 | def foo():"
    """

    LINE_NUMBER_FORMAT = "{:4d} | {}"

    def __init__(self, target_dir: str):
        """
        Initialize formatter with target directory.

        Args:
            target_dir: Base directory for file operations
        """
        self.target_dir = target_dir

    def format_file(self, content: str, filename: str = "") -> FormattedFile:
        """
        Format a single file's content with line numbers.

        Args:
            content: Raw file content
            filename: Optional filename for metadata

        Returns:
            FormattedFile with original and numbered content
        """
        lines = content.split("\n")
        numbered_lines = [
            self.LINE_NUMBER_FORMAT.format(i + 1, line) for i, line in enumerate(lines)
        ]

        return FormattedFile(
            path=filename,
            content=content,
            numbered_content="\n".join(numbered_lines),
            line_count=len(lines),
        )

    def format_files(self, files: Dict[str, str]) -> Dict[str, FormattedFile]:
        """
        Format multiple files.

        Args:
            files: Dictionary mapping paths to content

        Returns:
            Dictionary mapping paths to FormattedFile objects
        """
        return {
            path: self.format_file(content, path) for path, content in files.items()
        }

    def build_code_context(
        self,
        files: Dict[str, str],
        include_line_numbers: bool = True,
        max_lines_per_file: Optional[int] = None,
    ) -> str:
        """
        Build a formatted context string for multiple files.

        This is the primary method for generating file context in prompts.

        Args:
            files: Dictionary mapping file paths to content
            include_line_numbers: Whether to add line numbers
            max_lines_per_file: Optional limit on lines per file

        Returns:
            Formatted context string ready for LLM prompt
        """
        parts = []

        for path, content in files.items():
            formatted = self.format_file(content, path)

            parts.append(f"## File: {path}")

            if include_line_numbers:
                display_content = formatted.numbered_content
            else:
                display_content = content

            # Truncate if needed
            if max_lines_per_file and formatted.line_count > max_lines_per_file:
                lines = display_content.split("\n")[:max_lines_per_file]
                display_content = "\n".join(lines)
                display_content += f"\n... (truncated, {formatted.line_count - max_lines_per_file} more lines)"

            parts.append("```python")
            parts.append(display_content)
            parts.append("```")
            parts.append("")

        return "\n".join(parts)

    def build_file_section(
        self,
        path: str,
        content: str,
        extra_info: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Build a formatted section for a single file.

        Args:
            path: File path
            content: File content
            extra_info: Optional additional info to include (e.g., pylint results)

        Returns:
            Formatted file section
        """
        formatted = self.format_file(content, path)

        parts = [
            f"### File: {path}",
            f"Module: `{formatted.module_name}` | Lines: {formatted.line_count}",
        ]

        if extra_info:
            for key, value in extra_info.items():
                parts.append(f"#### {key}")
                parts.append(value)

        parts.append("#### Content")
        parts.append("```python")
        parts.append(formatted.numbered_content)
        parts.append("```")
        parts.append("")

        return "\n".join(parts)

    @staticmethod
    def strip_line_numbers(content: str) -> str:
        """
        Remove line number prefixes from content.

        Useful for cleaning LLM output that may have copied line numbers.

        Args:
            content: Content that may contain line number prefixes

        Returns:
            Content with line numbers removed
        """
        import re

        lines = content.split("\n")
        cleaned = []

        for line in lines:
            # Match pattern: optional whitespace, digits, pipe, optional space
            match = re.match(r"^\s*\d+\s*\|\s?(.*)$", line)
            if match:
                cleaned.append(match.group(1))
            else:
                cleaned.append(line)

        return "\n".join(cleaned)

    @staticmethod
    def extract_code_blocks(response: str) -> List[Dict[str, str]]:
        """
        Extract code blocks from LLM response.

        Handles various formats:
        - ### FILE: path
        - ## FILE: path
        - **File:** path

        Args:
            response: Raw LLM response

        Returns:
            List of dicts with 'path' and 'content' keys
        """
        import re

        blocks = []

        # Try different patterns
        patterns = [
            r"###?\s*FILE:\s*([^\n]+)\n```python\n(.*?)```",
            r"###?\s*File:\s*([^\n]+)\n```python\n(.*?)```",
            r"\*\*File:\*\*\s*`?([^`\n]+)`?\n```python\n(.*?)```",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, response, re.DOTALL | re.IGNORECASE)
            if matches:
                for path, content in matches:
                    blocks.append(
                        {
                            "path": path.strip(),
                            "content": FileFormatter.strip_line_numbers(
                                content.strip()
                            ),
                        }
                    )
                break

        return blocks


def format_error_context(
    errors: List[str],
    max_errors: int = 10,
    prioritize_critical: bool = True,
) -> str:
    """
    Format error messages for inclusion in prompts.

    Args:
        errors: List of error messages
        max_errors: Maximum number of errors to include
        prioritize_critical: Whether to put critical errors first

    Returns:
        Formatted error context string
    """
    if not errors:
        return "No errors to display."

    if prioritize_critical:
        # Sort critical errors first
        critical_keywords = ["AssertionError", "TypeError", "ValueError"]

        def is_critical(error: str) -> bool:
            return any(kw in error for kw in critical_keywords)

        critical = [e for e in errors if is_critical(e)]
        other = [e for e in errors if not is_critical(e)]
        errors = critical + other

    # Limit errors
    if len(errors) > max_errors:
        displayed = errors[:max_errors]
        remaining = len(errors) - max_errors
        displayed.append(f"... and {remaining} more errors")
    else:
        displayed = errors

    parts = ["## Error Context", ""]
    for i, error in enumerate(displayed, 1):
        parts.append(f"{i}. {error}")

    return "\n".join(parts)
