"""
File operations with sandbox security for The Refactoring Swarm.

All file operations are restricted to the target directory (sandbox) to prevent
unauthorized access to the file system.
"""

from pathlib import Path
from typing import List


def validate_path(path: str, target_dir: str) -> str:
    """
    Validate that path is within target_dir (sandbox).

    Args:
        path: Path to validate (absolute or relative)
        target_dir: The sandbox directory (from --target_dir CLI arg)

    Returns:
        Resolved absolute path if valid

    Raises:
        PermissionError: If path escapes sandbox
    """
    # Resolve both paths to absolute
    sandbox = Path(target_dir).resolve()

    # Handle relative paths by joining with sandbox
    if not Path(path).is_absolute():
        target = (sandbox / path).resolve()
    else:
        target = Path(path).resolve()

    # Check if target is within sandbox
    try:
        target.relative_to(sandbox)
    except ValueError:
        raise PermissionError(
            f"Security violation: Path '{path}' is outside sandbox '{target_dir}'"
        )

    return str(target)


def read_file(path: str, target_dir: str) -> str:
    """
    Read and return file contents (with sandbox validation).

    Args:
        path: Absolute or relative path to file
        target_dir: Sandbox directory for validation

    Returns:
        File contents as string

    Raises:
        FileNotFoundError: If file doesn't exist
        PermissionError: If path is outside sandbox
    """
    # SECURITY: Validate path is within sandbox
    safe_path = validate_path(path, target_dir)

    with open(safe_path, "r", encoding="utf-8") as f:
        return f.read()


def write_file(path: str, content: str, target_dir: str) -> bool:
    """
    Write content to file (with sandbox validation).

    Args:
        path: Absolute or relative path to file
        content: Complete file content
        target_dir: Sandbox directory for validation

    Returns:
        True if successful

    Raises:
        PermissionError: If path is outside sandbox
    """
    # SECURITY: Validate path is within sandbox
    safe_path = validate_path(path, target_dir)

    # Create parent directories if needed
    Path(safe_path).parent.mkdir(parents=True, exist_ok=True)

    with open(safe_path, "w", encoding="utf-8") as f:
        f.write(content)
    return True


def list_directory(path: str, target_dir: str, pattern: str = "*.py") -> List[str]:
    """
    List files matching pattern in directory (with sandbox validation).

    Args:
        path: Directory path (use "." for target_dir itself)
        target_dir: Sandbox directory for validation
        pattern: Glob pattern (default: *.py)

    Returns:
        List of file paths (all within sandbox)
    """
    # SECURITY: Validate path is within sandbox
    safe_path = validate_path(path, target_dir)

    # Get all matching files recursively
    files = list(Path(safe_path).rglob(pattern))

    # Filter out __pycache__ and hidden directories
    filtered = []
    for f in files:
        parts = f.parts
        if any(part.startswith(".") or part == "__pycache__" for part in parts):
            continue
        # Also filter out test directories for source file listing
        if "tests" in parts and pattern == "*.py":
            continue
        filtered.append(str(f))

    return sorted(filtered)


def list_all_python_files(target_dir: str) -> List[str]:
    """
    List all Python files in target directory, including tests.

    Args:
        target_dir: The target directory to scan

    Returns:
        List of all .py file paths
    """
    sandbox = Path(target_dir).resolve()
    files = list(sandbox.rglob("*.py"))

    # Filter out __pycache__ and hidden directories
    filtered = []
    for f in files:
        parts = f.parts
        if any(part.startswith(".") or part == "__pycache__" for part in parts):
            continue
        filtered.append(str(f))

    return sorted(filtered)
