---
name: http-fetch
description: Build, integrate, debug, or document fetchkit HTTP workflows using FetchClient, AsyncFetchClient, FetchService, HTTP/2, proxies, pooling, retries, streaming uploads/downloads, middleware, FastAPI injection, or large sync/async URL iterables. Use for ordinary HTTP acquisition; route Scrapy engine work and specialized media/gallery acquisition to their focused skills.
---

# fetchkit HTTP Fetch

Use the public ``pyfetcher`` API and keep one client alive for repeated work.

## Choose the surface

- Use ``fetch`` or ``afetch`` for short scripts.
- Use ``FetchClient`` for repeated synchronous requests.
- Use ``AsyncFetchClient`` for async applications, workers, and FastAPI.
- Use ``FetchService`` for custom transports or middleware.
- Use ``AcquisitionService`` only when provider selection or downloader-native
  behavior is required.

Accept supported foreign URL values at application boundaries, then normalize
them through ``URL.from_value`` or a local ``URLAdapterRegistry``. Apply
``URLRule`` values before request construction when reusable canonicalization
or routing policy is needed. Use ``$url-workflows`` for adapter and pattern
design rather than adding URL-library branches to a client.

## Build a pooled client

```python
from pyfetcher import AsyncFetchClient, PoolPolicy, RetryPolicy, TimeoutPolicy

async with AsyncFetchClient(
    base_url="https://api.example.com/v1/",
    http2=True,
    proxy=None,
    pool=PoolPolicy(max_connections=100, concurrency=20),
    timeout=TimeoutPolicy(total_seconds=30),
    retry=RetryPolicy(attempts=4),
) as client:
    response = await client.get("items", params={"limit": 20})
```

Treat HTTP/2 as negotiated; inspect ``response.http_version``. Keep proxy,
TLS, HTTP/2, and pool configurations stable to maximize pool reuse.

## Stream safely

- Consume downloads with ``iter_bytes`` or ``iter_text``.
- Set ``StreamPolicy(max_bytes=...)`` when input size is not trusted.
- Pass ``content`` for one-shot bytes, text, sync iterables, or async iterables.
- Pass ``content_factory`` for retryable generator uploads.
- Never combine ``data``, ``json_data``, ``content``, and ``content_factory``.

Use ``AsyncFetchClient.imap`` for large sync or async URL sources. Choose
``ordered=False`` for completion order and lower head-of-line blocking.

Treat a streamed response body as single-consumer unless it is explicitly
buffered. Use ``ByteStream`` when downstream consumers need a bounded,
replay-aware sync/async content abstraction; use ``$media-artifacts`` when the
bytes become durable media or blob artifacts.

## Integrate middleware

Pass ``sync_middleware`` or ``async_middleware`` to ``FetchService``. A layer
receives ``(request, call_next)`` and may transform the immutable request,
observe the response, short-circuit, or translate failures. Keep transport
selection and lifecycle ownership in the service.

## Integrate FastAPI

Create one ``AsyncFetchClient`` in the application lifespan, store it on
``app.state``, and inject the same instance into routes. Do not construct a
client per request.

## Validate changes

Run focused tests first, then:

```bash
pdm run ruff format --check src/ tests/ examples/
pdm run ruff check src/ tests/ examples/
pdm run pytest tests/ -q
LC_ALL=C pdm run sphinx-build -E -W --keep-going -b html docs docs/_build/html
```

Keep live HTTP tests opt-in. Use fake transports for unit tests.

## Respect capability boundaries

- Use ``$scrapy-crawl`` for Scrapy engine, scheduler, middleware, or reactor work.
- Use ``$yt-dlp-acquire`` for extractor formats, playlists, or postprocessing.
- Use ``$gallery-dl-acquire`` for gallery extractors, ranges, and archives.
- Use ``$typed-page-extraction`` after a response becomes a selectable document.
- Use ``$durable-web-jobs`` when a fetch becomes a queued or replayable job.
