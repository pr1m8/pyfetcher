"""Optional Scrapy request, response, engine, and middleware bridges.

Purpose:
    Interoperate with an existing Scrapy crawler without making Scrapy or
    Twisted core fetchkit dependencies.

Design:
    Conversion helpers are duck-typed and injectable for unit testing. The
    engine transport attaches to an already-running Scrapy engine and never
    installs or stops a reactor. Response streaming is explicitly unsupported
    because Scrapy's downloader engine resolves a complete response.
"""

from __future__ import annotations

import inspect
import json
from collections.abc import Callable, Mapping
from time import perf_counter
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field

from pyfetcher.contracts.policy import RetryPolicy, StreamPolicy, TimeoutPolicy
from pyfetcher.contracts.request import FetchRequest
from pyfetcher.contracts.response import FetchResponse


class ScrapyBridgeError(RuntimeError):
    """Base exception for Scrapy conversion and engine failures."""


class ScrapyHttpStatusError(ScrapyBridgeError):
    """Raised for non-retryable HTTP errors returned by Scrapy."""

    def __init__(self, status_code: int, url: str) -> None:
        self.status_code = status_code
        self.url = url
        super().__init__(f"Scrapy response {status_code} for {url}")


class ScrapyRequestOptions(BaseModel):
    """Scrapy-native request options kept outside ``FetchRequest``."""

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    meta: dict[str, Any] = Field(default_factory=dict)
    cb_kwargs: dict[str, Any] = Field(default_factory=dict)
    priority: int = 0
    dont_filter: bool = False


def _url_with_params(request: FetchRequest) -> str:
    if not request.params:
        return request.url.unicode_string()
    parts = urlsplit(request.url.unicode_string())
    query = [*parse_qsl(parts.query, keep_blank_values=True), *request.params.items()]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def _buffered_body(request: FetchRequest) -> tuple[bytes, dict[str, str]]:
    headers = dict(request.headers)
    if request.json_data is not None:
        headers.setdefault("content-type", "application/json")
        return json.dumps(request.json_data, separators=(",", ":")).encode(), headers
    body = request.content if request.content is not None else request.data
    if request.content_factory is not None or (
        body is not None and not isinstance(body, (bytes, str))
    ):
        raise ScrapyBridgeError(
            "Scrapy requests require buffered bytes or text; "
            "streaming request content is unsupported"
        )
    if isinstance(body, str):
        return body.encode(), headers
    return body or b"", headers


def to_scrapy_request(
    request: FetchRequest,
    *,
    options: ScrapyRequestOptions | None = None,
    callback: Callable[..., object] | None = None,
    errback: Callable[..., object] | None = None,
    request_factory: Callable[..., object] | None = None,
) -> object:
    """Convert a fetchkit request into a Scrapy ``Request``."""
    if request_factory is None:
        try:
            from scrapy import Request
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise ImportError(
                "Scrapy integration requires `pip install 'fetchkit[scrapy]'`"
            ) from exc
        request_factory = Request
    resolved = options or ScrapyRequestOptions()
    body, headers = _buffered_body(request)
    meta = {
        "download_timeout": request.timeout.total_seconds,
        "max_retry_times": max(0, request.retry.attempts - 1),
        "handle_httpstatus_all": True,
        **resolved.meta,
    }
    if request.proxy is not None:
        meta.setdefault("proxy", request.proxy)
    if not request.allow_redirects:
        meta.setdefault("dont_redirect", True)
    if request.stream.max_bytes is not None:
        meta.setdefault("download_maxsize", request.stream.max_bytes)
    return request_factory(
        url=_url_with_params(request),
        method=request.method,
        headers=headers,
        body=body,
        callback=callback,
        errback=errback,
        meta=meta,
        cb_kwargs=resolved.cb_kwargs,
        priority=resolved.priority,
        dont_filter=resolved.dont_filter,
    )


def _unicode_headers(headers: object) -> dict[str, str]:
    to_unicode_dict = getattr(headers, "to_unicode_dict", None)
    if callable(to_unicode_dict):
        return dict(to_unicode_dict())
    if not isinstance(headers, Mapping):
        return {}
    normalized: dict[str, str] = {}
    for key, value in headers.items():
        decoded_key = key.decode(errors="replace") if isinstance(key, bytes) else str(key)
        if isinstance(value, (list, tuple)):
            value = b", ".join(value) if value and isinstance(value[0], bytes) else ", ".join(value)
        decoded_value = value.decode(errors="replace") if isinstance(value, bytes) else str(value)
        normalized[decoded_key] = decoded_value
    return normalized


def from_scrapy_request(request: object, *, backend: str = "httpx") -> FetchRequest:
    """Convert a buffered Scrapy request into a fetchkit request."""
    meta = dict(getattr(request, "meta", {}) or {})
    timeout = float(meta.get("download_timeout", 30.0))
    attempts = int(meta.get("max_retry_times", 2)) + 1
    body = bytes(getattr(request, "body", b"") or b"")
    return FetchRequest(
        url=str(request.url),
        method=str(getattr(request, "method", "GET")),
        headers=_unicode_headers(getattr(request, "headers", {})),
        data=body or None,
        backend=backend,
        proxy=meta.get("proxy"),
        allow_redirects=not bool(meta.get("dont_redirect", False)),
        timeout=TimeoutPolicy(
            total_seconds=timeout,
            connect_seconds=min(10.0, timeout),
            read_seconds=timeout,
            write_seconds=timeout,
            pool_seconds=min(10.0, timeout),
        ),
        retry=RetryPolicy(attempts=attempts),
        stream=StreamPolicy(max_bytes=meta.get("download_maxsize")),
    )


def from_scrapy_response(
    response: object, request: FetchRequest, elapsed_ms: float
) -> FetchResponse:
    """Normalize a Scrapy response into ``FetchResponse``."""
    body = bytes(getattr(response, "body", b"") or b"")
    headers = _unicode_headers(getattr(response, "headers", {}))
    encoding = getattr(response, "encoding", None) or "utf-8"
    protocol = getattr(response, "protocol", None)
    if isinstance(protocol, bytes):
        protocol = protocol.decode(errors="replace")
    return FetchResponse(
        request_url=request.url.unicode_string(),
        final_url=str(getattr(response, "url", request.url.unicode_string())),
        status_code=int(getattr(response, "status", 200)),
        headers=headers,
        content_type=headers.get("Content-Type") or headers.get("content-type"),
        text=body.decode(encoding, errors="replace"),
        body=body,
        backend="scrapy",
        http_version=str(protocol) if protocol else None,
        elapsed_ms=elapsed_ms,
    )


def to_scrapy_response(
    response: FetchResponse,
    scrapy_request: object,
    *,
    response_factory: Callable[..., object] | None = None,
) -> object:
    """Convert a fetchkit response for use by Scrapy downloader middleware."""
    if response_factory is None:
        try:
            from scrapy.http import HtmlResponse, Response, TextResponse
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise ImportError(
                "Scrapy integration requires `pip install 'fetchkit[scrapy]'`"
            ) from exc
        content_type = (response.content_type or "").lower()
        if "html" in content_type:
            response_factory = HtmlResponse
        elif content_type.startswith("text/") or any(
            kind in content_type for kind in ("json", "xml", "javascript")
        ):
            response_factory = TextResponse
        else:
            response_factory = Response
    return response_factory(
        url=response.final_url,
        status=response.status_code,
        headers=response.headers,
        body=response.body or b"",
        request=scrapy_request,
    )


class ScrapyEngineTransport:
    """Async transport attached to an already-running Scrapy engine.

    Pass the engine itself or another object exposing current
    ``download_async(request)``. Older ``download(request)`` Deferred APIs are
    supported as a compatibility fallback when the asyncio reactor is active.
    """

    def __init__(
        self,
        engine: object,
        *,
        request_options: ScrapyRequestOptions | None = None,
        request_factory: Callable[..., object] | None = None,
    ) -> None:
        self._engine = engine
        self._request_options = request_options
        self._request_factory = request_factory

    async def afetch(self, request: FetchRequest) -> FetchResponse:
        scrapy_request = to_scrapy_request(
            request,
            options=self._request_options,
            request_factory=self._request_factory,
        )
        start = perf_counter()
        download_async = getattr(self._engine, "download_async", None)
        if callable(download_async):
            response = await download_async(scrapy_request)
        else:
            download = getattr(self._engine, "download", None)
            if not callable(download):
                raise ScrapyBridgeError("Scrapy engine has no download_async or download method")
            deferred = download(scrapy_request)
            if inspect.isawaitable(deferred):
                response = await deferred
            else:
                try:
                    from scrapy.utils.defer import deferred_to_future
                except ImportError as exc:  # pragma: no cover - optional dependency
                    raise ImportError(
                        "Scrapy integration requires `pip install 'fetchkit[scrapy]'`"
                    ) from exc
                response = await deferred_to_future(deferred)
        elapsed_ms = (perf_counter() - start) * 1000.0
        normalized = from_scrapy_response(response, request, elapsed_ms)
        if (
            normalized.status_code >= 400
            and normalized.status_code not in request.retry.retry_status_codes
        ):
            raise ScrapyHttpStatusError(normalized.status_code, normalized.final_url)
        return normalized

    async def astream(self, request: FetchRequest):
        raise NotImplementedError(
            "ScrapyEngineTransport does not expose response streaming; use HTTPX or aiohttp"
        )
        yield  # pragma: no cover

    async def aclose(self) -> None:
        """Leave lifecycle ownership with the attached Scrapy engine."""
        return None


class PyfetcherDownloaderMiddleware:
    """Route opted-in Scrapy requests through a fetchkit async backend.

    Set ``request.meta['pyfetcher'] = True`` and optionally
    ``request.meta['pyfetcher_backend']``. Requests without that flag continue
    through Scrapy's ordinary downloader stack.
    """

    def __init__(self, service: object | None = None) -> None:
        self._owns_service = service is None
        if service is None:
            from pyfetcher.fetch.service import FetchService

            service = FetchService()
        self._service = service

    @classmethod
    def from_crawler(cls, crawler: object) -> PyfetcherDownloaderMiddleware:
        middleware = cls()
        try:
            from scrapy import signals
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise ImportError(
                "Scrapy integration requires `pip install 'fetchkit[scrapy]'`"
            ) from exc
        crawler.signals.connect(middleware.spider_closed, signal=signals.spider_closed)
        return middleware

    def process_request(self, request: object, spider: object):
        meta = dict(getattr(request, "meta", {}) or {})
        if not meta.get("pyfetcher"):
            return None
        try:
            from scrapy.utils.defer import deferred_from_coro
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise ImportError(
                "Scrapy integration requires `pip install 'fetchkit[scrapy]'`"
            ) from exc

        async def run() -> object:
            fetch_request = from_scrapy_request(
                request,
                backend=str(meta.get("pyfetcher_backend", "httpx")),
            )
            response = await self._service.afetch(fetch_request)
            return to_scrapy_response(response, request)

        return deferred_from_coro(run())

    def spider_closed(self, spider: object):
        if not self._owns_service:
            return None
        try:
            from scrapy.utils.defer import deferred_from_coro
        except ImportError:  # pragma: no cover - optional dependency
            return None
        return deferred_from_coro(self._service.aclose())


__all__ = [
    "PyfetcherDownloaderMiddleware",
    "ScrapyBridgeError",
    "ScrapyEngineTransport",
    "ScrapyHttpStatusError",
    "ScrapyRequestOptions",
    "from_scrapy_request",
    "from_scrapy_response",
    "to_scrapy_request",
    "to_scrapy_response",
]
