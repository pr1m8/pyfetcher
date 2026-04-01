"""Rate limiting for :mod:`pyfetcher`.

Purpose:
    Provide per-domain and global rate limiting for HTTP requests using
    the ``pyrate_limiter`` library. Rate limiters integrate with the fetch
    service to throttle requests automatically.

Public API:
    - :class:`~pyfetcher.ratelimit.limiter.RateLimitPolicy`
    - :class:`~pyfetcher.ratelimit.limiter.DomainRateLimiter`
"""

from __future__ import annotations

__all__: list[str] = []

try:
    from pyfetcher.ratelimit.limiter import DomainRateLimiter  # noqa: F401
    from pyfetcher.ratelimit.limiter import RateLimitPolicy  # noqa: F401
except Exception:  # pragma: no cover - optional dependency guard  # noqa: S110  # nosec B110
    pass  # nosec B110
else:
    __all__.extend(["DomainRateLimiter", "RateLimitPolicy"])
