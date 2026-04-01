"""pyfetcher - Advanced web fetching and scraping toolkit.

Purpose:
    Provide a reusable, transport-agnostic toolkit for HTTP fetching, web
    scraping, realistic browser header generation, and content extraction.
    Supports multiple backends (httpx, aiohttp), per-domain rate limiting,
    retry with exponential backoff, CLI and TUI interfaces, and comprehensive
    scraping utilities.

Design:
    - ``contracts`` defines validated request/response/policy models.
    - ``headers`` provides realistic browser header generation with full
      profile support (Chrome, Firefox, Safari, Edge across platforms).
    - ``retry`` adapts policy models to :mod:`tenacity`.
    - ``ratelimit`` provides per-domain and global rate limiting.
    - ``transports`` encapsulate concrete backend implementations.
    - ``fetch`` exposes the ergonomic function and service APIs.
    - ``scrape`` provides CSS selector extraction, link harvesting, form
      parsing, robots.txt support, sitemap parsing, and content extraction.
    - ``metadata`` parses page metadata after fetch.
    - ``download`` provides file-oriented helpers built on streaming.
    - ``cli`` provides a command-line interface.
    - ``tui`` provides an interactive terminal UI.

Public API:
    - :class:`~pyfetcher.contracts.url.URL`
    - :class:`~pyfetcher.contracts.request.FetchRequest`
    - :class:`~pyfetcher.contracts.response.FetchResponse`
    - :class:`~pyfetcher.contracts.policy.RetryPolicy`
    - :class:`~pyfetcher.contracts.policy.TimeoutPolicy`
    - :class:`~pyfetcher.contracts.policy.PoolPolicy`
    - :class:`~pyfetcher.contracts.policy.StreamPolicy`
    - :class:`~pyfetcher.fetch.service.FetchService`
    - :func:`~pyfetcher.fetch.functions.fetch`
    - :func:`~pyfetcher.fetch.functions.afetch`
    - :func:`~pyfetcher.fetch.functions.afetch_many`
    - :func:`~pyfetcher.fetch.functions.astream`
    - :class:`~pyfetcher.headers.browser.BrowserHeaderProvider`
    - :class:`~pyfetcher.headers.rotating.RotatingHeaderProvider`
    - :func:`~pyfetcher.headers.ua.random_user_agent`
    - :class:`~pyfetcher.ratelimit.limiter.DomainRateLimiter`
    - :class:`~pyfetcher.ratelimit.limiter.RateLimitPolicy`

Examples:
    ::

        >>> from pyfetcher import FetchRequest
        >>> request = FetchRequest(url="https://example.com")
        >>> request.method
        'GET'
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

try:
    from pyfetcher.fetch.functions import (
        afetch,  # noqa: F401
        afetch_many,  # noqa: F401
        astream,  # noqa: F401
        fetch,  # noqa: F401
    )
    from pyfetcher.fetch.service import FetchService  # noqa: F401
except Exception:  # pragma: no cover - optional dependency guard  # nosec B110
    pass
else:
    __all__.extend(
        [
            "FetchService",
            "afetch",
            "afetch_many",
            "astream",
            "fetch",
        ]
    )

try:
    from pyfetcher.headers.browser import BrowserHeaderProvider  # noqa: F401
    from pyfetcher.headers.rotating import RotatingHeaderProvider  # noqa: F401
    from pyfetcher.headers.ua import random_user_agent  # noqa: F401
except Exception:  # pragma: no cover  # nosec B110
    pass
else:
    __all__.extend(
        [
            "BrowserHeaderProvider",
            "RotatingHeaderProvider",
            "random_user_agent",
        ]
    )

try:
    from pyfetcher.ratelimit.limiter import (
        DomainRateLimiter,  # noqa: F401
        RateLimitPolicy,  # noqa: F401
    )
except Exception:  # pragma: no cover  # nosec B110
    pass
else:
    __all__.extend(["DomainRateLimiter", "RateLimitPolicy"])
