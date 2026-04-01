Pipeline
========

pyfetcher includes an event-driven pipeline that connects three stages:

1. **Crawl** -- Discover URLs, fetch pages, store in Postgres
2. **Scrape** -- Extract content, metadata, and media references
3. **Download** -- Acquire binary assets via yt-dlp, gallery-dl, or HTTP

Architecture
------------

.. code-block:: text

   Seeds / RSS / Sitemap
        |
   [Crawl Stage] --NOTIFY--> [Scrape Stage] --NOTIFY--> [Download Stage]
        |                          |                           |
        v                          v                           v
   pages table              pages (enriched)            media_assets table
   + new crawl jobs         + download jobs             + MinIO objects

Each stage:

- Claims jobs from Postgres using ``SELECT FOR UPDATE SKIP LOCKED``
- Processes them with configurable concurrency
- Writes results and emits ``NOTIFY`` for the next stage

Quick Start
-----------

.. code-block:: bash

   # Start infrastructure
   make infra-up
   make migrate

   # Run the pipeline
   make pipeline

Programmatic Usage
------------------

.. code-block:: python

   from pyfetcher.pipeline.runner import PipelineRunner
   from pyfetcher.config import PyfetcherConfig

   config = PyfetcherConfig(
       crawl_concurrency=10,
       scrape_concurrency=20,
       download_concurrency=5,
   )
   runner = PipelineRunner(config)
   await runner.start()

Seeding URLs
------------

.. code-block:: python

   from pyfetcher.crawler.frontier import Frontier
   from pyfetcher.db.engine import build_async_engine, build_session_factory

   engine = build_async_engine()
   session_factory = build_session_factory(engine)

   async with session_factory() as session:
       frontier = Frontier()
       await frontier.add_urls(session, [
           "https://example.com",
           "https://example.com/blog",
       ])
       await session.commit()

Custom Spider
-------------

.. code-block:: python

   from pyfetcher.crawler.spider import Spider, SpiderResult
   from pyfetcher.contracts.response import FetchResponse
   from pyfetcher.scrape.links import extract_links

   spider = Spider(name="my-spider")

   @spider.router.default
   async def handle_page(url: str, response: FetchResponse) -> SpiderResult:
       links = extract_links(response.text or "", base_url=url)
       return SpiderResult(
           discovered_urls=[l.url for l in links if not l.is_external],
           items=[{"url": url, "title": "..."}],
       )
