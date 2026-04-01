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

   .. grid-item-card:: 🤖 MCP Server
      :link: mcp
      :link-type: doc

      16 tools for AI agents. Fetch, scrape, extract, download --
      all with structured Pydantic outputs. Works with Claude Desktop,
      Claude Code, and LangChain.

   .. grid-item-card:: 🔍 Web Scraping
      :link: scraping
      :link-type: doc

      CSS selectors, link harvesting, form parsing, table extraction,
      robots.txt, sitemap parsing, and readable text extraction.

   .. grid-item-card:: 🌐 Browser Headers
      :link: headers
      :link-type: doc

      11 browser profiles with consistent User-Agent, Client Hints,
      and Sec-Fetch-* headers. Market-share-weighted rotation.
      TLS fingerprinting via curl_cffi.

   .. grid-item-card:: ⚡ Pipeline
      :link: pipeline
      :link-type: doc

      Event-driven crawl → scrape → download stages via Postgres
      LISTEN/NOTIFY. URL frontier with dedup, politeness, and
      RSS/Atom feed monitoring.

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
   mcp

.. toctree::
   :maxdepth: 2
   :caption: Core Features
   :hidden:

   headers
   scraping

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
