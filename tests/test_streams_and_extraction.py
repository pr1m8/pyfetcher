"""Reusable byte stream and custom extractor tests."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from pyfetcher.contracts import FetchResponse, StreamChunk
from pyfetcher.extraction import (
    CallableExtractor,
    ExtractionContext,
    ExtractorRegistry,
)
from pyfetcher.streams import (
    ByteLimitExceededError,
    ByteStream,
    ByteStreamError,
    adapt_byte_stream,
)


def test_replayable_memory_and_path_streams(tmp_path: Path) -> None:
    memory = ByteStream.from_bytes(b"abcdef", chunk_size=2)
    assert list(memory.iter_bytes()) == [b"ab", b"cd", b"ef"]
    assert memory.read() == b"abcdef"

    path = tmp_path / "data.bin"
    path.write_bytes(b"content")
    stream = adapt_byte_stream(path)
    assert stream.path == path
    assert stream.sha256() == hashlib.sha256(b"content").hexdigest()


def test_one_shot_stream_and_byte_limit_errors() -> None:
    stream = ByteStream.from_iterable(iter([b"one", b"two"]))
    assert stream.read() == b"onetwo"
    with pytest.raises(ByteStreamError, match="already been consumed"):
        stream.read()
    with pytest.raises(ByteLimitExceededError, match="exceeded 3"):
        ByteStream.from_bytes(b"four").read(max_bytes=3)


async def test_async_streams_and_sync_to_async_adaptation() -> None:
    async def chunks():
        yield b"a"
        yield b"b"

    async_only = ByteStream.from_async_iterable(chunks())
    assert await async_only.aread() == b"ab"
    with pytest.raises(ByteStreamError, match="async-only"):
        next(async_only.iter_bytes())

    sync = ByteStream.from_bytes(b"sync")
    assert b"".join([chunk async for chunk in sync.aiter_bytes()]) == b"sync"


def test_response_and_chunk_adapters() -> None:
    response = FetchResponse(
        request_url="https://example.com/",
        final_url="https://example.com/",
        status_code=200,
        headers={"content-type": "text/plain"},
        body=b"body",
        backend="httpx",
        elapsed_ms=1,
    )
    assert ByteStream.from_response(response).read() == b"body"
    chunks = [
        StreamChunk(
            request_url="https://example.com/",
            final_url="https://example.com/",
            backend="httpx",
            index=0,
            data=b"part",
        )
    ]
    assert adapt_byte_stream(chunks).read() == b"part"


async def test_custom_extractor_registry_supports_sync_async_and_fallback() -> None:
    context = ExtractionContext.adapt(b"hello", media_type="text/plain")
    registry = ExtractorRegistry(
        (
            CallableExtractor(
                "broken",
                lambda value: 1 / 0,
                priority=10,
            ),
            CallableExtractor(
                "length",
                lambda value: {"length": value.source.info.length or 0},
                priority=1,
            ),
        )
    )
    result = await registry.extract(context, strict=False)
    assert result.extractor == "length"
    assert result.data == {"length": 5}
    assert result.warnings and result.warnings[0].startswith("broken:")


async def test_extraction_context_can_materialize_page_documents() -> None:
    context = ExtractionContext.adapt(
        b"<h1>Page</h1>",
        url="https://example.com/",
        media_type="text/html",
    )
    page = await context.adocument(max_bytes=100)
    assert page.css("h1::text").get() == "Page"


async def test_extractor_fallback_rejects_one_shot_multiple_consumers() -> None:
    context = ExtractionContext.adapt(iter([b"hello"]))
    registry = ExtractorRegistry(
        (
            CallableExtractor("first", lambda value: {}),
            CallableExtractor("second", lambda value: {}),
        )
    )
    with pytest.raises(ValueError, match="replayable"):
        await registry.extract(context, strict=False)
