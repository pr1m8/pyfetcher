"""Async and batch fetching examples for pyfetcher.

Demonstrates concurrent fetching with bounded concurrency.
"""

from __future__ import annotations

import asyncio

from pyfetcher import FetchRequest
from pyfetcher.fetch.batch import build_batch_request
from pyfetcher.fetch.functions import afetch, afetch_many


async def batch_fetch_example() -> None:
    """Fetch multiple URLs concurrently with bounded concurrency."""
    urls = [
        "https://httpbin.org/get",
        "https://httpbin.org/ip",
        "https://httpbin.org/user-agent",
        "https://httpbin.org/headers",
    ]

    requests = [FetchRequest(url=url) for url in urls]
    batch = build_batch_request(requests, concurrency=2)

    print("=== Batch Fetch (concurrency=2) ===")
    result = await afetch_many(batch)

    for item in result.items:
        if item.ok:
            print(f"  OK  {item.request_url} -> {item.response.status_code}")  # type: ignore[union-attr]
        else:
            print(f"  ERR {item.request_url} -> {item.error}")


async def parallel_fetch_example() -> None:
    """Fetch URLs in parallel using asyncio.gather."""
    print("\n=== Parallel Fetch ===")
    urls = ["https://httpbin.org/delay/1", "https://httpbin.org/delay/1"]

    import time

    start = time.monotonic()
    responses = await asyncio.gather(*(afetch(url) for url in urls))
    elapsed = time.monotonic() - start

    for resp in responses:
        print(f"  {resp.final_url} -> {resp.status_code} ({resp.elapsed_ms:.0f}ms)")
    print(f"  Total wall time: {elapsed:.2f}s (should be ~1s, not ~2s)")


if __name__ == "__main__":
    asyncio.run(batch_fetch_example())
    asyncio.run(parallel_fetch_example())
