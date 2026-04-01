"""Function-first fetch API for :mod:`pyfetcher`.

Purpose:
    Provide a small ergonomic surface for common fetch, batch, and stream
    operations without requiring callers to manage a service object directly.

Design:
    - Functions delegate to a module-level default service.
    - Request dictionaries are validated through Pydantic models.
    - Advanced callers can still instantiate
      :class:`~pyfetcher.fetch.service.FetchService` directly.

Examples:
    ::

        >>> request = FetchRequest(url="https://example.com")
        >>> request.method
        'GET'
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from functools import lru_cache

from pyfetcher.contracts.request import BatchFetchRequest, FetchRequest
from pyfetcher.contracts.response import BatchFetchResponse, FetchResponse, StreamChunk
from pyfetcher.fetch.service import FetchService


@lru_cache(maxsize=1)
def get_default_fetch_service() -> FetchService:
    """Return the module-level default fetch service (cached singleton).

    Returns:
        A cached :class:`~pyfetcher.fetch.service.FetchService` instance.

    Examples:
        ::

            >>> isinstance(get_default_fetch_service(), FetchService)
            True
    """
    return FetchService()


def fetch(url: str | FetchRequest, /, **kwargs: object) -> FetchResponse:
    """Fetch a URL synchronously using the default service.

    Convenience function that creates a :class:`FetchRequest` from the
    given URL string (or accepts a pre-built request) and delegates to
    the default :class:`FetchService`.

    Args:
        url: URL string or pre-built :class:`FetchRequest`.
        **kwargs: Additional request fields when ``url`` is a string.

    Returns:
        A normalized :class:`~pyfetcher.contracts.response.FetchResponse`.

    Raises:
        Exception: Any underlying fetch failure.

    Examples:
        ::

            >>> callable(fetch)
            True
    """
    request = url if isinstance(url, FetchRequest) else FetchRequest(url=url, **kwargs)
    return get_default_fetch_service().fetch(request)


async def afetch(url: str | FetchRequest, /, **kwargs: object) -> FetchResponse:
    """Fetch a URL asynchronously using the default service.

    Convenience function that creates a :class:`FetchRequest` from the
    given URL string (or accepts a pre-built request) and delegates to
    the default :class:`FetchService`.

    Args:
        url: URL string or pre-built :class:`FetchRequest`.
        **kwargs: Additional request fields when ``url`` is a string.

    Returns:
        A normalized :class:`~pyfetcher.contracts.response.FetchResponse`.

    Raises:
        Exception: Any underlying fetch failure.

    Examples:
        ::

            >>> callable(afetch)
            True
    """
    request = url if isinstance(url, FetchRequest) else FetchRequest(url=url, **kwargs)
    return await get_default_fetch_service().afetch(request)


async def afetch_many(
    requests: list[FetchRequest] | BatchFetchRequest,
    /,
    **kwargs: object,
) -> BatchFetchResponse:
    """Fetch many URLs asynchronously using the default service.

    Convenience function for batch fetching with bounded concurrency.

    Args:
        requests: A list of :class:`FetchRequest` objects or a pre-built
            :class:`BatchFetchRequest`.
        **kwargs: Additional batch fields when passing a plain request list.

    Returns:
        A :class:`~pyfetcher.contracts.response.BatchFetchResponse`
        preserving input order.

    Raises:
        Exception: Any service-level failure.

    Examples:
        ::

            >>> callable(afetch_many)
            True
    """
    batch = (
        requests
        if isinstance(requests, BatchFetchRequest)
        else BatchFetchRequest(requests=requests, **kwargs)
    )
    return await get_default_fetch_service().afetch_many(batch)


async def astream(url: str | FetchRequest, /, **kwargs: object) -> AsyncIterator[StreamChunk]:
    """Stream a URL asynchronously using the default service.

    Convenience function for streaming responses as chunks.

    Args:
        url: URL string or pre-built :class:`FetchRequest`.
        **kwargs: Additional request fields when ``url`` is a string.

    Yields:
        :class:`~pyfetcher.contracts.response.StreamChunk` objects.

    Raises:
        Exception: Any streaming failure.

    Examples:
        ::

            >>> callable(astream)
            True
    """
    request = url if isinstance(url, FetchRequest) else FetchRequest(url=url, **kwargs)
    async for chunk in get_default_fetch_service().astream(request):
        yield chunk
