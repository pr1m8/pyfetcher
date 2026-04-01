"""Transport adapters for :mod:`pyfetcher`.

Purpose:
    Provide pluggable HTTP backend implementations that conform to the
    :class:`SyncTransport` and :class:`AsyncTransport` protocols.

Public API:
    - :class:`~pyfetcher.transports.base.AsyncTransport`
    - :class:`~pyfetcher.transports.base.SyncTransport`
    - :class:`~pyfetcher.transports.httpx.HttpxTransport`
    - :class:`~pyfetcher.transports.aiohttp.AiohttpTransport`
"""

from __future__ import annotations

from pyfetcher.transports.aiohttp import AiohttpTransport
from pyfetcher.transports.base import AsyncTransport, SyncTransport
from pyfetcher.transports.httpx import HttpxTransport

__all__ = [
    "AiohttpTransport",
    "AsyncTransport",
    "HttpxTransport",
    "SyncTransport",
]
