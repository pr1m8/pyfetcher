"""Reusable synchronous and asynchronous byte-stream adapters.

Purpose:
    Normalize byte sources from memory, files, fetch chunks, Scrapy responses,
    and downloader results without forcing every integration to share a client.

Design:
    ``ByteStream`` distinguishes replayable sources from one-shot iterators,
    validates chunks at consumption time, and makes buffering an explicit
    ``read``/``aread`` operation with an optional size limit.
"""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import (
    AsyncIterable,
    AsyncIterator,
    Callable,
    Iterable,
    Iterator,
    Mapping,
)
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

type BytesLike = bytes | bytearray | memoryview
type SyncByteFactory = Callable[[], Iterator[bytes]]
type AsyncByteFactory = Callable[[], AsyncIterator[bytes]]

_END = object()


def _next(chunks: Iterator[bytes]) -> bytes | object:
    return next(chunks, _END)


class ByteStreamError(RuntimeError):
    """Base error for byte-source adaptation and consumption."""


class ByteLimitExceededError(ByteStreamError):
    """Raised before a stream consumer exceeds its configured byte limit."""


# Backward-compatible name retained for the unreleased draft API.
ByteLimitExceeded = ByteLimitExceededError


class ByteStreamInfo(BaseModel):
    """Serializable hints describing a runtime byte stream."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str | None = None
    media_type: str | None = None
    length: int | None = Field(default=None, ge=0)
    replayable: bool = False
    source: str = "custom"


class SyncByteSource(Protocol):
    """Lightweight protocol for synchronous byte producers."""

    def iter_bytes(self, *, max_bytes: int | None = None) -> Iterator[bytes]: ...


class AsyncByteSource(Protocol):
    """Lightweight protocol for asynchronous byte producers."""

    def aiter_bytes(self, *, max_bytes: int | None = None) -> AsyncIterator[bytes]: ...


def _chunk(value: object) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, (bytearray, memoryview)):
        return bytes(value)
    data = getattr(value, "data", None)
    if isinstance(data, (bytes, bytearray, memoryview)):
        return bytes(data)
    raise TypeError(f"byte streams must yield bytes-like chunks, got {type(value).__name__}")


def _bounded(chunks: Iterator[bytes], max_bytes: int | None) -> Iterator[bytes]:
    consumed = 0
    for value in chunks:
        chunk = _chunk(value)
        consumed += len(chunk)
        if max_bytes is not None and consumed > max_bytes:
            raise ByteLimitExceededError(f"byte stream exceeded {max_bytes} bytes")
        yield chunk


async def _abounded(
    chunks: AsyncIterator[bytes],
    max_bytes: int | None,
) -> AsyncIterator[bytes]:
    consumed = 0
    async for value in chunks:
        chunk = _chunk(value)
        consumed += len(chunk)
        if max_bytes is not None and consumed > max_bytes:
            raise ByteLimitExceededError(f"byte stream exceeded {max_bytes} bytes")
        yield chunk


class ByteStream:
    """One normalized byte source with explicit sync/async consumption modes."""

    def __init__(
        self,
        *,
        info: ByteStreamInfo,
        sync_factory: SyncByteFactory | None = None,
        async_factory: AsyncByteFactory | None = None,
        path: Path | None = None,
    ) -> None:
        if sync_factory is None and async_factory is None:
            raise ValueError("ByteStream requires a sync or async byte factory")
        self.info = info
        self._sync_factory = sync_factory
        self._async_factory = async_factory
        self._path = path
        self._opened = False

    @property
    def path(self) -> Path | None:
        """Return the underlying path when the stream was created from a file."""
        return self._path

    @property
    def supports_sync(self) -> bool:
        """Return whether the stream can be consumed synchronously."""
        return self._sync_factory is not None

    def _claim(self) -> None:
        if not self.info.replayable and self._opened:
            raise ByteStreamError("one-shot byte stream has already been consumed")
        self._opened = True

    @classmethod
    def from_bytes(
        cls,
        data: BytesLike,
        *,
        name: str | None = None,
        media_type: str | None = None,
        chunk_size: int = 64 * 1024,
        source: str = "memory",
    ) -> ByteStream:
        """Create a replayable stream over immutable buffered bytes."""
        if chunk_size < 1:
            raise ValueError("chunk_size must be positive")
        value = bytes(data)

        def chunks() -> Iterator[bytes]:
            for offset in range(0, len(value), chunk_size):
                yield value[offset : offset + chunk_size]

        return cls(
            info=ByteStreamInfo(
                name=name,
                media_type=media_type,
                length=len(value),
                replayable=True,
                source=source,
            ),
            sync_factory=chunks,
        )

    @classmethod
    def from_path(
        cls,
        path: str | Path,
        *,
        media_type: str | None = None,
        chunk_size: int = 64 * 1024,
    ) -> ByteStream:
        """Create a replayable, incrementally read filesystem stream."""
        if chunk_size < 1:
            raise ValueError("chunk_size must be positive")
        resolved = Path(path)
        if not resolved.is_file():
            raise FileNotFoundError(resolved)

        def chunks() -> Iterator[bytes]:
            with resolved.open("rb") as handle:
                while chunk := handle.read(chunk_size):
                    yield chunk

        return cls(
            info=ByteStreamInfo(
                name=resolved.name,
                media_type=media_type,
                length=resolved.stat().st_size,
                replayable=True,
                source="file",
            ),
            sync_factory=chunks,
            path=resolved,
        )

    @classmethod
    def from_iterable(
        cls,
        chunks: Iterable[BytesLike | object],
        *,
        name: str | None = None,
        media_type: str | None = None,
        length: int | None = None,
        source: str = "iterable",
    ) -> ByteStream:
        """Adapt a synchronous iterable, preserving one-shot iterator semantics."""
        replayable = not isinstance(chunks, Iterator)

        def factory() -> Iterator[bytes]:
            for value in chunks:
                yield _chunk(value)

        return cls(
            info=ByteStreamInfo(
                name=name,
                media_type=media_type,
                length=length,
                replayable=replayable,
                source=source,
            ),
            sync_factory=factory,
        )

    @classmethod
    def from_async_iterable(
        cls,
        chunks: AsyncIterable[BytesLike | object],
        *,
        name: str | None = None,
        media_type: str | None = None,
        length: int | None = None,
        source: str = "async_iterable",
    ) -> ByteStream:
        """Adapt an async iterable without buffering it."""
        replayable = not isinstance(chunks, AsyncIterator)

        async def factory() -> AsyncIterator[bytes]:
            async for value in chunks:
                yield _chunk(value)

        return cls(
            info=ByteStreamInfo(
                name=name,
                media_type=media_type,
                length=length,
                replayable=replayable,
                source=source,
            ),
            async_factory=factory,
        )

    @classmethod
    def from_response(cls, response: object) -> ByteStream:
        """Adapt a buffered fetchkit or Scrapy response by duck typing."""
        body = getattr(response, "body", None)
        if not isinstance(body, (bytes, bytearray, memoryview)):
            raise TypeError("response adapter requires a buffered bytes-like body")
        headers = getattr(response, "headers", {}) or {}
        media_type = getattr(response, "content_type", None)
        if media_type is None and hasattr(headers, "get"):
            media_type = headers.get("content-type") or headers.get("Content-Type")
            if isinstance(media_type, bytes):
                media_type = media_type.decode(errors="replace")
        url = getattr(response, "final_url", None) or getattr(response, "url", None)
        return cls.from_bytes(
            body,
            name=str(url) if url is not None else None,
            media_type=str(media_type) if media_type else None,
            source="response",
        )

    @classmethod
    def from_download_result(cls, result: object) -> ByteStream:
        """Adapt a yt-dlp, gallery-dl, or direct downloader result with a path."""
        path = getattr(result, "local_path", None)
        if not path:
            raise TypeError("download result has no local_path; resolve its blob reference first")
        return cls.from_path(path, media_type=getattr(result, "mime_type", None))

    def iter_bytes(self, *, max_bytes: int | None = None) -> Iterator[bytes]:
        """Consume synchronously, raising when the source is async-only."""
        if self._sync_factory is None:
            raise ByteStreamError("async-only byte stream requires aiter_bytes()")
        self._claim()
        yield from _bounded(self._sync_factory(), max_bytes)

    async def aiter_bytes(self, *, max_bytes: int | None = None) -> AsyncIterator[bytes]:
        """Consume asynchronously; synchronous sources are adapted lazily."""
        self._claim()
        if self._async_factory is not None:
            async for chunk in _abounded(self._async_factory(), max_bytes):
                yield chunk
            return
        assert self._sync_factory is not None
        consumed = 0
        chunks = self._sync_factory()
        while (value := await asyncio.to_thread(_next, chunks)) is not _END:
            chunk = _chunk(value)
            consumed += len(chunk)
            if max_bytes is not None and consumed > max_bytes:
                raise ByteLimitExceededError(f"byte stream exceeded {max_bytes} bytes")
            yield chunk

    def read(self, *, max_bytes: int | None = None) -> bytes:
        """Explicitly buffer a synchronous stream."""
        return b"".join(self.iter_bytes(max_bytes=max_bytes))

    async def aread(self, *, max_bytes: int | None = None) -> bytes:
        """Explicitly buffer a sync or async stream."""
        return b"".join([chunk async for chunk in self.aiter_bytes(max_bytes=max_bytes)])

    def sha256(self, *, max_bytes: int | None = None) -> str:
        """Hash a synchronous stream incrementally."""
        digest = hashlib.sha256()
        for chunk in self.iter_bytes(max_bytes=max_bytes):
            digest.update(chunk)
        return digest.hexdigest()

    async def asha256(self, *, max_bytes: int | None = None) -> str:
        """Hash a sync or async stream incrementally."""
        digest = hashlib.sha256()
        async for chunk in self.aiter_bytes(max_bytes=max_bytes):
            digest.update(chunk)
        return digest.hexdigest()

    def as_request_content(self, *, asynchronous: bool) -> Iterable[bytes] | AsyncIterable[bytes]:
        """Return the appropriate iterator for ``FetchRequest.content``."""
        return self.aiter_bytes() if asynchronous else self.iter_bytes()


def adapt_byte_stream(value: object, *, media_type: str | None = None) -> ByteStream:
    """Normalize common runtime byte sources into one ``ByteStream``."""
    if isinstance(value, ByteStream):
        return value
    if isinstance(value, (bytes, bytearray, memoryview)):
        return ByteStream.from_bytes(value, media_type=media_type)
    if isinstance(value, Path):
        return ByteStream.from_path(value, media_type=media_type)
    if getattr(value, "local_path", None):
        return ByteStream.from_download_result(value)
    if isinstance(getattr(value, "body", None), (bytes, bytearray, memoryview)):
        return ByteStream.from_response(value)
    if isinstance(value, AsyncIterable):
        return ByteStream.from_async_iterable(value, media_type=media_type)
    if isinstance(value, Iterable) and not isinstance(value, (str, Mapping)):
        return ByteStream.from_iterable(value, media_type=media_type)
    raise TypeError(f"cannot adapt {type(value).__name__} to ByteStream")


__all__ = [
    "AsyncByteSource",
    "ByteLimitExceeded",
    "ByteLimitExceededError",
    "ByteStream",
    "ByteStreamError",
    "ByteStreamInfo",
    "BytesLike",
    "SyncByteSource",
    "adapt_byte_stream",
]
