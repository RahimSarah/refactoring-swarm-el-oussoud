import pytest
from unittest.mock import patch, MagicMock

from src.agents.fixer import FixerAgent
from src.agents.judge import JudgeAgent


class TestFixerResponseParsing:
    def test_parse_single_file_fix(self, mock_llm, temp_sandbox, disable_logging):
        fixer = FixerAgent(llm=mock_llm, target_dir=temp_sandbox)

        response = """
### FILE: calculator.py
```python
def add(a, b):
    return a + b
```
"""
        fixed_files = fixer._parse_response(response)

        assert "calculator.py" in fixed_files
        assert "def add" in fixed_files["calculator.py"]

    def test_parse_multiple_file_fixes(self, mock_llm, temp_sandbox, disable_logging):
        fixer = FixerAgent(llm=mock_llm, target_dir=temp_sandbox)

        response = """
### FILE: module_a.py
```python
def func_a():
    return 1
```

### FILE: module_b.py
```python
def func_b():
    return 2
```
"""
        fixed_files = fixer._parse_response(response)

        assert len(fixed_files) == 2
        assert "module_a.py" in fixed_files
        assert "module_b.py" in fixed_files

    def test_parse_with_path_prefix(self, mock_llm, temp_sandbox, disable_logging):
        fixer = FixerAgent(llm=mock_llm, target_dir=temp_sandbox)

        response = """
### FILE: src/utils/helper.py
```python
def helper():
    pass
```
"""
        fixed_files = fixer._parse_response(response)

        assert "src/utils/helper.py" in fixed_files

    def test_parse_empty_response(self, mock_llm, temp_sandbox, disable_logging):
        fixer = FixerAgent(llm=mock_llm, target_dir=temp_sandbox)

        fixed_files = fixer._parse_response("No files to fix")

        assert fixed_files == {}

    def test_parse_malformed_response(self, mock_llm, temp_sandbox, disable_logging):
        fixer = FixerAgent(llm=mock_llm, target_dir=temp_sandbox)

        response = "Here's some code:\ndef broken():\n    pass"
        fixed_files = fixer._parse_response(response)

        assert fixed_files == {}


class TestJudgeTestParsing:
    def test_save_generated_tests(self, mock_llm, temp_sandbox, disable_logging):
        judge = JudgeAgent(llm=mock_llm, target_dir=temp_sandbox)

        response = """
### FILE: tests/test_calculator.py
```python
import pytest

def test_add():
    assert 1 + 1 == 2
```
"""
        saved = judge._save_generated_tests(response)

        assert len(saved) == 1
        assert "test_calculator.py" in saved[0]

    def test_save_multiple_test_files(self, mock_llm, temp_sandbox, disable_logging):
        judge = JudgeAgent(llm=mock_llm, target_dir=temp_sandbox)

        response = """
### FILE: tests/test_module_a.py
```python
def test_a():
    assert True
```

### FILE: tests/test_module_b.py
```python
def test_b():
    assert True
```
"""
        saved = judge._save_generated_tests(response)

        assert len(saved) == 2

    def test_extract_error_logs_from_failures(
        self, mock_llm, temp_sandbox, disable_logging
    ):
        from src.tools.test_runner import TestResult

        judge = JudgeAgent(llm=mock_llm, target_dir=temp_sandbox)

        test_result = TestResult(
            passed=1,
            failed=2,
            errors=0,
            skipped=0,
            total=3,
            success=False,
            output="test output",
            failures=[
                {"test": "test_average", "message": "assert 30 == 15"},
                {"test": "test_divide", "message": "ZeroDivisionError"},
            ],
        )

        error_logs = judge._extract_error_logs(test_result)

        assert len(error_logs) >= 1
        assert any("test_average" in log for log in error_logs)

    def test_extract_empty_error_logs_on_success(
        self, mock_llm, temp_sandbox, disable_logging
    ):
        from src.tools.test_runner import TestResult

        judge = JudgeAgent(llm=mock_llm, target_dir=temp_sandbox)

        test_result = TestResult(
            passed=5,
            failed=0,
            errors=0,
            skipped=0,
            total=5,
            success=True,
            output="all passed",
            failures=[],
        )

        error_logs = judge._extract_error_logs(test_result)

        assert error_logs == []


class TestAgentLogging:
    def test_base_agent_logs_llm_calls(self, mock_llm, temp_sandbox, capture_logs):
        from src.agents.base import BaseAgent
        from src.utils.logger import ActionType

        agent = BaseAgent(llm=mock_llm, name="TestAgent", target_dir=temp_sandbox)
        agent.call_llm("system prompt", "user prompt", ActionType.ANALYSIS)

        assert len(capture_logs) == 1
        assert capture_logs[0]["kwargs"]["agent_name"] == "TestAgent"
        assert "input_prompt" in capture_logs[0]["kwargs"]["details"]
        assert "output_response" in capture_logs[0]["kwargs"]["details"]

    def test_base_agent_logs_tool_actions(self, mock_llm, temp_sandbox, capture_logs):
        from src.agents.base import BaseAgent
        from src.utils.logger import ActionType

        agent = BaseAgent(llm=mock_llm, name="TestAgent", target_dir=temp_sandbox)
        agent.log_tool_action(ActionType.ANALYSIS, "pylint file.py", "Score: 8/10")

        assert len(capture_logs) == 1
        assert capture_logs[0]["kwargs"]["model_used"] == "N/A"
        assert capture_logs[0]["kwargs"]["status"] == "SUCCESS"


class TestAgentBuildPrompt:
    def test_fixer_builds_prompt_with_plan(
        self, mock_llm, temp_sandbox, disable_logging
    ):
        fixer = FixerAgent(llm=mock_llm, target_dir=temp_sandbox)

        plan = "# Plan\n## Issue 1: Bug in line 5"
        file_contents = {"test.py": "def buggy(): pass"}
        error_logs = []

        prompt = fixer._build_prompt(
            plan, file_contents, error_logs, previous_attempts=[]
        )

        assert "# Plan" in prompt
        assert "test.py" in prompt
        assert "def buggy" in prompt

    def test_fixer_includes_error_logs(self, mock_llm, temp_sandbox, disable_logging):
        fixer = FixerAgent(llm=mock_llm, target_dir=temp_sandbox)

        plan = "# Plan"
        file_contents = {"test.py": "code"}
        error_logs = ["FAILED: test_foo - assert 1 == 2", "Expected 1 got 2"]

        prompt = fixer._build_prompt(
            plan, file_contents, error_logs, previous_attempts=[]
        )

        assert "FAILED: test_foo" in prompt
        assert "MUST FIX" in prompt

    def test_judge_builds_generate_prompt_with_source(
        self, mock_llm, temp_sandbox, disable_logging
    ):
        judge = JudgeAgent(llm=mock_llm, target_dir=temp_sandbox)

        plan = "# Plan\n## Bug: returns sum not average"
        files = ["calculator.py"]
        file_contents = {
            "calculator.py": "def calculate_average(nums): return sum(nums)"
        }

        prompt = judge._build_generate_prompt(plan, files, file_contents)

        assert "Plan" in prompt
        assert "calculator.py" in prompt
        assert "calculate_average" in prompt
        assert "BUSINESS LOGIC" in prompt


class TestJudgeErrorTiering:
    """Tests for Judge error tiering functionality (SPEC 4.3)."""

    def test_tier1_errors_come_first(self, mock_llm, temp_sandbox, disable_logging):
        """Test that critical errors (Tier 1) appear before others."""
        from src.tools.test_runner import TestResult

        judge = JudgeAgent(llm=mock_llm, target_dir=temp_sandbox)

        test_result = TestResult(
            passed=0,
            failed=3,
            errors=0,
            skipped=0,
            total=3,
            success=False,
            output="test output",
            failures=[
                {"test": "test_attr", "message": "AttributeError: no attr 'foo'"},
                {"test": "test_assert", "message": "AssertionError: assert 1 == 2"},
                {"test": "test_key", "message": "KeyError: 'missing'"},
            ],
        )

        error_logs = judge._extract_error_logs(test_result)
        joined = "\n".join(error_logs)

        # Tier 1 (AssertionError) should appear before Tier 2 (AttributeError, KeyError)
        critical_idx = joined.find("CRITICAL FAILURES")
        important_idx = joined.find("IMPORTANT FAILURES")

        assert critical_idx < important_idx
        assert "test_assert" in joined

    def test_tier1_includes_assertion_and_type_errors(
        self, mock_llm, temp_sandbox, disable_logging
    ):
        """Test that Tier 1 captures AssertionError, TypeError, ValueError."""
        from src.tools.test_runner import TestResult

        judge = JudgeAgent(llm=mock_llm, target_dir=temp_sandbox)

        test_result = TestResult(
            passed=0,
            failed=3,
            errors=0,
            skipped=0,
            total=3,
            success=False,
            output="",
            failures=[
                {"test": "test_1", "message": "AssertionError: bad"},
                {"test": "test_2", "message": "TypeError: expected int"},
                {"test": "test_3", "message": "ValueError: invalid"},
            ],
        )

        error_logs = judge._extract_error_logs(test_result)
        joined = "\n".join(error_logs)

        assert "CRITICAL FAILURES" in joined
        assert "test_1" in joined
        assert "test_2" in joined
        assert "test_3" in joined

    def test_tier2_includes_attribute_key_index_errors(
        self, mock_llm, temp_sandbox, disable_logging
    ):
        """Test that Tier 2 captures AttributeError, KeyError, IndexError."""
        from src.tools.test_runner import TestResult

        judge = JudgeAgent(llm=mock_llm, target_dir=temp_sandbox)

        test_result = TestResult(
            passed=0,
            failed=3,
            errors=0,
            skipped=0,
            total=3,
            success=False,
            output="",
            failures=[
                {"test": "test_1", "message": "AttributeError: object has no attr"},
                {"test": "test_2", "message": "KeyError: 'missing_key'"},
                {"test": "test_3", "message": "IndexError: list index out of range"},
            ],
        )

        error_logs = judge._extract_error_logs(test_result)
        joined = "\n".join(error_logs)

        assert "IMPORTANT FAILURES" in joined

    def test_extract_actionable_info_from_assertion(
        self, mock_llm, temp_sandbox, disable_logging
    ):
        """Test that actionable info is extracted from assertion errors."""
        judge = JudgeAgent(llm=mock_llm, target_dir=temp_sandbox)

        # Test assertion with comparison
        info = judge._extract_actionable_info("assert 30 == 15")
        assert "30" in info and "15" in info

        # Test AssertionError message
        info = judge._extract_actionable_info(
            "AssertionError: expected True, got False"
        )
        assert "expected True, got False" in info


class TestJudgeSemanticAnalysis:
    """Tests for Judge semantic analysis functionality (SPEC 4.1)."""

    def test_analyze_detects_added_lines(self, mock_llm, temp_sandbox, disable_logging):
        """Test that added lines are detected in semantic analysis."""
        judge = JudgeAgent(llm=mock_llm, target_dir=temp_sandbox)

        original = "def foo():\n    return 1\n"
        fixed = "def foo():\n    # Added comment\n    return 1\n"

        result = judge._analyze_semantic_changes(original, fixed, [])

        assert result["lines_added"] > 0
        assert "Added" in str(result["changes_detected"])

    def test_analyze_detects_removed_lines(
        self, mock_llm, temp_sandbox, disable_logging
    ):
        """Test that removed lines are detected in semantic analysis."""
        judge = JudgeAgent(llm=mock_llm, target_dir=temp_sandbox)

        original = "def foo():\n    x = 1\n    y = 2\n    return x + y\n"
        fixed = "def foo():\n    return 3\n"

        result = judge._analyze_semantic_changes(original, fixed, [])

        assert result["lines_removed"] > 0

    def test_analyze_detects_conditional_changes(
        self, mock_llm, temp_sandbox, disable_logging
    ):
        """Test that conditional changes are identified."""
        judge = JudgeAgent(llm=mock_llm, target_dir=temp_sandbox)

        original = "def divide(a, b):\n    return a / b\n"
        fixed = "def divide(a, b):\n    if b == 0:\n        raise ValueError('zero')\n    return a / b\n"

        result = judge._analyze_semantic_changes(original, fixed, [])

        assert any("conditional" in c.lower() for c in result["changes_detected"])

    def test_analyze_flags_large_deletions_as_concern(
        self, mock_llm, temp_sandbox, disable_logging
    ):
        """Test that large code deletions are flagged as concerns."""
        judge = JudgeAgent(llm=mock_llm, target_dir=temp_sandbox)

        original = "\n".join([f"line {i}" for i in range(20)])
        fixed = "# simplified"

        result = judge._analyze_semantic_changes(original, fixed, [])

        assert len(result["concerns"]) > 0
        assert any("deletion" in c.lower() for c in result["concerns"])

    def test_analyze_detects_return_statement_changes(
        self, mock_llm, temp_sandbox, disable_logging
    ):
        """Test that return statement modifications are detected."""
        judge = JudgeAgent(llm=mock_llm, target_dir=temp_sandbox)

        original = "def avg(nums):\n    return sum(nums)\n"
        fixed = "def avg(nums):\n    return sum(nums) / len(nums)\n"

        result = judge._analyze_semantic_changes(original, fixed, [])

        assert any("return" in c.lower() for c in result["changes_detected"])


class TestAuditorExistingTests:
    """Tests for Auditor's _run_existing_tests functionality (SPEC 3.1)."""

    def test_returns_none_when_no_tests_dir(
        self, mock_llm, temp_sandbox, disable_logging
    ):
        """Test that None is returned when no tests directory exists."""
        from src.agents.auditor import AuditorAgent

        auditor = AuditorAgent(llm=mock_llm, target_dir=temp_sandbox)
        result = auditor._run_existing_tests()

        assert result is None

    def test_returns_none_when_empty_tests_dir(
        self, mock_llm, temp_sandbox, disable_logging
    ):
        """Test that None is returned when tests dir has no test files."""
        import os
        from src.agents.auditor import AuditorAgent

        os.makedirs(os.path.join(temp_sandbox, "tests"))

        auditor = AuditorAgent(llm=mock_llm, target_dir=temp_sandbox)
        result = auditor._run_existing_tests()

        assert result is None

    def test_runs_existing_tests(self, mock_llm, temp_sandbox, disable_logging):
        """Test that existing tests are run and results returned."""
        import os
        from pathlib import Path
        from src.agents.auditor import AuditorAgent

        # Create a tests directory with a passing test
        tests_dir = Path(temp_sandbox) / "tests"
        tests_dir.mkdir()
        (tests_dir / "__init__.py").write_text("")
        (tests_dir / "test_example.py").write_text(
            "def test_passes():\n    assert True\n"
        )

        auditor = AuditorAgent(llm=mock_llm, target_dir=temp_sandbox)
        result = auditor._run_existing_tests()

        assert result is not None
        assert "passed" in result
        assert "failed" in result
        assert "test_files" in result
        assert "test_example.py" in result["test_files"]

    def test_existing_test_results_in_analyze(
        self, mock_llm, temp_sandbox, disable_logging
    ):
        """Test that existing test results are included in analyze output."""
        import os
        from pathlib import Path
        from src.agents.auditor import AuditorAgent

        # Create a source file and tests
        (Path(temp_sandbox) / "main.py").write_text("def main(): pass\n")
        tests_dir = Path(temp_sandbox) / "tests"
        tests_dir.mkdir()
        (tests_dir / "__init__.py").write_text("")
        (tests_dir / "test_main.py").write_text("def test_main():\n    assert True\n")

        auditor = AuditorAgent(llm=mock_llm, target_dir=temp_sandbox)
        result = auditor.analyze()

        assert "existing_test_results" in result
