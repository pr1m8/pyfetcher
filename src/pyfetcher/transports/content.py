"""Request-content adapters shared by HTTP transports.

Purpose:
    Preserve one-shot request body generators while validating byte chunks at
    the point they are consumed.

Design:
    Synchronous transports reject async-only content. Async transports accept
    both async iterables and ordinary iterables, adapting the latter without
    buffering the complete body.
"""

from __future__ import annotations

from collections.abc import AsyncIterable, AsyncIterator, Iterable, Iterator

from pyfetcher.contracts.request import FetchRequest, RequestContent


def get_request_content(request: FetchRequest) -> RequestContent | None:
    """Return the request's preferred body source."""
    if request.content_factory is not None:
        return request.content_factory()
    return request.content if request.content is not None else request.data


def _validate_chunk(chunk: object) -> bytes:
    """Return one bytes chunk or raise an actionable type error."""
    if not isinstance(chunk, bytes):
        raise TypeError(f"streaming request content must yield bytes, got {type(chunk).__name__}")
    return chunk


def _iter_validated(content: Iterable[bytes]) -> Iterator[bytes]:
    for chunk in content:
        yield _validate_chunk(chunk)


async def _aiter_validated(content: AsyncIterable[bytes]) -> AsyncIterator[bytes]:
    async for chunk in content:
        yield _validate_chunk(chunk)


async def _aiter_from_sync(content: Iterable[bytes]) -> AsyncIterator[bytes]:
    for chunk in content:
        yield _validate_chunk(chunk)


def prepare_sync_content(
    content: RequestContent | None,
) -> bytes | str | Iterable[bytes] | None:
    """Prepare buffered or iterable content for a synchronous transport."""
    if content is None or isinstance(content, (bytes, str)):
        return content
    if isinstance(content, AsyncIterable):
        raise TypeError("async request content requires AsyncFetchClient or FetchService.afetch")
    return _iter_validated(content)


def prepare_async_content(
    content: RequestContent | None,
) -> bytes | str | AsyncIterable[bytes] | None:
    """Prepare buffered, sync-iterable, or async-iterable content for async I/O."""
    if content is None or isinstance(content, (bytes, str)):
        return content
    if isinstance(content, AsyncIterable):
        return _aiter_validated(content)
    return _aiter_from_sync(content)
