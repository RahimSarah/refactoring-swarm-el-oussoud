"""
Pylint tool for static code analysis.

This module provides functionality to run Pylint and parse its output.
"""

import subprocess
import json
import re
import sys
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class PylintResult:
    """Result of a Pylint analysis."""

    score: float  # 0.0 to 10.0
    messages: List[Dict[str, Any]] = field(default_factory=list)  # Individual issues
    raw_output: str = ""  # Complete output


def run_pylint(path: str, timeout: int = 30) -> PylintResult:
    """
    Run Pylint on file or directory.

    Args:
        path: File or directory to analyze
        timeout: Max execution time in seconds

    Returns:
        PylintResult with score and messages

    Raises:
        TimeoutError: If Pylint hangs
    """
    try:
        json_result = subprocess.run(
            [sys.executable, "-m", "pylint", path, "--output-format=json"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        messages = []
        if json_result.stdout.strip():
            try:
                messages = json.loads(json_result.stdout)
            except json.JSONDecodeError:
                json_match = re.search(r"\[.*\]", json_result.stdout, re.DOTALL)
                if json_match:
                    try:
                        messages = json.loads(json_match.group())
                    except json.JSONDecodeError:
                        pass

        text_result = subprocess.run(
            [sys.executable, "-m", "pylint", path, "--score=y"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        combined_output = text_result.stdout + "\n" + text_result.stderr
        score = _extract_score(combined_output)

        if score == 0.0 and not messages:
            score = 10.0

        return PylintResult(
            score=score,
            messages=messages if isinstance(messages, list) else [],
            raw_output=combined_output,
        )

    except subprocess.TimeoutExpired:
        return PylintResult(
            score=0.0,
            messages=[{"message": f"Pylint timed out after {timeout} seconds"}],
            raw_output=f"TIMEOUT after {timeout}s",
        )
    except FileNotFoundError:
        return PylintResult(
            score=0.0,
            messages=[{"message": "Pylint not found. Please install pylint."}],
            raw_output="ERROR: pylint command not found",
        )
    except Exception as e:
        return PylintResult(
            score=0.0,
            messages=[{"message": f"Pylint error: {str(e)}"}],
            raw_output=f"ERROR: {str(e)}",
        )


def _extract_score(output: str) -> float:
    """Extract Pylint score from output text."""
    # Look for patterns like "Your code has been rated at 7.50/10"
    # or "rated at -5.00/10" (negative scores are possible)
    patterns = [
        r"Your code has been rated at (-?\d+\.?\d*)/10",
        r"rated at (-?\d+\.?\d*)/10",
        r"score[:\s]+(-?\d+\.?\d*)/10",
        r"(-?\d+\.?\d*)/10",
    ]

    for pattern in patterns:
        match = re.search(pattern, output, re.IGNORECASE)
        if match:
            try:
                score = float(match.group(1))
                # Clamp to valid range
                return max(0.0, min(10.0, score))
            except (ValueError, IndexError):
                continue

    return 0.0


def format_pylint_issues(result: PylintResult) -> str:
    """Format Pylint issues as a readable string for the LLM."""
    if not result.messages:
        return f"No issues found. Score: {result.score}/10"

    lines = [f"Pylint Score: {result.score}/10", "", "Issues Found:"]

    for msg in result.messages:
        if isinstance(msg, dict):
            line_num = msg.get("line", "?")
            column = msg.get("column", "?")
            msg_type = msg.get("type", "unknown")
            symbol = msg.get("symbol", "")
            message = msg.get("message", "")
            module = msg.get("module", "")

            lines.append(
                f"  - [{msg_type.upper()}] Line {line_num}:{column} ({symbol}): {message}"
            )

    return "\n".join(lines)
