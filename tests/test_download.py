"""Tests for DownloadService with mocked FetchService."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from pyfetcher.contracts.request import FetchRequest
from pyfetcher.contracts.response import StreamChunk
from pyfetcher.download.service import DownloadService


def _make_chunks(
    url: str = "https://example.com/file",
    parts: list[bytes] | None = None,
) -> list[StreamChunk]:
    """Create a list of StreamChunk objects for testing."""
    if parts is None:
        parts = [b"hello ", b"world"]
    return [
        StreamChunk(
            request_url=url + "/",
            final_url=url + "/",
            backend="httpx",
            index=i,
            data=data,
        )
        for i, data in enumerate(parts)
    ]


async def test_download_to_path():
    """Basic download assembles chunks into a file."""
    chunks = _make_chunks()

    mock_service = MagicMock()

    async def mock_stream(req):
        for chunk in chunks:
            yield chunk

    mock_service.astream = mock_stream

    dl = DownloadService(fetch_service=mock_service)
    with tempfile.TemporaryDirectory() as tmpdir:
        dest = Path(tmpdir) / "output.txt"
        result = await dl.adownload_to_path(FetchRequest(url="https://example.com/file"), dest)
        assert result == dest
        assert result.read_bytes() == b"hello world"


async def test_download_creates_parent_directories():
    """Download creates missing parent directories automatically."""
    chunks = _make_chunks(parts=[b"data"])

    mock_service = MagicMock()

    async def mock_stream(req):
        for chunk in chunks:
            yield chunk

    mock_service.astream = mock_stream

    dl = DownloadService(fetch_service=mock_service)
    with tempfile.TemporaryDirectory() as tmpdir:
        dest = Path(tmpdir) / "nested" / "deep" / "output.bin"
        result = await dl.adownload_to_path(FetchRequest(url="https://example.com/file"), dest)
        assert result.exists()
        assert result.read_bytes() == b"data"


async def test_download_empty_stream():
    """An empty stream creates an empty file."""
    mock_service = MagicMock()

    async def mock_stream(req):
        return
        yield  # noqa: RET504  # make it an async generator

    mock_service.astream = mock_stream

    dl = DownloadService(fetch_service=mock_service)
    with tempfile.TemporaryDirectory() as tmpdir:
        dest = Path(tmpdir) / "empty.bin"
        result = await dl.adownload_to_path(FetchRequest(url="https://example.com/file"), dest)
        assert result.exists()
        assert result.read_bytes() == b""


async def test_download_large_chunks():
    """Download correctly writes multiple large chunks."""
    chunk_data = b"x" * 65536  # 64 KiB
    chunks = _make_chunks(parts=[chunk_data, chunk_data, chunk_data])

    mock_service = MagicMock()

    async def mock_stream(req):
        for chunk in chunks:
            yield chunk

    mock_service.astream = mock_stream

    dl = DownloadService(fetch_service=mock_service)
    with tempfile.TemporaryDirectory() as tmpdir:
        dest = Path(tmpdir) / "large.bin"
        result = await dl.adownload_to_path(FetchRequest(url="https://example.com/file"), dest)
        assert result.stat().st_size == 65536 * 3


async def test_download_with_string_destination():
    """Download works with a string path, not just Path objects."""
    chunks = _make_chunks(parts=[b"string path"])

    mock_service = MagicMock()

    async def mock_stream(req):
        for chunk in chunks:
            yield chunk

    mock_service.astream = mock_stream

    dl = DownloadService(fetch_service=mock_service)
    with tempfile.TemporaryDirectory() as tmpdir:
        dest_str = str(Path(tmpdir) / "output.txt")
        result = await dl.adownload_to_path(FetchRequest(url="https://example.com/file"), dest_str)
        assert isinstance(result, Path)
        assert result.read_bytes() == b"string path"


async def test_download_stream_error_propagates():
    """Errors during streaming should propagate to the caller."""
    mock_service = MagicMock()

    async def mock_stream(req):
        yield StreamChunk(
            request_url="https://example.com/file/",
            final_url="https://example.com/file/",
            backend="httpx",
            index=0,
            data=b"partial",
        )
        raise ConnectionError("stream interrupted")

    mock_service.astream = mock_stream

    dl = DownloadService(fetch_service=mock_service)
    with tempfile.TemporaryDirectory() as tmpdir:
        dest = Path(tmpdir) / "broken.bin"
        with pytest.raises(ConnectionError, match="stream interrupted"):
            await dl.adownload_to_path(FetchRequest(url="https://example.com/file"), dest)
