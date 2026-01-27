"""
Tests for agent mixins.

Tests FileReadMixin and ContentCleaningMixin functionality.
"""

import os
import pytest
from pathlib import Path

from src.agents.mixins import FileReadMixin, ContentCleaningMixin


class TestFileReadMixin:
    """Tests for FileReadMixin file reading functionality."""

    class MockAgent(FileReadMixin):
        """Mock agent class using FileReadMixin."""

        def __init__(self, target_dir: str):
            self.target_dir = target_dir

    def test_read_single_file(self, temp_sandbox):
        """Test reading a single existing file."""
        Path(temp_sandbox, "test.py").write_text("print('hello')")

        agent = self.MockAgent(temp_sandbox)
        contents = agent._read_files(["test.py"])

        assert "test.py" in contents
        assert contents["test.py"] == "print('hello')"

    def test_read_multiple_files(self, temp_sandbox):
        """Test reading multiple files."""
        Path(temp_sandbox, "a.py").write_text("# file a")
        Path(temp_sandbox, "b.py").write_text("# file b")

        agent = self.MockAgent(temp_sandbox)
        contents = agent._read_files(["a.py", "b.py"])

        assert len(contents) == 2
        assert "# file a" in contents["a.py"]
        assert "# file b" in contents["b.py"]

    def test_read_nonexistent_file_returns_error(self, temp_sandbox):
        """Test that reading missing file returns error message instead of raising."""
        agent = self.MockAgent(temp_sandbox)
        contents = agent._read_files(["nonexistent.py"])

        assert "nonexistent.py" in contents
        assert "ERROR: File not found" in contents["nonexistent.py"]

    def test_read_file_in_subdirectory(self, temp_sandbox):
        """Test reading file in nested directory."""
        subdir = Path(temp_sandbox, "src", "utils")
        subdir.mkdir(parents=True)
        (subdir / "helper.py").write_text("def help(): pass")

        agent = self.MockAgent(temp_sandbox)
        contents = agent._read_files(["src/utils/helper.py"])

        assert "src/utils/helper.py" in contents
        assert "def help" in contents["src/utils/helper.py"]

    def test_read_empty_file_list(self, temp_sandbox):
        """Test reading empty file list returns empty dict."""
        agent = self.MockAgent(temp_sandbox)
        contents = agent._read_files([])

        assert contents == {}

    def test_read_mixed_existing_and_missing(self, temp_sandbox):
        """Test reading mix of existing and missing files."""
        Path(temp_sandbox, "exists.py").write_text("# exists")

        agent = self.MockAgent(temp_sandbox)
        contents = agent._read_files(["exists.py", "missing.py"])

        assert len(contents) == 2
        assert "# exists" in contents["exists.py"]
        assert "ERROR" in contents["missing.py"]


class TestContentCleaningMixin:
    """Tests for ContentCleaningMixin content processing functionality."""

    class MockCleaner(ContentCleaningMixin):
        """Mock class using ContentCleaningMixin."""

        pass

    def test_clean_content_removes_line_numbers(self):
        """Test that line number prefixes are removed."""
        cleaner = self.MockCleaner()
        content = """   1 | def foo():
   2 |     return 42
   3 | """
        cleaned = cleaner._clean_content(content)

        assert "   1 |" not in cleaned
        assert "def foo():" in cleaned
        assert "return 42" in cleaned

    def test_clean_content_handles_various_formats(self):
        """Test cleaning handles different line number formats."""
        cleaner = self.MockCleaner()

        # Test single digit
        assert cleaner._clean_content("1 | code") == "code"

        # Test multi-digit with spacing
        assert cleaner._clean_content("  42 | more code") == "more code"

        # Test large line numbers
        assert cleaner._clean_content("1234 | lots of code") == "lots of code"

    def test_clean_content_preserves_non_numbered_lines(self):
        """Test that lines without numbers are preserved."""
        cleaner = self.MockCleaner()
        content = "just regular code\nno line numbers here"

        cleaned = cleaner._clean_content(content)

        assert cleaned == content

    def test_clean_content_handles_mixed_content(self):
        """Test cleaning mixed numbered and non-numbered content."""
        cleaner = self.MockCleaner()
        content = """   1 | def foo():
regular line
   3 |     return 42"""

        cleaned = cleaner._clean_content(content)

        assert "1 |" not in cleaned
        assert "3 |" not in cleaned
        assert "def foo():" in cleaned
        assert "regular line" in cleaned
        assert "return 42" in cleaned

    def test_clean_content_preserves_pipe_in_code(self):
        """Test that pipes in actual code (like OR operator) are preserved."""
        cleaner = self.MockCleaner()
        # This is actual code with bitwise OR, not a line number
        content = "result = a | b"

        cleaned = cleaner._clean_content(content)

        # Should be unchanged since it doesn't match line number pattern
        assert cleaned == content

    def test_format_with_line_numbers_adds_numbers(self):
        """Test that line numbers are added correctly."""
        cleaner = self.MockCleaner()
        content = "line one\nline two\nline three"

        formatted = cleaner._format_with_line_numbers(content)

        assert "   1 | line one" in formatted
        assert "   2 | line two" in formatted
        assert "   3 | line three" in formatted

    def test_format_with_line_numbers_handles_empty_lines(self):
        """Test formatting preserves empty lines with numbers."""
        cleaner = self.MockCleaner()
        content = "line one\n\nline three"

        formatted = cleaner._format_with_line_numbers(content)

        assert "   1 | line one" in formatted
        assert "   2 | " in formatted  # Empty line gets number
        assert "   3 | line three" in formatted

    def test_format_then_clean_roundtrip(self):
        """Test that formatting then cleaning returns original content."""
        cleaner = self.MockCleaner()
        original = "def foo():\n    return 42\n"

        formatted = cleaner._format_with_line_numbers(original)
        cleaned = cleaner._clean_content(formatted)

        assert cleaned == original

    def test_format_large_file(self):
        """Test formatting works for files with many lines."""
        cleaner = self.MockCleaner()
        lines = [f"line {i}" for i in range(1, 1001)]
        content = "\n".join(lines)

        formatted = cleaner._format_with_line_numbers(content)

        assert "1000 | line 1000" in formatted
        assert " 999 | line 999" in formatted
