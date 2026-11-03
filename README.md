<div align="center">

# fetchkit

**Agentic web infrastructure for autonomous fetching, scraping, and content acquisition.**

Give AI agents the power to fetch, scrape, extract, and download anything on the web -- with realistic browser fingerprints, structured outputs, and a full crawl-scrape-download pipeline backed by Postgres and MinIO.

[![PyPI](https://img.shields.io/pypi/v/fetchkit?style=flat-square&logo=pypi&logoColor=white&color=blue)](https://pypi.org/project/fetchkit/)
[![Python](https://img.shields.io/pypi/pyversions/fetchkit?style=flat-square&logo=python&logoColor=white)](https://pypi.org/project/fetchkit/)
[![Docs](https://img.shields.io/github/actions/workflow/status/pr1m8/pyfetcher/pages.yml?branch=main&style=flat-square&logo=github&label=docs)](https://pr1m8.github.io/pyfetcher/)
[![CI](https://img.shields.io/github/actions/workflow/status/pr1m8/pyfetcher/ci.yml?branch=main&style=flat-square&logo=github&label=CI)](https://github.com/pr1m8/pyfetcher/actions/workflows/ci.yml)
[![License](https://img.shields.io/github/license/pr1m8/pyfetcher?style=flat-square&color=green)](https://github.com/pr1m8/pyfetcher/blob/main/LICENSE)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json&style=flat-square)](https://github.com/astral-sh/ruff)
[![PDM](https://img.shields.io/badge/pdm-managed-blueviolet?style=flat-square)](https://pdm-project.org)
[![MCP](https://img.shields.io/badge/MCP-16_tools-orange?style=flat-square)](#mcp-server-ai-agent-integration)

---

[MCP Server](#mcp-server-ai-agent-integration) | [Quick Start](#quick-start) | [Pipeline](#pipeline) | [CLI](#cli) | [Documentation](https://pr1m8.github.io/pyfetcher/) | [Changelog](CHANGELOG.md) | [Examples](examples/)

</div>

## Why fetchkit?

**The problem**: AI agents need to interact with the web -- fetch pages, extract data, download files -- but existing tools aren't designed for autonomous operation. They lack structured outputs, realistic browser fingerprints, and pipeline orchestration.

**fetchkit solves this** by providing:

1. **MCP Server** -- 16 tools that any AI agent (Claude, LangChain, LangGraph) can call directly. Structured Pydantic outputs, not raw HTML.
2. **Realistic browser identity** -- 11 profiles with consistent UA + Client Hints + Sec-Fetch-\* headers. TLS fingerprinting via curl_cffi. Cloudflare bypass.
3. **Full pipeline** -- Concurrent crawl -> scrape -> download workers backed by Postgres job queues and MinIO object storage.
4. **Typed acquisition providers** -- direct HTTP, yt-dlp, and gallery-dl behind capability discovery, provenance, credential references, and async progress events.
5. **Reusable durable jobs** -- versioned pagination, media-collection, and site-search templates with portable artifacts; run locally or through optional Redis Streams and Temporal adapters.
6. **Typed page extraction** -- chainable CSS/XPath selectors, explicit cardinality and conversion, filtered links, reversible URL patterns, responsive images, and gallery collections.
7. **URL interoperability** -- one immutable HTTP/HTTPS value across Pydantic,
   urllib, HTTPX, yarl, tldextract, Requests/Scrapy-style objects, and structural
   adapters for other URL libraries.

## Project status

fetchkit is in active alpha development. The typed request/response contracts,
HTTP transports, reusable clients, scraping helpers, and CLI are usable today.
The database pipeline, browser automation, downloader integrations, and MCP
server are broader optional layers and may evolve more quickly. The PyPI package
is named `fetchkit`; Python imports use `pyfetcher`.

The extension model deliberately separates ordinary HTTP transports, the
optional Scrapy crawler-engine bridge, and acquisition providers such as
yt-dlp and gallery-dl. See [adapters and execution engines](docs/adapters.rst)
for the implemented transport, middleware, provider, and focused-skill
boundaries.

```bash
pip install 'fetchkit[mcp]'     # AI agent integration
pip install 'fetchkit[full]'    # Everything
```

## Highlights

```bash
pip install fetchkit                   # Core: fetch, scrape, headers
pip install 'fetchkit[mcp]'            # + MCP server for AI agents
pip install 'fetchkit[pipeline]'       # + Postgres job queue + MinIO storage
pip install 'fetchkit[full]'           # Everything including yt-dlp, Playwright, etc.
```

### Fetch with realistic browser headers

```python
from pyfetcher import fetch

response = fetch("https://example.com")
print(response.status_code, response.ok)
# Sends Chrome-like headers with Client Hints, Sec-Fetch-*, UA rotation automatically
```

### Reuse an async HTTP/2 connection pool

```python
from pyfetcher import AsyncFetchClient, PoolPolicy

async with AsyncFetchClient(
    http2=True,
    pool=PoolPolicy(max_connections=100, concurrency=20),
) as client:
    response = await client.get("https://example.com")
    print(response.status_code, response.http_version)
```

Keep one client for the lifetime of a service. HTTP/2 is negotiated with the
origin and may fall back to HTTP/1.1; `response.http_version` reports what was
actually used.

### Scrape anything

```python
from pyfetcher.scrape import extract_links, extract_text, extract_readable_text

links = extract_links(html, base_url="https://example.com")  # all links with internal/external tags
titles = extract_text(html, "h1")                             # CSS selector extraction
article = extract_readable_text(html)                         # strips scripts, nav, ads
```

For reusable typed extraction, install `fetchkit[selectors]`:

```python
from pyfetcher import PageDocument, SelectorRule

page = PageDocument(html, url="https://example.com/gallery/42")
title = SelectorRule(
    css="h1",
    output="text",
    cardinality="one",
    transforms=("normalize_whitespace",),
).apply(page)

image_urls = page.xpath("//article//img/@src").getall()
```

### 4 HTTP backends -- pick the right one for the job

```python
from pyfetcher import FetchRequest, fetch

response = fetch("https://example.com")                                        # httpx (default, HTTP/2)
response = fetch(FetchRequest(url="https://example.com", backend="aiohttp"))   # aiohttp (pure async)
response = fetch(FetchRequest(url="https://example.com", backend="curl_cffi")) # TLS fingerprinting
response = fetch(FetchRequest(url="https://example.com", backend="cloudscraper")) # Cloudflare bypass
```

### Download media with yt-dlp & gallery-dl

```python
from pyfetcher.downloaders.ytdlp import YtdlpDownloader
from pyfetcher.downloaders.gallerydl import GalleryDlDownloader

# Video/audio with progress tracking
yt = YtdlpDownloader()
info = await yt.extract_info("https://youtube.com/watch?v=...")    # metadata only
results = await yt.download("https://youtube.com/watch?v=...",     # full download
    output_dir="./media", progress_callback=lambda p: print(p.status))

# Image galleries (170+ supported sites)
gdl = GalleryDlDownloader()
results = await gdl.download("https://imgur.com/gallery/...", output_dir="./images")
```

### MCP Server -- give AI agents web superpowers

```bash
pyfetcher-mcp                  # stdio for Claude Desktop / Claude Code
pyfetcher-mcp --http 8000      # HTTP for LangChain / remote agents
```

```python
# LangChain integration
from langchain_mcp_adapters import MultiServerMCPClient
client = MultiServerMCPClient({"pyfetcher": {"transport": "http", "url": "http://localhost:8000/mcp"}})
tools = await client.get_tools()  # 16 structured tools ready for any agent
```

## Features

### Core Library

| Feature             | Description                                                                                                                               |
| ------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| **Browser Headers** | 11 profiles (Chrome/Firefox/Safari/Edge) across 5 platforms. Consistent UA + Client Hints + Sec-Fetch-\*. Market-share-weighted rotation. |
| **4 Backends**      | `httpx` (default, HTTP/2), `aiohttp` (async), `curl_cffi` (TLS fingerprint), `cloudscraper` (CF bypass)                                   |
| **Reusable Clients** | Sync and async lifecycle clients with connection pooling, HTTP/2 negotiation, base URLs, and shared defaults                           |
| **Streaming I/O**   | Sync/async response iterators plus bytes, text, sync-generator, and async-generator request content                                     |
| **Acquisition**     | Direct, yt-dlp, and gallery-dl providers with discovery, native options, provenance, credential references, and progress events       |
| **Middleware**      | Composable sync/async request-response layers shared by fetch and acquisition services                                                |
| **Job runtime**     | Versioned templates plus a service, status store, bounded worker, cancellation, retries, and dynamic child fan-out                 |
| **Artifacts**       | Blob references and ordered gallery, playlist, search, and page collections without queueing large bytes                            |
| **Contracts**       | Versioned JSON Schema catalog for generated TypeScript/Zod types, provider discovery, queues, and RPC boundaries                  |
| **Rate Limiting**   | Per-domain + global token bucket with configurable burst                                                                                  |
| **Retry**           | Exponential backoff via Tenacity with configurable status codes                                                                           |
| **Scraping**        | BeautifulSoup helpers plus typed Parsel CSS/XPath rules, URL/link filtering, images, and collections                                    |
| **Typed URLs**      | Pydantic, urllib, HTTPX, yarl, tldextract, request/response adapters, relative resolution, and canonical identity                      |
| **Metadata**        | HTML meta, Open Graph, JSON-LD, microdata, RDFa, Dublin Core                                                                              |
| **CLI**             | Fetch, scrape, acquire, inspect templates, and export portable contracts                                                                  |
| **TUI**             | Interactive Textual terminal UI for building and inspecting requests                                                                      |

### Infrastructure (optional extras)

| Feature          | Extra           | Description                                                                 |
| ---------------- | --------------- | --------------------------------------------------------------------------- |
| **Pipeline**     | `[pipeline]`    | Concurrent Crawl -> Scrape -> Download workers over durable Postgres jobs  |
| **Database**     | `[db]`          | SQLAlchemy 2.0 async + Alembic. Jobs, pages, media, hosts, feeds, URL dedup |
| **Object Store** | `[store]`       | MinIO/S3 via aioboto3. Upload, download, presigned URLs                     |
| **Downloaders**  | `[downloaders]` | yt-dlp (progress hooks, info_dict) + gallery-dl (170+ sites)                |
| **Extractors**   | `[extractors]`  | trafilatura + readability-lxml fallback, html2text, markdownify             |
| **Media**        | `[media]`       | Audio (mutagen), video (pymediainfo), image (exifread), PDF (pypdf)         |
| **Browser**      | `[browser]`     | Playwright + stealth for JS-heavy sites                                     |
| **Scrapy**       | `[scrapy]`      | Optional request/response conversion and crawler-engine bridge              |
| **WebPoet**      | `[web-poet]`    | Page-object HTTP adapter and allowlisted standalone page execution           |
| **Scrapy-Poet**  | `[scrapy-poet]` | Complete WebPoet dependency injection and rules in Scrapy crawls             |
| **Selectors**    | `[selectors]`    | Parsel-backed CSS/XPath page documents and typed extraction rules             |
| **Redis queue**  | `[redis]`       | Streams consumer groups, leases, dead letters, and delayed retries           |
| **Temporal**     | `[temporal]`    | Durable dynamic flows with side effects isolated in activities               |
| **Job API**      | `[api]`         | FastAPI control plane, worker health, cancellation, paging, and SSE events    |
| **Telemetry**    | `[observe]`     | OTLP traces and metrics, W3C propagation, Tempo and log correlation          |
| **Feeds**        | `[feeds]`       | RSS/Atom monitoring with adaptive polling                                   |
| **Crawler**      | `[pipeline]`    | URL frontier, spider + router, dedup, politeness, sitemap discovery         |

## Installation

```bash
pip install fetchkit
```

All optional extras:

```bash
pip install 'fetchkit[tui]'            # Textual TUI
pip install 'fetchkit[curl]'           # curl_cffi TLS fingerprinting
pip install 'fetchkit[cloudscraper]'   # Cloudflare bypass
pip install 'fetchkit[db]'             # Postgres + SQLAlchemy + Alembic
pip install 'fetchkit[store]'          # MinIO/S3 object storage
pip install 'fetchkit[pipeline]'       # db + store (full pipeline)
pip install 'fetchkit[downloaders]'    # yt-dlp + gallery-dl
pip install 'fetchkit[extractors]'     # trafilatura, readability, html2text
pip install 'fetchkit[media]'          # Audio/video/image/PDF metadata
pip install 'fetchkit[browser]'        # Playwright + stealth
pip install 'fetchkit[scrapy]'         # Scrapy crawler-engine bridge
pip install 'fetchkit[web-poet]'       # WebPoet page-object adapter
pip install 'fetchkit[scrapy-poet]'    # WebPoet + full Scrapy integration
pip install 'fetchkit[selectors]'      # Typed CSS/XPath page extraction
pip install 'fetchkit[url-tools]'      # yarl, w3lib canonicalization, public-suffix domains
pip install 'fetchkit[redis]'          # Redis Streams job queue
pip install 'fetchkit[temporal]'       # Temporal durable flow runtime
pip install 'fetchkit[api]'            # FastAPI durable-job control plane
pip install 'fetchkit[observe]'        # OpenTelemetry OTLP traces + metrics
pip install 'fetchkit[feeds]'          # RSS/Atom feed parsing
pip install 'fetchkit[langchain]'      # LangChain MCP client adapters
pip install 'fetchkit[full]'           # Everything
```

## Quick Start

### Fetch

```python
from pyfetcher import fetch, afetch, FetchRequest
import asyncio

# Sync
response = fetch("https://example.com")
print(response.status_code, response.ok)

# Async
response = asyncio.run(afetch("https://example.com"))
```

The functions are convenient for scripts. Long-running applications should
reuse a client so keepalive and HTTP/2 connections remain pooled:

```python
import asyncio
from pyfetcher import AsyncFetchClient

async def main() -> None:
    async with AsyncFetchClient(base_url="https://api.example.com/v1/") as client:
        response = await client.get("users")
        print(response.status_code, response.http_version)

asyncio.run(main())
```

### Streaming responses and request bodies

Response bodies can be consumed as normalized chunks, raw bytes, or
incrementally decoded text:

```python
from pyfetcher import AsyncFetchClient, StreamPolicy

async with AsyncFetchClient(stream=StreamPolicy(max_bytes=10_000_000)) as client:
    async for data in client.iter_bytes("GET", "https://example.com/large-file"):
        await destination.write(data)
```

Uploads accept ordinary generators and async generators without first joining
the whole body in memory:

```python
async def content():
    yield b"first chunk\n"
    yield b"second chunk\n"

async with AsyncFetchClient() as client:
    response = await client.post("https://example.com/upload", content=content())
```

For a large or generated URL source, `imap()` keeps both source consumption and
network concurrency bounded:

```python
async with AsyncFetchClient() as client:
    async for response in client.imap(url_generator(), concurrency=20, ordered=False):
        print(response.final_url, response.status_code)
```

### FastAPI lifespan and dependency injection

Create one client in the FastAPI lifespan, store it in application state, and
inject that same pooled instance into routes:

```python
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from pyfetcher import AsyncFetchClient

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with AsyncFetchClient(http2=True) as client:
        app.state.fetcher = client
        yield

app = FastAPI(lifespan=lifespan)

def get_fetcher(request: Request) -> AsyncFetchClient:
    return request.app.state.fetcher

Fetcher = Annotated[AsyncFetchClient, Depends(get_fetcher)]

@app.get("/title")
async def title(fetcher: Fetcher) -> dict[str, str | None]:
    response = await fetcher.get("https://example.com")
    return {"protocol": response.http_version, "html": response.text}
```

### Provider-neutral acquisition

Select direct HTTP, yt-dlp, or gallery-dl explicitly, or allow conservative
URL-based capability selection:

```python
from pyfetcher import AcquisitionRequest, AcquisitionService

request = AcquisitionRequest(
    url="https://www.youtube.com/watch?v=...",
    provider="yt_dlp",
    operation="metadata",
    yt_dlp_options={"noplaylist": True},
)

async with AcquisitionService() as service:
    async for event in service.aiter_events(request):
        print(event.kind, event.provider)
```

Shared headers, cookies, proxies, output policy, credential references, and
progress use common contracts. Provider-native yt-dlp and gallery-dl options
remain isolated. See the [acquisition guide](docs/acquisition.rst).

Application downloaders can join the same API through
`DownloaderAcquisitionProvider`. Custom options are JSON-safe, namespaced by
stable provider name, validated by an optional Pydantic model, and exposed as
JSON Schema for generated TypeScript clients. Installed provider plugins are
loaded explicitly rather than during import.

### Versioned contracts for TypeScript and RPC

Export the portable Python contracts as deterministic JSON Schema instead of
maintaining a second set of request and result types by hand:

```bash
pyfetcher contracts list
pyfetcher contracts export ./generated/fetchkit --split
```

The manifest covers HTTP, extraction, acquisition, media, artifacts, search,
jobs, queues, and built-in template inputs. It also reports provider
capabilities and custom provider option schemas. Each `name@version` contract
has a stable `$id` and checksum suitable for generated TypeScript/Zod types and
CI drift checks. Runtime callables, byte iterators, clients, and resolved
credentials remain Python-side. See the
[cross-language contract guide](docs/contracts.rst).

### Reusable pagination and media jobs

Jobs are JSON-safe data that reference an allowlisted template version. They
can run in-process today or through the optional Redis Streams and Temporal
runtimes:

```python
from pyfetcher.jobs import JobRequest, PaginationInput, TemplateRef

job = JobRequest(
    template=TemplateRef(name="web.pagination", version="1"),
    target="https://example.com/archive?page=1",
    payload=PaginationInput(
        mode="enumerate",
        page_link_selector="nav.pagination a",
        visit_template=TemplateRef(name="article.extract", version="2"),
    ).model_dump(mode="json"),
)
```

Built-ins cover last-page discovery, page enumeration, next-link walking,
provider-neutral media/gallery/playlist acquisition, and pluggable site search.
Results use `ArtifactRef`, `BlobRef`, and ordered `ArtifactCollection` manifests,
so HTML, images, and videos stay out of queue messages and workflow histories.
See [durable jobs and reusable flows](docs/durable-flows.rst).

Run a job or flow file directly, or host the same service through FastAPI:

```bash
pyfetcher jobs run flow.json --concurrency 8 --artifacts-dir ./artifacts
pyfetcher jobs serve --host 127.0.0.1 --port 8000 --concurrency 8
```

The bundled queue and result store are process-local. Applications can inject
Redis Streams and a durable status-store adapter without changing job
templates; the latter adapter is still an extension point rather than a
built-in persistent implementation.

### Browser Profiles & Headers

```python
from pyfetcher.headers.browser import BrowserHeaderProvider
from pyfetcher.headers.rotating import RotatingHeaderProvider
from pyfetcher.headers.ua import random_user_agent
from pyfetcher.fetch.service import FetchService

# Fixed profile (Chrome on Windows)
service = FetchService(header_provider=BrowserHeaderProvider("chrome_win"))

# Rotating profiles weighted by real-world market share
service = FetchService(header_provider=RotatingHeaderProvider())

# Just need a user-agent string?
ua = random_user_agent(browser="firefox", platform="macOS")
```

### Scraping

```python
from pyfetcher.scrape import (
    extract_links, extract_text, extract_table,
    extract_forms, extract_readable_text,
)
from pyfetcher.scrape.robots import parse_robots_txt, is_allowed

# CSS selectors
titles = extract_text(html, "h1.title")
rows = extract_table(html, "table.data")

# Links with internal/external classification
links = extract_links(html, base_url=url, same_domain_only=True)

# Forms with field extraction
forms = extract_forms(html, base_url=url)
print(forms[0].action, forms[0].to_dict())

# Robots.txt
rules = parse_robots_txt(robots_content)
allowed = is_allowed(rules, "/admin", user_agent="MyBot")
```

### Rate-Limited Fetching

```python
from pyfetcher.fetch.service import FetchService
from pyfetcher.ratelimit.limiter import DomainRateLimiter, RateLimitPolicy

limiter = DomainRateLimiter(
    default_policy=RateLimitPolicy(requests_per_second=2.0, burst=5),
    domain_policies={
        "api.example.com": RateLimitPolicy(requests_per_second=0.5),
    },
)
service = FetchService(rate_limiter=limiter)
```

### Content Extraction

```python
from pyfetcher.extractors.content import extract_article_text
from pyfetcher.extractors.convert import html_to_markdown, html_to_plaintext

# Article text (trafilatura with readability-lxml fallback)
article = extract_article_text(html, url="https://example.com/post")

# HTML -> Markdown
md = html_to_markdown(html)
```

### yt-dlp & gallery-dl

```python
from pyfetcher.downloaders.ytdlp import YtdlpDownloader
from pyfetcher.downloaders.gallerydl import GalleryDlDownloader

# yt-dlp with progress tracking
yt = YtdlpDownloader()
info = await yt.extract_info("https://youtube.com/watch?v=dQw4w9WgXcQ")
results = await yt.download(url, output_dir="./videos",
    progress_callback=lambda p: print(f"{p.status}: {p.percent}"))

# gallery-dl for image galleries (170+ supported sites)
gdl = GalleryDlDownloader()
results = await gdl.download("https://imgur.com/gallery/...", output_dir="./images")
```

## CLI

```bash
# Fetch with any backend
pyfetcher fetch https://example.com
pyfetcher fetch https://example.com -o json -b curl_cffi

# Preview generated headers
pyfetcher headers --profile chrome_win
pyfetcher headers --browser firefox -o json
pyfetcher headers --list

# Scrape content
pyfetcher scrape https://example.com --css "h1"
pyfetcher scrape https://example.com --links -o json
pyfetcher scrape https://example.com --text
pyfetcher scrape https://example.com --meta

# Random user-agents
pyfetcher user-agent --browser chrome --count 5
pyfetcher user-agent --mobile

# Check robots.txt
pyfetcher robots https://example.com -p /admin

# Download files
pyfetcher download https://example.com/file.pdf ./file.pdf

# Provider-aware metadata and downloads
pyfetcher acquire URL --metadata --provider yt-dlp
pyfetcher acquire URL -d ./images --provider gallery-dl --events

# Inspect and validate serialized job templates
pyfetcher templates list
pyfetcher templates validate job.json

# Run a flow or host the job API and worker
pyfetcher jobs run flow.json --concurrency 8
pyfetcher jobs serve --port 8000

# Export portable contracts for TypeScript, queues, or an API layer
pyfetcher contracts list --category acquisition
pyfetcher contracts export ./generated/fetchkit --split
```

## Pipeline

The database pipeline runs concurrent polling workers over durable Postgres
job rows. Stage transitions also emit ``NOTIFY`` events for external listeners:

```
Seeds / RSS / Sitemap
       |
  [Crawl Stage]  ──job row──>  [Scrape Stage]  ──job row──>  [Download Stage]
       |                             |                             |
       v                             v                             v
  pages table                 pages (enriched)              media_assets
  + new crawl jobs            + download jobs               + MinIO objects
```

### Setup

```bash
make infra-up     # Start Postgres + MinIO
make migrate      # Run Alembic migrations
make pipeline     # Start all workers
```

### Programmatic

```python
from pyfetcher.pipeline.runner import PipelineRunner
from pyfetcher.config import PyfetcherConfig

runner = PipelineRunner(PyfetcherConfig(
    crawl_concurrency=10,
    scrape_concurrency=20,
    download_concurrency=5,
))
await runner.start()
```

### Custom Spiders

```python
from pyfetcher.crawler.spider import Spider, SpiderResult

spider = Spider(name="my-spider")

@spider.router.add(r"/blog/\d{4}/")
async def handle_post(url, response):
    return SpiderResult(
        discovered_urls=[...],
        items=[{"title": "...", "content": "..."}],
    )
```

## MCP Server (AI Agent Integration)

fetchkit ships as an **MCP server**, making all its capabilities available to AI agents (Claude, LangChain, LangGraph, and any MCP-compatible client). This turns fetchkit into **autonomous agentic infrastructure** -- LLMs can fetch, scrape, extract, and download without custom code.

### Why MCP?

Traditional scraping requires writing code for every site. With fetchkit's MCP server, an AI agent can:

- **Autonomously research topics** by fetching pages, extracting content, and following links
- **Audit websites** by checking metadata, robots.txt, sitemaps, and page structure
- **Extract structured data** from any page using CSS selectors, table parsing, or article extraction
- **Download media** with progress tracking and checksum verification
- **Generate realistic requests** using browser profiles that pass bot detection

All 16 tools return **structured Pydantic models** so the LLM gets clean, typed data -- not raw HTML.

### Quick Start

```bash
pip install 'fetchkit[mcp]'

# Run as stdio server (Claude Desktop / Claude Code)
pyfetcher-mcp

# Run as HTTP server (LangChain / remote agents)
pyfetcher-mcp --http 8000

# Or via Makefile
make mcp          # stdio
make mcp-http     # HTTP on port 8000
```

### Available Tools (16)

| Tool                | What it does                                                       |
| ------------------- | ------------------------------------------------------------------ |
| `fetch_url`         | Fetch any URL with browser headers, returns status + body + timing |
| `fetch_multiple`    | Batch fetch with concurrency control                               |
| `scrape_css`        | Extract content via CSS selectors                                  |
| `scrape_links`      | Harvest links with internal/external classification                |
| `scrape_text`       | Extract readable text (strips scripts, nav, etc.)                  |
| `scrape_metadata`   | Title, description, Open Graph, favicons                           |
| `scrape_forms`      | Parse forms with fields and default values                         |
| `scrape_table`      | Extract HTML table data as rows                                    |
| `check_robots`      | Check robots.txt rules for any path                                |
| `parse_sitemap`     | Parse XML sitemaps                                                 |
| `generate_headers`  | Preview full browser header sets                                   |
| `list_profiles`     | Show all 11 browser profiles                                       |
| `random_user_agent` | Generate random realistic UAs                                      |
| `extract_article`   | Article text + markdown via trafilatura                            |
| `convert_html`      | HTML -> markdown or plaintext                                      |
| `download_file`     | Download with checksum verification                                |

### Resources & Prompts

Resources expose data for context: `pyfetcher://profiles`, `pyfetcher://backends`, `pyfetcher://version`.

Prompts provide templates: `web_research`, `site_audit`, `scrape_guide`, `compare_pages`.

### Use with LangChain

```python
from langchain_mcp_adapters import MultiServerMCPClient

client = MultiServerMCPClient({
    "pyfetcher": {"transport": "http", "url": "http://localhost:8000/mcp"}
})
tools = await client.get_tools()  # 16 LangChain tools ready to use

# Build an agent
from langgraph.prebuilt import create_react_agent
agent = create_react_agent(model, tools)
```

### Use with Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "pyfetcher": {
      "command": "pyfetcher-mcp",
      "args": []
    }
  }
}
```

## Transport Backends

| Backend      | Sync | Async | Response stream | HTTP/2 | TLS fingerprint | CF bypass | Install          |
| ------------ | :--: | :---: | :-------------: | :----: | :-------------: | :-------: | ---------------- |
| httpx        |  Y   |   Y   |   sync + async  |   Y    |        -        |     -     | _(core)_         |
| aiohttp      |  -   |   Y   |      async      |   -    |        -        |     -     | _(core)_         |
| curl_cffi    |  Y   |   Y   |      async      |   Y    |        Y        |     -     | `[curl]`         |
| cloudscraper |  Y   |   -   |        -        |   -    |        -        |     Y     | `[cloudscraper]` |
| Scrapy bridge|  -   |   Y   |        -        | engine |       engine    |   engine  | `[scrapy]`       |

## Development

```bash
git clone https://github.com/pr1m8/pyfetcher.git
cd pyfetcher
make install-all              # pdm install with all deps
make test                     # run the test suite
make check                    # format + lint + test
make release-check            # tests + strict docs + distribution checks
make infra-up && make migrate # start Postgres + MinIO
```

### Makefile Targets

```
make help          Show all targets
make install-all   Install everything
make test          Run the test suite
make test-cov      Tests with coverage report
make fmt           Format with Ruff
make lint          Lint with Ruff
make check         Format + lint + test
make release-check Validate tests, docs, wheel, and source distribution
make infra-up      Start Postgres + MinIO
make infra-down    Stop infrastructure
make migrate       Run Alembic migrations
make pipeline      Run crawl->scrape->download
make build         Build wheel + sdist
make publish       Publish to PyPI
make docs          Build Sphinx docs
make clean         Remove build artifacts
```

## Documentation

<div align="center">

**[pr1m8.github.io/pyfetcher](https://pr1m8.github.io/pyfetcher/)**

[Quick Start](https://pr1m8.github.io/pyfetcher/quickstart.html) | [Reusable Clients](https://pr1m8.github.io/pyfetcher/clients.html) | [Acquisition](https://pr1m8.github.io/pyfetcher/acquisition.html) | [Adapters](https://pr1m8.github.io/pyfetcher/adapters.html) | [Scraping](https://pr1m8.github.io/pyfetcher/scraping.html) | [MCP](https://pr1m8.github.io/pyfetcher/mcp.html) | [API Reference](https://pr1m8.github.io/pyfetcher/api/index.html)

</div>

## License

[MIT](LICENSE)
