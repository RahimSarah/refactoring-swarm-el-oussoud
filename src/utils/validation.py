"""
Output validation utilities for LLM responses.

Provides validation for code fixes, test files, and refactoring plans
to catch malformed responses before they are applied.
"""

import ast
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class ValidationResult:
    """Result of validating LLM output."""

    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.is_valid


def validate_python_syntax(code: str, filename: str = "<unknown>") -> ValidationResult:
    """
    Validate that code is syntactically correct Python.

    Args:
        code: Python code to validate
        filename: Filename for error messages

    Returns:
        ValidationResult with syntax errors if any
    """
    errors = []
    warnings = []

    if not code.strip():
        return ValidationResult(is_valid=False, errors=["Empty code"])

    try:
        ast.parse(code)
    except SyntaxError as e:
        errors.append(f"Syntax error in {filename}: {e.msg} (line {e.lineno})")
    except Exception as e:
        errors.append(f"Parse error in {filename}: {str(e)}")

    # Check for common LLM artifacts that shouldn't be in code
    llm_artifacts = [
        (r"^\s*```", "Code block markers (```) found in code"),
        (r"###\s*FILE:", "File header markers found in code"),
        (r"^\s*\d+\s*\|", "Line numbers found in code output"),
    ]

    for pattern, message in llm_artifacts:
        if re.search(pattern, code, re.MULTILINE):
            warnings.append(message)

    return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)


def validate_fix_response(
    response: str, expected_files: Optional[List[str]] = None
) -> ValidationResult:
    """
    Validate a Fixer agent response.

    Checks that:
    - Response contains valid file markers
    - Code blocks are properly formatted
    - Each code block is valid Python syntax

    Args:
        response: Raw LLM response from Fixer
        expected_files: Optional list of files that should be fixed

    Returns:
        ValidationResult with any issues found
    """
    errors = []
    warnings = []

    if not response.strip():
        return ValidationResult(is_valid=False, errors=["Empty response"])

    # Check for file markers
    file_pattern = r"###?\s*FILE:\s*([^\n]+)\n```python\n(.*?)```"
    matches = re.findall(file_pattern, response, re.DOTALL | re.IGNORECASE)

    if not matches:
        # Try alternative patterns
        alt_pattern = r"\*\*File:\*\*\s*`?([^`\n]+)`?\n```python\n(.*?)```"
        matches = re.findall(alt_pattern, response, re.DOTALL)

    if not matches:
        errors.append("No valid file/code blocks found in response")
        return ValidationResult(is_valid=False, errors=errors)

    # Validate each code block
    found_files = []
    for filename, code in matches:
        filename = filename.strip()
        found_files.append(filename)

        # Validate syntax
        result = validate_python_syntax(code, filename)
        errors.extend(result.errors)
        warnings.extend(result.warnings)

    # Check if expected files are present
    if expected_files:
        missing = set(expected_files) - set(found_files)
        if missing:
            warnings.append(f"Expected files not in response: {missing}")

    return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)


def validate_test_response(response: str) -> ValidationResult:
    """
    Validate a Judge agent test generation response.

    Checks that:
    - Response contains test file markers
    - Test files follow pytest conventions
    - Code is valid Python syntax

    Args:
        response: Raw LLM response from Judge (test generation)

    Returns:
        ValidationResult with any issues found
    """
    errors = []
    warnings = []

    if not response.strip():
        return ValidationResult(is_valid=False, errors=["Empty response"])

    # Check for file markers
    file_pattern = r"###?\s*FILE:\s*([^\n]+)\n```python\n(.*?)```"
    matches = re.findall(file_pattern, response, re.DOTALL | re.IGNORECASE)

    if not matches:
        errors.append("No valid test file blocks found in response")
        return ValidationResult(is_valid=False, errors=errors)

    for filename, code in matches:
        filename = filename.strip()

        # Check test file naming convention
        basename = filename.split("/")[-1]
        if not basename.startswith("test_"):
            warnings.append(f"Test file '{filename}' doesn't start with 'test_'")

        # Validate syntax
        result = validate_python_syntax(code, filename)
        errors.extend(result.errors)
        warnings.extend(result.warnings)

        # Check for test functions
        if "def test_" not in code:
            warnings.append(f"No test functions found in {filename}")

        # Check for pytest import if fixtures used
        if "@pytest" in code and "import pytest" not in code:
            warnings.append(
                f"pytest fixtures used but pytest not imported in {filename}"
            )

    return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)


def validate_plan_response(response: str) -> ValidationResult:
    """
    Validate an Auditor agent refactoring plan response.

    Checks that:
    - Response has markdown structure
    - Contains required sections
    - Has actionable items

    Args:
        response: Raw LLM response from Auditor

    Returns:
        ValidationResult with any issues found
    """
    errors = []
    warnings = []

    if not response.strip():
        return ValidationResult(is_valid=False, errors=["Empty response"])

    # Check for minimum content
    if len(response) < 50:
        warnings.append("Plan seems too short to be useful")

    # Check for markdown headers
    if not re.search(r"^#+\s+", response, re.MULTILINE):
        warnings.append("No markdown headers found in plan")

    # Check for common plan sections (any of these)
    plan_indicators = [
        r"##?\s*(Summary|Overview)",
        r"##?\s*(Issue|Bug|Problem)",
        r"##?\s*(File|Module)",
        r"##?\s*(Priority|Severity)",
        r"##?\s*(Fix|Solution|Recommendation)",
    ]

    found_sections = sum(
        1 for p in plan_indicators if re.search(p, response, re.IGNORECASE)
    )

    if found_sections < 2:
        warnings.append("Plan may be missing important sections")

    return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)


def sanitize_code_output(code: str) -> str:
    """
    Clean common LLM artifacts from code output.

    Removes:
    - Line number prefixes
    - Code block markers
    - File header comments that shouldn't be in final code

    Args:
        code: Code that may contain artifacts

    Returns:
        Cleaned code
    """
    lines = code.split("\n")
    cleaned = []

    for line in lines:
        # Skip code block markers
        if line.strip().startswith("```"):
            continue

        # Remove line number prefixes
        match = re.match(r"^\s*\d+\s*\|\s?(.*)$", line)
        if match:
            cleaned.append(match.group(1))
        else:
            cleaned.append(line)

    return "\n".join(cleaned)
