Quick Start
===========

Installation
------------

Install with pip or PDM:

.. code-block:: bash

   pip install fetchkit
   # or
   pdm add fetchkit

With optional dependencies:

.. code-block:: bash

   pip install 'fetchkit[tui]'           # Textual TUI
   pip install 'fetchkit[metadata]'       # extruct + w3lib
   pip install 'fetchkit[pipeline]'       # Postgres + MinIO pipeline
   pip install 'fetchkit[downloaders]'    # yt-dlp + gallery-dl
   pip install 'fetchkit[full]'           # Everything

Import as ``pyfetcher``:

.. code-block:: python

   from pyfetcher import fetch, FetchRequest

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

   pip install 'fetchkit[curl]'

.. code-block:: python

   response = fetch(FetchRequest(url="https://example.com", backend="curl_cffi"))

cloudscraper (Cloudflare bypass):

.. code-block:: bash

   pip install 'fetchkit[cloudscraper]'

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

MCP Server
----------

Run fetchkit as an MCP server for AI agents:

.. code-block:: bash

   pip install 'fetchkit[mcp]'
   pyfetcher-mcp              # stdio for Claude Desktop
   pyfetcher-mcp --http 8000  # HTTP for LangChain

All fetch, scrape, and extraction tools become available to AI agents
as structured MCP tools.
