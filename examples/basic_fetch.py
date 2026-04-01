"""Basic fetch examples for pyfetcher.

Demonstrates simple synchronous and asynchronous fetching.
"""

from __future__ import annotations

import asyncio

from pyfetcher import FetchRequest, fetch
from pyfetcher.fetch.functions import afetch


def sync_fetch_example() -> None:
    """Fetch a URL synchronously."""
    response = fetch("https://httpbin.org/get")
    print(f"Status: {response.status_code}")
    print(f"URL: {response.final_url}")
    print(f"Elapsed: {response.elapsed_ms:.1f}ms")
    print(f"OK: {response.ok}")
    print(f"Body preview: {(response.text or '')[:200]}")


async def async_fetch_example() -> None:
    """Fetch a URL asynchronously."""
    response = await afetch("https://httpbin.org/get")
    print(f"[async] Status: {response.status_code}")
    print(f"[async] Elapsed: {response.elapsed_ms:.1f}ms")


def fetch_with_options() -> None:
    """Fetch with custom method, headers, and params."""
    request = FetchRequest(
        url="https://httpbin.org/post",
        method="POST",
        headers={"x-custom-header": "my-value"},
        json_data={"key": "value", "items": [1, 2, 3]},
    )
    response = fetch(request)
    print(f"POST Status: {response.status_code}")
    print(f"Body: {(response.text or '')[:300]}")


if __name__ == "__main__":
    print("=== Sync Fetch ===")
    sync_fetch_example()
    print("\n=== Async Fetch ===")
    asyncio.run(async_fetch_example())
    print("\n=== Fetch with Options ===")
    fetch_with_options()
