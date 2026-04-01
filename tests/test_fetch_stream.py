"""Unit tests for pyfetcher.fetch.stream and batch."""

from __future__ import annotations

import pytest

from pyfetcher.contracts.request import FetchRequest
from pyfetcher.fetch.batch import build_batch_request
from pyfetcher.fetch.stream import collect_bytes, collect_stream_bytes


class TestCollectBytes:
    def test_basic(self) -> None:
        assert collect_bytes([b"a", b"b", b"c"]) == b"abc"

    def test_empty(self) -> None:
        assert collect_bytes([]) == b""


@pytest.mark.asyncio
class TestCollectStreamBytes:
    async def test_basic(self) -> None:
        async def gen():
            yield b"hello"
            yield b" "
            yield b"world"

        result = await collect_stream_bytes(gen())
        assert result == b"hello world"


class TestBuildBatchRequest:
    def test_basic(self) -> None:
        req = FetchRequest(url="https://example.com")
        batch = build_batch_request([req, req])
        assert len(batch.requests) == 2
        assert batch.concurrency is None

    def test_with_concurrency(self) -> None:
        req = FetchRequest(url="https://example.com")
        batch = build_batch_request([req], concurrency=4)
        assert batch.concurrency == 4
