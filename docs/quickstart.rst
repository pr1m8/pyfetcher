Quick Start
===========

Installation
------------

Install with pip or PDM:

.. code-block:: bash

   pip install pyfetcher
   # or
   pdm add pyfetcher

With optional dependencies:

.. code-block:: bash

   pip install 'pyfetcher[tui]'       # Textual TUI
   pip install 'pyfetcher[metadata]'   # extruct + w3lib
   pip install 'pyfetcher[all]'        # Everything

Basic Usage
-----------

Simple fetch:

.. code-block:: python

   from pyfetcher import fetch, FetchRequest

   response = fetch("https://example.com")
   print(response.status_code, response.text[:100])

With a browser profile:

.. code-block:: python

   from pyfetcher.headers.browser import BrowserHeaderProvider
   from pyfetcher.fetch.service import FetchService

   service = FetchService(header_provider=BrowserHeaderProvider("chrome_win"))
   response = service.fetch(FetchRequest(url="https://example.com"))

Async fetch:

.. code-block:: python

   import asyncio
   from pyfetcher import afetch

   async def main():
       response = await afetch("https://example.com")
       print(response.status_code)

   asyncio.run(main())

Optional Backends
-----------------

curl_cffi (TLS fingerprint impersonation):

.. code-block:: bash

   pip install 'pyfetcher[curl]'

.. code-block:: python

   response = fetch(FetchRequest(url="https://example.com", backend="curl_cffi"))

cloudscraper (Cloudflare bypass):

.. code-block:: bash

   pip install 'pyfetcher[cloudscraper]'

.. code-block:: python

   response = fetch(FetchRequest(url="https://protected-site.com", backend="cloudscraper"))

Rate-Limited Fetching
---------------------

.. code-block:: python

   from pyfetcher.fetch.service import FetchService
   from pyfetcher.ratelimit.limiter import DomainRateLimiter, RateLimitPolicy

   limiter = DomainRateLimiter(
       default_policy=RateLimitPolicy(requests_per_second=2.0, burst=5)
   )
   service = FetchService(rate_limiter=limiter)
   response = service.fetch(FetchRequest(url="https://example.com"))
