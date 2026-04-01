# pyfetcher

[![CI](https://github.com/pr1m8/pyfetcher/actions/workflows/ci.yml/badge.svg)](https://github.com/pr1m8/pyfetcher/actions/workflows/ci.yml)
[![Docs](https://readthedocs.org/projects/pyfetcher/badge/?version=latest)](https://pyfetcher.readthedocs.io/en/latest/)
[![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![PDM](https://img.shields.io/badge/pdm-managed-blueviolet)](https://pdm-project.org)

Advanced web fetching and scraping toolkit for Python.

## Features

- **Realistic browser headers** -- 11 browser profiles (Chrome, Firefox, Safari, Edge) across Windows/macOS/Linux/Android/iOS with consistent User-Agent, Client Hints, Sec-Fetch-\*, and Accept headers. Weighted rotation by market share.
- **Multiple backends** -- httpx (sync + async) and aiohttp (async) transport support with HTTP/2.
- **Rate limiting** -- Per-domain and global rate limiting with token bucket algorithm.
- **Retry with backoff** -- Configurable exponential backoff with retryable status codes via Tenacity.
- **Scraping tools** -- CSS selectors, link harvesting, form parsing, robots.txt, sitemap parsing, content extraction.
- **Metadata extraction** -- HTML metadata, Open Graph, structured data (JSON-LD, microdata, RDFa, Dublin Core).
- **CLI** -- `pyfetcher` command with `fetch`, `scrape`, `headers`, `user-agent`, `robots`, and `download` subcommands.
- **TUI** -- Interactive terminal UI built with Textual for building and inspecting requests.
- **Streaming** -- Async streaming with chunked downloads to disk.
- **Batch operations** -- Concurrent fetching with bounded concurrency via asyncio.

## Installation

```bash
pip install pyfetcher
# or with PDM
pdm add pyfetcher
```

With optional dependencies:

```bash
pip install 'pyfetcher[tui]'       # Textual TUI
pip install 'pyfetcher[metadata]'   # extruct + w3lib for structured data
pip install 'pyfetcher[all]'        # Everything
```

## Quick Start

### Fetch a URL

```python
from pyfetcher import fetch, FetchRequest

response = fetch("https://example.com")
print(response.status_code, response.ok)
```

### Browser Profiles

```python
from pyfetcher.headers.browser import BrowserHeaderProvider
from pyfetcher.fetch.service import FetchService

# Use a specific browser profile
service = FetchService(header_provider=BrowserHeaderProvider("chrome_win"))
response = service.fetch(FetchRequest(url="https://example.com"))

# Or rotate through profiles automatically
from pyfetcher.headers.rotating import RotatingHeaderProvider
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

### Random User-Agent

```python
from pyfetcher.headers.ua import random_user_agent

ua = random_user_agent(browser="chrome")
ua = random_user_agent(mobile=True)
```

## CLI

```bash
# Fetch a URL
pyfetcher fetch https://example.com
pyfetcher fetch https://example.com -o json

# Preview browser headers
pyfetcher headers --profile chrome_win
pyfetcher headers --list

# Scrape content
pyfetcher scrape https://example.com --css "h1"
pyfetcher scrape https://example.com --links -o json
pyfetcher scrape https://example.com --text
pyfetcher scrape https://example.com --meta

# Generate user-agents
pyfetcher user-agent --browser chrome --count 5

# Check robots.txt
pyfetcher robots https://example.com -p /admin

# Download files
pyfetcher download https://example.com/file.pdf ./file.pdf
```

## Development

```bash
# Clone and install
git clone https://github.com/pr1m8/pyfetcher.git
cd pyfetcher
pdm install -G dev -G all

# Run tests
pdm run pytest tests/ -v

# Lint and format
trunk fmt src/ tests/
trunk check src/ tests/
```

## Documentation

Full documentation is available at [pyfetcher.readthedocs.io](https://pyfetcher.readthedocs.io/).

## License

MIT
