"""Base transport protocols for :mod:`pyfetcher`.

Purpose:
    Define the minimal sync/async transport interfaces consumed by fetch
    services. Implementations provide backend-specific HTTP execution while
    conforming to these duck-typed protocols.

Design:
    - Sync and async protocols are distinct to avoid forcing implementers
      to provide both.
    - Streaming is modeled explicitly for async transports.
    - Implementations own backend-specific session/client lifecycles.

Examples:
    ::

        >>> hasattr(SyncTransport, "fetch")
        True
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from pyfetcher.contracts.request import FetchRequest
from pyfetcher.contracts.response import FetchResponse, StreamChunk


class SyncTransport(Protocol):
    """Protocol for synchronous fetch transports.

    Implementations must provide a ``fetch`` method that accepts a
    :class:`~pyfetcher.contracts.request.FetchRequest` and returns a
    normalized :class:`~pyfetcher.contracts.response.FetchResponse`.
    """

    def fetch(self, request: FetchRequest) -> FetchResponse:
        """Fetch a request synchronously.

        Args:
            request: The fetch request to execute.

        Returns:
            A normalized fetch response.
        """
        ...


class AsyncTransport(Protocol):
    """Protocol for asynchronous fetch transports.

    Implementations must provide ``afetch`` for full responses and
    ``astream`` for chunked streaming.
    """

    async def afetch(self, request: FetchRequest) -> FetchResponse:
        """Fetch a request asynchronously.

        Args:
            request: The fetch request to execute.

        Returns:
            A normalized fetch response.
        """
        ...

    async def astream(self, request: FetchRequest) -> AsyncIterator[StreamChunk]:
        """Stream a request asynchronously.

        Args:
            request: The fetch request to stream.

        Returns:
            An async iterator yielding :class:`StreamChunk` objects.
        """
        ...
