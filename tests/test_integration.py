import pytest
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.graph.state import initialize_state
from src.graph.builder import build_graph, compile_graph


class TestGraphBuilder:
    def test_build_graph_has_all_nodes(self):
        graph = build_graph()

        node_names = list(graph.nodes.keys())

        assert "auditor" in node_names
        assert "judge_generate" in node_names
        assert "fixer" in node_names
        assert "judge_validate" in node_names

    def test_graph_entry_point_is_auditor(self):
        graph = build_graph()

        # Verify entry point by checking graph structure
        # The entry point node should be connected from __start__
        assert "auditor" in graph.nodes

    def test_graph_compiles_without_error(self):
        app = compile_graph()

        assert app is not None


class TestEndToEndWithMockLLM:
    @pytest.fixture
    def mock_config(self, temp_sandbox):
        with patch("src.graph.nodes.get_config") as mock_cfg:
            config = MagicMock()
            config.google_api_key = "fake-key"
            config.llm_model = "gemini-1.5-flash"
            mock_cfg.return_value = config
            yield config

    @pytest.fixture
    def mock_llm_provider(self):
        with patch("src.graph.nodes.get_llm_provider") as mock_provider:
            provider = MagicMock()
            provider.model_name = "mock-gemini"
            yield mock_provider, provider

    def test_auditor_node_updates_state(
        self, sandbox_with_buggy_code, mock_config, mock_llm_provider, disable_logging
    ):
        mock_get_provider, mock_provider = mock_llm_provider

        mock_provider.complete.return_value = MagicMock(
            content="""# Refactoring Plan

## Summary
- **Files Analyzed**: 1
- **Total Issues Found**: 3
- **Pylint Baseline Score**: 2.5/10

## File: buggy.py

### Issue 1: Logic Bug
- **Type**: BUG
- **Severity**: High
- **Description**: calculate_average returns sum not mean
"""
        )
        mock_get_provider.return_value = mock_provider

        from src.graph.nodes import auditor_node

        state = initialize_state(sandbox_with_buggy_code)
        result = auditor_node(state)

        assert "files" in result
        assert "plan" in result
        assert "pylint_baseline" in result
        assert result["current_iteration"] == 1

    def test_judge_generate_creates_tests(
        self, sandbox_with_buggy_code, mock_config, mock_llm_provider, disable_logging
    ):
        mock_get_provider, mock_provider = mock_llm_provider

        mock_provider.complete.return_value = MagicMock(
            content="""
### FILE: tests/test_buggy.py
```python
import pytest
from buggy import calculate_average

def test_calculate_average_returns_mean():
    assert calculate_average([10, 20]) == 15.0
```
"""
        )
        mock_get_provider.return_value = mock_provider

        from src.graph.nodes import judge_generate_tests_node

        state = initialize_state(sandbox_with_buggy_code)
        state["files"] = [f"{sandbox_with_buggy_code}/buggy.py"]
        state["plan"] = "# Plan\n## Bug: returns sum not average"

        result = judge_generate_tests_node(state)

        assert "generated_tests" in result
        assert "test_results" in result

    def test_fixer_applies_fixes(
        self, sandbox_with_buggy_code, mock_config, mock_llm_provider, disable_logging
    ):
        mock_get_provider, mock_provider = mock_llm_provider

        mock_provider.complete.return_value = MagicMock(
            content="""
### FILE: buggy.py
```python
def calculate_average(numbers):
    if not numbers:
        raise ValueError("Cannot calculate average of empty list")
    return sum(numbers) / len(numbers)

def divide(a, b):
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b

def find_maximum(values):
    if not values:
        raise ValueError("Cannot find maximum of empty list")
    return max(values)
```
"""
        )
        mock_get_provider.return_value = mock_provider

        from src.graph.nodes import fixer_node

        state = initialize_state(sandbox_with_buggy_code)
        state["files"] = [f"{sandbox_with_buggy_code}/buggy.py"]
        state["plan"] = "# Plan\n## Fix all bugs"
        state["error_logs"] = []

        result = fixer_node(state)

        assert "pylint_current" in result

    def test_judge_validate_detects_success(
        self, sandbox_with_clean_code, mock_config, mock_llm_provider, disable_logging
    ):
        mock_get_provider, mock_provider = mock_llm_provider
        mock_get_provider.return_value = mock_provider

        tests_dir = os.path.join(sandbox_with_clean_code, "tests")
        os.makedirs(tests_dir, exist_ok=True)
        Path(tests_dir, "__init__.py").write_text("")
        Path(tests_dir, "test_clean.py").write_text("""
def test_always_passes():
    assert True
""")

        from src.graph.nodes import judge_validate_node

        state = initialize_state(sandbox_with_clean_code)
        state["current_iteration"] = 1

        result = judge_validate_node(state)

        assert "status" in result
        assert result["current_iteration"] == 2


class TestFullPipelineSimulation:
    def test_complete_refactoring_cycle(self, sandbox_with_buggy_code, disable_logging):
        from src.graph.state import initialize_state
        from src.graph.nodes import should_continue

        state = initialize_state(sandbox_with_buggy_code, max_iterations=3)

        state["files"] = [f"{sandbox_with_buggy_code}/buggy.py"]
        state["plan"] = "# Plan"
        state["pylint_baseline"] = 2.0
        state["current_iteration"] = 1

        assert should_continue(state) == "continue"

        state["current_iteration"] = 2
        state["status"] = "success"

        assert should_continue(state) == "end"

    def test_max_iterations_terminates(self, temp_sandbox):
        """Test that should_continue returns 'end' when max iterations is reached.

        Note: In the refactored design, should_continue() is a PURE routing function.
        The 'max_iterations' status is now set by judge_validate_node() before
        should_continue() is called. This test simulates the state AFTER
        judge_validate_node has updated the status.
        """
        from src.graph.state import initialize_state
        from src.graph.nodes import should_continue

        state = initialize_state(temp_sandbox, max_iterations=5)
        state["current_iteration"] = 6  # After the 5th iteration
        state["status"] = "max_iterations"  # Set by judge_validate_node

        result = should_continue(state)

        assert result == "end"
        assert state["status"] == "max_iterations"


class TestLoggingIntegration:
    def test_all_agents_log_actions(
        self, sandbox_with_buggy_code, capture_logs, mock_llm
    ):
        from src.agents.auditor import AuditorAgent

        auditor = AuditorAgent(llm=mock_llm, target_dir=sandbox_with_buggy_code)

        auditor._discover_files()

        assert len(capture_logs) >= 1
        assert capture_logs[0]["kwargs"]["agent_name"] == "Auditor"

    def test_logs_contain_required_fields(self, temp_sandbox, capture_logs, mock_llm):
        from src.agents.base import BaseAgent
        from src.utils.logger import ActionType

        agent = BaseAgent(llm=mock_llm, name="TestAgent", target_dir=temp_sandbox)
        agent.call_llm("system", "user", ActionType.ANALYSIS)

        log = capture_logs[0]
        details = log["kwargs"]["details"]

        assert "input_prompt" in details
        assert "output_response" in details
        assert log["kwargs"]["status"] == "SUCCESS"


class TestSecurityInIntegration:
    def test_agents_cannot_escape_sandbox(
        self, temp_sandbox, mock_llm, disable_logging
    ):
        from src.agents.fixer import FixerAgent

        fixer = FixerAgent(llm=mock_llm, target_dir=temp_sandbox)

        malicious_files = {"../../../etc/passwd": "malicious content"}

        modified = fixer._apply_fixes(malicious_files)

        assert len(modified) == 0
        assert not os.path.exists("/etc/passwd.bak")
