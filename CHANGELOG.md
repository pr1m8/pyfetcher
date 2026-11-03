# Changelog

All notable changes to fetchkit are documented here. The project follows
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Bidirectional typed URL adapters for Pydantic, urllib, HTTPX, yarl,
  tldextract domain parts, request/response objects, and common structural URL
  protocols, including explicit relative resolution.
- Application-owned bespoke URL adapter registries, conditional URL transform
  rules, reusable client integration, and named custom selector transforms and
  converters without process-global registration.
- Parsel-backed ``PageDocument`` and chainable ``Selection`` adapters for
  buffered fetchkit responses, Scrapy responses, raw HTML, and XML.
- Serializable CSS/XPath ``SelectorRule`` values with explicit cardinality,
  transforms, regex capture, typed conversion, Pydantic ``ModelExtractor``,
  and sync-or-async typed page extractor functions.
- Scrapy-style ``LinkRule`` filtering by document region, URL regex, domain,
  scheme, extension, nofollow state, canonicalization, and stable deduplication.
- Typed ``URLPattern`` matching, validated named captures, explicit reversible
  ``URLTemplate`` rendering, query constraints, and round-trip checks.
- Responsive and lazy-loaded image discovery, ``srcset`` and ``picture``
  candidates, thumbnail normalization, and reusable collection/gallery rules.
- Replay-aware sync/async ``ByteStream`` adapters and provider-neutral typed
  image, GIF/WebP, video, audio, and thumbnail metadata and processing.
- Canonical media metadata output from direct HTTP, yt-dlp, and gallery-dl
  adapters while retaining their legacy result models.
- Provider-neutral acquisition requests, capability discovery, automatic or
  explicit provider selection, provenance, credential references, middleware,
  and async progress/item event streams.
- Direct HTTP, yt-dlp, and gallery-dl acquisition-provider adapters with
  isolated provider-native option dictionaries.
- Optional Scrapy request/response conversion, an engine transport targeting
  ``download_async()``, and an opt-in fetchkit downloader middleware.
- Mechanism-neutral synchronous and asynchronous middleware composers.
- Proxy policy across clients, requests, and built-in transports.
- Four repository-local Codex skills for HTTP, Scrapy, yt-dlp, and gallery-dl.
- A provider-aware ``pyfetcher acquire`` CLI command.
- Custom downloader provider adapters with sync/async iterable results,
  namespaced JSON-safe options, discoverable option schemas, credential and
  progress integration, and opt-in package entry-point loading.
- Serializable, versioned job and flow contracts with bounded local dynamic
  fan-out, retries, timeouts, idempotency keys, and W3C trace context.
- Built-in pagination, provider-neutral media collection, and pluggable site
  search templates for last-page discovery, page walking, galleries,
  playlists, collections, and search-result fan-out.
- Portable blob and artifact references, ordered collection manifests, atomic
  local storage, and an S3/MinIO blob-store adapter.
- A WebPoet ``HttpClient`` downloader bridge, allowlisted standalone page
  registry, and ``webpoet.extract@1`` job template, with a separate
  ``scrapy-poet`` extra for complete crawler integration.
- Optional Redis Streams at-least-once queue and Temporal durable flow runtime.
- OpenTelemetry job/fetch spans, metrics, W3C child-job propagation, OTLP/Tempo
  export configuration, and standard-log trace correlation.
- ``pyfetcher templates list`` and ``templates validate`` CLI commands.
- A transport-neutral job service, queryable status/result store, bounded
  long-running worker host, application lifecycle container, cooperative
  cancellation, lease heartbeats, structured worker events, and JSON logs.
- An optional FastAPI job control plane with health, template discovery,
  submission, paging, inspection, cancellation, worker state, and SSE events.
- ``pyfetcher jobs run`` for finite JSON job/flow execution and ``jobs serve``
  for a lifecycle-owned API and worker process, with optional OTLP export.
- A deterministic, versioned JSON Schema contract catalog for HTTP,
  extraction, acquisition, media, artifacts, search, queues, and jobs, with
  provider/template discovery, SHA-256 drift checks, split TypeScript-friendly
  exports, and ``pyfetcher contracts`` CLI commands.

### Changed

- The legacy Postgres pipeline now runs real concurrent worker slots, closes
  owned clients deterministically, and routes download jobs through the typed
  acquisition service with multi-item gallery and playlist persistence.
- Pull-request CI now enforces a coverage floor and smoke-tests the installed
  wheel in a clean environment in addition to checking distribution metadata.
- Core root imports now fail loudly instead of swallowing unrelated import-time
  errors, and examples consistently use the ``fetchkit`` distribution name.
- Direct downloads now support headers, cookies, proxies, progress callbacks,
  safe relative filenames, atomic destination replacement, and overwrite
  policy.
- yt-dlp metadata extraction now honors configured native options and reports
  numeric progress percentages.
- gallery-dl configuration is serialized to prevent concurrent jobs from
  racing over its process-global state.
- The CLI version flag now reads the published ``fetchkit`` distribution.

## [0.4.0] - 2026-08-14

### Added

- Reusable synchronous and asynchronous clients with explicit lifecycle
  management, shared defaults, base URLs, and connection pooling.
- HTTP/2 configuration and negotiated protocol reporting for HTTPX responses.
- Streaming uploads from bytes, text, synchronous iterables, asynchronous
  iterables, and retry-safe content factories.
- Synchronous and asynchronous download iterators with byte limits and text
  decoding helpers.
- Bounded asynchronous mapping across synchronous or asynchronous URL sources.
- Custom transport registration for downstream integrations.
- FastAPI lifespan and dependency-injection guidance, client examples, and a
  documented adapter roadmap for Scrapy, yt-dlp, and gallery-dl.
- A task-oriented quick start covering API selection, retry-safe uploads,
  bounded iteration, resource cleanup, and common integration pitfalls.
- A typed-package marker and public runtime `pyfetcher.__version__`.

### Changed

- Pool reuse now accounts for HTTP/2, TLS verification, and pool settings.
- Retryable HTTP statuses are retried by the service instead of escaping before
  Tenacity can apply the configured retry policy.
- Distribution metadata, project links, optional extras, release checks, and
  strict documentation workflows were refreshed.
- The MCP server now reports the installed distribution version instead of a
  stale hard-coded value.

### Roadmap

- Scrapy interoperability and yt-dlp/gallery-dl acquisition-provider adapters
  remain separate future capability and skill areas; they are not presented as
  implemented by this release.

## [0.3.1] - 2026-07-25

- Maintenance release preceding the reusable-client and streaming work.

[0.4.0]: https://github.com/pr1m8/pyfetcher/compare/v0.3.1...v0.4.0
[0.3.1]: https://github.com/pr1m8/pyfetcher/releases/tag/v0.3.1
