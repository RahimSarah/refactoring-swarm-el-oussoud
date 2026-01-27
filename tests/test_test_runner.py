import pytest

from src.tools.test_runner import (
    run_tests,
    _parse_pytest_output,
    format_test_results,
    TestResult,
)


class TestParsePytestOutput:
    def test_parse_all_passed(self):
        output = """
============================= test session starts ==============================
collected 5 items

test_example.py .....                                                     [100%]

============================== 5 passed in 0.12s ===============================
        """
        result = _parse_pytest_output(output, return_code=0)

        assert result.passed == 5
        assert result.failed == 0
        assert result.success is True

    def test_parse_with_failures(self):
        output = """
============================= test session starts ==============================
collected 3 items

test_example.py .F.                                                       [100%]

=================================== FAILURES ===================================
FAILED test_example.py::test_bad - AssertionError: assert 1 == 2
============================== 2 passed, 1 failed in 0.15s =====================
        """
        result = _parse_pytest_output(output, return_code=1)

        assert result.passed == 2
        assert result.failed == 1
        assert result.success is False
        assert len(result.failures) >= 1

    def test_parse_with_errors(self):
        output = """
============================= test session starts ==============================
collected 2 items

test_example.py E.                                                        [100%]

================================== ERRORS ======================================
ERROR test_example.py::test_broken - ImportError
============================== 1 passed, 1 error in 0.10s ======================
        """
        result = _parse_pytest_output(output, return_code=1)

        assert result.passed == 1
        assert result.errors == 1
        assert result.success is False

    def test_parse_with_skipped(self):
        output = """
============================= test session starts ==============================
collected 4 items

test_example.py ..ss                                                      [100%]

========================= 2 passed, 2 skipped in 0.08s =========================
        """
        result = _parse_pytest_output(output, return_code=0)

        assert result.passed == 2
        assert result.skipped == 2
        assert result.success is True

    def test_parse_empty_output(self):
        result = _parse_pytest_output("", return_code=0)

        assert result.success is True
        assert result.total == 0

    def test_parse_extracts_failure_details(self):
        output = """
FAILED test_calc.py::test_average - AssertionError: assert 30 == 15
FAILED test_calc.py::test_divide - ZeroDivisionError: division by zero
2 failed in 0.05s
        """
        result = _parse_pytest_output(output, return_code=1)

        assert result.failed == 2
        assert len(result.failures) >= 1


class TestRunTests:
    def test_run_with_no_tests_directory(self, temp_sandbox):
        result = run_tests(temp_sandbox)

        assert result.success is True
        assert "No tests directory" in result.output

    def test_run_with_empty_tests_directory(self, temp_sandbox):
        import os

        os.makedirs(os.path.join(temp_sandbox, "tests"))

        result = run_tests(temp_sandbox)

        assert isinstance(result, TestResult)

    def test_run_with_passing_tests(self, temp_sandbox):
        import os
        from pathlib import Path

        tests_dir = os.path.join(temp_sandbox, "tests")
        os.makedirs(tests_dir)
        Path(tests_dir, "__init__.py").write_text("")
        Path(tests_dir, "test_simple.py").write_text("""
def test_one_plus_one():
    assert 1 + 1 == 2

def test_string_concat():
    assert "a" + "b" == "ab"
""")

        result = run_tests(temp_sandbox)

        assert result.passed >= 2
        assert result.success is True

    def test_run_with_failing_tests(self, temp_sandbox):
        import os
        from pathlib import Path

        tests_dir = os.path.join(temp_sandbox, "tests")
        os.makedirs(tests_dir)
        Path(tests_dir, "__init__.py").write_text("")
        Path(tests_dir, "test_fail.py").write_text("""
def test_will_fail():
    assert 1 == 2, "One is not two"
""")

        result = run_tests(temp_sandbox)

        assert result.failed >= 1
        assert result.success is False


class TestFormatTestResults:
    def test_format_success(self):
        result = TestResult(
            passed=5,
            failed=0,
            errors=0,
            skipped=0,
            total=5,
            success=True,
            output="",
            failures=[],
        )
        formatted = format_test_results(result)

        assert "5 passed" in formatted
        assert "0 failed" in formatted
        assert "Success: True" in formatted

    def test_format_failure(self):
        result = TestResult(
            passed=2,
            failed=1,
            errors=0,
            skipped=0,
            total=3,
            success=False,
            output="",
            failures=[{"test": "test_bad", "message": "Expected 15, got 30"}],
        )
        formatted = format_test_results(result)

        assert "2 passed" in formatted
        assert "1 failed" in formatted
        assert "test_bad" in formatted
        assert "Expected 15" in formatted

    def test_format_with_errors(self):
        result = TestResult(
            passed=1,
            failed=0,
            errors=2,
            skipped=0,
            total=3,
            success=False,
            output="ImportError: No module named 'foo'",
            failures=[],
        )
        formatted = format_test_results(result)

        assert "2 errors" in formatted
