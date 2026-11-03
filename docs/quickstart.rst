Quick Start
===========

fetchkit is the distribution name on PyPI; the Python package is imported as
``pyfetcher``. Python 3.13 or newer is required.

Installation
------------

Install the core HTTP, scraping, and header functionality:

.. code-block:: bash

   python -m pip install fetchkit

Quote extras in shell commands so brackets are not interpreted by the shell:

.. list-table:: Common extras
   :header-rows: 1
   :widths: 24 30 46

   * - Extra
     - Install
     - Purpose
   * - ``curl``
     - ``fetchkit[curl]``
     - curl_cffi TLS and browser impersonation
   * - ``cloudscraper``
     - ``fetchkit[cloudscraper]``
     - Synchronous Cloudflare-oriented backend
   * - ``mcp``
     - ``fetchkit[mcp]``
     - MCP server for agent integrations
   * - ``langchain``
     - ``fetchkit[langchain]``
     - LangChain MCP client adapters
   * - ``downloaders``
     - ``fetchkit[downloaders]``
     - yt-dlp and gallery-dl integrations
   * - ``scrapy``
     - ``fetchkit[scrapy]``
     - Optional Scrapy crawler-engine bridge
   * - ``web-poet``
     - ``fetchkit[web-poet]``
     - WebPoet request downloader and page-object adapter
   * - ``scrapy-poet``
     - ``fetchkit[scrapy-poet]``
     - Complete WebPoet integration within Scrapy
   * - ``selectors``
     - ``fetchkit[selectors]``
     - Typed CSS/XPath page extraction with Parsel
   * - ``redis``
     - ``fetchkit[redis]``
     - Redis Streams queue adapter
   * - ``temporal``
     - ``fetchkit[temporal]``
     - Temporal durable-flow runtime
   * - ``observe``
     - ``fetchkit[observe]``
     - OTLP traces and metrics
   * - ``pipeline``
     - ``fetchkit[pipeline]``
     - PostgreSQL and object-storage pipeline
   * - ``full``
     - ``fetchkit[full]``
     - All runtime integrations

For example:

.. code-block:: bash

   python -m pip install 'fetchkit[mcp,langchain]'

Use from another project
------------------------

Add the distribution name, not the import name, to the downstream project's
dependencies. For example, in ``pyproject.toml``:

.. code-block:: toml

   dependencies = [
     "fetchkit>=0.4,<0.5",
   ]

Then import the Python package normally:

.. code-block:: python

   from pyfetcher import AsyncFetchClient, PageDocument

For local development, build once and install the resulting wheel into a clean
environment. This exercises the same package boundary as a registry install:

.. code-block:: bash

   cd /path/to/pyfetcher
   pdm build
   python -m pip install --force-reinstall dist/fetchkit-*.whl

An editable install is useful while changing both projects, but it can hide
missing package data. Run the wheel install above before releasing the
downstream application.

Choose an API
-------------

.. list-table:: Public entry points
   :header-rows: 1
   :widths: 31 30 39

   * - API
     - Best for
     - Resource lifetime
   * - :func:`pyfetcher.fetch` and :func:`pyfetcher.afetch`
     - Scripts and one-off calls
     - Cached process-wide service
   * - :class:`pyfetcher.FetchClient`
     - Repeated synchronous requests
     - Synchronous context manager
   * - :class:`pyfetcher.AsyncFetchClient`
     - Async services, workers, and FastAPI
     - Asynchronous context manager
   * - :class:`pyfetcher.FetchService`
     - Custom transports and advanced composition
     - Explicit ``close`` / ``aclose`` or context manager

Start with a client for any application that makes repeated requests. Keeping
one client alive allows HTTP keepalive connections, TLS sessions, and HTTP/2
connections to be reused.

First request
-------------

The function API is the shortest path for a script:

.. code-block:: python

   from pyfetcher import fetch

   response = fetch("https://example.com")
   print(response.status_code, response.ok)
   print(response.final_url, response.http_version)
   print((response.text or "")[:200])

Responses use the same :class:`pyfetcher.FetchResponse` model regardless of
the selected backend. HTTP error statuses raise an exception, and configured
retryable statuses are attempted again before the final error. ``response.ok``
therefore describes a successfully returned 2xx or 3xx response.

Extract from a page
-------------------

Install ``fetchkit[selectors]`` to adapt a buffered response into one lazily
parsed document with chainable CSS and XPath:

.. code-block:: python

   from pyfetcher import PageDocument, SelectorRule

   page = PageDocument.from_response(response)
   title = SelectorRule(
       css="h1",
       output="text",
       cardinality="optional",
       transforms=("normalize_whitespace",),
   ).apply(page)
   links = page.css("article a::attr(href)").getall()

See :doc:`page-extraction` for typed Pydantic model extraction, filtered link
rules, URL patterns, responsive images, and gallery collections.

Reusable async client
---------------------

Use one async client across related requests and place shared policy at
construction time:

.. code-block:: python

   import asyncio

   from pyfetcher import AsyncFetchClient, PoolPolicy, RetryPolicy, TimeoutPolicy


   async def main() -> None:
       async with AsyncFetchClient(
           base_url="https://api.example.com/v1/",
           headers={"accept": "application/json"},
           http2=True,
           pool=PoolPolicy(max_connections=100, concurrency=20),
           timeout=TimeoutPolicy(total_seconds=30),
           retry=RetryPolicy(attempts=4),
       ) as client:
           response = await client.get("users", params={"limit": 20})
           print(response.status_code, response.http_version)


   asyncio.run(main())

HTTP/2 is preferred by default for HTTPX, but protocol negotiation depends on
the origin. ``response.http_version`` reports the negotiated version when the
backend exposes it.

Per-request values override client defaults. The convenience methods
``get``, ``post``, ``put``, ``patch``, ``delete``, ``head``, and ``options``
all accept :class:`pyfetcher.FetchRequest` field names such as ``headers``,
``params``, ``json_data``, and ``timeout``.

Streaming a response
--------------------

Stream large bodies without buffering the complete response. ``max_bytes``
provides a hard consumption limit:

.. code-block:: python

   from pathlib import Path

   from pyfetcher import FetchClient, StreamPolicy


   destination = Path("download.bin")
   with FetchClient(
       stream=StreamPolicy(chunk_size=64 * 1024, max_bytes=100_000_000)
   ) as client:
       with destination.open("wb") as output:
           for data in client.iter_bytes("GET", "https://example.com/file"):
               output.write(data)

The async client exposes the same ``stream``, ``iter_bytes``, and
``iter_text`` concepts as async iterators. See :doc:`clients` for a FastAPI
``StreamingResponse`` recipe.

Streaming an upload
-------------------

Use ``content_factory`` when a streamed upload may be retried. The factory is
called again for every attempt, so it must return a fresh iterable:

.. code-block:: python

   import asyncio
   from pathlib import Path

   from pyfetcher import AsyncFetchClient


   source = Path("records.ndjson")


   def upload_body():
       with source.open("rb") as input_file:
           while chunk := input_file.read(64 * 1024):
               yield chunk


   async def main() -> None:
       async with AsyncFetchClient() as client:
           response = await client.post(
               "https://example.com/import",
               headers={"content-type": "application/x-ndjson"},
               content_factory=upload_body,
           )
           print(response.status_code)


   asyncio.run(main())

For one-shot requests, ``content`` also accepts bytes, text, a synchronous byte
iterable, or an asynchronous byte iterable. Do not combine ``content`` or
``content_factory`` with ``data`` or ``json_data``.

Lazy concurrent iteration
-------------------------

``imap`` consumes synchronous or asynchronous URL generators lazily. It limits
both active requests and buffered ordered results, so the input can be much
larger than memory:

.. code-block:: python

   import asyncio

   from pyfetcher import AsyncFetchClient


   async def discover_urls():
       for item_id in range(10_000):
           yield f"https://example.com/items/{item_id}"


   async def main() -> None:
       async with AsyncFetchClient() as client:
           async for response in client.imap(
               discover_urls(),
               concurrency=20,
               ordered=False,
           ):
               print(response.final_url, response.status_code)


   asyncio.run(main())

Use ``ordered=True`` when output must match input order. Transport errors are
raised during iteration. :meth:`pyfetcher.FetchService.afetch_many` is the
alternative when each result needs an explicit success/error record.

Optional backends
-----------------

Pass a backend name per client or request:

.. code-block:: python

   from pyfetcher import FetchClient

   with FetchClient(backend="curl_cffi") as client:
       response = client.get("https://example.com")

The core HTTPX backend supports sync and async use, streaming, pooling, and
HTTP/2. aiohttp is async-only. Backend streaming and protocol support differ;
see the matrix in :doc:`clients` and the extension boundaries in
:doc:`adapters`.

Rate limiting
-------------

Rate limiting composes with a client and is shared for that client's lifetime:

.. code-block:: python

   from pyfetcher import FetchClient
   from pyfetcher.ratelimit.limiter import DomainRateLimiter, RateLimitPolicy

   limiter = DomainRateLimiter(
       default_policy=RateLimitPolicy(requests_per_second=2.0, burst=5)
   )

   with FetchClient(rate_limiter=limiter) as client:
       response = client.get("https://example.com")

FastAPI and other services
--------------------------

Create one :class:`pyfetcher.AsyncFetchClient` in the host application's
lifespan, store it in application state, and inject that same instance into
request handlers. The complete typed FastAPI example is in :doc:`clients`.
fetchkit itself does not require FastAPI.

MCP server
----------

Install and start the optional MCP interface:

.. code-block:: bash

   python -m pip install 'fetchkit[mcp]'
   pyfetcher-mcp              # stdio
   pyfetcher-mcp --http 8000  # HTTP

See :doc:`mcp` for client configuration and the available tools and resources.

Common pitfalls
---------------

* Install ``fetchkit`` but import ``pyfetcher``.
* Keep clients in a context manager or explicitly call ``close`` / ``aclose``.
* Use ``content_factory`` instead of a one-shot generator when retries are
  enabled for an upload.
* Treat HTTP/2 as negotiated capability; always inspect ``http_version`` when
  protocol choice matters.
* Keep ``verify_ssl=True`` outside tightly controlled local testing.
* Scrapy, yt-dlp, and gallery-dl have distinct execution models. Their
  integration boundaries are documented in :doc:`adapters`.

Next steps
----------

* :doc:`clients` -- lifecycle, FastAPI, HTTP/2, streaming, and generators
* :doc:`acquisition` -- direct, yt-dlp, and gallery-dl provider workflows
* :doc:`adapters` -- custom transports, Scrapy, middleware, and skills
* :doc:`scraping` -- selectors, links, forms, robots.txt, and sitemaps
* :doc:`headers` -- fixed and rotating browser profiles
* :doc:`mcp` -- agent-facing MCP integration
* :doc:`api/index` -- complete API reference
