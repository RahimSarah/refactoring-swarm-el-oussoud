import pytest
from unittest.mock import patch, MagicMock

from src.graph.state import (
    RefactoringState,
    initialize_state,
    increment_iteration,
    check_pylint_improvement,
)
from src.graph.nodes import should_continue


class TestInitializeState:
    def test_creates_valid_state(self, temp_sandbox):
        state = initialize_state(temp_sandbox)

        assert state["target_dir"] == temp_sandbox
        assert state["files"] == []
        assert state["plan"] == ""
        assert state["current_iteration"] == 0
        assert state["max_iterations"] == 10
        assert state["status"] == "in_progress"

    def test_respects_custom_max_iterations(self, temp_sandbox):
        state = initialize_state(temp_sandbox, max_iterations=5)

        assert state["max_iterations"] == 5

    def test_initializes_empty_error_logs(self, temp_sandbox):
        state = initialize_state(temp_sandbox)

        assert state["error_logs"] == []
        assert isinstance(state["error_logs"], list)

    def test_initializes_pylint_scores_to_zero(self, temp_sandbox):
        state = initialize_state(temp_sandbox)

        assert state["pylint_baseline"] == 0.0
        assert state["pylint_current"] == 0.0


class TestIncrementIteration:
    def test_increments_by_one(self, initial_state):
        initial_state["current_iteration"] = 3

        increment_iteration(initial_state)

        assert initial_state["current_iteration"] == 4

    def test_increments_from_zero(self, initial_state):
        increment_iteration(initial_state)

        assert initial_state["current_iteration"] == 1


class TestCheckPylintImprovement:
    def test_returns_true_when_improved(self, initial_state):
        initial_state["pylint_baseline"] = 5.0
        initial_state["pylint_current"] = 7.5

        assert check_pylint_improvement(initial_state) is True

    def test_returns_true_when_equal(self, initial_state):
        initial_state["pylint_baseline"] = 5.0
        initial_state["pylint_current"] = 5.0

        assert check_pylint_improvement(initial_state) is True

    def test_returns_false_when_decreased(self, initial_state):
        initial_state["pylint_baseline"] = 8.0
        initial_state["pylint_current"] = 6.0

        assert check_pylint_improvement(initial_state) is False


class TestShouldContinue:
    def test_returns_end_on_success(self, initial_state):
        initial_state["status"] = "success"
        initial_state["current_iteration"] = 3

        result = should_continue(initial_state)

        assert result == "end"

    def test_returns_end_on_max_iterations(self, initial_state):
        """Test that should_continue returns 'end' when status is 'max_iterations'.

        Note: In the refactored design, should_continue() is a PURE routing function.
        The 'max_iterations' status is now set by judge_validate_node() before
        should_continue() is called.
        """
        initial_state["status"] = "max_iterations"  # Set by judge_validate_node
        initial_state["current_iteration"] = 10
        initial_state["max_iterations"] = 10

        result = should_continue(initial_state)

        assert result == "end"
        # Status is already set, should_continue just routes
        assert initial_state["status"] == "max_iterations"

    def test_returns_continue_when_in_progress(self, initial_state):
        initial_state["status"] = "in_progress"
        initial_state["current_iteration"] = 3
        initial_state["max_iterations"] = 10

        result = should_continue(initial_state)

        assert result == "continue"

    def test_returns_continue_at_iteration_boundary(self, initial_state):
        initial_state["status"] = "in_progress"
        initial_state["current_iteration"] = 9
        initial_state["max_iterations"] = 10

        result = should_continue(initial_state)

        assert result == "continue"

    def test_handles_failure_status(self, initial_state):
        initial_state["status"] = "failure"
        initial_state["current_iteration"] = 3

        result = should_continue(initial_state)

        assert result == "continue"


class TestStateTransitions:
    def test_error_logs_accumulate(self, initial_state):
        initial_state["error_logs"] = ["Error 1"]
        initial_state["error_logs"].append("Error 2")

        assert len(initial_state["error_logs"]) == 2
        assert "Error 1" in initial_state["error_logs"]
        assert "Error 2" in initial_state["error_logs"]

    def test_files_can_be_updated(self, initial_state):
        initial_state["files"] = ["file1.py", "file2.py"]

        assert len(initial_state["files"]) == 2

    def test_plan_can_be_set(self, initial_state):
        initial_state["plan"] = "# Refactoring Plan\n## Issue 1"

        assert "Refactoring Plan" in initial_state["plan"]

    def test_generated_tests_tracking(self, initial_state):
        initial_state["generated_tests"] = ["tests/test_a.py", "tests/test_b.py"]

        assert len(initial_state["generated_tests"]) == 2


class TestStateValidation:
    def test_status_must_be_valid_literal(self, temp_sandbox):
        state = initialize_state(temp_sandbox)

        # Test all valid statuses including the new "error" status
        valid_statuses = [
            "in_progress",
            "success",
            "failure",
            "max_iterations",
            "error",
        ]

        for status in valid_statuses:
            state["status"] = status  # type: ignore
            assert state["status"] == status

    def test_iteration_count_is_integer(self, initial_state):
        assert isinstance(initial_state["current_iteration"], int)
        assert isinstance(initial_state["max_iterations"], int)

    def test_pylint_scores_are_floats(self, initial_state):
        assert isinstance(initial_state["pylint_baseline"], float)
        assert isinstance(initial_state["pylint_current"], float)


class TestShouldContinueErrorStatus:
    """Tests for error status handling in should_continue (new functionality)."""

    def test_returns_end_on_error_status(self, initial_state):
        """Test that should_continue returns 'end' when status is 'error'."""
        initial_state["status"] = "error"
        initial_state["current_iteration"] = 1

        result = should_continue(initial_state)

        assert result == "end"

    def test_error_status_not_mutated(self, initial_state):
        """Test that should_continue doesn't mutate error status (pure function)."""
        initial_state["status"] = "error"

        should_continue(initial_state)

        # Status should remain unchanged
        assert initial_state["status"] == "error"


class TestJudgeValidateNodeMaxIterations:
    """Tests for max_iterations handling in judge_validate_node."""

    def test_sets_max_iterations_status_when_limit_reached(
        self, sandbox_with_clean_code, disable_logging
    ):
        """Test that judge_validate_node sets max_iterations status correctly."""
        from unittest.mock import patch, MagicMock
        from src.graph.nodes import judge_validate_node
        import os
        from pathlib import Path

        # Create test that will pass
        tests_dir = os.path.join(sandbox_with_clean_code, "tests")
        os.makedirs(tests_dir, exist_ok=True)
        Path(tests_dir, "__init__.py").write_text("")
        Path(tests_dir, "test_clean.py").write_text(
            "def test_fails():\n    assert False\n"
        )

        with patch("src.graph.nodes.get_config") as mock_cfg:
            config = MagicMock()
            config.llm_provider = "mistral"
            config.mistral_api_key = "fake-key"
            config.llm_model = "test-model"
            mock_cfg.return_value = config

            with patch("src.graph.nodes.get_llm_provider") as mock_provider:
                provider = MagicMock()
                mock_provider.return_value = provider

                state = initialize_state(sandbox_with_clean_code, max_iterations=2)
                state["current_iteration"] = 2  # At the limit

                result = judge_validate_node(state)

                # After incrementing, iteration will be 3 which exceeds max of 2
                assert result["status"] == "max_iterations"
                assert result["current_iteration"] == 3
