"""Rate limiting examples for pyfetcher.

Demonstrates per-domain and global rate limiting.
"""

from __future__ import annotations

import time

from pyfetcher.ratelimit.limiter import DomainRateLimiter, RateLimitPolicy


def basic_rate_limiting() -> None:
    """Basic per-domain rate limiting."""
    print("=== Basic Rate Limiting ===")
    limiter = DomainRateLimiter(default_policy=RateLimitPolicy(requests_per_second=5.0, burst=2))

    for i in range(5):
        start = time.monotonic()
        wait = limiter.acquire("https://example.com/page")
        elapsed = time.monotonic() - start
        print(f"  Request {i+1}: waited {elapsed:.3f}s (reported: {wait:.3f}s)")


def per_domain_policies() -> None:
    """Different rate limits per domain."""
    print("\n=== Per-Domain Policies ===")
    limiter = DomainRateLimiter(
        default_policy=RateLimitPolicy(requests_per_second=10.0, burst=5),
        domain_policies={
            "api.slow.com": RateLimitPolicy(requests_per_second=1.0, burst=1),
            "api.fast.com": RateLimitPolicy(requests_per_second=100.0, burst=50),
        },
    )

    print("  Fast domain (100 req/s):")
    for i in range(3):
        wait = limiter.acquire("https://api.fast.com/data")
        print(f"    Request {i+1}: wait={wait:.4f}s")

    print("  Slow domain (1 req/s):")
    for i in range(3):
        start = time.monotonic()
        limiter.acquire("https://api.slow.com/data")
        print(f"    Request {i+1}: took {time.monotonic() - start:.3f}s")


def with_fetch_service() -> None:
    """Rate limiting integrated with FetchService."""
    print("\n=== With FetchService ===")
    print("  Configure like this:")
    print("    from pyfetcher.fetch.service import FetchService")
    print("    from pyfetcher.ratelimit.limiter import DomainRateLimiter, RateLimitPolicy")
    print()
    print("    limiter = DomainRateLimiter(")
    print("        default_policy=RateLimitPolicy(requests_per_second=2.0, burst=5),")
    print("        domain_policies={")
    print('            "api.example.com": RateLimitPolicy(requests_per_second=0.5),')
    print("        },")
    print("    )")
    print("    service = FetchService(rate_limiter=limiter)")
    print("    response = service.fetch(FetchRequest(url='https://api.example.com/data'))")


if __name__ == "__main__":
    basic_rate_limiting()
    per_domain_policies()
    with_fetch_service()
