fetchkit
========

**Agentic web infrastructure for autonomous fetching, scraping, and content acquisition.**

.. mermaid::

   flowchart LR
       Agent["🤖 AI Agent"] --> MCP["MCP Server<br/>16 tools · 4 resources · 4 prompts"]
       MCP --> Core

       subgraph Core["fetchkit Core"]
           direction TB
           Fetch["⚡ Fetch<br/>4 backends · headers · retry · rate limit"]
           Scrape["🔍 Scrape<br/>CSS · links · forms · tables · robots"]
           Extract["📄 Extract<br/>trafilatura · markdown · media meta"]
           Download["💾 Download<br/>yt-dlp · gallery-dl · HTTP streaming"]
       end

       Core --> Infra

       subgraph Infra["Infrastructure"]
           direction TB
           PG[("PostgreSQL<br/>jobs · pages · media")]
           MinIO[("MinIO<br/>object storage")]
       end

       style MCP fill:#E74C3C,color:#fff
       style Fetch fill:#4A90D9,color:#fff
       style Scrape fill:#7B68EE,color:#fff
       style Extract fill:#2ECC71,color:#fff
       style Download fill:#F39C12,color:#fff
       style PG fill:#336791,color:#fff
       style MinIO fill:#C72C48,color:#fff

|

.. code-block:: bash

   pip install fetchkit              # Core library
   pip install 'fetchkit[mcp]'       # + MCP server for AI agents
   pip install 'fetchkit[pipeline]'  # + Postgres + MinIO pipeline
   pip install 'fetchkit[full]'      # Everything

Import as ``import pyfetcher``.

Key Features
------------

.. grid:: 2

   .. grid-item-card:: Reusable Clients
      :link: clients
      :link-type: doc

      Lifecycle-managed sync and async clients with connection pooling,
      HTTP/2 negotiation, streaming I/O, FastAPI injection, and bounded
      iteration over large generators.

   .. grid-item-card:: Adapter Boundaries
      :link: adapters
      :link-type: doc

      Custom HTTP transports, Scrapy engine bridging, provider-neutral
      acquisition, middleware, and focused skill boundaries.

   .. grid-item-card:: Durable Jobs and Flows
      :link: durable-flows
      :link-type: doc

      Versioned templates, dynamic pagination and collection fan-out, portable
      artifacts, WebPoet, Redis queue/status durability, Temporal, and
      OpenTelemetry.

   .. grid-item-card:: Cross-language Contracts
      :link: contracts
      :link-type: doc

      Versioned JSON Schema, generated TypeScript clients, provider discovery,
      durable messages, and gRPC service bindings.

   .. grid-item-card:: Content Acquisition
      :link: acquisition
      :link-type: doc

      Discover and select direct HTTP, yt-dlp, or gallery-dl providers with
      typed policy, credential references, provenance, and progress events.

   .. grid-item-card:: 🤖 MCP Server
      :link: mcp
      :link-type: doc

      16 tools for AI agents. Fetch, scrape, extract, download --
      all with structured Pydantic outputs. Works with Claude Desktop,
      Claude Code, and LangChain.

   .. grid-item-card:: 🔍 Web Scraping
      :link: page-extraction
      :link-type: doc

      Typed CSS/XPath rules, link filtering, URL patterns, responsive images,
      gallery collections, forms, tables, robots, and sitemaps.

   .. grid-item-card:: 🌐 Browser Headers
      :link: headers
      :link-type: doc

      11 browser profiles with consistent User-Agent, Client Hints,
      and Sec-Fetch-* headers. Market-share-weighted rotation.
      TLS fingerprinting via curl_cffi.

   .. grid-item-card:: ⚡ Pipeline
      :link: pipeline
      :link-type: doc

      Concurrent crawl → scrape → download workers over durable Postgres
      jobs. URL frontier with dedup, politeness, and RSS/Atom feed monitoring.

   .. grid-item-card:: 📄 Content Extraction
      :link: api/extractors_api
      :link-type: doc

      trafilatura + readability-lxml fallback, HTML to markdown/plaintext,
      newspaper3k article metadata, audio/video/image/PDF metadata.

   .. grid-item-card:: 💾 Downloaders
      :link: api/downloaders
      :link-type: doc

      Deep yt-dlp integration with progress hooks. gallery-dl for
      170+ image sites. Direct HTTP streaming with SHA-256 checksums.

.. toctree::
   :maxdepth: 2
   :caption: Getting Started
   :hidden:

   quickstart
   clients
   acquisition
   adapters
   durable-flows
   contracts
   mcp

.. toctree::
   :maxdepth: 2
   :caption: Core Features
   :hidden:

   headers
   scraping
   urls
   page-extraction

.. toctree::
   :maxdepth: 2
   :caption: Infrastructure
   :hidden:

   pipeline
   infrastructure

.. toctree::
   :maxdepth: 2
   :caption: Interfaces
   :hidden:

   cli
   tui

.. toctree::
   :maxdepth: 2
   :caption: API Reference
   :hidden:

   api/index

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
