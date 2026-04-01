MCP Server
==========

fetchkit ships as a Model Context Protocol (MCP) server, enabling AI agents
to fetch, scrape, extract, and download web content autonomously.

Installation
------------

.. code-block:: bash

   pip install 'fetchkit[mcp]'

Running
-------

**stdio** (Claude Desktop, Claude Code):

.. code-block:: bash

   pyfetcher-mcp

**HTTP** (LangChain, remote agents):

.. code-block:: bash

   pyfetcher-mcp --http 8000

**Makefile**:

.. code-block:: bash

   make mcp          # stdio
   make mcp-http     # HTTP on port 8000

Tools (16)
----------

.. list-table::
   :header-rows: 1
   :widths: 20 40 20

   * - Tool
     - Description
     - Returns
   * - ``fetch_url``
     - Fetch URL with browser headers
     - FetchResult
   * - ``fetch_multiple``
     - Batch fetch with concurrency
     - list[FetchResult]
   * - ``scrape_css``
     - CSS selector extraction
     - ScrapeResult
   * - ``scrape_links``
     - Link harvesting with classification
     - LinksResult
   * - ``scrape_text``
     - Readable text extraction
     - str
   * - ``scrape_metadata``
     - Page metadata + Open Graph
     - MetadataResult
   * - ``scrape_forms``
     - Form field extraction
     - FormsResult
   * - ``scrape_table``
     - HTML table parsing
     - TableResult
   * - ``check_robots``
     - robots.txt rule checking
     - RobotsResult
   * - ``parse_sitemap``
     - XML sitemap parsing
     - SitemapResult
   * - ``generate_headers``
     - Browser header preview
     - HeadersResult
   * - ``list_profiles``
     - All browser profiles
     - list[ProfileInfo]
   * - ``random_user_agent``
     - Random UA string
     - str
   * - ``extract_article``
     - Article text + markdown
     - ArticleResult
   * - ``convert_html``
     - HTML to markdown/plaintext
     - str
   * - ``download_file``
     - File download with checksum
     - DownloadResult

Resources
---------

- ``pyfetcher://profiles`` -- All browser profiles with details
- ``pyfetcher://profiles/{name}`` -- Headers for a specific profile
- ``pyfetcher://backends`` -- Backend capabilities table
- ``pyfetcher://version`` -- Version and feature info

Prompts
-------

- ``web_research(topic)`` -- Research a topic by fetching and analyzing pages
- ``site_audit(url)`` -- Audit a website's structure, metadata, and links
- ``scrape_guide(url, goal)`` -- Guide for scraping specific data
- ``compare_pages(url1, url2)`` -- Compare two web pages

Claude Desktop Configuration
-----------------------------

Add to ``claude_desktop_config.json``:

.. code-block:: json

   {
     "mcpServers": {
       "pyfetcher": {
         "command": "pyfetcher-mcp",
         "args": []
       }
     }
   }

LangChain Integration
---------------------

.. code-block:: python

   from langchain_mcp_adapters import MultiServerMCPClient
   from langgraph.prebuilt import create_react_agent

   client = MultiServerMCPClient({
       "pyfetcher": {"transport": "http", "url": "http://localhost:8000/mcp"}
   })
   tools = await client.get_tools()
   agent = create_react_agent(model, tools)
