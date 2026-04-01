"""Unit tests for pyfetcher.retry."""

from __future__ import annotations

from pyfetcher.contracts.policy import RetryPolicy
from pyfetcher.retry.tenacity import (
    RetryableStatusCodeError,
    _build_retry_exceptions,
    build_async_retrying,
    build_retrying,
)


class TestRetryableStatusCodeError:
    def test_message(self) -> None:
        err = RetryableStatusCodeError(429)
        assert "429" in str(err)
        assert err.status_code == 429

    def test_custom_message(self) -> None:
        err = RetryableStatusCodeError(503, "Service unavailable")
        assert str(err) == "Service unavailable"


class TestBuildRetryExceptions:
    def test_includes_status_code_error(self) -> None:
        exceptions = _build_retry_exceptions(RetryPolicy())
        assert RetryableStatusCodeError in exceptions

    def test_includes_connection_errors(self) -> None:
        exceptions = _build_retry_exceptions(RetryPolicy(retry_on_connection_errors=True))
        assert OSError in exceptions
        assert TimeoutError in exceptions

    def test_excludes_connection_errors(self) -> None:
        exceptions = _build_retry_exceptions(RetryPolicy(retry_on_connection_errors=False))
        assert OSError not in exceptions


class TestBuildRetrying:
    def test_sync_retrying(self) -> None:
        policy = RetryPolicy(attempts=3)
        retrying = build_retrying(policy)
        assert retrying.stop.max_attempt_number == 3

    def test_async_retrying(self) -> None:
        policy = RetryPolicy(attempts=5)
        retrying = build_async_retrying(policy)
        assert retrying.stop.max_attempt_number == 5
