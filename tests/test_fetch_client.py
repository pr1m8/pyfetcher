"""Tests for lifecycle clients, streaming helpers, and iterable request bodies."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass

import pytest
import respx
from httpx import Response

from pyfetcher import (
    AsyncFetchClient,
    FetchClient,
    FetchRequest,
    FetchResponse,
    PoolPolicy,
    StreamPolicy,
    URLAdapterRegistry,
)


@dataclass(frozen=True)
class ApplicationURL:
    value: str


def _response(request: FetchRequest) -> FetchResponse:
    return FetchResponse(
        request_url=request.url.unicode_string(),
        final_url=request.url.unicode_string(),
        status_code=200,
        headers={},
        backend=request.backend,
        http_version="HTTP/2",
        elapsed_ms=1.0,
    )


class RecordingService:
    def __init__(self, delays: dict[str, float] | None = None) -> None:
        self.requests: list[FetchRequest] = []
        self.delays = delays or {}
        self.active = 0
        self.max_active = 0
        self.closed = False

    def fetch(self, request: FetchRequest) -> FetchResponse:
        self.requests.append(request)
        return _response(request)

    async def afetch(self, request: FetchRequest) -> FetchResponse:
        self.requests.append(request)
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            await asyncio.sleep(self.delays.get(request.url.host or "", 0))
            return _response(request)
        finally:
            self.active -= 1

    async def astream(self, request: FetchRequest) -> AsyncIterator[object]:
        if False:
            yield request

    def close(self) -> None:
        self.closed = True

    async def aclose(self) -> None:
        self.closed = True


def test_sync_client_applies_defaults_and_base_url() -> None:
    service = RecordingService()
    client = FetchClient(
        service=service,  # type: ignore[arg-type]
        base_url="https://api.example.com/v1",
        headers={"authorization": "Bearer test"},
        http2=False,
        pool=PoolPolicy(max_connections=12),
    )

    response = client.get("users", headers={"x-request": "one"})

    request = service.requests[0]
    assert response.status_code == 200
    assert request.url.unicode_string() == "https://api.example.com/v1/users"
    assert request.headers == {"authorization": "Bearer test", "x-request": "one"}
    assert request.http2 is False
    assert request.pool.max_connections == 12


def test_sync_client_uses_an_injected_bespoke_url_registry() -> None:
    service = RecordingService()
    adapters = URLAdapterRegistry()
    adapters.register_type(ApplicationURL, lambda value: value.value)
    client = FetchClient(
        service=service,  # type: ignore[arg-type]
        base_url=ApplicationURL("https://api.example.com/v2"),
        url_adapters=adapters,
    )

    client.get(ApplicationURL("items/9"))

    assert service.requests[0].url.unicode_string() == "https://api.example.com/v2/items/9"


def test_client_does_not_close_external_service() -> None:
    service = RecordingService()
    with FetchClient(service=service):  # type: ignore[arg-type]
        pass
    assert service.closed is False


@respx.mock
def test_sync_client_streams_bytes_and_text_incrementally() -> None:
    payload = "A€B".encode()
    respx.get("https://example.com/data").mock(return_value=Response(200, content=payload))

    with FetchClient(stream=StreamPolicy(chunk_size=1)) as client:
        assert b"".join(client.iter_bytes("GET", "https://example.com/data")) == payload
        assert "".join(client.iter_text("GET", "https://example.com/data")) == "A€B"


@respx.mock
def test_sync_stream_enforces_max_bytes() -> None:
    respx.get("https://example.com/data").mock(return_value=Response(200, content=b"abcdef"))

    with FetchClient(stream=StreamPolicy(chunk_size=4, max_bytes=5)) as client:
        assert b"".join(client.iter_bytes("GET", "https://example.com/data")) == b"abcde"


@respx.mock
def test_sync_generator_upload_is_not_buffered_by_request_model() -> None:
    route = respx.post("https://example.com/upload").mock(return_value=Response(200))

    def content() -> Iterator[bytes]:
        yield b"one"
        yield b"two"

    with FetchClient() as client:
        client.post("https://example.com/upload", content=content())

    assert route.calls[0].request.content == b"onetwo"


@respx.mock
async def test_async_client_accepts_sync_and_async_generator_uploads() -> None:
    route = respx.post("https://example.com/upload").mock(return_value=Response(200))

    def sync_content():
        yield b"sync"

    async def async_content():
        yield b"async"

    async with AsyncFetchClient() as client:
        await client.post("https://example.com/upload", content=sync_content())
        await client.post("https://example.com/upload", content=async_content())

    assert [call.request.content for call in route.calls] == [b"sync", b"async"]


@respx.mock
async def test_streaming_upload_rejects_non_bytes_chunks() -> None:
    respx.post("https://example.com/upload").mock(return_value=Response(200))

    def invalid_content():
        yield "not bytes"

    async with AsyncFetchClient() as client:
        with pytest.raises(TypeError, match="must yield bytes"):
            await client.post("https://example.com/upload", content=invalid_content())


@respx.mock
async def test_async_client_context_closes_owned_pool() -> None:
    respx.get("https://example.com/").mock(return_value=Response(200))
    client = AsyncFetchClient()
    async with client:
        await client.get("https://example.com")
        assert client.service.httpx_transport._async_client is not None
    assert client.service.httpx_transport._async_client is None
    with pytest.raises(RuntimeError, match="closed"):
        await client.get("https://example.com")


async def test_async_client_does_not_close_external_service() -> None:
    service = RecordingService()
    async with AsyncFetchClient(service=service):  # type: ignore[arg-type]
        pass
    assert service.closed is False


async def test_imap_is_bounded_ordered_and_accepts_async_iterables() -> None:
    service = RecordingService({"one.example": 0.03, "two.example": 0.0})
    client = AsyncFetchClient(
        service=service,  # type: ignore[arg-type]
        pool=PoolPolicy(concurrency=2),
    )

    async def urls():
        yield "https://one.example"
        yield "https://two.example"
        yield "https://three.example"

    responses = [response async for response in client.imap(urls())]

    assert [response.request_url for response in responses] == [
        "https://one.example/",
        "https://two.example/",
        "https://three.example/",
    ]
    assert service.max_active == 2


async def test_imap_can_yield_completion_order() -> None:
    service = RecordingService({"slow.example": 0.03, "fast.example": 0.0})
    client = AsyncFetchClient(service=service)  # type: ignore[arg-type]

    responses = [
        response
        async for response in client.imap(
            ["https://slow.example", "https://fast.example"],
            concurrency=2,
            ordered=False,
        )
    ]

    assert [response.request_url for response in responses] == [
        "https://fast.example/",
        "https://slow.example/",
    ]


async def test_imap_rejects_zero_concurrency() -> None:
    client = AsyncFetchClient(service=RecordingService())  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="at least 1"):
        _ = [response async for response in client.imap([], concurrency=0)]
