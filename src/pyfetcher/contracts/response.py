"""Response models for :mod:`pyfetcher`.

Purpose:
    Provide normalized response types independent of the underlying transport.

Design:
    - Response objects are transport-agnostic.
    - Streaming chunks are modeled separately from full responses.
    - Batch responses preserve ordering and capture success/failure per request.

Examples:
    ::

        >>> response = FetchResponse(
        ...     request_url="https://example.com/",
        ...     final_url="https://example.com/",
        ...     status_code=200,
        ...     headers={},
        ...     backend="httpx",
        ...     elapsed_ms=10.0,
        ... )
        >>> response.ok
        True
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, computed_field

from pyfetcher.contracts.request import BackendKind


class FetchResponse(BaseModel):
    """Normalized fetch response.

    A transport-agnostic response model that captures the HTTP status,
    headers, body content, and timing information for a completed request.
    The :attr:`ok` computed property provides a quick success check.

    Args:
        request_url: Original request URL as a string.
        final_url: Final URL after any redirects.
        status_code: HTTP status code.
        headers: Response headers as a flat dict.
        content_type: Response ``Content-Type`` header value, if present.
        text: Decoded text body when fully loaded.
        body: Raw bytes body when available.
        backend: Name of the backend that executed the request.
        elapsed_ms: Total elapsed time in milliseconds.

    Examples:
        ::

            >>> response = FetchResponse(
            ...     request_url="https://example.com/",
            ...     final_url="https://example.com/",
            ...     status_code=204,
            ...     headers={},
            ...     backend="httpx",
            ...     elapsed_ms=1.0,
            ... )
            >>> response.ok
            True
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    request_url: str
    final_url: str
    status_code: int
    headers: dict[str, str]
    content_type: str | None = None
    text: str | None = None
    body: bytes | None = None
    backend: BackendKind
    elapsed_ms: float

    @computed_field
    @property
    def ok(self) -> bool:
        """Return whether the response indicates success.

        Returns:
            ``True`` for 2xx and 3xx status codes.

        Examples:
            ::

                >>> FetchResponse(
                ...     request_url="https://example.com/",
                ...     final_url="https://example.com/",
                ...     status_code=200,
                ...     headers={},
                ...     backend="httpx",
                ...     elapsed_ms=1.0,
                ... ).ok
                True
        """
        return 200 <= self.status_code < 400


class StreamChunk(BaseModel):
    """Single streamed response chunk.

    Represents one chunk of a streaming HTTP response, carrying the raw
    bytes along with positional metadata for ordered reassembly.

    Args:
        request_url: Original request URL.
        final_url: Final URL after redirects.
        backend: Backend that produced this chunk.
        index: Zero-based chunk index within the stream.
        data: Raw bytes payload for this chunk.

    Examples:
        ::

            >>> StreamChunk(
            ...     request_url="https://example.com/",
            ...     final_url="https://example.com/",
            ...     backend="aiohttp",
            ...     index=0,
            ...     data=b"abc",
            ... ).index
            0
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    request_url: str
    final_url: str
    backend: BackendKind
    index: int
    data: bytes


class BatchItemResponse(BaseModel):
    """Result of a single batch item.

    Captures either a successful :class:`FetchResponse` or an error message
    for one request within a batch execution.

    Args:
        request_url: Original request URL.
        ok: Whether the item succeeded.
        response: The fetch response on success.
        error: Error message string on failure.

    Examples:
        ::

            >>> item = BatchItemResponse(
            ...     request_url="https://example.com/",
            ...     ok=False,
            ...     error="boom",
            ... )
            >>> item.ok
            False
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    request_url: str
    ok: bool
    response: FetchResponse | None = None
    error: str | None = None


class BatchFetchResponse(BaseModel):
    """Response container for batch fetch execution.

    Wraps the results of a :class:`~pyfetcher.contracts.request.BatchFetchRequest`,
    preserving input order so callers can correlate responses to their
    original requests by index.

    Args:
        items: Batch item responses in input order.

    Examples:
        ::

            >>> BatchFetchResponse(items=[]).items
            []
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    items: list[BatchItemResponse]
