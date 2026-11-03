---
name: durable-web-jobs
description: Build or operate fetchkit durable jobs using JobRequest templates, JobApplication workers, Redis queue/store persistence, Temporal, artifacts, retries, idempotency, or telemetry. Use for serializable orchestration and control planes, not a single direct fetch.
---

# fetchkit Durable Web Jobs

Model durable work as versioned data and inject the services that execute it.

## Build the job contract

Create a ``JobRequest`` with serializable inputs and a versioned
``TemplateRef``. Register trusted implementations in a ``TemplateRegistry`` at
the worker boundary. Never serialize callables or arbitrary import paths.

Use the built-in template families where they fit:

- ``web.pagination@1`` for bounded page traversal.
- ``media.acquire@1`` for provider-backed media work.
- ``site.search@1`` for reusable search jobs.

Add a custom versioned template when a site or business process needs bespoke
logic. Keep selectors, URL rules, and provider options in typed configuration.

## Choose runtime and delivery semantics

- Use ``InProcessJobRuntime`` for local execution and tests.
- Use ``JobApplication`` to compose a long-running ``JobWorker``,
  ``JobService``, registry, queue, store, and runtime services.
- Use Redis Streams plus ``RedisJobStore`` for multi-process workers that
  tolerate at-least-once delivery and need shared status, results,
  cancellation, and submission idempotency.
- Use Temporal for durable orchestration whose workflow code remains
  deterministic and whose I/O occurs in activities.

Make handlers idempotent, bound retries, and record stable job and artifact
identifiers. Do not claim exactly-once effects.

## Keep persistence roles separate

- ``JobQueue`` owns delivery, leases, acknowledgement, and retry scheduling.
- ``JobStore`` owns status, results, cancellation intent, paging, and
  submission idempotency.
- ``BlobStore`` owns large HTML, media, manifests, and other bytes.

Never pair a shared queue with ``InMemoryJobStore`` when API and worker
processes must share state. Persist retry or terminal state before moving or
acknowledging a delivery. Treat ``JobRequest.idempotency_key`` as submission
deduplication; templates that write externally still need a stable downstream
idempotency key or application transaction.

## Host the worker and control plane

For the bundled HTTP host, install the optional adapters and select the Redis
pair through configuration:

```bash
python -m pip install 'fetchkit[api,redis]'
FETCHKIT_REDIS_URL=redis://localhost:6379/0 pyfetcher jobs serve
```

For a custom host, inject both ``RedisStreamJobQueue`` and ``RedisJobStore``
into ``JobApplication.create``. Add adapters created with ``from_url`` to
``owned_resources`` or close them in the host. Keep HTTP, CLI, and future RPC
adapters thin by delegating submit, inspect, list, cancel, health, and template
discovery to ``JobService``.

The Redis store uses atomic record/index transitions. Preserve a common Redis
Cluster hash tag if customizing its prefix, and make record retention an
explicit application policy. Cancellation remains cooperative, and API or
worker restarts do not make external side effects exactly once.

## Externalize content and observe work

Store large response or media bytes in ``MemoryBlobStore``, ``LocalBlobStore``,
or ``S3BlobStore`` and pass ``BlobRef`` or ``ArtifactRef`` in messages. Inject
fetch, acquisition, blob, and telemetry services through ``JobContext``. Carry
trace context across queue and activity boundaries without storing secrets.

## Validate jobs

Test templates in process before testing optional runtimes. Cover concurrent
idempotent submission, retries, duplicate delivery, cancellation, missing
template versions, status-index consistency, serialization, cleanup, and
artifact recovery. Keep live Redis and Temporal tests opt-in.

```bash
pdm run pytest tests/test_jobs.py tests/test_job_worker.py tests/test_job_api.py -q
pdm run pytest tests/test_redis_store.py tests/test_optional_runtimes.py -q
pdm run ruff check src/ tests/ examples/
LC_ALL=C pdm run sphinx-build -E -W --keep-going -b html docs docs/_build/html
```

Read ``docs/durable-flows.rst`` and ``examples/durable_jobs.py`` before changing
job contracts. Use ``$media-artifacts`` for blob and media details and the
focused acquisition skills for provider-native options.
