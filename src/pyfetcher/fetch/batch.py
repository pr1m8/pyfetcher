"""Batch convenience helpers for :mod:`pyfetcher`.

Purpose:
    Provide lightweight wrappers for constructing batch fetch requests.

Examples:
    ::

        >>> callable(build_batch_request)
        True
"""

from __future__ import annotations

from pyfetcher.contracts.request import BatchFetchRequest, FetchRequest


def build_batch_request(
    requests: list[FetchRequest],
    *,
    concurrency: int | None = None,
) -> BatchFetchRequest:
    """Build a batch fetch request from a list of individual requests.

    Args:
        requests: Individual requests to execute concurrently.
        concurrency: Optional concurrency override limiting the number
            of simultaneous in-flight requests.

    Returns:
        A validated :class:`~pyfetcher.contracts.request.BatchFetchRequest`.

    Examples:
        ::

            >>> req = FetchRequest(url="https://example.com")
            >>> build_batch_request([req]).requests[0].url.host
            'example.com'
    """
    return BatchFetchRequest(requests=requests, concurrency=concurrency)
