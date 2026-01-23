"""Retry utilities for handling transient failures in external service calls.

This module provides configurable retry logic using the tenacity library,
designed for resilient communication with third-party services like
Deepgram (STT), Google Gemini (LLM), and Cartesia (TTS).

The retry mechanism handles:
- Network timeouts and connection errors
- Rate limiting (429 responses)
- Temporary service unavailability (5xx errors)

Example:
    ```python
    from backend.utils.retry import service_retry, RetryConfig

    # Using default configuration
    @service_retry()
    async def call_external_api():
        return await some_api_call()

    # Using custom configuration
    config = RetryConfig(max_attempts=5, base_delay=2.0)

    @service_retry(config=config)
    async def call_critical_api():
        return await critical_api_call()
    ```
"""

import asyncio
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, Optional, Tuple, Type, TypeVar

from loguru import logger
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
    after_log,
)

# Type variable for generic function signatures
F = TypeVar("F", bound=Callable[..., Any])


# Common transient exceptions that should trigger retries
TRANSIENT_EXCEPTIONS: Tuple[Type[Exception], ...] = (
    ConnectionError,
    TimeoutError,
    asyncio.TimeoutError,
    OSError,  # Includes network-related errors
)


@dataclass
class RetryConfig:
    """Configuration for retry behavior.

    Attributes:
        max_attempts: Maximum number of retry attempts (including initial).
        base_delay: Base delay in seconds for exponential backoff.
        max_delay: Maximum delay in seconds between retries.
        exponential_base: Base for exponential backoff calculation.
        retry_exceptions: Tuple of exception types that should trigger retries.
        service_name: Optional name for logging purposes.
    """

    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    exponential_base: int = 2
    retry_exceptions: Tuple[Type[Exception], ...] = field(
        default_factory=lambda: TRANSIENT_EXCEPTIONS
    )
    service_name: Optional[str] = None


# Default retry configuration for external services
default_retry_config = RetryConfig(
    max_attempts=3,
    base_delay=1.0,
    max_delay=30.0,
    exponential_base=2,
)


def retry_with_config(config: RetryConfig) -> AsyncRetrying:
    """Create an AsyncRetrying instance with the given configuration.

    Args:
        config: The retry configuration to use.

    Returns:
        An AsyncRetrying instance configured with the specified parameters.
    """
    return AsyncRetrying(
        stop=stop_after_attempt(config.max_attempts),
        wait=wait_exponential(
            multiplier=config.base_delay,
            max=config.max_delay,
            exp_base=config.exponential_base,
        ),
        retry=retry_if_exception_type(config.retry_exceptions),
        before_sleep=before_sleep_log(logger, log_level=20),  # INFO level
        after=after_log(logger, log_level=20),
        reraise=True,
    )


def service_retry(
    config: Optional[RetryConfig] = None,
    service_name: Optional[str] = None,
) -> Callable[[F], F]:
    """Decorator for adding retry logic to async functions.

    This decorator wraps async functions with retry logic, automatically
    retrying on transient failures with exponential backoff.

    Args:
        config: Optional retry configuration. Uses default if not provided.
        service_name: Optional service name for logging. If not provided,
            uses the function name.

    Returns:
        A decorator that adds retry logic to the wrapped function.

    Example:
        ```python
        @service_retry(service_name="Deepgram")
        async def transcribe_audio(audio_data: bytes) -> str:
            return await deepgram_client.transcribe(audio_data)
        ```
    """
    retry_config = config or default_retry_config

    def decorator(func: F) -> F:
        name = service_name or retry_config.service_name or func.__name__

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            retrying = retry_with_config(retry_config)
            attempt = 0

            try:
                async for attempt_state in retrying:
                    with attempt_state:
                        attempt = attempt_state.retry_state.attempt_number
                        if attempt > 1:
                            logger.info(
                                f"{name}: Retry attempt {attempt}/{retry_config.max_attempts}"
                            )
                        return await func(*args, **kwargs)
            except RetryError as e:
                logger.error(
                    f"{name}: All {retry_config.max_attempts} retry attempts failed. "
                    f"Last error: {e.last_attempt.exception()}"
                )
                raise e.last_attempt.exception() from e

        return wrapper  # type: ignore

    return decorator


class ServiceInitializer:
    """Helper class for initializing services with retry logic.

    This class provides a context manager pattern for service initialization
    that includes retry logic for handling transient failures during startup.

    Example:
        ```python
        async with ServiceInitializer("Deepgram", config) as initializer:
            stt = await initializer.initialize(
                lambda: DeepgramSTTService(api_key=api_key)
            )
        ```
    """

    def __init__(
        self,
        service_name: str,
        config: Optional[RetryConfig] = None,
    ):
        """Initialize the ServiceInitializer.

        Args:
            service_name: Name of the service for logging.
            config: Optional retry configuration.
        """
        self.service_name = service_name
        self.config = config or default_retry_config

    async def __aenter__(self) -> "ServiceInitializer":
        """Enter the async context manager."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit the async context manager."""
        pass

    @service_retry()
    async def initialize(self, factory: Callable[[], Any]) -> Any:
        """Initialize a service using the provided factory function.

        Args:
            factory: A callable that creates and returns the service instance.

        Returns:
            The initialized service instance.

        Raises:
            Exception: If all retry attempts fail.
        """
        logger.debug(f"{self.service_name}: Initializing service...")
        service = factory()
        logger.info(f"{self.service_name}: Service initialized successfully")
        return service


async def with_retry(
    func: Callable[..., Any],
    *args: Any,
    config: Optional[RetryConfig] = None,
    service_name: Optional[str] = None,
    **kwargs: Any,
) -> Any:
    """Execute an async function with retry logic.

    This is a convenience function for one-off retryable operations
    without needing to use the decorator pattern.

    Args:
        func: The async function to execute.
        *args: Positional arguments to pass to the function.
        config: Optional retry configuration.
        service_name: Optional service name for logging.
        **kwargs: Keyword arguments to pass to the function.

    Returns:
        The result of the function call.

    Raises:
        Exception: If all retry attempts fail.

    Example:
        ```python
        result = await with_retry(
            external_api_call,
            param1, param2,
            service_name="ExternalAPI",
        )
        ```
    """
    retry_config = config or default_retry_config
    name = service_name or func.__name__

    @service_retry(config=retry_config, service_name=name)
    async def wrapped() -> Any:
        return await func(*args, **kwargs)

    return await wrapped()
