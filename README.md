# pyfetcher

[![CI](https://github.com/pr1m8/pyfetcher/actions/workflows/ci.yml/badge.svg)](https://github.com/pr1m8/pyfetcher/actions/workflows/ci.yml)
[![Docs](https://readthedocs.org/projects/pyfetcher/badge/?version=latest)](https://pyfetcher.readthedocs.io/en/latest/)
[![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![PDM](https://img.shields.io/badge/pdm-managed-blueviolet)](https://pdm-project.org)

Advanced web fetching, scraping, and content acquisition toolkit for Python. From simple HTTP requests to full crawl-scrape-download pipelines backed by Postgres and MinIO.

## Features

### Core

- **Realistic browser headers** -- 11 browser profiles (Chrome, Firefox, Safari, Edge) across platforms with consistent UA, Client Hints, and Sec-Fetch-\* headers. Market-share-weighted rotation.
- **4 HTTP backends** -- httpx, aiohttp, curl_cffi (TLS fingerprinting), cloudscraper (Cloudflare bypass).
- **Rate limiting** -- Per-domain and global token bucket rate limiting.
- **Retry** -- Configurable exponential backoff with retryable status codes via Tenacity.
- **Scraping** -- CSS selectors, link harvesting, form parsing, robots.txt, sitemap parsing, content extraction.
- **Metadata** -- HTML meta, Open Graph, JSON-LD, microdata, RDFa, Dublin Core.
- **CLI & TUI** -- `pyfetcher` CLI with 6 commands + interactive Textual TUI.

### Infrastructure (optional)

- **Event-driven pipeline** -- Crawl -> Scrape -> Download stages via Postgres LISTEN/NOTIFY.
- **Database** -- SQLAlchemy 2.0 async + Alembic migrations. Models for jobs, pages, media, hosts, feeds, URL dedup.
- **Object storage** -- MinIO/S3 via aioboto3 with presigned URLs and key generation.
- **Downloaders** -- Deep yt-dlp integration (progress hooks, info_dict), gallery-dl (job API), direct HTTP streaming.
- **Extractors** -- trafilatura + readability-lxml fallback, html2text, markdownify, media metadata (audio/video/image/PDF).
- **Crawler** -- URL frontier with dedup, spider + router, politeness enforcement, RSS/Atom feed monitoring.
- **Docker Compose** -- Postgres 17 + MinIO with health checks, `.env` config, Alembic migrations.

## Installation

```bash
pip install pyfetcher
```

Optional dependency groups:

```bash
pip install 'pyfetcher[tui]'          # Textual TUI
pip install 'pyfetcher[metadata]'      # extruct structured data
pip install 'pyfetcher[curl]'          # curl_cffi TLS fingerprinting
pip install 'pyfetcher[cloudscraper]'  # Cloudflare bypass
pip install 'pyfetcher[db]'            # Postgres + SQLAlchemy + Alembic
pip install 'pyfetcher[store]'         # MinIO/S3 object storage
pip install 'pyfetcher[pipeline]'      # db + store (full pipeline)
pip install 'pyfetcher[downloaders]'   # yt-dlp + gallery-dl
pip install 'pyfetcher[extractors]'    # trafilatura, readability, html2text
pip install 'pyfetcher[media]'         # mutagen, pymediainfo, exifread, pypdf
pip install 'pyfetcher[browser]'       # Playwright + stealth
pip install 'pyfetcher[feeds]'         # feedparser + dateparser
pip install 'pyfetcher[full]'          # Everything
```

## Quick Start

### Fetch a URL

```python
from pyfetcher import fetch, FetchRequest

response = fetch("https://example.com")
print(response.status_code, response.ok)
```

### Async Fetch

```python
import asyncio
from pyfetcher import afetch

async def main():
    response = await afetch("https://example.com")
    print(response.status_code)

asyncio.run(main())
```

### Browser Profiles

```python
from pyfetcher.headers.browser import BrowserHeaderProvider
from pyfetcher.headers.rotating import RotatingHeaderProvider
from pyfetcher.fetch.service import FetchService

# Fixed profile
service = FetchService(header_provider=BrowserHeaderProvider("chrome_win"))

# Rotating profiles (weighted by market share)
service = FetchService(header_provider=RotatingHeaderProvider())
```

### Scraping

```python
from pyfetcher.scrape import extract_links, extract_text, extract_readable_text

links = extract_links(html, base_url="https://example.com")
headings = extract_text(html, "h1")
content = extract_readable_text(html)
```

### Rate-Limited Fetching

```python
from pyfetcher.fetch.service import FetchService
from pyfetcher.ratelimit.limiter import DomainRateLimiter, RateLimitPolicy

limiter = DomainRateLimiter(
    default_policy=RateLimitPolicy(requests_per_second=2.0, burst=5),
    domain_policies={"api.example.com": RateLimitPolicy(requests_per_second=0.5)},
)
service = FetchService(rate_limiter=limiter)
```

### Content Extraction

```python
from pyfetcher.extractors.content import extract_article_text
from pyfetcher.extractors.convert import html_to_markdown

text = extract_article_text(html, url="https://example.com/article")
markdown = html_to_markdown(html)
```

### yt-dlp Integration

```python
from pyfetcher.downloaders.ytdlp import YtdlpDownloader

dl = YtdlpDownloader()
info = await dl.extract_info("https://youtube.com/watch?v=...")
results = await dl.download("https://youtube.com/watch?v=...", output_dir="./downloads")
```

### Pipeline (Crawl -> Scrape -> Download)

```python
from pyfetcher.pipeline.runner import PipelineRunner
from pyfetcher.config import PyfetcherConfig

runner = PipelineRunner(PyfetcherConfig())
await runner.start()  # Runs all 3 stages with Postgres job queue
```

## CLI

```bash
pyfetcher fetch https://example.com
pyfetcher fetch https://example.com -o json -b curl_cffi
pyfetcher headers --profile chrome_win
pyfetcher headers --list
pyfetcher scrape https://example.com --css "h1"
pyfetcher scrape https://example.com --links -o json
pyfetcher scrape https://example.com --text
pyfetcher user-agent --browser chrome --count 5
pyfetcher robots https://example.com -p /admin
pyfetcher download https://example.com/file.pdf ./file.pdf
```

## Infrastructure

Start Postgres + MinIO:

```bash
make infra-up          # docker compose up
make migrate           # run Alembic migrations
make pipeline          # start crawl->scrape->download workers
```

See `make help` for all available targets.

## Development

```bash
git clone https://github.com/pr1m8/pyfetcher.git
cd pyfetcher
make install-all       # pdm install -G dev -G full
make test              # 358 tests
make check             # format + lint + test
```

## Documentation

Full documentation at [pyfetcher.readthedocs.io](https://pyfetcher.readthedocs.io/).

## License

MIT
