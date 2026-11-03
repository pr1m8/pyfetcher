"""Unit tests for the optional duck-typed Scrapy bridge."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from pyfetcher.contracts.policy import RetryPolicy, StreamPolicy, TimeoutPolicy
from pyfetcher.contracts.request import FetchRequest
from pyfetcher.integrations.scrapy import (
    PyfetcherDownloaderMiddleware,
    ScrapyBridgeError,
    ScrapyEngineTransport,
    ScrapyHttpStatusError,
    ScrapyRequestOptions,
    from_scrapy_request,
    from_scrapy_response,
    to_scrapy_request,
    to_scrapy_response,
)


@dataclass
class FakeScrapyRequest:
    url: str
    method: str = "GET"
    headers: dict = field(default_factory=dict)
    body: bytes = b""
    callback: object | None = None
    errback: object | None = None
    meta: dict = field(default_factory=dict)
    cb_kwargs: dict = field(default_factory=dict)
    priority: int = 0
    dont_filter: bool = False


@dataclass
class FakeScrapyResponse:
    url: str
    status: int = 200
    headers: dict = field(default_factory=dict)
    body: bytes = b""
    request: object | None = None
    encoding: str = "utf-8"
    protocol: str = "HTTP/2"


def test_to_scrapy_request_maps_policy_and_native_options() -> None:
    request = FetchRequest(
        url="https://example.com/path?old=1",
        method="POST",
        params={"new": 2},
        headers={"content-type": "text/plain"},
        data="hello",
        proxy="http://proxy.example:8080",
        allow_redirects=False,
        timeout=TimeoutPolicy(total_seconds=12),
        retry=RetryPolicy(attempts=5),
        stream=StreamPolicy(max_bytes=1000),
    )
    options = ScrapyRequestOptions(meta={"download_slot": "example"}, priority=10)

    converted = to_scrapy_request(
        request,
        options=options,
        request_factory=FakeScrapyRequest,
    )

    assert isinstance(converted, FakeScrapyRequest)
    assert converted.url == "https://example.com/path?old=1&new=2"
    assert converted.body == b"hello"
    assert converted.priority == 10
    assert converted.meta["download_timeout"] == 12
    assert converted.meta["max_retry_times"] == 4
    assert converted.meta["proxy"] == "http://proxy.example:8080"
    assert converted.meta["dont_redirect"] is True
    assert converted.meta["download_maxsize"] == 1000


def test_to_scrapy_request_rejects_streaming_upload() -> None:
    request = FetchRequest(url="https://example.com", content=iter([b"chunk"]))
    with pytest.raises(ScrapyBridgeError, match="streaming request content"):
        to_scrapy_request(request, request_factory=FakeScrapyRequest)


def test_real_scrapy_request_and_engine_api_smoke() -> None:
    scrapy = pytest.importorskip("scrapy")
    from scrapy.core.engine import ExecutionEngine

    converted = to_scrapy_request(FetchRequest(url="https://example.com"))

    assert isinstance(converted, scrapy.Request)
    assert hasattr(ExecutionEngine, "download_async")


def test_scrapy_request_round_trip_to_fetch_request() -> None:
    request = FakeScrapyRequest(
        url="https://example.com/upload",
        method="POST",
        headers={b"X-Test": b"yes"},
        body=b"payload",
        meta={
            "download_timeout": 15,
            "max_retry_times": 3,
            "proxy": "http://proxy.example:8080",
            "dont_redirect": True,
        },
    )

    converted = from_scrapy_request(request, backend="aiohttp")

    assert converted.method == "POST"
    assert converted.data == b"payload"
    assert converted.headers["X-Test"] == "yes"
    assert converted.backend == "aiohttp"
    assert converted.retry.attempts == 4
    assert converted.allow_redirects is False


def test_response_conversion_in_both_directions() -> None:
    request = FetchRequest(url="https://example.com")
    scrapy_response = FakeScrapyResponse(
        url="https://example.com/final",
        status=201,
        headers={b"Content-Type": b"text/plain"},
        body="héllo".encode(),
    )

    converted = from_scrapy_response(scrapy_response, request, 12.5)
    assert converted.status_code == 201
    assert converted.text == "héllo"
    assert converted.http_version == "HTTP/2"

    round_trip = to_scrapy_response(
        converted,
        FakeScrapyRequest(url="https://example.com"),
        response_factory=FakeScrapyResponse,
    )
    assert isinstance(round_trip, FakeScrapyResponse)
    assert round_trip.status == 201


def test_real_scrapy_html_response_preserves_text_api() -> None:
    scrapy = pytest.importorskip("scrapy")
    request = scrapy.Request("https://example.com")
    response = from_scrapy_response(
        scrapy.http.HtmlResponse(
            url=request.url,
            request=request,
            headers={"Content-Type": "text/html; charset=utf-8"},
            body=b"<p>Hello</p>",
            encoding="utf-8",
        ),
        FetchRequest(url=request.url),
        1.0,
    )

    converted = to_scrapy_response(response, request)

    assert isinstance(converted, scrapy.http.HtmlResponse)
    assert converted.text == "<p>Hello</p>"


async def test_engine_transport_uses_download_async() -> None:
    class Engine:
        async def download_async(self, request):
            return FakeScrapyResponse(url=request.url, body=b"ok")

    transport = ScrapyEngineTransport(Engine(), request_factory=FakeScrapyRequest)
    response = await transport.afetch(FetchRequest(url="https://example.com"))

    assert response.status_code == 200
    assert response.backend == "scrapy"
    assert response.body == b"ok"


async def test_engine_transport_raises_non_retryable_status() -> None:
    class Engine:
        async def download_async(self, request):
            return FakeScrapyResponse(url=request.url, status=404)

    transport = ScrapyEngineTransport(Engine(), request_factory=FakeScrapyRequest)
    with pytest.raises(ScrapyHttpStatusError, match="404"):
        await transport.afetch(FetchRequest(url="https://example.com/missing"))


async def test_engine_transport_returns_retryable_status_to_service() -> None:
    class Engine:
        async def download_async(self, request):
            return FakeScrapyResponse(url=request.url, status=503)

    transport = ScrapyEngineTransport(Engine(), request_factory=FakeScrapyRequest)
    response = await transport.afetch(FetchRequest(url="https://example.com/busy"))
    assert response.status_code == 503


async def test_engine_transport_rejects_streaming() -> None:
    transport = ScrapyEngineTransport(object(), request_factory=FakeScrapyRequest)
    with pytest.raises(NotImplementedError, match="does not expose response streaming"):
        await anext(transport.astream(FetchRequest(url="https://example.com")))


def test_downloader_middleware_does_not_close_injected_service() -> None:
    middleware = PyfetcherDownloaderMiddleware(service=object())

    assert middleware.spider_closed(object()) is None
