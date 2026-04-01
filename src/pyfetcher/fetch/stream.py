"""Streaming convenience helpers for :mod:`pyfetcher`.

Purpose:
    Provide small helpers for consuming async stream chunks into a single
    bytes object.

Examples:
    ::

        >>> collect_bytes([b"a", b"b"])
        b'ab'
"""

from __future__ import annotations

from collections.abc import AsyncIterable


def collect_bytes(chunks: list[bytes]) -> bytes:
    """Concatenate a list of byte chunks into a single bytes object.

    Args:
        chunks: List of byte chunks.

    Returns:
        All chunks concatenated.

    Examples:
        ::

            >>> collect_bytes([b"a", b"b"])
            b'ab'
    """
    return b"".join(chunks)


async def collect_stream_bytes(chunks: AsyncIterable[bytes]) -> bytes:
    """Collect an async byte stream into a single bytes object.

    Iterates the async iterable and accumulates all bytes into a single
    contiguous buffer.

    Args:
        chunks: Async iterable yielding byte chunks.

    Returns:
        All chunks concatenated.

    Examples:
        ::

            >>> async def _demo():
            ...     async def _gen():
            ...         yield b"a"
            ...         yield b"b"
            ...     return await collect_stream_bytes(_gen())
    """
    collected = bytearray()
    async for chunk in chunks:
        collected.extend(chunk)
    return bytes(collected)
