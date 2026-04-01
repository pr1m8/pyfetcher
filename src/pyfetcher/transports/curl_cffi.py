"""curl_cffi transport implementation for :mod:`pyfetcher`.

Purpose:
    Provide a transport backed by ``curl_cffi`` that impersonates real browser
    TLS fingerprints (JA3/JA4), making requests appear to originate from
    genuine browsers at the network layer. This is the most effective approach
    for bypassing TLS-based bot detection (e.g. Cloudflare, Akamai).

Design:
    - Uses ``curl_cffi.requests.Session`` for synchronous requests.
    - Uses ``curl_cffi.requests.AsyncSession`` for asynchronous requests.
    - The ``impersonate`` parameter selects which browser's TLS fingerprint
      to match (e.g. ``'chrome120'``, ``'firefox'``, ``'safari'``).
    - Sessions are lazily initialized on first use.
    - ``curl_cffi`` is imported lazily so it remains an optional dependency.

Examples:
    ::

        >>> transport = CurlCffiTransport(impersonate="chrome120")
        >>> hasattr(transport, "fetch")
        True
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from time import perf_counter

from pyfetcher.contracts.request import FetchRequest
from pyfetcher.contracts.response import FetchResponse, StreamChunk

#: Supported curl_cffi browser impersonation targets.
CURL_CFFI_TARGETS: list[str] = [
    "chrome99",
    "chrome100",
    "chrome101",
    "chrome104",
    "chrome107",
    "chrome110",
    "chrome116",
    "chrome119",
    "chrome120",
    "chrome123",
    "chrome124",
    "chrome131",
    "chrome133",
    "edge99",
    "edge101",
    "firefox95",
    "firefox100",
    "firefox102",
    "firefox109",
    "firefox117",
    "safari15_3",
    "safari15_5",
    "safari17_0",
    "safari17_2_1",
    "safari18_0",
]


class CurlCffiTransport:
    """Transport using curl_cffi for browser TLS fingerprint impersonation.

    Matches real browser JA3/JA4 TLS fingerprints at the network level,
    making requests indistinguishable from genuine browser traffic to
    TLS-based bot detection systems.

    Args:
        impersonate: Browser TLS fingerprint target (e.g. ``'chrome120'``,
            ``'firefox'``, ``'safari'``). See :data:`CURL_CFFI_TARGETS`
            for all options.
        sync_session: Optional externally managed sync session.
        async_session: Optional externally managed async session.

    Examples:
        ::

            >>> transport = CurlCffiTransport(impersonate="chrome120")
            >>> hasattr(transport, "afetch")
            True
    """

    def __init__(
        self,
        *,
        impersonate: str = "chrome120",
        sync_session: object | None = None,
        async_session: object | None = None,
    ) -> None:
        self.impersonate = impersonate
        self._sync_session = sync_session
        self._async_session = async_session
        self._owns_sync = sync_session is None
        self._owns_async = async_session is None

    def _get_sync_session(self) -> object:
        """Get or lazily create the synchronous curl_cffi session.

        Returns:
            A ``curl_cffi.requests.Session`` instance.

        Raises:
            ImportError: If ``curl_cffi`` is not installed.
        """
        if self._sync_session is None:
            from curl_cffi.requests import Session  # type: ignore[import-untyped]

            self._sync_session = Session(impersonate=self.impersonate)
        return self._sync_session

    def _get_async_session(self) -> object:
        """Get or lazily create the asynchronous curl_cffi session.

        Returns:
            A ``curl_cffi.requests.AsyncSession`` instance.

        Raises:
            ImportError: If ``curl_cffi`` is not installed.
        """
        if self._async_session is None:
            from curl_cffi.requests import AsyncSession  # type: ignore[import-untyped]

            self._async_session = AsyncSession(impersonate=self.impersonate)
        return self._async_session

    def fetch(self, request: FetchRequest) -> FetchResponse:
        """Fetch a request synchronously with browser TLS impersonation.

        Args:
            request: The fetch request to execute.

        Returns:
            A normalized :class:`~pyfetcher.contracts.response.FetchResponse`.

        Raises:
            ImportError: If ``curl_cffi`` is not installed.
        """
        session = self._get_sync_session()
        start = perf_counter()
        response = session.request(  # type: ignore[union-attr]
            request.method,
            request.url.unicode_string(),
            params=request.params or None,
            headers=request.headers or None,
            data=request.data,
            json=request.json_data,
            allow_redirects=request.allow_redirects,
            verify=request.verify_ssl,
            timeout=request.timeout.total_seconds,
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
            backend="curl_cffi",
            elapsed_ms=elapsed_ms,
        )

    async def afetch(self, request: FetchRequest) -> FetchResponse:
        """Fetch a request asynchronously with browser TLS impersonation.

        Args:
            request: The fetch request to execute.

        Returns:
            A normalized :class:`~pyfetcher.contracts.response.FetchResponse`.

        Raises:
            ImportError: If ``curl_cffi`` is not installed.
        """
        session = self._get_async_session()
        start = perf_counter()
        response = await session.request(  # type: ignore[union-attr]
            request.method,
            request.url.unicode_string(),
            params=request.params or None,
            headers=request.headers or None,
            data=request.data,
            json=request.json_data,
            allow_redirects=request.allow_redirects,
            verify=request.verify_ssl,
            timeout=request.timeout.total_seconds,
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
            backend="curl_cffi",
            elapsed_ms=elapsed_ms,
        )

    async def astream(self, request: FetchRequest) -> AsyncIterator[StreamChunk]:
        """Stream a request asynchronously with browser TLS impersonation.

        Args:
            request: The fetch request to stream.

        Yields:
            :class:`~pyfetcher.contracts.response.StreamChunk` objects.

        Raises:
            ImportError: If ``curl_cffi`` is not installed.
        """
        session = self._get_async_session()
        response = await session.request(  # type: ignore[union-attr]
            request.method,
            request.url.unicode_string(),
            params=request.params or None,
            headers=request.headers or None,
            data=request.data,
            json=request.json_data,
            allow_redirects=request.allow_redirects,
            verify=request.verify_ssl,
            timeout=request.timeout.total_seconds,
            stream=True,
        )
        response.raise_for_status()
        index = 0
        async for chunk in response.aiter_content():  # type: ignore[union-attr]
            yield StreamChunk(
                request_url=request.url.unicode_string(),
                final_url=str(response.url),
                backend="curl_cffi",
                index=index,
                data=chunk if isinstance(chunk, bytes) else chunk.encode(),
            )
            index += 1

    def close(self) -> None:
        """Close the owned sync session if present."""
        if self._owns_sync and self._sync_session is not None:
            close = getattr(self._sync_session, "close", None)
            if callable(close):
                close()
            self._sync_session = None

    async def aclose(self) -> None:
        """Close the owned async session if present."""
        if self._owns_async and self._async_session is not None:
            aclose = getattr(self._async_session, "close", None)
            if callable(aclose):
                await aclose()
            self._async_session = None
