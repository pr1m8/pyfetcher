# Repository instructions for AI agents

This file governs the whole repository. More specific `AGENTS.md` files may
add constraints for their subtree, but they must not weaken these rules.

## Project identity

- The distribution is `fetchkit`; the Python import package is `pyfetcher`.
- The project targets Python 3.13 or newer and is managed with PDM.
- The package is an alpha-stage, typed toolkit for HTTP fetching, crawling,
  extraction, provider-backed acquisition, media processing, and durable web
  jobs. Preserve compatibility deliberately; do not assume alpha means that
  public contracts may be changed casually.
- Treat documented APIs, examples, exports from `pyfetcher`, and tests as one
  public surface. Update them together when behavior changes.

## Start with the right repository skill

Read the matching skill before designing or editing that area. When a task
crosses boundaries, use the smallest set that covers it.

| Work | Skill |
| --- | --- |
| HTTP clients, pooling, HTTP/2, retries, streaming, middleware, FastAPI | `skills/http-fetch/SKILL.md` |
| Scrapy engines, requests, middleware, spiders, scheduling | `skills/scrapy-crawl/SKILL.md` |
| yt-dlp metadata, video/audio downloads, playlists | `skills/yt-dlp-acquire/SKILL.md` |
| gallery-dl metadata, image/gallery downloads, archives | `skills/gallery-dl-acquire/SKILL.md` |
| Page documents, CSS/XPath selectors, typed extractors, links, galleries | `skills/typed-page-extraction/SKILL.md` |
| URL conversion, normalization, adapters, patterns, templates | `skills/url-workflows/SKILL.md` |
| Jobs, templates, queues, Temporal, Redis Streams, telemetry | `skills/durable-web-jobs/SKILL.md` |
| Byte streams, media metadata, thumbnails, blobs, artifacts | `skills/media-artifacts/SKILL.md` |

If no skill matches, follow this file and inspect the nearest public module,
documentation page, example, and tests before making a change.

## Architecture map

- `src/pyfetcher/contracts/`: immutable request, response, policy, resource,
  URL, adapter, pattern, and template contracts.
- `src/pyfetcher/fetch/`, `transports/`, `middleware.py`: ordinary HTTP
  execution, client lifecycles, batching, streaming, and transport adapters.
- `src/pyfetcher/documents/`, `scrape/`, `extraction.py`, `extractors/`:
  document selection and typed content extraction.
- `src/pyfetcher/acquisition/`, `downloaders/`: provider-neutral acquisition
  and optional yt-dlp/gallery-dl implementations.
- `src/pyfetcher/media/`, `streams.py`: canonical media metadata, bounded byte
  handling, inspection, and processing.
- `src/pyfetcher/artifacts/`, `jobs/`, `integrations/`, `telemetry.py`: blob
  references, serializable job contracts, runtimes, queues, and observability.
- `src/pyfetcher/protocol/`: versioned JSON Schema catalogs, RPC service
  discovery, protobuf framing, and generated TypeScript contract bundles.
- `src/pyfetcher/crawler/`, `pipeline/`, `search.py`: discovery, crawl policy,
  reusable stages, and search orchestration.
- `src/pyfetcher/mcp/`, `cli/`, `tui/`: user and agent-facing entry points.
- `docs/`, `examples/`, `tests/`: maintained behavior, runnable guidance, and
  contract verification. Do not let these drift behind implementation.

## Design invariants

1. Prefer typed, serializable Pydantic contracts at subsystem boundaries.
   Public configuration and job messages should be data, not hidden closures.
2. Use `URL` as the canonical HTTP/HTTPS URL value. Convert foreign URL types
   through `URLAdapterRegistry`; use `URLRule`, `URLPattern`, and `URLTemplate`
   instead of scattering string or regular-expression manipulation.
3. Keep execution mechanisms distinct:
   - HTTP transports fetch ordinary requests.
   - Scrapy owns crawler-engine scheduling and reactor lifecycle.
   - Acquisition providers own downloader/extractor-native behavior.
   - Media processors inspect or transform already acquired content.
4. Keep large bytes outside durable job and queue messages. Store content in a
   `BlobStore` and pass `BlobRef` or `ArtifactRef` with provenance.
5. Durable jobs reference versioned templates through `TemplateRef`. Never
   serialize arbitrary callables or import paths for remote execution.
6. Make lifecycle ownership explicit. Reuse clients and pools; do not create a
   network client per request, stop a host-owned Scrapy reactor, or hide
   long-lived resources in module globals.
7. Keep optional dependencies optional. Import integrations lazily and raise
   actionable errors naming the required extra.
8. Put site-specific selectors, URL rules, provider options, and workflow
   templates in injectable registries or configuration. Do not hard-code sites
   into general contracts.
9. Preserve normalized metadata and provenance when translating between HTTP,
   Scrapy, acquisition providers, media records, jobs, and artifacts.
10. Do not claim exactly-once delivery. Design Redis/worker paths for retries
    and idempotency; keep Temporal workflow code deterministic.
11. Keep JSON Schema as the source of truth for portable domain contracts.
    Protobuf supplies gRPC framing and service paths; generated TypeScript
    types and clients must retain the catalog's contract keys and checksums.

## Durable job integration checklist

- Keep the three persistence roles separate: `JobQueue` owns delivery, leases,
  acknowledgements, and retries; `JobStore` owns queryable state, results,
  cancellation intent, and submission idempotency; `BlobStore` owns large
  bytes. Do not make one adapter silently stand in for another.
- The in-memory queue and store are single-process defaults only. A distributed
  Redis host should inject both `RedisStreamJobQueue` and `RedisJobStore` into
  the same `JobApplication`. Never pair a shared queue with process-local job
  state when the API and workers run separately.
- Submit through `JobService` rather than enqueueing directly. Workers must
  persist retry or terminal state before moving or acknowledging the delivery,
  so a crash produces a recoverable redelivery instead of lost status.
- Treat `JobRequest.idempotency_key` as submission deduplication, not an
  exactly-once guarantee for external writes. Templates with side effects must
  also use a stable downstream idempotency key or an application transaction.
- Cancellation is cooperative. Store cancellation intent durably, check it
  while renewing leases, and make templates safe to retry after interruption.
- Make adapter ownership explicit. Either add injected queues, stores, clients,
  and providers to `JobApplication.owned_resources` or close them in the host;
  never rely on interpreter shutdown.
- Keep HTTP, CLI, and gRPC adapters thin: validate transport input, then
  delegate to `JobService` and its versioned Pydantic contracts. Do not create
  transport-specific execution or status models.
- Test durable changes offline for concurrent idempotent submission, retry and
  terminal transitions, redelivery, cancellation, paging/index consistency,
  and cleanup. Live Redis and Temporal tests must remain opt-in.

## Editing workflow

1. Inspect the relevant public exports, docs, example, and focused tests.
2. Make the smallest cohesive change; preserve unrelated dirty-worktree edits.
3. Add or update offline unit tests. Live sites, credentials, and network
   access must remain opt-in.
4. Update public exports, type hints, docs, examples, optional extras, and
   changelog entries when the public contract changes.
5. Run focused checks first, then broaden validation in proportion to risk.

Use modern Python 3.13 syntax and explicit sync/async APIs. Do not make a sync
function silently drive an event loop. Support sync and async iterables where
the public contract promises both, and keep retryable streaming bodies
replayable through factories or explicit buffering policies.

## Validation

Common commands:

```bash
pdm install -G dev -G full
pdm run ruff format --check src/ tests/ examples/
pdm run ruff check src/ tests/ examples/
pdm run pytest tests/ -q
pdm run doc8 docs/
LC_ALL=C pdm run sphinx-build -E -W --keep-going -b html docs docs/_build/html
pdm build
pdm run twine check dist/*
```

Choose focused tests by subsystem before the full suite. Validate repository
skills with:

```bash
python "$CODEX_HOME/skills/.system/skill-creator/scripts/quick_validate.py" skills/<skill-name>
```

`make check` formats files rather than only checking them. `make infra-reset`
deletes local infrastructure volumes. Do not run either accidentally.

## Safety and release boundaries

- Never commit, push, tag, bump the version, create a release, upload a
  distribution, or reset infrastructure unless the user explicitly requests
  that action.
- Publishing uses PyPI Trusted Publishing from the GitHub release workflow.
  Do not add repository tokens or long-lived package credentials.
- Never place passwords, cookies, access tokens, or credential file contents
  in source, fixtures, logs, examples, serialized jobs, or provider options.
- Full GUI management and stronger distributed control-plane features are
  future directions unless the current code and docs demonstrate them. Clearly
  label planned capabilities instead of documenting them as implemented.
