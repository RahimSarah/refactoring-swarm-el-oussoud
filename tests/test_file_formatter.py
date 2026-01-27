"""
Tests for unified FileFormatter utilities.

Tests file formatting, code context building, and error context formatting.
"""

import pytest

from src.utils.file_formatter import (
    FormattedFile,
    FileFormatter,
    format_error_context,
)


class TestFormattedFile:
    """Tests for FormattedFile dataclass."""

    def test_module_name_from_simple_path(self):
        """Test module name extraction from simple path."""
        ff = FormattedFile(
            path="calculator.py",
            content="",
            numbered_content="",
            line_count=0,
        )
        assert ff.module_name == "calculator"

    def test_module_name_from_nested_path(self):
        """Test module name extraction from nested path."""
        ff = FormattedFile(
            path="src/utils/helper.py",
            content="",
            numbered_content="",
            line_count=0,
        )
        assert ff.module_name == "helper"

    def test_module_name_removes_extension(self):
        """Test that .py extension is removed."""
        ff = FormattedFile(
            path="module.py",
            content="",
            numbered_content="",
            line_count=0,
        )
        assert ".py" not in ff.module_name


class TestFileFormatter:
    """Tests for FileFormatter class."""

    def test_format_file_adds_line_numbers(self, temp_sandbox):
        """Test that format_file adds correct line numbers."""
        formatter = FileFormatter(temp_sandbox)
        content = "line one\nline two\nline three"

        result = formatter.format_file(content, "test.py")

        assert "   1 | line one" in result.numbered_content
        assert "   2 | line two" in result.numbered_content
        assert "   3 | line three" in result.numbered_content

    def test_format_file_preserves_original(self, temp_sandbox):
        """Test that original content is preserved."""
        formatter = FileFormatter(temp_sandbox)
        content = "def foo():\n    return 42"

        result = formatter.format_file(content, "test.py")

        assert result.content == content

    def test_format_file_counts_lines(self, temp_sandbox):
        """Test that line count is accurate."""
        formatter = FileFormatter(temp_sandbox)
        content = "a\nb\nc\nd\ne"

        result = formatter.format_file(content, "test.py")

        assert result.line_count == 5

    def test_format_files_multiple(self, temp_sandbox):
        """Test formatting multiple files."""
        formatter = FileFormatter(temp_sandbox)
        files = {
            "a.py": "code a",
            "b.py": "code b\nline 2",
        }

        result = formatter.format_files(files)

        assert len(result) == 2
        assert "a.py" in result
        assert "b.py" in result
        assert result["a.py"].line_count == 1
        assert result["b.py"].line_count == 2

    def test_build_code_context_includes_all_files(self, temp_sandbox):
        """Test that code context includes all files."""
        formatter = FileFormatter(temp_sandbox)
        files = {
            "module_a.py": "def a(): pass",
            "module_b.py": "def b(): pass",
        }

        context = formatter.build_code_context(files)

        assert "## File: module_a.py" in context
        assert "## File: module_b.py" in context
        assert "def a()" in context
        assert "def b()" in context

    def test_build_code_context_with_line_numbers(self, temp_sandbox):
        """Test that code context includes line numbers by default."""
        formatter = FileFormatter(temp_sandbox)
        files = {"test.py": "line 1\nline 2"}

        context = formatter.build_code_context(files, include_line_numbers=True)

        assert "   1 |" in context
        assert "   2 |" in context

    def test_build_code_context_without_line_numbers(self, temp_sandbox):
        """Test code context without line numbers."""
        formatter = FileFormatter(temp_sandbox)
        files = {"test.py": "line 1\nline 2"}

        context = formatter.build_code_context(files, include_line_numbers=False)

        assert "   1 |" not in context
        assert "line 1" in context

    def test_build_code_context_truncates_long_files(self, temp_sandbox):
        """Test that long files are truncated."""
        formatter = FileFormatter(temp_sandbox)
        files = {"test.py": "\n".join([f"line {i}" for i in range(100)])}

        context = formatter.build_code_context(files, max_lines_per_file=10)

        assert "truncated" in context
        assert "90 more lines" in context

    def test_build_file_section_with_extra_info(self, temp_sandbox):
        """Test file section with additional info."""
        formatter = FileFormatter(temp_sandbox)

        section = formatter.build_file_section(
            "calc.py",
            "def add(a, b): return a + b",
            extra_info={"Pylint Score": "8.5/10"},
        )

        assert "### File: calc.py" in section
        assert "Module: `calc`" in section
        assert "#### Pylint Score" in section
        assert "8.5/10" in section

    def test_strip_line_numbers_removes_prefixes(self):
        """Test that line number prefixes are stripped."""
        content = "   1 | def foo():\n   2 |     return 42"

        result = FileFormatter.strip_line_numbers(content)

        assert "   1 |" not in result
        assert "def foo():" in result
        assert "return 42" in result

    def test_strip_line_numbers_preserves_clean_content(self):
        """Test that content without line numbers is unchanged."""
        content = "def foo():\n    return 42"

        result = FileFormatter.strip_line_numbers(content)

        assert result == content

    def test_extract_code_blocks_single_file(self):
        """Test extracting code blocks from response."""
        response = """
### FILE: calc.py
```python
def add(a, b):
    return a + b
```
"""
        blocks = FileFormatter.extract_code_blocks(response)

        assert len(blocks) == 1
        assert blocks[0]["path"] == "calc.py"
        assert "def add" in blocks[0]["content"]

    def test_extract_code_blocks_multiple_files(self):
        """Test extracting multiple code blocks."""
        response = """
### FILE: a.py
```python
def a(): pass
```

### FILE: b.py
```python
def b(): pass
```
"""
        blocks = FileFormatter.extract_code_blocks(response)

        assert len(blocks) == 2
        paths = [b["path"] for b in blocks]
        assert "a.py" in paths
        assert "b.py" in paths

    def test_extract_code_blocks_strips_line_numbers(self):
        """Test that extracted code has line numbers stripped."""
        response = """
### FILE: test.py
```python
   1 | def foo():
   2 |     return 42
```
"""
        blocks = FileFormatter.extract_code_blocks(response)

        assert len(blocks) == 1
        assert "   1 |" not in blocks[0]["content"]
        assert "def foo():" in blocks[0]["content"]

    def test_extract_code_blocks_handles_alternative_formats(self):
        """Test extraction with different markdown formats."""
        response = """
## File: alternative.py
```python
code here
```
"""
        blocks = FileFormatter.extract_code_blocks(response)

        assert len(blocks) == 1
        assert blocks[0]["path"] == "alternative.py"


class TestFormatErrorContext:
    """Tests for format_error_context function."""

    def test_formats_error_list(self):
        """Test formatting a list of errors."""
        errors = ["Error 1", "Error 2", "Error 3"]

        result = format_error_context(errors)

        assert "## Error Context" in result
        assert "1. Error 1" in result
        assert "2. Error 2" in result
        assert "3. Error 3" in result

    def test_empty_errors_shows_message(self):
        """Test that empty error list shows appropriate message."""
        result = format_error_context([])

        assert "No errors" in result

    def test_limits_errors_to_max(self):
        """Test that errors are limited to max_errors."""
        errors = [f"Error {i}" for i in range(20)]

        result = format_error_context(errors, max_errors=5)

        assert "1. Error 0" in result
        assert "5. Error 4" in result
        assert "15 more errors" in result
        assert "Error 19" not in result

    def test_prioritizes_critical_errors(self):
        """Test that critical errors appear first."""
        errors = [
            "Some random error",
            "AssertionError: failed assertion",
            "Another random error",
            "TypeError: bad type",
        ]

        result = format_error_context(errors, prioritize_critical=True)

        # Critical errors should be first
        assert result.index("AssertionError") < result.index("random error")
        assert result.index("TypeError") < result.index("Another random")

    def test_no_prioritization_when_disabled(self):
        """Test that order is preserved when prioritization disabled."""
        errors = [
            "First error",
            "AssertionError: second",
            "Third error",
        ]

        result = format_error_context(errors, prioritize_critical=False)

        # Order should be preserved
        lines = result.split("\n")
        error_lines = [l for l in lines if l.startswith(("1.", "2.", "3."))]
        assert "First error" in error_lines[0]
        assert "AssertionError" in error_lines[1]
        assert "Third error" in error_lines[2]
