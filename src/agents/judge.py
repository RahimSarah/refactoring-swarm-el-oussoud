"""
Judge Agent for The Refactoring Swarm.

The Judge has two modes:
1. Generate Tests (TDD): Create tests that validate code correctness
2. Validate: Run tests and report results
"""

import os
import re
from typing import Dict, Any, List

from src.agents.base import BaseAgent
from src.llm.base import LLMProvider
from src.prompts.judge_prompt import JUDGE_GENERATE_PROMPT
from src.tools.file_ops import read_file, write_file
from src.tools.test_runner import run_tests, format_test_results, TestResult
from src.utils.logger import ActionType


class JudgeAgent(BaseAgent):
    """
    Judge Agent that generates tests and validates fixes.

    The Judge operates in two modes:
    1. Generate Tests (TDD Phase 1):
       - Reads the refactoring plan
       - Generates pytest tests that validate correct behavior
       - Tests should FAIL on buggy code

    2. Validate (TDD Phase 2):
       - Runs the generated tests
       - Reports success or failure
       - Provides error context for the Fixer
    """

    def __init__(self, llm: LLMProvider, target_dir: str):
        """
        Initialize the Judge agent.

        Args:
            llm: LLM provider for test generation
            target_dir: Directory containing code to test
        """
        super().__init__(llm=llm, name="Judge", target_dir=target_dir)

    def _get_module_name(self, file_path: str) -> str:
        """
        Convert a file path to a module name for imports.

        This strips the target directory prefix and converts to module format.
        Example: "sandbox/cart.py" with target_dir="sandbox" -> "cart"
        Example: "src/models/user.py" with target_dir="." -> "src.models.user"
        """
        # Normalize path separators
        path = file_path.replace("\\", "/")
        target = self.target_dir.rstrip("/\\").replace("\\", "/")

        # Strip target directory prefix if present
        if path.startswith(target + "/"):
            path = path[len(target) + 1 :]
        elif path.startswith(target):
            path = path[len(target) :].lstrip("/")

        # Remove .py extension
        if path.endswith(".py"):
            path = path[:-3]

        # Convert path separators to dots for module import
        module_name = path.replace("/", ".")

        return module_name

    def generate_tests(
        self,
        plan: str,
        files: List[str],
    ) -> Dict[str, Any]:
        """
        Generate tests based on the refactoring plan (TDD Phase 1).

        Args:
            plan: Markdown refactoring plan from the Auditor
            files: List of source files to generate tests for

        Returns:
            Dict with keys:
                - generated_tests: List of generated test file paths
                - test_results: Results of running the tests
                - error_logs: Error details if tests fail
        """
        # Read source files
        file_contents = self._read_source_files(files)

        # Build context for test generation
        user_prompt = self._build_generate_prompt(plan, files, file_contents)

        print(f"\n🤔 Judge analyzing code to generate tests...")
        print(f"   Input: {len(files)} source files, refactoring plan")

        # Call LLM to generate tests
        response = self.call_llm(
            system_prompt=JUDGE_GENERATE_PROMPT,
            user_prompt=user_prompt,
            action_type=ActionType.GENERATION,
            extra_details={
                "source_files": files,
                "mode": "generate_tests",
            },
        )

        print(f"✅ Judge received test generation response ({len(response)} chars)")

        # Parse and save generated tests
        generated_tests = self._save_generated_tests(response)

        if generated_tests:
            print(f"📝 Created test files:")
            for test_file in generated_tests:
                print(f"   • {test_file}")

        # Ensure tests directory has __init__.py
        self._ensure_tests_init()

        # Run the tests (we expect them to fail on buggy code)
        test_result = self._run_tests()

        # Extract error logs for the Fixer
        error_logs = self._extract_error_logs(test_result)

        return {
            "generated_tests": generated_tests,
            "test_results": {
                "passed": test_result.passed,
                "failed": test_result.failed,
                "errors": test_result.errors,
                "total": test_result.total,
                "success": test_result.success,
            },
            "error_logs": error_logs,
            "status": "success" if test_result.success else "in_progress",
        }

    def validate(self) -> Dict[str, Any]:
        """
        Validate fixes by running tests (TDD Phase 2).

        Returns:
            Dict with keys:
                - test_results: Results of running the tests
                - error_logs: Error details if tests fail
                - status: "success" if all tests pass, "in_progress" otherwise
        """
        print(f"\n🧪 Judge running tests to validate fixes...")

        # Run the tests
        test_result = self._run_tests()

        print(f"✅ Test execution complete")
        print(f"   • Passed: {test_result.passed}")
        print(f"   • Failed: {test_result.failed}")
        print(f"   • Errors: {test_result.errors}")

        # Log the validation
        self.log_tool_action(
            action_type=ActionType.ANALYSIS,
            command=f"pytest {self.target_dir}/tests -v",
            output=test_result.output[:2000],
            extra_details={
                "passed": test_result.passed,
                "failed": test_result.failed,
                "errors": test_result.errors,
                "success": test_result.success,
            },
        )

        # Extract error logs for the Fixer
        error_logs = self._extract_error_logs(test_result)

        if error_logs:
            print(f"📋 Extracted {len(error_logs)} error messages for Fixer")

        # Determine status
        if test_result.success:
            status = "success"
            print(f"✅ Validation: SUCCESS - All tests pass!")
        elif test_result.total == 0:
            status = "error"
            print(
                f"❌ Validation: ERROR - No tests found or all tests failed to collect"
            )
            error_logs.append(
                "ERROR: No tests were collected. Test files may have import errors or were deleted."
            )
        else:
            status = "in_progress"
            print(f"❌ Validation: FAILED - Need more fixes")

        return {
            "test_results": {
                "passed": test_result.passed,
                "failed": test_result.failed,
                "errors": test_result.errors,
                "total": test_result.total,
                "success": test_result.success,
            },
            "error_logs": error_logs,
            "status": status,
        }

    def _read_source_files(self, files: List[str]) -> Dict[str, str]:
        """Read contents of source files."""
        contents = {}
        for file_path in files:
            try:
                content = read_file(file_path, self.target_dir)
                contents[file_path] = content
            except Exception as e:
                contents[file_path] = f"ERROR: {e}"
        return contents

    def _build_generate_prompt(
        self,
        plan: str,
        files: List[str],
        file_contents: Dict[str, str],
    ) -> str:
        """Build the prompt for test generation."""
        parts = [
            "# Refactoring Plan (Issues to Test)",
            plan,
            "",
            "# Source Files to Test",
            "",
            "IMPORTANT: Use these module names for imports (NOT the full file path):",
        ]

        # Build module name reference
        for file_path in files:
            module_name = self._get_module_name(file_path)
            parts.append(f"  - {file_path} -> import from `{module_name}`")

        parts.append("")

        for file_path in files:
            content = file_contents.get(file_path, "")
            module_name = self._get_module_name(file_path)

            parts.append(f"## File: {file_path}")
            parts.append(f"## Module for imports: `{module_name}`")
            parts.append("```python")

            # Add line numbers
            lines = content.split("\n")
            numbered = [f"{i + 1:4d} | {line}" for i, line in enumerate(lines)]
            parts.append("\n".join(numbered))
            parts.append("```")
            parts.append("")

        parts.append("# Instructions")
        parts.append("Generate pytest tests that:")
        parts.append("1. Test the CORRECT expected behavior (based on function names)")
        parts.append("2. Will FAIL on the buggy code shown above")
        parts.append("3. Will PASS once the code is fixed correctly")
        parts.append("")
        parts.append("CRITICAL: Use the MODULE NAMES shown above for imports!")
        parts.append(
            "Example: `from cart import Product` NOT `from sandbox.cart import Product`"
        )
        parts.append("")
        parts.append(
            "Focus especially on testing BUSINESS LOGIC, not just error handling."
        )

        return "\n".join(parts)

    def _save_generated_tests(self, response: str) -> List[str]:
        """Parse and save generated test files."""
        saved_files = []

        tests_dir = os.path.join(self.target_dir, "tests")
        os.makedirs(tests_dir, exist_ok=True)

        patterns = [
            r"###\s*FILE:\s*([^\n]+)\n```python\n(.*?)```",
            r"##\s*FILE:\s*([^\n]+)\n```python\n(.*?)```",
            r"###\s*File:\s*([^\n]+)\n```python\n(.*?)```",
            r"##\s*File:\s*([^\n]+)\n```python\n(.*?)```",
            r"\*\*File:\*\*\s*`?([^\n`]+)`?\n```python\n(.*?)```",
        ]

        matches = []
        for pattern in patterns:
            matches = re.findall(pattern, response, re.DOTALL)
            if matches:
                break

        for file_path, content in matches:
            file_path = file_path.strip()
            content = content.strip()

            if not file_path.startswith("tests/"):
                file_path = f"tests/{os.path.basename(file_path)}"

            try:
                write_file(file_path, content, self.target_dir)
                saved_files.append(file_path)

                self.log_tool_action(
                    action_type=ActionType.GENERATION,
                    command=f"write_file('{file_path}', ...)",
                    output=f"Test file created: {file_path}",
                    extra_details={"test_file": file_path},
                )
            except Exception as e:
                self.log_tool_action(
                    action_type=ActionType.GENERATION,
                    command=f"write_file('{file_path}', ...)",
                    output=f"ERROR: {e}",
                    status="FAILURE",
                )

        return saved_files

    def _ensure_tests_init(self) -> None:
        """Ensure tests/__init__.py exists."""
        init_path = os.path.join(self.target_dir, "tests", "__init__.py")
        if not os.path.exists(init_path):
            try:
                write_file(
                    "tests/__init__.py", '"""Test package."""\n', self.target_dir
                )
            except Exception:
                pass

    def _run_tests(self) -> TestResult:
        """Run pytest on the tests directory."""
        return run_tests(self.target_dir)

    def _extract_error_logs(self, test_result: TestResult) -> List[str]:
        """
        Extract meaningful error logs from test results with tiered priority.

        Error context tiering (SPEC 4.3):
        - Tier 1 (Critical): AssertionError, TypeError, ValueError - most actionable
        - Tier 2 (Important): AttributeError, KeyError, IndexError - common bugs
        - Tier 3 (Context): Other errors, tracebacks, output excerpts
        """
        error_logs = []

        if not test_result.success:
            # Add summary first
            error_logs.append(
                f"Tests: {test_result.passed} passed, {test_result.failed} failed, "
                f"{test_result.errors} errors"
            )

            # Tier 1: Critical errors (most actionable for fixing)
            tier1_keywords = ["AssertionError", "TypeError", "ValueError"]
            tier1_failures = []
            tier2_failures = []
            tier3_failures = []

            for failure in test_result.failures:
                test_name = failure.get("test", "unknown")
                message = failure.get("message", "")

                # Categorize by error type
                if any(kw in message for kw in tier1_keywords):
                    tier1_failures.append((test_name, message))
                elif any(
                    kw in message
                    for kw in ["AttributeError", "KeyError", "IndexError", "NameError"]
                ):
                    tier2_failures.append((test_name, message))
                else:
                    tier3_failures.append((test_name, message))

            # Add failures in priority order with clear labeling
            if tier1_failures:
                error_logs.append("\n## CRITICAL FAILURES (fix these first):")
                for test_name, message in tier1_failures:
                    error_logs.append(f"FAILED: {test_name}")
                    error_logs.append(f"  {self._extract_actionable_info(message)}")

            if tier2_failures:
                error_logs.append("\n## IMPORTANT FAILURES:")
                for test_name, message in tier2_failures:
                    error_logs.append(f"FAILED: {test_name}")
                    error_logs.append(f"  {self._extract_actionable_info(message)}")

            if tier3_failures:
                error_logs.append("\n## OTHER FAILURES:")
                for test_name, message in tier3_failures:
                    error_logs.append(f"FAILED: {test_name}")
                    error_logs.append(f"  Message: {message[:300]}")

            # If no structured failures, add output excerpt (Tier 3)
            if not test_result.failures and test_result.output:
                error_logs.append("\n## Output excerpt:")
                error_logs.append(test_result.output[:1000])

        # Deduplicate error logs while preserving order
        seen = set()
        unique_logs = []
        for log in error_logs:
            # Normalize for comparison (strip whitespace, lowercase)
            normalized = log.strip().lower()
            if normalized and normalized not in seen:
                seen.add(normalized)
                unique_logs.append(log)

        return unique_logs

    def _extract_actionable_info(self, error_message: str) -> str:
        """
        Extract the most actionable information from an error message.

        Focuses on:
        - Expected vs actual values for assertions
        - The specific error type and message
        - Line numbers if available
        """
        import re

        # Look for assertion comparison patterns
        assertion_patterns = [
            r"assert\s+(.+?)\s*==\s*(.+)",  # assert x == y
            r"AssertionError:\s*(.+)",  # AssertionError: message
            r"Expected:\s*(.+)",  # Expected: value
            r"Actual:\s*(.+)",  # Actual: value
            r"(\d+)\s*!=\s*(\d+)",  # number != number
        ]

        actionable_parts = []

        for pattern in assertion_patterns:
            matches = re.findall(pattern, error_message, re.IGNORECASE)
            if matches:
                for match in matches:
                    if isinstance(match, tuple):
                        actionable_parts.append(" vs ".join(match))
                    else:
                        actionable_parts.append(match)

        if actionable_parts:
            return "; ".join(actionable_parts[:3])  # Limit to 3 most relevant parts

        # Fallback: return truncated original message
        return error_message[:400]

    def _analyze_semantic_changes(
        self,
        original_code: str,
        fixed_code: str,
        test_failures: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Analyze semantic differences between original and fixed code (SPEC 4.1).

        This helper identifies what actually changed and whether it addresses
        the test failures.

        Returns:
            Dict with:
                - changes_detected: List of identified changes
                - likely_fixes: Which failures might be addressed
                - concerns: Any potential issues with the changes
        """
        import difflib

        changes_detected = []
        likely_fixes = []
        concerns = []

        # Get line-by-line diff
        original_lines = original_code.splitlines(keepends=True)
        fixed_lines = fixed_code.splitlines(keepends=True)

        diff = list(difflib.unified_diff(original_lines, fixed_lines, lineterm=""))

        # Analyze the diff
        added_lines = [
            l[1:].strip() for l in diff if l.startswith("+") and not l.startswith("+++")
        ]
        removed_lines = [
            l[1:].strip() for l in diff if l.startswith("-") and not l.startswith("---")
        ]

        if added_lines:
            changes_detected.append(f"Added {len(added_lines)} line(s)")
        if removed_lines:
            changes_detected.append(f"Removed {len(removed_lines)} line(s)")

        # Check for common fix patterns
        fix_patterns = {
            "return": "Modified return statement",
            "if ": "Added/changed conditional",
            "except": "Added/modified exception handling",
            "raise": "Modified exception raising",
            "==": "Changed comparison",
            "!=": "Changed comparison",
            "<=": "Changed comparison operator",
            ">=": "Changed comparison operator",
            "+": "Modified arithmetic",
            "-": "Modified arithmetic",
            "*": "Modified arithmetic",
            "/": "Modified arithmetic",
        }

        for line in added_lines:
            for pattern, description in fix_patterns.items():
                if pattern in line and description not in changes_detected:
                    changes_detected.append(description)
                    break

        # Match changes to potential test fixes
        for failure in test_failures:
            test_name = failure.get("test", "")
            message = failure.get("message", "")

            # If an assertion value changed and the test checks that value
            if "assert" in message.lower() or "Error" in message:
                likely_fixes.append(f"May fix: {test_name}")

        # Check for concerning patterns
        if len(removed_lines) > len(added_lines) * 2:
            concerns.append("Large code deletion - verify intended behavior preserved")

        if any("# TODO" in l or "# FIXME" in l for l in added_lines):
            concerns.append("Contains TODO/FIXME comments - may be incomplete")

        return {
            "changes_detected": changes_detected,
            "likely_fixes": likely_fixes,
            "concerns": concerns,
            "lines_added": len(added_lines),
            "lines_removed": len(removed_lines),
        }
