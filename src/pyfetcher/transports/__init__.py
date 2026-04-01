"""Transport adapters for :mod:`pyfetcher`.

Purpose:
    Provide pluggable HTTP backend implementations that conform to the
    :class:`SyncTransport` and :class:`AsyncTransport` protocols.

Public API:
    - :class:`~pyfetcher.transports.base.AsyncTransport`
    - :class:`~pyfetcher.transports.base.SyncTransport`
    - :class:`~pyfetcher.transports.httpx.HttpxTransport`
    - :class:`~pyfetcher.transports.aiohttp.AiohttpTransport`
    - :class:`~pyfetcher.transports.curl_cffi.CurlCffiTransport` *(optional)*
    - :class:`~pyfetcher.transports.cloudscraper.CloudscraperTransport` *(optional)*
"""

from __future__ import annotations

from pyfetcher.transports.aiohttp import AiohttpTransport
from pyfetcher.transports.base import AsyncTransport, SyncTransport
from pyfetcher.transports.httpx import HttpxTransport

__all__: list[str] = [
    "AiohttpTransport",
    "AsyncTransport",
    "HttpxTransport",
    "SyncTransport",
]

try:
    from pyfetcher.transports.curl_cffi import CurlCffiTransport  # noqa: F401
except Exception:  # pragma: no cover - optional dependency guard  # noqa: S110  # nosec B110
    pass  # nosec B110
else:
    __all__.append("CurlCffiTransport")

try:
    from pyfetcher.transports.cloudscraper import CloudscraperTransport  # noqa: F401
except Exception:  # pragma: no cover - optional dependency guard  # noqa: S110  # nosec B110
    pass  # nosec B110
else:
    __all__.append("CloudscraperTransport")
