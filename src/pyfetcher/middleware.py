"""Composable middleware primitives shared across pyfetcher mechanisms.

Purpose:
    Provide small sync and async call-chain composers that can wrap HTTP
    fetching, acquisition providers, or downstream integration services.

Design:
    Middleware receives a typed request and a ``call_next`` handler. It may
    transform the request, observe or replace the response, retry, short-circuit,
    or translate failures without depending on a specific execution engine.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable
from typing import Protocol, TypeVar

RequestT = TypeVar("RequestT")
ResponseT = TypeVar("ResponseT")

type SyncHandler[RequestT, ResponseT] = Callable[[RequestT], ResponseT]
type AsyncHandler[RequestT, ResponseT] = Callable[[RequestT], Awaitable[ResponseT]]


class SyncMiddleware(Protocol[RequestT, ResponseT]):
    """Protocol for synchronous request/response middleware."""

    def __call__(
        self,
        request: RequestT,
        call_next: SyncHandler[RequestT, ResponseT],
    ) -> ResponseT: ...


class AsyncMiddleware(Protocol[RequestT, ResponseT]):
    """Protocol for asynchronous request/response middleware."""

    async def __call__(
        self,
        request: RequestT,
        call_next: AsyncHandler[RequestT, ResponseT],
    ) -> ResponseT: ...


def compose_sync[RequestT, ResponseT](
    handler: SyncHandler[RequestT, ResponseT],
    middleware: Iterable[SyncMiddleware[RequestT, ResponseT]],
) -> SyncHandler[RequestT, ResponseT]:
    """Wrap a synchronous handler in middleware declaration order."""
    composed = handler
    for layer in reversed(tuple(middleware)):
        call_next = composed

        def composed(
            request: RequestT,
            *,
            _layer: SyncMiddleware[RequestT, ResponseT] = layer,
            _next: SyncHandler[RequestT, ResponseT] = call_next,
        ) -> ResponseT:
            return _layer(request, _next)

    return composed


def compose_async[RequestT, ResponseT](
    handler: AsyncHandler[RequestT, ResponseT],
    middleware: Iterable[AsyncMiddleware[RequestT, ResponseT]],
) -> AsyncHandler[RequestT, ResponseT]:
    """Wrap an asynchronous handler in middleware declaration order."""
    composed = handler
    for layer in reversed(tuple(middleware)):
        call_next = composed

        async def composed(
            request: RequestT,
            *,
            _layer: AsyncMiddleware[RequestT, ResponseT] = layer,
            _next: AsyncHandler[RequestT, ResponseT] = call_next,
        ) -> ResponseT:
            return await _layer(request, _next)

    return composed


__all__ = [
    "AsyncHandler",
    "AsyncMiddleware",
    "SyncHandler",
    "SyncMiddleware",
    "compose_async",
    "compose_sync",
]
