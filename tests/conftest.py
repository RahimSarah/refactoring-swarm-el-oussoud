import os
import sys
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch
from dataclasses import dataclass

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.llm.base import Message, LLMResponse, LLMProvider
from src.graph.state import RefactoringState, initialize_state


@dataclass
class MockLLMResponse:
    content: str
    model: str = "mock-model"
    usage: dict = None

    def __post_init__(self):
        if self.usage is None:
            self.usage = {"prompt_tokens": 100, "completion_tokens": 50}


class MockLLMProvider:
    def __init__(self, responses: list[str] = None):
        self._responses = responses or ["Mock response"]
        self._call_count = 0
        self._calls = []

    @property
    def model_name(self) -> str:
        return "mock-gemini-1.5-flash"

    def complete(
        self, messages: list[Message], temperature: float = 0.7, max_tokens: int = 4096
    ) -> LLMResponse:
        self._calls.append({"messages": messages, "temperature": temperature})
        response = self._responses[min(self._call_count, len(self._responses) - 1)]
        self._call_count += 1
        return LLMResponse(content=response, model=self.model_name, usage={})


@pytest.fixture
def mock_llm():
    return MockLLMProvider()


@pytest.fixture
def mock_llm_with_responses():
    def _create(responses: list[str]):
        return MockLLMProvider(responses)

    return _create


@pytest.fixture
def temp_sandbox():
    sandbox = tempfile.mkdtemp(prefix="refactor_test_")
    yield sandbox
    shutil.rmtree(sandbox, ignore_errors=True)


@pytest.fixture
def sandbox_with_buggy_code(temp_sandbox):
    code = """def calculate_average(numbers):
    return sum(numbers)

def divide(a, b):
    return a / b

def find_maximum(values):
    return min(values)
"""
    code_path = Path(temp_sandbox) / "buggy.py"
    code_path.write_text(code)
    return temp_sandbox


@pytest.fixture
def sandbox_with_clean_code(temp_sandbox):
    code = '''"""Clean calculator module."""


def calculate_average(numbers: list[float]) -> float:
    """Calculate the arithmetic mean of a list of numbers."""
    if not numbers:
        raise ValueError("Cannot calculate average of empty list")
    return sum(numbers) / len(numbers)


def divide(a: float, b: float) -> float:
    """Divide a by b with zero-check."""
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b


def find_maximum(values: list) -> any:
    """Find the maximum value in a list."""
    if not values:
        raise ValueError("Cannot find maximum of empty list")
    return max(values)
'''
    code_path = Path(temp_sandbox) / "clean.py"
    code_path.write_text(code)
    return temp_sandbox


@pytest.fixture
def initial_state(temp_sandbox):
    return initialize_state(target_dir=temp_sandbox, max_iterations=10)


@pytest.fixture
def state_after_auditor(temp_sandbox):
    state = initialize_state(target_dir=temp_sandbox, max_iterations=10)
    state["files"] = [f"{temp_sandbox}/buggy.py"]
    state["plan"] = """# Refactoring Plan

## Summary
- **Files Analyzed**: 1
- **Total Issues Found**: 3
- **Pylint Baseline Score**: 2.5/10

## File: buggy.py

### Issue 1: Logic Bug (Line 2)
- **Type**: `BUG`
- **Severity**: High
- **Description**: calculate_average returns sum instead of mean
- **Suggested Fix**: Divide sum by len(numbers)

### Issue 2: Division by Zero (Line 5)
- **Type**: `BUG`
- **Severity**: High
- **Description**: No zero-check in divide function
- **Suggested Fix**: Add if b == 0 check

### Issue 3: Logic Bug (Line 8)
- **Type**: `BUG`
- **Severity**: High
- **Description**: find_maximum returns minimum instead
- **Suggested Fix**: Use max() instead of min()
"""
    state["pylint_baseline"] = 2.5
    state["current_iteration"] = 1
    return state


@pytest.fixture
def disable_logging():
    with patch("src.agents.base.log_experiment") as mock_log:
        mock_log.return_value = None
        yield mock_log


@pytest.fixture
def capture_logs():
    logs = []

    def capture(*args, **kwargs):
        logs.append({"args": args, "kwargs": kwargs})

    with patch("src.agents.base.log_experiment", side_effect=capture):
        yield logs
