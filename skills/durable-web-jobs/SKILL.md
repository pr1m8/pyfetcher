---
name: durable-web-jobs
description: Build, integrate, debug, or document fetchkit JobRequest workflows, TemplateRegistry, TemplateRef, InProcessJobRuntime, Redis Streams queues, Temporal workflows, BlobStore artifacts, pagination, media acquisition, site search, retries, idempotency, telemetry, tracing, or worker delivery semantics. Use for serializable durable orchestration, not a single direct fetch.
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
- Use Redis Streams for worker queues that tolerate at-least-once delivery.
- Use Temporal for durable orchestration whose workflow code remains
  deterministic and whose I/O occurs in activities.

Make handlers idempotent, bound retries, and record stable job and artifact
identifiers. Do not claim exactly-once effects.

## Externalize content and observe work

Store large response or media bytes in ``MemoryBlobStore``, ``LocalBlobStore``,
or ``S3BlobStore`` and pass ``BlobRef`` or ``ArtifactRef`` in messages. Inject
fetch, acquisition, blob, and telemetry services through ``JobContext``. Carry
trace context across queue and activity boundaries without storing secrets.

## Validate jobs

Test templates in process before testing optional runtimes. Cover retries,
duplicate delivery, cancellation, missing template versions, serialization,
and artifact recovery.

```bash
pdm run pytest tests/test_jobs.py tests/test_optional_runtimes.py -q
pdm run ruff check src/ tests/ examples/
LC_ALL=C pdm run sphinx-build -E -W --keep-going -b html docs docs/_build/html
```

Read ``docs/durable-flows.rst`` and ``examples/durable_jobs.py`` before changing
job contracts. Use ``$media-artifacts`` for blob and media details and the
focused acquisition skills for provider-native options.
