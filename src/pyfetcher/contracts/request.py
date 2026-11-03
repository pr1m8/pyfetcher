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

from collections.abc import AsyncIterable, Callable, Iterable, Mapping
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, SkipValidation, field_validator, model_validator

from pyfetcher.contracts.policy import (
    PoolPolicy,
    RetryPolicy,
    StreamPolicy,
    TimeoutPolicy,
)
from pyfetcher.contracts.url import URL

type BackendKind = str
type RequestMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]
type RequestContent = bytes | str | Iterable[bytes] | AsyncIterable[bytes]
type RequestContentFactory = Callable[[], RequestContent]


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
        data: Optional buffered request body (bytes or string).
        content: Optional runtime request content. In addition to bytes and
            strings, this accepts synchronous and asynchronous byte iterables
            for streaming uploads. Runtime streams are intentionally excluded
            from model serialization.
        content_factory: Optional callable that returns fresh request content
            for each attempt. Use this for retryable streaming uploads.
        json_data: Optional JSON request body (dict or list).
        backend: Preferred HTTP backend. Built-in names are ``httpx``,
            ``aiohttp``, ``curl_cffi``, and ``cloudscraper``; applications may
            register additional transport adapter names on ``FetchService``.
        timeout: Timeout policy controlling per-phase timeouts.
        retry: Retry policy controlling backoff and retryable status codes.
        pool: Pool policy controlling connection limits and concurrency.
        stream: Stream policy controlling chunk size and byte limits.
        allow_redirects: Whether HTTP redirects should be followed.
        verify_ssl: Whether TLS certificate verification is enabled.
        http2: Whether HTTP/2 is preferred where the backend supports it.
        proxy: Optional HTTP(S) proxy URL. Pooling transports isolate clients
            with different proxy settings.

    Examples:
        ::

            >>> FetchRequest(url="https://example.com").backend
            'httpx'
    """

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    url: URL
    method: RequestMethod = "GET"
    params: dict[str, str | int | float | bool] = Field(default_factory=dict)
    headers: dict[str, str] = Field(default_factory=dict)
    data: bytes | str | None = None
    content: Annotated[RequestContent, SkipValidation] | None = Field(default=None, exclude=True)
    content_factory: Annotated[RequestContentFactory, SkipValidation] | None = Field(
        default=None,
        exclude=True,
    )
    json_data: dict[str, Any] | list[Any] | None = None
    backend: BackendKind = "httpx"
    timeout: TimeoutPolicy = Field(default_factory=TimeoutPolicy)
    retry: RetryPolicy = Field(default_factory=RetryPolicy)
    pool: PoolPolicy = Field(default_factory=PoolPolicy)
    stream: StreamPolicy = Field(default_factory=StreamPolicy)
    allow_redirects: bool = True
    verify_ssl: bool = True
    http2: bool = True
    proxy: str | None = None

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

    @field_validator("content", mode="before")
    @classmethod
    def _validate_content(cls, value: object) -> object:
        """Validate a request content source without consuming it.

        Element types are checked lazily by the transport adapters so a
        one-shot generator remains untouched until the request is sent.
        """
        if value is None or isinstance(value, (bytes, str)):
            return value
        if isinstance(value, Mapping):
            raise ValueError("content mappings are not supported; use json_data instead")
        if isinstance(value, (Iterable, AsyncIterable)):
            return value
        raise ValueError("content must be bytes, str, or a sync/async iterable of bytes")

    @field_validator("content_factory", mode="before")
    @classmethod
    def _validate_content_factory(cls, value: object) -> object:
        if value is not None and not callable(value):
            raise ValueError("content_factory must be callable")
        return value

    @field_validator("proxy")
    @classmethod
    def _validate_proxy(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parts = urlsplit(value)
        if parts.scheme not in {"http", "https"} or not parts.netloc:
            raise ValueError("proxy must be an absolute HTTP(S) URL")
        return value

    @model_validator(mode="after")
    def _validate_body_sources(self) -> FetchRequest:
        """Require callers to choose exactly one request body source."""
        supplied = sum(
            value is not None
            for value in (self.data, self.content, self.content_factory, self.json_data)
        )
        if supplied > 1:
            raise ValueError("data, content, content_factory, and json_data are mutually exclusive")
        return self


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
