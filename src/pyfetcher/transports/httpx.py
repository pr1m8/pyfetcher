"""HTTPX transport implementation for :mod:`pyfetcher`.

Purpose:
    Provide pooled synchronous and asynchronous fetching using ``httpx`` as
    the underlying HTTP client library.

Design:
    - One transport instance owns long-lived clients and pooling state.
    - Request conversion stays thin because the main contracts are
      transport-agnostic.
    - Streaming is supported via ``httpx.AsyncClient.stream``.
    - Clients are lazily initialized on first use with settings derived
      from the request's embedded policies.

Examples:
    ::

        >>> transport = HttpxTransport()
        >>> hasattr(transport, "fetch")
        True
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from time import perf_counter

import httpx

from pyfetcher.contracts.policy import PoolPolicy, TimeoutPolicy
from pyfetcher.contracts.request import FetchRequest
from pyfetcher.contracts.response import FetchResponse, StreamChunk


def _build_timeout(timeout: TimeoutPolicy) -> httpx.Timeout:
    """Convert a timeout policy into an ``httpx.Timeout`` object.

    Args:
        timeout: The timeout policy to convert.

    Returns:
        A configured ``httpx.Timeout`` instance.

    Examples:
        ::

            >>> isinstance(_build_timeout(TimeoutPolicy()), httpx.Timeout)
            True
    """
    return httpx.Timeout(
        timeout=timeout.total_seconds,
        connect=timeout.connect_seconds,
        read=timeout.read_seconds,
        write=timeout.write_seconds,
        pool=timeout.pool_seconds,
    )


def _build_limits(pool: PoolPolicy) -> httpx.Limits:
    """Convert a pool policy into an ``httpx.Limits`` object.

    Args:
        pool: The pool policy to convert.

    Returns:
        A configured ``httpx.Limits`` instance.

    Examples:
        ::

            >>> isinstance(_build_limits(PoolPolicy()), httpx.Limits)
            True
    """
    return httpx.Limits(
        max_connections=pool.max_connections,
        max_keepalive_connections=pool.max_keepalive_connections,
        keepalive_expiry=pool.keepalive_expiry_seconds,
    )


class HttpxTransport:
    """Combined sync/async HTTPX transport with pooled client management.

    Manages long-lived ``httpx.Client`` and ``httpx.AsyncClient`` instances
    that are lazily initialized from the first request's embedded policies.
    Supports synchronous fetch, asynchronous fetch, and async streaming.

    Args:
        sync_client: Optional externally managed sync client (caller owns lifecycle).
        async_client: Optional externally managed async client (caller owns lifecycle).

    Examples:
        ::

            >>> transport = HttpxTransport()
            >>> hasattr(transport, "afetch")
            True
    """

    def __init__(
        self,
        *,
        sync_client: httpx.Client | None = None,
        async_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._sync_client = sync_client
        self._async_client = async_client
        self._owns_sync_client = sync_client is None
        self._owns_async_client = async_client is None

    def _get_sync_client(self, request: FetchRequest) -> httpx.Client:
        """Get or lazily create the synchronous HTTPX client.

        Args:
            request: Fetch request whose policies configure the client.

        Returns:
            A configured ``httpx.Client`` instance.
        """
        if self._sync_client is None:
            self._sync_client = httpx.Client(
                timeout=_build_timeout(request.timeout),
                limits=_build_limits(request.pool),
                follow_redirects=request.allow_redirects,
                verify=request.verify_ssl,
                http2=request.http2,
            )
        return self._sync_client

    def _get_async_client(self, request: FetchRequest) -> httpx.AsyncClient:
        """Get or lazily create the asynchronous HTTPX client.

        Args:
            request: Fetch request whose policies configure the client.

        Returns:
            A configured ``httpx.AsyncClient`` instance.
        """
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(
                timeout=_build_timeout(request.timeout),
                limits=_build_limits(request.pool),
                follow_redirects=request.allow_redirects,
                verify=request.verify_ssl,
                http2=request.http2,
            )
        return self._async_client

    def fetch(self, request: FetchRequest) -> FetchResponse:
        """Fetch a request synchronously.

        Args:
            request: The fetch request to execute.

        Returns:
            A normalized :class:`~pyfetcher.contracts.response.FetchResponse`.

        Raises:
            httpx.HTTPStatusError: If the response status indicates an error.
        """
        client = self._get_sync_client(request)
        start = perf_counter()
        response = client.request(
            request.method,
            request.url.unicode_string(),
            params=request.params,
            headers=request.headers,
            content=request.data,
            json=request.json_data,
        )
        elapsed_ms = (perf_counter() - start) * 1000.0
        response.raise_for_status()
        return FetchResponse(
            request_url=request.url.unicode_string(),
            final_url=str(response.url),
            status_code=response.status_code,
            headers=dict(response.headers),
            content_type=response.headers.get("content-type"),
            text=response.text,
            body=response.content,
            backend="httpx",
            elapsed_ms=elapsed_ms,
        )

    async def afetch(self, request: FetchRequest) -> FetchResponse:
        """Fetch a request asynchronously.

        Args:
            request: The fetch request to execute.

        Returns:
            A normalized :class:`~pyfetcher.contracts.response.FetchResponse`.

        Raises:
            httpx.HTTPStatusError: If the response status indicates an error.
        """
        client = self._get_async_client(request)
        start = perf_counter()
        response = await client.request(
            request.method,
            request.url.unicode_string(),
            params=request.params,
            headers=request.headers,
            content=request.data,
            json=request.json_data,
        )
        elapsed_ms = (perf_counter() - start) * 1000.0
        response.raise_for_status()
        return FetchResponse(
            request_url=request.url.unicode_string(),
            final_url=str(response.url),
            status_code=response.status_code,
            headers=dict(response.headers),
            content_type=response.headers.get("content-type"),
            text=response.text,
            body=response.content,
            backend="httpx",
            elapsed_ms=elapsed_ms,
        )

    async def astream(self, request: FetchRequest) -> AsyncIterator[StreamChunk]:
        """Stream a request asynchronously.

        Yields chunks of the response body as :class:`StreamChunk` objects,
        each carrying the raw bytes and a zero-based index.

        Args:
            request: The fetch request to stream.

        Yields:
            :class:`~pyfetcher.contracts.response.StreamChunk` objects.

        Raises:
            httpx.HTTPStatusError: If the response status indicates an error.
        """
        client = self._get_async_client(request)
        async with client.stream(
            request.method,
            request.url.unicode_string(),
            params=request.params,
            headers=request.headers,
            content=request.data,
            json=request.json_data,
        ) as response:
            response.raise_for_status()
            index = 0
            async for chunk in response.aiter_bytes(chunk_size=request.stream.chunk_size):
                yield StreamChunk(
                    request_url=request.url.unicode_string(),
                    final_url=str(response.url),
                    backend="httpx",
                    index=index,
                    data=chunk,
                )
                index += 1

    def close(self) -> None:
        """Close the owned sync client if present.

        Only closes clients that were created internally (not externally
        provided via the constructor).
        """
        if self._owns_sync_client and self._sync_client is not None:
            self._sync_client.close()
            self._sync_client = None

    async def aclose(self) -> None:
        """Close the owned async client if present.

        Only closes clients that were created internally (not externally
        provided via the constructor).
        """
        if self._owns_async_client and self._async_client is not None:
            await self._async_client.aclose()
            self._async_client = None
