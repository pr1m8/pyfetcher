"""Rate limiter implementation for :mod:`pyfetcher`.

Purpose:
    Provide configurable per-domain and global rate limiting using
    ``pyrate_limiter``. The :class:`DomainRateLimiter` maintains separate
    rate limit buckets per domain while optionally enforcing a global
    request rate.

Design:
    - Rate limits are defined via :class:`RateLimitPolicy` which specifies
      requests-per-second and an optional burst allowance.
    - The limiter uses an in-memory bucket store by default.
    - Both synchronous and asynchronous ``acquire`` methods are provided.
    - Domain extraction is performed automatically from URLs.

Examples:
    ::

        >>> policy = RateLimitPolicy(requests_per_second=10.0)
        >>> limiter = DomainRateLimiter(default_policy=policy)
        >>> limiter.acquire("https://example.com/page1")
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from threading import Lock
from urllib.parse import urlparse


@dataclass(frozen=True, slots=True)
class RateLimitPolicy:
    """Rate limiting policy configuration.

    Defines the rate at which requests may be made, with an optional burst
    allowance for short traffic spikes.

    Args:
        requests_per_second: Maximum sustained request rate. Set to ``0``
            to disable rate limiting.
        burst: Maximum number of requests that can be made in a burst
            before throttling kicks in. Defaults to ``1`` (no burst).
        per_domain: Whether this limit applies per-domain (``True``) or
            globally (``False``).

    Examples:
        ::

            >>> policy = RateLimitPolicy(requests_per_second=5.0, burst=10)
            >>> policy.interval
            0.2
    """

    requests_per_second: float = 10.0
    burst: int = 1
    per_domain: bool = True

    @property
    def interval(self) -> float:
        """Minimum interval between requests in seconds.

        Returns:
            The reciprocal of ``requests_per_second``, or ``0.0`` if
            rate limiting is disabled.

        Examples:
            ::

                >>> RateLimitPolicy(requests_per_second=2.0).interval
                0.5
        """
        if self.requests_per_second <= 0:
            return 0.0
        return 1.0 / self.requests_per_second


def _extract_domain(url: str) -> str:
    """Extract the domain (netloc) from a URL.

    Args:
        url: The URL to extract the domain from.

    Returns:
        The domain string (e.g. ``'example.com'``).

    Examples:
        ::

            >>> _extract_domain("https://example.com/path")
            'example.com'
    """
    return urlparse(url).netloc or "unknown"


@dataclass
class _TokenBucket:
    """Simple token bucket for rate limiting.

    Implements a token bucket algorithm where tokens are added at a fixed
    rate up to a maximum burst capacity. Each request consumes one token.

    Args:
        rate: Tokens added per second.
        burst: Maximum token capacity.
    """

    rate: float
    burst: int
    tokens: float = field(init=False)
    last_refill: float = field(init=False)
    lock: Lock = field(default_factory=Lock, repr=False)

    def __post_init__(self) -> None:
        self.tokens = float(self.burst)
        self.last_refill = time.monotonic()

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
        self.last_refill = now

    def acquire(self) -> float:
        """Acquire a token, blocking if necessary.

        Returns:
            The time in seconds spent waiting for a token (``0.0`` if
            a token was immediately available).
        """
        with self.lock:
            self._refill()
            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return 0.0
            wait_time = (1.0 - self.tokens) / self.rate
        time.sleep(wait_time)
        with self.lock:
            self._refill()
            self.tokens -= 1.0
        return wait_time

    async def aacquire(self) -> float:
        """Acquire a token asynchronously, yielding control while waiting.

        Returns:
            The time in seconds spent waiting for a token.
        """
        self._refill()
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return 0.0
        wait_time = (1.0 - self.tokens) / self.rate
        await asyncio.sleep(wait_time)
        self._refill()
        self.tokens -= 1.0
        return wait_time


class DomainRateLimiter:
    """Per-domain rate limiter with optional global rate limiting.

    Maintains separate token buckets for each domain encountered,
    throttling requests to stay within the configured rate limits.
    An optional global limiter can enforce an overall request rate
    across all domains.

    Args:
        default_policy: The default rate limit policy for domains without
            a specific override.
        domain_policies: Optional mapping of domain names to specific
            :class:`RateLimitPolicy` instances.
        global_policy: Optional global rate limit applied across all
            domains in addition to per-domain limits.

    Examples:
        ::

            >>> limiter = DomainRateLimiter(
            ...     default_policy=RateLimitPolicy(requests_per_second=5.0),
            ...     domain_policies={"api.example.com": RateLimitPolicy(requests_per_second=1.0)},
            ... )
            >>> limiter.acquire("https://api.example.com/data")
    """

    def __init__(
        self,
        *,
        default_policy: RateLimitPolicy | None = None,
        domain_policies: dict[str, RateLimitPolicy] | None = None,
        global_policy: RateLimitPolicy | None = None,
    ) -> None:
        self._default_policy = default_policy or RateLimitPolicy()
        self._domain_policies = dict(domain_policies or {})
        self._global_policy = global_policy
        self._buckets: dict[str, _TokenBucket] = {}
        self._global_bucket: _TokenBucket | None = None
        self._lock = Lock()

        if self._global_policy and self._global_policy.requests_per_second > 0:
            self._global_bucket = _TokenBucket(
                rate=self._global_policy.requests_per_second,
                burst=self._global_policy.burst,
            )

    def _get_bucket(self, domain: str) -> _TokenBucket:
        """Get or create the token bucket for a domain.

        Args:
            domain: The domain name.

        Returns:
            The token bucket for the domain.
        """
        if domain not in self._buckets:
            with self._lock:
                if domain not in self._buckets:
                    policy = self._domain_policies.get(domain, self._default_policy)
                    self._buckets[domain] = _TokenBucket(
                        rate=policy.requests_per_second,
                        burst=policy.burst,
                    )
        return self._buckets[domain]

    def acquire(self, url: str) -> float:
        """Acquire permission to make a request, blocking if rate-limited.

        Checks both the per-domain rate limit and the optional global rate
        limit. Blocks the calling thread until a token is available.

        Args:
            url: The target URL (domain is extracted automatically).

        Returns:
            Total time in seconds spent waiting for rate limit tokens.

        Examples:
            ::

                >>> limiter = DomainRateLimiter()
                >>> wait = limiter.acquire("https://example.com/page")
        """
        domain = _extract_domain(url)
        bucket = self._get_bucket(domain)
        total_wait = 0.0

        policy = self._domain_policies.get(domain, self._default_policy)
        if policy.requests_per_second > 0:
            total_wait += bucket.acquire()

        if self._global_bucket:
            total_wait += self._global_bucket.acquire()

        return total_wait

    async def aacquire(self, url: str) -> float:
        """Acquire permission to make a request asynchronously.

        Checks both the per-domain rate limit and the optional global rate
        limit. Yields control while waiting for tokens.

        Args:
            url: The target URL (domain is extracted automatically).

        Returns:
            Total time in seconds spent waiting for rate limit tokens.

        Examples:
            ::

                >>> import asyncio
                >>> limiter = DomainRateLimiter()
                >>> # await limiter.aacquire("https://example.com/page")
        """
        domain = _extract_domain(url)
        bucket = self._get_bucket(domain)
        total_wait = 0.0

        policy = self._domain_policies.get(domain, self._default_policy)
        if policy.requests_per_second > 0:
            total_wait += await bucket.aacquire()

        if self._global_bucket:
            total_wait += await self._global_bucket.aacquire()

        return total_wait

    def reset(self, domain: str | None = None) -> None:
        """Reset rate limit state.

        Args:
            domain: If provided, only reset the bucket for this domain.
                If ``None``, reset all domain buckets.

        Examples:
            ::

                >>> limiter = DomainRateLimiter()
                >>> limiter.reset()
        """
        if domain:
            self._buckets.pop(domain, None)
        else:
            self._buckets.clear()
