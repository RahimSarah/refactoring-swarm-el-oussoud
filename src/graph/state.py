"""
State schema for The Refactoring Swarm.

Defines the RefactoringState TypedDict used by LangGraph.
"""

from typing import TypedDict, Literal, List, Dict, Any


class TestResultsDict(TypedDict, total=False):
    """Structured type for test execution results."""

    passed: int
    failed: int
    errors: int
    total: int
    success: bool


class FixAttemptDict(TypedDict):
    """Record of a fix attempt for tracking and avoiding repetition."""

    file: str
    issue: str
    fix_hash: str
    iteration: int


class RefactoringState(TypedDict):
    """
    State schema for the refactoring graph.

    This minimal state schema matches grader expectations.
    Detailed action history is logged to experiment_data.json, not stored in state.
    """

    # === INPUT ===
    target_dir: str  # Path to code directory

    # === DISCOVERY ===
    files: List[str]  # List of Python file paths

    # === AUDITOR OUTPUT ===
    plan: str  # Markdown refactoring plan
    pylint_baseline: float  # Initial Pylint score

    # === ITERATION TRACKING ===
    current_iteration: int  # Current loop count
    max_iterations: int  # Hard limit (default: 10)

    # === FIXER OUTPUT ===
    pylint_current: float  # Latest Pylint score
    fix_attempts: List[FixAttemptDict]  # Track what fixes were tried (SPEC 3.2)

    # === JUDGE OUTPUT ===
    generated_tests: List[str]  # Paths to generated test files
    test_results: Dict[
        str, Any
    ]  # Test execution results (see TestResultsDict for expected shape)
    error_logs: List[
        str
    ]  # Error messages from current iteration (replaced, not accumulated)

    # === CONTEXT MANAGEMENT ===
    context_truncated: bool  # Flag if prompts were truncated due to length

    # === TERMINATION ===
    status: Literal["in_progress", "success", "failure", "max_iterations", "error"]


def initialize_state(target_dir: str, max_iterations: int = 10) -> RefactoringState:
    """
    Create initial state for the refactoring graph.

    Args:
        target_dir: Path to the target directory
        max_iterations: Maximum number of iterations (default: 10)

    Returns:
        Initialized RefactoringState
    """
    return RefactoringState(
        target_dir=target_dir,
        files=[],
        plan="",
        pylint_baseline=0.0,
        current_iteration=0,
        max_iterations=max_iterations,
        pylint_current=0.0,
        fix_attempts=[],  # NEW: Track fix attempts
        generated_tests=[],
        test_results={},
        error_logs=[],
        context_truncated=False,  # NEW: Context truncation flag
        status="in_progress",
    )


def increment_iteration(state: RefactoringState) -> RefactoringState:
    """Increment the iteration counter."""
    state["current_iteration"] += 1
    return state


def check_pylint_improvement(state: RefactoringState) -> bool:
    """Check if Pylint score has improved (required for success)."""
    return state["pylint_current"] >= state["pylint_baseline"]
