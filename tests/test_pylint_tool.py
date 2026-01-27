import pytest

from src.tools.pylint_tool import (
    run_pylint,
    _extract_score,
    format_pylint_issues,
    PylintResult,
)


class TestExtractScore:
    def test_extract_standard_format(self):
        output = "Your code has been rated at 7.50/10 (previous run: 6.00/10)"
        assert _extract_score(output) == 7.5

    def test_extract_negative_score(self):
        output = "Your code has been rated at -2.50/10"
        assert _extract_score(output) == 0.0

    def test_extract_perfect_score(self):
        output = "Your code has been rated at 10.00/10"
        assert _extract_score(output) == 10.0

    def test_extract_zero_score(self):
        output = "Your code has been rated at 0.00/10"
        assert _extract_score(output) == 0.0

    def test_extract_from_multiline(self):
        output = """
        ************* Module test
        test.py:1:0: C0114: Missing module docstring
        
        Your code has been rated at 8.33/10
        """
        assert _extract_score(output) == 8.33

    def test_no_score_returns_zero(self):
        output = "Some random text without a score"
        assert _extract_score(output) == 0.0

    def test_extract_integer_score(self):
        output = "Your code has been rated at 5/10"
        assert _extract_score(output) == 5.0


class TestRunPylint:
    def test_run_on_valid_python_file(self, sandbox_with_clean_code):
        result = run_pylint(f"{sandbox_with_clean_code}/clean.py")

        assert isinstance(result, PylintResult)
        assert isinstance(result.score, float)
        assert 0.0 <= result.score <= 10.0

    def test_run_on_buggy_file_has_messages(self, sandbox_with_buggy_code):
        result = run_pylint(f"{sandbox_with_buggy_code}/buggy.py")

        assert isinstance(result.messages, list)
        assert result.score < 10.0

    def test_run_on_nonexistent_returns_zero_score(self, temp_sandbox):
        result = run_pylint(f"{temp_sandbox}/nonexistent.py")

        assert result.score == 0.0

    def test_timeout_returns_result(self, sandbox_with_buggy_code):
        result = run_pylint(f"{sandbox_with_buggy_code}/buggy.py", timeout=1)

        assert isinstance(result, PylintResult)

    def test_result_has_raw_output(self, sandbox_with_buggy_code):
        result = run_pylint(f"{sandbox_with_buggy_code}/buggy.py")

        assert isinstance(result.raw_output, str)


class TestFormatPylintIssues:
    def test_format_empty_messages(self):
        result = PylintResult(score=10.0, messages=[], raw_output="")
        formatted = format_pylint_issues(result)

        assert "10.0/10" in formatted
        assert "No issues found" in formatted

    def test_format_with_messages(self):
        messages = [
            {
                "line": 5,
                "column": 0,
                "type": "convention",
                "symbol": "missing-docstring",
                "message": "Missing docstring",
            }
        ]
        result = PylintResult(score=8.0, messages=messages, raw_output="")
        formatted = format_pylint_issues(result)

        assert "8.0/10" in formatted
        assert "Line 5" in formatted
        assert "missing-docstring" in formatted

    def test_format_multiple_issues(self):
        messages = [
            {
                "line": 1,
                "column": 0,
                "type": "error",
                "symbol": "syntax-error",
                "message": "Syntax error",
            },
            {
                "line": 10,
                "column": 4,
                "type": "warning",
                "symbol": "unused-variable",
                "message": "Unused var",
            },
        ]
        result = PylintResult(score=3.0, messages=messages, raw_output="")
        formatted = format_pylint_issues(result)

        assert "Line 1" in formatted
        assert "Line 10" in formatted
        assert "ERROR" in formatted
        assert "WARNING" in formatted


class TestPylintIntegration:
    def test_detects_missing_docstring(self, temp_sandbox):
        from pathlib import Path

        code = "def foo():\n    pass"
        Path(temp_sandbox, "no_doc.py").write_text(code)

        result = run_pylint(f"{temp_sandbox}/no_doc.py")

        message_symbols = [
            m.get("symbol", "") for m in result.messages if isinstance(m, dict)
        ]
        assert any("docstring" in s for s in message_symbols) or result.score < 10.0

    def test_detects_unused_import(self, temp_sandbox):
        from pathlib import Path

        code = "import os\nimport sys\n\ndef foo():\n    pass"
        Path(temp_sandbox, "unused.py").write_text(code)

        result = run_pylint(f"{temp_sandbox}/unused.py")

        assert result.score < 10.0

    def test_clean_code_has_good_score(self, sandbox_with_clean_code):
        result = run_pylint(f"{sandbox_with_clean_code}/clean.py")

        assert result.score >= 5.0
