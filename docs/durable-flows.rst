Durable jobs and reusable flows
===============================

fetchkit models acquisition work as **data**, not as serialized Python
callables. A :class:`~pyfetcher.jobs.JobRequest` points to an allowlisted,
versioned :class:`~pyfetcher.jobs.TemplateRef`; a worker resolves that reference
through :class:`~pyfetcher.jobs.TemplateRegistry` and injects runtime clients,
credentials, and storage through :class:`~pyfetcher.jobs.JobContext`.

This same envelope can be kept in a JSON file, sent through Redis Streams,
executed as a Temporal activity, accepted by a future RPC API, or run locally.

.. mermaid::

   flowchart LR
       Spec["JobRequest<br/>template@version + JSON policy"] --> Runtime
       Registry["TemplateRegistry<br/>allowlisted implementations"] --> Runtime
       Services["JobContext<br/>fetch · acquisition · search · blobs"] --> Runtime
       Runtime{"Flow runtime"}
       Runtime --> Local["In-process queue"]
       Runtime --> Redis["Redis Streams workers"]
       Runtime --> Temporal["Temporal workflow + activities"]
       Local --> Result
       Redis --> Result
       Temporal --> Result
       Result["JobResult<br/>artifacts · collections · child jobs"] --> Blob[("Local / S3 / MinIO blobs")]

Core contracts
--------------

``JobRequest``
   A stable template reference, optional target, JSON payload, execution
   policy, idempotency key, parent/run IDs, and W3C trace context.

``JobResult``
   A terminal or retry status, JSON output, artifact references, ordered
   collections, metrics, and zero or more child jobs.

``ArtifactRef`` and ``BlobRef``
   Metadata and an immutable address for bytes. Large HTML bodies, videos,
   images, manifests, and exports do not belong in queue messages or workflow
   histories.

``ArtifactCollection``
   An ordered gallery, playlist, search result, page set, or other collection.
   A collection may have a continuation token and a stored manifest.

``FlowRequest``
   Initial jobs plus concurrency and total-job bounds. The flow is dynamic:
   successful jobs can spawn more work without requiring a static DAG.

The contracts use frozen Pydantic models and round-trip through JSON. Template
names are resolved from an explicit registry; fetchkit does not deserialize
arbitrary import paths or callables.

Built-in template catalog
-------------------------

``web.pagination@1``
   Discover the last page, enumerate page URLs, or follow a next-link chain.
   CSS selectors, query-parameter names, URL templates, maximum pages, and the
   template to run for each page are data-driven.

``media.acquire@1``
   Route metadata or downloads through direct HTTP, yt-dlp, or gallery-dl.
   Results become artifact references and an ordered gallery, playlist,
   collection, or media-set manifest. Local downloads may be copied to the
   configured blob store.

``site.search@1``
   Route through a registered :class:`~pyfetcher.search.SearchProvider`, return
   normalized hits and a continuation token, and optionally spawn a visit job
   for each hit.

List the catalog or validate a serialized job/flow before enqueueing it:

.. code-block:: bash

   pyfetcher templates list
   pyfetcher templates list --output json
   pyfetcher templates validate job.json

Pagination example
------------------

The pagination template is not tied to a scraper. Here it discovers the final
page and schedules ``article.extract@2`` for each page URL:

.. code-block:: python

   from pyfetcher.jobs import JobRequest, PaginationInput, TemplateRef

   job = JobRequest(
       template=TemplateRef(name="web.pagination", version="1"),
       target="https://example.com/archive?page=1",
       payload=PaginationInput(
           mode="enumerate",
           page_link_selector="nav.pagination a[href]",
           page_parameter="page",
           max_pages=500,
           visit_template=TemplateRef(name="article.extract", version="2"),
           visit_payload={"store_html": True},
       ).model_dump(mode="json"),
       idempotency_key="example-archive-pages",
   )

For cursor- or next-link pagination, set ``mode="follow_next"`` and provide
``next_link_selector``. Each page schedules the next pagination job until no
link exists or ``max_pages`` is reached.

Local runtime
-------------

The in-process runtime is the reference implementation for scripts, tests, and
single-process workers:

.. code-block:: python

   from pyfetcher import AsyncFetchClient
   from pyfetcher.artifacts import LocalBlobStore
   from pyfetcher.jobs import (
       FlowRequest,
       InProcessJobRuntime,
       JobContext,
       JobExecutor,
       TemplateRegistry,
       register_builtin_templates,
   )

   registry = TemplateRegistry()
   register_builtin_templates(registry)

   async with AsyncFetchClient() as fetcher:
       executor = JobExecutor(
           registry,
           context=JobContext(
               services={"fetch": fetcher},
               blob_store=LocalBlobStore("./artifacts"),
           ),
       )
       async with InProcessJobRuntime(executor) as runtime:
           result = await runtime.run(
               FlowRequest(name="archive", jobs=(job,), concurrency=10)
           )

Retries use the job policy, including exponential backoff. ``max_jobs`` bounds
dynamic expansion, and idempotency keys suppress duplicate enqueueing within
the local queue.

WebPoet page objects
--------------------

Install the WebPoet adapter:

.. code-block:: bash

   python -m pip install 'fetchkit[web-poet]'

fetchkit can act as the request downloader for WebPoet's ``HttpClient``. This
means additional page-object requests reuse fetchkit's async pool, HTTP/2,
headers, retry, rate limiting, and middleware:

.. code-block:: python

   from pyfetcher.integrations.webpoet import WebPoetHttpAdapter

   poet_client = WebPoetHttpAdapter(fetcher).http_client()
   response = await poet_client.get("https://example.com/sidebar")

For job execution, register page classes under stable names with
:class:`~pyfetcher.integrations.webpoet.WebPoetPageRegistry`, construct a
:class:`~pyfetcher.integrations.webpoet.WebPoetService`, and add
:class:`~pyfetcher.integrations.webpoet.WebPoetTemplate` to the template
registry. The standalone service supports common direct inputs such as
``HttpResponse``, ``HttpClient``, ``PageParams``, and request/response URLs.

Use the ``scrapy-poet`` integration for custom input providers, rule overrides,
retry/fallback dependencies, and full crawl scheduling:

.. code-block:: bash

   python -m pip install 'fetchkit[scrapy-poet]'

WebPoet additional requests fetch data required to build a page object; they do
not replace a crawler frontier. This boundary follows the `WebPoet framework
integration specification <https://web-poet.readthedocs.io/en/stable/frameworks/index.html>`_
and `additional-request contract
<https://web-poet.readthedocs.io/en/stable/frameworks/additional-requests.html>`_.

Redis Streams queue
-------------------

Install ``fetchkit[redis]`` and create
:class:`~pyfetcher.integrations.redis_streams.RedisStreamJobQueue` with an
injected async Redis client or ``RedisStreamJobQueue.from_url()``.

The adapter uses consumer groups, explicit acknowledgement, stale-message
claiming, a dead-letter stream, and a sorted set for delayed retries. Its
delivery contract is **at least once**, so side-effecting templates still need
idempotency keys or a durable result/transaction boundary. Redis Pub/Sub is not
used because it is at-most-once and non-durable. See the official `Redis Streams
documentation <https://redis.io/docs/latest/develop/data-types/streams/>`_ and
`Pub/Sub delivery semantics <https://redis.io/docs/latest/develop/pubsub/>`_.

Temporal durable execution
--------------------------

Install ``fetchkit[temporal]``. Connect with ``connect_temporal`` so the
Pydantic data converter is configured, build a worker with
``build_temporal_worker``, and submit flows through ``TemporalJobRuntime`` from
``pyfetcher.integrations.temporal``.

Temporal is a durable **flow runtime**, not an implementation of
``JobQueue``. The deterministic workflow schedules activities, applies bounds,
handles child jobs, and records terminal results. All HTTP, filesystem,
downloader, search, and blob operations occur in the activity-side
``JobExecutor``. This follows the Temporal Python SDK's `workflow determinism
and activity model <https://github.com/temporalio/sdk-python>`_.

Storage
-------

Core storage implementations are:

* :class:`~pyfetcher.artifacts.MemoryBlobStore` for tests;
* :class:`~pyfetcher.artifacts.LocalBlobStore` for atomic local files; and
* :class:`~pyfetcher.artifacts.S3BlobStore` over the optional MinIO/S3 client.

Files are hashed incrementally and references include size and SHA-256 where
available. Pass references through jobs; do not pass downloaded bytes through
Redis, Temporal, RPC, or tracing attributes.

Tracing, metrics, and logs
--------------------------

Install ``fetchkit[observe]``. ``pyfetcher.telemetry.configure_telemetry``
exports OTLP traces and metrics to an OpenTelemetry Collector or directly to a
compatible endpoint such as Grafana Tempo. Add
``pyfetcher.telemetry.OpenTelemetryFetchMiddleware`` to ``FetchService`` and
``pyfetcher.telemetry.OpenTelemetryJobHook`` to ``JobExecutor``.

The job hook propagates W3C trace context into child jobs. Standard Python logs
can use ``pyfetcher.telemetry.TraceContextFilter`` to add the active trace
and span IDs. This avoids presenting the OpenTelemetry Python logs API as
stable while its official status remains development; traces and metrics are
stable. See `OpenTelemetry Python status
<https://opentelemetry.io/docs/languages/python/>`_ and `Grafana Tempo
documentation <https://grafana.com/docs/tempo/latest/>`_.

Delivery guarantees and non-goals
---------------------------------

* A queue delivery and a workflow execution are different abstractions.
* Redis Streams provides at-least-once delivery, not exactly-once side effects.
* Temporal persists orchestration but activities must still be idempotent.
* Blob stores persist bytes; a separate metadata/result store may index
  artifacts and completed jobs.
* Templates are versioned. Changing incompatible input/output semantics means
  registering a new version rather than mutating old queued jobs.
* RPC, web UI, TUI workflow inspection, and job-category scheduling can be
  layered above these contracts without changing provider implementations.
