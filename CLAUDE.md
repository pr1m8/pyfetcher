# pyfetcher - Project Guide

## Overview

pyfetcher is an advanced web fetching and scraping toolkit for Python 3.13+. It provides realistic browser header generation, multiple HTTP backends, rate limiting, retry with backoff, comprehensive scraping tools, and both CLI and TUI interfaces.

**Status**: Active development. Core fetch/scrape/headers/transport layer is stable. More functionality coming soon -- see [Roadmap](#roadmap) below.

## Architecture

```
src/pyfetcher/
├── contracts/     # Pydantic models: URL, FetchRequest, FetchResponse, policies
├── headers/       # Browser header generation: profiles, UA rotation, static providers
├── transports/    # HTTP backends: httpx, aiohttp, curl_cffi, cloudscraper
├── retry/         # Tenacity-based retry with exponential backoff
├── ratelimit/     # Per-domain + global rate limiting with token buckets
├── fetch/         # Orchestration: FetchService, function API, batch, stream
├── scrape/        # CSS selectors, links, forms, robots.txt, sitemap, content extraction
├── metadata/      # HTML metadata, Open Graph, extruct structured data
├── download/      # Async streaming file downloads
├── cli/           # Click-based CLI (pyfetcher command)
├── tui/           # Textual-based interactive TUI (pyfetcher-tui command)
└── rich.py        # Rich table rendering helpers
```

### Layer Dependencies (top-down)

1. `contracts` - Pure Pydantic models, no I/O
2. `headers` - Browser profile system, depends only on contracts
3. `transports` - HTTP backends, depends on contracts
4. `retry` - Tenacity adapters, depends on contracts
5. `ratelimit` - Token bucket rate limiter, standalone
6. `fetch` - Orchestration composing headers + transports + retry + ratelimit
7. `scrape` / `metadata` / `download` - Higher-level tools using fetch
8. `cli` / `tui` - User interfaces using everything above

### Adding New Modules

When adding new functionality:

- Put data models in `contracts/` if they're shared across layers
- New I/O capabilities go in their own subpackage at the appropriate layer
- Guard optional dependencies with `try/except` in `__init__.py` (see existing patterns)
- Add docstrings (Google-style with Purpose, Design, Args, Returns, Examples)
- Add unit tests in `tests/test_<module>.py`, integration tests if it touches I/O
- Add a docs page in `docs/api/<module>.rst` with `automodule` directives
- Add an example in `examples/` if it's a user-facing feature
- Update the CLI in `cli/app.py` if it should be accessible from the terminal
- Run `trunk fmt` and `trunk check` before committing

## Development

### Setup

```bash
pdm install -G dev      # Install with dev dependencies
pdm install -G dev -G all  # Include optional deps (textual, extruct, curl_cffi, cloudscraper)
```

### Testing

```bash
pytest tests/ -v                    # Run all tests (195 currently)
pytest tests/test_scrape.py -v      # Run specific module
pytest tests/ --cov=pyfetcher       # With coverage
```

- Tests use **pytest** with **pytest-asyncio** (auto mode)
- Fixtures are in `tests/conftest.py`
- Unit tests cover: contracts, headers, scrape, metadata, retry, ratelimit, stream/batch, transports
- Integration tests cover: FetchService with mocked httpx (respx), CLI commands (CliRunner), download service
- Mock network calls with `respx` for httpx, `unittest.mock` for other transports
- Test CLI commands with `click.testing.CliRunner` and mock the `FetchService`

### Linting & Formatting

```bash
trunk fmt src/ tests/     # Format with trunk (black + isort)
trunk check src/ tests/   # Lint with trunk (ruff + bandit + etc.)
```

Trunk configuration is in `.trunk/trunk.yaml`. Active linters: ruff, black, isort, bandit, markdownlint, prettier, taplo, yamllint. Bandit is excluded from `tests/` (B101 assert noise).

### Code Style

- **Python 3.13+** - uses `type` aliases, modern syntax
- **Pydantic v2** models with `ConfigDict(extra="forbid", frozen=True)`
- **Google-style docstrings** with Purpose, Design, Args, Returns, Raises, Examples
- **Protocol-based abstractions** (HeaderProvider, SyncTransport, AsyncTransport)
- All imports use `from __future__ import annotations`
- Line length: 100 characters

### Key Patterns

- **Optional dependency guards**: `try/except` blocks in `__init__.py` files protect against missing optional deps
- **`# nosec B311`**: Used for intentional `random.choice` in header randomization (not security-sensitive)
- **Frozen models**: All Pydantic models are frozen (immutable) - use `model_copy(update={...})` to create modified copies
- **Async-first**: Most operations support both sync and async; async is the primary pattern
- **Lazy transport init**: curl_cffi and cloudscraper transports are created on first use in FetchService, so their deps remain optional
- **Incremental commits**: Commit after each logical chunk of work. Run tests + trunk before each commit.

## CLI Entry Points

- `pyfetcher` - Main CLI (defined in `pyfetcher.cli.app:main`)
- `pyfetcher-tui` - Interactive TUI (defined in `pyfetcher.tui.app:run_tui`)

## Transport Backends

| Backend      | Sync | Async | Stream | TLS Fingerprint | CF Bypass |
| ------------ | ---- | ----- | ------ | --------------- | --------- |
| httpx        | Y    | Y     | Y      | N               | N         |
| aiohttp      | N    | Y     | Y      | N               | N         |
| curl_cffi    | Y    | Y     | Y      | Y               | N         |
| cloudscraper | Y    | N     | N      | N               | Y         |

## Browser Profiles

11 profiles covering Chrome/Firefox/Safari/Edge across Windows/macOS/Linux/Android/iOS. Each profile bundles consistent User-Agent + Client Hints + Sec-Fetch-\* + Accept headers. Profiles are weighted by real-world market share for realistic rotation.

## Roadmap

Planned additions (this list will evolve):

- Proxy support (rotating proxies, SOCKS5, proxy chains)
- Cookie jar management (persistence, domain-scoped)
- Caching layer (HTTP cache, local file cache, TTL)
- Spider/crawler framework (depth control, link following, dedup)
- JavaScript rendering (Playwright/Selenium integration)
- Export formats (CSV, JSON Lines, Parquet)
- Middleware/plugin system for request/response hooks
- More browser profiles (Brave, Opera, Arc, older versions)
- Captcha solving integration
- Webhook/callback support for async pipelines
