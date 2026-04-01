"""FastMCP server exposing pyfetcher capabilities.

Purpose:
    Provide MCP tools for fetching URLs, scraping content, generating
    browser headers, extracting articles, and downloading files. All tools
    return structured Pydantic models for reliable LLM consumption.

Usage:
    python -m pyfetcher.mcp                          # stdio
    python -m pyfetcher.mcp --http 8000              # HTTP
    fastmcp run src/pyfetcher/mcp/server.py          # via CLI
"""

from __future__ import annotations

import json
from typing import Annotated

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from pyfetcher.mcp.models import (
    ArticleResult,
    DownloadResult,
    FetchResult,
    FormInfo,
    FormsResult,
    HeadersResult,
    LinkInfo,
    LinksResult,
    MetadataResult,
    ProfileInfo,
    RobotsResult,
    ScrapeResult,
    SitemapResult,
    TableResult,
)

mcp = FastMCP("pyfetcher", version="0.2.0")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fetch_sync(
    url: str, *, backend: str = "httpx", profile: str = "chrome_win", timeout: float = 30.0
):
    """Fetch a URL synchronously, returning a FetchResponse."""
    from pyfetcher.contracts.policy import TimeoutPolicy
    from pyfetcher.contracts.request import FetchRequest
    from pyfetcher.fetch.service import FetchService
    from pyfetcher.headers.browser import BrowserHeaderProvider

    service = FetchService(header_provider=BrowserHeaderProvider(profile))
    try:
        return service.fetch(
            FetchRequest(
                url=url,
                backend=backend,  # type: ignore[arg-type]
                timeout=TimeoutPolicy(total_seconds=timeout),
            )
        )
    finally:
        service.close()


# ---------------------------------------------------------------------------
# TOOLS: Fetching
# ---------------------------------------------------------------------------


@mcp.tool()
def fetch_url(
    url: Annotated[str, "URL to fetch"],
    backend: Annotated[str, "HTTP backend (httpx, aiohttp, curl_cffi, cloudscraper)"] = "httpx",
    profile: Annotated[str, "Browser profile for headers"] = "chrome_win",
    timeout: Annotated[int, "Timeout in seconds"] = 30,
) -> FetchResult:
    """Fetch a URL and return the response with status, headers, and body text."""
    try:
        response = _fetch_sync(url, backend=backend, profile=profile, timeout=float(timeout))
        return FetchResult(
            url=response.request_url,
            final_url=response.final_url,
            status_code=response.status_code,
            ok=response.ok,
            content_type=response.content_type,
            headers=response.headers,
            text=response.text,
            elapsed_ms=response.elapsed_ms,
            backend=response.backend,
        )
    except Exception as exc:
        raise ToolError(f"Failed to fetch {url}: {exc}") from exc


@mcp.tool()
def fetch_multiple(
    urls: Annotated[list[str], "List of URLs to fetch"],
    concurrency: Annotated[int, "Max concurrent requests"] = 4,
    profile: Annotated[str, "Browser profile"] = "chrome_win",
) -> list[FetchResult]:
    """Fetch multiple URLs concurrently and return all results."""
    import asyncio

    from pyfetcher.contracts.request import BatchFetchRequest, FetchRequest
    from pyfetcher.fetch.service import FetchService
    from pyfetcher.headers.browser import BrowserHeaderProvider

    async def _run():
        service = FetchService(header_provider=BrowserHeaderProvider(profile))
        try:
            requests = [FetchRequest(url=u) for u in urls]
            batch = BatchFetchRequest(requests=requests, concurrency=concurrency)
            batch_response = await service.afetch_many(batch)
            results = []
            for item in batch_response.items:
                if item.ok and item.response:
                    r = item.response
                    results.append(
                        FetchResult(
                            url=r.request_url,
                            final_url=r.final_url,
                            status_code=r.status_code,
                            ok=r.ok,
                            content_type=r.content_type,
                            headers=r.headers,
                            text=r.text,
                            elapsed_ms=r.elapsed_ms,
                            backend=r.backend,
                        )
                    )
                else:
                    results.append(
                        FetchResult(
                            url=item.request_url,
                            final_url=item.request_url,
                            status_code=0,
                            ok=False,
                            headers={},
                            elapsed_ms=0,
                            backend="httpx",
                            text=f"Error: {item.error}",
                        )
                    )
            return results
        finally:
            await service.aclose()

    try:
        return asyncio.run(_run())
    except Exception as exc:
        raise ToolError(f"Batch fetch failed: {exc}") from exc


# ---------------------------------------------------------------------------
# TOOLS: Scraping
# ---------------------------------------------------------------------------


@mcp.tool()
def scrape_css(
    url: Annotated[str, "URL to scrape"],
    selector: Annotated[str, "CSS selector to extract"],
    profile: Annotated[str, "Browser profile"] = "chrome_win",
) -> ScrapeResult:
    """Fetch a URL and extract text content matching a CSS selector."""
    try:
        response = _fetch_sync(url, profile=profile)
        from pyfetcher.scrape.selectors import extract_text

        elements = extract_text(response.text or "", selector)
        return ScrapeResult(url=url, selector=selector, elements=elements, count=len(elements))
    except Exception as exc:
        raise ToolError(f"Scrape failed: {exc}") from exc


@mcp.tool()
def scrape_links(
    url: Annotated[str, "URL to extract links from"],
    same_domain_only: Annotated[bool, "Only return same-domain links"] = False,
    profile: Annotated[str, "Browser profile"] = "chrome_win",
) -> LinksResult:
    """Fetch a URL and extract all links with internal/external classification."""
    try:
        response = _fetch_sync(url, profile=profile)
        from pyfetcher.scrape.links import extract_links

        links = extract_links(
            response.text or "", base_url=response.final_url, same_domain_only=same_domain_only
        )
        link_infos = [
            LinkInfo(url=lnk.url, text=lnk.text, is_external=lnk.is_external) for lnk in links
        ]
        internal = sum(1 for lnk in links if not lnk.is_external)
        external = sum(1 for lnk in links if lnk.is_external)
        return LinksResult(
            url=url, links=link_infos, total=len(links), internal=internal, external=external
        )
    except Exception as exc:
        raise ToolError(f"Link extraction failed: {exc}") from exc


@mcp.tool()
def scrape_text(
    url: Annotated[str, "URL to extract readable text from"],
    selector: Annotated[str | None, "Optional CSS selector to narrow extraction"] = None,
    profile: Annotated[str, "Browser profile"] = "chrome_win",
) -> str:
    """Fetch a URL and extract the readable text content (strips scripts, nav, etc.)."""
    try:
        response = _fetch_sync(url, profile=profile)
        from pyfetcher.scrape.content import extract_readable_text

        return extract_readable_text(response.text or "", selector=selector)
    except Exception as exc:
        raise ToolError(f"Text extraction failed: {exc}") from exc


@mcp.tool()
def scrape_metadata(
    url: Annotated[str, "URL to extract metadata from"],
    profile: Annotated[str, "Browser profile"] = "chrome_win",
) -> MetadataResult:
    """Fetch a URL and extract page metadata (title, description, Open Graph, favicons)."""
    try:
        response = _fetch_sync(url, profile=profile)
        from pyfetcher.metadata.html import extract_basic_html_metadata
        from pyfetcher.metadata.opengraph import extract_open_graph_metadata

        html = response.text or ""
        meta = extract_basic_html_metadata(html, base_url=response.final_url)
        og = extract_open_graph_metadata(html)

        return MetadataResult(
            url=url,
            title=meta.title,
            description=meta.description,
            canonical_url=meta.canonical_url,
            og_title=og.title if og else None,
            og_description=og.description if og else None,
            og_image=og.image if og else None,
            og_type=og.type if og else None,
            favicons=[f.href for f in meta.favicons],
        )
    except Exception as exc:
        raise ToolError(f"Metadata extraction failed: {exc}") from exc


@mcp.tool()
def scrape_forms(
    url: Annotated[str, "URL to extract forms from"],
    profile: Annotated[str, "Browser profile"] = "chrome_win",
) -> FormsResult:
    """Fetch a URL and extract all HTML forms with their fields."""
    try:
        response = _fetch_sync(url, profile=profile)
        from pyfetcher.scrape.forms import extract_forms

        forms = extract_forms(response.text or "", base_url=response.final_url)
        form_infos = [FormInfo(action=f.action, method=f.method, fields=f.to_dict()) for f in forms]
        return FormsResult(url=url, forms=form_infos, count=len(forms))
    except Exception as exc:
        raise ToolError(f"Form extraction failed: {exc}") from exc


@mcp.tool()
def scrape_table(
    url: Annotated[str, "URL to extract table from"],
    selector: Annotated[str, "CSS selector for the table element"] = "table",
    profile: Annotated[str, "Browser profile"] = "chrome_win",
) -> TableResult:
    """Fetch a URL and extract data from an HTML table as rows."""
    try:
        response = _fetch_sync(url, profile=profile)
        from pyfetcher.scrape.selectors import extract_table

        rows = extract_table(response.text or "", selector)
        return TableResult(url=url, selector=selector, rows=rows, row_count=len(rows))
    except Exception as exc:
        raise ToolError(f"Table extraction failed: {exc}") from exc


# ---------------------------------------------------------------------------
# TOOLS: Robots & Sitemap
# ---------------------------------------------------------------------------


@mcp.tool()
def check_robots(
    url: Annotated[str, "Site base URL (e.g. https://example.com)"],
    path: Annotated[str, "Path to check"] = "/",
    user_agent: Annotated[str, "User-agent to check for"] = "*",
) -> RobotsResult:
    """Fetch and check robots.txt for a site. Returns whether a path is allowed."""
    try:
        robots_url = url.rstrip("/") + "/robots.txt"
        response = _fetch_sync(robots_url)
        from pyfetcher.scrape.robots import is_allowed, parse_robots_txt

        content = response.text or ""
        rules = parse_robots_txt(content)
        allowed = is_allowed(rules, path, user_agent=user_agent)
        return RobotsResult(
            url=url,
            path=path,
            user_agent=user_agent,
            allowed=allowed,
            sitemaps=rules.sitemaps,
        )
    except Exception as exc:
        raise ToolError(f"Robots check failed: {exc}") from exc


@mcp.tool()
def parse_sitemap(
    url: Annotated[str, "Sitemap URL to parse"],
) -> SitemapResult:
    """Fetch and parse an XML sitemap, returning all URLs with metadata."""
    try:
        response = _fetch_sync(url)
        from pyfetcher.scrape.sitemap import parse_sitemap as _parse

        entries = _parse(response.text or "")
        entry_dicts = [
            {"loc": e.loc, "lastmod": e.lastmod, "changefreq": e.changefreq, "priority": e.priority}
            for e in entries
        ]
        return SitemapResult(url=url, entries=entry_dicts, count=len(entries))
    except Exception as exc:
        raise ToolError(f"Sitemap parsing failed: {exc}") from exc


# ---------------------------------------------------------------------------
# TOOLS: Headers & Profiles
# ---------------------------------------------------------------------------


@mcp.tool()
def generate_headers(
    profile: Annotated[str, "Browser profile name (e.g. chrome_win, firefox_mac)"] = "chrome_win",
) -> HeadersResult:
    """Generate a complete set of realistic browser headers for the given profile."""
    try:
        from pyfetcher.headers.browser import get_best_browser_headers

        headers = get_best_browser_headers(profile)
        return HeadersResult(profile=profile, headers=headers)
    except Exception as exc:
        raise ToolError(f"Header generation failed: {exc}") from exc


@mcp.tool()
def list_profiles() -> list[ProfileInfo]:
    """List all available browser profiles with their details."""
    from pyfetcher.headers.profiles import get_profile
    from pyfetcher.headers.profiles import list_profiles as _list

    return [
        ProfileInfo(
            name=name,
            browser=get_profile(name).browser,
            platform=get_profile(name).platform,
            mobile=get_profile(name).mobile,
        )
        for name in _list()
    ]


@mcp.tool()
def random_user_agent(
    browser: Annotated[str | None, "Filter by browser (chrome, firefox, safari, edge)"] = None,
    platform: Annotated[str | None, "Filter by platform (Windows, macOS, Linux)"] = None,
    mobile: Annotated[bool | None, "Filter mobile (true) or desktop (false)"] = None,
) -> str:
    """Generate a random realistic User-Agent string."""
    try:
        from pyfetcher.headers.ua import random_user_agent as _random_ua

        return _random_ua(browser=browser, platform=platform, mobile=mobile)
    except Exception as exc:
        raise ToolError(f"UA generation failed: {exc}") from exc


# ---------------------------------------------------------------------------
# TOOLS: Content Extraction
# ---------------------------------------------------------------------------


@mcp.tool()
def extract_article(
    url: Annotated[str, "URL to extract article from"],
    profile: Annotated[str, "Browser profile"] = "chrome_win",
) -> ArticleResult:
    """Fetch a URL and extract the main article text and optionally convert to markdown."""
    try:
        response = _fetch_sync(url, profile=profile)
        html = response.text or ""
        text = None
        markdown = None
        title = None

        try:
            from pyfetcher.extractors.content import extract_article_text

            text = extract_article_text(html, url=response.final_url)
        except ImportError:
            from pyfetcher.scrape.content import extract_readable_text

            text = extract_readable_text(html)

        try:
            from pyfetcher.extractors.convert import html_to_markdown

            markdown = html_to_markdown(html)
        except ImportError:
            pass

        from pyfetcher.metadata.html import extract_basic_html_metadata

        meta = extract_basic_html_metadata(html, base_url=response.final_url)
        title = meta.title

        return ArticleResult(url=url, text=text, markdown=markdown, title=title)
    except ToolError:
        raise
    except Exception as exc:
        raise ToolError(f"Article extraction failed: {exc}") from exc


@mcp.tool()
def convert_html(
    html: Annotated[str, "HTML content to convert"],
    format: Annotated[str, "Output format: 'markdown' or 'plaintext'"] = "markdown",
) -> str:
    """Convert HTML to markdown or plaintext."""
    try:
        if format == "markdown":
            try:
                from pyfetcher.extractors.convert import html_to_markdown

                return html_to_markdown(html)
            except ImportError as exc:
                raise ToolError("Install 'fetchkit[extractors]' for markdown conversion") from exc
        elif format == "plaintext":
            try:
                from pyfetcher.extractors.convert import html_to_plaintext

                return html_to_plaintext(html)
            except ImportError:
                from pyfetcher.scrape.content import extract_readable_text

                return extract_readable_text(html)
        else:
            raise ToolError(f"Unknown format: {format}. Use 'markdown' or 'plaintext'.")
    except ToolError:
        raise
    except Exception as exc:
        raise ToolError(f"Conversion failed: {exc}") from exc


# ---------------------------------------------------------------------------
# TOOLS: Download
# ---------------------------------------------------------------------------


@mcp.tool()
def download_file(
    url: Annotated[str, "URL to download"],
    destination: Annotated[str, "Local file path to save to"],
    profile: Annotated[str, "Browser profile"] = "chrome_win",
) -> DownloadResult:
    """Download a file from a URL to a local path."""
    import asyncio

    from pyfetcher.contracts.request import FetchRequest
    from pyfetcher.download.service import DownloadService
    from pyfetcher.fetch.service import FetchService
    from pyfetcher.headers.browser import BrowserHeaderProvider

    try:
        service = FetchService(header_provider=BrowserHeaderProvider(profile))
        dl = DownloadService(fetch_service=service)
        path = asyncio.run(dl.adownload_to_path(FetchRequest(url=url), destination))
        size = path.stat().st_size

        import hashlib

        sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        return DownloadResult(url=url, path=str(path), size_bytes=size, checksum_sha256=sha256)
    except Exception as exc:
        raise ToolError(f"Download failed: {exc}") from exc


# ---------------------------------------------------------------------------
# RESOURCES
# ---------------------------------------------------------------------------


@mcp.resource("pyfetcher://profiles")
def resource_profiles() -> str:
    """List all available browser profiles with details."""
    from pyfetcher.headers.profiles import get_profile
    from pyfetcher.headers.profiles import list_profiles as _list

    profiles = []
    for name in _list():
        p = get_profile(name)
        profiles.append(
            {"name": name, "browser": p.browser, "platform": p.platform, "mobile": p.mobile}
        )
    return json.dumps(profiles, indent=2)


@mcp.resource("pyfetcher://profiles/{name}")
def resource_profile_headers(name: str) -> str:
    """Get the full header set for a specific browser profile."""
    from pyfetcher.headers.browser import get_best_browser_headers

    try:
        headers = get_best_browser_headers(name)
        return json.dumps(headers, indent=2)
    except Exception:
        return json.dumps({"error": f"Unknown profile: {name}"})


@mcp.resource("pyfetcher://backends")
def resource_backends() -> str:
    """List available HTTP backends and their capabilities."""
    backends = [
        {
            "name": "httpx",
            "sync": True,
            "async": True,
            "stream": True,
            "tls_fingerprint": False,
            "cf_bypass": False,
            "install": "core",
        },
        {
            "name": "aiohttp",
            "sync": False,
            "async": True,
            "stream": True,
            "tls_fingerprint": False,
            "cf_bypass": False,
            "install": "core",
        },
        {
            "name": "curl_cffi",
            "sync": True,
            "async": True,
            "stream": True,
            "tls_fingerprint": True,
            "cf_bypass": False,
            "install": "fetchkit[curl]",
        },
        {
            "name": "cloudscraper",
            "sync": True,
            "async": False,
            "stream": False,
            "tls_fingerprint": False,
            "cf_bypass": True,
            "install": "fetchkit[cloudscraper]",
        },
    ]
    return json.dumps(backends, indent=2)


@mcp.resource("pyfetcher://version")
def resource_version() -> str:
    """Get pyfetcher version and feature information."""
    from pyfetcher.headers.profiles import list_profiles as _list

    return json.dumps(
        {
            "name": "fetchkit",
            "import_name": "pyfetcher",
            "version": "0.2.0",
            "profiles": len(_list()),
            "backends": ["httpx", "aiohttp", "curl_cffi", "cloudscraper"],
            "tools": 16,
            "resources": 4,
            "prompts": 4,
        },
        indent=2,
    )


# ---------------------------------------------------------------------------
# PROMPTS
# ---------------------------------------------------------------------------


@mcp.prompt()
def web_research(topic: Annotated[str, "Topic to research"]) -> str:
    """Generate a prompt for researching a topic by fetching and analyzing web pages."""
    return f"""Research the following topic using the available pyfetcher tools:

Topic: {topic}

Steps:
1. Use fetch_url to get relevant pages about this topic
2. Use scrape_text or extract_article to get the main content
3. Use scrape_links to find related pages for deeper research
4. Use scrape_metadata to understand page context (title, description, OG tags)
5. Synthesize the information into a clear summary

Focus on authoritative sources and cross-reference information across multiple pages."""


@mcp.prompt()
def site_audit(url: Annotated[str, "Website URL to audit"]) -> str:
    """Generate a prompt for auditing a website's structure and metadata."""
    return f"""Perform a comprehensive audit of this website:

URL: {url}

Use these tools in order:
1. check_robots -- Check robots.txt rules and find sitemaps
2. If sitemaps found, use parse_sitemap to discover all pages
3. fetch_url -- Fetch the homepage
4. scrape_metadata -- Extract all metadata (title, description, OG tags, favicons)
5. scrape_links -- Map all internal and external links
6. scrape_forms -- Identify any forms
7. scrape_text -- Extract the main content

Report on:
- Site structure (pages found, link graph)
- SEO metadata completeness
- robots.txt configuration
- Form inventory
- Content quality assessment"""


@mcp.prompt()
def scrape_guide(
    url: Annotated[str, "Target URL"],
    goal: Annotated[str, "What data to extract"],
) -> str:
    """Generate a prompt for scraping specific data from a website."""
    return f"""Help me scrape the following data from this website:

URL: {url}
Goal: {goal}

Approach:
1. First, use fetch_url to get the page content
2. Use scrape_metadata to understand the page structure
3. Try scrape_css with appropriate selectors to extract the target data
4. If the data is in a table, use scrape_table
5. If there are links to follow, use scrape_links to find them
6. For article content, use extract_article

If CSS selectors don't work well, try:
- Different selector strategies (class, id, tag hierarchy)
- scrape_text for general content extraction
- convert_html to get a cleaner view of the page structure

Return the extracted data in a structured format."""


@mcp.prompt()
def compare_pages(
    url1: Annotated[str, "First URL to compare"],
    url2: Annotated[str, "Second URL to compare"],
) -> str:
    """Generate a prompt for comparing the content of two web pages."""
    return f"""Compare the content and structure of these two web pages:

URL 1: {url1}
URL 2: {url2}

For each page:
1. Use fetch_url to get both pages
2. Use scrape_metadata to compare titles, descriptions, OG tags
3. Use scrape_text or extract_article to get the main content
4. Use scrape_links to compare link structures

Compare:
- Content similarity and differences
- Metadata completeness
- Page structure (headings, sections)
- Link profiles (internal vs external)
- Load performance (elapsed_ms)

Provide a structured comparison report."""
