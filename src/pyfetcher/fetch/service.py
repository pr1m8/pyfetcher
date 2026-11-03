"""Fetch service orchestration for :mod:`pyfetcher`.

Purpose:
    Compose header providers, retry policies, rate limiters, and transports
    into a single reusable service object that handles the full lifecycle
    of HTTP requests.

Design:
    - Retry logic sits above transports via :mod:`tenacity`.
    - Rate limiting is applied before each request attempt.
    - A function-first API is layered on top of this service.
    - Requests are normalized through central contracts.
    - Backends can be swapped per request.

Examples:
    ::

        >>> service = FetchService()
        >>> hasattr(service, "afetch")
        True
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Iterable, Iterator, Mapping

from pyfetcher.contracts.request import BatchFetchRequest, FetchRequest
from pyfetcher.contracts.response import (
    BatchFetchResponse,
    BatchItemResponse,
    FetchResponse,
    StreamChunk,
)
from pyfetcher.headers.base import HeaderProvider
from pyfetcher.headers.browser import BrowserHeaderProvider
from pyfetcher.middleware import AsyncMiddleware, SyncMiddleware, compose_async, compose_sync
from pyfetcher.ratelimit.limiter import DomainRateLimiter
from pyfetcher.retry.tenacity import (
    RetryableStatusCodeError,
    build_async_retrying,
    build_retrying,
)
from pyfetcher.transports.aiohttp import AiohttpTransport
from pyfetcher.transports.base import AsyncTransport, SyncTransport
from pyfetcher.transports.httpx import HttpxTransport

# Optional transport backends (lazy imports guard missing dependencies)
try:
    from pyfetcher.transports.curl_cffi import (  # noqa: F401  # nosec B110
        CurlCffiTransport,
    )
except Exception:  # pragma: no cover  # noqa: S110
    CurlCffiTransport = None  # type: ignore[assignment,misc]  # nosec B110

try:
    from pyfetcher.transports.cloudscraper import (  # noqa: F401  # nosec B110
        CloudscraperTransport,
    )
except Exception:  # pragma: no cover  # noqa: S110
    CloudscraperTransport = None  # type: ignore[assignment,misc]  # nosec B110

logger = logging.getLogger("pyfetcher.fetch")


class FetchService:
    """Reusable fetch orchestration service.

    Composes header generation, rate limiting, retry logic, and transport
    execution into a single service. Supports both synchronous and
    asynchronous operation, batch fetching with bounded concurrency, and
    streaming.

    Args:
        header_provider: Optional header provider for generating request
            headers. Defaults to :class:`~pyfetcher.headers.browser.BrowserHeaderProvider`.
        httpx_transport: Optional HTTPX transport instance. Created lazily
            if not provided.
        aiohttp_transport: Optional aiohttp transport instance. Created
            lazily if not provided.
        sync_transports: Additional named synchronous transport adapters.
        async_transports: Additional named asynchronous transport adapters.
        rate_limiter: Optional per-domain rate limiter. Pass ``None``
            to disable rate limiting (the default).

    Examples:
        ::

            >>> service = FetchService()
            >>> hasattr(service, "fetch")
            True
    """

    def __init__(
        self,
        *,
        header_provider: HeaderProvider | None = None,
        httpx_transport: HttpxTransport | None = None,
        aiohttp_transport: AiohttpTransport | None = None,
        sync_transports: Mapping[str, SyncTransport] | None = None,
        async_transports: Mapping[str, AsyncTransport] | None = None,
        sync_middleware: Iterable[SyncMiddleware[FetchRequest, FetchResponse]] = (),
        async_middleware: Iterable[AsyncMiddleware[FetchRequest, FetchResponse]] = (),
        rate_limiter: DomainRateLimiter | None = None,
    ) -> None:
        self.header_provider = header_provider or BrowserHeaderProvider()
        self.httpx_transport = httpx_transport or HttpxTransport()
        self.aiohttp_transport = aiohttp_transport or AiohttpTransport()
        self._sync_transports = dict(sync_transports or {})
        self._async_transports = dict(async_transports or {})
        self.rate_limiter = rate_limiter
        self._curl_cffi_transport: CurlCffiTransport | None = None  # type: ignore[type-arg]
        self._cloudscraper_transport: CloudscraperTransport | None = None  # type: ignore[type-arg]
        self._fetch_handler = compose_sync(self._fetch_impl, sync_middleware)
        self._afetch_handler = compose_async(self._afetch_impl, async_middleware)

    def _prepare_request(self, request: FetchRequest) -> FetchRequest:
        """Merge provider headers into the request.

        Args:
            request: Original fetch request.

        Returns:
            A copied request with merged headers (provider headers as base,
            per-request headers as overrides).
        """
        provider_headers = self.header_provider.build(request=request)
        return request.model_copy(update={"headers": {**provider_headers, **request.headers}})

    def _get_sync_transport(self, request: FetchRequest) -> SyncTransport:
        """Resolve the synchronous transport for the request's backend.

        Args:
            request: Fetch request specifying the backend.

        Returns:
            A synchronous transport.

        Raises:
            ValueError: If the backend does not support synchronous fetch.
        """
        registered = self._sync_transports.get(request.backend)
        if registered is not None:
            return registered
        if request.backend == "httpx":
            return self.httpx_transport
        if request.backend == "curl_cffi":
            if CurlCffiTransport is None:
                raise ValueError("curl_cffi backend requires the 'curl_cffi' package")
            if self._curl_cffi_transport is None:
                self._curl_cffi_transport = CurlCffiTransport()
            return self._curl_cffi_transport  # type: ignore[return-value]
        if request.backend == "cloudscraper":
            if CloudscraperTransport is None:
                raise ValueError("cloudscraper backend requires the 'cloudscraper' package")
            if self._cloudscraper_transport is None:
                self._cloudscraper_transport = CloudscraperTransport()
            return self._cloudscraper_transport  # type: ignore[return-value]
        raise ValueError(f"Backend does not support synchronous fetch: {request.backend!r}")

    def _get_async_transport(self, request: FetchRequest) -> AsyncTransport:
        """Resolve the asynchronous transport for the request's backend.

        Args:
            request: Fetch request specifying the backend.

        Returns:
            An asynchronous transport.

        Raises:
            ValueError: If the backend is unsupported for async.
        """
        registered = self._async_transports.get(request.backend)
        if registered is not None:
            return registered
        if request.backend == "httpx":
            return self.httpx_transport
        if request.backend == "aiohttp":
            return self.aiohttp_transport
        if request.backend == "curl_cffi":
            if CurlCffiTransport is None:
                raise ValueError("curl_cffi backend requires the 'curl_cffi' package")
            if self._curl_cffi_transport is None:
                self._curl_cffi_transport = CurlCffiTransport()
            return self._curl_cffi_transport  # type: ignore[return-value]
        raise ValueError(f"Unsupported async backend: {request.backend!r}")

    def register_sync_transport(self, name: str, transport: SyncTransport) -> None:
        """Register or replace a named synchronous transport adapter."""
        if not name:
            raise ValueError("transport name cannot be empty")
        self._sync_transports[name] = transport

    def register_async_transport(self, name: str, transport: AsyncTransport) -> None:
        """Register or replace a named asynchronous transport adapter."""
        if not name:
            raise ValueError("transport name cannot be empty")
        self._async_transports[name] = transport

    def _maybe_raise_retryable_status(self, response: FetchResponse, request: FetchRequest) -> None:
        """Raise a retryable status error when the response code is configured as retryable.

        Args:
            response: The fetch response to check.
            request: The original request (carries retry policy config).

        Raises:
            RetryableStatusCodeError: If the status code is in the retry set.
        """
        if response.status_code in request.retry.retry_status_codes:
            raise RetryableStatusCodeError(response.status_code)

    def fetch(self, request: FetchRequest) -> FetchResponse:
        """Fetch synchronously with retries and optional rate limiting.

        Prepares the request with provider headers, applies rate limiting
        if configured, then executes the request through the appropriate
        transport with Tenacity retry logic.

        Args:
            request: The fetch request to execute.

        Returns:
            A normalized :class:`~pyfetcher.contracts.response.FetchResponse`.

        Raises:
            Exception: The final transport or retry failure after all
                attempts are exhausted.

        Examples:
            ::

                >>> service = FetchService()
                >>> hasattr(service, "fetch")
                True
        """
        return self._fetch_handler(request)

    def _fetch_impl(self, request: FetchRequest) -> FetchResponse:
        """Execute the core synchronous fetch beneath middleware."""
        prepared = self._prepare_request(request)
        transport = self._get_sync_transport(prepared)
        retrying = build_retrying(prepared.retry)

        for attempt in retrying:
            with attempt:
                if self.rate_limiter:
                    self.rate_limiter.acquire(prepared.url.unicode_string())
                response = transport.fetch(prepared)
                self._maybe_raise_retryable_status(response, prepared)
                return response

        raise RuntimeError("Unreachable retry state.")

    async def afetch(self, request: FetchRequest) -> FetchResponse:
        """Fetch asynchronously with retries and optional rate limiting.

        Prepares the request with provider headers, applies async rate
        limiting if configured, then executes the request through the
        appropriate transport with async Tenacity retry logic.

        Args:
            request: The fetch request to execute.

        Returns:
            A normalized :class:`~pyfetcher.contracts.response.FetchResponse`.

        Raises:
            Exception: The final transport or retry failure after all
                attempts are exhausted.

        Examples:
            ::

                >>> service = FetchService()
                >>> hasattr(service, "afetch")
                True
        """
        return await self._afetch_handler(request)

    async def _afetch_impl(self, request: FetchRequest) -> FetchResponse:
        """Execute the core asynchronous fetch beneath middleware."""
        prepared = self._prepare_request(request)
        transport = self._get_async_transport(prepared)
        retrying = build_async_retrying(prepared.retry)

        async for attempt in retrying:
            with attempt:
                if self.rate_limiter:
                    await self.rate_limiter.aacquire(prepared.url.unicode_string())
                response = await transport.afetch(prepared)
                self._maybe_raise_retryable_status(response, prepared)
                return response

        raise RuntimeError("Unreachable retry state.")

    async def afetch_many(self, batch: BatchFetchRequest) -> BatchFetchResponse:
        """Fetch many requests asynchronously with bounded concurrency.

        Executes all requests in the batch concurrently, limited by the
        batch concurrency setting or the first request's pool concurrency.
        Individual failures are captured per-item without aborting the batch.

        Args:
            batch: The batch fetch request containing all requests.

        Returns:
            A :class:`~pyfetcher.contracts.response.BatchFetchResponse`
            preserving input order.

        Examples:
            ::

                >>> service = FetchService()
                >>> hasattr(service, "afetch_many")
                True
        """
        requests = list(batch.requests)
        concurrency = batch.concurrency or (requests[0].pool.concurrency if requests else 1)
        semaphore = asyncio.Semaphore(concurrency)

        async def _run(request: FetchRequest) -> BatchItemResponse:
            async with semaphore:
                try:
                    response = await self.afetch(request)
                    return BatchItemResponse(
                        request_url=request.url.unicode_string(),
                        ok=True,
                        response=response,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "batch_request_failed",
                        extra={
                            "url": request.url.unicode_string(),
                            "backend": request.backend,
                            "error": str(exc),
                        },
                    )
                    return BatchItemResponse(
                        request_url=request.url.unicode_string(),
                        ok=False,
                        error=str(exc),
                    )

        items = await asyncio.gather(*(_run(request) for request in requests))
        return BatchFetchResponse(items=items)

    async def astream(self, request: FetchRequest) -> AsyncIterator[StreamChunk]:
        """Stream a request asynchronously.

        Prepares the request and delegates to the transport's streaming
        interface. Rate limiting is applied once before streaming begins.

        Args:
            request: The fetch request to stream.

        Yields:
            :class:`~pyfetcher.contracts.response.StreamChunk` objects.

        Raises:
            Exception: Streaming or backend failures.

        Examples:
            ::

                >>> service = FetchService()
                >>> hasattr(service, "astream")
                True
        """
        prepared = self._prepare_request(request)
        if self.rate_limiter:
            await self.rate_limiter.aacquire(prepared.url.unicode_string())
        transport = self._get_async_transport(prepared)
        total_bytes = 0
        async for chunk in transport.astream(prepared):
            if prepared.stream.max_bytes is not None:
                remaining = prepared.stream.max_bytes - total_bytes
                if remaining <= 0:
                    break
                if len(chunk.data) > remaining:
                    yield chunk.model_copy(update={"data": chunk.data[:remaining]})
                    break
            total_bytes += len(chunk.data)
            yield chunk

    def stream(self, request: FetchRequest) -> Iterator[StreamChunk]:
        """Stream a request synchronously through a capable backend.

        The default HTTPX backend supports this interface. ``max_bytes`` from
        the request's stream policy is enforced without buffering the body.
        """
        prepared = self._prepare_request(request)
        if self.rate_limiter:
            self.rate_limiter.acquire(prepared.url.unicode_string())
        transport = self._get_sync_transport(prepared)
        stream = getattr(transport, "stream", None)
        if not callable(stream):
            raise ValueError(f"Backend does not support synchronous streaming: {request.backend!r}")

        total_bytes = 0
        for chunk in stream(prepared):
            if prepared.stream.max_bytes is not None:
                remaining = prepared.stream.max_bytes - total_bytes
                if remaining <= 0:
                    break
                if len(chunk.data) > remaining:
                    yield chunk.model_copy(update={"data": chunk.data[:remaining]})
                    break
            total_bytes += len(chunk.data)
            yield chunk

    def __enter__(self) -> FetchService:
        """Return this service for synchronous context-manager use."""
        return self

    def __exit__(self, *exc_info: object) -> None:
        """Close synchronous resources on context-manager exit."""
        self.close()

    async def __aenter__(self) -> FetchService:
        """Return this service for application-lifespan use."""
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        """Close asynchronous resources on context-manager exit."""
        await self.aclose()

    def close(self) -> None:
        """Close owned synchronous resources.

        Closes built-in and registered synchronous transports. A caller that
        shares a transport between services must coordinate that lifecycle.
        """
        transports = (
            self.httpx_transport,
            self._curl_cffi_transport,
            self._cloudscraper_transport,
            *self._sync_transports.values(),
        )
        seen: set[int] = set()
        for transport in transports:
            if id(transport) in seen:
                continue
            seen.add(id(transport))
            close = getattr(transport, "close", None)
            if callable(close):
                close()

    async def aclose(self) -> None:
        """Close owned asynchronous resources.

        Closes built-in and registered asynchronous transports. A caller that
        shares a transport between services must coordinate that lifecycle.
        """
        transports = (
            self.httpx_transport,
            self.aiohttp_transport,
            self._curl_cffi_transport,
            *self._async_transports.values(),
        )
        seen: set[int] = set()
        for transport in transports:
            if id(transport) in seen:
                continue
            seen.add(id(transport))
            aclose = getattr(transport, "aclose", None)
            if callable(aclose):
                await aclose()
