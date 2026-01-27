import os
import tempfile
import shutil
from pathlib import Path

import pytest

from src.tools.file_ops import validate_path, read_file, write_file, list_directory


class TestValidatePath:
    def test_valid_relative_path_within_sandbox(self, temp_sandbox):
        result = validate_path("subdir/file.py", temp_sandbox)
        assert temp_sandbox in result
        assert "subdir/file.py" in result or "subdir" in result

    def test_valid_absolute_path_within_sandbox(self, temp_sandbox):
        abs_path = os.path.join(temp_sandbox, "test.py")
        result = validate_path(abs_path, temp_sandbox)
        assert result == abs_path

    def test_path_traversal_attack_blocked(self, temp_sandbox):
        with pytest.raises(PermissionError, match="Security violation"):
            validate_path("../../../etc/passwd", temp_sandbox)

    def test_double_dot_in_middle_blocked(self, temp_sandbox):
        with pytest.raises(PermissionError, match="Security violation"):
            validate_path("subdir/../../outside.py", temp_sandbox)

    def test_absolute_path_outside_sandbox_blocked(self, temp_sandbox):
        with pytest.raises(PermissionError, match="Security violation"):
            validate_path("/etc/passwd", temp_sandbox)

    def test_symlink_escape_attempt_blocked(self, temp_sandbox):
        link_path = os.path.join(temp_sandbox, "evil_link")
        try:
            os.symlink("/etc", link_path)
            with pytest.raises(PermissionError, match="Security violation"):
                validate_path("evil_link/passwd", temp_sandbox)
        except OSError:
            pytest.skip("Cannot create symlinks on this system")
        finally:
            if os.path.islink(link_path):
                os.unlink(link_path)

    def test_dot_path_resolves_to_sandbox(self, temp_sandbox):
        result = validate_path(".", temp_sandbox)
        assert Path(result).resolve() == Path(temp_sandbox).resolve()


class TestReadFile:
    def test_read_existing_file(self, temp_sandbox):
        test_content = "print('hello world')"
        file_path = os.path.join(temp_sandbox, "test.py")
        Path(file_path).write_text(test_content)

        result = read_file("test.py", temp_sandbox)
        assert result == test_content

    def test_read_file_in_subdirectory(self, temp_sandbox):
        subdir = os.path.join(temp_sandbox, "src", "utils")
        os.makedirs(subdir)
        file_path = os.path.join(subdir, "helper.py")
        Path(file_path).write_text("def helper(): pass")

        result = read_file("src/utils/helper.py", temp_sandbox)
        assert "def helper" in result

    def test_read_nonexistent_file_raises(self, temp_sandbox):
        with pytest.raises(FileNotFoundError):
            read_file("nonexistent.py", temp_sandbox)

    def test_read_file_outside_sandbox_blocked(self, temp_sandbox):
        with pytest.raises(PermissionError):
            read_file("/etc/passwd", temp_sandbox)

    def test_read_file_with_unicode(self, temp_sandbox):
        content = "# Commentaire en français: éàü\nprint('日本語')"
        file_path = os.path.join(temp_sandbox, "unicode.py")
        Path(file_path).write_text(content, encoding="utf-8")

        result = read_file("unicode.py", temp_sandbox)
        assert "français" in result
        assert "日本語" in result


class TestWriteFile:
    def test_write_new_file(self, temp_sandbox):
        content = "def new_function(): return 42"
        result = write_file("new.py", content, temp_sandbox)

        assert result is True
        assert Path(temp_sandbox, "new.py").read_text() == content

    def test_write_creates_parent_directories(self, temp_sandbox):
        content = "nested content"
        write_file("deep/nested/dir/file.py", content, temp_sandbox)

        assert Path(temp_sandbox, "deep/nested/dir/file.py").exists()
        assert Path(temp_sandbox, "deep/nested/dir/file.py").read_text() == content

    def test_write_overwrites_existing_file(self, temp_sandbox):
        file_path = os.path.join(temp_sandbox, "overwrite.py")
        Path(file_path).write_text("original content")

        write_file("overwrite.py", "new content", temp_sandbox)

        assert Path(file_path).read_text() == "new content"

    def test_write_outside_sandbox_blocked(self, temp_sandbox):
        with pytest.raises(PermissionError):
            write_file("/tmp/evil.py", "malicious code", temp_sandbox)

    def test_write_with_path_traversal_blocked(self, temp_sandbox):
        with pytest.raises(PermissionError):
            write_file("../escape.py", "escaped!", temp_sandbox)


class TestListDirectory:
    def test_list_empty_directory(self, temp_sandbox):
        result = list_directory(".", temp_sandbox, "*.py")
        assert result == []

    def test_list_python_files_only(self, temp_sandbox):
        Path(temp_sandbox, "code.py").write_text("# python")
        Path(temp_sandbox, "data.json").write_text("{}")
        Path(temp_sandbox, "readme.txt").write_text("text")

        result = list_directory(".", temp_sandbox, "*.py")

        assert len(result) == 1
        assert "code.py" in result[0]

    def test_list_recursive(self, temp_sandbox):
        os.makedirs(os.path.join(temp_sandbox, "src", "utils"))
        Path(temp_sandbox, "main.py").write_text("")
        Path(temp_sandbox, "src", "app.py").write_text("")
        Path(temp_sandbox, "src", "utils", "helper.py").write_text("")

        result = list_directory(".", temp_sandbox, "*.py")

        assert len(result) == 3

    def test_list_excludes_pycache(self, temp_sandbox):
        os.makedirs(os.path.join(temp_sandbox, "__pycache__"))
        Path(temp_sandbox, "good.py").write_text("")
        Path(temp_sandbox, "__pycache__", "bad.cpython-310.pyc").write_text("")

        result = list_directory(".", temp_sandbox, "*.py")

        assert len(result) == 1
        assert "__pycache__" not in result[0]

    def test_list_excludes_hidden_directories(self, temp_sandbox):
        os.makedirs(os.path.join(temp_sandbox, ".git"))
        Path(temp_sandbox, "visible.py").write_text("")
        Path(temp_sandbox, ".git", "hidden.py").write_text("")

        result = list_directory(".", temp_sandbox, "*.py")

        assert len(result) == 1
        assert ".git" not in result[0]

    def test_list_with_custom_pattern(self, temp_sandbox):
        Path(temp_sandbox, "test_one.py").write_text("")
        Path(temp_sandbox, "test_two.py").write_text("")
        Path(temp_sandbox, "main.py").write_text("")

        result = list_directory(".", temp_sandbox, "test_*.py")

        assert len(result) == 2
        assert all("test_" in f for f in result)
