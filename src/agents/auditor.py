"""
Auditor Agent for The Refactoring Swarm.

The Auditor analyzes code, runs Pylint, and produces refactoring plans.
"""

from typing import Dict, Any, List

from src.agents.base import BaseAgent
from src.llm.base import LLMProvider
from src.prompts.auditor_prompt import AUDITOR_SYSTEM_PROMPT
from src.tools.file_ops import list_directory, read_file
from src.tools.pylint_tool import run_pylint, format_pylint_issues, PylintResult
from src.tools.test_runner import run_tests, format_test_results, TestResult
from src.utils.logger import ActionType


class AuditorAgent(BaseAgent):
    """
    Auditor Agent that analyzes code and produces refactoring plans.

    The Auditor:
    1. Scans target_dir for Python files
    2. Runs Pylint on each file
    3. Analyzes code with LLM
    4. Produces a structured Markdown refactoring plan
    """

    def __init__(self, llm: LLMProvider, target_dir: str):
        """
        Initialize the Auditor agent.

        Args:
            llm: LLM provider for analysis
            target_dir: Directory containing code to analyze
        """
        super().__init__(llm=llm, name="Auditor", target_dir=target_dir)

    def analyze(self) -> Dict[str, Any]:
        """
        Analyze the codebase and produce a refactoring plan.

        Returns:
            Dict with keys:
                - files: List of Python file paths
                - plan: Markdown refactoring plan
                - pylint_baseline: Average Pylint score
                - existing_test_results: Results from any pre-existing tests (SPEC 3.1)
        """
        # Step 1: Discover Python files
        files = self._discover_files()

        if not files:
            return {
                "files": [],
                "plan": "# Refactoring Plan\n\n## Summary\nNo Python files found in target directory.",
                "pylint_baseline": 10.0,
                "existing_test_results": None,
            }

        # Step 2: Run any existing tests to establish baseline (SPEC 3.1)
        existing_test_results = self._run_existing_tests()

        # Step 3: Run Pylint on all files and collect results
        pylint_results = self._run_pylint_analysis(files)

        # Calculate baseline score (average)
        pylint_baseline = self._calculate_baseline_score(pylint_results)

        # Step 4: Read file contents for analysis
        file_contents = self._read_file_contents(files)

        # Step 5: Generate refactoring plan using LLM
        print(f"\n🤔 Auditor analyzing code with LLM...")
        print(
            f"   Context: {len(files)} files, {sum(len(c.split()) for c in file_contents.values())} words"
        )

        plan = self._generate_plan(
            files, pylint_results, file_contents, pylint_baseline, existing_test_results
        )

        print(f"✅ Auditor generated refactoring plan")
        self._display_plan_summary(plan, pylint_results)

        return {
            "files": files,
            "plan": plan,
            "pylint_baseline": pylint_baseline,
            "existing_test_results": existing_test_results,
        }

    def _display_plan_summary(
        self, plan: str, pylint_results: Dict[str, PylintResult]
    ) -> None:
        """Display a summary of detected issues."""
        print(f"\n📋 Issues Detected:")

        total_issues = sum(len(r.messages) for r in pylint_results.values())
        print(f"   • Total Pylint Issues: {total_issues}")

        issue_types = {}
        for result in pylint_results.values():
            for msg in result.messages:
                msg_type = msg.get("type", "unknown")
                issue_types[msg_type] = issue_types.get(msg_type, 0) + 1

        for issue_type, count in sorted(issue_types.items()):
            print(f"   • {issue_type}: {count}")

        if "# Bugs Detected" in plan or "## Bugs" in plan:
            print(f"   • LLM identified semantic/logic bugs (see plan)")

        if "# Refactoring Priorities" in plan or "## Priority" in plan:
            print(f"   • LLM prioritized fixes by severity")

    def _discover_files(self) -> List[str]:
        """Discover Python files in the target directory."""
        files = list_directory(".", self.target_dir, "*.py")

        # Log the discovery
        self.log_tool_action(
            action_type=ActionType.ANALYSIS,
            command=f"list_directory('.', '{self.target_dir}', '*.py')",
            output=f"Found {len(files)} Python files: {files}",
            extra_details={"files_found": len(files)},
        )

        return files

    def _run_pylint_analysis(self, files: List[str]) -> Dict[str, PylintResult]:
        """Run Pylint on all files and return results."""
        results = {}

        for file_path in files:
            result = run_pylint(file_path)
            results[file_path] = result

            # Log each Pylint run
            self.log_tool_action(
                action_type=ActionType.ANALYSIS,
                command=f"pylint {file_path} --output-format=json",
                output=format_pylint_issues(result),
                extra_details={
                    "file_analyzed": file_path,
                    "pylint_score": result.score,
                    "issues_count": len(result.messages),
                },
            )

        return results

    def _calculate_baseline_score(
        self, pylint_results: Dict[str, PylintResult]
    ) -> float:
        """Calculate the average Pylint score across all files."""
        if not pylint_results:
            return 10.0

        scores = [r.score for r in pylint_results.values()]
        return sum(scores) / len(scores)

    def _read_file_contents(self, files: List[str]) -> Dict[str, str]:
        """Read contents of all files."""
        contents = {}

        for file_path in files:
            try:
                content = read_file(file_path, self.target_dir)
                contents[file_path] = content
            except Exception as e:
                contents[file_path] = f"ERROR reading file: {e}"

        return contents

    def _run_existing_tests(self) -> Dict[str, Any] | None:
        """
        Run any existing tests in the target directory (SPEC 3.1).

        This establishes a baseline of what tests already exist and their
        current pass/fail status before we start refactoring.

        Returns:
            Dict with test results if tests exist, None otherwise
        """
        import os

        tests_dir = os.path.join(self.target_dir, "tests")

        if not os.path.exists(tests_dir):
            print("   📋 No existing tests directory found")
            return None

        # Check if there are any test files
        test_files = [
            f
            for f in os.listdir(tests_dir)
            if f.startswith("test_") and f.endswith(".py")
        ]
        if not test_files:
            print("   📋 No existing test files found")
            return None

        print(f"\n🧪 Running existing tests to establish baseline...")
        print(f"   Found {len(test_files)} test file(s)")

        result = run_tests(self.target_dir)

        # Log the test run
        self.log_tool_action(
            action_type=ActionType.ANALYSIS,
            command=f"pytest {self.target_dir}/tests -v (existing tests)",
            output=format_test_results(result),
            extra_details={
                "passed": result.passed,
                "failed": result.failed,
                "errors": result.errors,
                "total": result.total,
                "existing_tests": True,
            },
        )

        print(
            f"   ✅ Existing tests: {result.passed} passed, {result.failed} failed, {result.errors} errors"
        )

        return {
            "passed": result.passed,
            "failed": result.failed,
            "errors": result.errors,
            "total": result.total,
            "success": result.success,
            "test_files": test_files,
        }

    def _generate_plan(
        self,
        files: List[str],
        pylint_results: Dict[str, PylintResult],
        file_contents: Dict[str, str],
        pylint_baseline: float,
        existing_test_results: Dict[str, Any] | None = None,
    ) -> str:
        """Generate the refactoring plan using the LLM."""
        # Build context for the LLM
        context_parts = [
            f"## Target Directory: {self.target_dir}",
            f"## Files to Analyze: {len(files)}",
            f"## Pylint Baseline Score: {pylint_baseline:.2f}/10",
            "",
        ]

        # Include existing test results if available (SPEC 3.1)
        if existing_test_results:
            context_parts.append("## Existing Test Results (Baseline)")
            context_parts.append(
                f"- Test files: {', '.join(existing_test_results.get('test_files', []))}"
            )
            context_parts.append(f"- Passed: {existing_test_results['passed']}")
            context_parts.append(f"- Failed: {existing_test_results['failed']}")
            context_parts.append(f"- Errors: {existing_test_results['errors']}")
            context_parts.append("")
            if not existing_test_results["success"]:
                context_parts.append(
                    "**NOTE:** Some existing tests are failing. The refactoring plan should"
                )
                context_parts.append(
                    "consider these failures and prioritize fixes that address them."
                )
            context_parts.append("")

        for file_path in files:
            content = file_contents.get(file_path, "")
            pylint = pylint_results.get(file_path)

            context_parts.append(f"### File: {file_path}")
            context_parts.append("#### Content:")
            context_parts.append("```python")

            # Add line numbers to content
            lines = content.split("\n")
            numbered_lines = [f"{i + 1:4d} | {line}" for i, line in enumerate(lines)]
            context_parts.append("\n".join(numbered_lines))
            context_parts.append("```")

            if pylint:
                context_parts.append("#### Pylint Analysis:")
                context_parts.append(format_pylint_issues(pylint))

            context_parts.append("")

        user_prompt = "\n".join(context_parts)

        # Call LLM to generate the plan
        plan = self.call_llm(
            system_prompt=AUDITOR_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            action_type=ActionType.ANALYSIS,
            extra_details={
                "files_analyzed": files,
                "pylint_baseline": pylint_baseline,
            },
        )

        return plan
