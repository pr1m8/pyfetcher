Typed URLs and interoperability
===============================

``pyfetcher.URL`` is the canonical URL value used by fetchkit's request,
extraction, crawling, and acquisition layers. It accepts many common URL
representations at the boundary, but always validates the result as an absolute
HTTP or HTTPS URL. This keeps queue keys, deduplication, selectors, and provider
adapters consistent without requiring every integration to use the same URL
library internally.

Core adapters
-------------

Use the named constructors when the source type is known. ``from_value`` is the
broad adapter for framework and third-party objects.

.. code-block:: python

   from urllib.parse import urlsplit
   from urllib.request import Request

   import httpx
   from pydantic import AnyHttpUrl

   from pyfetcher import URL

   standard = URL.from_urllib(urlsplit("https://example.com/gallery/1"))
   pydantic_url = URL.from_pydantic(AnyHttpUrl("https://example.com/gallery/2"))
   httpx_url = URL.from_httpx(httpx.URL("https://example.com/gallery/3"))
   request_url = URL.from_request(Request("https://example.com/gallery/4"))

   assert standard.host == pydantic_url.host == httpx_url.host == request_url.host

The constructor and ``URL.from_value`` also understand:

* ``str``, ``bytes``, ``bytearray``, and ``memoryview`` values;
* all string and bytes results from ``urllib.parse``;
* objects implementing ``geturl()``, ``get_full_url()``, ``to_text()``, or
  ``unsplit()``;
* request or response objects exposing ``url`` or ``final_url``; and
* ordinary URL value objects with a meaningful string representation, including
  Starlette URLs and similar framework types.

Those structural adapters cover Requests, urllib, HTTPX, Scrapy, Hyperlink,
RFC 3986 libraries, and most small framework URL wrappers without adding them as
dependencies. Explicit ``from_httpx`` and ``from_yarl`` methods additionally
check their input type and make intent visible to type checkers.

Bespoke adapters
-----------------

Application-specific URL objects can use an explicit ``URLAdapterRegistry``.
The first matching adapter wins, adapters may be selected by concrete type or
an arbitrary predicate, and the converted value is fed back through normal URL
validation. Registries belong to the application instead of global process
state.

.. code-block:: python

   from dataclasses import dataclass

   from pyfetcher import URL, URLAdapter, URLAdapterRegistry

   @dataclass(frozen=True)
   class AssetLocation:
       value: str

   adapters = URLAdapterRegistry()
   adapters.register_type(
       AssetLocation,
       lambda value: value.value,
       name="asset-location",
   )
   adapters.register(
       URLAdapter(
           "mapping-location",
           predicate=lambda value: isinstance(value, dict) and "location" in value,
           convert=lambda value: value["location"],
       )
   )

   asset = URL.from_value(
       AssetLocation("images/1.webp"),
       base="https://cdn.example.com/",
       adapters=adapters,
   )

The same registry can be injected into ``FetchClient`` or ``AsyncFetchClient``
as ``url_adapters=adapters``. This makes bespoke values work for client base
URLs, individual calls, streams, and ``AsyncFetchClient.imap``.

Conditional normalization rules
--------------------------------

``apply_url_rules`` accepts both plain URL-to-URL functions and declaratively
selected ``URLRule`` values. A rule can select by scheme, exact host or parent
domain, path regular expression, and a custom predicate. Transform functions
may return any URL-like value understood by the same adapter registry.

.. code-block:: python

   from pyfetcher import URLRule, apply_url_rules

   normalized = apply_url_rules(
       "https://img.example.com/images/1.jpg?utm_source=crawl",
       (
           lambda url: url.without_query("utm_source"),
           URLRule(
               "prefer-large-images",
               hosts=("example.com",),
               path_pattern=r"^/images/",
               predicate=lambda url: url.query_params.get("size") != ["large"],
               transform=lambda url: url.add_query(size="large"),
           ),
       ),
   )

   assert str(normalized) == "https://img.example.com/images/1.jpg?size=large"

This is the runtime policy layer for reusable site or media conventions.
``URLPattern`` remains the separate typed matching and reversible-template
layer for extracting values from page, gallery, playlist, or pagination URLs.

Relative URLs
-------------

Relative references are accepted only when an absolute base is supplied. Use
``from_value`` at an adapter boundary or ``join`` when a base URL is already
available.

.. code-block:: python

   page = URL("https://example.com/galleries/42/page/3")

   image = URL.from_value("../cover.webp", base=page)
   next_page = page.join("../page/4")

   assert str(image) == "https://example.com/galleries/42/cover.webp"
   assert str(next_page) == "https://example.com/galleries/42/page/4"

Conversions back to other libraries
-----------------------------------

The normalized value can be converted without reparsing it in application
code.

.. code-block:: python

   from pydantic import AnyHttpUrl

   url = URL("https://example.com/items?q=web")

   urllib_parts = url.to_urllib()
   validated = url.to_pydantic(AnyHttpUrl)
   httpx_value = url.to_httpx()

   assert urllib_parts.hostname == "example.com"
   assert isinstance(validated, AnyHttpUrl)
   assert str(httpx_value) == str(url)

Install ``fetchkit[url-tools]`` for yarl conversion, Scrapy-compatible w3lib
canonicalization, and public-suffix-aware domain decomposition:

.. code-block:: bash

   pip install 'fetchkit[url-tools]'

.. code-block:: python

   url = URL("https://images.cdn.example.co.uk/a?b=2&a=1#preview")

   yarl_value = url.to_yarl()
   canonical = url.canonicalize()
   parts = url.domain_parts()

   assert str(URL.from_yarl(yarl_value)) == str(url)
   assert str(canonical) == "https://images.cdn.example.co.uk/a?a=1&b=2"
   assert parts.host == "images.cdn.example.co.uk"
   assert parts.registered_domain == "example.co.uk"

``tldextract`` results contain domain components rather than a scheme, port,
path, query, or fragment. ``DomainParts.from_tldextract`` preserves that honest
boundary; ``URL.from_tldextract`` builds a complete URL only when the caller
supplies or accepts those missing values.

.. code-block:: python

   import tldextract

   from pyfetcher import DomainParts

   extracted = tldextract.extract("assets.example.org")
   parts = DomainParts.from_tldextract(extracted)
   url = URL.from_tldextract(extracted, scheme="https", path="media/1.webp")

   assert parts.host == "assets.example.org"
   assert str(url) == "https://assets.example.org/media/1.webp"

Manipulation and stable identity
--------------------------------

URL operations return new immutable values. Query helpers preserve repeated and
blank parameters, while canonicalization and fingerprints are useful for crawl
frontiers, caches, and idempotency keys.

.. code-block:: python

   url = URL("https://example.com/items?tag=a&tag=b")

   filtered = url.without_query("tag").add_query(page=2, empty=None)
   storage_key = filtered.fingerprint()

   assert filtered.query_params == {"page": ["2"], "empty": [""]}
   assert len(storage_key) == 64

For Scrapy and other crawling engines, adapt request/response URLs into
``pyfetcher.URL`` before matching, deduplication, or extraction. For yt-dlp and
gallery-dl, pass ``str(url)`` at the provider boundary and retain the normalized
URL in metadata or artifact provenance.

See ``examples/url_interoperability.py`` for a complete offline example.
