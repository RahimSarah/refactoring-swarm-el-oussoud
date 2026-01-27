"""
Tests for retry logic in LLM providers.

Tests the with_retry decorator and related functionality.
"""

import pytest
import time
from unittest.mock import MagicMock, patch

from src.llm.mistral import with_retry


class TestWithRetryDecorator:
    """Tests for the with_retry decorator."""

    def test_succeeds_on_first_attempt(self):
        """Test that successful calls return immediately."""
        call_count = 0

        @with_retry(max_retries=3, base_delay=0.01)
        def successful_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = successful_func()

        assert result == "success"
        assert call_count == 1

    def test_retries_on_failure(self):
        """Test that function is retried on exception."""
        call_count = 0

        @with_retry(max_retries=3, base_delay=0.01)
        def failing_then_succeeding():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary failure")
            return "success"

        result = failing_then_succeeding()

        assert result == "success"
        assert call_count == 3

    def test_raises_after_max_retries(self):
        """Test that exception is raised after max retries."""
        call_count = 0

        @with_retry(max_retries=2, base_delay=0.01)
        def always_failing():
            nonlocal call_count
            call_count += 1
            raise ValueError("Always fails")

        with pytest.raises(ValueError, match="Always fails"):
            always_failing()

        # 1 initial + 2 retries = 3 total attempts
        assert call_count == 3

    def test_exponential_backoff(self):
        """Test that delay increases exponentially."""
        call_times = []

        @with_retry(max_retries=3, base_delay=0.05, max_delay=10.0)
        def track_timing():
            call_times.append(time.time())
            if len(call_times) < 4:
                raise ValueError("Keep trying")
            return "success"

        track_timing()

        # Check delays are increasing
        if len(call_times) >= 3:
            delay1 = call_times[1] - call_times[0]
            delay2 = call_times[2] - call_times[1]
            # Second delay should be approximately 2x the first
            assert delay2 >= delay1 * 1.5  # Allow some tolerance

    def test_respects_max_delay(self):
        """Test that delay doesn't exceed max_delay."""
        call_times = []

        @with_retry(max_retries=4, base_delay=1.0, max_delay=0.1)
        def track_timing():
            call_times.append(time.time())
            if len(call_times) < 5:
                raise ValueError("Keep trying")
            return "success"

        track_timing()

        # All delays should be near max_delay (0.1s)
        for i in range(1, len(call_times)):
            delay = call_times[i] - call_times[i - 1]
            assert delay < 0.2  # max_delay + tolerance

    def test_only_catches_specified_exceptions(self):
        """Test that only specified exception types are retried."""
        call_count = 0

        @with_retry(max_retries=3, base_delay=0.01, exceptions=(ValueError,))
        def raises_type_error():
            nonlocal call_count
            call_count += 1
            raise TypeError("Not retried")

        with pytest.raises(TypeError, match="Not retried"):
            raises_type_error()

        # Should not retry for TypeError
        assert call_count == 1

    def test_catches_multiple_exception_types(self):
        """Test retry with multiple exception types."""
        call_count = 0

        @with_retry(max_retries=3, base_delay=0.01, exceptions=(ValueError, OSError))
        def alternating_errors():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("First error")
            elif call_count == 2:
                raise OSError("Second error")
            return "success"

        result = alternating_errors()

        assert result == "success"
        assert call_count == 3

    def test_preserves_function_metadata(self):
        """Test that decorator preserves function name and docstring."""

        @with_retry()
        def documented_function():
            """This is the docstring."""
            pass

        assert documented_function.__name__ == "documented_function"
        assert "docstring" in documented_function.__doc__

    def test_passes_arguments_correctly(self):
        """Test that args and kwargs are passed to wrapped function."""

        @with_retry(max_retries=1, base_delay=0.01)
        def func_with_args(a, b, c=None):
            return f"{a}-{b}-{c}"

        result = func_with_args("x", "y", c="z")

        assert result == "x-y-z"


class TestRetryLogging:
    """Tests for retry logging behavior."""

    def test_logs_warning_on_retry(self):
        """Test that warnings are logged on retry attempts."""
        with patch("src.llm.mistral.logger") as mock_logger:
            call_count = 0

            @with_retry(max_retries=2, base_delay=0.01)
            def failing_func():
                nonlocal call_count
                call_count += 1
                if call_count < 3:
                    raise ValueError("Fail")
                return "ok"

            failing_func()

            # Should have logged 2 warnings (for 2 retry attempts)
            assert mock_logger.warning.call_count == 2

    def test_logs_error_on_final_failure(self):
        """Test that error is logged when all retries exhausted."""
        with patch("src.llm.mistral.logger") as mock_logger:

            @with_retry(max_retries=1, base_delay=0.01)
            def always_fails():
                raise ValueError("Always fails")

            with pytest.raises(ValueError):
                always_fails()

            # Should have logged 1 warning (for retry) and 1 error (for final failure)
            assert mock_logger.warning.call_count == 1
            assert mock_logger.error.call_count == 1
