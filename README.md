<div align="center">

# fetchkit

**Advanced web fetching, scraping, and content acquisition toolkit for Python.**

From simple HTTP requests to full crawl-scrape-download pipelines backed by Postgres and MinIO.

[![PyPI](https://img.shields.io/pypi/v/fetchkit?style=flat-square&logo=pypi&logoColor=white&color=blue)](https://pypi.org/project/fetchkit/)
[![Python](https://img.shields.io/pypi/pyversions/fetchkit?style=flat-square&logo=python&logoColor=white)](https://pypi.org/project/fetchkit/)
[![Docs](https://img.shields.io/github/actions/workflow/status/pr1m8/pyfetcher/pages.yml?branch=main&style=flat-square&logo=github&label=docs)](https://pr1m8.github.io/pyfetcher/)
[![CI](https://img.shields.io/github/actions/workflow/status/pr1m8/pyfetcher/ci.yml?branch=main&style=flat-square&logo=github&label=CI)](https://github.com/pr1m8/pyfetcher/actions/workflows/ci.yml)
[![License](https://img.shields.io/github/license/pr1m8/pyfetcher?style=flat-square&color=green)](https://github.com/pr1m8/pyfetcher/blob/main/LICENSE)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json&style=flat-square)](https://github.com/astral-sh/ruff)
[![PDM](https://img.shields.io/badge/pdm-managed-blueviolet?style=flat-square)](https://pdm-project.org)
[![Tests](https://img.shields.io/badge/tests-358_passed-brightgreen?style=flat-square)](#testing)

---

[Installation](#installation) | [Quick Start](#quick-start) | [CLI](#cli) | [Pipeline](#pipeline) | [Documentation](https://pr1m8.github.io/pyfetcher/) | [Examples](examples/)

</div>

## Highlights

```
pip install fetchkit                   # Core: fetch, scrape, headers
pip install 'fetchkit[pipeline]'       # + Postgres job queue + MinIO storage
pip install 'fetchkit[full]'           # Everything including yt-dlp, Playwright, etc.
```

<table>
<tr>
<td width="50%">

**Fetch with realistic browser headers**

```python
from pyfetcher import fetch

response = fetch("https://example.com")
# Sends Chrome-like headers with Client Hints,
# Sec-Fetch-*, UA rotation automatically
```

</td>
<td width="50%">

**Scrape anything**

```python
from pyfetcher.scrape import (
    extract_links, extract_text,
    extract_readable_text,
)

links = extract_links(html, base_url=url)
titles = extract_text(html, "h1")
article = extract_readable_text(html)
```

</td>
</tr>
<tr>
<td>

**4 HTTP backends**

```python
from pyfetcher import FetchRequest, fetch

# TLS fingerprinting (bypass bot detection)
fetch(FetchRequest(url=url, backend="curl_cffi"))

# Cloudflare bypass
fetch(FetchRequest(url=url, backend="cloudscraper"))
```

</td>
<td>

**Download media with yt-dlp**

```python
from pyfetcher.downloaders.ytdlp import YtdlpDownloader

dl = YtdlpDownloader()
info = await dl.extract_info(video_url)
results = await dl.download(video_url,
    output_dir="./media")
```

</td>
</tr>
</table>

## Features

### Core Library

| Feature             | Description                                                                                                                               |
| ------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| **Browser Headers** | 11 profiles (Chrome/Firefox/Safari/Edge) across 5 platforms. Consistent UA + Client Hints + Sec-Fetch-\*. Market-share-weighted rotation. |
| **4 Backends**      | `httpx` (default, HTTP/2), `aiohttp` (async), `curl_cffi` (TLS fingerprint), `cloudscraper` (CF bypass)                                   |
| **Rate Limiting**   | Per-domain + global token bucket with configurable burst                                                                                  |
| **Retry**           | Exponential backoff via Tenacity with configurable status codes                                                                           |
| **Scraping**        | CSS selectors, link harvesting, form parsing, table extraction                                                                            |
| **Metadata**        | HTML meta, Open Graph, JSON-LD, microdata, RDFa, Dublin Core                                                                              |
| **CLI**             | `pyfetcher fetch`, `scrape`, `headers`, `user-agent`, `robots`, `download`                                                                |
| **TUI**             | Interactive Textual terminal UI for building and inspecting requests                                                                      |

### Infrastructure (optional extras)

| Feature          | Extra           | Description                                                                 |
| ---------------- | --------------- | --------------------------------------------------------------------------- |
| **Pipeline**     | `[pipeline]`    | Event-driven Crawl -> Scrape -> Download via Postgres LISTEN/NOTIFY         |
| **Database**     | `[db]`          | SQLAlchemy 2.0 async + Alembic. Jobs, pages, media, hosts, feeds, URL dedup |
| **Object Store** | `[store]`       | MinIO/S3 via aioboto3. Upload, download, presigned URLs                     |
| **Downloaders**  | `[downloaders]` | yt-dlp (progress hooks, info_dict) + gallery-dl (170+ sites)                |
| **Extractors**   | `[extractors]`  | trafilatura + readability-lxml fallback, html2text, markdownify             |
| **Media**        | `[media]`       | Audio (mutagen), video (pymediainfo), image (exifread), PDF (pypdf)         |
| **Browser**      | `[browser]`     | Playwright + stealth for JS-heavy sites                                     |
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
pip install 'fetchkit[feeds]'          # RSS/Atom feed parsing
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
```

## Pipeline

The event-driven pipeline connects three stages via Postgres LISTEN/NOTIFY:

```
Seeds / RSS / Sitemap
       |
  [Crawl Stage]  ──NOTIFY──>  [Scrape Stage]  ──NOTIFY──>  [Download Stage]
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

## Transport Backends

| Backend      | Sync | Async | Stream | TLS Fingerprint | CF Bypass | Install          |
| ------------ | :--: | :---: | :----: | :-------------: | :-------: | ---------------- |
| httpx        |  Y   |   Y   |   Y    |        -        |     -     | _(core)_         |
| aiohttp      |  -   |   Y   |   Y    |        -        |     -     | _(core)_         |
| curl_cffi    |  Y   |   Y   |   Y    |        Y        |     -     | `[curl]`         |
| cloudscraper |  Y   |   -   |   -    |        -        |     Y     | `[cloudscraper]` |

## Development

```bash
git clone https://github.com/pr1m8/pyfetcher.git
cd pyfetcher
make install-all              # pdm install with all deps
make test                     # 358 tests
make check                    # format + lint + test
make infra-up && make migrate # start Postgres + MinIO
```

### Makefile Targets

```
make help          Show all targets
make install-all   Install everything
make test          Run 358 tests
make test-cov      Tests with coverage report
make fmt           Format with trunk
make lint          Lint with trunk
make check         Format + lint + test
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

[Quick Start](https://pr1m8.github.io/pyfetcher/en/latest/quickstart.html) | [Headers](https://pr1m8.github.io/pyfetcher/en/latest/headers.html) | [Scraping](https://pr1m8.github.io/pyfetcher/en/latest/scraping.html) | [Pipeline](https://pr1m8.github.io/pyfetcher/en/latest/pipeline.html) | [Infrastructure](https://pr1m8.github.io/pyfetcher/en/latest/infrastructure.html) | [CLI](https://pr1m8.github.io/pyfetcher/en/latest/cli.html) | [API Reference](https://pr1m8.github.io/pyfetcher/en/latest/api/index.html)

</div>

## License

[MIT](LICENSE)
