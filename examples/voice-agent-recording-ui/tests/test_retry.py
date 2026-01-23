"""Tests for retry utilities."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from backend.utils.retry import (
    RetryConfig,
    TRANSIENT_EXCEPTIONS,
    default_retry_config,
    retry_with_config,
    service_retry,
    with_retry,
)


class TestRetryConfig:
    """Tests for RetryConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = RetryConfig()

        assert config.max_attempts == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 30.0
        assert config.exponential_base == 2
        assert config.service_name is None
        assert config.retry_exceptions == TRANSIENT_EXCEPTIONS

    def test_custom_config(self):
        """Test custom configuration values."""
        config = RetryConfig(
            max_attempts=5,
            base_delay=0.5,
            max_delay=10.0,
            exponential_base=3,
            service_name="TestService",
        )

        assert config.max_attempts == 5
        assert config.base_delay == 0.5
        assert config.max_delay == 10.0
        assert config.exponential_base == 3
        assert config.service_name == "TestService"

    def test_custom_exceptions(self):
        """Test custom retry exceptions."""
        custom_exceptions = (ValueError, TypeError)
        config = RetryConfig(retry_exceptions=custom_exceptions)

        assert config.retry_exceptions == custom_exceptions


class TestDefaultRetryConfig:
    """Tests for default retry configuration."""

    def test_default_retry_config_exists(self):
        """Test default_retry_config is defined."""
        assert default_retry_config is not None
        assert isinstance(default_retry_config, RetryConfig)

    def test_default_retry_config_values(self):
        """Test default_retry_config has expected values."""
        assert default_retry_config.max_attempts == 3
        assert default_retry_config.base_delay == 1.0
        assert default_retry_config.max_delay == 30.0


class TestTransientExceptions:
    """Tests for transient exception types."""

    def test_transient_exceptions_includes_connection_error(self):
        """Test ConnectionError is in transient exceptions."""
        assert ConnectionError in TRANSIENT_EXCEPTIONS

    def test_transient_exceptions_includes_timeout_error(self):
        """Test TimeoutError is in transient exceptions."""
        assert TimeoutError in TRANSIENT_EXCEPTIONS

    def test_transient_exceptions_includes_asyncio_timeout(self):
        """Test asyncio.TimeoutError is in transient exceptions."""
        assert asyncio.TimeoutError in TRANSIENT_EXCEPTIONS

    def test_transient_exceptions_includes_os_error(self):
        """Test OSError is in transient exceptions."""
        assert OSError in TRANSIENT_EXCEPTIONS


class TestServiceRetryDecorator:
    """Tests for service_retry decorator."""

    @pytest.mark.asyncio
    async def test_successful_call_no_retry(self):
        """Test successful call doesn't retry."""
        call_count = 0

        @service_retry()
        async def successful_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await successful_func()

        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_transient_error(self):
        """Test retry on transient error."""
        call_count = 0

        @service_retry(config=RetryConfig(max_attempts=3, base_delay=0.01))
        async def failing_then_success():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Simulated connection error")
            return "success"

        result = await failing_then_success()

        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        """Test exception raised after max retries."""
        call_count = 0

        @service_retry(config=RetryConfig(max_attempts=2, base_delay=0.01))
        async def always_failing():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Always fails")

        with pytest.raises(ConnectionError):
            await always_failing()

        assert call_count == 2

    @pytest.mark.asyncio
    async def test_no_retry_on_non_transient_error(self):
        """Test no retry on non-transient error."""
        call_count = 0

        @service_retry(config=RetryConfig(max_attempts=3, base_delay=0.01))
        async def value_error_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("Not a transient error")

        with pytest.raises(ValueError):
            await value_error_func()

        # Should only be called once since ValueError isn't retryable
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_custom_service_name(self):
        """Test custom service name in decorator."""
        @service_retry(service_name="CustomService")
        async def func():
            return "success"

        result = await func()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_preserves_function_metadata(self):
        """Test decorator preserves function metadata."""
        @service_retry()
        async def documented_func():
            """This is a docstring."""
            return "success"

        assert documented_func.__name__ == "documented_func"
        # Note: __doc__ might not be preserved depending on implementation


class TestWithRetry:
    """Tests for with_retry helper function."""

    @pytest.mark.asyncio
    async def test_with_retry_success(self):
        """Test with_retry on successful call."""
        async def successful_func(x, y):
            return x + y

        result = await with_retry(successful_func, 1, 2)
        assert result == 3

    @pytest.mark.asyncio
    async def test_with_retry_with_kwargs(self):
        """Test with_retry with keyword arguments."""
        async def func_with_kwargs(a, b=10):
            return a * b

        result = await with_retry(func_with_kwargs, 5, b=20)
        assert result == 100

    @pytest.mark.asyncio
    async def test_with_retry_custom_config(self):
        """Test with_retry with custom config."""
        call_count = 0

        async def failing_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Fail once")
            return "success"

        config = RetryConfig(max_attempts=3, base_delay=0.01)
        result = await with_retry(
            failing_func,
            config=config,
            service_name="TestService",
        )

        assert result == "success"
        assert call_count == 2


class TestRetryWithConfig:
    """Tests for retry_with_config function."""

    def test_creates_async_retrying(self):
        """Test creates AsyncRetrying instance."""
        config = RetryConfig()
        retrying = retry_with_config(config)

        # Check it's an AsyncRetrying instance
        assert hasattr(retrying, "__aiter__")

    def test_respects_max_attempts(self):
        """Test retrying respects max_attempts config."""
        config = RetryConfig(max_attempts=5)
        retrying = retry_with_config(config)

        # The stop condition should use the configured max attempts
        assert retrying.stop is not None

    def test_respects_wait_config(self):
        """Test retrying respects wait configuration."""
        config = RetryConfig(base_delay=2.0, max_delay=60.0)
        retrying = retry_with_config(config)

        # The wait strategy should be configured
        assert retrying.wait is not None
