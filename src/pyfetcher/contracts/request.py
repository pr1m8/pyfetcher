"""Request models for :mod:`pyfetcher`.

Purpose:
    Provide transport-agnostic request contracts that can be consumed by fetch
    services and backend implementations.

Design:
    - Requests are immutable and serializable.
    - URL validation is delegated to :class:`~pyfetcher.contracts.url.URL`.
    - Policies are embedded so one request object is self-describing.

Examples:
    ::

        >>> request = FetchRequest(url="https://example.com")
        >>> request.method
        'GET'
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from pyfetcher.contracts.policy import (
    PoolPolicy,
    RetryPolicy,
    StreamPolicy,
    TimeoutPolicy,
)
from pyfetcher.contracts.url import URL

type BackendKind = Literal["httpx", "aiohttp", "curl_cffi", "cloudscraper"]
type RequestMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]


class FetchRequest(BaseModel):
    """Transport-agnostic fetch request.

    Encapsulates everything needed to make an HTTP request: the target URL,
    method, headers, body, and all policy objects that control timeout, retry,
    pooling, and streaming behavior. The request is frozen and backend-agnostic
    so it can be serialized, queued, or handed to any transport.

    Args:
        url: Target URL (string or :class:`~pyfetcher.contracts.url.URL`).
        method: HTTP method (automatically uppercased).
        params: Query parameters to append to the URL.
        headers: Per-request headers (merged with provider headers).
        data: Optional raw request body (bytes or string).
        json_data: Optional JSON request body (dict or list).
        backend: Preferred HTTP backend.
        timeout: Timeout policy controlling per-phase timeouts.
        retry: Retry policy controlling backoff and retryable status codes.
        pool: Pool policy controlling connection limits and concurrency.
        stream: Stream policy controlling chunk size and byte limits.
        allow_redirects: Whether HTTP redirects should be followed.
        verify_ssl: Whether TLS certificate verification is enabled.
        http2: Whether HTTP/2 is preferred where the backend supports it.

    Examples:
        ::

            >>> FetchRequest(url="https://example.com").backend
            'httpx'
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    url: URL
    method: RequestMethod = "GET"
    params: dict[str, str | int | float | bool] = Field(default_factory=dict)
    headers: dict[str, str] = Field(default_factory=dict)
    data: bytes | str | None = None
    json_data: dict[str, Any] | list[Any] | None = None
    backend: BackendKind = "httpx"
    timeout: TimeoutPolicy = Field(default_factory=TimeoutPolicy)
    retry: RetryPolicy = Field(default_factory=RetryPolicy)
    pool: PoolPolicy = Field(default_factory=PoolPolicy)
    stream: StreamPolicy = Field(default_factory=StreamPolicy)
    allow_redirects: bool = True
    verify_ssl: bool = True
    http2: bool = True

    @field_validator("method")
    @classmethod
    def _normalize_method(cls, value: RequestMethod) -> RequestMethod:
        """Normalize HTTP methods to uppercase.

        Args:
            value: Candidate HTTP method string.

        Returns:
            The uppercased HTTP method.

        Examples:
            ::

                >>> FetchRequest._normalize_method("GET")
                'GET'
        """
        return value.upper()  # type: ignore[return-value]


class BatchFetchRequest(BaseModel):
    """Batch request wrapper for multiple fetch operations.

    Groups multiple :class:`FetchRequest` objects for concurrent execution
    with an optional concurrency override that caps the number of in-flight
    requests.

    Args:
        requests: Request objects to execute concurrently.
        concurrency: Optional concurrency override (defaults to pool policy).

    Examples:
        ::

            >>> req = FetchRequest(url="https://example.com")
            >>> batch = BatchFetchRequest(requests=[req])
            >>> len(batch.requests)
            1
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    requests: list[FetchRequest]
    concurrency: int | None = None
