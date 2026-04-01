"""Tenacity adapters for :mod:`pyfetcher`.

Purpose:
    Convert retry policy models into :mod:`tenacity` retrying objects for
    both synchronous and asynchronous execution.

Design:
    - Policy is modeled separately in :mod:`pyfetcher.contracts.policy`.
    - Retry decisions are applied at the service layer, not the transport layer.
    - Logging uses the standard library logger.

Examples:
    ::

        >>> policy = RetryPolicy(attempts=3)
        >>> retrying = build_retrying(policy)
        >>> retrying.stop.max_attempt_number
        3
"""

from __future__ import annotations

import logging

from tenacity import (
    AsyncRetrying,
    Retrying,
    before_sleep_log,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from pyfetcher.contracts.policy import RetryPolicy

logger = logging.getLogger("pyfetcher.retry")


class RetryableStatusCodeError(RuntimeError):
    """Error raised for retryable HTTP status codes.

    This exception is raised by the fetch service when a response's status
    code matches one of the configured retryable codes. Tenacity catches
    it to trigger another attempt.

    Args:
        status_code: The HTTP status code that triggered the retry.
        message: Optional human-readable message override.

    Examples:
        ::

            >>> str(RetryableStatusCodeError(429))
            'Retryable HTTP status code: 429'
    """

    def __init__(self, status_code: int, message: str | None = None) -> None:
        self.status_code = status_code
        super().__init__(message or f"Retryable HTTP status code: {status_code}")


def _build_retry_exceptions(policy: RetryPolicy) -> tuple[type[BaseException], ...]:
    """Build the tuple of exception types that should trigger retries.

    Args:
        policy: The retry policy specifying which errors to retry.

    Returns:
        A tuple of exception types that Tenacity should catch.

    Examples:
        ::

            >>> RetryableStatusCodeError in _build_retry_exceptions(RetryPolicy())
            True
    """
    exceptions: list[type[BaseException]] = [RetryableStatusCodeError]
    if policy.retry_on_connection_errors:
        exceptions.extend([OSError, TimeoutError, ConnectionError])
    return tuple(exceptions)


def build_retrying(policy: RetryPolicy) -> Retrying:
    """Build a synchronous :class:`tenacity.Retrying` from a retry policy.

    Configures exponential backoff with the policy's base and max wait times,
    stops after the configured number of attempts, and retries on the
    appropriate exception types.

    Args:
        policy: The retry policy to convert.

    Returns:
        A configured :class:`tenacity.Retrying` instance.

    Examples:
        ::

            >>> retrying = build_retrying(RetryPolicy(attempts=2))
            >>> retrying.stop.max_attempt_number
            2
    """
    return Retrying(
        stop=stop_after_attempt(policy.attempts),
        wait=wait_exponential(
            multiplier=policy.wait_base_seconds,
            max=policy.wait_max_seconds,
        ),
        retry=retry_if_exception_type(_build_retry_exceptions(policy)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=policy.reraise,
    )


def build_async_retrying(policy: RetryPolicy) -> AsyncRetrying:
    """Build an asynchronous :class:`tenacity.AsyncRetrying` from a retry policy.

    Identical configuration to :func:`build_retrying` but returns an
    async-compatible retrying object.

    Args:
        policy: The retry policy to convert.

    Returns:
        A configured :class:`tenacity.AsyncRetrying` instance.

    Examples:
        ::

            >>> retrying = build_async_retrying(RetryPolicy(attempts=2))
            >>> retrying.stop.max_attempt_number
            2
    """
    return AsyncRetrying(
        stop=stop_after_attempt(policy.attempts),
        wait=wait_exponential(
            multiplier=policy.wait_base_seconds,
            max=policy.wait_max_seconds,
        ),
        retry=retry_if_exception_type(_build_retry_exceptions(policy)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=policy.reraise,
    )
