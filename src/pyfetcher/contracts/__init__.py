"""Central contracts for :mod:`pyfetcher`.

Purpose:
    Provide one stable layer of Pydantic request/response/value models that can
    be reused by transports, fetch services, metadata parsers, scrapers, and
    command-line interfaces.

Design:
    - URL modeling remains separate from transport code.
    - Policies are explicit and serializable.
    - Request/response contracts are backend-agnostic.

Public API:
    - :class:`~pyfetcher.contracts.url.URL`
    - :class:`~pyfetcher.contracts.request.FetchRequest`
    - :class:`~pyfetcher.contracts.request.BatchFetchRequest`
    - :class:`~pyfetcher.contracts.response.FetchResponse`
    - :class:`~pyfetcher.contracts.response.BatchFetchResponse`
    - :class:`~pyfetcher.contracts.response.StreamChunk`
    - :class:`~pyfetcher.contracts.policy.RetryPolicy`
    - :class:`~pyfetcher.contracts.policy.TimeoutPolicy`
    - :class:`~pyfetcher.contracts.policy.PoolPolicy`
    - :class:`~pyfetcher.contracts.policy.StreamPolicy`
"""

from __future__ import annotations

from pyfetcher.contracts.policy import (
    PoolPolicy,
    RetryPolicy,
    StreamPolicy,
    TimeoutPolicy,
)
from pyfetcher.contracts.request import BatchFetchRequest, FetchRequest
from pyfetcher.contracts.response import BatchFetchResponse, FetchResponse, StreamChunk
from pyfetcher.contracts.url import URL

__all__ = [
    "BatchFetchRequest",
    "BatchFetchResponse",
    "FetchRequest",
    "FetchResponse",
    "PoolPolicy",
    "RetryPolicy",
    "StreamChunk",
    "StreamPolicy",
    "TimeoutPolicy",
    "URL",
]
