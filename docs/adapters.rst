Adapters and execution engines
==============================

fetchkit separates ordinary HTTP transports, acquisition providers, and crawl
engines because HTTPX, Scrapy, yt-dlp, and gallery-dl do not share one useful
execution model.

Architecture boundaries
-----------------------

.. list-table:: Extension areas
   :header-rows: 1
   :widths: 21 28 51

   * - Area
     - Implementations
     - Responsibility
   * - HTTP transport
     - HTTPX, aiohttp, curl_cffi, cloudscraper
     - Execute a normalized ``FetchRequest`` and return ``FetchResponse`` or
       response chunks.
   * - Crawl engine bridge
     - Scrapy engine transport and downloader middleware
     - Preserve Scrapy scheduling, downloader middleware, Deferred/reactor
       lifecycle, and request metadata.
   * - Acquisition provider
     - Direct HTTP, yt-dlp, gallery-dl
     - Resolve provider-native extractors, formats, galleries, metadata,
       filenames, progress, and downloads.
   * - Middleware
     - Sync and async call-chain layers
     - Transform requests, observe responses, short-circuit, translate errors,
       or implement cross-cutting policy.
   * - Codex skill
     - HTTP, Scrapy, yt-dlp, gallery-dl
     - Translate task intent into the correct capability without mixing
       provider-native options.

Custom HTTP transports
----------------------

:class:`pyfetcher.FetchService` accepts registered synchronous and asynchronous
transports. A registered transport implements ``fetch`` / ``stream`` or
``afetch`` / ``astream`` and may implement lifecycle cleanup.

.. code-block:: python

   service = FetchService(async_transports={"custom": custom_transport})
   response = await service.afetch(
       FetchRequest(url="https://example.com", backend="custom")
   )

Applications may register adapters later with
:meth:`pyfetcher.FetchService.register_sync_transport` and
:meth:`pyfetcher.FetchService.register_async_transport`.

Mechanism-neutral middleware
----------------------------

The :mod:`pyfetcher.middleware` composers are used by both
:class:`pyfetcher.FetchService` and :class:`pyfetcher.AcquisitionService`. A
layer receives an immutable request and a ``call_next`` handler:

.. code-block:: python

   async def annotate(request, call_next):
       request = request.model_copy(
           update={"headers": {**request.headers, "x-client": "worker-1"}}
       )
       return await call_next(request)

   service = FetchService(async_middleware=[annotate])

Middleware declaration order is outermost-first. Use it for observability,
policy, caches, and integration-specific translation. Keep retryable HTTP
status handling in ``FetchService`` unless a layer intentionally replaces it.

Scrapy bridge
-------------

Install the optional integration:

.. code-block:: bash

   python -m pip install 'fetchkit[scrapy]'

Attach fetchkit to an already-running Scrapy engine:

.. code-block:: python

   from pyfetcher import FetchRequest
   from pyfetcher.fetch.service import FetchService
   from pyfetcher.integrations.scrapy import ScrapyEngineTransport

   transport = ScrapyEngineTransport(crawler.engine)
   service = FetchService(async_transports={"scrapy": transport})

   response = await service.afetch(
       FetchRequest(url="https://example.com", backend="scrapy")
   )

The bridge prefers Scrapy's current ``download_async(request)`` engine API. It
falls back to ``download(request)`` and ``deferred_to_future`` for older
engines. The fallback requires Scrapy's asyncio reactor.

The engine remains owned by Scrapy. The transport never installs or stops a
reactor. Scrapy returns complete responses through this engine API, so
``ScrapyEngineTransport.astream`` raises ``NotImplementedError``. Select HTTPX
or aiohttp when response streaming is required.

The inverse bridge is :class:`~pyfetcher.integrations.scrapy.PyfetcherDownloaderMiddleware`.
It only intercepts requests containing ``request.meta['pyfetcher'] = True``;
other requests continue through Scrapy's configured downloader stack. Set
``pyfetcher_backend`` in meta to select a fetchkit backend.

Conversion helpers
~~~~~~~~~~~~~~~~~~

The following helpers can be used independently:

* :func:`~pyfetcher.integrations.scrapy.to_scrapy_request`
* :func:`~pyfetcher.integrations.scrapy.from_scrapy_request`
* :func:`~pyfetcher.integrations.scrapy.from_scrapy_response`
* :func:`~pyfetcher.integrations.scrapy.to_scrapy_response`

Timeouts, retry counts, redirects, proxies, size limits, headers, and buffered
bodies are mapped. Scrapy-specific values remain in
:class:`~pyfetcher.integrations.scrapy.ScrapyRequestOptions`. Streaming upload
iterables cannot be converted to a Scrapy request.

Acquisition providers
---------------------

Direct HTTP, yt-dlp, and gallery-dl are available through
:class:`pyfetcher.AcquisitionService`. Shared policy lives on
:class:`pyfetcher.AcquisitionRequest`; native options remain separated under
``direct_options``, ``yt_dlp_options``, and ``gallery_dl_options``. Application
downloaders can be wrapped with
:class:`pyfetcher.DownloaderAcquisitionProvider`; JSON-safe custom settings use
the namespaced ``provider_options`` mapping and can publish an option schema for
generated clients.

See :doc:`acquisition` for capability discovery, credential references,
provider selection, middleware, and async event streams.

Focused Codex skills
--------------------

The repository includes eight validated skills under ``skills/``. The four
execution-specific skills are:

``http-fetch``
   Pooling, HTTP/2, proxies, streaming, retries, middleware, and FastAPI.

``scrapy-crawl``
   Engine attachment, middleware, request conversion, reactors, and crawl
   ownership.

``yt-dlp-acquire``
   Formats, playlists, postprocessors, credentials, and video/audio progress.

``gallery-dl-acquire``
   Extractors, ranges, archives, naming, credentials, and gallery progress.

Typed extraction, URL workflows, durable jobs, and media/artifact handling
have separate focused skills so provider code does not absorb those concerns.

Current limitations
-------------------

* Automatic provider selection uses conservative URL/host scoring. Set an
  explicit provider for ambiguous URLs.
* Scrapy engine response streaming is not exposed.
* Cancelling an acquisition cancels its async task, but a provider running in a
  worker thread may only stop at its next native cancellation boundary.
* gallery-dl uses process-global configuration, so fetchkit serializes its
  gallery-dl jobs within the process.
* Credentials are resolved by application callbacks; fetchkit does not include
  a secret store.
