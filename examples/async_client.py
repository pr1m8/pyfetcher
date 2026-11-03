"""Example: reuse an async client for pooling, streaming, and lazy mapping.

Run with:
    python examples/async_client.py
"""

from __future__ import annotations

import asyncio

from pyfetcher import AsyncFetchClient, PoolPolicy, StreamPolicy


async def urls():
    """Yield work lazily; this could also read from a queue or database."""
    for path in ("get", "headers", "user-agent"):
        yield f"https://httpbin.org/{path}"


async def main() -> None:
    """Reuse one pool across ordinary, streamed, and mapped requests."""
    async with AsyncFetchClient(
        http2=True,
        pool=PoolPolicy(max_connections=20, concurrency=3),
        stream=StreamPolicy(chunk_size=16 * 1024),
    ) as client:
        response = await client.get("https://httpbin.org/get")
        print(response.status_code, response.http_version)

        streamed = 0
        async for chunk in client.iter_bytes("GET", "https://httpbin.org/bytes/1024"):
            streamed += len(chunk)
        print(f"streamed {streamed} bytes")

        async for item in client.imap(urls(), ordered=False):
            print(item.final_url, item.status_code)


if __name__ == "__main__":
    asyncio.run(main())
