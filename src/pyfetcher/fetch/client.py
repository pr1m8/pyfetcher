"""Application-lifecycle clients for :mod:`pyfetcher`.

Purpose:
    Provide ergonomic, reusable sync and async clients with explicit resource
    ownership, connection pooling, streaming helpers, and bounded async mapping.

Design:
    The clients build immutable :class:`~pyfetcher.contracts.request.FetchRequest`
    objects and delegate execution to :class:`~pyfetcher.fetch.service.FetchService`.
    They are suitable for dependency injection and application state because
    their context managers align pool cleanup with the host application's lifespan.
"""

from __future__ import annotations

import asyncio
import codecs
from collections.abc import AsyncIterable, AsyncIterator, Iterable, Iterator, Mapping
from typing import Any

from pyfetcher.contracts.policy import PoolPolicy, RetryPolicy, StreamPolicy, TimeoutPolicy
from pyfetcher.contracts.request import BackendKind, FetchRequest, RequestMethod
from pyfetcher.contracts.response import FetchResponse, StreamChunk
from pyfetcher.contracts.url import URL, URLInput
from pyfetcher.contracts.url_adapters import URLAdapterRegistry
from pyfetcher.fetch.service import FetchService
from pyfetcher.headers.base import HeaderProvider
from pyfetcher.ratelimit.limiter import DomainRateLimiter

type FetchInput = URLInput | FetchRequest

__all__ = ["AsyncFetchClient", "FetchClient"]


class _RequestBuilder:
    """Build requests from client defaults plus per-call overrides."""

    def __init__(
        self,
        *,
        base_url: URLInput | None,
        url_adapters: URLAdapterRegistry | None,
        headers: Mapping[str, str] | None,
        backend: BackendKind,
        timeout: TimeoutPolicy,
        retry: RetryPolicy,
        pool: PoolPolicy,
        stream: StreamPolicy,
        allow_redirects: bool,
        verify_ssl: bool,
        http2: bool,
        proxy: str | None,
    ) -> None:
        if base_url is None:
            self.base_url = None
        else:
            normalized_base = URL.from_value(base_url, adapters=url_adapters)
            base_path = f"{(normalized_base.path or '').rstrip('/')}/"
            self.base_url = normalized_base.with_path(base_path, keep_query=False).with_fragment(
                None
            )
        self.url_adapters = url_adapters
        self.headers = dict(headers or {})
        self.backend = backend
        self.timeout = timeout
        self.retry = retry
        self.pool = pool
        self.stream = stream
        self.allow_redirects = allow_redirects
        self.verify_ssl = verify_ssl
        self.http2 = http2
        self.proxy = proxy

    def build(self, method: str, url: URLInput, kwargs: dict[str, object]) -> FetchRequest:
        """Merge defaults into one validated request."""
        resolved_url = URL.from_value(
            url,
            base=self.base_url,
            adapters=self.url_adapters,
        )
        request_headers = {**self.headers, **dict(kwargs.pop("headers", {}) or {})}
        values: dict[str, Any] = {
            "url": resolved_url,
            "method": method.upper(),
            "headers": request_headers,
            "backend": self.backend,
            "timeout": self.timeout,
            "retry": self.retry,
            "pool": self.pool,
            "stream": self.stream,
            "allow_redirects": self.allow_redirects,
            "verify_ssl": self.verify_ssl,
            "http2": self.http2,
            "proxy": self.proxy,
        }
        values.update(kwargs)
        return FetchRequest(**values)


class FetchClient:
    """Reusable synchronous fetch client with pooled connections.

    Use this as a context manager when the client owns its service. A supplied
    service remains owned by the caller and is not closed by this wrapper.
    """

    def __init__(
        self,
        *,
        base_url: URLInput | None = None,
        url_adapters: URLAdapterRegistry | None = None,
        headers: Mapping[str, str] | None = None,
        backend: BackendKind = "httpx",
        timeout: TimeoutPolicy | None = None,
        retry: RetryPolicy | None = None,
        pool: PoolPolicy | None = None,
        stream: StreamPolicy | None = None,
        allow_redirects: bool = True,
        verify_ssl: bool = True,
        http2: bool = True,
        proxy: str | None = None,
        header_provider: HeaderProvider | None = None,
        rate_limiter: DomainRateLimiter | None = None,
        service: FetchService | None = None,
    ) -> None:
        self._owns_service = service is None
        self.service = service or FetchService(
            header_provider=header_provider,
            rate_limiter=rate_limiter,
        )
        self._builder = _RequestBuilder(
            base_url=base_url,
            url_adapters=url_adapters,
            headers=headers,
            backend=backend,
            timeout=timeout or TimeoutPolicy(),
            retry=retry or RetryPolicy(),
            pool=pool or PoolPolicy(),
            stream=stream or StreamPolicy(),
            allow_redirects=allow_redirects,
            verify_ssl=verify_ssl,
            http2=http2,
            proxy=proxy,
        )
        self._closed = False

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("FetchClient is closed")

    def send(self, request: FetchRequest) -> FetchResponse:
        """Send a pre-built request."""
        self._ensure_open()
        return self.service.fetch(request)

    def request(
        self, method: RequestMethod | str, url: URLInput, /, **kwargs: object
    ) -> FetchResponse:
        """Build and send a request using client defaults."""
        return self.send(self._builder.build(method, url, kwargs))

    def get(self, url: URLInput, /, **kwargs: object) -> FetchResponse:
        """Send a GET request."""
        return self.request("GET", url, **kwargs)

    def post(self, url: URLInput, /, **kwargs: object) -> FetchResponse:
        """Send a POST request."""
        return self.request("POST", url, **kwargs)

    def put(self, url: URLInput, /, **kwargs: object) -> FetchResponse:
        """Send a PUT request."""
        return self.request("PUT", url, **kwargs)

    def patch(self, url: URLInput, /, **kwargs: object) -> FetchResponse:
        """Send a PATCH request."""
        return self.request("PATCH", url, **kwargs)

    def delete(self, url: URLInput, /, **kwargs: object) -> FetchResponse:
        """Send a DELETE request."""
        return self.request("DELETE", url, **kwargs)

    def head(self, url: URLInput, /, **kwargs: object) -> FetchResponse:
        """Send a HEAD request."""
        return self.request("HEAD", url, **kwargs)

    def options(self, url: URLInput, /, **kwargs: object) -> FetchResponse:
        """Send an OPTIONS request."""
        return self.request("OPTIONS", url, **kwargs)

    def stream(
        self, method: RequestMethod | str, url: URLInput, /, **kwargs: object
    ) -> Iterator[StreamChunk]:
        """Stream normalized response chunks."""
        self._ensure_open()
        request = self._builder.build(method, url, kwargs)
        yield from self.service.stream(request)

    def iter_bytes(
        self, method: RequestMethod | str, url: URLInput, /, **kwargs: object
    ) -> Iterator[bytes]:
        """Stream raw response bytes for file and proxy consumers."""
        for chunk in self.stream(method, url, **kwargs):
            yield chunk.data

    def iter_text(
        self,
        method: RequestMethod | str,
        url: URLInput,
        /,
        *,
        encoding: str = "utf-8",
        errors: str = "replace",
        **kwargs: object,
    ) -> Iterator[str]:
        """Incrementally decode a streamed response without splitting characters."""
        decoder = codecs.getincrementaldecoder(encoding)(errors=errors)
        for chunk in self.iter_bytes(method, url, **kwargs):
            text = decoder.decode(chunk)
            if text:
                yield text
        tail = decoder.decode(b"", final=True)
        if tail:
            yield tail

    def close(self) -> None:
        """Close resources owned by this client."""
        if not self._closed and self._owns_service:
            self.service.close()
        self._closed = True

    def __enter__(self) -> FetchClient:
        self._ensure_open()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


class AsyncFetchClient:
    """Reusable async client for application state and dependency injection.

    One instance should normally live for an application's entire lifespan so
    HTTP/1.1 keepalive connections and HTTP/2 multiplexed connections can be
    reused across requests.
    """

    def __init__(
        self,
        *,
        base_url: URLInput | None = None,
        url_adapters: URLAdapterRegistry | None = None,
        headers: Mapping[str, str] | None = None,
        backend: BackendKind = "httpx",
        timeout: TimeoutPolicy | None = None,
        retry: RetryPolicy | None = None,
        pool: PoolPolicy | None = None,
        stream: StreamPolicy | None = None,
        allow_redirects: bool = True,
        verify_ssl: bool = True,
        http2: bool = True,
        proxy: str | None = None,
        header_provider: HeaderProvider | None = None,
        rate_limiter: DomainRateLimiter | None = None,
        service: FetchService | None = None,
    ) -> None:
        self._owns_service = service is None
        self.service = service or FetchService(
            header_provider=header_provider,
            rate_limiter=rate_limiter,
        )
        resolved_pool = pool or PoolPolicy()
        self._builder = _RequestBuilder(
            base_url=base_url,
            url_adapters=url_adapters,
            headers=headers,
            backend=backend,
            timeout=timeout or TimeoutPolicy(),
            retry=retry or RetryPolicy(),
            pool=resolved_pool,
            stream=stream or StreamPolicy(),
            allow_redirects=allow_redirects,
            verify_ssl=verify_ssl,
            http2=http2,
            proxy=proxy,
        )
        self._concurrency = resolved_pool.concurrency
        self._closed = False

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("AsyncFetchClient is closed")

    async def send(self, request: FetchRequest) -> FetchResponse:
        """Send a pre-built request."""
        self._ensure_open()
        return await self.service.afetch(request)

    async def request(
        self, method: RequestMethod | str, url: URLInput, /, **kwargs: object
    ) -> FetchResponse:
        """Build and send a request using client defaults."""
        return await self.send(self._builder.build(method, url, kwargs))

    async def get(self, url: URLInput, /, **kwargs: object) -> FetchResponse:
        """Send a GET request."""
        return await self.request("GET", url, **kwargs)

    async def post(self, url: URLInput, /, **kwargs: object) -> FetchResponse:
        """Send a POST request."""
        return await self.request("POST", url, **kwargs)

    async def put(self, url: URLInput, /, **kwargs: object) -> FetchResponse:
        """Send a PUT request."""
        return await self.request("PUT", url, **kwargs)

    async def patch(self, url: URLInput, /, **kwargs: object) -> FetchResponse:
        """Send a PATCH request."""
        return await self.request("PATCH", url, **kwargs)

    async def delete(self, url: URLInput, /, **kwargs: object) -> FetchResponse:
        """Send a DELETE request."""
        return await self.request("DELETE", url, **kwargs)

    async def head(self, url: URLInput, /, **kwargs: object) -> FetchResponse:
        """Send a HEAD request."""
        return await self.request("HEAD", url, **kwargs)

    async def options(self, url: URLInput, /, **kwargs: object) -> FetchResponse:
        """Send an OPTIONS request."""
        return await self.request("OPTIONS", url, **kwargs)

    async def stream(
        self, method: RequestMethod | str, url: URLInput, /, **kwargs: object
    ) -> AsyncIterator[StreamChunk]:
        """Stream normalized response chunks."""
        self._ensure_open()
        request = self._builder.build(method, url, kwargs)
        async for chunk in self.service.astream(request):
            yield chunk

    async def iter_bytes(
        self, method: RequestMethod | str, url: URLInput, /, **kwargs: object
    ) -> AsyncIterator[bytes]:
        """Stream raw bytes, suitable for FastAPI ``StreamingResponse``."""
        async for chunk in self.stream(method, url, **kwargs):
            yield chunk.data

    async def iter_text(
        self,
        method: RequestMethod | str,
        url: URLInput,
        /,
        *,
        encoding: str = "utf-8",
        errors: str = "replace",
        **kwargs: object,
    ) -> AsyncIterator[str]:
        """Incrementally decode a streamed response without splitting characters."""
        decoder = codecs.getincrementaldecoder(encoding)(errors=errors)
        async for chunk in self.iter_bytes(method, url, **kwargs):
            text = decoder.decode(chunk)
            if text:
                yield text
        tail = decoder.decode(b"", final=True)
        if tail:
            yield tail

    async def _iter_inputs(
        self, inputs: Iterable[FetchInput] | AsyncIterable[FetchInput]
    ) -> AsyncIterator[FetchInput]:
        if isinstance(inputs, AsyncIterable):
            async for item in inputs:
                yield item
        else:
            for item in inputs:
                yield item

    async def _send_input(self, item: FetchInput) -> FetchResponse:
        return await self.send(item) if isinstance(item, FetchRequest) else await self.get(item)

    async def imap(
        self,
        inputs: Iterable[FetchInput] | AsyncIterable[FetchInput],
        *,
        concurrency: int | None = None,
        ordered: bool = True,
    ) -> AsyncIterator[FetchResponse]:
        """Fetch a sync or async iterable with bounded, backpressured concurrency.

        Args:
            inputs: URL strings or pre-built requests. The source is consumed
                lazily, so it may be a large generator or an async generator.
            concurrency: Maximum number of active requests. Defaults to the
                client pool policy's concurrency setting.
            ordered: Preserve source ordering when true. Set false to yield
                responses as soon as they complete.
        """
        self._ensure_open()
        limit = self._concurrency if concurrency is None else concurrency
        if limit < 1:
            raise ValueError("concurrency must be at least 1")

        source = self._iter_inputs(inputs).__aiter__()
        pending: dict[asyncio.Task[FetchResponse], int] = {}
        ready: dict[int, asyncio.Task[FetchResponse]] = {}
        source_exhausted = False
        input_index = 0
        output_index = 0

        try:
            while pending or not source_exhausted:
                occupied = len(pending) + (len(ready) if ordered else 0)
                while not source_exhausted and occupied < limit:
                    try:
                        item = await anext(source)
                    except StopAsyncIteration:
                        source_exhausted = True
                        break
                    task = asyncio.create_task(self._send_input(item))
                    pending[task] = input_index
                    input_index += 1
                    occupied += 1

                if not pending:
                    break

                done, _ = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                if ordered:
                    for task in done:
                        ready[pending.pop(task)] = task
                    while output_index in ready:
                        yield ready.pop(output_index).result()
                        output_index += 1
                else:
                    for task in done:
                        pending.pop(task)
                        yield task.result()
        finally:
            for task in pending:
                task.cancel()
            unfinished = [*pending, *ready.values()]
            if unfinished:
                await asyncio.gather(*unfinished, return_exceptions=True)
            close_source = getattr(source, "aclose", None)
            if callable(close_source):
                await close_source()

    async def aclose(self) -> None:
        """Close resources owned by this client."""
        if not self._closed and self._owns_service:
            await self.service.aclose()
        self._closed = True

    async def __aenter__(self) -> AsyncFetchClient:
        self._ensure_open()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()
