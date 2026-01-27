"""
Tests for output validation utilities.

Tests validation of LLM responses for code fixes, tests, and plans.
"""

import pytest

from src.utils.validation import (
    ValidationResult,
    validate_python_syntax,
    validate_fix_response,
    validate_test_response,
    validate_plan_response,
    sanitize_code_output,
)


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_valid_result_is_truthy(self):
        """Test that valid result evaluates to True."""
        result = ValidationResult(is_valid=True)
        assert result
        assert bool(result) is True

    def test_invalid_result_is_falsy(self):
        """Test that invalid result evaluates to False."""
        result = ValidationResult(is_valid=False, errors=["error"])
        assert not result
        assert bool(result) is False

    def test_stores_errors_and_warnings(self):
        """Test that errors and warnings are stored."""
        result = ValidationResult(
            is_valid=False,
            errors=["error1", "error2"],
            warnings=["warning1"],
        )
        assert len(result.errors) == 2
        assert len(result.warnings) == 1


class TestValidatePythonSyntax:
    """Tests for Python syntax validation."""

    def test_valid_code_passes(self):
        """Test that valid Python code passes validation."""
        code = """
def hello():
    return "world"
"""
        result = validate_python_syntax(code)

        assert result.is_valid
        assert len(result.errors) == 0

    def test_syntax_error_detected(self):
        """Test that syntax errors are detected."""
        code = "def broken(\n    return"  # Missing closing paren and body

        result = validate_python_syntax(code, "broken.py")

        assert not result.is_valid
        assert any("Syntax error" in e for e in result.errors)
        assert "broken.py" in result.errors[0]

    def test_empty_code_fails(self):
        """Test that empty code fails validation."""
        result = validate_python_syntax("")

        assert not result.is_valid
        assert "Empty code" in result.errors

    def test_whitespace_only_fails(self):
        """Test that whitespace-only code fails."""
        result = validate_python_syntax("   \n\t\n  ")

        assert not result.is_valid

    def test_detects_code_block_markers(self):
        """Test that code block markers are flagged as warnings."""
        code = "```python\ndef foo(): pass\n```"

        result = validate_python_syntax(code)

        assert len(result.warnings) > 0
        assert any("```" in w for w in result.warnings)

    def test_detects_line_numbers_in_output(self):
        """Test that line numbers in code are flagged."""
        code = "   1 | def foo():\n   2 |     pass"

        result = validate_python_syntax(code)

        assert len(result.warnings) > 0
        assert any("Line numbers" in w for w in result.warnings)


class TestValidateFixResponse:
    """Tests for Fixer response validation."""

    def test_valid_fix_response(self):
        """Test validation of properly formatted fix response."""
        response = """
### FILE: calculator.py
```python
def add(a, b):
    return a + b
```
"""
        result = validate_fix_response(response)

        assert result.is_valid
        assert len(result.errors) == 0

    def test_multiple_files_valid(self):
        """Test validation with multiple file fixes."""
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
        result = validate_fix_response(response)

        assert result.is_valid

    def test_empty_response_fails(self):
        """Test that empty response fails validation."""
        result = validate_fix_response("")

        assert not result.is_valid
        assert "Empty response" in result.errors

    def test_no_code_blocks_fails(self):
        """Test that response without code blocks fails."""
        response = "Just some text without any code blocks"

        result = validate_fix_response(response)

        assert not result.is_valid
        assert any("No valid file" in e for e in result.errors)

    def test_syntax_error_in_code_fails(self):
        """Test that syntax errors in code are caught."""
        response = """
### FILE: broken.py
```python
def broken(
    return oops
```
"""
        result = validate_fix_response(response)

        assert not result.is_valid
        assert any("Syntax error" in e for e in result.errors)

    def test_warns_about_missing_expected_files(self):
        """Test warning when expected files are missing."""
        response = """
### FILE: only_one.py
```python
pass
```
"""
        result = validate_fix_response(
            response, expected_files=["only_one.py", "missing.py"]
        )

        assert result.is_valid  # Warning, not error
        assert any("Expected files" in w for w in result.warnings)


class TestValidateTestResponse:
    """Tests for test generation response validation."""

    def test_valid_test_response(self):
        """Test validation of properly formatted test response."""
        response = """
### FILE: tests/test_example.py
```python
import pytest

def test_example():
    assert 1 + 1 == 2
```
"""
        result = validate_test_response(response)

        assert result.is_valid
        assert len(result.errors) == 0

    def test_warns_about_non_test_filename(self):
        """Test warning for files not starting with test_."""
        response = """
### FILE: tests/example_test.py
```python
def test_example():
    assert True
```
"""
        result = validate_test_response(response)

        assert result.is_valid  # Warning, not error
        assert any("doesn't start with 'test_'" in w for w in result.warnings)

    def test_warns_about_missing_test_functions(self):
        """Test warning when no test functions found."""
        response = """
### FILE: tests/test_example.py
```python
# Just a helper file with no tests
def helper():
    return 42
```
"""
        result = validate_test_response(response)

        assert result.is_valid  # Warning, not error
        assert any("No test functions" in w for w in result.warnings)

    def test_warns_about_missing_pytest_import(self):
        """Test warning when pytest fixtures used without import."""
        response = """
### FILE: tests/test_example.py
```python
@pytest.fixture
def my_fixture():
    return 42

def test_uses_fixture(my_fixture):
    assert my_fixture == 42
```
"""
        result = validate_test_response(response)

        assert any("pytest not imported" in w for w in result.warnings)


class TestValidatePlanResponse:
    """Tests for plan response validation."""

    def test_valid_plan_response(self):
        """Test validation of properly formatted plan."""
        response = """
# Refactoring Plan

## Summary
This plan addresses 3 issues found in the codebase.

## File: calculator.py

### Issue 1: Logic Bug
- **Severity**: High
- **Description**: Returns sum instead of average
- **Fix**: Divide sum by length
"""
        result = validate_plan_response(response)

        assert result.is_valid

    def test_empty_plan_fails(self):
        """Test that empty plan fails validation."""
        result = validate_plan_response("")

        assert not result.is_valid

    def test_warns_about_short_plan(self):
        """Test warning for very short plans."""
        result = validate_plan_response("# Plan\nFix bugs")

        assert result.is_valid  # Warning, not error
        assert any("too short" in w for w in result.warnings)

    def test_warns_about_missing_headers(self):
        """Test warning when no markdown headers found."""
        response = "Just plain text without any structure or markdown formatting that goes on and on"

        result = validate_plan_response(response)

        assert any("No markdown headers" in w for w in result.warnings)


class TestSanitizeCodeOutput:
    """Tests for code output sanitization."""

    def test_removes_line_numbers(self):
        """Test that line number prefixes are removed."""
        code = "   1 | def foo():\n   2 |     return 42"

        result = sanitize_code_output(code)

        assert "1 |" not in result
        assert "2 |" not in result
        assert "def foo():" in result
        assert "return 42" in result

    def test_removes_code_block_markers(self):
        """Test that code block markers are removed."""
        code = "```python\ndef foo():\n    pass\n```"

        result = sanitize_code_output(code)

        assert "```" not in result
        assert "def foo():" in result

    def test_preserves_clean_code(self):
        """Test that clean code is unchanged."""
        code = "def foo():\n    return 42\n"

        result = sanitize_code_output(code)

        assert result == code

    def test_handles_mixed_content(self):
        """Test sanitization of mixed content."""
        code = """```python
   1 | def foo():
   2 |     return 42
```"""
        result = sanitize_code_output(code)

        assert "```" not in result
        assert "1 |" not in result
        assert "def foo():" in result
