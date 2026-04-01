"""Aiohttp transport implementation for :mod:`pyfetcher`.

Purpose:
    Provide an async-first transport backed by :mod:`aiohttp`, suitable for
    pooled crawling, bounded concurrency, and chunked streaming.

Design:
    - A long-lived :class:`aiohttp.ClientSession` owns connector pooling.
    - Connector settings come from the shared pool policy embedded in each
      request.
    - Full fetch and streaming interfaces are both supported.

Examples:
    ::

        >>> transport = AiohttpTransport()
        >>> hasattr(transport, "afetch")
        True
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from time import perf_counter

import aiohttp

from pyfetcher.contracts.request import FetchRequest
from pyfetcher.contracts.response import FetchResponse, StreamChunk


class AiohttpTransport:
    """Async ``aiohttp`` transport with pooled session reuse.

    Manages a long-lived :class:`aiohttp.ClientSession` that is lazily
    created from the first request's embedded policies. The session's
    TCP connector provides connection pooling and keepalive management.

    Args:
        session: Optional externally managed session (caller owns lifecycle).

    Examples:
        ::

            >>> transport = AiohttpTransport()
            >>> hasattr(transport, "astream")
            True
    """

    def __init__(self, *, session: aiohttp.ClientSession | None = None) -> None:
        self._session = session
        self._owns_session = session is None

    def _build_timeout(self, request: FetchRequest) -> aiohttp.ClientTimeout:
        """Build an aiohttp timeout from the request's timeout policy.

        Args:
            request: Fetch request carrying the timeout policy.

        Returns:
            A configured :class:`aiohttp.ClientTimeout`.
        """
        return aiohttp.ClientTimeout(
            total=request.timeout.total_seconds,
            connect=request.timeout.connect_seconds,
            sock_read=request.timeout.read_seconds,
            sock_connect=request.timeout.connect_seconds,
        )

    def _build_connector(self, request: FetchRequest) -> aiohttp.TCPConnector:
        """Build an aiohttp TCP connector from the request's pool policy.

        Args:
            request: Fetch request carrying the pool policy.

        Returns:
            A configured :class:`aiohttp.TCPConnector`.
        """
        return aiohttp.TCPConnector(
            limit=request.pool.max_connections,
            limit_per_host=request.pool.max_connections_per_host,
            ttl_dns_cache=300,
            ssl=request.verify_ssl,
            enable_cleanup_closed=True,
            keepalive_timeout=request.pool.keepalive_expiry_seconds,
        )

    async def _get_session(self, request: FetchRequest) -> aiohttp.ClientSession:
        """Get or lazily create the aiohttp session.

        Args:
            request: Fetch request whose policies configure the session.

        Returns:
            A configured :class:`aiohttp.ClientSession`.
        """
        if self._session is None:
            self._session = aiohttp.ClientSession(
                connector=self._build_connector(request),
                timeout=self._build_timeout(request),
                raise_for_status=False,
            )
        return self._session

    async def afetch(self, request: FetchRequest) -> FetchResponse:
        """Fetch a request asynchronously.

        Args:
            request: The fetch request to execute.

        Returns:
            A normalized :class:`~pyfetcher.contracts.response.FetchResponse`.

        Raises:
            aiohttp.ClientResponseError: If the response status indicates an error.
        """
        session = await self._get_session(request)
        start = perf_counter()
        async with session.request(
            request.method,
            request.url.unicode_string(),
            params=request.params,
            headers=request.headers,
            data=request.data,
            json=request.json_data,
            allow_redirects=request.allow_redirects,
            ssl=request.verify_ssl,
        ) as response:
            body = await response.read()
            elapsed_ms = (perf_counter() - start) * 1000.0
            response.raise_for_status()
            return FetchResponse(
                request_url=request.url.unicode_string(),
                final_url=str(response.url),
                status_code=response.status,
                headers=dict(response.headers),
                content_type=response.headers.get("content-type"),
                text=body.decode(response.charset or "utf-8", errors="replace"),
                body=body,
                backend="aiohttp",
                elapsed_ms=elapsed_ms,
            )

    async def astream(self, request: FetchRequest) -> AsyncIterator[StreamChunk]:
        """Stream a request asynchronously.

        Yields chunks of the response body as :class:`StreamChunk` objects.

        Args:
            request: The fetch request to stream.

        Yields:
            :class:`~pyfetcher.contracts.response.StreamChunk` objects.

        Raises:
            aiohttp.ClientResponseError: If the response status indicates an error.
        """
        session = await self._get_session(request)
        async with session.request(
            request.method,
            request.url.unicode_string(),
            params=request.params,
            headers=request.headers,
            data=request.data,
            json=request.json_data,
            allow_redirects=request.allow_redirects,
            ssl=request.verify_ssl,
        ) as response:
            response.raise_for_status()
            index = 0
            async for chunk in response.content.iter_chunked(request.stream.chunk_size):
                yield StreamChunk(
                    request_url=request.url.unicode_string(),
                    final_url=str(response.url),
                    backend="aiohttp",
                    index=index,
                    data=chunk,
                )
                index += 1

    async def aclose(self) -> None:
        """Close the owned session if present.

        Only closes sessions that were created internally (not externally
        provided via the constructor).
        """
        if self._owns_session and self._session is not None:
            await self._session.close()
            self._session = None
