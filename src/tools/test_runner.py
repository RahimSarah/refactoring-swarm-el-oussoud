"""
Test runner tool for executing pytest.

This module provides functionality to run pytest and parse its output.
"""

import subprocess
import re
import os
import sys
from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class TestResult:
    """Result of a test execution."""

    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    total: int = 0
    success: bool = False
    output: str = ""
    failures: List[Dict[str, Any]] = field(
        default_factory=list
    )  # Detailed failure info


def run_tests(path: str, timeout: int = 60) -> TestResult:
    """
    Execute pytest on target directory.

    Args:
        path: Directory containing tests
        timeout: Max execution time in seconds

    Returns:
        TestResult with pass/fail counts and details

    Raises:
        TimeoutError: If tests hang
    """
    # Check if tests directory exists
    tests_dir = os.path.join(path, "tests")
    if not os.path.exists(tests_dir):
        return TestResult(
            passed=0,
            failed=0,
            errors=0,
            skipped=0,
            total=0,
            success=True,  # No tests = considered success for first run
            output="No tests directory found",
            failures=[],
        )

    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "tests",
                "-v",
                "--tb=short",
                "-q",
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=path,
            env={**os.environ, "PYTHONPATH": path},
        )

        # Parse the output
        return _parse_pytest_output(
            result.stdout + "\n" + result.stderr, result.returncode
        )

    except subprocess.TimeoutExpired:
        return TestResult(
            passed=0,
            failed=1,
            errors=0,
            skipped=0,
            total=1,
            success=False,
            output=f"Tests timed out after {timeout} seconds",
            failures=[
                {
                    "test": "TIMEOUT",
                    "message": f"Test execution exceeded {timeout}s limit",
                }
            ],
        )
    except FileNotFoundError:
        return TestResult(
            passed=0,
            failed=0,
            errors=1,
            skipped=0,
            total=0,
            success=False,
            output="pytest not found. Please install pytest.",
            failures=[{"test": "SETUP", "message": "pytest command not found"}],
        )
    except Exception as e:
        return TestResult(
            passed=0,
            failed=0,
            errors=1,
            skipped=0,
            total=1,
            success=False,
            output=f"Error running tests: {str(e)}",
            failures=[{"test": "SETUP", "message": str(e)}],
        )


def _parse_pytest_output(output: str, return_code: int) -> TestResult:
    """Parse pytest output to extract test counts and failures."""
    passed = 0
    failed = 0
    errors = 0
    skipped = 0
    failures = []

    # Look for summary line like "5 passed, 2 failed, 1 error"
    # or "===== 3 passed in 0.12s ====="
    summary_patterns = [
        r"(\d+) passed",
        r"(\d+) failed",
        r"(\d+) error",
        r"(\d+) skipped",
    ]

    for pattern in summary_patterns:
        match = re.search(pattern, output, re.IGNORECASE)
        if match:
            count = int(match.group(1))
            if "passed" in pattern:
                passed = count
            elif "failed" in pattern:
                failed = count
            elif "error" in pattern:
                errors = count
            elif "skipped" in pattern:
                skipped = count

    # Extract individual failures
    # Look for patterns like "FAILED test_file.py::test_name - AssertionError"
    failure_pattern = (
        r"FAILED\s+(\S+)\s*[-:]\s*(.*?)(?=\n(?:FAILED|PASSED|ERROR|=====)|$)"
    )
    failure_matches = re.findall(failure_pattern, output, re.DOTALL)

    for test_name, error_msg in failure_matches:
        failures.append(
            {
                "test": test_name.strip(),
                "message": error_msg.strip()[:500],  # Limit message length
            }
        )

    # Also look for assertion errors in the output
    assertion_pattern = (
        r"(test_\w+).*?AssertionError:\s*(.*?)(?=\n\n|\nFAILED|\n=====|$)"
    )
    assertion_matches = re.findall(assertion_pattern, output, re.DOTALL | re.IGNORECASE)

    for test_name, error_msg in assertion_matches:
        if not any(f["test"].endswith(test_name) for f in failures):
            failures.append(
                {
                    "test": test_name.strip(),
                    "message": f"AssertionError: {error_msg.strip()[:500]}",
                }
            )

    total = passed + failed + errors + skipped
    success = return_code == 0 and failed == 0 and errors == 0

    return TestResult(
        passed=passed,
        failed=failed,
        errors=errors,
        skipped=skipped,
        total=total,
        success=success,
        output=output,
        failures=failures,
    )


def format_test_results(result: TestResult) -> str:
    """Format test results as a readable string for the LLM."""
    lines = [
        f"Test Results: {result.passed} passed, {result.failed} failed, {result.errors} errors",
        f"Total: {result.total} | Success: {result.success}",
    ]

    if result.failures:
        lines.append("")
        lines.append("Failures:")
        for failure in result.failures:
            lines.append(f"  - {failure['test']}: {failure['message'][:200]}")

    if not result.success and not result.failures:
        lines.append("")
        lines.append("Output excerpt:")
        lines.append(result.output[:1000])

    return "\n".join(lines)
