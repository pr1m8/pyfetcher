---
name: url-workflows
description: Build, integrate, debug, or document fetchkit URL conversion, normalization, relative resolution, canonicalization, fingerprints, URLAdapterRegistry, URLRule, URLPattern, URLTemplate, Pydantic AnyUrl, urllib, httpx, yarl, w3lib, or tldextract interoperability. Use for URL contracts and manipulation, not network execution.
---

# fetchkit URL Workflows

Use one canonical URL contract while allowing application-specific libraries at
the edges.

## Preserve the canonical invariant

``URL`` represents absolute HTTP or HTTPS URLs. Construct it directly for known
strings, or use ``URL.from_value`` for supported foreign values. Resolve
relative references against an explicit base before they cross a subsystem
boundary.

Convert to or from Pydantic URLs, ``urllib.parse`` results, HTTPX URLs, yarl,
w3lib, and tldextract through adapters. Keep optional integrations lazy.

## Extend through local registries

Create a ``URLAdapterRegistry`` for application-specific URL types and inject
it where conversion occurs. Avoid changing a process-global registry and avoid
``isinstance`` ladders spread across clients, extractors, and jobs.

Use:

- ``URLRule`` and ``apply_url_rules`` for reusable normalization or routing.
- ``URLPattern`` for typed recognition and path parameter extraction.
- ``URLTemplate`` for safe generation from validated values.
- Canonicalization and fingerprints for deduplication, with query policy made
  explicit rather than assumed.

Do not make normalization perform I/O or hide redirects. Network-observed URLs
belong in response or provenance data.

## Validate URL behavior

Test round trips, unicode and percent encoding, default ports, relative paths,
query ordering, fragments, unsupported schemes, and optional-library absence.

```bash
pdm run pytest tests/test_url_adapters.py tests/test_url_patterns.py -q
pdm run pytest tests/test_contracts.py -q
pdm run ruff check src/ tests/ examples/
```

Read ``docs/urls.rst`` and ``examples/url_interoperability.py`` before changing
adapters. Use ``$http-fetch`` only when the task proceeds to network execution.
