"""Unit tests for pyfetcher.ratelimit."""

from __future__ import annotations

import time

import pytest

from pyfetcher.ratelimit.limiter import (
    DomainRateLimiter,
    RateLimitPolicy,
    _extract_domain,
    _TokenBucket,
)


class TestRateLimitPolicy:
    def test_defaults(self) -> None:
        policy = RateLimitPolicy()
        assert policy.requests_per_second == 10.0
        assert policy.burst == 1
        assert policy.per_domain is True

    def test_interval(self) -> None:
        policy = RateLimitPolicy(requests_per_second=5.0)
        assert policy.interval == 0.2

    def test_disabled(self) -> None:
        policy = RateLimitPolicy(requests_per_second=0)
        assert policy.interval == 0.0


class TestExtractDomain:
    def test_basic(self) -> None:
        assert _extract_domain("https://example.com/path") == "example.com"

    def test_with_port(self) -> None:
        assert _extract_domain("https://example.com:8080/path") == "example.com:8080"

    def test_no_netloc(self) -> None:
        assert _extract_domain("/path") == "unknown"


class TestTokenBucket:
    def test_immediate_acquire(self) -> None:
        bucket = _TokenBucket(rate=10.0, burst=5)
        wait = bucket.acquire()
        assert wait == 0.0

    def test_burst_exhaustion(self) -> None:
        bucket = _TokenBucket(rate=100.0, burst=2)
        bucket.acquire()
        bucket.acquire()
        # Third acquire should wait briefly
        start = time.monotonic()
        bucket.acquire()
        elapsed = time.monotonic() - start
        assert elapsed < 0.1  # Should be very short with high rate


class TestDomainRateLimiter:
    def test_basic_acquire(self) -> None:
        limiter = DomainRateLimiter(
            default_policy=RateLimitPolicy(requests_per_second=100.0, burst=10)
        )
        wait = limiter.acquire("https://example.com/page1")
        assert wait == 0.0

    def test_separate_domains(self) -> None:
        limiter = DomainRateLimiter(
            default_policy=RateLimitPolicy(requests_per_second=100.0, burst=2)
        )
        limiter.acquire("https://a.com/1")
        limiter.acquire("https://b.com/1")
        # Each domain has its own bucket
        wait_a = limiter.acquire("https://a.com/2")
        wait_b = limiter.acquire("https://b.com/2")
        assert wait_a == 0.0
        assert wait_b == 0.0

    def test_domain_specific_policy(self) -> None:
        limiter = DomainRateLimiter(
            default_policy=RateLimitPolicy(requests_per_second=100.0, burst=10),
            domain_policies={
                "slow.com": RateLimitPolicy(requests_per_second=1.0, burst=1),
            },
        )
        limiter.acquire("https://slow.com/page")
        # Second request to slow.com should be rate limited
        start = time.monotonic()
        limiter.acquire("https://slow.com/page2")
        elapsed = time.monotonic() - start
        assert elapsed >= 0.5  # At 1 req/s with burst 1, should wait ~1s

    def test_reset(self) -> None:
        limiter = DomainRateLimiter()
        limiter.acquire("https://example.com/1")
        limiter.reset()
        assert len(limiter._buckets) == 0

    def test_reset_specific_domain(self) -> None:
        limiter = DomainRateLimiter()
        limiter.acquire("https://a.com/1")
        limiter.acquire("https://b.com/1")
        limiter.reset("a.com")
        assert "a.com" not in limiter._buckets
        assert "b.com" in limiter._buckets


@pytest.mark.asyncio
class TestDomainRateLimiterAsync:
    async def test_async_acquire(self) -> None:
        limiter = DomainRateLimiter(
            default_policy=RateLimitPolicy(requests_per_second=100.0, burst=10)
        )
        wait = await limiter.aacquire("https://example.com/page")
        assert wait == 0.0
