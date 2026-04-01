"""Retry helpers for :mod:`pyfetcher`.

Purpose:
    Adapt repository retry policy models to :mod:`tenacity` for both
    synchronous and asynchronous execution.

Public API:
    - :class:`~pyfetcher.retry.tenacity.RetryableStatusCodeError`
    - :func:`~pyfetcher.retry.tenacity.build_retrying`
    - :func:`~pyfetcher.retry.tenacity.build_async_retrying`
"""

from __future__ import annotations

__all__: list[str] = []

try:
    from pyfetcher.retry.tenacity import (
        RetryableStatusCodeError,  # noqa: F401
        build_async_retrying,  # noqa: F401
        build_retrying,  # noqa: F401
    )
except Exception:  # pragma: no cover - optional dependency guard  # noqa: S110  # nosec B110
    pass  # nosec B110
else:
    __all__.extend(
        [
            "RetryableStatusCodeError",
            "build_async_retrying",
            "build_retrying",
        ]
    )
