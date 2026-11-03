---
name: scrapy-crawl
description: Build, integrate, debug, or document fetchkit and Scrapy crawling through ScrapyEngineTransport, request/response conversion, PyfetcherDownloaderMiddleware, downloader settings, retries, proxies, crawler-engine lifecycle, Deferred compatibility, spiders, scheduling, or item pipelines. Use when Scrapy owns or participates in execution; do not model Scrapy as a media acquisition provider.
---

# fetchkit Scrapy Crawl

Keep Scrapy optional and attach to an existing crawler lifecycle.

## Install and select a direction

```bash
python -m pip install 'fetchkit[scrapy]'
```

Choose one bridge direction:

1. **fetchkit through Scrapy**: register ``ScrapyEngineTransport`` on a
   ``FetchService`` attached to an already-running engine.
2. **Scrapy through fetchkit**: enable ``PyfetcherDownloaderMiddleware`` and set
   ``request.meta['pyfetcher'] = True`` only on opted-in requests.
3. **Contract conversion only**: use ``to_scrapy_request``,
   ``from_scrapy_request``, ``from_scrapy_response``, or
   ``to_scrapy_response``.

## Attach an existing engine

```python
from pyfetcher import FetchRequest
from pyfetcher.fetch.service import FetchService
from pyfetcher.integrations.scrapy import ScrapyEngineTransport

transport = ScrapyEngineTransport(crawler.engine)
service = FetchService(async_transports={"scrapy": transport})
response = await service.afetch(
    FetchRequest(url="https://example.com", backend="scrapy")
)
```

Prefer Scrapy's current ``download_async(request)`` engine API. The bridge uses
``download(request)`` plus ``deferred_to_future`` only as a compatibility
fallback. Require an asyncio reactor for that fallback.

## Map policy deliberately

The conversion layer maps timeout, retries, redirects, proxy, headers, body,
priority, ``dont_filter``, and download size. Keep additional Scrapy settings
inside ``ScrapyRequestOptions.meta`` rather than adding them to ``FetchRequest``.

Scrapy request bodies must be buffered bytes or text. Response streaming is not
available through ``ScrapyEngineTransport``; select HTTPX or aiohttp when
streaming is required.

Convert a completed response to ``PageDocument`` when extraction should be
shared with non-Scrapy callers. Express reusable CSS/XPath work with typed
selector rules and route those changes through ``$typed-page-extraction``.
Use the WebPoet or scrapy-poet integration for injectable page objects; keep
engine scheduling and page extraction as separate layers.

## Preserve lifecycle ownership

Do not install, start, stop, or replace a reactor inside the transport. The host
CrawlerRunner/CrawlerProcess owns it. ``ScrapyEngineTransport.aclose`` therefore
does not close the engine.

## Test and validate

Use duck-typed fake requests, responses, and engines for unit tests. Keep live
crawls opt-in.

```bash
pdm run pytest tests/test_scrapy_integration.py -q
pdm run pytest tests/test_webpoet_integration.py tests/test_documents.py -q
pdm run ruff check src/ tests/ examples/
```

Use ``$http-fetch`` when no Scrapy scheduler, middleware, or engine behavior is
needed. Use ``$url-workflows`` for canonical URL and typed pattern behavior.
