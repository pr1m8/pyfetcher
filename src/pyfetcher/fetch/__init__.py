"""Fetch orchestration for :mod:`pyfetcher`.

Purpose:
    Compose header providers, retry policies, rate limiters, and transports
    into a single reusable service object with an ergonomic function-first API.

Public API:
    - :class:`~pyfetcher.fetch.service.FetchService`
    - :func:`~pyfetcher.fetch.functions.fetch`
    - :func:`~pyfetcher.fetch.functions.afetch`
    - :func:`~pyfetcher.fetch.functions.afetch_many`
    - :func:`~pyfetcher.fetch.functions.astream`
"""

from __future__ import annotations

__all__: list[str] = []

try:
    from pyfetcher.fetch.functions import afetch  # noqa: F401
    from pyfetcher.fetch.functions import afetch_many  # noqa: F401
    from pyfetcher.fetch.functions import astream  # noqa: F401
    from pyfetcher.fetch.functions import fetch  # noqa: F401
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
