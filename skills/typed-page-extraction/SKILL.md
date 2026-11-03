---
name: typed-page-extraction
description: Build, integrate, debug, or document fetchkit PageDocument extraction using CSS or XPath Selection, SelectorRule, ModelExtractor, LinkRule, ImageRule, CollectionRule, GalleryRule, cardinality, conversions, custom selector functions, WebPoet page objects, or typed URL patterns. Use after content is fetched; use Scrapy or HTTP skills for execution and scheduling.
---

# fetchkit Typed Page Extraction

Turn fetched HTML into reusable typed data without coupling extraction rules to
a particular network engine.

## Choose the smallest extraction surface

- Use ``PageDocument`` and ``Selection`` for direct CSS/XPath exploration.
- Use ``SelectorRule`` for serializable selectors with explicit cardinality and
  conversion.
- Use ``ModelExtractor`` when several rules populate a typed Pydantic model.
- Use ``LinkRule``, ``ImageRule``, ``CollectionRule``, and ``GalleryRule`` for
  reusable web and media structures.
- Use a WebPoet page object when extraction is dependency-injected across a
  Scrapy or application workflow.

Create documents from fetchkit or Scrapy responses so the same extractor works
regardless of transport. Preserve the response URL as the base for resolving
relative links.

## Make contracts explicit

Set whether a rule expects one, optional, or many values. Choose text, HTML,
attribute, or URL extraction deliberately, and attach conversion at the rule
boundary. Do not silently collapse multiple matches or treat a missing required
value as an empty string.

Use ``URLPattern`` for typed path matching and ``URLTemplate`` for generation.
Use ``$url-workflows`` when normalization, foreign URL types, or reusable URL
rules are the main concern.

## Add bespoke behavior safely

Register named functions in a ``SelectorFunctionRegistry`` and inject the
registry into extraction. Keep serializable rules referring to stable function
names; do not embed arbitrary callables in job payloads. Put site-specific
selector sets and patterns in configuration or versioned templates rather than
adding host checks to core models.

## Validate extraction

Use local HTML fixtures that cover missing, single, and repeated matches,
relative URLs, invalid conversions, and custom functions.

```bash
pdm run pytest tests/test_documents.py tests/test_url_patterns.py -q
pdm run pytest tests/test_webpoet_integration.py -q
pdm run ruff check src/ tests/ examples/
```

Read ``docs/page-extraction.rst`` and ``examples/page_extraction.py`` before
changing the public rule model. Use ``$http-fetch`` to obtain ordinary pages
and ``$scrapy-crawl`` when the crawler engine owns execution.
